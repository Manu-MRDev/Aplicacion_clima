"""Configuración tipada de la aplicación, cargada desde variables de entorno."""

from __future__ import annotations

import base64
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _decode_base64_key(value: SecretStr, field_name: str) -> bytes:
    raw = value.get_secret_value().strip()
    if not raw:
        raise ValueError(f"{field_name} no puede estar vacía")
    try:
        padded = raw + "=" * (-len(raw) % 4)
        key = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:  # pragma: no cover - mensaje uniforme
        raise ValueError(f"{field_name} debe ser base64 válido") from exc
    if len(key) != 32:
        raise ValueError(f"{field_name} debe decodificar exactamente 32 bytes (AES-256)")
    return key


def _as_list(value: Any) -> Any:
    """Permite listas JSON y también valores separados por comas."""
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            return raw  # deja que pydantic lo parsee como JSON
        return [item.strip() for item in raw.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicación ---
    app_name: str = "Clima API"
    app_env: Literal["development", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False
    api_prefix: str = "/api"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    docs_enabled: bool | None = None
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: list[str] = Field(default_factory=list)
    trusted_proxies: list[str] = Field(default_factory=list)
    # Sin valor explícito: habilitado en desarrollo y deshabilitado en producción.
    registration_enabled: bool | None = None

    # --- PostgreSQL ---
    postgres_host: str = "192.168.56.10"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "UPP"
    postgres_user: str = "tux"
    postgres_password: SecretStr = SecretStr("")
    postgres_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = (
        "prefer"
    )
    postgres_connect_timeout: float = Field(default=5.0, gt=0, le=60)
    postgres_pool_min_size: int = Field(default=1, ge=0, le=50)
    postgres_pool_max_size: int = Field(default=10, ge=1, le=50)

    # --- SQL Server ---
    sqlserver_host: str = "192.168.56.11"
    sqlserver_port: int = Field(default=49834, ge=1, le=65535)
    sqlserver_db: str = "UPP"
    sqlserver_user: str = "tux"
    sqlserver_password: SecretStr = SecretStr("")
    sqlserver_odbc_driver: str = "ODBC Driver 18 for SQL Server"
    sqlserver_encrypt: Literal["yes", "no"] = "yes"
    sqlserver_trust_server_certificate: Literal["yes", "no"] = "no"
    sqlserver_connect_timeout: float = Field(default=5.0, gt=0, le=60)
    sqlserver_pool_max_size: int = Field(default=5, ge=1, le=50)
    # Directorio con odbcinst.ini (solo desarrollo local; en producción, /etc).
    odbc_config_dir: str = ""

    # --- Claves criptográficas (32 bytes base64, propósitos separados) ---
    session_secret_key: SecretStr
    totp_encryption_key: SecretStr
    record_encryption_key: SecretStr

    # --- Sesiones ---
    session_cookie_name: str = ""
    session_secure_cookies: bool | None = None
    session_samesite: Literal["lax", "strict", "none"] = "lax"
    session_ttl_seconds: int = Field(default=28800, ge=300, le=604800)
    session_absolute_ttl_seconds: int = Field(default=43200, ge=300, le=1209600)
    pending_session_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    # --- Bloqueo / TOTP ---
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_lockout_seconds: int = Field(default=900, ge=30, le=86400)
    totp_max_attempts: int = Field(default=5, ge=1, le=20)
    totp_enroll_max_generations_per_hour: int = Field(default=3, ge=1, le=20)

    # --- Rate limit ---
    rate_limit_login_per_minute: int = Field(default=5, ge=1, le=1000)
    rate_limit_register_per_minute: int = Field(default=3, ge=1, le=1000)
    rate_limit_totp_per_minute: int = Field(default=5, ge=1, le=1000)
    rate_limit_enroll_per_minute: int = Field(default=3, ge=1, le=1000)
    rate_limit_records_per_minute: int = Field(default=60, ge=1, le=10000)
    rate_limit_public_per_minute: int = Field(default=30, ge=1, le=10000)

    # --- Open-Meteo ---
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    weather_cache_ttl_seconds: int = Field(default=60, ge=0, le=3600)

    # --- Nominatim ---
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "Clima-API/1.0 (contacto@example.invalid)"
    geocoding_accept_language: str = "es"
    geocoding_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    geocoding_cache_ttl_seconds: int = Field(default=86400, ge=0, le=604800)
    geocoding_min_interval_seconds: float = Field(default=1.0, ge=0, le=60)

    # --- Integridad ---
    integrity_enabled: bool = True

    # --- TLS ---
    ssl_certfile: str = ""
    ssl_keyfile: str = ""

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @field_validator("cors_origins", "allowed_hosts", "trusted_proxies", mode="before")
    @classmethod
    def _parse_lists(cls, value: Any) -> Any:
        return _as_list(value)

    @field_validator("docs_enabled", "session_secure_cookies", mode="before")
    @classmethod
    def _empty_is_none(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("cors_origins")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for origin in value:
            origin = origin.strip().rstrip("/")
            if not origin:
                continue
            if origin == "*":
                raise ValueError("CORS_ORIGINS no admite '*' cuando se usan cookies")
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(f"Origen CORS inválido: {origin!r}")
            cleaned.append(origin)
        return cleaned

    @field_validator("postgres_password", "sqlserver_password")
    @classmethod
    def _require_db_password(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("La contraseña de base de datos es obligatoria")
        return value

    @model_validator(mode="after")
    def _validate_consistency(self) -> "Settings":
        # Claves: 32 bytes y propósitos separados.
        keys = {
            "SESSION_SECRET_KEY": _decode_base64_key(self.session_secret_key, "SESSION_SECRET_KEY"),
            "TOTP_ENCRYPTION_KEY": _decode_base64_key(self.totp_encryption_key, "TOTP_ENCRYPTION_KEY"),
            "RECORD_ENCRYPTION_KEY": _decode_base64_key(
                self.record_encryption_key, "RECORD_ENCRYPTION_KEY"
            ),
        }
        if len(set(keys.values())) != 3:
            raise ValueError("Las tres claves criptográficas deben ser distintas")

        if self.session_absolute_ttl_seconds < self.session_ttl_seconds:
            raise ValueError("SESSION_ABSOLUTE_TTL_SECONDS debe ser >= SESSION_TTL_SECONDS")
        if self.postgres_pool_min_size > self.postgres_pool_max_size:
            raise ValueError("POSTGRES_POOL_MIN_SIZE no puede superar POSTGRES_POOL_MAX_SIZE")
        if self.session_samesite == "none" and not self.secure_cookies:
            raise ValueError("SameSite=None requiere cookies Secure")
        if not self.geocoding_user_agent.strip():
            raise ValueError("GEOCODING_USER_AGENT es obligatorio (política de Nominatim)")
        if self.is_production and self.debug:
            raise ValueError("DEBUG no puede estar activo en producción")
        if self.is_production and self.docs_enabled:
            raise ValueError("DOCS_ENABLED no puede estar activo en producción")
        if self.is_production and self.session_secure_cookies is False:
            raise ValueError("Las cookies deben ser Secure en producción")
        if self.is_production and self.sqlserver_trust_server_certificate == "yes":
            raise ValueError(
                "SQLSERVER_TRUST_SERVER_CERTIFICATE=yes no se permite en producción"
            )
        if self.is_production and self.postgres_sslmode not in ("require", "verify-ca", "verify-full"):
            raise ValueError(
                "En producción POSTGRES_SSLMODE debe ser require, verify-ca o verify-full"
            )
        return self

    # ------------------------------------------------------------------
    # Derivados
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def registration_is_enabled(self) -> bool:
        if self.registration_enabled is not None:
            return self.registration_enabled
        return not self.is_production

    @property
    def docs_are_enabled(self) -> bool:
        # /docs y /openapi.json nunca se publican en producción.
        if self.is_production:
            return False
        if self.docs_enabled is not None:
            return self.docs_enabled
        return True

    @property
    def secure_cookies(self) -> bool:
        if self.is_production:
            return True
        if self.session_secure_cookies is not None:
            return self.session_secure_cookies
        return False

    @property
    def cookie_name(self) -> str:
        if self.session_cookie_name:
            return self.session_cookie_name
        return "__Host-clima_session" if self.is_production else "clima_session"

    @property
    def session_key(self) -> bytes:
        return _decode_base64_key(self.session_secret_key, "SESSION_SECRET_KEY")

    @property
    def totp_key(self) -> bytes:
        return _decode_base64_key(self.totp_encryption_key, "TOTP_ENCRYPTION_KEY")

    @property
    def record_key(self) -> bytes:
        return _decode_base64_key(self.record_encryption_key, "RECORD_ENCRYPTION_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
