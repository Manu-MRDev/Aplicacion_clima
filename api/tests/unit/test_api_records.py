"""Pruebas HTTP de registros, CSRF e integridad."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.domain import User
from app.services.auth_service import AuthService
from app.services.crypto_service import CryptoService
from app.services.session_service import SessionService
from app.services.totp_service import TOTPService
from tests.support import (
    FakeApiRecordsService,
    FakeAuthRepository,
    FakeContainer,
    FakeIntegrityService,
    FakeProvider,
    MemorySessionStore,
    make_settings,
)


def build_app(*, integrity_payload=None):
    settings = make_settings()
    user = User(
        id=1,
        username="ana",
        password_hash="x",
        totp_secret_encrypted=None,
        totp_enabled=False,
        created_at=None,
    )
    repository = FakeAuthRepository([user])
    sessions = SessionService(settings, MemorySessionStore(), FakeProvider())
    auth = AuthService(
        settings,
        repository,
        sessions,
        TOTPService(settings, CryptoService(settings.totp_key, purpose="totp-secret")),
    )
    container = FakeContainer(
        settings=settings,
        auth_service=auth,
        session_service=sessions,
        records_service=FakeApiRecordsService(),
        integrity_check_service=FakeIntegrityService(integrity_payload),
    )
    app = create_app(settings, container)
    context = sessions.create_authenticated(user)
    return app, settings, context


def _client(app, settings, context):
    client = TestClient(app, base_url="http://testserver")
    client.cookies.set(settings.cookie_name, context.token)
    return client


def _payload(**overrides):
    data = {
        "servidor": "ubuntu",
        "nombre": "Ana",
        "paterno": "Pérez",
        "materno": "López",
        "estado": "CDMX",
        "municipio": "Coyoacán",
        "latitud": 19.35,
        "longitud": -99.16,
        "temperatura": 21.5,
        "humedad": 55,
        "viento": 12.3,
    }
    data.update(overrides)
    return data


def test_crear_registro():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.post(
            "/api/records",
            json=_payload(),
            headers={"X-CSRF-Token": context.csrf_token},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["registro"]["servidor"] == "ubuntu"
        assert body["integridad"]["status"] == "created"
        assert len(body["integridad"]["hash_actual"]) == 64


def test_crear_sin_csrf():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.post("/api/records", json=_payload())
        assert response.status_code == 403


def test_crear_sin_sesion():
    app, settings, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.post("/api/records", json=_payload()).status_code == 401


def test_windows_exige_paterno():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.post(
            "/api/records",
            json=_payload(servidor="windows", paterno=None),
            headers={"X-CSRF-Token": context.csrf_token},
        )
        assert response.status_code == 422


def test_id_en_insercion_rechazado():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.post(
            "/api/records",
            json=_payload(id=42),
            headers={"X-CSRF-Token": context.csrf_token},
        )
        assert response.status_code == 422


def test_rangos_invalidos():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.post(
            "/api/records",
            json=_payload(humedad=150),
            headers={"X-CSRF-Token": context.csrf_token},
        )
        assert response.status_code == 422


def test_listar_registros():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.get("/api/records?servidor=ambos&limit=10")
        assert response.status_code == 200
        body = response.json()
        assert body["servidor"] == "ambos"
        assert body["paginacion"]["per_source"] is True
        assert body["registros"]
        assert body["fuentes"]["ubuntu"]["status"] == "ok"


def test_listar_rango_invalido():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.get(
            "/api/records?desde=2026-10-25T12:00:00Z&hasta=2026-10-24T12:00:00Z"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"


def test_servidor_invalido():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        assert client.get("/api/records?servidor=otro").status_code == 422


def test_obtener_registro():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        assert client.get("/api/records/1").status_code == 200
        assert client.get("/api/records/999").status_code == 404
        assert client.get("/api/records/0").status_code == 422


def test_verificar_integridad():
    payload = {
        "status": "ok",
        "servidor": "ambos",
        "sources": {
            "ubuntu": {
                "servidor": "ubuntu",
                "status": "ok",
                "bloques_verificados": 2,
                "registros_verificados": 2,
                "registros_sin_bloque": 0,
                "errores": [],
                "advertencias": [],
            }
        },
    }
    app, settings, context = build_app(integrity_payload=payload)
    with _client(app, settings, context) as client:
        response = client.get("/api/integrity/verify?servidor=ambos")
        assert response.status_code == 200
        assert response.json()["sources"]["ubuntu"]["bloques_verificados"] == 2


def test_integridad_requiere_sesion():
    app, settings, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/integrity/verify").status_code == 401


def test_headers_de_seguridad_y_request_id():
    app, settings, context = build_app()
    with _client(app, settings, context) as client:
        response = client.get(
            "/api/records", headers={"X-Request-ID": "abc123"}
        )
        assert response.headers["X-Request-ID"] == "abc123"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Cache-Control"] == "no-store"
