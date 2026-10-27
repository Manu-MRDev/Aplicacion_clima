"""Pools de conexión independientes para PostgreSQL y SQL Server."""

from __future__ import annotations

import os
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import pyodbc
from psycopg import OperationalError as PsycopgOperationalError
from psycopg_pool import ConnectionPool, PoolTimeout

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyStatus:
    name: str
    status: str  # "up" | "down"
    reason: str | None = None
    latency_ms: float | None = None

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"status": self.status}
        if self.reason:
            data["reason"] = self.reason
        if self.latency_ms is not None:
            data["latency_ms"] = round(self.latency_ms, 1)
        return data


def _classify_pg_error(exc: BaseException) -> str:
    message = str(exc).lower()
    if "password authentication failed" in message or "authentication failed" in message:
        return "auth_failed"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "does not exist" in message:
        return "database_missing"
    return "unreachable"


class PostgresManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._pool: ConnectionPool | None = None
        self._next_retry_at = 0.0
        self._last_reason: str | None = None

    def _kwargs(self) -> dict[str, object]:
        return {
            "host": self._settings.postgres_host,
            "port": self._settings.postgres_port,
            "dbname": self._settings.postgres_db,
            "user": self._settings.postgres_user,
            "password": self._settings.postgres_password.get_secret_value(),
            "sslmode": self._settings.postgres_sslmode,
            "connect_timeout": int(self._settings.postgres_connect_timeout),
            "application_name": "clima-api",
        }

    def _get_pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        if time.monotonic() < self._next_retry_at:
            raise DatabaseUnavailableError()
        with self._lock:
            if self._pool is None:
                pool = ConnectionPool(
                    kwargs=self._kwargs(),
                    min_size=self._settings.postgres_pool_min_size,
                    max_size=self._settings.postgres_pool_max_size,
                    timeout=self._settings.postgres_connect_timeout,
                    open=False,
                    name="clima-postgres",
                )
                try:
                    pool.open(wait=True, timeout=self._settings.postgres_connect_timeout)
                except Exception as exc:
                    pool.close()
                    self._last_reason = _classify_pg_error(exc)
                    self._next_retry_at = (
                        time.monotonic() + min(30.0, self._settings.postgres_connect_timeout)
                    )
                    logger.warning("PostgreSQL no disponible (%s)", type(exc).__name__)
                    raise DatabaseUnavailableError() from exc
                self._pool = pool
                self._last_reason = None
                logger.info("Pool PostgreSQL inicializado")
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[object]:
        pool = self._get_pool()
        try:
            with pool.connection(timeout=self._settings.postgres_connect_timeout) as conn:
                yield conn
        except PoolTimeout as exc:
            self._last_reason = "timeout"
            raise DatabaseUnavailableError() from exc
        except PsycopgOperationalError as exc:
            self._last_reason = _classify_pg_error(exc)
            raise DatabaseUnavailableError() from exc

    def ping(self) -> DependencyStatus:
        started = time.perf_counter()
        try:
            with self.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
        except DatabaseUnavailableError:
            return DependencyStatus("postgresql", "down", self._last_reason or "unreachable")
        except Exception as exc:
            self._last_reason = _classify_pg_error(exc)
            logger.warning("Fallo de ping PostgreSQL (%s)", type(exc).__name__)
            return DependencyStatus("postgresql", "down", self._last_reason)
        return DependencyStatus(
            "postgresql", "up", latency_ms=(time.perf_counter() - started) * 1000
        )

    def close(self) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.close()
                self._pool = None


class SqlServerManager:
    def __init__(self, settings: Settings) -> None:
        if settings.odbc_config_dir:
            # unixODBC resuelve el driver al primer drivers()/connect(); el valor
            # debe existir antes, incluso si no se creó la app mediante create_app().
            os.environ.setdefault("ODBCSYSINI", settings.odbc_config_dir)
        self._settings = settings
        self._pool: queue.LifoQueue[pyodbc.Connection] = queue.LifoQueue(
            maxsize=settings.sqlserver_pool_max_size
        )
        self._lock = threading.Lock()
        self._created = 0
        self._next_retry_at = 0.0
        self._last_reason: str | None = None
        self._drivers = tuple(pyodbc.drivers())

    @property
    def driver_missing(self) -> bool:
        return self._settings.sqlserver_odbc_driver not in self._drivers

    @property
    def last_reason(self) -> str | None:
        if self.driver_missing:
            return "driver_missing"
        return self._last_reason

    def _connection_string(self) -> str:
        s = self._settings
        return (
            f"DRIVER={{{s.sqlserver_odbc_driver}}};"
            f"SERVER={s.sqlserver_host},{s.sqlserver_port};"
            f"DATABASE={s.sqlserver_db};"
            f"UID={s.sqlserver_user};"
            f"PWD={s.sqlserver_password.get_secret_value()};"
            f"Encrypt={s.sqlserver_encrypt};"
            f"TrustServerCertificate={s.sqlserver_trust_server_certificate};"
            f"Connection Timeout={int(s.sqlserver_connect_timeout)};"
        )

    def _new_connection(self) -> pyodbc.Connection:
        if self.driver_missing:
            self._last_reason = "driver_missing"
            raise DatabaseUnavailableError()
        if time.monotonic() < self._next_retry_at:
            raise DatabaseUnavailableError()
        try:
            conn = pyodbc.connect(
                self._connection_string(),
                timeout=int(self._settings.sqlserver_connect_timeout),
                autocommit=False,
            )
        except pyodbc.Error as exc:
            self._last_reason = self._classify(exc)
            self._next_retry_at = (
                time.monotonic() + min(30.0, self._settings.sqlserver_connect_timeout)
            )
            logger.warning("SQL Server no disponible (%s)", type(exc).__name__)
            raise DatabaseUnavailableError() from exc
        self._last_reason = None
        self._next_retry_at = 0.0
        with self._lock:
            self._created += 1
        return conn

    @staticmethod
    def _classify(exc: BaseException) -> str:
        message = str(exc).lower()
        if "login failed" in message or "authentication" in message:
            return "auth_failed"
        if "timeout" in message or "timed out" in message:
            return "timeout"
        if "cannot open database" in message:
            return "database_missing"
        if "can't open lib" in message or "data source name not found" in message:
            return "driver_missing"
        return "unreachable"

    @contextmanager
    def connection(self) -> Iterator[pyodbc.Connection]:
        conn = self._acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except pyodbc.Error:  # pragma: no cover - conexión ya rota
                pass
            raise
        finally:
            self._release(conn)

    def _acquire(self) -> pyodbc.Connection:
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            with self._lock:
                can_create = self._created < self._settings.sqlserver_pool_max_size
            if can_create:
                return self._new_connection()
            try:
                conn = self._pool.get(timeout=self._settings.sqlserver_connect_timeout)
            except queue.Empty as exc:
                raise DatabaseUnavailableError() from exc
        if getattr(conn, "closed", False):
            with self._lock:
                self._created = max(0, self._created - 1)
            return self._acquire()
        return conn

    def _release(self, conn: pyodbc.Connection) -> None:
        if getattr(conn, "closed", False):
            with self._lock:
                self._created = max(0, self._created - 1)
            return
        try:
            self._pool.put_nowait(conn)
        except queue.Full:  # pragma: no cover - defensivo
            conn.close()
            with self._lock:
                self._created = max(0, self._created - 1)

    def ping(self) -> DependencyStatus:
        started = time.perf_counter()
        if self.driver_missing:
            return DependencyStatus("sqlserver", "down", "driver_missing")
        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
        except DatabaseUnavailableError:
            return DependencyStatus("sqlserver", "down", self._last_reason or "unreachable")
        except Exception as exc:
            self._last_reason = self._classify(exc)
            logger.warning("Fallo de ping SQL Server (%s)", type(exc).__name__)
            return DependencyStatus("sqlserver", "down", self._last_reason)
        return DependencyStatus("sqlserver", "up", latency_ms=(time.perf_counter() - started) * 1000)

    def close(self) -> None:
        while True:
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except pyodbc.Error:  # pragma: no cover
                pass
            with self._lock:
                self._created = max(0, self._created - 1)
