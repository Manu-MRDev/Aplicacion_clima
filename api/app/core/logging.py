"""Configuración de logging con redacción de datos sensibles."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

REDACTED = "[REDACTED]"

_SENSITIVE_PATTERNS = [
    # Bearer primero: si no, la regla genérica redactaría solo la palabra "Bearer"
    # y dejaría visible el token que le sigue.
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)\b(password|passwd|pwd|contraseña|secret|token|api[_-]?key|authorization|"
        r"cookie|set-cookie|totp|otp|session_secret)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
    ),
]


def redact(text: str) -> str:
    """Elimina valores sensibles de un mensaje antes de escribirlo."""
    redacted = text
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.groups == 1:  # Bearer <token>
            redacted = pattern.sub(r"\1 " + REDACTED, redacted)
        else:
            redacted = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Evitar que clientes HTTP registren URLs completas con parámetros.
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
