"""Configuración de las pruebas de integración (opt-in)."""

from __future__ import annotations

import os

if os.getenv("RUN_DB_INTEGRATION") == "1":
    from app.core.config import get_settings

    _settings = get_settings()
    if _settings.odbc_config_dir:
        # Debe fijarse antes de la primera llamada a pyodbc.drivers()/connect().
        os.environ.setdefault("ODBCSYSINI", _settings.odbc_config_dir)
