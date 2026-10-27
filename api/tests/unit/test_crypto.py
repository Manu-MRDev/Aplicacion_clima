"""Pruebas de AES-256-GCM y del formato versionado."""

from __future__ import annotations

import base64

import pytest

from app.core.exceptions import CryptoError
from app.services.crypto_service import CryptoService, build_crypto_services


def _service() -> CryptoService:
    key = base64.urlsafe_b64decode(base64.urlsafe_b64encode(b"k" * 32))
    return CryptoService(key, purpose="totp-secret")


def test_roundtrip_y_formato():
    service = _service()
    token = service.encrypt("JBSWY3DPEHPK3PXP", context="user:7")
    assert token.startswith("v1.")
    assert token.count(".") == 2
    assert service.decrypt(token, context="user:7") == "JBSWY3DPEHPK3PXP"


def test_nonce_aleatorio():
    service = _service()
    first = service.encrypt("secreto", context="user:1")
    second = service.encrypt("secreto", context="user:1")
    assert first != second


def test_contexto_distinto_falla():
    service = _service()
    token = service.encrypt("secreto", context="user:1")
    with pytest.raises(CryptoError):
        service.decrypt(token, context="user:2")


def test_manipulacion_falla():
    service = _service()
    token = service.encrypt("secreto", context="user:1")
    version, nonce, ciphertext = token.split(".")
    tampered = f"{version}.{nonce}.{ciphertext[:-2]}AA"
    with pytest.raises(CryptoError):
        service.decrypt(tampered, context="user:1")


@pytest.mark.parametrize(
    "token",
    ["", "v1", "v2.abc.def", "v1..", "v1.abc.def", "no-es-un-token"],
)
def test_tokens_invalidos(token: str):
    with pytest.raises(CryptoError):
        _service().decrypt(token, context="")


def test_clave_debe_ser_de_32_bytes():
    with pytest.raises(ValueError):
        CryptoService(b"corta", purpose="x")


def test_propositos_separados():
    totp, record = build_crypto_services(b"t" * 32, b"r" * 32)
    token = totp.encrypt("valor", context="user:1")
    with pytest.raises(CryptoError):
        record.decrypt(token, context="user:1")
