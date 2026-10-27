"""Fixtures globales de la suite."""

from __future__ import annotations

import pytest

from app.core.rate_limit import limiter
from tests.support import make_settings


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def settings():
    return make_settings()
