"""Pruebas de Nominatim con transporte HTTP simulado."""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import NotFoundError, UpstreamError
from app.services.geocoding_service import ATTRIBUTION, GeocodingService
from tests.support import make_settings

PAYLOAD = {
    "display_name": "Coyoacán, Ciudad de México, México",
    "address": {
        "municipality": "Coyoacán",
        "state": "Ciudad de México",
        "country": "México",
        "country_code": "mx",
        "city": "Coyoacán",
    },
}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_geocodificacion_valida():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    settings = make_settings()
    client = _client(handler)
    service = GeocodingService(settings, lambda: client)
    data = await service.reverse(19.35, -99.16)
    await client.aclose()

    assert data["municipio"] == "Coyoacán"
    assert data["estado"] == "Ciudad de México"
    assert data["pais"] == "México"
    assert data["attribution"] == ATTRIBUTION
    assert seen[0].headers["user-agent"] == settings.geocoding_user_agent
    assert seen[0].url.path == "/reverse"
    assert seen[0].url.params["format"] == "jsonv2"
    assert seen[0].url.params["accept-language"] == "es"


async def test_cache_evita_segunda_llamada():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=PAYLOAD)

    settings = make_settings(geocoding_cache_ttl_seconds=60)
    client = _client(handler)
    service = GeocodingService(settings, lambda: client)
    await service.reverse(19.35, -99.16)
    await service.reverse(19.35001, -99.16001)
    await client.aclose()
    assert calls == 1


async def test_404_es_no_encontrado():
    settings = make_settings()
    client = _client(lambda request: httpx.Response(404))
    service = GeocodingService(settings, lambda: client)
    with pytest.raises(NotFoundError):
        await service.reverse(0, 0)
    await client.aclose()


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_errores_del_proveedor(status):
    settings = make_settings()
    client = _client(lambda request: httpx.Response(status))
    service = GeocodingService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.reverse(19.35, -99.16)
    await client.aclose()


async def test_json_invalido():
    settings = make_settings()
    client = _client(lambda request: httpx.Response(200, text="no-json"))
    service = GeocodingService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.reverse(19.35, -99.16)
    await client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "Unable to geocode"},
        {"display_name": "x"},
        {"address": {"country": "México"}},
    ],
)
async def test_sin_localidad(payload):
    settings = make_settings()
    client = _client(lambda request: httpx.Response(200, json=payload))
    service = GeocodingService(settings, lambda: client)
    with pytest.raises(NotFoundError):
        await service.reverse(19.35, -99.16)
    await client.aclose()


async def test_error_de_red():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    settings = make_settings()
    client = _client(handler)
    service = GeocodingService(settings, lambda: client)
    with pytest.raises(UpstreamError):
        await service.reverse(19.35, -99.16)
    await client.aclose()
