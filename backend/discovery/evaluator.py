"""The single evaluator (INV-1) — the only function that produces results.

`evaluate(cqs, data_version)` is a pure function of `(canonical CQS, dataVersion)`
(INV-2): filter → sort, no scoring (INV-3), no inference/defaulting/conflict
resolution (INV-6). It reads only the immutable parcel snapshot bound to
`data_version` (via `parcel.default_source`) and the static registry — no clock, RNG,
or mutable global. This module is a leaf: it MUST NOT import `compile_*`, `api`, or
`diagnostics` (09).
"""

from __future__ import annotations

import functools

from pydantic import BaseModel, Field

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import CQS
from backend.discovery.predicates import satisfies, within_scope
from backend.discovery.registry import load as load_registry


class OrderedResult(BaseModel):
    dataVersion: str
    pins: list[str] = Field(default_factory=list)  # ordered, total order, no duplicates
    total: int = 0


def _normalize_pin(pin: str) -> str:
    """14-digit form for a stable, separator-insensitive PIN tie-break."""
    return pin.replace("-", "").zfill(14)


def evaluate(cqs: CQS, data_version: str) -> OrderedResult:
    registry = load_registry()
    parcels = parcel_mod.default_source.get(data_version)

    # Resolve each applied filter's field + unknownPolicy once (not per parcel).
    applied = [
        (a.predicate, registry.filter_def(fid).field, registry.filter_def(fid).unknownPolicy)
        for fid, a in cqs.filters.items()
    ]
    scope = cqs.scope

    # --- Stage 1: filter (AND across filters; scope ANDs too, 05) ---
    candidates = [
        p
        for p in parcels
        if within_scope(p, scope)
        and all(satisfies(pred, p, field, policy) for pred, field, policy in applied)
    ]

    # --- Stage 2: sort (single key + dir, missing-last, final PIN-asc tie-break) ---
    sort_field = registry.sort_field(cqs.sort.key)
    descending = cqs.sort.dir == "desc"

    def sort_value(p) -> object | None:
        # Sorting by the PIN key uses the normalized PIN as the value (never missing).
        return _normalize_pin(p.pin) if sort_field == "pin" else p.get(sort_field)

    def compare(a, b) -> int:
        av, bv = sort_value(a), sort_value(b)
        a_missing, b_missing = av is None, bv is None
        if a_missing != b_missing:
            return 1 if a_missing else -1  # missing sorts last, regardless of dir
        if not a_missing:
            if av < bv:
                primary = -1
            elif av > bv:
                primary = 1
            else:
                primary = 0
            if descending:
                primary = -primary
            if primary != 0:
                return primary
        # tie (or both missing) → ascending PIN, always
        pa, pb = _normalize_pin(a.pin), _normalize_pin(b.pin)
        return -1 if pa < pb else (1 if pa > pb else 0)

    ordered = sorted(candidates, key=functools.cmp_to_key(compare))
    pins = [p.pin for p in ordered]
    return OrderedResult(dataVersion=data_version, pins=pins, total=len(pins))
