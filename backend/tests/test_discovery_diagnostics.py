"""Step 4 tests — advisory diagnostics: broad, conflicts, excludedUnknown, mostRestrictive (06)."""

from __future__ import annotations

import pytest

from backend.discovery import diagnostics as diag
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
from backend.discovery.diagnostics import DroppedInvalid, build
from backend.discovery.evaluator import evaluate
from backend.discovery.parcel import DictParcel

VERSION = "diag-v1"


@pytest.fixture(autouse=True)
def _isolate_snapshot():
    parcel_mod.default_source.clear()
    yield
    parcel_mod.default_source.clear()


def _register(parcels):
    parcel_mod.default_source.register(VERSION, parcels)


def _cqs(filters=None, scope=None) -> CQS:
    return CQS(
        filters=filters or {},
        sort=SortSpec(key="pin", dir="asc"),
        scope=scope or SpatialScope(),
    )


# --- D1 broad + counts ------------------------------------------------------


def test_broad_flag_below_threshold():
    _register([DictParcel("p1", {"in_tif_district": True})])
    cqs = _cqs(filters={"tif": FilterAssignment(predicate=FlagPredicate(value=True))})
    d = build(cqs, VERSION, evaluate)
    assert d.broad is True  # 1 applied < broadMinFilters (2)
    assert d.appliedFilters == 1
    assert d.resultCount == 1


def test_not_broad_at_or_above_threshold():
    _register([DictParcel("p1", {"in_tif_district": True, "is_vacant": True})])
    cqs = _cqs(filters={
        "tif": FilterAssignment(predicate=FlagPredicate(value=True)),
        "vacancy": FilterAssignment(predicate=FlagPredicate(value=True)),
    })
    d = build(cqs, VERSION, evaluate)
    assert d.broad is False
    assert d.appliedFilters == 2


def test_result_count_matches_evaluate():
    _register([DictParcel("p1", {}), DictParcel("p2", {})])
    d = build(_cqs(), VERSION, evaluate)
    assert d.resultCount == evaluate(_cqs(), VERSION).total == 2


# --- D2 conflicts (static table) --------------------------------------------


def test_conflict_reported_when_both_contradictory_filters_applied():
    _register([DictParcel("p1", {"is_vacant": True, "bldg_sqft": 1000})])
    cqs = _cqs(filters={
        "vacancy": FilterAssignment(predicate=FlagPredicate(value=True)),
        "building_size": FilterAssignment(predicate=RangePredicate(min=1)),
    })
    d = build(cqs, VERSION, evaluate)
    assert [c.filters for c in d.conflicts] == [["building_size", "vacancy"]]


def test_no_conflict_when_only_one_side_applied():
    _register([DictParcel("p1", {"is_vacant": True})])
    cqs = _cqs(filters={"vacancy": FilterAssignment(predicate=FlagPredicate(value=True))})
    assert build(cqs, VERSION, evaluate).conflicts == []


# --- D3 droppedInvalid (pass-through from merge) -----------------------------


def test_dropped_invalid_passthrough():
    _register([DictParcel("p1", {})])
    dropped = [DroppedInvalid(filterId="land_use", reason="empty enum")]
    d = build(_cqs(), VERSION, evaluate, dropped=dropped)
    assert d.droppedInvalid == dropped


# --- D4 excludedUnknown -----------------------------------------------------


def test_excluded_unknown_counts_missing_field_after_passing_others():
    _register([
        DictParcel("pA", {"land_use_class": "residential"}),                 # land_sqft missing
        DictParcel("pB", {"land_use_class": "commercial", "land_sqft": 5000}),  # fails land_use
        DictParcel("pC", {"land_use_class": "residential", "land_sqft": 5000}),  # passes both
        DictParcel("pD", {"land_sqft": 5000}),                                # land_use missing
    ])
    cqs = _cqs(filters={
        "land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"])),
        "lot_size": FilterAssignment(predicate=RangePredicate(min=1000)),
    })
    d = build(cqs, VERSION, evaluate)
    assert d.resultCount == 1  # pC only
    # pA dropped solely for missing land_sqft; pD dropped solely for missing land_use
    assert d.excludedUnknown == {"lot_size": 1, "land_use": 1}


def test_excluded_unknown_omits_region_filters():
    # region membership is computed, never a missing scalar → not a D4 contributor.
    _register([DictParcel("p1", regions=set(), lat=41.9, lon=-87.7)])
    cqs = _cqs(filters={"ward": FilterAssignment(predicate=RegionPredicate(regions=["ward:1"]))})
    d = build(cqs, VERSION, evaluate)
    assert d.excludedUnknown == {}


# --- D5 mostRestrictive (zero-result only) ----------------------------------


def test_most_restrictive_absent_when_results_nonempty():
    _register([DictParcel("p1", {"land_use_class": "residential", "land_sqft": 5000})])
    cqs = _cqs(filters={
        "land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"])),
        "lot_size": FilterAssignment(predicate=RangePredicate(min=1000)),
    })
    assert build(cqs, VERSION, evaluate).mostRestrictive == []


def test_most_restrictive_ranks_by_removal_gain_descending():
    _register([
        DictParcel("p1", {"land_use_class": "residential", "land_sqft": 5000}),
        DictParcel("p2", {"land_use_class": "residential", "land_sqft": 6000}),
        DictParcel("p3", {"land_use_class": "commercial", "land_sqft": 7000}),
    ])
    cqs = _cqs(filters={
        "land_use": FilterAssignment(predicate=EnumPredicate(values=["residential"])),
        "lot_size": FilterAssignment(predicate=RangePredicate(min=99999)),  # no parcel qualifies
    })
    d = build(cqs, VERSION, evaluate)
    assert d.resultCount == 0
    rows = [(r.filterId, r.countWithoutIt) for r in d.mostRestrictive]
    # removing lot_size → 2 residential; removing land_use → 0 (none ≥99999)
    assert rows == [("lot_size", 2), ("land_use", 0)]


def test_most_restrictive_ties_broken_by_filter_id_ascending():
    _register([
        DictParcel("q1", {"in_tif_district": True, "is_vacant": False}),
        DictParcel("q2", {"in_tif_district": False, "is_vacant": True}),
    ])
    cqs = _cqs(filters={
        "tif": FilterAssignment(predicate=FlagPredicate(value=True)),
        "vacancy": FilterAssignment(predicate=FlagPredicate(value=True)),
    })
    d = build(cqs, VERSION, evaluate)
    assert d.resultCount == 0
    rows = [(r.filterId, r.countWithoutIt) for r in d.mostRestrictive]
    assert rows == [("tif", 1), ("vacancy", 1)]  # equal gain → filterId ascending


# --- non-mutation (INV-2/INV-6) ---------------------------------------------


def test_building_diagnostics_does_not_change_results():
    _register([
        DictParcel("p1", {"land_sqft": 5000}),
        DictParcel("p2", {"land_sqft": 6000}),
    ])
    cqs = _cqs(filters={"lot_size": FilterAssignment(predicate=RangePredicate(min=1000))})
    before = evaluate(cqs, VERSION).pins
    build(cqs, VERSION, evaluate)
    after = evaluate(cqs, VERSION).pins
    assert before == after
