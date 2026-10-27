"""Utilidades de tiempo (UTC consistente)."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_expired(value: datetime | None, *, now: datetime | None = None) -> bool:
    normalized = as_utc(value)
    if normalized is None:
        return True
    return normalized <= (now or utcnow())
