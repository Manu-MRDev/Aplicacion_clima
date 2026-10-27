"""Pruebas del formato canónico, hashes y verificación de cadena."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.domain import IntegrityBlock, StoredRecord
from app.services.integrity_service import (
    GENESIS_HASH,
    block_payload,
    canonical_json,
    canonical_record_dict,
    canonical_record_json,
    compute_block_hash,
    normalize_datetime,
    normalize_decimal,
    normalize_text,
    record_hash,
    sha256_hex,
    verify_chain,
)


def _record(record_id: int = 1, *, nombre: str = "Ana") -> StoredRecord:
    return StoredRecord(
        id=record_id,
        usuario="ana",
        nombre=nombre,
        paterno="Pérez",
        materno="López",
        estado="CDMX",
        municipio="Coyoacán",
        latitud=Decimal("19.3500000"),
        longitud=Decimal("-99.1620000"),
        temperatura=Decimal("21.50"),
        humedad=Decimal("55.00"),
        viento=Decimal("12.30"),
        fecha_hora=datetime(2026, 10, 25, 12, 0, 0, 123456, tzinfo=UTC),
        servidor="ubuntu",
    )


def _block(record: StoredRecord, *, index: int, previous: str | None) -> IntegrityBlock:
    data = canonical_record_json(record, servidor="ubuntu", record_id=record.id)
    current = compute_block_hash(
        cadena="api-ubuntu",
        indice=index,
        registro_id=record.id,
        datos_canonicos=data,
        hash_anterior=previous,
    )
    return IntegrityBlock(
        cadena="api-ubuntu",
        indice=index,
        registro_id=record.id,
        datos_canonicos=data,
        hash_anterior=previous,
        hash_actual=current,
    )


def test_normalizacion_decimales():
    assert normalize_decimal(Decimal("1.2300")) == "1.23"
    assert normalize_decimal(Decimal("-0.00")) == "0"
    assert normalize_decimal(Decimal("1E+3")) == "1000"
    assert normalize_decimal(Decimal("0.000001")) == "0.000001"
    assert normalize_decimal(None) is None
    with pytest.raises(ValueError):
        normalize_decimal(Decimal("NaN"))


def test_normalizacion_fechas():
    naive = datetime(2026, 1, 2, 3, 4, 5, 6000)
    aware = naive.replace(tzinfo=timezone(timedelta(hours=-6)))
    assert normalize_datetime(naive) == "2026-01-02T03:04:05.006000+00:00"
    assert normalize_datetime(aware) == "2026-01-02T09:04:05.006000+00:00"
    assert normalize_datetime(None) is None


def test_normalizacion_unicode():
    decomposed = "A\u0301na"
    assert normalize_text(decomposed) == "Ána"
    assert normalize_text(None) is None


def test_json_canonico_es_estable():
    first = canonical_json({"b": 2, "a": "ñ"})
    second = canonical_json({"a": "ñ", "b": 2})
    assert first == second == '{"a":"ñ","b":2}'


def test_dict_canonico_incluye_version_y_todos_los_campos():
    data = canonical_record_dict(_record(), servidor="ubuntu", record_id=7)
    assert data["v"] == "canon-v1"
    assert data["servidor"] == "ubuntu"
    assert data["registro_id"] == 7
    assert data["latitud"] == "19.35"
    assert data["fecha_hora"] == "2026-10-25T12:00:00.123456+00:00"
    assert set(data) == {
        "v",
        "servidor",
        "registro_id",
        "usuario",
        "nombre",
        "paterno",
        "materno",
        "estado",
        "municipio",
        "latitud",
        "longitud",
        "temperatura",
        "humedad",
        "viento",
        "fecha_hora",
    }


def test_hash_de_registro_es_sha256_hex():
    data = canonical_record_json(_record(), servidor="ubuntu", record_id=1)
    digest = record_hash(data)
    assert len(digest) == 64
    assert digest == sha256_hex(data)


def test_payload_de_bloque_es_versionado():
    payload = block_payload(
        cadena="api-ubuntu",
        indice=0,
        registro_id=1,
        datos_canonicos="{}",
        hash_anterior=GENESIS_HASH,
    )
    assert payload["v"] == "block-v1"
    assert payload["hash_anterior"] == GENESIS_HASH


def test_cadena_valida():
    first = _record(1)
    second = _record(2, nombre="Luis")
    blocks = [
        _block(first, index=0, previous=GENESIS_HASH),
        _block(second, index=1, previous=None),
    ]
    blocks[1] = _block(
        second, index=1, previous=blocks[0].hash_actual
    )
    errors = verify_chain(
        blocks,
        records={1: first, 2: second},
        cadena="api-ubuntu",
        servidor="ubuntu",
    )
    assert errors == []


def test_datos_alterados():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    altered = StoredRecord(**{**record.__dict__, "temperatura": Decimal("99.99")})
    errors = verify_chain(
        [block], records={1: altered}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("alterados" in error for error in errors)


def test_hashes_con_relleno_de_char_se_aceptan():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    padded = IntegrityBlock(
        **{
            **block.__dict__,
            "hash_anterior": GENESIS_HASH + "  ",
            "hash_actual": block.hash_actual + "  ",
        }
    )
    errors = verify_chain(
        [padded], records={1: record}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert errors == []


def test_hash_alterado():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    tampered = IntegrityBlock(**{**block.__dict__, "hash_actual": "f" * 64})
    errors = verify_chain(
        [tampered], records={1: record}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("hash del bloque" in error for error in errors)


def test_hash_anterior_roto():
    first = _record(1)
    second = _record(2)
    blocks = [
        _block(first, index=0, previous=GENESIS_HASH),
        _block(second, index=1, previous="a" * 64),
    ]
    errors = verify_chain(
        blocks, records={1: first, 2: second}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("hash anterior inconsistente" in error for error in errors)


def test_hash_anterior_nulo_no_se_acepta_despues_del_primero():
    first = _record(1)
    second = _record(2)
    blocks = [
        _block(first, index=0, previous=GENESIS_HASH),
        _block(second, index=1, previous=None),
    ]
    errors = verify_chain(
        blocks, records={1: first, 2: second}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("hash anterior inconsistente" in error for error in errors)


def test_indices_duplicados_y_fuera_de_secuencia():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    errors = verify_chain(
        [block, block], records={1: record}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("índice duplicado" in error for error in errors)
    assert any("secuencia de índices rota" in error for error in errors)
    assert any("registro duplicado" in error for error in errors)


def test_registro_inexistente():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    errors = verify_chain([block], records={}, cadena="api-ubuntu", servidor="ubuntu")
    assert any("registro inexistente" in error for error in errors)


def test_cadena_distinta():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    other = IntegrityBlock(**{**block.__dict__, "cadena": "api-windows"})
    errors = verify_chain(
        [other], records={1: record}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("otra cadena" in error for error in errors)


def test_formato_de_hash_invalido():
    record = _record(1)
    block = _block(record, index=0, previous=GENESIS_HASH)
    shortened = IntegrityBlock(**{**block.__dict__, "hash_actual": "abc"})
    errors = verify_chain(
        [shortened], records={1: record}, cadena="api-ubuntu", servidor="ubuntu"
    )
    assert any("formato de hash" in error for error in errors)
