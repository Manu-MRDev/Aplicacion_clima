"""Rutas de disponibilidad."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.core.container import Container

router = APIRouter(prefix="/health", tags=["Disponibilidad"])


@router.get("/live", summary="La aplicación está en ejecución")
def live(container: Container = Depends(get_container)) -> dict[str, str]:
    return {"status": "ok", "service": container.settings.app_name}


@router.get("/ready", summary="Estado de las dependencias")
def ready(
    strict: bool = Query(default=False, description="Devuelve 503 si el estado no es 'ok'"),
    container: Container = Depends(get_container),
):
    payload = container.readiness()
    if strict and payload["status"] != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload
