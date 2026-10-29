"""Result cache in front of the single evaluator (INV-1, INV-2).

`evaluate(cqs, dataVersion)` is a pure function, so its output can be memoised without
changing what any caller sees: a cache hit returns the ordering a fresh evaluation would.
`cached_evaluate` is that memo; `evaluate` itself stays pure and uncached (tests and the
index builder call it directly).

Key: (dataVersion, snapshot generation, `canonical_key(cqs)`). The canonical key covers
`filters`, `sort` and `scope` only, so `meta` and every `source` tag cannot split or merge
entries (INV-2). The generation is the registration id of the snapshot that was read, so a
snapshot that is replaced under the same version string can never serve rows computed on
the old one. Entries from any other (version, generation) are dropped as soon as the next
entry is stored, and a lookup only ever sees its own.

Storage is an immutable tuple of PIN strings, which are the same string objects the parcels
already hold (8 bytes per match, ~7.6 MB for a 949k-match result). The cache is an LRU
bounded by entry count and by the total number of PINs held; a result larger than the whole
budget is returned but not stored. A failed evaluation raises and stores nothing.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import CQS, canonical_key
from backend.discovery.evaluator import evaluate

# ~48 MB of pointers at most (6M PINs x 8 bytes) on a box whose index alone is ~3 GB.
MAX_ENTRIES = 32
MAX_TOTAL_PINS = 6_000_000


@dataclass(frozen=True, slots=True)
class CachedResult:
    """An immutable evaluation result (same read surface as `OrderedResult`)."""

    dataVersion: str
    pins: tuple[str, ...]
    total: int
    excludedUnknown: dict[str, int]


_Key = tuple[str, int, str]

_lock = threading.Lock()
_entries: OrderedDict[_Key, CachedResult] = OrderedDict()
_total_pins = 0
_stats = {"hits": 0, "misses": 0}


def stats() -> dict[str, int]:
    with _lock:
        return {**_stats, "entries": len(_entries), "pins": _total_pins}


def clear() -> None:
    global _total_pins
    with _lock:
        _entries.clear()
        _total_pins = 0
        _stats["hits"] = _stats["misses"] = 0


def _store(key: _Key, value: CachedResult) -> None:
    global _total_pins
    if len(value.pins) > MAX_TOTAL_PINS:
        return  # never cache what alone exceeds the budget
    with _lock:
        for stale in [k for k in _entries if k[:2] != key[:2]]:  # other version/generation
            _total_pins -= len(_entries.pop(stale).pins)
        if key in _entries:
            _total_pins -= len(_entries.pop(key).pins)
        _entries[key] = value
        _total_pins += len(value.pins)
        while len(_entries) > MAX_ENTRIES or _total_pins > MAX_TOTAL_PINS:
            _, evicted = _entries.popitem(last=False)
            _total_pins -= len(evicted.pins)


def cached_evaluate(cqs: CQS, data_version: str) -> CachedResult:
    generation = parcel_mod.default_source.generation(data_version)  # KeyError: unknown version
    key: _Key = (data_version, generation, canonical_key(cqs))
    with _lock:
        hit = _entries.get(key)
        if hit is not None:
            _entries.move_to_end(key)
            _stats["hits"] += 1
            return hit
        _stats["misses"] += 1
    fresh = evaluate(cqs, data_version)
    value = CachedResult(
        dataVersion=fresh.dataVersion,
        pins=tuple(fresh.pins),
        total=fresh.total,
        excludedUnknown=dict(fresh.excludedUnknown),
    )
    # Store only if the snapshot is still the one this key names (a replaced snapshot would
    # otherwise be filed under the old generation).
    if parcel_mod.default_source.generation(data_version) == generation:
        _store(key, value)
    return value
