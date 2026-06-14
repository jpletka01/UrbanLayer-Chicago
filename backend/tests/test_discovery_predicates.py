"""Step 2 tests — satisfies() per kind incl. unknownPolicy + inverted range, within_scope (03/05)."""

from __future__ import annotations

from backend.discovery.cqs import (
    EnumPredicate,
    FlagPredicate,
    RangePredicate,
    RegionPredicate,
    SpatialScope,
)
from backend.discovery.parcel import DictParcel
from backend.discovery.predicates import satisfies, within_scope


# --- enum -------------------------------------------------------------------


def test_enum_hit_and_miss():
    p = DictParcel("1", {"land_use_class": "residential"})
    assert satisfies(EnumPredicate(values=["residential"]), p, "land_use_class", "exclude")
    assert not satisfies(EnumPredicate(values=["commercial"]), p, "land_use_class", "exclude")


def test_enum_or_within_values():
    p = DictParcel("1", {"land_use_class": "commercial"})
    assert satisfies(EnumPredicate(values=["residential", "commercial"]), p, "land_use_class", "exclude")


def test_enum_missing_follows_unknown_policy():
    p = DictParcel("1", {})  # field absent
    assert not satisfies(EnumPredicate(values=["residential"]), p, "land_use_class", "exclude")
    assert satisfies(EnumPredicate(values=["residential"]), p, "land_use_class", "include")


# --- range ------------------------------------------------------------------


def test_range_min_only_max_only_both():
    p = DictParcel("1", {"land_sqft": 5000})
    assert satisfies(RangePredicate(min=2500), p, "land_sqft", "exclude")
    assert satisfies(RangePredicate(max=10000), p, "land_sqft", "exclude")
    assert satisfies(RangePredicate(min=2500, max=10000), p, "land_sqft", "exclude")
    assert not satisfies(RangePredicate(min=6000), p, "land_sqft", "exclude")
    assert not satisfies(RangePredicate(max=4000), p, "land_sqft", "exclude")


def test_range_bounds_are_inclusive():
    p = DictParcel("1", {"land_sqft": 5000})
    assert satisfies(RangePredicate(min=5000, max=5000), p, "land_sqft", "exclude")


def test_range_missing_follows_unknown_policy():
    p = DictParcel("1", {})
    assert not satisfies(RangePredicate(min=2500), p, "land_sqft", "exclude")
    assert satisfies(RangePredicate(min=2500), p, "land_sqft", "include")


def test_inverted_range_present_value_never_matches():
    p = DictParcel("1", {"land_sqft": 5000})
    assert not satisfies(RangePredicate(min=500, max=100), p, "land_sqft", "exclude")
    assert not satisfies(RangePredicate(min=500, max=100), p, "land_sqft", "include")


def test_inverted_range_missing_follows_unknown_policy():
    p = DictParcel("1", {})
    assert not satisfies(RangePredicate(min=500, max=100), p, "land_sqft", "exclude")
    assert satisfies(RangePredicate(min=500, max=100), p, "land_sqft", "include")


# --- flag (decision 1: present→polarity; missing→unknownPolicy) --------------


def test_flag_present_true_matches_value_true():
    p = DictParcel("1", {"in_tif_district": True})
    assert satisfies(FlagPredicate(value=True), p, "in_tif_district", "exclude")
    assert not satisfies(FlagPredicate(value=False), p, "in_tif_district", "exclude")


def test_flag_present_false_matches_value_false():
    p = DictParcel("1", {"in_tif_district": False})
    assert satisfies(FlagPredicate(value=False), p, "in_tif_district", "exclude")
    assert not satisfies(FlagPredicate(value=True), p, "in_tif_district", "exclude")


def test_flag_missing_follows_unknown_policy_both_polarities():
    p = DictParcel("1", {})
    assert not satisfies(FlagPredicate(value=True), p, "in_tif_district", "exclude")
    assert not satisfies(FlagPredicate(value=False), p, "in_tif_district", "exclude")
    assert satisfies(FlagPredicate(value=True), p, "in_tif_district", "include")
    assert satisfies(FlagPredicate(value=False), p, "in_tif_district", "include")


# --- region -----------------------------------------------------------------


def test_region_membership_or_within():
    p = DictParcel("1", regions={"ward:1"})
    assert satisfies(RegionPredicate(regions=["ward:1"]), p, "ward", "exclude")
    assert satisfies(RegionPredicate(regions=["ward:2", "ward:1"]), p, "ward", "exclude")
    assert not satisfies(RegionPredicate(regions=["ward:9"]), p, "ward", "exclude")


def test_region_no_membership_is_dropped():
    p = DictParcel("1", regions=set())
    assert not satisfies(RegionPredicate(regions=["ward:1"]), p, "ward", "exclude")


# --- within_scope -----------------------------------------------------------


def test_scope_all_always_true():
    p = DictParcel("1", lat=41.9, lon=-87.7)
    assert within_scope(p, SpatialScope(mode="all"))


def test_scope_viewport_in_and_out_of_bbox():
    inside = DictParcel("1", lat=41.9, lon=-87.7)
    outside = DictParcel("2", lat=42.5, lon=-87.7)
    bbox = (-87.8, 41.8, -87.6, 42.0)  # [minLon, minLat, maxLon, maxLat]
    assert within_scope(inside, SpatialScope(mode="viewport", bbox=bbox))
    assert not within_scope(outside, SpatialScope(mode="viewport", bbox=bbox))


def test_scope_viewport_missing_latlon_excluded():
    p = DictParcel("1")  # no lat/lon
    assert not within_scope(p, SpatialScope(mode="viewport", bbox=(-87.8, 41.8, -87.6, 42.0)))


def test_scope_region_in_and_out():
    p = DictParcel("1", regions={"neighborhood:logan_square"})
    assert within_scope(p, SpatialScope(mode="region", regions=["neighborhood:logan_square"]))
    assert not within_scope(p, SpatialScope(mode="region", regions=["neighborhood:loop"]))
