"""Filter registry — the single, versioned, static artifact (03).

Authored once as `registry.json`, validated at load, read-only thereafter (09). One
source ⇒ no FE/BE drift on predicate kinds, topic definitions, or `unknownPolicy`.
Adding a filter is a registry-version bump + new `FilterDef` — never an evaluator
code change.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.discovery.cqs import SortSpec

log = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).with_name("registry.json")

FilterCategory = Literal[
    "location", "property_use", "zoning_dev", "incentives", "financial", "condition_risk"
]
PredicateKind = Literal["enum", "range", "flag", "region"]
UnknownPolicy = Literal["exclude", "include"]
# How a range control is presented (drives FE formatting + adornments, not evaluation).
RangeDisplay = Literal["number", "usd", "percent", "far", "mi", "score", "count", "year"]
# Which bounds a range control exposes ("within X" = max only; "≥ X" = min only).
BoundMode = Literal["min", "max", "both"]


class RangePreset(BaseModel):
    """A one-tap bound preset (e.g. "Bottom 25%" → {max: 25})."""

    label: str
    min: float | None = None
    max: float | None = None


class RangeMeta(BaseModel):
    """Display/control metadata for a range filter (PR2). Pure presentation — the
    evaluator never reads it; it bounds + shapes the FE control."""

    domain: tuple[float, float]  # [lo, hi] slider/preset bounds
    step: float
    boundMode: BoundMode
    display: RangeDisplay
    presets: list[RangePreset] | None = None


class FilterDef(BaseModel):
    id: str
    category: FilterCategory
    kind: PredicateKind
    field: str
    # REQUIRED — behavior when the parcel attribute is missing/NULL (03).
    unknownPolicy: UnknownPolicy
    enumValues: list[str] | None = None  # required iff kind == "enum"
    unit: str | None = None  # display only, for range filters
    contradicts: list[str] = Field(default_factory=list)  # static contradiction table (06)
    # --- PR2 display + control metadata (presentation only; never read by the evaluator) ---
    range: RangeMeta | None = None  # control metadata, range kind only
    requires: list[str] = Field(default_factory=list)  # filter ids that must co-occur (FE-declared)
    label: str | None = None  # hand-authored display label — kills humanize() on the FE
    help: str | None = None  # one-line tooltip copy
    enumLabels: dict[str, str] | None = None  # enum value -> display label (enum only)

    @model_validator(mode="after")
    def _check_fields(self) -> "FilterDef":
        if self.kind == "enum":
            if not self.enumValues:
                raise ValueError(f"filter {self.id!r}: enum kind requires non-empty enumValues")
            if self.enumLabels:
                unknown = set(self.enumLabels) - set(self.enumValues)
                if unknown:
                    raise ValueError(f"filter {self.id!r}: enumLabels for non-values {sorted(unknown)}")
        else:
            if self.enumValues is not None:
                raise ValueError(f"filter {self.id!r}: enumValues only valid for enum kind")
            if self.enumLabels is not None:
                raise ValueError(f"filter {self.id!r}: enumLabels only valid for enum kind")
        if self.kind != "range" and self.range is not None:
            raise ValueError(f"filter {self.id!r}: range metadata only valid for range kind")
        return self


class TopicDef(BaseModel):
    id: str
    label: str | None = None  # recipe-shelf title (PR2)
    description: str | None = None  # one-line recipe description (PR2)
    presets: dict[str, dict] = Field(default_factory=dict)  # FilterId -> raw predicate (04)
    defaultSort: SortSpec | None = None


class SortKeyDef(BaseModel):
    key: str
    field: str


class Coverage(BaseModel):
    """What geography the current index covers (PR4). Presentation only — it drives a
    standalone scope banner and is NEVER part of the CQS / chip array.

    `mode` "none" is the safe default (no index built → page reads dormant); "partial"
    = a subset of community areas; "all" = the full city.
    """

    mode: Literal["none", "partial", "all"] = "none"
    liveAreas: list[int] = Field(default_factory=list)  # community-area ids that are indexed
    asOf: str | None = None  # ISO date the index was built


class Registry(BaseModel):
    version: str
    filters: list[FilterDef]
    topics: list[TopicDef] = Field(default_factory=list)
    sortKeys: list[SortKeyDef]
    defaultSort: SortSpec
    broadMinFilters: int
    # --- PR4 dynamic, index-derived fields (injected by the /registry endpoint, not the
    # static artifact). Defaults = dormant: no coverage, nothing populated. ---
    coverage: Coverage = Field(default_factory=Coverage)
    populatedFields: list[str] = Field(default_factory=list)  # filter ids with real data

    @model_validator(mode="after")
    def _check_integrity(self) -> "Registry":
        ids = [f.id for f in self.filters]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate filter ids: {dupes}")
        id_set = set(ids)
        for f in self.filters:
            for c in f.contradicts:
                if c not in id_set:
                    raise ValueError(f"filter {f.id!r}: contradicts unknown filter {c!r}")
            for r in f.requires:
                if r not in id_set:
                    raise ValueError(f"filter {f.id!r}: requires unknown filter {r!r}")

        keys = [sk.key for sk in self.sortKeys]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate sort keys")
        sort_keys = set(keys)
        if self.defaultSort.key not in sort_keys:
            raise ValueError(f"defaultSort.key {self.defaultSort.key!r} not in sortKeys")

        for t in self.topics:
            for fid in t.presets:
                if fid not in id_set:
                    raise ValueError(f"topic {t.id!r}: preset references unknown filter {fid!r}")
            if t.defaultSort and t.defaultSort.key not in sort_keys:
                raise ValueError(f"topic {t.id!r}: defaultSort.key {t.defaultSort.key!r} not in sortKeys")
        return self

    # --- typed accessors -----------------------------------------------------

    def filter_def(self, filter_id: str) -> FilterDef:
        for f in self.filters:
            if f.id == filter_id:
                return f
        raise KeyError(filter_id)

    def sortable_keys(self) -> set[str]:
        return {sk.key for sk in self.sortKeys}

    def sort_field(self, key: str) -> str:
        for sk in self.sortKeys:
            if sk.key == key:
                return sk.field
        raise KeyError(key)


@lru_cache(maxsize=1)
def load() -> Registry:
    """Load + validate the static registry artifact. Raises on a bad artifact."""
    raw = json.loads(_REGISTRY_PATH.read_text())
    return Registry.model_validate(raw)
