"""Geocodificación inversa mediante Nominatim (OpenStreetMap)."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import NotFoundError, UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)

ATTRIBUTION = "© OpenStreetMap contributors"


class GeocodingService:
    def __init__(self, settings: Settings, client_getter) -> None:
        self._settings = settings
        self._client_getter = client_getter
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()
        self._throttle_lock = asyncio.Lock()
        self._last_request = 0.0

    async def reverse(self, lat: float, lon: float) -> dict[str, Any]:
        key = (round(lat, 4), round(lon, 4))
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]

        await self._throttle()
        params = {
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "format": "jsonv2",
            "zoom": "10",
            "addressdetails": "1",
            "accept-language": self._settings.geocoding_accept_language,
        }
        client = self._client_getter()
        try:
            response = await client.get(
                f"{self._settings.geocoding_base_url.rstrip('/')}/reverse",
                params=params,
                headers={"User-Agent": self._settings.geocoding_user_agent},
                timeout=self._settings.geocoding_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("Nominatim: tiempo de espera agotado")
            raise UpstreamError("El servicio de geocodificación no respondió a tiempo") from exc
        except httpx.RequestError as exc:
            logger.warning("Nominatim: error de red (%s)", type(exc).__name__)
            raise UpstreamError() from exc

        if response.status_code == 404:
            raise NotFoundError("No se pudo identificar una localidad para esas coordenadas")
        if response.status_code in (403, 429):
            logger.warning("Nominatim: límite de uso alcanzado (%s)", response.status_code)
            raise UpstreamError("El servicio de geocodificación no está disponible temporalmente")
        if response.status_code >= 400:
            logger.warning("Nominatim: HTTP %s", response.status_code)
            raise UpstreamError()

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError("Respuesta inválida del servicio de geocodificación") from exc
        if not isinstance(payload, dict) or payload.get("error"):
            raise NotFoundError("No se pudo identificar una localidad para esas coordenadas")

        address = payload.get("address")
        if not isinstance(address, dict):
            raise NotFoundError("No se pudo identificar una localidad para esas coordenadas")

        def pick(*keys: str) -> str | None:
            for name in keys:
                value = address.get(name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return None

        municipio = pick(
            "municipality", "city", "town", "village", "hamlet", "county", "state_district"
        )
        estado = pick("state", "region", "province", "state_district", "county")
        locality = pick("city", "town", "village", "hamlet", "municipality")
        country = pick("country")

        if not municipio and not estado:
            raise NotFoundError("No se pudo identificar una localidad para esas coordenadas")

        result = {
            "coordinates": {"latitude": lat, "longitude": lon},
            "city": locality,
            "municipio": municipio,
            "estado": estado,
            "pais": country,
            "country_code": pick("country_code"),
            "display_name": payload.get("display_name"),
            "provider": "nominatim",
            "attribution": ATTRIBUTION,
        }
        ttl = self._settings.geocoding_cache_ttl_seconds
        if ttl > 0:
            with self._cache_lock:
                if len(self._cache) > 1000:
                    self._cache.clear()
                self._cache[key] = (time.monotonic() + ttl, result)
        return result

    async def _throttle(self) -> None:
        interval = self._settings.geocoding_min_interval_seconds
        if interval <= 0:
            return
        async with self._throttle_lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request = time.monotonic()
