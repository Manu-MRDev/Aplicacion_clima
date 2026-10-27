"""Pruebas del limitador de ventana deslizante."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def monotonic(self) -> float:
        return self.value


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(rate_limit_module, "time", SimpleNamespace(monotonic=fake.monotonic))
    return fake


def test_permite_hasta_el_limite_y_luego_espera(clock):
    limiter = SlidingWindowLimiter()
    for _ in range(3):
        assert limiter.check("k", limit=3, window_seconds=60) is None
    retry = limiter.check("k", limit=3, window_seconds=60)
    assert retry is not None
    assert 0 < retry <= 60


def test_ventana_se_desplaza(clock):
    limiter = SlidingWindowLimiter()
    for _ in range(2):
        assert limiter.check("k", limit=2, window_seconds=10) is None
    assert limiter.check("k", limit=2, window_seconds=10) is not None
    clock.value += 10.1
    assert limiter.check("k", limit=2, window_seconds=10) is None


def test_claves_independientes(clock):
    limiter = SlidingWindowLimiter()
    assert limiter.check("a", limit=1, window_seconds=60) is None
    assert limiter.check("b", limit=1, window_seconds=60) is None
    assert limiter.check("a", limit=1, window_seconds=60) is not None


def test_reset_por_clave_y_global(clock):
    limiter = SlidingWindowLimiter()
    assert limiter.check("a", limit=1, window_seconds=60) is None
    limiter.reset("a")
    assert limiter.check("a", limit=1, window_seconds=60) is None
    limiter.reset()
    assert limiter.check("a", limit=1, window_seconds=60) is None


def test_limpieza_de_claves_antiguas(clock):
    limiter = SlidingWindowLimiter()
    assert limiter.check("vieja", limit=1, window_seconds=60) is None
    clock.value += 4000
    assert limiter.check("nueva", limit=1, window_seconds=60) is None
    assert "vieja" not in limiter._events
