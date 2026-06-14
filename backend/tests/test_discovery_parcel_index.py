"""Index tests — IndexedParcel semantics + SQLite round-trip."""

from __future__ import annotations

import time

from backend.discovery.parcel_index import IndexedParcel, read_index, write_index


def test_get_returns_attr_or_none():
    p = IndexedParcel("p1", 41.9, -87.7, {"land_sqft": 5000}, [])
    assert p.get("land_sqft") == 5000
    assert p.get("missing") is None


def test_in_region_static_membership():
    p = IndexedParcel("p1", 41.9, -87.7, {}, ["neighborhood:24", "ward:1"])
    assert p.in_region("neighborhood:24")
    assert not p.in_region("neighborhood:32")


def test_in_region_radius_haversine():
    # ~0 mi from itself; a point ~3 mi away is outside a 1 mi radius, inside a 5 mi radius.
    p = IndexedParcel("p1", 41.9000, -87.7000, {}, [])
    assert p.in_region("radius:41.9000,-87.7000,1")          # same point
    assert not p.in_region("radius:41.9500,-87.7000,1")      # ~3.1 mi north → outside 1mi
    assert p.in_region("radius:41.9500,-87.7000,5")          # inside 5mi


def test_in_region_radius_missing_latlon_is_false():
    p = IndexedParcel("p1", None, None, {}, [])
    assert not p.in_region("radius:41.9,-87.7,5")


def test_in_region_malformed_radius_is_false():
    p = IndexedParcel("p1", 41.9, -87.7, {}, [])
    assert not p.in_region("radius:not,a,number")


def test_write_then_read_round_trip(tmp_path):
    path = tmp_path / "idx.db"
    rows = [
        ("p1", 41.9, -87.7, {"land_sqft": 5000, "in_tif_district": True, "skip": None}, ["neighborhood:24"]),
        ("p2", 41.8, -87.6, {"land_use_class": "residential"}, ["neighborhood:24", "ward:1"]),
    ]
    total = write_index(path, data_version="idx-test-1", built_at=int(time.time()),
                        community_areas=[24], rows=rows)
    assert total == 2

    version, parcels = read_index(path)
    assert version == "idx-test-1"
    by_pin = {p.pin: p for p in parcels}
    assert by_pin["p1"].get("land_sqft") == 5000
    assert by_pin["p1"].get("in_tif_district") is True
    assert by_pin["p1"].get("skip") is None  # None attrs are not stored
    assert by_pin["p2"].in_region("ward:1")


def test_upsert_is_incremental_by_pin(tmp_path):
    path = tmp_path / "idx.db"
    write_index(path, data_version="v1", built_at=1, community_areas=[24],
                rows=[("p1", 1.0, 2.0, {"land_sqft": 100}, [])])
    total = write_index(path, data_version="v2", built_at=2, community_areas=[24, 25],
                        rows=[("p1", 1.0, 2.0, {"land_sqft": 999}, []), ("p2", 3.0, 4.0, {}, [])])
    assert total == 2
    version, parcels = read_index(path)
    assert version == "v2"
    assert {p.pin for p in parcels} == {"p1", "p2"}
    assert next(p for p in parcels if p.pin == "p1").get("land_sqft") == 999  # replaced


def test_read_missing_index_returns_empty(tmp_path):
    version, parcels = read_index(tmp_path / "nope.db")
    assert version is None
    assert parcels == []
