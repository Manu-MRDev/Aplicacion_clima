"""Pruebas de TOTP RFC 6238 y del QR de inscripción."""

from __future__ import annotations

from types import SimpleNamespace

import pyotp
import pytest

from app.services import totp_service as totp_module
from app.services.crypto_service import CryptoService
from app.services.totp_service import TOTPService

FIXED_TIME = 1_800_000_000
COUNTER = FIXED_TIME // 30
SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture
def service(settings, monkeypatch):
    monkeypatch.setattr(totp_module, "time", SimpleNamespace(time=lambda: FIXED_TIME))
    return TOTPService(settings, CryptoService(settings.totp_key, purpose="totp-secret"))


def code_for(counter: int, secret: str = SECRET) -> str:
    return pyotp.TOTP(secret, interval=30).generate_otp(counter)


def test_codigo_actual_valido(service):
    valid, counter, reason = service.verify(SECRET, code_for(COUNTER), None)
    assert valid is True
    assert counter == COUNTER
    assert reason == "ok"


@pytest.mark.parametrize("offset", [-1, 1])
def test_ventana_de_un_intervalo(service, offset):
    valid, counter, _ = service.verify(SECRET, code_for(COUNTER + offset), None)
    assert valid is True
    assert counter == COUNTER + offset


def test_fuera_de_ventana(service):
    valid, counter, reason = service.verify(SECRET, code_for(COUNTER + 2), None)
    assert valid is False
    assert counter is None
    assert reason == "mismatch"


def test_contador_reutilizado(service):
    valid, counter, reason = service.verify(SECRET, code_for(COUNTER), COUNTER)
    assert valid is False
    assert counter == COUNTER
    assert reason == "reused"


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 345"])
def test_formato_invalido(service, code):
    valid, counter, reason = service.verify(SECRET, code, None)
    assert valid is False
    assert counter is None
    assert reason == "format"


def test_secreto_aleatorio(service):
    secret = service.new_secret()
    assert len(secret) >= 16
    assert secret == secret.upper()


def test_uri_de_aprovisionamiento(service):
    uri = service.provisioning_uri(SECRET, "ana")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=Clima%20API%20Test" in uri
    assert "secret=JBSWY3DPEHPK3PXP" in uri


def test_qr_es_png_data_uri(service):
    qr = service.qr_data_uri(service.provisioning_uri(SECRET, "ana"))
    assert qr.startswith("data:image/png;base64,")
    assert len(qr) > 100


def test_cifrado_vinculado_al_usuario(service):
    encrypted = service.encrypt_secret(SECRET, 5)
    assert service.decrypt_secret(encrypted, 5) == SECRET
    with pytest.raises(Exception):
        service.decrypt_secret(encrypted, 6)
