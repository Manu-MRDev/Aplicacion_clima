"""Rutas de meteorología y geocodificación inversa."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import enforce_rate_limit, get_container
from app.core.container import Container
from app.schemas.common import ErrorResponse
from app.schemas.weather import CurrentWeatherResponse

router = APIRouter(tags=["Servicios externos"])

_UPSTREAM_ERRORS = {
    422: {"model": ErrorResponse, "description": "Coordenadas inválidas"},
    429: {"model": ErrorResponse, "description": "Demasiadas solicitudes"},
    502: {"model": ErrorResponse, "description": "Servicio externo no disponible"},
    503: {"model": ErrorResponse, "description": "Servicio no disponible"},
}


@router.get(
    "/weather/current",
    response_model=CurrentWeatherResponse,
    responses=_UPSTREAM_ERRORS,
    summary="Clima actual por coordenadas",
)
async def current_weather(
    request: Request,
    lat: float = Query(ge=-90, le=90, description="Latitud en grados decimales"),
    lon: float = Query(ge=-180, le=180, description="Longitud en grados decimales"),
    container: Container = Depends(get_container),
) -> CurrentWeatherResponse:
    enforce_rate_limit(
        request, bucket="weather", limit=container.settings.rate_limit_public_per_minute
    )
    data = await container.weather_service.get_current(lat, lon)
    return CurrentWeatherResponse.model_validate(data)
