"""Lógica de autenticación: contraseña, inscripción TOTP, verificación y sesión."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.core.config import Settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    RateLimitedError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.logging import get_logger
from app.core.security import consume_dummy_verification, hash_password, verify_password
from app.core.time import as_utc, utcnow
from app.models.domain import User
from app.repositories.postgres_repository import PostgresAuthRepository
from app.services.session_service import SessionContext, SessionService
from app.services.totp_service import TOTPService

logger = get_logger(__name__)


@dataclass
class LoginResult:
    token: str
    context: SessionContext
    next_step: Literal["totp_required", "enrollment_required"]


@dataclass
class EnrollmentResult:
    context: SessionContext
    manual_key: str
    otpauth_uri: str
    qr_data_uri: str


@dataclass
class AuthenticationResult:
    token: str
    context: SessionContext
    user: User


class AuthService:
    def __init__(
        self,
        settings: Settings,
        users: PostgresAuthRepository,
        sessions: SessionService,
        totp: TOTPService,
    ) -> None:
        self._settings = settings
        self._users = users
        self._sessions = sessions
        self._totp = totp

    # ------------------------------------------------------------------
    # Primer factor
    # ------------------------------------------------------------------
    def login(self, username: str, password: str) -> LoginResult:
        user = self._users.get_by_username(username)
        if user is None:
            consume_dummy_verification(password)
            logger.info("Intento de acceso con usuario inexistente")
            raise UnauthorizedError()

        if self._is_locked(user):
            consume_dummy_verification(password)
            logger.warning("Intento de acceso con cuenta bloqueada user_id=%s", user.id)
            raise UnauthorizedError()

        check = verify_password(user.password_hash, password)
        if not check.valid:
            attempts = self._users.record_failed_attempt(
                user.id,
                self._settings.login_max_attempts,
                self._settings.login_lockout_seconds,
            )
            logger.warning("Credenciales incorrectas user_id=%s intentos=%s", user.id, attempts)
            raise UnauthorizedError()

        new_hash = hash_password(password) if check.needs_rehash else None
        self._users.record_success(user.id, new_hash)

        if user.totp_enabled:
            if not user.totp_secret_encrypted:
                logger.error("Cuenta con TOTP habilitado sin secreto user_id=%s", user.id)
                raise ServiceUnavailableError(
                    "No fue posible completar el acceso. Contacte al administrador"
                )
            context = self._sessions.create_pending(user, "pending_totp")
            return LoginResult(context.token, context, "totp_required")

        context = self._sessions.create_pending(user, "pending_enroll")
        return LoginResult(context.token, context, "enrollment_required")

    # ------------------------------------------------------------------
    # Alta de usuarios
    # ------------------------------------------------------------------
    def register(self, username: str, password: str) -> LoginResult:
        """Crea una cuenta y deja una sesión pendiente de inscribir TOTP."""
        if not self._settings.registration_is_enabled:
            raise ForbiddenError("El registro de nuevos usuarios está deshabilitado")
        if self._users.get_by_username(username) is not None:
            raise ConflictError("El nombre de usuario ya está en uso")

        user = self._users.create_user(username, hash_password(password))
        logger.info("Usuario registrado user_id=%s", user.id)
        context = self._sessions.create_pending(user, "pending_enroll")
        return LoginResult(context.token, context, "enrollment_required")

    # ------------------------------------------------------------------
    # Segundo factor
    # ------------------------------------------------------------------
    def verify_totp(self, context: SessionContext, code: str) -> AuthenticationResult:
        if context.state != "pending_totp":
            raise UnauthorizedError("La sesión no permite esta operación")
        user = self._users.get_by_id(context.user_id)
        if user is None or not user.totp_enabled or not user.totp_secret_encrypted:
            self._sessions.revoke(context)
            raise UnauthorizedError()

        if self._is_locked(user):
            self._sessions.revoke(context)
            raise UnauthorizedError()

        try:
            secret = self._totp.decrypt_secret(user.totp_secret_encrypted, user.id)
        except Exception:
            logger.error("No se pudo descifrar el secreto TOTP user_id=%s", user.id)
            raise ServiceUnavailableError(
                "No fue posible completar la verificación. Contacte al administrador"
            ) from None

        valid, counter, reason = self._totp.verify(secret, code, user.totp_ultimo_counter)
        if not valid or counter is None:
            self._register_totp_failure(context, user, reason)
            raise UnauthorizedError("Código de verificación inválido")

        if not self._users.advance_totp_counter(user.id, counter):
            self._register_totp_failure(context, user, "reused")
            raise UnauthorizedError("Código de verificación inválido")

        self._users.record_success(user.id)
        refreshed = self._users.get_by_id(user.id) or user
        new_context = self._sessions.rotate_authenticated(context, refreshed)
        return AuthenticationResult(new_context.token, new_context, refreshed)

    # ------------------------------------------------------------------
    # Inscripción TOTP
    # ------------------------------------------------------------------
    def begin_enrollment(self, context: SessionContext) -> EnrollmentResult:
        if context.state != "pending_enroll":
            raise UnauthorizedError("La sesión no permite esta operación")
        self._require_recent_password(context)

        current = self._users.get_by_id(context.user_id)
        if current is None:
            self._sessions.revoke(context)
            raise UnauthorizedError()
        if current.totp_enabled:
            raise ConflictError("La cuenta ya tiene un segundo factor configurado")

        now = utcnow()
        enroll = context.enroll or {}
        generation_times = self._recent_generations(enroll, now)
        if len(generation_times) >= self._settings.totp_enroll_max_generations_per_hour:
            raise RateLimitedError(retry_after=3600)

        secret = self._totp.new_secret()
        encrypted = self._totp.encrypt_secret(secret, current.id)
        uri = self._totp.provisioning_uri(secret, current.username)
        qr = self._totp.qr_data_uri(uri)
        generation_times.append(now)
        context.enroll = {
            "secret_encrypted": encrypted,
            "created_at": now.isoformat(),
            "attempts": 0,
            "last_counter": None,
            "generation_times": [moment.isoformat() for moment in generation_times],
        }
        self._sessions.update(context)
        return EnrollmentResult(context, secret, uri, qr)

    def confirm_enrollment(self, context: SessionContext, code: str) -> AuthenticationResult:
        if context.state != "pending_enroll":
            raise UnauthorizedError("La sesión no permite esta operación")
        self._require_recent_password(context)
        enroll = context.enroll or {}
        encrypted = enroll.get("secret_encrypted")
        if not isinstance(encrypted, str):
            raise ConflictError("No hay una inscripción TOTP en curso")

        attempts = int(enroll.get("attempts") or 0)
        if attempts >= self._settings.totp_max_attempts:
            self._sessions.revoke(context)
            raise UnauthorizedError("Demasiados intentos de verificación")

        user = self._users.get_by_id(context.user_id)
        if user is None:
            self._sessions.revoke(context)
            raise UnauthorizedError()
        if user.totp_enabled:
            raise ConflictError("La cuenta ya tiene un segundo factor configurado")

        try:
            secret = self._totp.decrypt_secret(encrypted, user.id)
        except Exception:
            logger.error("No se pudo descifrar el secreto TOTP en inscripción user_id=%s", user.id)
            raise ServiceUnavailableError(
                "No fue posible completar la inscripción. Contacte al administrador"
            ) from None

        last_counter = enroll.get("last_counter")
        valid, counter, reason = self._totp.verify(
            secret,
            code,
            int(last_counter) if isinstance(last_counter, int) else None,
        )
        if not valid or counter is None:
            enroll["attempts"] = attempts + 1
            context.enroll = enroll
            if enroll["attempts"] >= self._settings.totp_max_attempts:
                self._sessions.revoke(context)
            else:
                self._sessions.update(context)
            logger.warning("Confirmación TOTP fallida user_id=%s motivo=%s", user.id, reason)
            raise UnauthorizedError("Código de verificación inválido")

        if not self._users.confirm_totp_enrollment(user.id, encrypted, counter):
            raise ConflictError("El código ya fue utilizado. Inicie sesión nuevamente")

        self._users.record_success(user.id)
        refreshed = self._users.get_by_id(user.id) or user
        new_context = self._sessions.rotate_authenticated(context, refreshed)
        return AuthenticationResult(new_context.token, new_context, refreshed)

    # ------------------------------------------------------------------
    # Sesión
    # ------------------------------------------------------------------
    def logout(self, context: SessionContext) -> None:
        self._sessions.revoke(context)

    def current_user(self, context: SessionContext) -> User:
        user = self._users.get_by_id(context.user_id)
        if user is None:
            self._sessions.revoke(context)
            raise UnauthorizedError()
        return user

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------
    @staticmethod
    def _is_locked(user: User) -> bool:
        locked_until = as_utc(user.bloqueado_hasta)
        return locked_until is not None and locked_until > utcnow()

    def _register_totp_failure(
        self, context: SessionContext, user: User, reason: str
    ) -> None:
        attempts = self._users.record_failed_attempt(
            user.id,
            self._settings.login_max_attempts,
            self._settings.login_lockout_seconds,
        )
        logger.warning("TOTP inválido user_id=%s motivo=%s intentos=%s", user.id, reason, attempts)
        if attempts >= self._settings.login_max_attempts:
            self._sessions.revoke(context)
        else:
            self._sessions.update(context)

    def _require_recent_password(self, context: SessionContext) -> None:
        verified_at = as_utc(context.password_verified_at)
        if verified_at is None:
            raise UnauthorizedError("Se requiere verificar la contraseña nuevamente")
        if verified_at + timedelta(seconds=self._settings.pending_session_ttl_seconds) < utcnow():
            self._sessions.revoke(context)
            raise UnauthorizedError("La verificación de contraseña expiró. Inicie sesión nuevamente")

    @staticmethod
    def _recent_generations(enroll: dict, now: datetime) -> list[datetime]:
        moments: list[datetime] = []
        for raw in enroll.get("generation_times") or []:
            try:
                parsed = as_utc(datetime.fromisoformat(str(raw)))
            except ValueError:
                continue
            if parsed is not None and parsed >= now - timedelta(hours=1):
                moments.append(parsed)
        return moments
