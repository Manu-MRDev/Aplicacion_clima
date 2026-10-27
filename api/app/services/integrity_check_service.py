"""Verificación de las cadenas de integridad por servidor."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.logging import get_logger
from app.repositories.postgres_repository import PostgresRecordsRepository
from app.repositories.sqlserver_repository import SqlServerRecordsRepository
from app.services.integrity_service import verify_chain

logger = get_logger(__name__)


class IntegrityCheckService:
    def __init__(
        self,
        settings: Settings,
        postgres: PostgresRecordsRepository,
        sqlserver: SqlServerRecordsRepository,
    ) -> None:
        self._settings = settings
        self._postgres = postgres
        self._sqlserver = sqlserver

    def verify(self, servidor: str) -> dict[str, Any]:
        targets = ["ubuntu", "windows"] if servidor == "ambos" else [servidor]
        sources: dict[str, Any] = {}

        def check(target: str) -> dict[str, Any]:
            repo = self._postgres if target == "ubuntu" else self._sqlserver
            if not self._settings.integrity_enabled:
                return {
                    "servidor": target,
                    "status": "disabled",
                    "errores": [],
                    "detalle": "INTEGRITY_ENABLED está desactivado",
                }
            try:
                if not repo.integrity_available():
                    return {
                        "servidor": target,
                        "status": "unavailable",
                        "errores": [],
                        "detalle": "tabla de integridad ausente o incompatible",
                    }
                blocks = repo.integrity_repository.fetch_blocks()
                records = repo.all_records()
                records_map = {record.id: record for record in records}
                covered_ids = {block.registro_id for block in blocks}
                # La tabla es compartida con la aplicación heredada: puede contener
                # registros históricos o escritos por otros procesos sin bloque.
                # Se informan como advertencia, no como fallo de integridad.
                sin_bloque = sorted(set(records_map) - covered_ids)
                advertencias: list[str] = []
                if sin_bloque:
                    muestra = ", ".join(str(record_id) for record_id in sin_bloque[:20])
                    sufijo = " ..." if len(sin_bloque) > 20 else ""
                    advertencias.append(
                        f"{len(sin_bloque)} registro(s) sin bloque de integridad "
                        f"(pueden pertenecer a otro proceso): {muestra}{sufijo}"
                    )
                errors = verify_chain(
                    blocks,
                    records=records_map,
                    cadena=repo.chain_id,
                    servidor=target,
                )
                if not blocks:
                    status = "empty"
                else:
                    status = "ok" if not errors else "invalid"
                return {
                    "servidor": target,
                    "status": status,
                    "bloques_verificados": len(blocks),
                    "registros_verificados": len(covered_ids),
                    "registros_sin_bloque": len(sin_bloque),
                    "errores": errors,
                    "advertencias": advertencias,
                }
            except DatabaseUnavailableError:
                return {
                    "servidor": target,
                    "status": "unavailable",
                    "errores": [],
                    "detalle": "servidor de datos no disponible",
                }
            except Exception:
                logger.exception("Fallo inesperado verificando integridad en %s", target)
                return {
                    "servidor": target,
                    "status": "error",
                    "errores": [],
                    "detalle": "error interno durante la verificación",
                }

        if len(targets) == 1:
            sources[targets[0]] = check(targets[0])
        else:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(check, target): target for target in targets}
                for future in as_completed(futures):
                    target = futures[future]
                    sources[target] = future.result()

        statuses = [source["status"] for source in sources.values()]
        if any(status == "invalid" for status in statuses):
            overall = "invalid"
        elif all(status == "ok" for status in statuses):
            overall = "ok"
        elif all(status in ("unavailable", "disabled") for status in statuses):
            overall = "unavailable" if "unavailable" in statuses else "disabled"
        elif all(status == "empty" for status in statuses):
            overall = "empty"
        else:
            overall = "partial"
        return {"status": overall, "servidor": servidor, "sources": sources}
