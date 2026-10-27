"""Utilidades de seguridad: contraseñas, tokens de sesión y CSRF."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Parámetros Argon2id (RFC 9106 / recomendación OWASP).
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Hash señuelo para igualar tiempos cuando el usuario no existe.
DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash(secrets.token_urlsafe(32))

SUPPORTED_ARGON2_PREFIXES = ("$argon2id$", "$argon2i$", "$argon2d$")
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


@dataclass(frozen=True)
class PasswordCheck:
    valid: bool
    needs_rehash: bool = False


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(stored_hash: str, password: str) -> PasswordCheck:
    """Verifica Argon2id y, por compatibilidad, hashes bcrypt existentes.

    Los hashes bcrypt válidos se marcan para rehash a Argon2id tras un login correcto.
    """
    if not stored_hash:
        return PasswordCheck(valid=False)
    try:
        if stored_hash.startswith(SUPPORTED_ARGON2_PREFIXES):
            _PASSWORD_HASHER.verify(stored_hash, password)
            return PasswordCheck(
                valid=True, needs_rehash=_PASSWORD_HASHER.check_needs_rehash(stored_hash)
            )
        if stored_hash.startswith(BCRYPT_PREFIXES):
            # bcrypt solo considera los primeros 72 bytes (compatibilidad histórica).
            candidate = password.encode("utf-8")[:72]
            if bcrypt.checkpw(candidate, stored_hash.encode("utf-8")):
                return PasswordCheck(valid=True, needs_rehash=True)
            return PasswordCheck(valid=False)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError, TypeError):
        return PasswordCheck(valid=False)
    return PasswordCheck(valid=False)


def consume_dummy_verification(password: str) -> None:
    """Ejecuta una verificación descartable para reducir diferencias de tiempo."""
    verify_password(DUMMY_PASSWORD_HASH, password)


def new_session_token() -> str:
    return "s1_" + secrets.token_urlsafe(32)


def session_sid(token: str, *, as_uuid: bool) -> str | uuid.UUID:
    """Deriva un identificador irreversible que se almacena en la base de datos."""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    if as_uuid:
        return uuid.UUID(bytes=digest[:16])
    return digest.hex()


def sid_as_text(sid: str | uuid.UUID) -> str:
    return str(sid)


def csrf_token_for(session_key: bytes, sid_text: str) -> str:
    return hmac.new(session_key, f"csrf:{sid_text}".encode("utf-8"), hashlib.sha256).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def stable_token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
