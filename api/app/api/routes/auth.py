"""Rutas de autenticación y TOTP."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    clear_session_cookie,
    enforce_csrf,
    enforce_origin,
    enforce_rate_limit,
    get_any_session,
    get_authenticated_session,
    get_container,
    get_pending_enroll_session,
    get_pending_totp_session,
    get_session_token,
    set_session_cookie,
    username_suffix,
)
from app.core.container import Container
from app.schemas.auth import (
    AuthenticatedResponse,
    EnrollmentResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RegisterRequest,
    RegistrationResponse,
    TOTPCodeRequest,
    UserResponse,
)
from app.schemas.common import ErrorResponse
from app.services.session_service import SessionContext

router = APIRouter(prefix="/auth", tags=["Autenticación"])

_AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Credenciales o sesión inválidas"},
    403: {"model": ErrorResponse, "description": "CSRF u origen no permitido"},
    429: {"model": ErrorResponse, "description": "Demasiadas solicitudes"},
}

_REGISTER_ERRORS = {
    403: {"model": ErrorResponse, "description": "Registro deshabilitado u origen no permitido"},
    409: {"model": ErrorResponse, "description": "Nombre de usuario no disponible"},
    429: {"model": ErrorResponse, "description": "Demasiadas solicitudes"},
}


def _user_payload(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        totp_enabled=user.totp_enabled,
        created_at=user.created_at,
    )


@router.post("/login", response_model=LoginResponse, responses=_AUTH_ERRORS)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    container: Container = Depends(get_container),
) -> LoginResponse:
    settings = container.settings
    enforce_origin(request, settings)
    enforce_rate_limit(
        request, bucket="login-ip", limit=settings.rate_limit_login_per_minute
    )
    enforce_rate_limit(
        request,
        bucket="login-user",
        limit=settings.rate_limit_login_per_minute,
        suffix=username_suffix(payload.username),
    )
    result = container.auth_service.login(payload.username, payload.password)
    set_session_cookie(response, settings, result.token, state="pending")
    message = (
        "Introduzca el código de su aplicación autenticadora"
        if result.next_step == "totp_required"
        else "Debe configurar el segundo factor antes de continuar"
    )
    return LoginResponse(
        status=result.next_step,
        csrf_token=result.context.csrf_token,
        expires_at=result.context.idle_expires_at,
        message=message,
    )


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_REGISTER_ERRORS,
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    container: Container = Depends(get_container),
) -> RegistrationResponse:
    settings = container.settings
    enforce_origin(request, settings)
    enforce_rate_limit(
        request, bucket="register-ip", limit=settings.rate_limit_register_per_minute
    )
    enforce_rate_limit(
        request,
        bucket="register-user",
        limit=settings.rate_limit_register_per_minute,
        suffix=username_suffix(payload.username),
    )
    result = container.auth_service.register(payload.username, payload.password)
    set_session_cookie(response, settings, result.token, state="pending")
    return RegistrationResponse(
        status="enrollment_required",
        csrf_token=result.context.csrf_token,
        expires_at=result.context.idle_expires_at,
        message="Cuenta creada. Configure el segundo factor antes de continuar.",
    )


@router.post("/totp/verify", response_model=AuthenticatedResponse, responses=_AUTH_ERRORS)
def verify_totp(
    payload: TOTPCodeRequest,
    request: Request,
    response: Response,
    context: SessionContext = Depends(get_pending_totp_session),
    container: Container = Depends(get_container),
) -> AuthenticatedResponse:
    settings = container.settings
    enforce_csrf(request, context, settings)
    enforce_rate_limit(request, bucket="totp-ip", limit=settings.rate_limit_totp_per_minute)
    enforce_rate_limit(
        request,
        bucket="totp-user",
        limit=settings.rate_limit_totp_per_minute,
        suffix=str(context.user_id),
    )
    result = container.auth_service.verify_totp(context, payload.code)
    set_session_cookie(response, settings, result.token, state="authenticated")
    return AuthenticatedResponse(
        user=_user_payload(result.user),
        csrf_token=result.context.csrf_token,
        session_expires_at=result.context.idle_expires_at,
    )


@router.post("/totp/enroll", response_model=EnrollmentResponse, responses=_AUTH_ERRORS)
def enroll_totp(
    request: Request,
    context: SessionContext = Depends(get_pending_enroll_session),
    container: Container = Depends(get_container),
) -> EnrollmentResponse:
    settings = container.settings
    enforce_csrf(request, context, settings)
    enforce_rate_limit(request, bucket="enroll-ip", limit=settings.rate_limit_enroll_per_minute)
    enforce_rate_limit(
        request,
        bucket="enroll-user",
        limit=settings.rate_limit_enroll_per_minute,
        suffix=str(context.user_id),
    )
    result = container.auth_service.begin_enrollment(context)
    return EnrollmentResponse(
        manual_key=result.manual_key,
        otpauth_uri=result.otpauth_uri,
        qr_data_uri=result.qr_data_uri,
        issuer=settings.app_name,
        account=context.username,
        expires_at=result.context.idle_expires_at,
        message="Escanee el código QR y confirme con un código de 6 dígitos. "
        "La clave se muestra una única vez.",
    )


@router.post("/totp/confirm", response_model=AuthenticatedResponse, responses=_AUTH_ERRORS)
def confirm_totp(
    payload: TOTPCodeRequest,
    request: Request,
    response: Response,
    context: SessionContext = Depends(get_pending_enroll_session),
    container: Container = Depends(get_container),
) -> AuthenticatedResponse:
    settings = container.settings
    enforce_csrf(request, context, settings)
    enforce_rate_limit(request, bucket="confirm-ip", limit=settings.rate_limit_totp_per_minute)
    enforce_rate_limit(
        request,
        bucket="confirm-user",
        limit=settings.rate_limit_totp_per_minute,
        suffix=str(context.user_id),
    )
    result = container.auth_service.confirm_enrollment(context, payload.code)
    set_session_cookie(response, settings, result.token, state="authenticated")
    return AuthenticatedResponse(
        user=_user_payload(result.user),
        csrf_token=result.context.csrf_token,
        session_expires_at=result.context.idle_expires_at,
    )


@router.post("/logout", response_model=LogoutResponse, responses=_AUTH_ERRORS)
def logout(
    request: Request,
    response: Response,
    token: str | None = Depends(get_session_token),
    container: Container = Depends(get_container),
) -> LogoutResponse:
    settings = container.settings
    context = container.session_service.get(token)
    if context is not None:
        enforce_csrf(request, context, settings)
        container.auth_service.logout(context)
    else:
        enforce_origin(request, settings)
    clear_session_cookie(response, settings)
    return LogoutResponse()


@router.get("/me", response_model=MeResponse, responses=_AUTH_ERRORS)
def me(
    context: SessionContext = Depends(get_authenticated_session),
    container: Container = Depends(get_container),
) -> MeResponse:
    user = container.auth_service.current_user(context)
    return MeResponse(
        user=_user_payload(user),
        csrf_token=context.csrf_token,
        session_expires_at=context.idle_expires_at,
    )
