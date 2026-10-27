"""Pruebas de contraseñas, tokens de sesión y CSRF."""

from __future__ import annotations

import hashlib
import uuid

import bcrypt
import pytest

from app.core.security import (
    constant_time_equals,
    consume_dummy_verification,
    csrf_token_for,
    hash_password,
    new_session_token,
    session_sid,
    stable_token_hash,
    verify_password,
)


def test_argon2id_roundtrip_y_rehash():
    stored = hash_password("Contraseña-Segura-123")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "Contraseña-Segura-123").valid
    assert not verify_password(stored, "otra").valid
    # El hash actual no debería necesitar rehash con los parámetros vigentes.
    assert verify_password(stored, "Contraseña-Segura-123").needs_rehash is False


def test_hash_vacio_y_corrupto():
    assert not verify_password("", "x").valid
    assert not verify_password("no-es-un-hash", "x").valid


def test_bcrypt_legado_se_marca_para_rehash():
    stored = bcrypt.hashpw(b"clave-legada", bcrypt.gensalt(rounds=4)).decode("ascii")
    check = verify_password(stored, "clave-legada")
    assert check.valid
    assert check.needs_rehash


def test_bcrypt_legado_incorrecto():
    stored = bcrypt.hashpw(b"clave-legada", bcrypt.gensalt(rounds=4)).decode("ascii")
    assert not verify_password(stored, "incorrecta").valid


def test_dummy_no_lanza():
    consume_dummy_verification("cualquiera")


def test_token_de_sesion_es_opaco_y_unico():
    first = new_session_token()
    second = new_session_token()
    assert first.startswith("s1_")
    assert first != second
    assert len(first) > 30


def test_sid_hex_es_sha256_del_token():
    token = "s1_abc"
    assert session_sid(token, as_uuid=False) == hashlib.sha256(token.encode()).hexdigest()


def test_sid_uuid_es_determinista():
    token = "s1_abc"
    first = session_sid(token, as_uuid=True)
    second = session_sid(token, as_uuid=True)
    assert isinstance(first, uuid.UUID)
    assert first == second
    assert first.bytes == hashlib.sha256(token.encode()).digest()[:16]


def test_csrf_depende_de_clave_y_sid():
    first = csrf_token_for(b"a" * 32, "sid-1")
    second = csrf_token_for(b"a" * 32, "sid-1")
    other_sid = csrf_token_for(b"a" * 32, "sid-2")
    other_key = csrf_token_for(b"b" * 32, "sid-1")
    assert first == second
    assert first != other_sid
    assert first != other_key


def test_comparacion_tiempo_constante():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")


def test_hash_estable_no_reversible():
    digest = stable_token_hash("Usuario")
    assert digest == stable_token_hash("Usuario")
    assert len(digest) == 64
    assert "Usuario" not in digest


@pytest.mark.parametrize("password", ["a" * 72, "ñ" * 40, "emoji-🔐-123"])
def test_passwords_unicodes(password: str):
    stored = hash_password(password)
    assert verify_password(stored, password).valid
