"""Esquemas comunes y utilidades de validación."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Servidor(str, Enum):
    ubuntu = "ubuntu"
    windows = "windows"


class ServidorQuery(str, Enum):
    ubuntu = "ubuntu"
    windows = "windows"
    ambos = "ambos"


class OrdenCampo(str, Enum):
    fecha_hora = "fecha_hora"
    id = "id"


class Direccion(str, Enum):
    asc = "asc"
    desc = "desc"


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Pagination(BaseModel):
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
    order: OrdenCampo
    direction: Direccion
    per_source: bool = True
