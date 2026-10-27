"""Modelos de dominio internos (independientes de Pydantic y de los drivers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    totp_secret_encrypted: str | None
    totp_enabled: bool
    created_at: datetime | None
    intentos_fallidos: int = 0
    bloqueado_hasta: datetime | None = None
    totp_ultimo_counter: int | None = None


@dataclass(frozen=True)
class WeatherRecord:
    nombre: str
    paterno: str | None
    materno: str | None
    estado: str
    municipio: str
    latitud: Decimal
    longitud: Decimal
    temperatura: Decimal
    humedad: Decimal
    viento: Decimal
    fecha_hora: datetime
    usuario: str = ""


@dataclass(frozen=True)
class StoredRecord:
    id: int
    usuario: str
    nombre: str
    paterno: str | None
    materno: str | None
    estado: str
    municipio: str
    latitud: Decimal | None
    longitud: Decimal | None
    temperatura: Decimal | None
    humedad: Decimal | None
    viento: Decimal | None
    fecha_hora: datetime | None
    servidor: str


@dataclass(frozen=True)
class IntegrityBlock:
    cadena: str
    indice: int
    registro_id: int
    datos_canonicos: str
    hash_anterior: str | None
    hash_actual: str
    creado_en: datetime | None = None


@dataclass
class IntegrityReport:
    servidor: str
    status: str  # ok | invalid | unavailable
    checked_blocks: int = 0
    checked_records: int = 0
    errors: list[str] = field(default_factory=list)
    detail: str | None = None

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "servidor": self.servidor,
            "status": self.status,
            "bloques_verificados": self.checked_blocks,
            "registros_verificados": self.checked_records,
            "errores": self.errors,
        }
        if self.detail:
            data["detalle"] = self.detail
        return data
