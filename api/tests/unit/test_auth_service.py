"""Pruebas de autenticación, bloqueo, TOTP e inscripción."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pyotp
import pytest

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    RateLimitedError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.core.time import utcnow
from app.models.domain import User
from app.services import totp_service as totp_module
from app.services.auth_service import AuthService
from app.services.crypto_service import CryptoService
from app.services.session_service import SessionService
from app.services.totp_service import TOTPService
from tests.support import FakeAuthRepository, FakeProvider, MemorySessionStore, make_settings

PASSWORD = "Clave-De-Prueba-2026"
FIXED_TIME = 1_800_000_000
COUNTER = FIXED_TIME // 30
SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture(scope="module")
def password_hash() -> str:
    return hash_password(PASSWORD)


@pytest.fixture
def totp(settings, monkeypatch) -> TOTPService:
    monkeypatch.setattr(totp_module, "time", SimpleNamespace(time=lambda: FIXED_TIME))
    return TOTPService(settings, CryptoService(settings.totp_key, purpose="totp-secret"))


@pytest.fixture
def users(password_hash) -> FakeAuthRepository:
    return FakeAuthRepository(
        [
            User(
                id=1,
                username="ana",
                password_hash=password_hash,
                totp_secret_encrypted=None,
                totp_enabled=False,
                created_at=utcnow(),
            ),
            User(
                id=2,
                username="luis",
                password_hash=password_hash,
                totp_secret_encrypted=totp_encrypt(SECRET, 2),
                totp_enabled=True,
                created_at=utcnow(),
            ),
        ]
    )


def totp_encrypt(secret: str, user_id: int) -> str:
    from tests.support import make_settings

    settings = make_settings()
    return CryptoService(settings.totp_key, purpose="totp-secret").encrypt(
        secret, context=f"user:{user_id}"
    )


@pytest.fixture
def service(settings, users, totp) -> AuthService:
    sessions = SessionService(settings, MemorySessionStore(), FakeProvider())
    return AuthService(settings, users, sessions, totp)


def code(counter: int = COUNTER) -> str:
    return pyotp.TOTP(SECRET, interval=30).generate_otp(counter)


def test_login_usuario_inexistente(service, users):
    with pytest.raises(UnauthorizedError):
        service.login("nadie", PASSWORD)
    assert users.failed_attempts == 0


def test_login_password_incorrecta(service, users):
    with pytest.raises(UnauthorizedError):
        service.login("ana", "incorrecta")
    assert users.users[1].intentos_fallidos == 1
    assert users.failed_attempts == 1


def test_login_cuenta_bloqueada(service, users):
    users.users[1] = replace(users.users[1], bloqueado_hasta=utcnow() + timedelta(minutes=10))
    with pytest.raises(UnauthorizedError):
        service.login("ana", PASSWORD)


def test_login_sin_totp_pide_inscripcion(service, users):
    result = service.login("ana", PASSWORD)
    assert result.next_step == "enrollment_required"
    assert result.context.state == "pending_enroll"
    assert result.context.is_authenticated is False
    assert users.successes == 1


def test_login_con_totp_pide_segundo_factor(service):
    result = service.login("luis", PASSWORD)
    assert result.next_step == "totp_required"
    assert result.context.state == "pending_totp"


def test_login_totp_habilitado_sin_secreto(service, users):
    users.users[2] = replace(users.users[2], totp_secret_encrypted=None)
    with pytest.raises(ServiceUnavailableError):
        service.login("luis", PASSWORD)


def test_registro_crea_usuario_y_sesion_pendiente(service, users):
    result = service.register("nuevo", PASSWORD)

    assert result.next_step == "enrollment_required"
    assert result.context.state == "pending_enroll"
    user = users.get_by_username("nuevo")
    assert user is not None
    assert user.id == result.context.user_id
    assert user.totp_enabled is False
    assert user.totp_secret_encrypted is None
    assert verify_password(user.password_hash, PASSWORD).valid


def test_registro_rechaza_usuario_duplicado(service):
    with pytest.raises(ConflictError):
        service.register("ana", PASSWORD)


def test_registro_deshabilitado_por_configuracion(users, totp):
    settings = make_settings(registration_enabled=False)
    sessions = SessionService(settings, MemorySessionStore(), FakeProvider())
    auth = AuthService(settings, users, sessions, totp)

    with pytest.raises(ForbiddenError):
        auth.register("nuevo", PASSWORD)


def test_verificar_totp_y_rotar_sesion(service, users):
    pending = service.login("luis", PASSWORD).context
    result = service.verify_totp(pending, code())
    assert result.context.state == "authenticated"
    assert result.context.sid != pending.sid
    assert result.user.totp_ultimo_counter == COUNTER
    assert users.users[2].totp_ultimo_counter == COUNTER


def test_codigo_totp_reutilizado(service, users):
    pending = service.login("luis", PASSWORD).context
    service.verify_totp(pending, code())
    second = service.login("luis", PASSWORD).context
    with pytest.raises(UnauthorizedError):
        service.verify_totp(second, code())


def test_totp_con_estado_incorrecto(service):
    pending = service.login("ana", PASSWORD).context
    with pytest.raises(UnauthorizedError):
        service.verify_totp(pending, code())


def test_totp_legado_no_descifrable(service, users):
    users.users[2] = replace(
        users.users[2], totp_secret_encrypted="secreto-legado-en-otro-formato"
    )
    pending = service.login("luis", PASSWORD).context
    with pytest.raises(ServiceUnavailableError):
        service.verify_totp(pending, code())


def test_totp_incorrecto_incrementa_fallos(service, users):
    pending = service.login("luis", PASSWORD).context
    with pytest.raises(UnauthorizedError):
        service.verify_totp(pending, wrong_code())
    assert users.users[2].intentos_fallidos == 1


def test_inscripcion_completa(service, users):
    pending = service.login("ana", PASSWORD).context
    enrollment = service.begin_enrollment(pending)
    assert enrollment.manual_key
    assert enrollment.qr_data_uri.startswith("data:image/png;base64,")
    assert pending.enroll is not None

    result = service.confirm_enrollment(
        pending, code_for_secret(enrollment.manual_key)
    )
    assert result.context.state == "authenticated"
    assert users.users[1].totp_enabled is True
    assert users.users[1].totp_ultimo_counter == COUNTER
    assert users.users[1].totp_secret_encrypted is not None


def code_for_secret(secret: str, counter: int = COUNTER) -> str:
    return pyotp.TOTP(secret, interval=30).generate_otp(counter)


def wrong_code(secret: str = SECRET) -> str:
    valid = {code_for_secret(secret, COUNTER + offset) for offset in (-1, 0, 1)}
    for candidate in range(1_000_000):
        code = f"{candidate:06d}"
        if code not in valid:
            return code
    raise AssertionError("no se encontró un código inválido")


def test_inscripcion_sin_sesion_adecuada(service):
    pending = service.login("luis", PASSWORD).context
    with pytest.raises(UnauthorizedError):
        service.begin_enrollment(pending)


def test_inscripcion_de_cuenta_ya_configurada(service, users):
    users.users[1] = replace(
        users.users[1], totp_enabled=True, totp_secret_encrypted="v1.x.y"
    )
    pending = service._sessions.create_pending(users.users[1], "pending_enroll")
    with pytest.raises(ConflictError):
        service.begin_enrollment(pending)


def test_inscripcion_limitada_por_hora(service):
    pending = service.login("ana", PASSWORD).context
    pending.enroll = {
        "generation_times": [
            (utcnow() - timedelta(minutes=1)).isoformat(),
            (utcnow() - timedelta(minutes=2)).isoformat(),
            (utcnow() - timedelta(minutes=3)).isoformat(),
        ]
    }
    with pytest.raises(RateLimitedError):
        service.begin_enrollment(pending)


def test_confirmar_sin_inscripcion(service):
    pending = service.login("ana", PASSWORD).context
    with pytest.raises(ConflictError):
        service.confirm_enrollment(pending, "123456")


def test_confirmar_codigo_incorrecto(service):
    pending = service.login("ana", PASSWORD).context
    enrollment = service.begin_enrollment(pending)
    with pytest.raises(UnauthorizedError):
        service.confirm_enrollment(pending, wrong_code(enrollment.manual_key))
    assert pending.enroll is not None
    assert pending.enroll["attempts"] == 1


def test_inscripcion_expirada_por_password_antigua(service, users):
    pending = service.login("ana", PASSWORD).context
    pending.password_verified_at = utcnow() - timedelta(hours=1)
    with pytest.raises(UnauthorizedError):
        service.begin_enrollment(pending)


def test_logout_revoca(service, users):
    pending = service.login("ana", PASSWORD).context
    service.logout(pending)
    assert service._sessions.get(pending.token) is None


def test_current_user(service, users):
    pending = service.login("ana", PASSWORD).context
    assert service.current_user(pending).username == "ana"
    service.logout(pending)
    assert service._sessions.get(pending.token) is None
