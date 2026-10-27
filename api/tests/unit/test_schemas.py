"""Pruebas de validación de entrada y salida."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.domain import StoredRecord
from app.schemas.auth import LoginRequest, RegisterRequest, TOTPCodeRequest
from app.schemas.records import RecordCreateRequest, RecordOut


def _payload(**overrides):
    data = {
        "servidor": "ubuntu",
        "nombre": "Ana",
        "paterno": "Pérez",
        "materno": "López",
        "estado": "CDMX",
        "municipio": "Coyoacán",
        "latitud": "19.35",
        "longitud": "-99.16",
        "temperatura": "21.5",
        "humedad": "55",
        "viento": "12.3",
    }
    data.update(overrides)
    return data


def test_registro_valido():
    payload = RecordCreateRequest.model_validate(_payload())
    assert payload.latitud == Decimal("19.35")
    assert payload.fecha_hora is None


def test_id_no_se_acepta_en_insercion():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(id=5))


def test_windows_exige_paterno():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(servidor="windows", paterno=None))


def test_servidor_solo_ubuntu_o_windows():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(servidor="ambos"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("humedad", "-1"),
        ("humedad", "101"),
        ("latitud", "91"),
        ("longitud", "-181"),
        ("temperatura", "-91"),
        ("viento", "-1"),
    ],
)
def test_rangos_fisicos(field, value):
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(**{field: value}))


def test_campos_obligatorios_no_vacios():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(nombre="   "))


def test_caracteres_de_control_rechazados():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(_payload(municipio="Coyoacán\x00"))


def test_fecha_futura_rechazada():
    with pytest.raises(ValidationError):
        RecordCreateRequest.model_validate(
            _payload(fecha_hora=(datetime.now(UTC) + timedelta(hours=1)).isoformat())
        )


def test_fecha_naive_se_asume_utc():
    payload = RecordCreateRequest.model_validate(
        _payload(fecha_hora="2026-01-02T03:04:05")
    )
    assert payload.fecha_hora == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_paterno_vacio_se_normaliza_a_none():
    payload = RecordCreateRequest.model_validate(_payload(paterno="   "))
    assert payload.paterno is None


def test_login_limpia_espacios():
    request = LoginRequest(username="  ana  ", password="x")
    assert request.username == "ana"


def test_login_rechaza_controles():
    with pytest.raises(ValidationError):
        LoginRequest(username="an\x01a", password="x")


def test_registro_limpia_usuario_y_acepta_clave_fuerte():
    request = RegisterRequest(
        username="  nueva.cuenta  ", password="Clave-Segura-2026!"
    )
    assert request.username == "nueva.cuenta"


@pytest.mark.parametrize(
    "username",
    ["a", "con espacio", ".empieza", "nueva@cuenta", "x" * 65],
)
def test_registro_rechaza_usuarios_invalidos(username):
    with pytest.raises(ValidationError):
        RegisterRequest(username=username, password="Clave-Segura-2026!")


@pytest.mark.parametrize(
    "password",
    [
        "corta",
        "solominusculas2026",
        "SOLOMAYUSCULAS2026",
        "1234567890123",
        " Clave-Segura-2026!",
        "x" * 129,
    ],
)
def test_registro_rechaza_claves_debiles(password):
    with pytest.raises(ValidationError):
        RegisterRequest(username="nueva", password=password)


def test_registro_rechaza_campos_extra():
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(
            {
                "username": "nueva",
                "password": "Clave-Segura-2026!",
                "admin": True,
            }
        )


@pytest.mark.parametrize("code", ["123456", "000000"])
def test_codigo_totp_valido(code):
    assert TOTPCodeRequest(code=code).code == code


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 34"])
def test_codigo_totp_invalido(code):
    with pytest.raises(ValidationError):
        TOTPCodeRequest(code=code)


def test_record_out_convierte_decimales():
    record = StoredRecord(
        id=1,
        usuario="ana",
        nombre="Ana",
        paterno=None,
        materno=None,
        estado="CDMX",
        municipio="Coyoacán",
        latitud=Decimal("19.35"),
        longitud=None,
        temperatura=Decimal("21.50"),
        humedad=None,
        viento=None,
        fecha_hora=datetime.now(UTC),
        servidor="ubuntu",
    )
    out = RecordOut.from_domain(record)
    assert out.latitud == 19.35
    assert out.temperatura == 21.5
    assert out.longitud is None
