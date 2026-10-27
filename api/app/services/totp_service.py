"""Generación y verificación de TOTP (RFC 6238) compatible con Google/Microsoft Authenticator."""

from __future__ import annotations

import hmac
import re
import time

import pyotp
import segno

from app.core.config import Settings
from app.services.crypto_service import CryptoService

_CODE_RE = re.compile(r"^\d{6}$")
_INTERVAL = 30
_WINDOW = 1


class TOTPService:
    def __init__(self, settings: Settings, crypto: CryptoService) -> None:
        self._settings = settings
        self._crypto = crypto
        self._issuer = settings.app_name

    def new_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, username: str) -> str:
        return pyotp.TOTP(secret, interval=_INTERVAL).provisioning_uri(
            name=username, issuer_name=self._issuer
        )

    def qr_data_uri(self, uri: str) -> str:
        return segno.make(uri, error="m").png_data_uri(scale=6, border=2)

    def encrypt_secret(self, secret: str, user_id: int) -> str:
        return self._crypto.encrypt(secret, context=f"user:{user_id}")

    def decrypt_secret(self, encrypted: str, user_id: int) -> str:
        return self._crypto.decrypt(encrypted, context=f"user:{user_id}")

    def verify(self, secret: str, code: str, last_counter: int | None) -> tuple[bool, int | None, str]:
        """Devuelve (válido, contador, motivo). Acepta ±1 intervalo de 30 s."""
        if not _CODE_RE.match(code or ""):
            return False, None, "format"
        totp = pyotp.TOTP(secret, interval=_INTERVAL)
        current = int(time.time()) // _INTERVAL
        for offset in range(-_WINDOW, _WINDOW + 1):
            counter = current + offset
            expected = totp.generate_otp(counter)
            if hmac.compare_digest(expected, code):
                if last_counter is not None and counter <= last_counter:
                    return False, counter, "reused"
                return True, counter, "ok"
        return False, None, "mismatch"
