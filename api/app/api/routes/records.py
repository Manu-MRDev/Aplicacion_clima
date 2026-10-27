"""Rutas de registros climáticos."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.api.deps import enforce_csrf, enforce_rate_limit, get_authenticated_session, get_container
from app.core.container import Container
from app.core.exceptions import BadRequestError
from app.core.time import as_utc, utcnow
from app.schemas.common import Direccion, ErrorResponse, OrdenCampo, Pagination, Servidor, ServidorQuery
from app.schemas.records import (
    CreateRecordResponse,
    IntegrityInfo,
    RecordCreateRequest,
    RecordOut,
    RecordsListResponse,
    SourceStatus,
)
from app.services.records_service import RecordInput
from app.services.session_service import SessionContext

router = APIRouter(prefix="/records", tags=["Registros climáticos"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "No autenticado"},
    403: {"model": ErrorResponse, "description": "CSRF u origen no permitido"},
    422: {"model": ErrorResponse, "description": "Datos inválidos"},
    429: {"model": ErrorResponse, "description": "Demasiadas solicitudes"},
    503: {"model": ErrorResponse, "description": "Servidor de datos no disponible"},
}


@router.post(
    "",
    response_model=CreateRecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Crear un registro climático",
)
def create_record(
    payload: RecordCreateRequest,
    request: Request,
    context: SessionContext = Depends(get_authenticated_session),
    container: Container = Depends(get_container),
) -> CreateRecordResponse:
    settings = container.settings
    enforce_csrf(request, context, settings)
    enforce_rate_limit(request, bucket="records-write", limit=settings.rate_limit_records_per_minute)
    data = RecordInput(
        nombre=payload.nombre,
        paterno=payload.paterno,
        materno=payload.materno,
        estado=payload.estado,
        municipio=payload.municipio,
        latitud=payload.latitud,
        longitud=payload.longitud,
        temperatura=payload.temperatura,
        humedad=payload.humedad,
        viento=payload.viento,
        fecha_hora=payload.fecha_hora or utcnow(),
    )
    result = container.records_service.create(context, data, payload.servidor.value)
    return CreateRecordResponse(
        registro=RecordOut.from_domain(result.record),
        integridad=IntegrityInfo.model_validate(result.integrity),
    )


@router.get(
    "",
    response_model=RecordsListResponse,
    responses=_ERRORS,
    summary="Listar registros de uno o ambos servidores",
)
def list_records(
    request: Request,
    servidor: ServidorQuery = Query(default=ServidorQuery.ubuntu),
    usuario: str | None = Query(default=None, min_length=1, max_length=64),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    orden: OrdenCampo = Query(default=OrdenCampo.fecha_hora),
    direccion: Direccion = Query(default=Direccion.desc),
    context: SessionContext = Depends(get_authenticated_session),
    container: Container = Depends(get_container),
) -> RecordsListResponse:
    settings = container.settings
    enforce_rate_limit(request, bucket="records-read", limit=settings.rate_limit_records_per_minute)
    desde_utc = as_utc(desde)
    hasta_utc = as_utc(hasta)
    if desde_utc and hasta_utc and desde_utc > hasta_utc:
        raise BadRequestError("El rango de fechas es inválido")
    if usuario is not None:
        usuario = usuario.strip()
        if not usuario:
            usuario = None

    result = container.records_service.list_records(
        context,
        servidor=servidor.value,
        usuario=usuario,
        desde=desde_utc,
        hasta=hasta_utc,
        limit=limit,
        offset=offset,
        order_field=orden.value,
        order_desc=direccion == Direccion.desc,
    )
    return RecordsListResponse(
        servidor=servidor.value,
        registros=[RecordOut.from_domain(record) for record in result.records],
        paginacion=Pagination(
            limit=limit,
            offset=offset,
            order=orden,
            direction=direccion,
            per_source=servidor == ServidorQuery.ambos,
        ),
        fuentes={
            target: SourceStatus.model_validate(meta) for target, meta in result.sources.items()
        },
        parcial=result.partial,
    )


@router.get(
    "/{id}",
    response_model=RecordOut,
    responses=_ERRORS,
    summary="Obtener un registro por identificador y servidor",
)
def get_record(
    request: Request,
    id: int = Path(ge=1),
    servidor: Servidor = Query(default=Servidor.ubuntu),
    context: SessionContext = Depends(get_authenticated_session),
    container: Container = Depends(get_container),
) -> RecordOut:
    settings = container.settings
    enforce_rate_limit(request, bucket="records-read", limit=settings.rate_limit_records_per_minute)
    record = container.records_service.get_record(context, servidor.value, id)
    return RecordOut.from_domain(record)
