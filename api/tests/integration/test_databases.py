"""Pruebas reales de PostgreSQL y SQL Server.

Se ejecutan solo con ``RUN_DB_INTEGRATION=1``. Las escrituras se hacen en una
transacción que siempre termina en ``ROLLBACK``; no se conservan filas.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import psycopg
import pyodbc
import pytest

from app.core.config import get_settings
from app.core.container import Container
from app.core.security import hash_password, verify_password
from app.models.domain import WeatherRecord
from app.repositories.pool import PostgresManager, SqlServerManager
from app.repositories.postgres_repository import (
    PostgresAuthRepository,
    PostgresIntegrityRepository,
    PostgresRecordsRepository,
    PostgresSchemaProvider,
)
from app.repositories.schema import quote_mssql, quote_pg
from app.repositories.sqlserver_repository import (
    SqlServerRecordsRepository,
    SqlServerSchemaProvider,
)
from app.services.integrity_check_service import IntegrityCheckService
from app.services.integrity_service import canonical_record_json, compute_block_hash

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_INTEGRATION") != "1",
        reason="definir RUN_DB_INTEGRATION=1 para pruebas reales",
    ),
]

FECHA = datetime(2026, 10, 25, 18, 30, 45, 123000, tzinfo=UTC)


class SingleConnectionManager:
    """Entrega siempre la misma conexión y nunca confirma la transacción."""

    def __init__(self, connection) -> None:
        self._connection = connection

    @contextmanager
    def connection(self):
        yield self._connection

    def close(self) -> None:  # pragma: no cover - compatibilidad
        return None


def _pg_connect(settings):
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        sslmode=settings.postgres_sslmode,
        connect_timeout=int(settings.postgres_connect_timeout),
        application_name="clima-api-integration",
    )


def _mssql_connect(settings):
    manager = SqlServerManager(settings)
    connection = pyodbc.connect(
        manager._connection_string(),
        timeout=int(settings.sqlserver_connect_timeout),
        autocommit=False,
    )
    return connection, manager


def _record(usuario: str) -> WeatherRecord:
    return WeatherRecord(
        usuario=usuario,
        nombre="Integración",
        paterno="Prueba",
        materno="Automática",
        estado="Estado de prueba",
        municipio="Municipio de prueba",
        latitud=Decimal("19.3500000"),
        longitud=Decimal("-99.1620000"),
        temperatura=Decimal("21.50"),
        humedad=Decimal("55.00"),
        viento=Decimal("12.30"),
        fecha_hora=FECHA,
    )


def test_readiness_real():
    settings = get_settings()
    container = Container(settings)
    try:
        payload = container.readiness(use_cache=False)
    finally:
        asyncio.run(container.shutdown())

    assert payload["checks"]["postgresql"]["status"] == "up"
    assert payload["checks"]["sqlserver"]["status"] == "up"
    assert payload["checks"]["postgresql_schema"]["status"] == "ok"
    assert payload["checks"]["sqlserver_schema"]["status"] == "ok"


def test_postgres_listado_real():
    settings = get_settings()
    manager = PostgresManager(settings)
    try:
        provider = PostgresSchemaProvider(manager, settings)
        repo = PostgresRecordsRepository(manager, provider)
        records, has_more = repo.list_records(
            limit=5,
            offset=0,
            order_desc=True,
            order_field="fecha_hora",
        )
        assert isinstance(records, list)
        assert isinstance(has_more, bool)
        assert len(records) <= 5
        for record in records:
            assert record.servidor == "ubuntu"
            assert record.id >= 1
    finally:
        manager.close()


def test_postgres_alta_usuario_y_rollback():
    settings = get_settings()
    connection = _pg_connect(settings)
    try:
        manager = SingleConnectionManager(connection)
        provider = PostgresSchemaProvider(manager, settings)
        repo = PostgresAuthRepository(manager, provider)
        schema = provider.get()
        username = f"integracion_{uuid4().hex[:12]}"
        password = "Integracion-2026!"

        user = repo.create_user(username, hash_password(password))
        assert user.username == username
        assert user.totp_enabled is False
        assert user.totp_secret_encrypted is None
        assert verify_password(user.password_hash, password).valid
        assert repo.get_by_username(username) is not None

        connection.rollback()

        with connection.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM {schema.users.qualified_name} "
                f"WHERE {quote_pg(schema.users.require('username').name)} = %s",
                (username,),
            )
            assert cur.fetchone()[0] == 0
    finally:
        connection.close()


def test_sqlserver_listado_real():
    settings = get_settings()
    manager = SqlServerManager(settings)
    try:
        provider = SqlServerSchemaProvider(manager)
        repo = SqlServerRecordsRepository(manager, provider)
        records, has_more = repo.list_records(
            limit=5,
            offset=0,
            order_desc=True,
            order_field="fecha_hora",
        )
        assert isinstance(records, list)
        assert isinstance(has_more, bool)
        assert len(records) <= 5
        for record in records:
            assert record.servidor == "windows"
            assert record.id >= 1
    finally:
        manager.close()


def test_postgres_insercion_y_rollback():
    settings = get_settings()
    connection = _pg_connect(settings)
    try:
        manager = SingleConnectionManager(connection)
        provider = PostgresSchemaProvider(manager, settings)
        schema = provider.get()
        integrity = PostgresIntegrityRepository(manager, provider)
        repo = PostgresRecordsRepository(manager, provider, integrity=integrity)

        if schema.usuario_is_numeric:
            with connection.cursor() as cur:
                cur.execute(
                    f"SELECT {quote_pg(schema.users.require('id').name)} "
                    f"FROM {schema.users.qualified_name} LIMIT 1"
                )
                row = cur.fetchone()
            usuario_value = int(row[0]) if row else 1
        else:
            with connection.cursor() as cur:
                cur.execute(
                    f"SELECT {quote_pg(schema.users.require('username', 'usuario').name)} "
                    f"FROM {schema.users.qualified_name} LIMIT 1"
                )
                row = cur.fetchone()
            usuario_value = str(row[0]) if row else "integracion"

        record = _record(str(usuario_value))
        available = repo.integrity_available()
        stored, block = repo.insert(
            record, usuario_value=usuario_value, with_integrity=available
        )
        assert stored.id >= 1

        fetched = repo.get_record(stored.id)
        assert fetched is not None
        assert fetched.usuario == str(usuario_value)

        if available:
            assert block is not None
            blocks = integrity.fetch_blocks()
            found = next(item for item in blocks if item.registro_id == stored.id)
            expected = compute_block_hash(
                cadena=repo.chain_id,
                indice=found.indice,
                registro_id=found.registro_id,
                datos_canonicos=found.datos_canonicos,
                hash_anterior=found.hash_anterior,
            )
            assert found.hash_actual == expected
            assert found.datos_canonicos == canonical_record_json(
                fetched, servidor="ubuntu", record_id=stored.id
            )

        connection.rollback()

        with connection.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM {schema.records.qualified_name} "
                f"WHERE {quote_pg(schema.records_map['id'].name)} = %s",
                (stored.id,),
            )
            assert cur.fetchone()[0] == 0
            if available and schema.integrity is not None:
                cur.execute(
                    f"SELECT count(*) FROM {schema.integrity.qualified_name} "
                    f"WHERE {quote_pg(schema.integrity_map['registro_id'].name)} = %s",
                    (stored.id,),
                )
                assert cur.fetchone()[0] == 0
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def test_sqlserver_insercion_y_rollback():
    settings = get_settings()
    connection, manager = _mssql_connect(settings)
    try:
        single = SingleConnectionManager(connection)
        provider = SqlServerSchemaProvider(single)
        schema = provider.get()
        repo = SqlServerRecordsRepository(single, provider)

        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT TOP 1 {quote_mssql(schema.records_map['usuario'].name)} "
                f"FROM [{schema.records.schema}].[{schema.records.name}]"
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        usuario_value = str(row[0]) if row and row[0] else "integracion"

        record = _record(usuario_value)
        available = repo.integrity_available()
        stored, block = repo.insert(
            record, usuario_value=usuario_value, with_integrity=available
        )
        assert stored.id >= 1

        fetched = repo.get_record(stored.id)
        assert fetched is not None

        if available:
            assert block is not None
            blocks = repo.integrity.fetch_blocks()
            found = next(item for item in blocks if item.registro_id == stored.id)
            expected = compute_block_hash(
                cadena=repo.chain_id,
                indice=found.indice,
                registro_id=found.registro_id,
                datos_canonicos=found.datos_canonicos,
                hash_anterior=found.hash_anterior,
            )
            assert found.hash_actual == expected
            assert found.datos_canonicos == canonical_record_json(
                fetched, servidor="windows", record_id=stored.id
            )

        connection.rollback()

        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM [{schema.records.schema}].[{schema.records.name}] "
                f"WHERE {quote_mssql(schema.records_map['id'].name)} = ?",
                (stored.id,),
            )
            assert cursor.fetchone()[0] == 0
            if available and schema.integrity is not None:
                cursor.execute(
                    f"SELECT COUNT(*) FROM [{schema.integrity.schema}].[{schema.integrity.name}] "
                    f"WHERE {quote_mssql(schema.integrity_map['registro_id'].name)} = ?",
                    (stored.id,),
                )
                assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
        manager.close()


def test_verificacion_de_integridad_real():
    settings = get_settings()
    pg_manager = PostgresManager(settings)
    ms_manager = SqlServerManager(settings)
    try:
        pg_provider = PostgresSchemaProvider(pg_manager, settings)
        ms_provider = SqlServerSchemaProvider(ms_manager)
        pg_repo = PostgresRecordsRepository(pg_manager, pg_provider)
        ms_repo = SqlServerRecordsRepository(ms_manager, ms_provider)
        report = IntegrityCheckService(settings, pg_repo, ms_repo).verify("ambos")
        assert report["status"] in {
            "ok",
            "empty",
            "invalid",
            "partial",
            "unavailable",
            "disabled",
        }
        assert set(report["sources"]) == {"ubuntu", "windows"}
        for source in report["sources"].values():
            assert source["status"] in {
                "ok",
                "empty",
                "invalid",
                "unavailable",
                "disabled",
                "error",
            }
    finally:
        pg_manager.close()
        ms_manager.close()
