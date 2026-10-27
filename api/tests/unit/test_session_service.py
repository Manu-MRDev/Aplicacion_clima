"""Pruebas del ciclo de vida de sesiones."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import csrf_token_for, session_sid
from app.core.time import utcnow
from app.models.domain import User
from app.services.session_service import SessionService
from tests.support import FakeProvider, MemorySessionStore


@pytest.fixture
def user() -> User:
    return User(
        id=1,
        username="ana",
        password_hash="x",
        totp_secret_encrypted=None,
        totp_enabled=False,
        created_at=utcnow(),
    )


@pytest.fixture
def service(settings) -> SessionService:
    return SessionService(settings, MemorySessionStore(), FakeProvider())


def test_crear_y_leer_sesion_pendiente(service, user):
    context = service.create_pending(user, "pending_enroll")
    assert context.state == "pending_enroll"
    assert context.token.startswith("s1_")
    assert context.csrf_token == csrf_token_for(
        service._settings.session_key, str(context.sid)
    )

    loaded = service.get(context.token)
    assert loaded is not None
    assert loaded.user_id == user.id
    assert loaded.username == "ana"
    assert loaded.state == "pending_enroll"
    assert loaded.csrf_token == context.csrf_token


def test_token_ajeno_o_malformado(service):
    assert service.get(None) is None
    assert service.get("") is None
    assert service.get("otro") is None
    assert service.get("s1_no-existe") is None


def test_payload_ajeno_no_se_elimina(service, user):
    token = "s1_token-ajeno"
    sid = session_sid(token, as_uuid=False)
    service._store.create(sid, {"etapa": "legacy", "usuario": "otro"}, utcnow() + timedelta(hours=1))
    assert service.get(token) is None
    assert str(sid) in service._store.rows


def test_sesion_expirada_se_elimina(service, user):
    context = service.create_pending(user, "pending_totp")
    payload, _ = service._store.rows[str(context.sid)]
    service._store.rows[str(context.sid)] = (payload, utcnow() - timedelta(seconds=1))
    assert service.get(context.token) is None
    assert str(context.sid) not in service._store.rows


def test_expiracion_absoluta(service, user):
    context = service.create_authenticated(user)
    context.absolute_expires_at = utcnow() - timedelta(seconds=1)
    service._store.update(context.sid, context.to_payload(), context.idle_expires_at)
    assert service.get(context.token) is None


def test_touch_renueva_solo_si_es_autenticada(service, user):
    pending = service.create_pending(user, "pending_enroll")
    old_pending = pending.idle_expires_at
    loaded = service.get(pending.token)
    assert loaded is not None
    assert loaded.idle_expires_at == old_pending

    authenticated = service.create_authenticated(user)
    authenticated.idle_expires_at = utcnow() + timedelta(seconds=60)
    service._store.update(
        authenticated.sid, authenticated.to_payload(), authenticated.idle_expires_at
    )
    refreshed = service.get(authenticated.token)
    assert refreshed is not None
    assert refreshed.idle_expires_at > authenticated.idle_expires_at


def test_rotacion_invalida_el_sid_anterior(service, user):
    pending = service.create_pending(user, "pending_totp")
    rotated = service.rotate_authenticated(pending, user)
    assert rotated.state == "authenticated"
    assert rotated.sid != pending.sid
    assert rotated.csrf_token != pending.csrf_token
    assert service.get(pending.token) is None
    assert service.get(rotated.token) is not None


def test_require_valida_estado(service, user):
    pending = service.create_pending(user, "pending_totp")
    with pytest.raises(UnauthorizedError):
        service.require(pending.token, state="authenticated")
    assert service.require(pending.token, state="pending_totp").state == "pending_totp"


def test_revocar(service, user):
    context = service.create_authenticated(user)
    service.revoke(context)
    assert service.get(context.token) is None


def test_sid_uuid_cuando_la_columna_lo_exige(settings, user):
    store = MemorySessionStore()
    service = SessionService(settings, store, FakeProvider(sid_is_uuid=True))
    context = service.create_pending(user, "pending_enroll")
    assert str(context.sid) in store.rows
    loaded = service.get(context.token)
    assert loaded is not None
    assert loaded.sid == context.sid
