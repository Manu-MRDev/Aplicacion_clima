"""Ruta de verificación de integridad."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import enforce_rate_limit, get_authenticated_session, get_container
from app.core.container import Container
from app.schemas.common import ErrorResponse, ServidorQuery
from app.schemas.integrity import IntegritySourceReport, IntegrityVerifyResponse
from app.services.session_service import SessionContext

router = APIRouter(prefix="/integrity", tags=["Integridad"])


@router.get(
    "/verify",
    response_model=IntegrityVerifyResponse,
    responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    summary="Verificar la cadena de hashes de uno o ambos servidores",
)
def verify_integrity(
    request: Request,
    servidor: ServidorQuery = Query(default=ServidorQuery.ambos),
    context: SessionContext = Depends(get_authenticated_session),
    container: Container = Depends(get_container),
) -> IntegrityVerifyResponse:
    enforce_rate_limit(
        request,
        bucket="integrity",
        limit=container.settings.rate_limit_records_per_minute,
    )
    result = container.integrity_check_service.verify(servidor.value)
    return IntegrityVerifyResponse(
        status=result["status"],
        servidor=result["servidor"],
        sources={
            name: IntegritySourceReport.model_validate(report)
            for name, report in result["sources"].items()
        },
    )
