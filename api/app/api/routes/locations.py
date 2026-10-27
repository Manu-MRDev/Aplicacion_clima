"""Ruta de geocodificación inversa (Nominatim / OpenStreetMap)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import enforce_rate_limit, get_container
from app.core.container import Container
from app.schemas.common import ErrorResponse
from app.schemas.weather import ReverseLocationResponse

router = APIRouter(tags=["Servicios externos"])


@router.get(
    "/locations/reverse",
    response_model=ReverseLocationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Localidad no identificada"},
        422: {"model": ErrorResponse, "description": "Coordenadas inválidas"},
        429: {"model": ErrorResponse, "description": "Demasiadas solicitudes"},
        502: {"model": ErrorResponse, "description": "Servicio externo no disponible"},
    },
    summary="Geocodificación inversa a partir de coordenadas",
)
async def reverse_location(
    request: Request,
    lat: float = Query(ge=-90, le=90, description="Latitud en grados decimales"),
    lon: float = Query(ge=-180, le=180, description="Longitud en grados decimales"),
    container: Container = Depends(get_container),
) -> ReverseLocationResponse:
    enforce_rate_limit(
        request, bucket="geocode", limit=container.settings.rate_limit_public_per_minute
    )
    data = await container.geocoding_service.reverse(lat, lon)
    return ReverseLocationResponse.model_validate(data)
