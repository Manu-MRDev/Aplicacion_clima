"""Inspección de solo lectura de los esquemas existentes.

Uso: ``uv run python scripts/inspect_db.py``

No modifica nada. No imprime contraseñas, hashes ni secretos: solo metadatos,
recuentos y prefijos de formato.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
import pyodbc

from app.core.config import get_settings

PG_TABLES = ("usuarios", "session", "api_sessions", "Georreferencia", "cadena_bloques")
MSSQL_TABLES = ("Georreferencia", "CadenaBloques")


def show(title: str) -> None:
    print(f"\n=== {title} ===")


def inspect_postgres() -> None:
    s = get_settings()
    show("PostgreSQL")
    kwargs = {
        "host": s.postgres_host,
        "port": s.postgres_port,
        "dbname": s.postgres_db,
        "user": s.postgres_user,
        "password": s.postgres_password.get_secret_value(),
        "sslmode": s.postgres_sslmode,
        "connect_timeout": int(s.postgres_connect_timeout),
        "application_name": "clima-inspect",
    }
    try:
        conn = psycopg.connect(**kwargs)
    except Exception as exc:
        print(f"No se pudo conectar: {type(exc).__name__}: {exc}")
        return

    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_user, current_database()")
            version, user, database = cur.fetchone()
            print(f"version: {version.split(',')[0]}")
            print(f"user: {user} | database: {database}")

        for table in PG_TABLES:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE lower(table_name) = lower(%s) AND table_type = 'BASE TABLE'
                    """,
                    (table,),
                )
                found = cur.fetchall()
            if not found:
                print(f"\n-- {table}: NO EXISTE")
                continue
            schema, name = found[0]
            print(f"\n-- {schema}.{name}")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, udt_name, is_nullable, column_default,
                           is_identity, character_maximum_length, numeric_precision,
                           numeric_scale, datetime_precision
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, name),
                )
                for row in cur.fetchall():
                    print(
                        f"   {row[0]}: {row[2]} nullable={row[3]} default={row[4]} "
                        f"identity={row[5]} len={row[6]} precision={row[7]} scale={row[8]}"
                    )
                cur.execute(
                    """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = %s::regclass AND i.indisprimary
                    ORDER BY array_position(i.indkey, a.attnum)
                    """,
                    (f'"{schema}"."{name}"',),
                )
                print(f"   PK: {[r[0] for r in cur.fetchall()]}")
                cur.execute(
                    """
                    SELECT indexname, indexdef FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                    """,
                    (schema, name),
                )
                for index_name, index_def in cur.fetchall():
                    print(f"   INDEX {index_name}: {index_def}")
                cur.execute(
                    """
                    SELECT privilege_type FROM information_schema.table_privileges
                    WHERE table_schema = %s AND table_name = %s
                      AND grantee = current_user
                    ORDER BY privilege_type
                    """,
                    (schema, name),
                )
                print(f"   PRIVILEGIOS: {[r[0] for r in cur.fetchall()]}")
                try:
                    cur.execute(f'SELECT count(*) FROM "{schema}"."{name}"')
                    print(f"   FILAS: {cur.fetchone()[0]}")
                except Exception as exc:
                    conn.rollback()
                    print(f"   FILAS: no disponible ({type(exc).__name__})")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  count(*) FILTER (WHERE password_hash LIKE '$argon2id$%') AS argon2id,
                  count(*) FILTER (WHERE password_hash LIKE '$argon2i$%') AS argon2i,
                  count(*) FILTER (WHERE password_hash LIKE '$2b$%') AS bcrypt_b,
                  count(*) FILTER (WHERE password_hash LIKE '$2a$%') AS bcrypt_a,
                  count(*) FILTER (WHERE password_hash IS NULL OR password_hash = '') AS vacios,
                  count(*) FILTER (WHERE totp_secret_encrypted IS NOT NULL
                                   AND totp_secret_encrypted <> '') AS con_secreto,
                  count(*) FILTER (WHERE totp_enabled) AS totp_activo
                FROM usuarios
                """
            )
            print("\n-- usuarios: formatos")
            print(
                "   argon2id={} argon2i={} bcrypt_b={} bcrypt_a={} vacios={} "
                "con_secreto={} totp_activo={}".format(*cur.fetchone())
            )
            cur.execute(
                """
                SELECT left(totp_secret_encrypted, 3) AS prefijo, length(totp_secret_encrypted) AS largo,
                       count(*)
                FROM usuarios
                WHERE totp_secret_encrypted IS NOT NULL AND totp_secret_encrypted <> ''
                GROUP BY 1, 2 ORDER BY 3 DESC
                """
            )
            print("   formatos de secreto TOTP (prefijo, longitud, cantidad):")
            for row in cur.fetchall():
                print(f"      {row[0]!r} len={row[1]} count={row[2]}")
        conn.rollback()


def inspect_sqlserver() -> None:
    s = get_settings()
    if s.odbc_config_dir:
        os.environ.setdefault("ODBCSYSINI", s.odbc_config_dir)
    show("SQL Server")
    drivers = pyodbc.drivers()
    print(f"drivers ODBC disponibles: {drivers}")
    if s.sqlserver_odbc_driver not in drivers:
        print(
            f"El driver {s.sqlserver_odbc_driver!r} no está instalado; "
            "no se puede inspeccionar SQL Server desde este host."
        )
        return
    connection_string = (
        f"DRIVER={{{s.sqlserver_odbc_driver}}};"
        f"SERVER={s.sqlserver_host},{s.sqlserver_port};"
        f"DATABASE={s.sqlserver_db};"
        f"UID={s.sqlserver_user};"
        f"PWD={s.sqlserver_password.get_secret_value()};"
        f"Encrypt={s.sqlserver_encrypt};"
        f"TrustServerCertificate={s.sqlserver_trust_server_certificate};"
        f"Connection Timeout={int(s.sqlserver_connect_timeout)};"
    )
    try:
        conn = pyodbc.connect(connection_string, timeout=int(s.sqlserver_connect_timeout))
    except Exception as exc:
        print(f"No se pudo conectar: {type(exc).__name__}: {exc}")
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT @@VERSION, SUSER_SNAME(), DB_NAME()")
        version, user, database = cur.fetchone()
        print(f"version: {version.splitlines()[0]}")
        print(f"user: {user} | database: {database}")
        for table in MSSQL_TABLES:
            cur.execute("SELECT OBJECT_ID(?, 'U')", (f"dbo.{table}",))
            if cur.fetchone()[0] is None:
                print(f"\n-- dbo.{table}: NO EXISTE")
                continue
            print(f"\n-- dbo.{table}")
            cur.execute(
                """
                SELECT c.name, t.name, c.max_length, c.is_nullable, c.is_identity,
                       c.precision, c.scale
                FROM sys.columns c
                JOIN sys.types t ON c.user_type_id = t.user_type_id
                WHERE c.object_id = OBJECT_ID(?) ORDER BY c.column_id
                """,
                (f"dbo.{table}",),
            )
            for row in cur.fetchall():
                print(
                    f"   {row[0]}: {row[1]} nullable={bool(row[3])} identity={bool(row[4])} "
                    f"max_length={row[2]} precision={row[5]} scale={row[6]}"
                )
            cur.execute(
                """
                SELECT c.name
                FROM sys.index_columns ic
                JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                WHERE ic.object_id = OBJECT_ID(?) AND i.is_primary_key = 1
                ORDER BY ic.key_ordinal
                """,
                (f"dbo.{table}",),
            )
            print(f"   PK: {[r[0] for r in cur.fetchall()]}")
            cur.execute(
                "SELECT i.name, i.type_desc, i.is_unique FROM sys.indexes i "
                "WHERE i.object_id = OBJECT_ID(?) AND i.name IS NOT NULL",
                (f"dbo.{table}",),
            )
            for name, type_desc, unique in cur.fetchall():
                print(f"   INDEX {name}: {type_desc} unique={bool(unique)}")
            cur.execute(
                "SELECT permission_name FROM fn_my_permissions(?, 'OBJECT')",
                (f"dbo.{table}",),
            )
            print(f"   PERMISOS: {[r[0] for r in cur.fetchall()]}")
            cur.execute(f"SELECT COUNT(*) FROM [dbo].[{table}]")
            print(f"   FILAS: {cur.fetchone()[0]}")
        conn.rollback()
    finally:
        conn.close()


def main() -> int:
    inspect_postgres()
    inspect_sqlserver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
