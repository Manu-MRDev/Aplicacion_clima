"""Pruebas de redacción de secretos en logs."""

from __future__ import annotations

import logging

from app.core.logging import REDACTED, JsonFormatter, RedactingFormatter, redact


def test_redacta_password():
    assert "secreto" not in redact("password=secreto")
    assert REDACTED in redact("password=secreto")


def test_redacta_token_y_cookie():
    assert "abc123" not in redact("token: abc123")
    assert "xyz" not in redact("cookie=xyz")
    assert "xyz" not in redact("Set-Cookie: xyz")


def test_redacta_bearer():
    text = redact("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in text
    assert REDACTED in text


def test_no_redacta_texto_normal():
    assert redact("usuario ana inició sesión") == "usuario ana inició sesión"


def test_formateador_redacta():
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "password=secreto", None, None
    )
    output = formatter.format(record)
    assert "secreto" not in output
    assert REDACTED in output


def test_formateador_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "token=secreto", None, None
    )
    output = formatter.format(record)
    assert '"level": "INFO"' in output
    assert '"logger": "test"' in output
    assert "secreto" not in output
