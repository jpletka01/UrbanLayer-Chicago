"""Canonical Query State (CQS) — the single contract the evaluator reads.

Mirrors `claude-context/property-discovery/02-cqs-schema.md`. The CQS is the only
object that crosses the FE/BE boundary with semantic authority and the only input
`evaluator.evaluate` reads. Two CQS are *equal* iff their `filters` (by predicate
value), `sort`, and `scope` are equal — `meta` and every `source` tag are excluded
(canonical form). Determinism (INV-2) is defined over this equality.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

# --- Predicates (discriminated union on `kind`) -----------------------------

Source = Literal["user", "text", "topic", "default"]


class EnumPredicate(BaseModel):
    kind: Literal["enum"] = "enum"
    values: list[str] = Field(default_factory=list)  # OR within; non-empty when valid


class RangePredicate(BaseModel):
    kind: Literal["range"] = "range"
    min: float | None = None  # inclusive
    max: float | None = None  # inclusive; min>max is valid-but-unsatisfiable (R6)


class FlagPredicate(BaseModel):
    kind: Literal["flag"] = "flag"
    value: bool  # true = must have; false = must not have


class RegionPredicate(BaseModel):
    kind: Literal["region"] = "region"
    regions: list[str] = Field(default_factory=list)  # OR within; non-empty when valid


Predicate = Annotated[
    Union[EnumPredicate, RangePredicate, FlagPredicate, RegionPredicate],
    Field(discriminator="kind"),
]


class FilterAssignment(BaseModel):
    predicate: Predicate
    # provenance; consumed at compile-time precedence (04), invisible to evaluate() (R4)
    source: Source = "user"


class SortSpec(BaseModel):
    key: str
    dir: Literal["asc", "desc"] = "asc"


class SpatialScope(BaseModel):
    mode: Literal["all", "viewport", "region"] = "all"
    bbox: tuple[float, float, float, float] | None = None  # [minLon,minLat,maxLon,maxLat]
    regions: list[str] | None = None


class QueryMeta(BaseModel):
    """Advisory only — the evaluator MUST NOT read this (R3)."""

    topicId: str | None = None
    rawText: str | None = None
    textResidual: list[str] = Field(default_factory=list)


class CQS(BaseModel):
    filters: dict[str, FilterAssignment] = Field(default_factory=dict)
    sort: SortSpec  # ALWAYS present (R5); default comes from the registry
    scope: SpatialScope = Field(default_factory=SpatialScope)
    meta: QueryMeta = Field(default_factory=QueryMeta)


class CqsFragment(BaseModel):
    """A compiler output (04): a partial filters map + optional sort/scope/meta.

    Each assignment carries its `source`. Fragments are merged into the canonical
    CQS by the precedence merge (06). `sort`/`scope` are absent unless the compiler
    sets them.
    """

    filters: dict[str, FilterAssignment] = Field(default_factory=dict)
    sort: SortSpec | None = None
    scope: SpatialScope | None = None
    meta: QueryMeta = Field(default_factory=QueryMeta)


# --- Predicate validity (R1/R6) ---------------------------------------------


def predicate_is_valid(p: Predicate) -> bool:
    """A predicate is INVALID iff it can never be a meaningful constraint (R1).

    Empty enum/region ⇒ invalid (must not mean "match nothing"). A range with no
    bound ⇒ invalid. An *inverted* range (min>max) is VALID — it is honestly
    unsatisfiable, not malformed (R6).
    """
    if isinstance(p, EnumPredicate):
        return len(p.values) > 0
    if isinstance(p, RegionPredicate):
        return len(p.regions) > 0
    if isinstance(p, RangePredicate):
        return p.min is not None or p.max is not None
    if isinstance(p, FlagPredicate):
        return True
    return False


# --- Canonical form + equality (02 canonical form) --------------------------


def _predicate_canonical(p: Predicate) -> dict:
    """Predicate value with OR-sets normalized (order-insensitive) for stable keys."""
    d = p.model_dump()
    if isinstance(p, EnumPredicate):
        d["values"] = sorted(p.values)
    elif isinstance(p, RegionPredicate):
        d["regions"] = sorted(p.regions)
    return d


def _scope_canonical(s: SpatialScope) -> dict:
    d = s.model_dump()
    if s.regions is not None:
        d["regions"] = sorted(s.regions)
    if s.bbox is not None:
        d["bbox"] = list(s.bbox)
    return d


def canonical_form(cqs: CQS) -> dict:
    """The equality-bearing projection: filters (by predicate value), sort, scope.

    `meta` and every `source` tag are excluded (R3/R4). Used for equality and for
    response caching keyed on canonical CQS + dataVersion.
    """
    return {
        "filters": {fid: _predicate_canonical(a.predicate) for fid, a in cqs.filters.items()},
        "sort": cqs.sort.model_dump(),
        "scope": _scope_canonical(cqs.scope),
    }


def canonical_key(cqs: CQS) -> str:
    """Deterministic, byte-stable serialization (sorted keys) of the canonical form."""
    return json.dumps(canonical_form(cqs), sort_keys=True, separators=(",", ":"))


def cqs_equal(a: CQS, b: CQS) -> bool:
    return canonical_key(a) == canonical_key(b)
