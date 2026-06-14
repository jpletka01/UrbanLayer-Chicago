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

    @model_validator(mode="after")
    def _check_enum_values(self) -> "FilterDef":
        if self.kind == "enum":
            if not self.enumValues:
                raise ValueError(f"filter {self.id!r}: enum kind requires non-empty enumValues")
        elif self.enumValues is not None:
            raise ValueError(f"filter {self.id!r}: enumValues only valid for enum kind")
        return self


class TopicDef(BaseModel):
    id: str
    presets: dict[str, dict] = Field(default_factory=dict)  # FilterId -> raw predicate (04)
    defaultSort: SortSpec | None = None


class SortKeyDef(BaseModel):
    key: str
    field: str


class Registry(BaseModel):
    version: str
    filters: list[FilterDef]
    topics: list[TopicDef] = Field(default_factory=list)
    sortKeys: list[SortKeyDef]
    defaultSort: SortSpec
    broadMinFilters: int

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
