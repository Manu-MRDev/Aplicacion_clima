"""Representación canónica, hashes SHA-256 y verificación de la cadena de bloques.

Versión del formato canónico: ``canon-v1``.
Versión del hash: ``sha256:v1``.

Reglas de normalización:
- Claves ordenadas y JSON compacto (separadores ``,`` y ``:``), UTF-8 sin escapar.
- Nulos explícitos (nunca se omiten claves).
- Decimales normalizados sin ceros finales y sin notación científica.
- Fechas en UTC, ISO-8601 con microsegundos.
- Texto Unicode NFC.
- Se incluye la versión del formato en el propio objeto canónico.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.domain import IntegrityBlock, StoredRecord, WeatherRecord

CANON_VERSION = "canon-v1"
# El hash se almacena como 64 caracteres hex porque las tablas existentes
# (bpchar(64) / char(64)) no admiten prefijo. La versión va en el payload.
HASH_VERSION = "sha256-hex-v1"
BLOCK_HASH_VERSION = "block-v1"
GENESIS_HASH = "0" * 64


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return unicodedata.normalize("NFC", value)


def normalize_decimal(value: Decimal | int | float | str | None) -> str | None:
    if value is None:
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("valor decimal inválido") from exc
    if not number.is_finite():
        raise ValueError("valor decimal no finito")
    if number == 0:
        return "0"
    normalized = number.normalize()
    return format(normalized, "f")


def normalize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def canonical_record_dict(
    record: WeatherRecord | StoredRecord, *, servidor: str, record_id: int
) -> dict[str, Any]:
    """Representación lógica y determinista de un registro climático."""
    return {
        "v": CANON_VERSION,
        "servidor": servidor,
        "registro_id": int(record_id),
        "usuario": normalize_text(record.usuario),
        "nombre": normalize_text(record.nombre),
        "paterno": normalize_text(record.paterno),
        "materno": normalize_text(record.materno),
        "estado": normalize_text(record.estado),
        "municipio": normalize_text(record.municipio),
        "latitud": normalize_decimal(record.latitud),
        "longitud": normalize_decimal(record.longitud),
        "temperatura": normalize_decimal(record.temperatura),
        "humedad": normalize_decimal(record.humedad),
        "viento": normalize_decimal(record.viento),
        "fecha_hora": normalize_datetime(record.fecha_hora),
    }


def canonical_record_json(
    record: WeatherRecord | StoredRecord, *, servidor: str, record_id: int
) -> str:
    return canonical_json(canonical_record_dict(record, servidor=servidor, record_id=record_id))


def record_hash(canonical_data: str) -> str:
    """SHA-256 (64 hex) de la representación canónica del registro."""
    return sha256_hex(canonical_data)


def block_payload(
    *,
    cadena: str,
    indice: int,
    registro_id: int,
    datos_canonicos: str,
    hash_anterior: str | None,
) -> dict[str, Any]:
    return {
        "v": BLOCK_HASH_VERSION,
        "cadena": cadena,
        "indice": int(indice),
        "registro_id": int(registro_id),
        "datos": datos_canonicos,
        "hash_anterior": hash_anterior,
    }


def compute_block_hash(
    *,
    cadena: str,
    indice: int,
    registro_id: int,
    datos_canonicos: str,
    hash_anterior: str | None,
) -> str:
    payload = block_payload(
        cadena=cadena,
        indice=indice,
        registro_id=registro_id,
        datos_canonicos=datos_canonicos,
        hash_anterior=hash_anterior,
    )
    return sha256_hex(canonical_json(payload))


def verify_chain(
    blocks: list[IntegrityBlock],
    *,
    records: dict[int, StoredRecord],
    cadena: str,
    servidor: str,
    record_ids: set[int] | None = None,
) -> list[str]:
    """Verifica estructura, hashes y correspondencia con los registros actuales."""
    errors: list[str] = []
    seen_indices: set[int] = set()
    seen_records: set[int] = set()
    previous_hash: str | None = None

    for position, block in enumerate(blocks):
        hash_anterior = (
            block.hash_anterior.strip() if block.hash_anterior is not None else None
        )
        hash_actual = block.hash_actual.strip()
        if block.cadena != cadena:
            errors.append(f"bloque {block.indice} pertenece a otra cadena")
        if block.indice in seen_indices:
            errors.append(f"índice duplicado: {block.indice}")
        seen_indices.add(block.indice)
        if block.indice != position:
            errors.append(
                f"secuencia de índices rota en la posición {position}: se esperaba {position} "
                f"y se encontró {block.indice}"
            )
        if block.registro_id in seen_records:
            errors.append(f"registro duplicado en la cadena: {block.registro_id}")
        seen_records.add(block.registro_id)
        if position == 0:
            # El génesis se admite como 64 ceros o como NULL (filas antiguas).
            previous_ok = hash_anterior in (GENESIS_HASH, None)
        else:
            previous_ok = hash_anterior is not None and hash_anterior.lower() == (
                previous_hash or ""
            ).lower()
        if not previous_ok:
            errors.append(
                f"hash anterior inconsistente en el bloque {block.indice}: "
                "no coincide con el bloque previo"
            )
        if len(hash_actual) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in hash_actual
        ):
            errors.append(f"formato de hash no soportado en el bloque {block.indice}")
        try:
            expected = compute_block_hash(
                cadena=cadena,
                indice=block.indice,
                registro_id=block.registro_id,
                datos_canonicos=block.datos_canonicos,
                hash_anterior=hash_anterior,
            )
        except ValueError:
            expected = ""
        if expected.lower() != hash_actual.lower():
            errors.append(f"hash del bloque {block.indice} no coincide")

        record = records.get(block.registro_id)
        if record is None:
            errors.append(f"el bloque {block.indice} referencia un registro inexistente")
        else:
            try:
                current = canonical_record_json(
                    record, servidor=servidor, record_id=block.registro_id
                )
            except ValueError:
                current = ""
            if current != block.datos_canonicos:
                errors.append(f"datos del registro {block.registro_id} alterados")
        previous_hash = hash_actual.lower()

    if record_ids is not None:
        missing = record_ids - seen_records
        for record_id in sorted(missing)[:50]:
            errors.append(f"registro {record_id} sin bloque de integridad")
        if len(missing) > 50:
            errors.append(f"... y {len(missing) - 50} registros más sin bloque")
    return errors
