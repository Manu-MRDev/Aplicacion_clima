"""Reset administrativo de TOTP (dry-run por defecto).

Uso:
    uv run python scripts/admin_reset_totp.py --username ana
    uv run python scripts/admin_reset_totp.py --username ana --apply

Sin ``--apply`` solo muestra el estado y revierte la transacción. Con
``--apply`` borra el secreto TOTP, desactiva el segundo factor, limpia bloqueos
y revoca las sesiones de esta API. No imprime secretos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings


def _connect(settings):
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        sslmode=settings.postgres_sslmode,
        connect_timeout=int(settings.postgres_connect_timeout),
        application_name="clima-admin-reset-totp",
    )


def reset(username: str, *, apply: bool) -> int:
    settings = get_settings()
    connection = _connect(settings)
    try:
        with connection.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, username, totp_enabled, totp_ultimo_counter,
                       left(coalesce(totp_secret_encrypted, ''), 3) AS prefijo_secreto
                FROM usuarios
                WHERE username = %s
                FOR UPDATE
                """,
                (username,),
            )
            rows = cur.fetchall()

        if len(rows) != 1:
            print(
                f"ERROR: se esperaba 1 usuario con username={username!r} y se "
                f"encontraron {len(rows)}; no se modifica nada"
            )
            connection.rollback()
            return 2

        print("ESTADO ACTUAL:")
        print(json.dumps(rows[0], ensure_ascii=False, default=str, indent=2))

        if not apply:
            connection.rollback()
            print("\nDRY-RUN: no se modificó nada. Repetir con --apply para ejecutar.")
            return 0

        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE usuarios
                SET totp_secret_encrypted = NULL,
                    totp_enabled = FALSE,
                    totp_ultimo_counter = NULL,
                    intentos_fallidos = 0,
                    bloqueado_hasta = NULL
                WHERE username = %s
                """,
                (username,),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"UPDATE afectó {cur.rowcount} filas; se revierte")

            cur.execute(
                """
                DELETE FROM "session"
                WHERE sess->>'v' = '1' AND sess->>'username' = %s
                """,
                (username,),
            )
            revoked = cur.rowcount

        connection.commit()
        print(
            f"\nOK: TOTP desactivado para {username!r}; "
            f"sesiones de esta API revocadas: {revoked}. "
            "El usuario deberá inscribir TOTP de nuevo."
        )
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset administrativo de TOTP")
    parser.add_argument("--username", required=True, help="username exacto")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="ejecuta el cambio; sin esta opción solo muestra el estado",
    )
    args = parser.parse_args()
    return reset(args.username, apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
