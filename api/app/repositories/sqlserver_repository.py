"""Repositorio de registros e integridad para SQL Server (PyODBC)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from app.core.exceptions import DatabaseUnavailableError
from app.core.logging import get_logger
from app.core.time import as_utc, utcnow
from app.models.domain import IntegrityBlock, StoredRecord, WeatherRecord
from app.repositories.pool import SqlServerManager
from app.repositories.postgres_repository import RECORD_COLUMN_ALIASES, INTEGRITY_COLUMN_ALIASES
from app.repositories.schema import (
    ColumnInfo,
    SchemaMismatchError,
    TableProfile,
    mssql_table_profile,
    quote_mssql,
)
from app.services import integrity_service

logger = get_logger(__name__)

RECORD_TABLES = ("Georreferencia", "georreferencia")
INTEGRITY_TABLES = ("CadenaBloques", "cadena_bloques")


def _qualified(profile: TableProfile) -> str:
    return f"{quote_mssql(profile.schema)}.{quote_mssql(profile.name)}"


def _find_table(cursor: Any, candidates: Sequence[str]) -> TableProfile | None:
    for candidate in candidates:
        profile = mssql_table_profile(cursor, "dbo", candidate)
        if profile is not None:
            return profile
    return None


@dataclass(frozen=True)
class SqlServerSchema:
    records: TableProfile
    records_map: dict[str, ColumnInfo]
    usuario_is_numeric: bool
    integrity: TableProfile | None
    integrity_map: dict[str, ColumnInfo] | None
    integrity_issue: str | None = None


class SqlServerSchemaProvider:
    def __init__(self, manager: SqlServerManager) -> None:
        self._manager = manager
        self._schema: SqlServerSchema | None = None
        self._lock = threading.Lock()
        self._last_error: str | None = None

    def get(self) -> SqlServerSchema:
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
                logger.error("Esquema SQL Server incompatible: %s", exc)
                raise DatabaseUnavailableError() from exc
            return self._schema

    def invalidate(self) -> None:
        with self._lock:
            self._schema = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _load(self) -> SqlServerSchema:
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                records = _find_table(cursor, RECORD_TABLES)
                if records is None:
                    raise SchemaMismatchError("no existe dbo.Georreferencia")
                records_map = {
                    key: records.require(key, *aliases)
                    for key, aliases in RECORD_COLUMN_ALIASES.items()
                }
                if not records_map["id"].is_identity:
                    raise SchemaMismatchError("la columna Id de Georreferencia no es IDENTITY")
                usuario_type = records_map["usuario"].data_type
                usuario_is_numeric = any(
                    marker in usuario_type for marker in ("int", "numeric", "decimal")
                )

                integrity = _find_table(cursor, INTEGRITY_TABLES)
                integrity_map: dict[str, ColumnInfo] | None = None
                integrity_issue: str | None = None
                if integrity is not None:
                    try:
                        integrity_map = {
                            key: integrity.require(key, *aliases)
                            for key, aliases in INTEGRITY_COLUMN_ALIASES.items()
                        }
                    except SchemaMismatchError as exc:
                        integrity_issue = str(exc)
                        logger.warning("Tabla de integridad SQL Server incompatible: %s", exc)
            finally:
                cursor.close()
        return SqlServerSchema(
            records=records,
            records_map=records_map,
            usuario_is_numeric=usuario_is_numeric,
            integrity=integrity if integrity_map else None,
            integrity_map=integrity_map,
            integrity_issue=integrity_issue,
        )


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class SqlServerRecordsRepository:
    servidor = "windows"
    chain_id = "api-windows"

    def __init__(self, manager: SqlServerManager, provider: SqlServerSchemaProvider) -> None:
        self._manager = manager
        self._provider = provider
        self.integrity = SqlServerIntegrityRepository(manager, provider)

    def _schema(self) -> SqlServerSchema:
        return self._provider.get()

    def usuario_value(self, user_id: int, username: str) -> Any:
        return user_id if self._schema().usuario_is_numeric else username

    @property
    def usuario_is_numeric(self) -> bool:
        return self._schema().usuario_is_numeric

    def insert(
        self, record: WeatherRecord, *, usuario_value: Any, with_integrity: bool
    ) -> tuple[StoredRecord, IntegrityBlock | None]:
        schema = self._schema()
        cols = schema.records_map
        keys = [
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
        column_names = ", ".join(quote_mssql(cols[key].name) for key in keys)
        placeholders = ", ".join(["?"] * len(keys))
        sql = (
            f"SET NOCOUNT ON; INSERT INTO {_qualified(schema.records)} ({column_names}) "
            f"OUTPUT INSERTED.{quote_mssql(cols['id'].name)} "
            f"VALUES ({placeholders})"
        )
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
            (as_utc(record.fecha_hora) or record.fecha_hora).replace(tzinfo=None),
        ]
        block: IntegrityBlock | None = None
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, values)
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseUnavailableError()
                record_id = int(row[0])
                if with_integrity:
                    block = self.integrity.append_with_cursor(
                        cursor, record=record, record_id=record_id
                    )
            finally:
                cursor.close()
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

    def _select_sql(self, cols: dict[str, ColumnInfo]) -> str:
        return ", ".join(quote_mssql(cols[key].name) for key in RECORD_COLUMN_ALIASES)

    def _row_to_record(self, row: Sequence[Any]) -> StoredRecord:
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
            fecha_hora=as_utc(values["fecha_hora"])
            if isinstance(values["fecha_hora"], datetime)
            else None,
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
        schema = self._schema()
        cols = schema.records_map
        select = self._select_sql(cols)
        where: list[str] = []
        params: list[Any] = []
        if usuario_filter is not None:
            where.append(f"{quote_mssql(cols['usuario'].name)} = ?")
            params.append(usuario_filter)
        if desde is not None:
            where.append(f"{quote_mssql(cols['fecha_hora'].name)} >= ?")
            params.append((as_utc(desde) or desde).replace(tzinfo=None))
        if hasta is not None:
            where.append(f"{quote_mssql(cols['fecha_hora'].name)} <= ?")
            params.append((as_utc(hasta) or hasta).replace(tzinfo=None))
        direction = "DESC" if order_desc else "ASC"
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        order_column = quote_mssql(cols[order_field].name)
        id_column = quote_mssql(cols["id"].name)
        sql = (
            f"SELECT {select} FROM {_qualified(schema.records)}{clause} "
            f"ORDER BY {order_column} {direction}, {id_column} {direction} "
            f"OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        params.extend([offset, limit + 1])
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        has_more = len(rows) > limit
        return [self._row_to_record(row) for row in rows[:limit]], has_more

    def get_record(self, record_id: int) -> StoredRecord | None:
        schema = self._schema()
        cols = schema.records_map
        sql = (
            f"SELECT TOP 1 {self._select_sql(cols)} FROM {_qualified(schema.records)} "
            f"WHERE {quote_mssql(cols['id'].name)} = ?"
        )
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (record_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        return self._row_to_record(row) if row else None

    def all_records(self, *, max_records: int = 50000) -> list[StoredRecord]:
        schema = self._schema()
        cols = schema.records_map
        sql = (
            f"SELECT {self._select_sql(cols)} FROM {_qualified(schema.records)} "
            f"ORDER BY {quote_mssql(cols['id'].name)} ASC "
            f"OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
        )
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (max_records + 1,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        if len(rows) > max_records:
            raise DatabaseUnavailableError("La tabla supera el límite para verificación")
        return [self._row_to_record(row) for row in rows]

    def integrity_available(self) -> bool:
        schema = self._schema()
        return schema.integrity is not None and schema.integrity_map is not None

    def integrity_issue(self) -> str | None:
        return self._schema().integrity_issue

    @property
    def integrity_repository(self) -> "SqlServerIntegrityRepository":
        return self.integrity


class SqlServerIntegrityRepository:
    def __init__(self, manager: SqlServerManager, provider: SqlServerSchemaProvider) -> None:
        self._manager = manager
        self._provider = provider
        self.chain_id = "api-windows"

    def _parts(self) -> tuple[SqlServerSchema, TableProfile, dict[str, ColumnInfo]]:
        schema = self._provider.get()
        if schema.integrity is None or schema.integrity_map is None:
            raise DatabaseUnavailableError()
        return schema, schema.integrity, schema.integrity_map

    def append_with_cursor(
        self, cursor: Any, *, record: WeatherRecord, record_id: int
    ) -> IntegrityBlock:
        schema, table, cols = self._parts()
        cursor.execute(
            f"SELECT TOP 1 {quote_mssql(cols['indice'].name)}, "
            f"{quote_mssql(cols['hash_actual'].name)} "
            f"FROM {_qualified(table)} WITH (UPDLOCK, HOLDLOCK) "
            f"WHERE {quote_mssql(cols['cadena'].name)} = ? "
            f"ORDER BY {quote_mssql(cols['indice'].name)} DESC",
            (self.chain_id,),
        )
        last = cursor.fetchone()
        indice = int(last[0]) + 1 if last else 0
        hash_anterior = str(last[1]).strip() if last else integrity_service.GENESIS_HASH
        datos = integrity_service.canonical_record_json(
            record, servidor="windows", record_id=record_id
        )
        hash_actual = integrity_service.compute_block_hash(
            cadena=self.chain_id,
            indice=indice,
            registro_id=record_id,
            datos_canonicos=datos,
            hash_anterior=hash_anterior,
        )
        insert_keys = [
            "cadena",
            "indice",
            "registro_id",
            "datos_canonicos",
            "hash_anterior",
            "hash_actual",
        ]
        insert_cols = [quote_mssql(cols[key].name) for key in insert_keys]
        values: list[Any] = [
            self.chain_id,
            indice,
            record_id,
            datos,
            hash_anterior,
            hash_actual,
        ]
        created = table.find("creado_en", "created_at", "fecha_creacion")
        if created is not None:
            insert_cols.append(quote_mssql(created.name))
            now = utcnow()
            values.append(
                now if "datetimeoffset" in created.data_type else now.replace(tzinfo=None)
            )
        cursor.execute(
            f"SET NOCOUNT ON; INSERT INTO {_qualified(table)} ({', '.join(insert_cols)}) "
            f"VALUES ({', '.join(['?'] * len(values))})",
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
        parts = [quote_mssql(cols[key].name) for key in (
            "cadena",
            "indice",
            "registro_id",
            "datos_canonicos",
            "hash_anterior",
            "hash_actual",
        )]
        created = table.find("creado_en", "created_at", "fecha_creacion")
        if created is not None:
            parts.append(quote_mssql(created.name))
        sql = (
            f"SELECT {', '.join(parts)} FROM {_qualified(table)} "
            f"WHERE {quote_mssql(cols['cadena'].name)} = ? "
            f"ORDER BY {quote_mssql(cols['indice'].name)} ASC"
        )
        with self._manager.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (self.chain_id,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [
            IntegrityBlock(
                cadena=str(row[0]),
                indice=int(row[1]),
                registro_id=int(row[2]),
                datos_canonicos=str(row[3]),
                hash_anterior=str(row[4]).strip() if row[4] is not None else None,
                hash_actual=str(row[5]).strip(),
                creado_en=as_utc(row[6]) if len(row) > 6 else None,
            )
            for row in rows
        ]
