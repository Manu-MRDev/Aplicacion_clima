"""Dependencias HTTP: contenedor, sesión, CSRF, cookies y límites."""

from __future__ import annotations

import math
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response, Security
from fastapi.security import APIKeyCookie

from app.core.config import Settings
from app.core.container import Container
from app.core.exceptions import ForbiddenError, ServiceUnavailableError
from app.core.rate_limit import limiter
from app.core.security import constant_time_equals, stable_token_hash
from app.services.session_service import SessionContext

# El nombre real se lee de la configuración; este esquema existe para OpenAPI.
cookie_scheme = APIKeyCookie(name="clima_session", auto_error=False)


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise ServiceUnavailableError()
    return container


def get_settings(container: Container = Depends(get_container)) -> Settings:
    return container.settings


def client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    suffix: str = "",
    window_seconds: float = 60.0,
) -> None:
    key = f"{bucket}:{client_ip(request)}:{suffix}"
    retry_after = limiter.check(key, limit=limit, window_seconds=window_seconds)
    if retry_after is not None:
        from app.core.exceptions import RateLimitedError

        raise RateLimitedError(retry_after=max(1, math.ceil(retry_after)))


def get_session_token(
    request: Request,
    container: Container = Depends(get_container),
    _: str | None = Security(cookie_scheme),
) -> str | None:
    # Se lee el nombre configurado (puede ser __Host-* en producción).
    return request.cookies.get(container.settings.cookie_name)


def get_any_session(
    token: str | None = Depends(get_session_token),
    container: Container = Depends(get_container),
) -> SessionContext:
    return container.session_service.require(token)


def get_authenticated_session(
    token: str | None = Depends(get_session_token),
    container: Container = Depends(get_container),
) -> SessionContext:
    return container.session_service.require(token, state="authenticated")


def get_pending_totp_session(
    token: str | None = Depends(get_session_token),
    container: Container = Depends(get_container),
) -> SessionContext:
    return container.session_service.require(token, state="pending_totp")


def get_pending_enroll_session(
    token: str | None = Depends(get_session_token),
    container: Container = Depends(get_container),
) -> SessionContext:
    return container.session_service.require(token, state="pending_enroll")


def normalize_origin(value: str) -> str:
    """Normaliza un origen para compararlo sin depender de mayúsculas ni del puerto por defecto."""
    raw = value.strip().rstrip("/")
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return raw.lower()
    if not scheme or not host:
        return raw.lower()
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def enforce_origin(request: Request, settings: Settings) -> None:
    """Comprueba Origin/Sec-Fetch-Site cuando el navegador los envía.

    Se admite el mismo origen de la API además de los orígenes CORS configurados,
    de modo que un frontend servido por el mismo host funcione sin listarse a sí mismo.
    """
    origin = request.headers.get("origin")
    if origin:
        allowed = {normalize_origin(item) for item in settings.cors_origins}
        allowed.add(normalize_origin(f"{request.url.scheme}://{request.url.netloc}"))
        if normalize_origin(origin) not in allowed:
            raise ForbiddenError("Origen no autorizado")
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "same-site", "none"):
        raise ForbiddenError("Solicitud entre sitios rechazada")


def enforce_csrf(request: Request, context: SessionContext, settings: Settings) -> None:
    enforce_origin(request, settings)
    header = request.headers.get("x-csrf-token", "")
    if not header or not constant_time_equals(header, context.csrf_token):
        raise ForbiddenError("Token CSRF inválido o ausente")


def set_session_cookie(
    response: Response,
    settings: Settings,
    token: str,
    *,
    state: Literal["pending", "authenticated"],
) -> None:
    max_age = (
        settings.session_ttl_seconds
        if state == "authenticated"
        else settings.pending_session_ttl_seconds
    )
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.session_samesite,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.session_samesite,
        path="/",
    )


def username_suffix(username: str) -> str:
    """Sufijo estable para limitar por cuenta sin guardar el nombre en claro."""
    return stable_token_hash(username.lower())[:16]
