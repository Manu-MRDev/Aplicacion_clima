"""Repositorios PostgreSQL: autenticación, sesiones, registros e integridad."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Iterable, Sequence

from psycopg.errors import UniqueViolation
from psycopg.types.json import Json, Jsonb

from app.core.config import Settings
from app.core.exceptions import ConflictError, DatabaseUnavailableError
from app.core.logging import get_logger
from app.core.time import as_utc, utcnow
from app.models.domain import IntegrityBlock, StoredRecord, User, WeatherRecord
from app.repositories.pool import PostgresManager
from app.repositories.schema import (
    ColumnInfo,
    SchemaMismatchError,
    TableProfile,
    pg_table_profile,
    quote_pg,
)
from app.services import integrity_service

logger = get_logger(__name__)

USER_TABLES = ("usuarios",)
SESSION_TABLES = ("session", "api_sessions")
RECORD_TABLES = ("Georreferencia", "georreferencia")
INTEGRITY_TABLES = ("cadena_bloques", "CadenaBloques")


@dataclass(frozen=True)
class SessionTableProfile:
    table: TableProfile
    sid: ColumnInfo
    payload: ColumnInfo
    expire: ColumnInfo
    payload_kind: str  # jsonb | json | text
    sid_is_uuid: bool

    @property
    def qualified_name(self) -> str:
        return self.table.qualified_name


@dataclass(frozen=True)
class PostgresSchema:
    users: TableProfile
    sessions: SessionTableProfile
    records: TableProfile
    records_map: dict[str, ColumnInfo]
    usuario_is_numeric: bool
    integrity: TableProfile | None
    integrity_map: dict[str, ColumnInfo] | None
    integrity_issue: str | None = None


RECORD_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id",),
    "usuario": ("usuario",),
    "nombre": ("nombre",),
    "paterno": ("paterno", "apellido_paterno"),
    "materno": ("materno", "apellido_materno"),
    "estado": ("estado",),
    "municipio": ("municipio",),
    "latitud": ("latitud", "lat"),
    "longitud": ("longitud", "lon", "lng"),
    "temperatura": ("temperatura", "temp"),
    "humedad": ("humedad",),
    "viento": ("viento", "velocidad_viento"),
    "fecha_hora": ("fechahora", "fecha_hora", "fecha"),
}

INTEGRITY_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "cadena": ("cadena", "chain", "chain_id"),
    "indice": ("indice", "index", "idx"),
    "registro_id": ("registro_id", "registroid", "record_id", "recordid"),
    "datos_canonicos": ("datos_canonicos", "datos", "canonical_data"),
    "hash_anterior": ("hash_anterior", "hashanterior", "prev_hash", "previous_hash"),
    "hash_actual": ("hash_actual", "hashactual", "hash", "current_hash"),
}

USER_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id",),
    "username": ("username", "usuario"),
    "password_hash": ("password_hash", "password"),
    "totp_secret_encrypted": ("totp_secret_encrypted",),
    "totp_enabled": ("totp_enabled",),
    "created_at": ("created_at",),
    "intentos_fallidos": ("intentos_fallidos",),
    "bloqueado_hasta": ("bloqueado_hasta",),
    "totp_ultimo_counter": ("totp_ultimo_counter",),
}


def _find_table(conn: Any, candidates: Sequence[str]) -> TableProfile | None:
    lowered = [candidate.lower() for candidate in candidates]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND lower(table_name) = ANY(%s)
            """,
            (lowered,),
        )
        rows = cur.fetchall()
    if not rows:
        return None
    by_lower: dict[str, list[tuple[str, str]]] = {}
    for schema, name in rows:
        by_lower.setdefault(name.lower(), []).append((schema, name))
    for candidate in candidates:
        matches = by_lower.get(candidate.lower(), [])
        if not matches:
            continue
        matches.sort(key=lambda item: (item[0] != "public", item[1] != candidate))
        schema, name = matches[0]
        return pg_table_profile(conn, schema, name)
    return None


class PostgresSchemaProvider:
    def __init__(self, manager: PostgresManager, settings: Settings) -> None:
        self._manager = manager
        self._settings = settings
        self._schema: PostgresSchema | None = None
        self._lock = threading.Lock()
        self._last_error: str | None = None

    def get(self) -> PostgresSchema:
        if self._schema is not None:
            return self._schema
        with self._lock:
            if self._schema is not None:
                return self._schema
            try:
                self._schema = self._load()
                self._last_error = None
            except SchemaMismatchError as exc:
                self._last_error = str(exc)
                logger.error("Esquema PostgreSQL incompatible: %s", exc)
                raise DatabaseUnavailableError() from exc
            return self._schema

    def invalidate(self) -> None:
        with self._lock:
            self._schema = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _load(self) -> PostgresSchema:
        with self._manager.connection() as conn:
            users = _find_table(conn, USER_TABLES)
            if users is None:
                raise SchemaMismatchError("no existe la tabla usuarios")
            for key, aliases in USER_COLUMN_ALIASES.items():
                users.require(key, *aliases)

            sessions_table = None
            for candidate in SESSION_TABLES:
                table = _find_table(conn, (candidate,))
                if table is None:
                    continue
                try:
                    sid = table.require("sid")
                    payload = table.require("sess", "payload")
                    expire = table.require("expire", "expires_at")
                except SchemaMismatchError:
                    logger.warning(
                        "Tabla de sesiones %s.%s no compatible; se busca alternativa",
                        table.schema,
                        table.name,
                    )
                    continue
                payload_kind = (
                    "jsonb"
                    if "jsonb" in payload.data_type
                    else "json"
                    if payload.data_type == "json"
                    else "text"
                )
                sessions_table = SessionTableProfile(
                    table=table,
                    sid=sid,
                    payload=payload,
                    expire=expire,
                    payload_kind=payload_kind,
                    sid_is_uuid=("uuid" in sid.data_type),
                )
                break
            if sessions_table is None:
                raise SchemaMismatchError(
                    "no existe una tabla de sesiones compatible (session/api_sessions)"
                )

            records = _find_table(conn, RECORD_TABLES)
            if records is None:
                raise SchemaMismatchError("no existe la tabla Georreferencia")
            records_map = {
                key: records.require(key, *aliases)
                for key, aliases in RECORD_COLUMN_ALIASES.items()
            }
            usuario_type = records_map["usuario"].data_type
            usuario_is_numeric = any(
                marker in usuario_type for marker in ("int", "numeric", "decimal")
            )

            integrity_table = _find_table(conn, INTEGRITY_TABLES)
            integrity_map: dict[str, ColumnInfo] | None = None
            integrity_issue: str | None = None
            if integrity_table is not None:
                try:
                    integrity_map = {
                        key: integrity_table.require(key, *aliases)
                        for key, aliases in INTEGRITY_COLUMN_ALIASES.items()
                    }
                except SchemaMismatchError as exc:
                    integrity_issue = str(exc)
                    logger.warning("Tabla de integridad incompatible: %s", exc)

            return PostgresSchema(
                users=users,
                sessions=sessions_table,
                records=records,
                records_map=records_map,
                usuario_is_numeric=usuario_is_numeric,
                integrity=integrity_table if integrity_map else None,
                integrity_map=integrity_map,
                integrity_issue=integrity_issue,
            )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="strict")
    return str(value)


class PostgresAuthRepository:
    def __init__(self, manager: PostgresManager, provider: PostgresSchemaProvider) -> None:
        self._manager = manager
        self._provider = provider

    def _table(self) -> TableProfile:
        return self._provider.get().users

    def _column_map(self, table: TableProfile) -> dict[str, ColumnInfo]:
        return {
            key: table.require(key, *aliases) for key, aliases in USER_COLUMN_ALIASES.items()
        }

    def _select_sql(self) -> tuple[str, list[ColumnInfo]]:
        table = self._table()
        cols = self._column_map(table)
        order = [
            "id",
            "username",
            "password_hash",
            "totp_secret_encrypted",
            "totp_enabled",
            "created_at",
            "intentos_fallidos",
            "bloqueado_hasta",
            "totp_ultimo_counter",
        ]
        selected = [cols[key] for key in order]
        select = ", ".join(quote_pg(column.name) for column in selected)
        sql = f"SELECT {select} FROM {table.qualified_name}"
        return sql, selected

    @staticmethod
    def _row_to_user(row: Sequence[Any]) -> User:
        (
            user_id,
            username,
            password_hash,
            totp_secret,
            totp_enabled,
            created_at,
            intentos,
            bloqueado,
            counter,
        ) = row
        return User(
            id=int(user_id),
            username=str(username),
            password_hash=_as_text(password_hash) or "",
            totp_secret_encrypted=_as_text(totp_secret),
            totp_enabled=bool(totp_enabled),
            created_at=as_utc(created_at) if isinstance(created_at, datetime) else None,
            intentos_fallidos=int(intentos or 0),
            bloqueado_hasta=as_utc(bloqueado) if isinstance(bloqueado, datetime) else None,
            totp_ultimo_counter=int(counter) if counter is not None else None,
        )

    def get_by_username(self, username: str) -> User | None:
        table = self._table()
        cols = self._column_map(table)
        base, _ = self._select_sql()
        sql = f"{base} WHERE {quote_pg(cols['username'].name)} = %s LIMIT 1"
        try:
            with self._manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (username,))
                    row = cur.fetchone()
        except SchemaMismatchError as exc:
            raise DatabaseUnavailableError() from exc
        return self._row_to_user(row) if row else None

    def create_user(self, username: str, password_hash: str) -> User:
        """Inserta un usuario sin TOTP. No se acepta id ni hash desde el cliente."""
        table = self._table()
        cols = self._column_map(table)
        _, selected = self._select_sql()
        returning = ", ".join(quote_pg(column.name) for column in selected)
        sql = (
            f"INSERT INTO {table.qualified_name} "
            f"({quote_pg(cols['username'].name)}, "
            f"{quote_pg(cols['password_hash'].name)}, "
            f"{quote_pg(cols['totp_enabled'].name)}, "
            f"{quote_pg(cols['created_at'].name)}, "
            f"{quote_pg(cols['intentos_fallidos'].name)}) "
            f"VALUES (%s, %s, FALSE, %s, 0) "
            f"RETURNING {returning}"
        )
        created_at = _db_datetime(utcnow(), cols["created_at"])
        try:
            with self._manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (username, password_hash, created_at))
                    row = cur.fetchone()
        except UniqueViolation as exc:
            raise ConflictError("El nombre de usuario ya está en uso") from exc
        if row is None:
            raise ConflictError("No fue posible crear el usuario")
        return self._row_to_user(row)

    def get_by_id(self, user_id: int) -> User | None:
        table = self._table()
        cols = self._column_map(table)
        base, _ = self._select_sql()
        sql = f"{base} WHERE {quote_pg(cols['id'].name)} = %s LIMIT 1"
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
        return self._row_to_user(row) if row else None

    def record_failed_attempt(self, user_id: int, max_attempts: int, lockout_seconds: int) -> int:
        table = self._table()
        cols = self._column_map(table)
        failed = quote_pg(cols["intentos_fallidos"].name)
        blocked = quote_pg(cols["bloqueado_hasta"].name)
        ident = quote_pg(cols["id"].name)
        lock_until = utcnow() + timedelta(seconds=lockout_seconds)
        sql = (
            f"UPDATE {table.qualified_name} SET "
            f"{failed} = COALESCE({failed}, 0) + 1, "
            f"{blocked} = CASE WHEN COALESCE({failed}, 0) + 1 >= %s THEN %s ELSE {blocked} END "
            f"WHERE {ident} = %s RETURNING COALESCE({failed}, 0)"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (max_attempts, lock_until, user_id))
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def record_success(self, user_id: int, new_password_hash: str | None = None) -> None:
        table = self._table()
        cols = self._column_map(table)
        failed = quote_pg(cols["intentos_fallidos"].name)
        blocked = quote_pg(cols["bloqueado_hasta"].name)
        ident = quote_pg(cols["id"].name)
        assignments = [f"{failed} = 0", f"{blocked} = NULL"]
        params: list[Any] = []
        if new_password_hash is not None:
            assignments.append(f"{quote_pg(cols['password_hash'].name)} = %s")
            params.append(new_password_hash)
        params.append(user_id)
        sql = f"UPDATE {table.qualified_name} SET {', '.join(assignments)} WHERE {ident} = %s"
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def confirm_totp_enrollment(
        self, user_id: int, encrypted_secret: str, counter: int
    ) -> bool:
        """Activa TOTP de forma atómica y rechaza reutilizar un contador."""
        table = self._table()
        cols = self._column_map(table)
        counter_col = quote_pg(cols["totp_ultimo_counter"].name)
        sql = (
            f"UPDATE {table.qualified_name} SET "
            f"{quote_pg(cols['totp_secret_encrypted'].name)} = %s, "
            f"{quote_pg(cols['totp_enabled'].name)} = TRUE, "
            f"{counter_col} = %s, "
            f"{quote_pg(cols['intentos_fallidos'].name)} = 0, "
            f"{quote_pg(cols['bloqueado_hasta'].name)} = NULL "
            f"WHERE {quote_pg(cols['id'].name)} = %s "
            f"AND ({counter_col} IS NULL OR {counter_col} < %s) "
            f"RETURNING {quote_pg(cols['id'].name)}"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (encrypted_secret, counter, user_id, counter))
                return cur.fetchone() is not None

    def advance_totp_counter(self, user_id: int, counter: int) -> bool:
        table = self._table()
        cols = self._column_map(table)
        sql = (
            f"UPDATE {table.qualified_name} SET "
            f"{quote_pg(cols['totp_ultimo_counter'].name)} = %s "
            f"WHERE {quote_pg(cols['id'].name)} = %s "
            f"AND ({quote_pg(cols['totp_ultimo_counter'].name)} IS NULL "
            f"OR {quote_pg(cols['totp_ultimo_counter'].name)} < %s) "
            f"RETURNING {quote_pg(cols['id'].name)}"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (counter, user_id, counter))
                return cur.fetchone() is not None


def _encode_payload(payload: dict[str, Any], kind: str) -> Any:
    if kind == "jsonb":
        return Jsonb(payload)
    if kind == "json":
        return Json(payload)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _decode_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


class PostgresSessionStore:
    def __init__(self, manager: PostgresManager, provider: PostgresSchemaProvider) -> None:
        self._manager = manager
        self._provider = provider

    def _profile(self) -> SessionTableProfile:
        return self._provider.get().sessions

    def create(self, sid: str | Any, payload: dict[str, Any], expires_at: datetime) -> None:
        profile = self._profile()
        sql = (
            f"INSERT INTO {profile.qualified_name} "
            f"({quote_pg(profile.sid.name)}, {quote_pg(profile.payload.name)}, "
            f"{quote_pg(profile.expire.name)}) VALUES (%s, %s, %s)"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (sid, _encode_payload(payload, profile.payload_kind), expires_at))

    def get(self, sid: str | Any) -> dict[str, Any] | None:
        profile = self._profile()
        sql = (
            f"SELECT {quote_pg(profile.payload.name)}, {quote_pg(profile.expire.name)} "
            f"FROM {profile.qualified_name} WHERE {quote_pg(profile.sid.name)} = %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (sid,))
                row = cur.fetchone()
                if row is None:
                    return None
                payload = _decode_payload(row[0])
                expires_at = as_utc(row[1]) if isinstance(row[1], datetime) else None
                if expires_at is None or expires_at <= utcnow():
                    cur.execute(
                        f"DELETE FROM {profile.qualified_name} "
                        f"WHERE {quote_pg(profile.sid.name)} = %s",
                        (sid,),
                    )
                    return None
        return payload

    def update(self, sid: str | Any, payload: dict[str, Any], expires_at: datetime) -> bool:
        profile = self._profile()
        sql = (
            f"UPDATE {profile.qualified_name} SET "
            f"{quote_pg(profile.payload.name)} = %s, {quote_pg(profile.expire.name)} = %s "
            f"WHERE {quote_pg(profile.sid.name)} = %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql, (_encode_payload(payload, profile.payload_kind), expires_at, sid)
                )
                return cur.rowcount > 0

    def delete(self, sid: str | Any) -> bool:
        profile = self._profile()
        sql = (
            f"DELETE FROM {profile.qualified_name} "
            f"WHERE {quote_pg(profile.sid.name)} = %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (sid,))
                return cur.rowcount > 0

    def rotate(
        self,
        old_sid: str | Any,
        new_sid: str | Any,
        payload: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        profile = self._profile()
        insert_sql = (
            f"INSERT INTO {profile.qualified_name} "
            f"({quote_pg(profile.sid.name)}, {quote_pg(profile.payload.name)}, "
            f"{quote_pg(profile.expire.name)}) VALUES (%s, %s, %s)"
        )
        delete_sql = (
            f"DELETE FROM {profile.qualified_name} "
            f"WHERE {quote_pg(profile.sid.name)} = %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(delete_sql, (old_sid,))
                cur.execute(
                    insert_sql,
                    (new_sid, _encode_payload(payload, profile.payload_kind), expires_at),
                )

    def delete_expired(self) -> int:
        profile = self._profile()
        sql = (
            f"DELETE FROM {profile.qualified_name} "
            f"WHERE {quote_pg(profile.expire.name)} <= %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (utcnow(),))
                return cur.rowcount


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _db_datetime(value: datetime | None, column: ColumnInfo) -> datetime | None:
    """Adapta un instante UTC al tipo real de la columna.

    Las columnas ``timestamp``/``datetime2`` no guardan zona: se envía UTC naive
    para que el servidor no aplique una conversión dependiente de su TimeZone.
    """
    if value is None:
        return None
    normalized = as_utc(value)
    assert normalized is not None
    if "timestamptz" in column.data_type or "timestamp with" in column.data_type:
        return normalized
    return normalized.replace(tzinfo=None)


class PostgresRecordsRepository:
    servidor = "ubuntu"
    chain_id = "api-ubuntu"

    def __init__(
        self,
        manager: PostgresManager,
        provider: PostgresSchemaProvider,
        integrity: "PostgresIntegrityRepository | None" = None,
    ) -> None:
        self._manager = manager
        self._provider = provider
        self._integrity = integrity

    def _schema(self) -> PostgresSchema:
        return self._provider.get()

    def usuario_value(self, user_id: int, username: str) -> Any:
        return user_id if self._schema().usuario_is_numeric else username

    @property
    def usuario_is_numeric(self) -> bool:
        return self._schema().usuario_is_numeric

    def resolve_usuario_filter(self, username: str) -> Any | None:
        """Traduce un username a una clave de filtro viable para la columna real."""
        schema = self._schema()
        if not schema.usuario_is_numeric:
            return username
        try:
            with self._manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {quote_pg(schema.users.find('id').name)} FROM "
                        f"{schema.users.qualified_name} WHERE "
                        f"{quote_pg(schema.users.find('username', 'usuario').name)} = %s LIMIT 1",
                        (username,),
                    )
                    row = cur.fetchone()
        except Exception:
            return None
        return int(row[0]) if row else None

    def _columns(self) -> tuple[PostgresSchema, dict[str, ColumnInfo]]:
        schema = self._schema()
        return schema, schema.records_map

    def insert(
        self, record: WeatherRecord, *, usuario_value: Any, with_integrity: bool = False
    ) -> tuple[StoredRecord, IntegrityBlock | None]:
        schema, cols = self._columns()
        table = schema.records
        insert_keys = [
            "usuario",
            "nombre",
            "paterno",
            "materno",
            "estado",
            "municipio",
            "latitud",
            "longitud",
            "temperatura",
            "humedad",
            "viento",
            "fecha_hora",
        ]
        column_names = [quote_pg(cols[key].name) for key in insert_keys]
        placeholders = ", ".join(["%s"] * len(insert_keys))
        sql = (
            f"INSERT INTO {table.qualified_name} ({', '.join(column_names)}) "
            f"VALUES ({placeholders}) RETURNING {quote_pg(cols['id'].name)}"
        )
        fecha = _db_datetime(record.fecha_hora, cols["fecha_hora"])
        values: list[Any] = [
            usuario_value,
            record.nombre,
            record.paterno,
            record.materno,
            record.estado,
            record.municipio,
            record.latitud,
            record.longitud,
            record.temperatura,
            record.humedad,
            record.viento,
            fecha,
        ]
        block: IntegrityBlock | None = None
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                row = cur.fetchone()
                if row is None:
                    raise DatabaseUnavailableError()
                record_id = int(row[0])
                if with_integrity and self._integrity is not None:
                    block = self._integrity.append_with_cursor(
                        cur, record=record, record_id=record_id
                    )
        stored = StoredRecord(
            id=record_id,
            usuario=record.usuario,
            nombre=record.nombre,
            paterno=record.paterno,
            materno=record.materno,
            estado=record.estado,
            municipio=record.municipio,
            latitud=record.latitud,
            longitud=record.longitud,
            temperatura=record.temperatura,
            humedad=record.humedad,
            viento=record.viento,
            fecha_hora=record.fecha_hora,
            servidor=self.servidor,
        )
        return stored, block

    def _select_columns(self, cols: dict[str, ColumnInfo]) -> str:
        return ", ".join(quote_pg(cols[key].name) for key in RECORD_COLUMN_ALIASES)

    def _row_to_record(self, row: Sequence[Any], cols: dict[str, ColumnInfo]) -> StoredRecord:
        values = dict(zip(RECORD_COLUMN_ALIASES, row))
        return StoredRecord(
            id=int(values["id"]),
            usuario=str(values["usuario"]) if values["usuario"] is not None else "",
            nombre=str(values["nombre"] or ""),
            paterno=values["paterno"],
            materno=values["materno"],
            estado=str(values["estado"] or ""),
            municipio=str(values["municipio"] or ""),
            latitud=_decimal(values["latitud"]),
            longitud=_decimal(values["longitud"]),
            temperatura=_decimal(values["temperatura"]),
            humedad=_decimal(values["humedad"]),
            viento=_decimal(values["viento"]),
            fecha_hora=as_utc(values["fecha_hora"]),
            servidor=self.servidor,
        )

    def list_records(
        self,
        *,
        limit: int,
        offset: int,
        order_desc: bool,
        order_field: str,
        usuario_filter: Any | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> tuple[list[StoredRecord], bool]:
        schema, cols = self._columns()
        select = self._select_columns(cols)
        where: list[str] = []
        params: list[Any] = []
        if usuario_filter is not None:
            where.append(f"{quote_pg(cols['usuario'].name)} = %s")
            params.append(usuario_filter)
        if desde is not None:
            where.append(f"{quote_pg(cols['fecha_hora'].name)} >= %s")
            params.append(_db_datetime(desde, cols["fecha_hora"]))
        if hasta is not None:
            where.append(f"{quote_pg(cols['fecha_hora'].name)} <= %s")
            params.append(_db_datetime(hasta, cols["fecha_hora"]))
        order_column = quote_pg(cols[order_field].name)
        direction = "DESC" if order_desc else "ASC"
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        sql = (
            f"SELECT {select} FROM {schema.records.qualified_name}{clause} "
            f"ORDER BY {order_column} {direction}, {quote_pg(cols['id'].name)} {direction} "
            f"LIMIT %s OFFSET %s"
        )
        params.extend([limit + 1, offset])
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        has_more = len(rows) > limit
        return [self._row_to_record(row, cols) for row in rows[:limit]], has_more

    def get_record(self, record_id: int) -> StoredRecord | None:
        schema, cols = self._columns()
        sql = (
            f"SELECT {self._select_columns(cols)} FROM {schema.records.qualified_name} "
            f"WHERE {quote_pg(cols['id'].name)} = %s LIMIT 1"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (record_id,))
                row = cur.fetchone()
        return self._row_to_record(row, cols) if row else None

    def all_records(self, *, max_records: int = 50000) -> list[StoredRecord]:
        schema, cols = self._columns()
        sql = (
            f"SELECT {self._select_columns(cols)} FROM {schema.records.qualified_name} "
            f"ORDER BY {quote_pg(cols['id'].name)} ASC LIMIT %s"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (max_records + 1,))
                rows = cur.fetchall()
        if len(rows) > max_records:
            raise DatabaseUnavailableError(
                "La tabla de registros supera el límite configurado para verificación"
            )
        return [self._row_to_record(row, cols) for row in rows]

    def integrity_available(self) -> bool:
        schema = self._schema()
        return schema.integrity is not None and schema.integrity_map is not None

    def integrity_issue(self) -> str | None:
        return self._schema().integrity_issue

    @property
    def integrity_repository(self) -> "PostgresIntegrityRepository":
        if self._integrity is None:
            raise DatabaseUnavailableError()
        return self._integrity


class PostgresIntegrityRepository:
    def __init__(
        self,
        manager: PostgresManager,
        provider: PostgresSchemaProvider,
        records_repo_getter: Callable[[], PostgresRecordsRepository] | None = None,
    ) -> None:
        self._manager = manager
        self._provider = provider
        self._records_repo_getter = records_repo_getter
        self.chain_id = "api-ubuntu"

    def _parts(self) -> tuple[PostgresSchema, TableProfile, dict[str, ColumnInfo]]:
        schema = self._provider.get()
        if schema.integrity is None or schema.integrity_map is None:
            raise DatabaseUnavailableError()
        return schema, schema.integrity, schema.integrity_map

    def append_with_cursor(
        self,
        cur: Any,
        *,
        record: WeatherRecord,
        record_id: int,
    ) -> IntegrityBlock:
        schema, table, cols = self._parts()
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (self.chain_id,))
        cur.execute(
            f"SELECT {quote_pg(cols['indice'].name)}, {quote_pg(cols['hash_actual'].name)} "
            f"FROM {table.qualified_name} WHERE {quote_pg(cols['cadena'].name)} = %s "
            f"ORDER BY {quote_pg(cols['indice'].name)} DESC LIMIT 1",
            (self.chain_id,),
        )
        last = cur.fetchone()
        indice = int(last[0]) + 1 if last else 0
        hash_anterior = str(last[1]).strip() if last else integrity_service.GENESIS_HASH

        datos = integrity_service.canonical_record_json(
            record, servidor="ubuntu", record_id=record_id
        )
        hash_actual = integrity_service.compute_block_hash(
            cadena=self.chain_id,
            indice=indice,
            registro_id=record_id,
            datos_canonicos=datos,
            hash_anterior=hash_anterior,
        )
        insert_cols = [
            quote_pg(cols["cadena"].name),
            quote_pg(cols["indice"].name),
            quote_pg(cols["registro_id"].name),
            quote_pg(cols["datos_canonicos"].name),
            quote_pg(cols["hash_anterior"].name),
            quote_pg(cols["hash_actual"].name),
        ]
        data_column = cols["datos_canonicos"]
        stored_data: Any = datos
        if "jsonb" in data_column.data_type:
            stored_data = Jsonb(json.loads(datos))
        elif data_column.data_type == "json":
            stored_data = Json(json.loads(datos))
        values: list[Any] = [
            self.chain_id,
            indice,
            record_id,
            stored_data,
            hash_anterior,
            hash_actual,
        ]
        if table.has("creado_en", "created_at", "fecha_creacion"):
            created = table.require("creado_en", "created_at", "fecha_creacion")
            insert_cols.append(quote_pg(created.name))
            values.append(_db_datetime(utcnow(), created))
        cur.execute(
            f"INSERT INTO {table.qualified_name} ({', '.join(insert_cols)}) "
            f"VALUES ({', '.join(['%s'] * len(values))})",
            values,
        )
        return IntegrityBlock(
            cadena=self.chain_id,
            indice=indice,
            registro_id=record_id,
            datos_canonicos=datos,
            hash_anterior=hash_anterior,
            hash_actual=hash_actual,
            creado_en=utcnow(),
        )

    def fetch_blocks(self) -> list[IntegrityBlock]:
        schema, table, cols = self._parts()
        select_parts = [
            quote_pg(cols["cadena"].name),
            quote_pg(cols["indice"].name),
            quote_pg(cols["registro_id"].name),
            quote_pg(cols["datos_canonicos"].name),
            quote_pg(cols["hash_anterior"].name),
            quote_pg(cols["hash_actual"].name),
        ]
        created = table.find("creado_en", "created_at", "fecha_creacion")
        if created:
            select_parts.append(quote_pg(created.name))
        sql = (
            f"SELECT {', '.join(select_parts)} FROM {table.qualified_name} "
            f"WHERE {quote_pg(cols['cadena'].name)} = %s "
            f"ORDER BY {quote_pg(cols['indice'].name)} ASC"
        )
        with self._manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (self.chain_id,))
                rows = cur.fetchall()
        blocks: list[IntegrityBlock] = []
        for row in rows:
            raw_data = row[3]
            if isinstance(raw_data, dict):
                datos = integrity_service.canonical_json(raw_data)
            elif isinstance(raw_data, (bytes, bytearray, memoryview)):
                datos = bytes(raw_data).decode("utf-8")
            else:
                datos = str(raw_data)
            blocks.append(
                IntegrityBlock(
                    cadena=str(row[0]),
                    indice=int(row[1]),
                    registro_id=int(row[2]),
                    datos_canonicos=datos,
                    hash_anterior=str(row[4]).strip() if row[4] is not None else None,
                    hash_actual=str(row[5]).strip(),
                    creado_en=as_utc(row[6]) if len(row) > 6 else None,
                )
            )
        return blocks
