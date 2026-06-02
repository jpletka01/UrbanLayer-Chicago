"""Simple in-memory TTL cache for spatial query results.

Thread-safe for asyncio's single-threaded event loop (no locks needed).
"""

import time
from typing import Any


class TTLCache:

    _instances: list["TTLCache"] = []

    def __init__(self, ttl_seconds: int, maxsize: int = 2048, name: str = ""):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self._name = name
        self._hits = 0
        self._misses = 0
        TTLCache._instances.append(self)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._maxsize and key not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic(), value)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "ttl_seconds": self._ttl,
            "maxsize": self._maxsize,
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
        }
