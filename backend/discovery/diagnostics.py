"""Conflicts & diagnostics — advisory, non-mutating (06).

Diagnostics explain a result; they NEVER change it. Every number here is a
deterministic function of `(CQS, dataVersion)`. Computing them MUST NOT alter `pins`
(INV-2/INV-6). Resolution lives in re-issue (the FE builds a modified CQS and
re-evaluates); the evaluator never auto-relaxes.

`build` receives `evaluate` as a black box (09) and calls it for `mostRestrictive`
(D5) — it MUST NOT reimplement filtering. `excludedUnknown` (D4) is the one piece that
inspects parcels directly (it must know *which* candidates miss a field, which the
black box cannot reveal); it does so via the same shared `satisfies`/`within_scope`
leaf semantics the evaluator uses, over the same dataVersion snapshot.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import CQS, DroppedInvalid
from backend.discovery.evaluator import OrderedResult
from backend.discovery.predicates import satisfies, within_scope
from backend.discovery.registry import load as load_registry

__all__ = ["Conflict", "DroppedInvalid", "MostRestrictive", "Diagnostics", "build"]

# Missing-value concept applies to scalar attributes only; region membership is a
# computed determination (never a NULL field), so it does not contribute to D4.
_SCALAR_KINDS = {"enum", "range", "flag"}


class Conflict(BaseModel):
    filters: list[str]  # sorted pair of statically-contradictory applied filter ids


class MostRestrictive(BaseModel):
    filterId: str
    countWithoutIt: int


class Diagnostics(BaseModel):
    resultCount: int
    broad: bool
    appliedFilters: int
    conflicts: list[Conflict] = Field(default_factory=list)
    droppedInvalid: list[DroppedInvalid] = Field(default_factory=list)
    excludedUnknown: dict[str, int] = Field(default_factory=dict)
    mostRestrictive: list[MostRestrictive] = Field(default_factory=list)


def _without(cqs: CQS, filter_id: str) -> CQS:
    """CQS with one filter removed (for D5 black-box re-evaluation)."""
    remaining = {k: v for k, v in cqs.filters.items() if k != filter_id}
    return cqs.model_copy(update={"filters": remaining})


def _conflicts(cqs: CQS) -> list[Conflict]:
    """D2 — pairs of applied filters declared contradictory in the static table."""
    registry = load_registry()
    applied = set(cqs.filters)
    pairs: set[frozenset[str]] = set()
    for fid in applied:
        for other in registry.filter_def(fid).contradicts:
            if other in applied:
                pairs.add(frozenset((fid, other)))
    return [Conflict(filters=sorted(p)) for p in sorted(pairs, key=lambda s: sorted(s))]


def _excluded_unknown(cqs: CQS, data_version: str) -> dict[str, int]:
    """D4 — per exclude-policy scalar filter, parcels dropped *solely* for a missing field.

    A parcel counts iff it is within scope, passes every *other* applied predicate, and
    the filter's own field is missing (so `unknownPolicy="exclude"` is the sole reason
    it was dropped). Only entries with a non-zero count are reported (a gap surface).
    """
    registry = load_registry()
    parcels = parcel_mod.default_source.get(data_version)
    scope = cqs.scope

    applied = [
        (fid, a.predicate, registry.filter_def(fid))
        for fid, a in cqs.filters.items()
    ]

    out: dict[str, int] = {}
    for fid, _pred, fdef in applied:
        if fdef.unknownPolicy != "exclude" or fdef.kind not in _SCALAR_KINDS:
            continue
        others = [(p, d.field, d.unknownPolicy) for (oid, p, d) in applied if oid != fid]
        count = 0
        for parcel in parcels:
            if parcel.get(fdef.field) is not None:
                continue  # field present → not a missing-value exclusion
            if not within_scope(parcel, scope):
                continue
            if all(satisfies(p, parcel, fld, pol) for (p, fld, pol) in others):
                count += 1
        if count:
            out[fid] = count
    return out


def _most_restrictive(
    cqs: CQS, data_version: str, evaluate: Callable[[CQS, str], OrderedResult]
) -> list[MostRestrictive]:
    """D5 — zero-result diagnosis. For each applied filter, |evaluate(CQS \\ f)|.

    Sorted by removal-gain descending, ties by filterId ascending. Uses `evaluate` as a
    black box (INV-1) — no special filtering path.
    """
    rows = [
        MostRestrictive(filterId=fid, countWithoutIt=evaluate(_without(cqs, fid), data_version).total)
        for fid in cqs.filters
    ]
    rows.sort(key=lambda r: (-r.countWithoutIt, r.filterId))
    return rows


def build(
    cqs: CQS,
    data_version: str,
    evaluate: Callable[[CQS, str], OrderedResult],
    *,
    result: OrderedResult | None = None,
    dropped: list[DroppedInvalid] | None = None,
) -> Diagnostics:
    """Assemble the advisory diagnostics for an evaluated CQS.

    `result` (the already-computed `OrderedResult`) may be passed to avoid a redundant
    evaluation; otherwise it is computed via the black-box `evaluate`. `dropped` is the
    compiler's invalid/validation drops (produced upstream by the merge, 04/06-D3).
    """
    registry = load_registry()
    if result is None:
        result = evaluate(cqs, data_version)

    applied_count = len(cqs.filters)
    diag = Diagnostics(
        resultCount=result.total,
        broad=applied_count < registry.broadMinFilters,  # D1
        appliedFilters=applied_count,
        conflicts=_conflicts(cqs),  # D2
        droppedInvalid=list(dropped or []),  # D3 (pass-through from merge)
        excludedUnknown=_excluded_unknown(cqs, data_version),  # D4
    )
    if result.total == 0:  # D5 — only when zero results
        diag.mostRestrictive = _most_restrictive(cqs, data_version, evaluate)
    return diag
