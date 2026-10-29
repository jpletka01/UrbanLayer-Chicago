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
already hold (8 bytes of pointer per match; ~17-20 MB RSS per 949k-match result in practice). The cache is an LRU
bounded by entry count and by the total number of PINs held; a result larger than the whole
budget is returned but not stored. A failed evaluation raises and stores nothing.

Cache misses are protected, too. Identical queries that are in flight at the same time are
coalesced: one caller evaluates, the others wait for its result (or its exception). The
evaluation is pure Python, so threads share the GIL and extra parallelism buys nothing;
concurrent *distinct* evaluations are capped (`MAX_CONCURRENT_EVALS`) so a burst of edits
queues instead of multiplying the work in progress on a small box. A request that waits is
served by the entry its predecessor stored when that happens to be its own query.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import CQS, canonical_key
from backend.discovery.evaluator import evaluate

# Measured on the 949k-parcel production index copy (macOS RSS, 2026-10-29): about 17-20 MB
# per 949k-match entry, so 4M PINs is roughly +130 MB worst case on a box whose index alone
# is ~3 GB of its 8 GB. Typical entries (a few thousand matches) cost kilobytes.
MAX_ENTRIES = 32
MAX_TOTAL_PINS = 4_000_000
MAX_CONCURRENT_EVALS = 2


@dataclass(frozen=True, slots=True)
class CachedResult:
    """An immutable evaluation result (same read surface as `OrderedResult`)."""

    dataVersion: str
    pins: tuple[str, ...]
    total: int
    excludedUnknown: dict[str, int]


_Key = tuple[str, int, str]


class _Flight:
    """One in-flight evaluation that identical concurrent requests wait on."""

    __slots__ = ("done", "result", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: CachedResult | None = None
        self.error: BaseException | None = None


_lock = threading.Lock()
_inflight: dict[_Key, _Flight] = {}
_eval_slots = threading.BoundedSemaphore(MAX_CONCURRENT_EVALS)
_entries: OrderedDict[_Key, CachedResult] = OrderedDict()
_total_pins = 0
_stats = {"hits": 0, "misses": 0, "coalesced": 0}


def stats() -> dict[str, int]:
    with _lock:
        return {**_stats, "entries": len(_entries), "pins": _total_pins}


def clear() -> None:
    global _total_pins
    with _lock:
        _entries.clear()
        _total_pins = 0
        _stats["hits"] = _stats["misses"] = _stats["coalesced"] = 0


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
        flight = _inflight.get(key)
        if flight is not None:
            _stats["coalesced"] += 1
            leader = False
        else:
            flight = _inflight[key] = _Flight()
            _stats["misses"] += 1
            leader = True

    if not leader:
        flight.done.wait()
        if flight.error is not None:
            raise flight.error
        assert flight.result is not None
        return flight.result

    try:
        with _eval_slots:
            fresh = evaluate(cqs, data_version)
        value = CachedResult(
            dataVersion=fresh.dataVersion,
            pins=tuple(fresh.pins),
            total=fresh.total,
            excludedUnknown=dict(fresh.excludedUnknown),
        )
        # Store only if the snapshot is still the one this key names (a replaced snapshot
        # would otherwise be filed under the old generation).
        if parcel_mod.default_source.generation(data_version) == generation:
            _store(key, value)
        flight.result = value
        return value
    except BaseException as exc:
        flight.error = exc  # waiters get the same failure; nothing was stored
        raise
    finally:
        with _lock:
            _inflight.pop(key, None)  # after the store, so a newcomer sees the entry
        flight.done.set()
