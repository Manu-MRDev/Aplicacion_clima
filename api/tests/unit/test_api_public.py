"""Pruebas HTTP de salud, servicios externos, docs y CORS."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, UpstreamError
from app.main import create_app
from tests.support import (
    FakeContainer,
    FakeGeocodingService,
    FakeWeatherService,
    make_settings,
)

WEATHER = {
    "coordinates": {"latitude": 19.35, "longitude": -99.16},
    "temperature_c": 21.5,
    "relative_humidity_pct": 55,
    "wind_speed_kmh": 12.3,
    "weather_code": 2,
    "condition": "Parcialmente nublado",
    "condition_known": True,
    "observed_at": "2026-10-25T12:00",
    "timezone": "America/Mexico_City",
    "utc_offset_seconds": -21600,
    "units": {"temperature": "°C", "relative_humidity": "%", "wind_speed": "km/h"},
    "provider": "open-meteo",
}

LOCATION = {
    "coordinates": {"latitude": 19.35, "longitude": -99.16},
    "city": "Coyoacán",
    "municipio": "Coyoacán",
    "estado": "Ciudad de México",
    "pais": "México",
    "country_code": "mx",
    "display_name": "Coyoacán, Ciudad de México, México",
    "provider": "nominatim",
    "attribution": "© OpenStreetMap contributors",
}


def build_app(*, weather=None, geocoding=None, settings=None):
    settings = settings or make_settings()
    weather_service = weather or FakeWeatherService(WEATHER)
    geocoding_service = geocoding or FakeGeocodingService(LOCATION)
    container = FakeContainer(
        settings=settings,
        auth_service=None,
        session_service=None,
        weather_service=weather_service,
        geocoding_service=geocoding_service,
    )
    return create_app(settings, container), weather_service, geocoding_service


def test_health_live_y_ready():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "ok"

        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ok"

        strict = client.get("/health/ready?strict=true")
        assert strict.status_code == 200


def test_root():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["docs"] == "/docs"


def test_clima_actual():
    app, weather, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/api/weather/current?lat=19.35&lon=-99.16")
        assert response.status_code == 200
        body = response.json()
        assert body["temperature_c"] == 21.5
        assert body["condition"] == "Parcialmente nublado"
        assert body["provider"] == "open-meteo"
    assert weather.calls == [(19.35, -99.16)]


def test_clima_coordenadas_invalidas():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/api/weather/current?lat=91&lon=0").status_code == 422
        assert client.get("/api/weather/current?lat=0&lon=-181").status_code == 422


def test_clima_error_del_proveedor():
    app, _, _ = build_app(weather=FakeWeatherService(error=UpstreamError()))
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/api/weather/current?lat=19.35&lon=-99.16")
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "upstream_error"


def test_geocodificacion_inversa():
    app, _, geocoding = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/api/locations/reverse?lat=19.35&lon=-99.16")
        assert response.status_code == 200
        assert response.json()["municipio"] == "Coyoacán"
        assert response.json()["attribution"].startswith("©")
    assert geocoding.calls == [(19.35, -99.16)]


def test_geocodificacion_no_encontrada():
    app, _, _ = build_app(
        geocoding=FakeGeocodingService(error=NotFoundError("sin localidad"))
    )
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/api/locations/reverse?lat=0&lon=0")
        assert response.status_code == 404


def test_docs_en_desarrollo():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/docs").status_code == 200
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        paths = openapi.json()["paths"]
        assert "/api/auth/login" in paths
        assert "/api/records" in paths
        assert "/api/integrity/verify" in paths


def test_docs_ocultos_en_produccion():
    settings = make_settings(
        app_env="production", postgres_sslmode="require", docs_enabled=None
    )
    app, _, _ = build_app(settings=settings)
    with TestClient(app, base_url="http://testserver") as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_error_404_con_formato_uniforme():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/api/no-existe")
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "not_found"
        assert error["request_id"]


def test_metodo_no_permitido():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.put("/api/weather/current")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"


def test_cors_preflight_origen_permitido():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://frontend.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://frontend.test"
        assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_no_refleja_origen_desconocido():
    app, _, _ = build_app()
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get(
            "/health/live", headers={"Origin": "https://malicioso.example"}
        )
        assert "access-control-allow-origin" not in response.headers
