"""Per-kind predicate matching + spatial scope — the leaf semantics (03, 05).

`satisfies` is the ONLY place missing values are interpreted, and it does so solely
via `unknown_policy` (no other missing-value branching, 05). The doc-09 shorthand
`satisfies(pred, parcel, unknownPolicy)` omits the attribute name; it is structurally
required for enum/range/flag, so `field` is an explicit parameter here (the `region`
kind ignores it and resolves membership via `Parcel.in_region`).
"""

from __future__ import annotations

from typing import Literal

from backend.discovery.cqs import (
    EnumPredicate,
    FlagPredicate,
    Predicate,
    RangePredicate,
    RegionPredicate,
    SpatialScope,
)
from backend.discovery.parcel import Parcel

UnknownPolicy = Literal["exclude", "include"]


def satisfies(
    predicate: Predicate,
    parcel: Parcel,
    field: str,
    unknown_policy: UnknownPolicy,
) -> bool:
    """Whether `parcel` satisfies `predicate` (03 semantics table).

    enum:   p.field ∈ values (OR within)
    range:  min ≤ p.field ≤ max for whichever bounds are present (inclusive); an
            inverted range (min>max) is never satisfied by a present value (R6).
    flag:   present field → truthy == value; missing field → `unknown_policy`.
    region: p lies in any of `regions` (OR); membership encodes its own missing-as-false.

    For enum/range/flag a missing field is resolved deterministically by
    `unknown_policy` ("include" → kept, "exclude" → dropped) — the only branch on
    missingness.
    """
    if isinstance(predicate, RegionPredicate):
        return any(parcel.in_region(r) for r in predicate.regions)

    value = parcel.get(field)

    if isinstance(predicate, FlagPredicate):
        if value is None:
            return unknown_policy == "include"
        return bool(value) == predicate.value

    if value is None:
        return unknown_policy == "include"

    if isinstance(predicate, EnumPredicate):
        return value in predicate.values

    if isinstance(predicate, RangePredicate):
        if predicate.min is not None and value < predicate.min:
            return False
        if predicate.max is not None and value > predicate.max:
            return False
        return True

    return False


def within_scope(parcel: Parcel, scope: SpatialScope) -> bool:
    """Whether `parcel` is inside the spatial scope. `mode="all"` adds no constraint.

    A `viewport`/`region` scope ANDs with any Location region *filter* — scope never
    overrides a filter (05); that conjunction is enforced in the evaluator.
    """
    if scope.mode == "all":
        return True
    if scope.mode == "viewport":
        if scope.bbox is None or parcel.lat is None or parcel.lon is None:
            return False
        min_lon, min_lat, max_lon, max_lat = scope.bbox
        return min_lon <= parcel.lon <= max_lon and min_lat <= parcel.lat <= max_lat
    if scope.mode == "region":
        return any(parcel.in_region(r) for r in (scope.regions or []))
    return True
