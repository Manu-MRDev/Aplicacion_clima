"""Excepciones de dominio y manejo centralizado de errores HTTP."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"
    public_message: str = "Solicitud inválida"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message
        self.details = details
        self.headers = headers


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    public_message = "Solicitud inválida"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    public_message = "Credenciales inválidas o sesión no válida"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    public_message = "No tiene permisos para realizar esta operación"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    public_message = "Recurso no encontrado"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    public_message = "La operación entra en conflicto con el estado actual"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    public_message = "Demasiadas solicitudes. Intente más tarde"

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(headers={"Retry-After": str(max(1, int(retry_after)))})
        self.retry_after = retry_after


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"
    public_message = "El servicio externo no respondió correctamente"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    public_message = "Servicio no disponible temporalmente"


class DatabaseUnavailableError(ServiceUnavailableError):
    code = "database_unavailable"
    public_message = "El servicio de datos no está disponible temporalmente"


class SessionStoreUnavailableError(ServiceUnavailableError):
    code = "session_store_unavailable"
    public_message = "El almacenamiento de sesiones no está disponible temporalmente"


class IntegrityUnavailableError(ServiceUnavailableError):
    code = "integrity_unavailable"
    public_message = "La verificación de integridad no está disponible"


class CryptoError(Exception):
    """Fallo interno de criptografía (nunca se expone el detalle al cliente)."""


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("error de aplicación", extra={"code": exc.code})
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # No se devuelven los valores de entrada: pueden contener contraseñas o códigos TOTP.
        details = {
            "errors": [
                {
                    "loc": [str(part) for part in error.get("loc", ())],
                    "type": error.get("type", "value_error"),
                    "msg": str(error.get("msg", "Valor inválido")),
                }
                for error in exc.errors()
            ]
        }
        return _error_response(
            request,
            status_code=422,
            code="validation_error",
            message="Los datos enviados no son válidos",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        message = {
            401: "No autenticado",
            403: "No autorizado",
            404: "Recurso no encontrado",
            405: "Método no permitido",
        }.get(exc.status_code, "Error HTTP")
        return _error_response(request, status_code=exc.status_code, code=code, message=message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("error no controlado en %s %s", request.method, request.url.path)
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="Error interno del servidor",
        )
