"""Pruebas de configuración y valores derivados de seguridad."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.support import make_settings


def test_development_permite_docs_y_cookies_no_secure():
    settings = make_settings()
    assert settings.docs_are_enabled is True
    assert settings.secure_cookies is False
    assert settings.cookie_name == "clima_session"
    assert settings.registration_is_enabled is True


def test_produccion_deshabilita_registro_por_defecto():
    settings = make_settings(
        app_env="production",
        postgres_sslmode="require",
        docs_enabled=None,
    )
    assert settings.registration_is_enabled is False


def test_produccion_permite_registro_explicito():
    settings = make_settings(
        app_env="production",
        postgres_sslmode="require",
        docs_enabled=None,
        registration_enabled=True,
    )
    assert settings.registration_is_enabled is True


def test_production_endurece_cookies_y_oculta_docs():
    settings = make_settings(
        app_env="production",
        postgres_sslmode="require",
        docs_enabled=None,
    )
    assert settings.docs_are_enabled is False
    assert settings.secure_cookies is True
    assert settings.cookie_name == "__Host-clima_session"


def test_production_rechaza_docs_explicitos():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="production",
            postgres_sslmode="require",
            docs_enabled=True,
        )


def test_production_rechaza_sslmode_inseguro():
    with pytest.raises(ValidationError):
        make_settings(app_env="production", postgres_sslmode="prefer")


def test_production_rechaza_trust_server_certificate():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="production",
            postgres_sslmode="require",
            sqlserver_trust_server_certificate="yes",
        )


def test_production_rechaza_cookies_no_secure():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="production",
            postgres_sslmode="require",
            session_secure_cookies=False,
        )


def test_production_rechaza_debug():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="production",
            postgres_sslmode="require",
            debug=True,
        )


def test_samesite_none_exige_secure():
    with pytest.raises(ValidationError):
        make_settings(session_samesite="none", session_secure_cookies=False)


def test_claves_deben_ser_distintas():
    shared = make_settings().session_secret_key
    with pytest.raises(ValidationError):
        make_settings(totp_encryption_key=shared)


def test_clave_debe_decodificar_32_bytes():
    with pytest.raises(ValidationError):
        make_settings(session_secret_key="Y29ydGE=")


def test_cors_no_admite_wildcard():
    with pytest.raises(ValidationError):
        make_settings(cors_origins=["*"])


def test_cors_exige_esquema():
    with pytest.raises(ValidationError):
        make_settings(cors_origins=["frontend.test"])


def test_listas_por_comas():
    settings = make_settings(
        allowed_hosts="localhost, 127.0.0.1 ,testserver",
        cors_origins="http://a.test, http://b.test/",
    )
    assert settings.allowed_hosts == ["localhost", "127.0.0.1", "testserver"]
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_ttl_absoluto_mayor_o_igual():
    with pytest.raises(ValidationError):
        make_settings(session_ttl_seconds=600, session_absolute_ttl_seconds=300)


def test_user_agent_de_geocoding_obligatorio():
    with pytest.raises(ValidationError):
        make_settings(geocoding_user_agent="   ")
