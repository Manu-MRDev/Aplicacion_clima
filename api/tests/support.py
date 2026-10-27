"""Utilidades compartidas por las pruebas (sin bases de datos ni red real)."""

from __future__ import annotations

import base64
import copy
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.time import utcnow
from app.models.domain import StoredRecord, User


def _key(byte: bytes) -> str:
    return base64.urlsafe_b64encode(byte * 32).decode("ascii")


def make_settings(**overrides: Any) -> Settings:
    """Configuración determinista; nunca lee el .env real."""
    values: dict[str, Any] = {
        "app_name": "Clima API Test",
        "app_env": "development",
        "debug": False,
        "docs_enabled": True,
        "log_level": "WARNING",
        "allowed_hosts": ["testserver", "localhost", "127.0.0.1"],
        "cors_origins": ["http://frontend.test"],
        "session_secret_key": _key(b"s"),
        "totp_encryption_key": _key(b"t"),
        "record_encryption_key": _key(b"r"),
        "postgres_host": "127.0.0.1",
        "postgres_password": "pg-test",
        "sqlserver_host": "127.0.0.1",
        "sqlserver_password": "ms-test",
        "geocoding_user_agent": "Clima-API-Test/1.0 (test@example.invalid)",
        "session_secure_cookies": None,
        "weather_cache_ttl_seconds": 0,
        "geocoding_cache_ttl_seconds": 0,
        "geocoding_min_interval_seconds": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class MemorySessionStore:
    """Implementación en memoria con la misma semántica que el store PostgreSQL."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[dict[str, Any], datetime]] = {}

    def create(self, sid, payload: dict[str, Any], expires_at: datetime) -> None:
        self.rows[str(sid)] = (copy.deepcopy(payload), expires_at)

    def get(self, sid) -> dict[str, Any] | None:
        row = self.rows.get(str(sid))
        if row is None:
            return None
        payload, expires_at = row
        if expires_at <= utcnow():
            self.rows.pop(str(sid), None)
            return None
        return copy.deepcopy(payload)

    def update(self, sid, payload: dict[str, Any], expires_at: datetime) -> bool:
        if str(sid) not in self.rows:
            return False
        self.rows[str(sid)] = (copy.deepcopy(payload), expires_at)
        return True

    def delete(self, sid) -> bool:
        return self.rows.pop(str(sid), None) is not None

    def rotate(self, old_sid, new_sid, payload: dict[str, Any], expires_at: datetime) -> None:
        self.rows.pop(str(old_sid), None)
        self.create(new_sid, payload, expires_at)


class FakeProvider:
    """Proveedor de esquema mínimo para SessionService."""

    def __init__(self, *, sid_is_uuid: bool = False) -> None:
        self._schema = SimpleNamespace(
            sessions=SimpleNamespace(sid_is_uuid=sid_is_uuid),
        )

    def get(self):
        return self._schema


class FakeAuthRepository:
    """Repositorio de usuarios en memoria con bloqueo y contadores TOTP."""

    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}
        self.failed_attempts = 0
        self.successes = 0

    def get_by_username(self, username: str) -> User | None:
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def create_user(self, username: str, password_hash: str) -> User:
        if self.get_by_username(username) is not None:
            from app.core.exceptions import ConflictError

            raise ConflictError("El nombre de usuario ya está en uso")
        user_id = max(self.users, default=0) + 1
        user = User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            totp_secret_encrypted=None,
            totp_enabled=False,
            created_at=utcnow(),
        )
        self.users[user_id] = user
        return user

    def record_failed_attempt(
        self, user_id: int, max_attempts: int, lockout_seconds: int
    ) -> int:
        user = self.users[user_id]
        attempts = user.intentos_fallidos + 1
        blocked = (
            utcnow() + timedelta(seconds=lockout_seconds)
            if attempts >= max_attempts
            else user.bloqueado_hasta
        )
        self.users[user_id] = replace(
            user, intentos_fallidos=attempts, bloqueado_hasta=blocked
        )
        self.failed_attempts += 1
        return attempts

    def record_success(self, user_id: int, new_password_hash: str | None = None) -> None:
        user = self.users[user_id]
        self.users[user_id] = replace(
            user,
            intentos_fallidos=0,
            bloqueado_hasta=None,
            password_hash=new_password_hash or user.password_hash,
        )
        self.successes += 1

    def confirm_totp_enrollment(
        self, user_id: int, encrypted_secret: str, counter: int
    ) -> bool:
        user = self.users[user_id]
        if user.totp_enabled:
            return False
        self.users[user_id] = replace(
            user,
            totp_secret_encrypted=encrypted_secret,
            totp_enabled=True,
            totp_ultimo_counter=counter,
            intentos_fallidos=0,
            bloqueado_hasta=None,
        )
        return True

    def advance_totp_counter(self, user_id: int, counter: int) -> bool:
        user = self.users[user_id]
        if user.totp_ultimo_counter is not None and counter <= user.totp_ultimo_counter:
            return False
        self.users[user_id] = replace(user, totp_ultimo_counter=counter)
        return True


def stored_record(
    *,
    record_id: int = 1,
    usuario: str = "ana",
    servidor: str = "ubuntu",
    fecha_hora: datetime | None = None,
) -> StoredRecord:
    return StoredRecord(
        id=record_id,
        usuario=usuario,
        nombre="Ana",
        paterno="Pérez",
        materno="López",
        estado="Ciudad de México",
        municipio="Coyoacán",
        latitud=None,
        longitud=None,
        temperatura=None,
        humedad=None,
        viento=None,
        fecha_hora=fecha_hora or utcnow(),
        servidor=servidor,
    )


class FakeRecordsRepository:
    """Repositorio de registros configurable para el servicio."""

    def __init__(
        self,
        *,
        servidor: str = "ubuntu",
        chain_id: str = "api-ubuntu",
        numeric_user: bool = False,
        integrity: bool = True,
        issue: str | None = None,
        records: list[StoredRecord] | None = None,
        fail: bool = False,
    ) -> None:
        self.servidor = servidor
        self.chain_id = chain_id
        self.usuario_is_numeric = numeric_user
        self._integrity = integrity
        self._issue = issue
        self.records = records or []
        self.fail = fail
        self.inserted: list[tuple[Any, bool]] = []
        self.last_filters: dict[str, Any] = {}

    def usuario_value(self, user_id: int, username: str) -> Any:
        return user_id if self.usuario_is_numeric else username

    def integrity_available(self) -> bool:
        return self._integrity

    def integrity_issue(self) -> str | None:
        return self._issue

    def insert(self, record, *, usuario_value, with_integrity: bool):
        from app.models.domain import IntegrityBlock
        from app.services.integrity_service import GENESIS_HASH

        self.inserted.append((record, with_integrity))
        stored = stored_record(
            record_id=99,
            usuario=str(usuario_value),
            servidor=self.servidor,
            fecha_hora=record.fecha_hora,
        )
        block = (
            IntegrityBlock(
                cadena=self.chain_id,
                indice=0,
                registro_id=99,
                datos_canonicos="{}",
                hash_anterior=GENESIS_HASH,
                hash_actual="a" * 64,
            )
            if with_integrity
            else None
        )
        return stored, block

    def list_records(self, **kwargs):
        if self.fail:
            from app.core.exceptions import DatabaseUnavailableError

            raise DatabaseUnavailableError()
        self.last_filters = kwargs
        return self.records, False

    def get_record(self, record_id: int):
        for record in self.records:
            if record.id == record_id:
                return record
        return None


class FakeIntegrityService:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {
            "status": "empty",
            "servidor": "ambos",
            "sources": {},
        }

    def verify(self, servidor: str) -> dict[str, Any]:
        return self.payload


class FakeWeatherService:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[tuple[float, float]] = []

    async def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        self.calls.append((lat, lon))
        if self.error:
            raise self.error
        return self.payload or {}


class FakeGeocodingService:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[tuple[float, float]] = []

    async def reverse(self, lat: float, lon: float) -> dict[str, Any]:
        self.calls.append((lat, lon))
        if self.error:
            raise self.error
        return self.payload or {}


class FakeApiRecordsService:
    """Servicio de registros para las pruebas HTTP (sin tocar la base)."""

    def __init__(self, record: StoredRecord | None = None) -> None:
        self.record = record or stored_record()

    def create(self, context, data, servidor: str):
        from app.services.records_service import CreateResult

        record = replace(self.record, servidor=servidor, usuario=context.username)
        return CreateResult(
            record=record,
            integrity={
                "status": "created",
                "cadena": f"api-{servidor}",
                "indice": 0,
                "hash_actual": "a" * 64,
            },
        )

    def list_records(self, context, **kwargs):
        from app.services.records_service import ListResult

        return ListResult(
            records=[self.record],
            sources={
                "ubuntu": {"status": "ok", "count": 1, "has_more": False},
            },
            partial=False,
        )

    def get_record(self, context, servidor: str, record_id: int) -> StoredRecord:
        from app.core.exceptions import NotFoundError

        if record_id != self.record.id:
            raise NotFoundError("Registro no encontrado")
        return replace(self.record, servidor=servidor)


class FakeContainer:
    """Contenedor mínimo para probar las rutas con TestClient."""

    def __init__(
        self,
        *,
        settings: Settings,
        auth_service,
        session_service,
        records_service=None,
        integrity_check_service=None,
        weather_service=None,
        geocoding_service=None,
    ) -> None:
        self.settings = settings
        self.auth_service = auth_service
        self.session_service = session_service
        self.records_service = records_service or FakeApiRecordsService()
        self.integrity_check_service = integrity_check_service or FakeIntegrityService()
        self.weather_service = weather_service or FakeWeatherService()
        self.geocoding_service = geocoding_service or FakeGeocodingService()

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    def readiness(self, *, use_cache: bool = True) -> dict[str, Any]:
        return {
            "status": "ok",
            "checks": {
                "postgresql": {"status": "up"},
                "sqlserver": {"status": "up"},
            },
            "integrity": {"enabled": True, "postgres": "available", "sqlserver": "available"},
        }
