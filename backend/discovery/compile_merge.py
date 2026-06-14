"""Precedence merge — the ONLY writer of the canonical CQS (04.4, 09).

Combines the compiler fragments into one canonical CQS. Precedence is strict
highest-wins: `user > text > default`. Topic expansion already happened on the
frontend (it rides inside `userFilters`); the merge does NOT re-expand a topic —
`topicId` is inert telemetry in `meta` (R3). That is the cleared-field rule: a field
the user removed is simply absent from the user fragment and cannot reappear.

The merge also performs all compile-time ambiguity resolution (INV-6): it drops
invalid predicates (R1), kind mismatches, and unknown filter ids, and runs static
validations (e.g. `density_band` requires `zoning_group`), recording every drop. The
evaluator then mechanically determines the result; it never resolves conflicts.
"""

from __future__ import annotations

from backend.discovery.cqs import (
    CQS,
    CqsFragment,
    DroppedInvalid,
    EnumPredicate,
    FilterAssignment,
    Predicate,
    QueryMeta,
    RangePredicate,
    RegionPredicate,
    SortSpec,
    SpatialScope,
    predicate_is_valid,
)
from backend.discovery.registry import load as load_registry


def _invalid_reason(p: Predicate) -> str:
    if isinstance(p, EnumPredicate):
        return "empty enum"
    if isinstance(p, RegionPredicate):
        return "empty region"
    if isinstance(p, RangePredicate):
        return "range has no bound"
    return "invalid predicate"


def merge(
    user_frag: CqsFragment,
    text_frag: CqsFragment,
    *,
    sort: SortSpec | None = None,
    scope: SpatialScope | None = None,
    topic_id: str | None = None,
) -> tuple[CQS, list[DroppedInvalid]]:
    """Merge fragments → (canonical CQS, dropped). `sort`/`scope` are the user overrides."""
    registry = load_registry()
    valid_ids = {f.id for f in registry.filters}

    # Precedence: text fills genuinely-absent fields; user overwrites per filter id.
    merged: dict[str, FilterAssignment] = {}
    merged.update(text_frag.filters)
    merged.update(user_frag.filters)

    dropped: list[DroppedInvalid] = []
    kept: dict[str, FilterAssignment] = {}
    for fid, a in merged.items():
        if fid not in valid_ids:
            dropped.append(DroppedInvalid(filterId=fid, reason="unknown filter"))
            continue
        if a.predicate.kind != registry.filter_def(fid).kind:
            dropped.append(DroppedInvalid(filterId=fid, reason="predicate kind mismatch"))
            continue
        if not predicate_is_valid(a.predicate):
            dropped.append(DroppedInvalid(filterId=fid, reason=_invalid_reason(a.predicate)))
            continue
        kept[fid] = a

    # Compile-time validation: a density band is meaningless without a zoning family (03).
    if "density_band" in kept and "zoning_group" not in kept:
        del kept["density_band"]
        dropped.append(
            DroppedInvalid(filterId="density_band", reason="density_band requires a zoning_group filter")
        )

    final_sort = sort or text_frag.sort or registry.defaultSort
    final_scope = scope or SpatialScope(mode="all")
    meta = QueryMeta(
        topicId=topic_id,
        rawText=text_frag.meta.rawText,
        textResidual=text_frag.meta.textResidual,
    )
    return CQS(filters=kept, sort=final_sort, scope=final_scope, meta=meta), dropped
