"""Esquemas de meteorología y geocodificación."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class WeatherUnits(BaseModel):
    temperature: str
    relative_humidity: str
    wind_speed: str


class CurrentWeatherResponse(BaseModel):
    coordinates: Coordinates
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_kmh: float
    weather_code: int
    condition: str
    condition_known: bool
    observed_at: str
    timezone: str
    utc_offset_seconds: int | None = None
    units: WeatherUnits
    provider: str


class ReverseLocationResponse(BaseModel):
    coordinates: Coordinates
    city: str | None = None
    municipio: str | None = None
    estado: str | None = None
    pais: str | None = None
    country_code: str | None = None
    display_name: str | None = None
    provider: str
    attribution: str
