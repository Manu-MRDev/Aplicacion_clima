"""Cifrado autenticado AES-256-GCM con formato versionado.

Formato: ``v1.<nonce_b64url>.<ciphertext_b64url>``
El AAD vincula el criptograma a su propósito y contexto (por ejemplo, un usuario),
de modo que un texto cifrado no puede trasladarse entre campos o identidades.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.exceptions import CryptoError

_VERSION = "v1"
_NONCE_BYTES = 12


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _aad(purpose: str, context: str) -> bytes:
    return f"{_VERSION}:{purpose}:{context}".encode("utf-8")


class CryptoService:
    """Servicio de cifrado para un propósito concreto (clave separada por finalidad)."""

    def __init__(self, key: bytes, *, purpose: str) -> None:
        if len(key) != 32:
            raise ValueError("La clave AES-256-GCM debe tener 32 bytes")
        self._key = key
        self._purpose = purpose
        self._aesgcm = AESGCM(key)

    @property
    def purpose(self) -> str:
        return self._purpose

    def encrypt(self, plaintext: str, *, context: str = "") -> str:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(
            nonce, plaintext.encode("utf-8"), _aad(self._purpose, context)
        )
        return f"{_VERSION}.{_b64e(nonce)}.{_b64e(ciphertext)}"

    def decrypt(self, token: str, *, context: str = "") -> str:
        try:
            version, nonce_b64, ciphertext_b64 = token.split(".", 2)
        except (AttributeError, ValueError) as exc:
            raise CryptoError("formato cifrado inválido") from exc
        if version != _VERSION:
            raise CryptoError("versión de cifrado no soportada")
        try:
            nonce = _b64d(nonce_b64)
            ciphertext = _b64d(ciphertext_b64)
        except (ValueError, TypeError) as exc:
            raise CryptoError("codificación cifrada inválida") from exc
        if len(nonce) != _NONCE_BYTES or not ciphertext:
            raise CryptoError("criptograma inválido")
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, _aad(self._purpose, context))
        except InvalidTag as exc:
            raise CryptoError("autenticación del criptograma fallida") from exc
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - defensivo
            raise CryptoError("texto cifrado inválido") from exc


def build_crypto_services(
    totp_key: bytes, record_key: bytes
) -> tuple[CryptoService, CryptoService]:
    return (
        CryptoService(totp_key, purpose="totp-secret"),
        CryptoService(record_key, purpose="record-field"),
    )
