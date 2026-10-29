"""The single evaluator (INV-1) — the only function that produces results.

`evaluate(cqs, data_version)` is a pure function of `(canonical CQS, dataVersion)`
(INV-2): filter → sort, no scoring (INV-3), no inference/defaulting/conflict
resolution (INV-6). It reads only the immutable parcel snapshot bound to
`data_version` (via `parcel.default_source`) and the static registry — no clock, RNG,
or mutable global. This module is a leaf: it MUST NOT import `compile_*`, `api`, or
`diagnostics` (09).
"""

from __future__ import annotations

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


def _pin_key(p) -> str:
    return _normalize_pin(p.pin)


def _order(candidates: list, sort_field: str, descending: bool) -> list:
    """Total order: sort key (missing last, regardless of dir), then ascending PIN.

    Python's sort is stable, including with `reverse=True` (equal elements keep their input
    order), so sorting by PIN first and then by the value yields the PIN-ascending tie-break
    for both directions. This replaces a `cmp_to_key` comparator (millions of Python calls at
    citywide scale) with C-level key sorts and produces the identical order.
    """
    if sort_field == "pin":
        return sorted(candidates, key=_pin_key, reverse=descending)
    present: list = []
    missing: list = []
    for p in candidates:
        (missing if p.get(sort_field) is None else present).append(p)
    present.sort(key=_pin_key)
    present.sort(key=lambda p: p.get(sort_field), reverse=descending)
    missing.sort(key=_pin_key)
    return present + missing


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
    ordered = _order(candidates, registry.sort_field(cqs.sort.key), cqs.sort.dir == "desc")
    pins = [p.pin for p in ordered]
    return OrderedResult(dataVersion=data_version, pins=pins, total=len(pins))
