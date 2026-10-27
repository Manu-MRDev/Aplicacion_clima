"""Sesiones del lado del servidor con cookie opaca y estado versionado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import csrf_token_for, new_session_token, session_sid
from app.core.time import as_utc, utcnow
from app.models.domain import User
from app.repositories.postgres_repository import PostgresSessionStore
from app.repositories.postgres_repository import PostgresSchemaProvider

SessionState = Literal["pending_totp", "pending_enroll", "authenticated"]
SESSION_VERSION = 1


@dataclass
class SessionContext:
    token: str
    sid: str | UUID
    state: SessionState
    user_id: int
    username: str
    created_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    csrf_token: str
    password_verified_at: datetime | None = None
    authenticated_at: datetime | None = None
    enroll: dict[str, Any] | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.state == "authenticated"

    def to_payload(self) -> dict[str, Any]:
        return {
            "v": SESSION_VERSION,
            "state": self.state,
            "user_id": self.user_id,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "password_verified_at": self.password_verified_at.isoformat()
            if self.password_verified_at
            else None,
            "authenticated_at": self.authenticated_at.isoformat()
            if self.authenticated_at
            else None,
            "idle_expires_at": self.idle_expires_at.isoformat(),
            "absolute_expires_at": self.absolute_expires_at.isoformat(),
            "enroll": self.enroll,
        }


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return as_utc(parsed)


class SessionService:
    def __init__(self, settings: Settings, store: PostgresSessionStore, provider: PostgresSchemaProvider):
        self._settings = settings
        self._store = store
        self._provider = provider

    # ------------------------------------------------------------------
    # Creación y lectura
    # ------------------------------------------------------------------
    def _new_session(self, user: User, state: SessionState) -> SessionContext:
        token = new_session_token()
        sid_is_uuid = self._provider.get().sessions.sid_is_uuid
        sid = session_sid(token, as_uuid=sid_is_uuid)
        now = utcnow()
        ttl = (
            timedelta(seconds=self._settings.session_ttl_seconds)
            if state == "authenticated"
            else timedelta(seconds=self._settings.pending_session_ttl_seconds)
        )
        absolute_ttl = (
            timedelta(seconds=self._settings.session_absolute_ttl_seconds)
            if state == "authenticated"
            else ttl
        )
        return SessionContext(
            token=token,
            sid=sid,
            state=state,
            user_id=user.id,
            username=user.username,
            created_at=now,
            idle_expires_at=now + ttl,
            absolute_expires_at=now + absolute_ttl,
            csrf_token=csrf_token_for(self._settings.session_key, str(sid)),
            password_verified_at=now if state != "authenticated" else now,
            authenticated_at=now if state == "authenticated" else None,
        )

    def create_pending(self, user: User, state: Literal["pending_totp", "pending_enroll"]) -> SessionContext:
        ctx = self._new_session(user, state)
        self._store.create(ctx.sid, ctx.to_payload(), ctx.idle_expires_at)
        return ctx

    def create_authenticated(self, user: User) -> SessionContext:
        ctx = self._new_session(user, "authenticated")
        self._store.create(ctx.sid, ctx.to_payload(), ctx.idle_expires_at)
        return ctx

    def get(self, token: str | None, *, touch: bool = True) -> SessionContext | None:
        if not token or not token.startswith("s1_"):
            return None
        sid_is_uuid = self._provider.get().sessions.sid_is_uuid
        sid = session_sid(token, as_uuid=sid_is_uuid)
        payload = self._store.get(sid)
        if payload is None:
            return None
        ctx = self._from_payload(token, sid, payload)
        if ctx is None:
            # Puede ser una fila de otra aplicación que comparte la tabla `session`.
            # No se elimina: no es nuestra y expirará por su propia política.
            return None
        now = utcnow()
        if now >= ctx.absolute_expires_at or now >= ctx.idle_expires_at:
            self._store.delete(sid)
            return None
        if (
            touch
            and ctx.is_authenticated
            and ctx.idle_expires_at - now
            < timedelta(seconds=self._settings.session_ttl_seconds) / 2
        ):
            new_idle = min(
                now + timedelta(seconds=self._settings.session_ttl_seconds),
                ctx.absolute_expires_at,
            )
            ctx.idle_expires_at = new_idle
            self._store.update(sid, ctx.to_payload(), new_idle)
        return ctx

    def require(self, token: str | None, *, state: SessionState | None = None) -> SessionContext:
        ctx = self.get(token)
        if ctx is None:
            raise UnauthorizedError("Sesión no válida o expirada")
        if state is not None and ctx.state != state:
            raise UnauthorizedError("La sesión no permite esta operación")
        return ctx

    def rotate_authenticated(self, ctx: SessionContext, user: User) -> SessionContext:
        new_ctx = self._new_session(user, "authenticated")
        self._store.rotate(ctx.sid, new_ctx.sid, new_ctx.to_payload(), new_ctx.idle_expires_at)
        return new_ctx

    def revoke(self, ctx: SessionContext) -> None:
        self._store.delete(ctx.sid)

    def update(self, ctx: SessionContext) -> None:
        self._store.update(ctx.sid, ctx.to_payload(), ctx.idle_expires_at)

    def _from_payload(
        self, token: str, sid: str | UUID, payload: dict[str, Any]
    ) -> SessionContext | None:
        if payload.get("v") != SESSION_VERSION:
            return None
        state = payload.get("state")
        if state not in ("pending_totp", "pending_enroll", "authenticated"):
            return None
        try:
            user_id = int(payload["user_id"])
            username = str(payload["username"])
        except (KeyError, TypeError, ValueError):
            return None
        created_at = _parse_dt(payload.get("created_at"))
        idle = _parse_dt(payload.get("idle_expires_at"))
        absolute = _parse_dt(payload.get("absolute_expires_at"))
        if not created_at or not idle or not absolute:
            return None
        enroll = payload.get("enroll")
        return SessionContext(
            token=token,
            sid=sid,
            state=state,
            user_id=user_id,
            username=username,
            created_at=created_at,
            idle_expires_at=idle,
            absolute_expires_at=absolute,
            csrf_token=csrf_token_for(self._settings.session_key, str(sid)),
            password_verified_at=_parse_dt(payload.get("password_verified_at")),
            authenticated_at=_parse_dt(payload.get("authenticated_at")),
            enroll=enroll if isinstance(enroll, dict) else None,
        )
