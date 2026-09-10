"""Cache TTL simples, em memória, para a camada de API.

Os dados de fechamento (B3) e expectativas (Focus) mudam no máximo uma
vez por pregão — bater neles a cada requisição HTTP do frontend seria
lento (o boletim da B3 tem milhares de linhas) e desnecessário. Um TTL
curto absorve a rajada de chamadas de uma sessão de terminal sem
arriscar servir dado desatualizado por muito tempo.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Cache chave -> valor com expiração por tempo, thread-safe."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, T]] = {}

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            cached = self._store.get(key)
            if cached is not None and now - cached[0] < self._ttl:
                return cached[1]

        value = factory()
        with self._lock:
            self._store[key] = (now, value)
        return value
