"""Limitador de solicitudes en memoria (ventana deslizante)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Limitador por clave con ventana deslizante.

    Es válido por proceso. Con varios workers de Uvicorn cada proceso mantiene su
    propio contador; para un límite global se debe sustituir por Redis. El bloqueo
    de cuentas en base de datos sigue siendo global.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def check(self, key: str, *, limit: int, window_seconds: float) -> float | None:
        """Devuelve None si se permite, o los segundos de espera si se rechaza."""
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(0.1, window_seconds - (now - events[0]))
            events.append(now)
            self._cleanup(now)
            return None

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < 300:
            return
        self._last_cleanup = now
        stale = [key for key, events in self._events.items() if not events or events[-1] < now - 3600]
        for key in stale:
            self._events.pop(key, None)


limiter = SlidingWindowLimiter()
