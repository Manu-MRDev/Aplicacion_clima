"""Esquemas de autenticación y TOTP."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_StrictModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=512)

    @field_validator("username")
    @classmethod
    def _clean_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(ord(char) < 32 for char in cleaned):
            raise ValueError("nombre de usuario inválido")
        return cleaned


class RegisterRequest(_StrictModel):
    """Datos de alta. El backend no acepta id, TOTP ni datos de sesión."""

    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$",
    )
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def _clean_username(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned or any(ord(char) < 32 for char in cleaned):
            raise ValueError("nombre de usuario inválido")
        return cleaned

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("la contraseña no puede empezar ni terminar con espacios")
        classes = sum(
            (
                any("a" <= char <= "z" for char in value),
                any("A" <= char <= "Z" for char in value),
                any("0" <= char <= "9" for char in value),
                any(
                    not (
                        "a" <= char <= "z"
                        or "A" <= char <= "Z"
                        or "0" <= char <= "9"
                    )
                    for char in value
                ),
            )
        )
        if classes < 3:
            raise ValueError(
                "la contraseña debe combinar al menos tres tipos de caracteres"
            )
        return value


class TOTPCodeRequest(_StrictModel):
    code: str = Field(pattern=r"^\d{6}$")


class LoginResponse(BaseModel):
    status: Literal["totp_required", "enrollment_required"]
    csrf_token: str
    expires_at: datetime
    message: str


class RegistrationResponse(BaseModel):
    status: Literal["enrollment_required"]
    csrf_token: str
    expires_at: datetime
    message: str


class EnrollmentResponse(BaseModel):
    manual_key: str
    otpauth_uri: str
    qr_data_uri: str
    issuer: str
    account: str
    expires_at: datetime
    message: str


class UserResponse(BaseModel):
    id: int
    username: str
    totp_enabled: bool
    created_at: datetime | None = None


class AuthenticatedResponse(BaseModel):
    status: Literal["authenticated"] = "authenticated"
    user: UserResponse
    csrf_token: str
    session_expires_at: datetime


class LogoutResponse(BaseModel):
    status: Literal["logged_out"] = "logged_out"


class MeResponse(BaseModel):
    user: UserResponse
    csrf_token: str
    session_expires_at: datetime
