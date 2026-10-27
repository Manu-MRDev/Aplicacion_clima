"""Servicio de meteorología actual mediante Open-Meteo."""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Mapeo WMO Weather interpretation codes (Open-Meteo).
WMO_CODES: dict[int, str] = {
    0: "Despejado",
    1: "Principalmente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna moderada",
    55: "Llovizna densa",
    56: "Llovizna helada ligera",
    57: "Llovizna helada densa",
    61: "Lluvia ligera",
    63: "Lluvia moderada",
    65: "Lluvia fuerte",
    66: "Lluvia helada ligera",
    67: "Lluvia helada fuerte",
    71: "Nevada ligera",
    73: "Nevada moderada",
    75: "Nevada fuerte",
    77: "Granos de nieve",
    80: "Chubascos ligeros",
    81: "Chubascos moderados",
    82: "Chubascos violentos",
    85: "Chubascos de nieve ligeros",
    86: "Chubascos de nieve fuertes",
    95: "Tormenta eléctrica",
    96: "Tormenta con granizo ligero",
    99: "Tormenta con granizo fuerte",
}


def describe_weather_code(code: int) -> tuple[str, bool]:
    """Devuelve (descripción, conocido). Nunca inventa una condición."""
    description = WMO_CODES.get(code)
    if description is None:
        return f"Condición desconocida (código {code})", False
    return description, True


class WeatherService:
    def __init__(self, settings: Settings, client_getter) -> None:
        self._settings = settings
        self._client_getter = client_getter
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    async def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        key = (round(lat, 3), round(lon, 3))
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return cached[1]

        params = {
            "latitude": f"{lat:.6f}",
            "longitude": f"{lon:.6f}",
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
        }
        client = self._client_getter()
        try:
            response = await client.get(
                self._settings.weather_base_url,
                params=params,
                timeout=self._settings.weather_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Open-Meteo: tiempo de espera agotado")
            raise UpstreamError("El servicio meteorológico no respondió a tiempo") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Open-Meteo: HTTP %s", exc.response.status_code)
            raise UpstreamError() from exc
        except httpx.RequestError as exc:
            logger.warning("Open-Meteo: error de red (%s)", type(exc).__name__)
            raise UpstreamError() from exc
        except ValueError as exc:
            logger.warning("Open-Meteo: respuesta no es JSON válido")
            raise UpstreamError() from exc

        data = self._parse(payload, lat, lon)
        ttl = self._settings.weather_cache_ttl_seconds
        if ttl > 0:
            with self._lock:
                if len(self._cache) > 500:
                    self._cache.clear()
                self._cache[key] = (time.monotonic() + ttl, data)
        return data

    @staticmethod
    def _number(value: Any, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise UpstreamError(f"El servicio meteorológico devolvió un valor inválido ({field})")
        return float(value)

    def _parse(self, payload: Any, lat: float, lon: float) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise UpstreamError("Respuesta incompleta del servicio meteorológico")
        current = payload.get("current")
        if not isinstance(current, dict):
            raise UpstreamError("Respuesta incompleta del servicio meteorológico")

        required = ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "weather_code")
        missing = [field for field in required if current.get(field) is None]
        if missing:
            logger.warning("Open-Meteo: faltan campos %s", ",".join(missing))
            raise UpstreamError("Respuesta incompleta del servicio meteorológico")

        code_value = current["weather_code"]
        if isinstance(code_value, bool) or not isinstance(code_value, int):
            raise UpstreamError("El servicio meteorológico devolvió un código inválido")
        condition, known = describe_weather_code(code_value)

        observed_at = current.get("time")
        if not isinstance(observed_at, str) or not observed_at:
            raise UpstreamError("Respuesta incompleta del servicio meteorológico")

        return {
            "coordinates": {"latitude": lat, "longitude": lon},
            "temperature_c": self._number(current["temperature_2m"], "temperature_2m"),
            "relative_humidity_pct": self._number(
                current["relative_humidity_2m"], "relative_humidity_2m"
            ),
            "wind_speed_kmh": self._number(current["wind_speed_10m"], "wind_speed_10m"),
            "weather_code": code_value,
            "condition": condition,
            "condition_known": known,
            "observed_at": observed_at,
            "timezone": payload.get("timezone") or "UTC",
            "utc_offset_seconds": payload.get("utc_offset_seconds"),
            "units": {
                "temperature": "°C",
                "relative_humidity": "%",
                "wind_speed": "km/h",
            },
            "provider": "open-meteo",
        }
