"""Orquestación de registros climáticos en ambos servidores independientes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError, NotFoundError
from app.core.logging import get_logger
from app.core.time import as_utc
from app.models.domain import IntegrityBlock, StoredRecord, WeatherRecord
from app.repositories.postgres_repository import (
    PostgresAuthRepository,
    PostgresRecordsRepository,
)
from app.repositories.sqlserver_repository import SqlServerRecordsRepository

logger = get_logger(__name__)

Servidor = Literal["ubuntu", "windows", "ambos"]
NO_MATCH = object()


@dataclass(frozen=True)
class RecordInput:
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


@dataclass
class CreateResult:
    record: StoredRecord
    integrity: dict[str, Any]


@dataclass
class ListSourceResult:
    status: str
    records: list[StoredRecord]
    has_more: bool = False
    error: str | None = None

    def as_meta(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status,
            "count": len(self.records),
            "has_more": self.has_more,
        }
        if self.error:
            data["error"] = self.error
        return data


@dataclass
class ListResult:
    records: list[StoredRecord]
    sources: dict[str, dict[str, Any]]
    partial: bool


class RecordsService:
    def __init__(
        self,
        settings: Settings,
        postgres: PostgresRecordsRepository,
        sqlserver: SqlServerRecordsRepository,
        users: PostgresAuthRepository,
    ) -> None:
        self._settings = settings
        self._postgres = postgres
        self._sqlserver = sqlserver
        self._users = users

    def _repo(self, servidor: str):
        if servidor == "ubuntu":
            return self._postgres
        if servidor == "windows":
            return self._sqlserver
        raise ValueError("servidor no permitido")

    def create(self, context, data: RecordInput, servidor: str) -> CreateResult:
        repo = self._repo(servidor)
        usuario_value = repo.usuario_value(context.user_id, context.username)
        record = WeatherRecord(
            usuario=str(usuario_value),
            nombre=data.nombre,
            paterno=data.paterno,
            materno=data.materno,
            estado=data.estado,
            municipio=data.municipio,
            latitud=data.latitud,
            longitud=data.longitud,
            temperatura=data.temperatura,
            humedad=data.humedad,
            viento=data.viento,
            fecha_hora=data.fecha_hora,
        )

        integrity_enabled = self._settings.integrity_enabled
        available = integrity_enabled and repo.integrity_available()
        status = "disabled" if not integrity_enabled else ("created" if available else "unavailable")
        detail = None
        if integrity_enabled and not available:
            detail = repo.integrity_issue() or "tabla de integridad no disponible"
            logger.warning(
                "Registro sin bloque de integridad servidor=%s detalle=%s", servidor, detail
            )

        stored, block = repo.insert(record, usuario_value=usuario_value, with_integrity=available)
        if status == "created" and block is None:
            status = "unavailable"
            detail = "no se confirmó la creación del bloque"
            logger.error("Inserción sin bloque en servidor=%s", servidor)

        return CreateResult(stored, self._integrity_payload(status, repo, block, detail))

    @staticmethod
    def _integrity_payload(
        status: str, repo, block: IntegrityBlock | None, detail: str | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": status,
            "cadena": repo.chain_id,
        }
        if block is not None:
            payload.update(
                {
                    "indice": block.indice,
                    "hash_actual": block.hash_actual,
                }
            )
        if detail:
            payload["detalle"] = detail
        return payload

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def list_records(
        self,
        context,
        *,
        servidor: str,
        usuario: str | None,
        desde: datetime | None,
        hasta: datetime | None,
        limit: int,
        offset: int,
        order_field: str,
        order_desc: bool,
    ) -> ListResult:
        targets = ["ubuntu", "windows"] if servidor == "ambos" else [servidor]
        results: dict[str, ListSourceResult] = {}

        def load(target: str) -> ListSourceResult:
            repo = self._repo(target)
            filtro = self._resolve_filter(target, usuario)
            if filtro is NO_MATCH:
                return ListSourceResult("ok", [], False)
            records, has_more = repo.list_records(
                limit=limit,
                offset=offset,
                order_desc=order_desc,
                order_field=order_field,
                usuario_filter=filtro,
                desde=desde,
                hasta=hasta,
            )
            return ListSourceResult("ok", records, has_more)

        if len(targets) == 1:
            target = targets[0]
            try:
                results[target] = load(target)
            except DatabaseUnavailableError:
                raise
        else:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(load, target): target for target in targets}
                for future in as_completed(futures):
                    target = futures[future]
                    try:
                        results[target] = future.result()
                    except DatabaseUnavailableError:
                        logger.warning("Consulta combinada: servidor %s no disponible", target)
                        results[target] = ListSourceResult(
                            "unavailable", [], False, "database_unavailable"
                        )

            if all(result.status != "ok" for result in results.values()):
                raise DatabaseUnavailableError()

        combined: list[StoredRecord] = []
        for result in results.values():
            combined.extend(result.records)
        combined.sort(key=lambda record: self._sort_key(record, order_field), reverse=order_desc)
        partial = any(result.status != "ok" for result in results.values())
        return ListResult(
            records=combined,
            sources={target: result.as_meta() for target, result in results.items()},
            partial=partial,
        )

    def get_record(self, context, servidor: str, record_id: int) -> StoredRecord:
        repo = self._repo(servidor)
        record = repo.get_record(record_id)
        if record is None:
            raise NotFoundError("Registro no encontrado")
        return record

    @staticmethod
    def _sort_key(record: StoredRecord, order_field: str):
        if order_field == "id":
            return record.id
        fecha = as_utc(record.fecha_hora) or datetime.min.replace(tzinfo=UTC)
        return (fecha, record.id)

    def _resolve_filter(self, servidor: str, usuario: str | None) -> Any:
        if not usuario:
            return None
        repo = self._repo(servidor)
        if not repo.usuario_is_numeric:
            return usuario
        user = self._users.get_by_username(usuario)
        return user.id if user is not None else NO_MATCH
