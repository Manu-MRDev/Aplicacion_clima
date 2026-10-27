"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth, health, integrity, locations, records, weather
from app.core.config import Settings, get_settings
from app.core.container import Container
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.time import utcnow

MAX_BODY_BYTES = 1_048_576


def create_app(
    settings: Settings | None = None, container: Container | None = None
) -> FastAPI:
    settings = settings or get_settings()
    if settings.odbc_config_dir:
        # unixODBC lee este directorio al resolver el driver; debe fijarse antes
        # de la primera llamada a pyodbc.drivers()/connect().
        os.environ.setdefault("ODBCSYSINI", settings.odbc_config_dir)
    configure_logging(settings.log_level, settings.log_json)
    container = container or Container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.container.startup()
        yield
        await app.state.container.shutdown()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "API del backend climático. Incluye alta de usuarios, autenticación con "
            "contraseña y TOTP, consultas a Open-Meteo, geocodificación inversa, "
            "registros en PostgreSQL "
            "y SQL Server, y verificación de integridad mediante cadenas de hashes."
        ),
        docs_url="/docs" if settings.docs_are_enabled else None,
        redoc_url="/redoc" if settings.docs_are_enabled else None,
        openapi_url="/openapi.json" if settings.docs_are_enabled else None,
        lifespan=lifespan,
    )
    app.state.container = container

    install_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    if settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
            www_redirect=False,
        )

    @app.middleware("http")
    async def request_limits(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > MAX_BODY_BYTES
            except ValueError:
                too_large = False
            if too_large:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "El cuerpo de la solicitud es demasiado grande",
                            "request_id": request_id,
                        }
                    },
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(self)"
        if request.url.path.startswith(settings.api_prefix) or request.url.path.startswith(
            "/health"
        ):
            response.headers["Cache-Control"] = "no-store"
        if settings.is_production and settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    prefix = settings.api_prefix.rstrip("/")
    app.include_router(auth.router, prefix=prefix)
    app.include_router(weather.router, prefix=prefix)
    app.include_router(locations.router, prefix=prefix)
    app.include_router(records.router, prefix=prefix)
    app.include_router(integrity.router, prefix=prefix)
    app.include_router(health.router)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "service": settings.app_name,
            "docs": "/docs" if settings.docs_are_enabled else None,
            "time": utcnow().isoformat(),
        }

    return app

