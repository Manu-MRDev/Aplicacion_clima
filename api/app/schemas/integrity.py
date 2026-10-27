"""Esquemas de verificación de integridad."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IntegritySourceReport(BaseModel):
    servidor: str
    status: str
    bloques_verificados: int = 0
    registros_verificados: int = 0
    registros_sin_bloque: int = 0
    errores: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    detalle: str | None = None


class IntegrityVerifyResponse(BaseModel):
    status: str
    servidor: str
    sources: dict[str, IntegritySourceReport]
