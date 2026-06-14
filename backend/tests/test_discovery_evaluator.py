"""Step 3 tests — the single evaluator: filter + sort + determinism (05, INV-1..3)."""

from __future__ import annotations

import pytest

from backend.discovery import parcel as parcel_mod
from backend.discovery.cqs import (
    CQS,
    EnumPredicate,
    FilterAssignment,
    FlagPredicate,
    RangePredicate,
    RegionPredicate,
    SortSpec,
    SpatialScope,
)
from backend.discovery.evaluator import evaluate
from backend.discovery.parcel import DictParcel

VERSION = "test-v1"


@pytest.fixture(autouse=True)
def _isolate_snapshot():
    """Each test owns the default snapshot source under a fixed test version."""
    parcel_mod.default_source.clear()
    yield
    parcel_mod.default_source.clear()


def _register(parcels):
    parcel_mod.default_source.register(VERSION, parcels)


def _cqs(filters=None, sort=None, scope=None) -> CQS:
    return CQS(
        filters=filters or {},
        sort=sort or SortSpec(key="pin", dir="asc"),
        scope=scope or SpatialScope(),
    )


# --- filtering --------------------------------------------------------------


def test_no_filters_returns_all_pin_sorted():
    _register([
        DictParcel("00-00-000-000-0003", {}),
        DictParcel("00-00-000-000-0001", {}),
        DictParcel("00-00-000-000-0002", {}),
    ])
    res = evaluate(_cqs(), VERSION)
    assert res.total == 3
    assert res.pins == [
        "00-00-000-000-0001",
        "00-00-000-000-0002",
        "00-00-000-000-0003",
    ]


def test_and_across_filters():
    _register([
        DictParcel("p1", {"land_use_class": "residential", "in_tif_district": True}),
        DictParcel("p2", {"land_use_class": "residential", "in_tif_district": False}),
        DictParcel("p3", {"land_use_class": "commercial", "in_tif_district": True}),
    ])
    cqs = _cqs(filters={
        "land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"])),
        "tif": FilterAssignment(predicate=FlagPredicate(value=True)),
    })
    assert evaluate(cqs, VERSION).pins == ["p1"]


def test_or_within_enum():
    _register([
        DictParcel("p1", {"land_use_class": "residential"}),
        DictParcel("p2", {"land_use_class": "commercial"}),
        DictParcel("p3", {"land_use_class": "industrial"}),
    ])
    cqs = _cqs(filters={
        "land_use": FilterAssignment(predicate=EnumPredicate(values=["residential", "commercial"])),
    })
    assert evaluate(cqs, VERSION).pins == ["p1", "p2"]


def test_unsatisfiable_conjunction_is_empty():
    _register([DictParcel("p1", {"land_sqft": 5000})])
    cqs = _cqs(filters={
        "lot_size": FilterAssignment(predicate=RangePredicate(min=9000, max=1000)),  # inverted
    })
    res = evaluate(cqs, VERSION)
    assert res.pins == []
    assert res.total == 0


# --- determinism (INV-2) ----------------------------------------------------


def test_repeat_calls_are_byte_identical():
    _register([
        DictParcel("p3", {"land_sqft": 4000}),
        DictParcel("p1", {"land_sqft": 4000}),
        DictParcel("p2", {"land_sqft": 9000}),
    ])
    cqs = _cqs(sort=SortSpec(key="lot_size", dir="asc"))
    first = evaluate(cqs, VERSION).pins
    second = evaluate(cqs, VERSION).pins
    assert first == second


# --- sorting + total order --------------------------------------------------


def test_sort_with_pin_tiebreak_on_equal_keys():
    _register([
        DictParcel("p3", {"land_sqft": 4000}),
        DictParcel("p1", {"land_sqft": 4000}),
        DictParcel("p2", {"land_sqft": 4000}),
    ])
    cqs = _cqs(sort=SortSpec(key="lot_size", dir="asc"))
    # all keys equal → ascending PIN order
    assert evaluate(cqs, VERSION).pins == ["p1", "p2", "p3"]


def test_descending_sort_keeps_pin_tiebreak_ascending():
    _register([
        DictParcel("p1", {"land_sqft": 4000}),
        DictParcel("p2", {"land_sqft": 4000}),
        DictParcel("p3", {"land_sqft": 9000}),
    ])
    cqs = _cqs(sort=SortSpec(key="lot_size", dir="desc"))
    # 9000 first; the two 4000s tie → PIN ascending (p1 before p2), NOT reversed
    assert evaluate(cqs, VERSION).pins == ["p3", "p1", "p2"]


def test_missing_sort_field_sorts_last_then_pin():
    _register([
        DictParcel("p2", {}),                  # missing
        DictParcel("p1", {}),                  # missing
        DictParcel("p3", {"land_sqft": 5000}),  # present
    ])
    cqs = _cqs(sort=SortSpec(key="lot_size", dir="asc"))
    assert evaluate(cqs, VERSION).pins == ["p3", "p1", "p2"]


def test_missing_sorts_last_in_descending_too():
    _register([
        DictParcel("p2", {}),
        DictParcel("p3", {"land_sqft": 5000}),
    ])
    cqs = _cqs(sort=SortSpec(key="lot_size", dir="desc"))
    assert evaluate(cqs, VERSION).pins == ["p3", "p2"]


def test_no_duplicate_pins_total_order():
    _register([DictParcel(f"p{i}", {"land_sqft": 1000}) for i in range(10)])
    pins = evaluate(_cqs(sort=SortSpec(key="lot_size", dir="asc")), VERSION).pins
    assert len(pins) == len(set(pins)) == 10


# --- scope (05) -------------------------------------------------------------


def test_scope_all_adds_no_constraint():
    _register([DictParcel("p1", lat=41.9, lon=-87.7), DictParcel("p2", lat=42.9, lon=-87.7)])
    assert evaluate(_cqs(scope=SpatialScope(mode="all")), VERSION).total == 2


def test_viewport_scope_ands():
    _register([
        DictParcel("p1", lat=41.9, lon=-87.7),
        DictParcel("p2", lat=42.9, lon=-87.7),  # outside bbox
    ])
    cqs = _cqs(scope=SpatialScope(mode="viewport", bbox=(-87.8, 41.8, -87.6, 42.0)))
    assert evaluate(cqs, VERSION).pins == ["p1"]


def test_region_filter_and_viewport_scope_both_apply():
    # In-ward but outside viewport → dropped (scope ANDs with the Location filter, 05).
    _register([
        DictParcel("p1", regions={"ward:1"}, lat=41.9, lon=-87.7),  # in ward AND in bbox
        DictParcel("p2", regions={"ward:1"}, lat=42.9, lon=-87.7),  # in ward, OUT of bbox
        DictParcel("p3", regions={"ward:2"}, lat=41.9, lon=-87.7),  # in bbox, wrong ward
    ])
    cqs = _cqs(
        filters={"ward": FilterAssignment(predicate=RegionPredicate(regions=["ward:1"]))},
        scope=SpatialScope(mode="viewport", bbox=(-87.8, 41.8, -87.6, 42.0)),
    )
    assert evaluate(cqs, VERSION).pins == ["p1"]


def test_unknown_data_version_raises():
    with pytest.raises(KeyError):
        evaluate(_cqs(), "no-such-version")
