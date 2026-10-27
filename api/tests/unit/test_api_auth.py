"""Pruebas HTTP del flujo de autenticación con servicios reales y store en memoria."""

from __future__ import annotations

from functools import lru_cache

import pyotp
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.time import utcnow
from app.main import create_app
from app.models.domain import User
from app.services.auth_service import AuthService
from app.services.crypto_service import CryptoService
from app.services.session_service import SessionService
from app.services.totp_service import TOTPService
from tests.support import (
    FakeAuthRepository,
    FakeContainer,
    FakeProvider,
    MemorySessionStore,
    make_settings,
)

PASSWORD = "Clave-HTTP-2026"
SECRET = "JBSWY3DPEHPK3PXP"


@lru_cache(maxsize=1)
def password_hash() -> str:
    return hash_password(PASSWORD)


def _users(password_hash: str, settings) -> FakeAuthRepository:
    encrypted = CryptoService(settings.totp_key, purpose="totp-secret").encrypt(
        SECRET, context="user:2"
    )
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
                totp_secret_encrypted=encrypted,
                totp_enabled=True,
                created_at=utcnow(),
            ),
            User(
                id=3,
                username="legado",
                password_hash=password_hash,
                totp_secret_encrypted="formato-legado",
                totp_enabled=True,
                created_at=utcnow(),
            ),
        ]
    )


def build_app(*, users=None, settings=None):
    settings = settings or make_settings()
    repository = users or _users(password_hash(), settings)
    sessions = SessionService(settings, MemorySessionStore(), FakeProvider())
    totp = TOTPService(settings, CryptoService(settings.totp_key, purpose="totp-secret"))
    auth = AuthService(settings, repository, sessions, totp)
    container = FakeContainer(
        settings=settings, auth_service=auth, session_service=sessions
    )
    return create_app(settings, container), repository, settings, sessions


def test_flujo_completo_inscripcion_y_logout():
    app, repository, settings, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login", json={"username": "ana", "password": PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "enrollment_required"
        assert settings.cookie_name in client.cookies
        csrf = body["csrf_token"]

        # Una sesión pendiente no accede a /me.
        assert client.get("/api/auth/me").status_code == 401

        enroll = client.post(
            "/api/auth/totp/enroll", headers={"X-CSRF-Token": csrf}
        )
        assert enroll.status_code == 200
        enrollment = enroll.json()
        assert enrollment["manual_key"]
        assert enrollment["qr_data_uri"].startswith("data:image/png;base64,")

        code = pyotp.TOTP(enrollment["manual_key"], interval=30).now()
        confirm = client.post(
            "/api/auth/totp/confirm",
            json={"code": code},
            headers={"X-CSRF-Token": csrf},
        )
        assert confirm.status_code == 200
        authenticated = confirm.json()
        assert authenticated["status"] == "authenticated"
        assert authenticated["user"]["username"] == "ana"
        csrf = authenticated["csrf_token"]

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["totp_enabled"] is True

        logout = client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": csrf}
        )
        assert logout.status_code == 200
        assert logout.json()["status"] == "logged_out"
        assert client.get("/api/auth/me").status_code == 401
    assert repository.users[1].totp_enabled is True


def test_registro_crea_cuenta_y_exige_inscripcion():
    app, repository, settings, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "nuevo", "password": PASSWORD},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "enrollment_required"
        assert settings.cookie_name in client.cookies
        csrf = body["csrf_token"]

        # La cuenta creada no obtiene acceso hasta confirmar TOTP.
        assert client.get("/api/auth/me").status_code == 401

        enroll = client.post(
            "/api/auth/totp/enroll", headers={"X-CSRF-Token": csrf}
        )
        assert enroll.status_code == 200
        enrollment = enroll.json()
        code = pyotp.TOTP(enrollment["manual_key"], interval=30).now()
        confirm = client.post(
            "/api/auth/totp/confirm",
            json={"code": code},
            headers={"X-CSRF-Token": csrf},
        )
        assert confirm.status_code == 200
        assert confirm.json()["user"]["username"] == "nuevo"
        assert client.get("/api/auth/me").status_code == 200

    created = repository.get_by_username("nuevo")
    assert created is not None
    assert created.totp_enabled is True


def test_registro_duplicado_devuelve_conflicto():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register", json={"username": "ana", "password": PASSWORD}
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"


def test_registro_deshabilitado():
    app, _, _, _ = build_app(settings=make_settings(registration_enabled=False))
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "nuevo", "password": PASSWORD},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


def test_registro_valida_y_no_ecoa_la_contrasena():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "nuevo", "password": "corta"},
        )
        assert response.status_code == 422
        assert "corta" not in response.text
        assert response.json()["error"]["code"] == "validation_error"


def test_registro_rechaza_campos_extra():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "nuevo", "password": PASSWORD, "admin": True},
        )
        assert response.status_code == 422


def test_registro_rechaza_origen_cruzado():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "nuevo", "password": PASSWORD},
            headers={"Origin": "https://malicioso.example"},
        )
        assert response.status_code == 403


def test_registro_limitado_por_ip():
    settings = make_settings(rate_limit_register_per_minute=3)
    app, _, _, _ = build_app(settings=settings)
    with TestClient(app, base_url="http://testserver") as client:
        statuses = []
        for index in range(4):
            response = client.post(
                "/api/auth/register",
                json={"username": f"nuevo{index}", "password": PASSWORD},
            )
            statuses.append(response.status_code)
        assert statuses[:3] == [201, 201, 201]
        assert statuses[3] == 429
        assert "Retry-After" in response.headers


def test_flujo_totp_existente():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        login = client.post(
            "/api/auth/login", json={"username": "luis", "password": PASSWORD}
        )
        assert login.status_code == 200
        assert login.json()["status"] == "totp_required"
        csrf = login.json()["csrf_token"]

        code = pyotp.TOTP(SECRET, interval=30).now()
        verify = client.post(
            "/api/auth/totp/verify",
            json={"code": code},
            headers={"X-CSRF-Token": csrf},
        )
        assert verify.status_code == 200
        assert verify.json()["status"] == "authenticated"
        assert client.get("/api/auth/me").status_code == 200


def test_csrf_ausente_en_inscripcion():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.post(
            "/api/auth/login", json={"username": "ana", "password": PASSWORD}
        ).status_code == 200
        response = client.post("/api/auth/totp/enroll")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


def test_origen_cruzado_rechazado():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "ana", "password": PASSWORD},
            headers={"Origin": "https://malicioso.example"},
        )
        assert response.status_code == 403


def test_origen_propio_aceptado():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "ana", "password": PASSWORD},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200


def test_credenciales_incorrectas_no_crean_sesion():
    app, _, settings, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login", json={"username": "ana", "password": "incorrecta"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert settings.cookie_name not in client.cookies


def test_totp_legado_devuelve_503():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        login = client.post(
            "/api/auth/login", json={"username": "legado", "password": PASSWORD}
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        response = client.post(
            "/api/auth/totp/verify",
            json={"code": "123456"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_unavailable"


def test_validacion_no_ecoa_la_contrasena():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login", json={"username": "ana", "password": ""}
        )
        assert response.status_code == 422
        assert "Clave" not in response.text
        assert response.json()["error"]["code"] == "validation_error"


def test_campo_extra_rechazado():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "ana", "password": PASSWORD, "admin": True},
        )
        assert response.status_code == 422


def test_rate_limit_de_login():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        statuses = []
        for _ in range(6):
            response = client.post(
                "/api/auth/login",
                json={"username": "nadie", "password": PASSWORD},
            )
            statuses.append(response.status_code)
        assert statuses[:5] == [401] * 5
        assert statuses[5] == 429
        assert "Retry-After" in response.headers


def test_me_sin_cookie():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/auth/me").status_code == 401


def test_sesion_pendiente_no_permite_records():
    app, _, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD})
        assert client.get("/api/records").status_code == 401
