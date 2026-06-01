"""Simple in-memory TTL cache for spatial query results.

Thread-safe for asyncio's single-threaded event loop (no locks needed).
"""

import time
from typing import Any


class TTLCache:

    def __init__(self, ttl_seconds: int, maxsize: int = 2048):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._maxsize and key not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic(), value)
