"""Contenedor de dependencias y estado de la aplicación."""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.logging import get_logger
from app.repositories.pool import PostgresManager, SqlServerManager
from app.repositories.postgres_repository import (
    PostgresAuthRepository,
    PostgresIntegrityRepository,
    PostgresRecordsRepository,
    PostgresSchemaProvider,
    PostgresSessionStore,
)
from app.repositories.sqlserver_repository import SqlServerRecordsRepository, SqlServerSchemaProvider
from app.services.auth_service import AuthService
from app.services.crypto_service import CryptoService
from app.services.geocoding_service import GeocodingService
from app.services.integrity_check_service import IntegrityCheckService
from app.services.records_service import RecordsService
from app.services.session_service import SessionService
from app.services.totp_service import TOTPService
from app.services.weather_service import WeatherService

logger = get_logger(__name__)


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.postgres_manager = PostgresManager(settings)
        self.sqlserver_manager = SqlServerManager(settings)
        self.postgres_provider = PostgresSchemaProvider(self.postgres_manager, settings)
        self.sqlserver_provider = SqlServerSchemaProvider(self.sqlserver_manager)

        self.auth_repository = PostgresAuthRepository(self.postgres_manager, self.postgres_provider)
        self.session_store = PostgresSessionStore(self.postgres_manager, self.postgres_provider)
        self.session_service = SessionService(settings, self.session_store, self.postgres_provider)
        totp_crypto = CryptoService(settings.totp_key, purpose="totp-secret")
        record_crypto = CryptoService(settings.record_key, purpose="record-field")
        self.totp_service = TOTPService(settings, totp_crypto)
        self.record_crypto = record_crypto
        self.auth_service = AuthService(
            settings, self.auth_repository, self.session_service, self.totp_service
        )

        self.postgres_integrity = PostgresIntegrityRepository(
            self.postgres_manager, self.postgres_provider
        )
        self.postgres_records = PostgresRecordsRepository(
            self.postgres_manager, self.postgres_provider, integrity=self.postgres_integrity
        )
        self.sqlserver_records = SqlServerRecordsRepository(
            self.sqlserver_manager, self.sqlserver_provider
        )
        self.records_service = RecordsService(
            settings, self.postgres_records, self.sqlserver_records, self.auth_repository
        )
        self.integrity_check_service = IntegrityCheckService(
            settings, self.postgres_records, self.sqlserver_records
        )

        self._http_client: httpx.AsyncClient | None = None
        self.weather_service = WeatherService(settings, self._client)
        self.geocoding_service = GeocodingService(settings, self._client)
        self._readiness_lock = threading.Lock()
        self._readiness_cache: tuple[float, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    async def startup(self) -> None:
        self._http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=False,
            headers={"User-Agent": f"{self.settings.app_name}/1.0"},
        )

    async def shutdown(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        self.postgres_manager.close()
        self.sqlserver_manager.close()

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            raise RuntimeError("El cliente HTTP no está inicializado")
        return self._http_client

    # ------------------------------------------------------------------
    # Disponibilidad
    # ------------------------------------------------------------------
    def readiness(self, *, use_cache: bool = True) -> dict[str, Any]:
        now = time.monotonic()
        if use_cache:
            with self._readiness_lock:
                if self._readiness_cache and self._readiness_cache[0] > now:
                    return self._readiness_cache[1]

        checks: dict[str, Any] = {"app": {"status": "up"}}
        pg_status = self.postgres_manager.ping()
        checks["postgresql"] = pg_status.as_dict()
        sql_status = self.sqlserver_manager.ping()
        checks["sqlserver"] = sql_status.as_dict()

        core_ok = pg_status.status == "up"
        if core_ok:
            try:
                self.postgres_provider.get()
                checks["postgresql_schema"] = {"status": "ok"}
                checks["session_store"] = {"status": "ok"}
            except DatabaseUnavailableError:
                checks["postgresql_schema"] = {"status": "down", "reason": "schema_unavailable"}
                checks["session_store"] = {"status": "down", "reason": "unavailable"}
                core_ok = False
        else:
            checks["postgresql_schema"] = {"status": "down", "reason": "database_unavailable"}
            checks["session_store"] = {"status": "down", "reason": "database_unavailable"}

        if sql_status.status == "up":
            try:
                self.sqlserver_provider.get()
                checks["sqlserver_schema"] = {"status": "ok"}
            except DatabaseUnavailableError:
                checks["sqlserver_schema"] = {"status": "down", "reason": "schema_unavailable"}

        if not core_ok:
            overall = "error"
        elif sql_status.status != "up" or checks.get("sqlserver_schema", {}).get("status") != "ok":
            overall = "degraded"
        else:
            overall = "ok"

        payload = {
            "status": overall,
            "checks": checks,
            "integrity": {
                "enabled": self.settings.integrity_enabled,
                "postgres": self._integrity_flag(self.postgres_records, core_ok),
                "sqlserver": self._integrity_flag(
                    self.sqlserver_records, checks.get("sqlserver_schema", {}).get("status") == "ok"
                ),
            },
        }
        integrity_states = [payload["integrity"]["postgres"], payload["integrity"]["sqlserver"]]
        if overall == "ok" and self.settings.integrity_enabled and "missing" in integrity_states:
            # La API opera, pero una capacidad declarada no está disponible.
            payload["status"] = "degraded"

        with self._readiness_lock:
            self._readiness_cache = (time.monotonic() + 3.0, payload)
        return payload

    @staticmethod
    def _integrity_flag(repo, database_ok: bool) -> str:
        if not database_ok:
            return "unknown"
        try:
            return "available" if repo.integrity_available() else "missing"
        except Exception:
            return "unknown"
