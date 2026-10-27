"""Esquemas de registros climáticos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.domain import StoredRecord
from app.schemas.common import Pagination, Servidor


class RecordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servidor: Servidor
    nombre: str = Field(min_length=1, max_length=100)
    paterno: str | None = Field(default=None, max_length=100)
    materno: str | None = Field(default=None, max_length=100)
    estado: str = Field(min_length=1, max_length=120)
    municipio: str = Field(min_length=1, max_length=120)
    latitud: Decimal = Field(ge=-90, le=90, max_digits=10, decimal_places=7)
    longitud: Decimal = Field(ge=-180, le=180, max_digits=10, decimal_places=7)
    temperatura: Decimal = Field(ge=-90, le=60, max_digits=6, decimal_places=2)
    humedad: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    viento: Decimal = Field(ge=0, le=500, max_digits=6, decimal_places=2)
    fecha_hora: datetime | None = None

    @field_validator("nombre", "estado", "municipio")
    @classmethod
    def _clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("el campo no puede estar vacío")
        if any(ord(char) < 32 for char in cleaned):
            raise ValueError("el campo contiene caracteres de control")
        return cleaned

    @field_validator("paterno", "materno")
    @classmethod
    def _clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if any(ord(char) < 32 for char in cleaned):
            raise ValueError("el campo contiene caracteres de control")
        return cleaned

    @model_validator(mode="after")
    def _windows_required_fields(self) -> "RecordCreateRequest":
        # dbo.Georreferencia tiene Paterno NOT NULL; se valida antes de tocar la BD.
        if self.servidor == Servidor.windows and not self.paterno:
            raise ValueError("paterno es obligatorio para el servidor windows")
        return self

    @field_validator("fecha_hora")
    @classmethod
    def _validate_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone(UTC)
        if value.year < 1900:
            raise ValueError("fecha demasiado antigua")
        if value > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("la fecha de observación no puede estar en el futuro")
        return value


class RecordOut(BaseModel):
    id: int
    servidor: str
    usuario: str
    nombre: str
    paterno: str | None = None
    materno: str | None = None
    estado: str
    municipio: str
    latitud: float | None = None
    longitud: float | None = None
    temperatura: float | None = None
    humedad: float | None = None
    viento: float | None = None
    fecha_hora: datetime | None = None

    @classmethod
    def from_domain(cls, record: StoredRecord) -> "RecordOut":
        def number(value: Decimal | None) -> float | None:
            return float(value) if value is not None else None

        return cls(
            id=record.id,
            servidor=record.servidor,
            usuario=record.usuario,
            nombre=record.nombre,
            paterno=record.paterno,
            materno=record.materno,
            estado=record.estado,
            municipio=record.municipio,
            latitud=number(record.latitud),
            longitud=number(record.longitud),
            temperatura=number(record.temperatura),
            humedad=number(record.humedad),
            viento=number(record.viento),
            fecha_hora=record.fecha_hora,
        )


class IntegrityInfo(BaseModel):
    status: Literal["created", "disabled", "unavailable"]
    cadena: str
    indice: int | None = None
    hash_actual: str | None = None
    detalle: str | None = None


class CreateRecordResponse(BaseModel):
    registro: RecordOut
    integridad: IntegrityInfo


class SourceStatus(BaseModel):
    status: str
    count: int
    has_more: bool
    error: str | None = None


class RecordsListResponse(BaseModel):
    servidor: str
    registros: list[RecordOut]
    paginacion: Pagination
    fuentes: dict[str, SourceStatus]
    parcial: bool
