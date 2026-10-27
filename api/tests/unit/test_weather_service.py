"""Pruebas de Open-Meteo con transporte HTTP simulado."""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import UpstreamError
from app.services.weather_service import WeatherService, describe_weather_code
from tests.support import make_settings

PAYLOAD = {
    "timezone": "America/Mexico_City",
    "utc_offset_seconds": -21600,
    "current": {
        "time": "2026-10-25T12:00",
        "temperature_2m": 21.5,
        "relative_humidity_2m": 55,
        "wind_speed_10m": 12.3,
        "weather_code": 2,
    },
}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_consulta_valida():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    settings = make_settings()
    client = _client(handler)
    service = WeatherService(settings, lambda: client)
    data = await service.get_current(19.35, -99.16)
    await client.aclose()

    assert data["temperature_c"] == 21.5
    assert data["relative_humidity_pct"] == 55.0
    assert data["wind_speed_kmh"] == 12.3
    assert data["condition"] == "Parcialmente nublado"
    assert data["condition_known"] is True
    assert data["coordinates"] == {"latitude": 19.35, "longitude": -99.16}
    assert seen[0].url.params["current"].startswith("temperature_2m")
    assert seen[0].url.params["timezone"] == "auto"


async def test_cache_evita_segunda_llamada():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=PAYLOAD)

    settings = make_settings(weather_cache_ttl_seconds=60)
    client = _client(handler)
    service = WeatherService(settings, lambda: client)
    await service.get_current(19.35, -99.16)
    await service.get_current(19.3501, -99.1601)
    await client.aclose()
    assert calls == 1


async def test_error_http():
    settings = make_settings()
    client = _client(lambda request: httpx.Response(500))
    service = WeatherService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.get_current(19.35, -99.16)
    await client.aclose()


async def test_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("agotado", request=request)

    settings = make_settings()
    client = _client(handler)
    service = WeatherService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.get_current(19.35, -99.16)
    await client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"current": None},
        {"current": {"temperature_2m": 1}},
        {
            "current": {
                "time": "2026-10-25T12:00",
                "temperature_2m": 1,
                "relative_humidity_2m": 2,
                "wind_speed_10m": 3,
                "weather_code": "2",
            }
        },
        {
            "current": {
                "time": "2026-10-25T12:00",
                "temperature_2m": True,
                "relative_humidity_2m": 2,
                "wind_speed_10m": 3,
                "weather_code": 2,
            }
        },
    ],
)
async def test_respuestas_incompletas(payload):
    settings = make_settings()
    client = _client(lambda request: httpx.Response(200, json=payload))
    service = WeatherService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.get_current(19.35, -99.16)
    await client.aclose()


async def test_json_invalido():
    settings = make_settings()
    client = _client(lambda request: httpx.Response(200, text="no-json"))
    service = WeatherService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.get_current(19.35, -99.16)
    await client.aclose()


def test_codigo_desconocido_no_se_inventa():
    description, known = describe_weather_code(123)
    assert known is False
    assert "desconocida" in description
