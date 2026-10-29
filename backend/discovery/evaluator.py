"""The single evaluator (INV-1) — the only function that produces results.

`evaluate(cqs, data_version)` is a pure function of `(canonical CQS, dataVersion)`
(INV-2): filter → sort, no scoring (INV-3), no inference/defaulting/conflict
resolution (INV-6). It reads only the immutable parcel snapshot bound to
`data_version` (via `parcel.default_source`) and the static registry — no clock, RNG,
or mutable global. This module is a leaf: it MUST NOT import `compile_*`, `api`, or
`diagnostics` (09).
"""

from __future__ import annotations

from typing import Protocol, Sequence

from pydantic import BaseModel, Field

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import CQS
from backend.discovery.predicates import satisfies, within_scope
from backend.discovery.registry import load as load_registry


# Missing-value concept applies to scalar attributes only (see diagnostics D4).
_SCALAR_KINDS = {"enum", "range", "flag"}


class OrderedResult(BaseModel):
    dataVersion: str
    pins: list[str] = Field(default_factory=list)  # ordered, total order, no duplicates
    total: int = 0
    # D4 (diagnostics): per exclude-policy scalar filter, parcels in scope that pass every
    # OTHER applied predicate and are dropped solely because that filter's field is missing.
    # Computed in the same pass as the filter (a pure function of the CQS and dataVersion);
    # only non-zero entries, in applied-filter order.
    excludedUnknown: dict[str, int] = Field(default_factory=dict)


class EvalResult(Protocol):
    """What callers read from an evaluation: `OrderedResult`, or a cached, immutable copy."""

    dataVersion: str
    pins: Sequence[str]
    total: int
    excludedUnknown: dict[str, int]


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

    # Resolve each applied filter's field + unknownPolicy once (not per parcel). `track` marks
    # the scalar exclude-policy filters whose missing-value drops D4 reports (region membership
    # is a computed determination, never a NULL field).
    applied = []
    for fid, a in cqs.filters.items():
        fdef = registry.filter_def(fid)
        track = fdef.unknownPolicy == "exclude" and fdef.kind in _SCALAR_KINDS
        applied.append((fid, a.predicate, fdef.field, fdef.unknownPolicy, track))
    scope = cqs.scope

    # --- Stage 1: filter (AND across filters; scope ANDs too, 05) ---
    # One pass. A parcel stops at its first failing predicate; if that filter is tracked and
    # the parcel's field for it is missing, the parcel is a D4 exclusion for that filter iff
    # every LATER predicate passes (the earlier ones already did). It can count for no other
    # filter: any other filter's count requires passing this one.
    candidates = []
    unknown_counts: dict[str, int] = {}
    for p in parcels:
        if not within_scope(p, scope):
            continue
        failed = -1
        for i, (_fid, pred, field, policy, _track) in enumerate(applied):
            if not satisfies(pred, p, field, policy):
                failed = i
                break
        if failed < 0:
            candidates.append(p)
            continue
        fid, _pred, field, _policy, track = applied[failed]
        if track and p.get(field) is None and all(
            satisfies(pr, p, fl, po) for _f, pr, fl, po, _t in applied[failed + 1 :]
        ):
            unknown_counts[fid] = unknown_counts.get(fid, 0) + 1

    # --- Stage 2: sort (single key + dir, missing-last, final PIN-asc tie-break) ---
    ordered = _order(candidates, registry.sort_field(cqs.sort.key), cqs.sort.dir == "desc")
    pins = [p.pin for p in ordered]
    excluded = {fid: unknown_counts[fid] for fid, *_ in applied if unknown_counts.get(fid)}
    return OrderedResult(
        dataVersion=data_version, pins=pins, total=len(pins), excludedUnknown=excluded
    )
