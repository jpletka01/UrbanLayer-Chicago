"""What stands on a Discovery lot, and which lots are offered as empty land (decision Item 110)."""

from __future__ import annotations

import dataclasses

from shapely.geometry import Point, box

from backend.discovery.index_backfill import enrich
from backend.discovery.lot_facts import EMPTY_LAND_KINDS, land_kind, mark_empty_land, structure_on_lot
from backend.tests.test_discovery_lot_facts import FT_LAT, FT_LON, LOT, _sources

PIN10 = "1234567890"
HOUSE = box(-87.70 + 3 * FT_LON, 41.84 + 10 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 70 * FT_LAT)  # ~1,140 sq ft
GARAGE = box(-87.70 + 3 * FT_LON, 41.84 + 100 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 120 * FT_LAT)  # ~380 sq ft
ON_LOT = Point(-87.70 + 12 * FT_LON, 41.84 + 60 * FT_LAT)


def _src(footprints=(), points=(), lidar=None, city=()):
    s = _sources(footprints, points)
    return dataclasses.replace(s, lidar_on_lot=lidar, city_land=frozenset(city))


def test_land_kinds():
    assert land_kind("1-00", False) == "vacant"
    assert land_kind("EX", True) == "city_owned"
    assert land_kind("5-90", False) == "parking" and land_kind("5-80", False) == "parking"
    assert land_kind("2-41", False) == "side_yard"
    assert land_kind("2-11", False) == "residential"
    assert land_kind("5-17", False) == "commercial"
    assert land_kind("RR", False) == "railroad"
    assert EMPTY_LAND_KINDS == {"vacant", "city_owned", "parking", "exempt"}


def test_two_sources_decide_what_stands_on_the_lot():
    assert structure_on_lot(LOT, PIN10, "vacant", _src(lidar={})) == "empty"
    assert structure_on_lot(LOT, PIN10, "vacant", _src([(HOUSE, 2)], lidar={PIN10: (1140.0, 1140.0)})) == "built"
    assert structure_on_lot(LOT, PIN10, "vacant", _src([(GARAGE, 1)], lidar={PIN10: (380.0, 380.0)})) == "accessory"
    assert structure_on_lot(LOT, PIN10, "vacant", _src([], lidar={PIN10: (1140.0, 1140.0)})) == "disagree"
    assert structure_on_lot(LOT, PIN10, "vacant", _src()) is None  # a copy without the LiDAR table


def test_a_demolition_permit_outdates_the_city_footprint_only_where_the_tax_class_allows():
    pts = [("demolition_history", "2015-04-02", ON_LOT)]
    src = _src([(HOUSE, 2)], pts, lidar={})
    assert structure_on_lot(LOT, PIN10, "vacant", src) == "empty"
    # A lot taxed as a house: it was likely rebuilt (the owner's check found two such lots), so no override.
    assert structure_on_lot(LOT, PIN10, "residential", src) == "disagree"


def test_demolished_after_the_flight_and_new_construction():
    src = _src([(HOUSE, 2)], [("demolition_history", "2024-03-01", ON_LOT)], lidar={PIN10: (1140.0, 1140.0)})
    assert structure_on_lot(LOT, PIN10, "vacant", src) == "demolished_since_2022"
    src = _src([], [("new_construction", "2025-05-05", ON_LOT)], lidar={})
    assert structure_on_lot(LOT, PIN10, "city_owned", src) == "new_construction"


def test_empty_land_only_on_the_four_kinds_and_the_old_assessor_area_is_set_aside():
    src = _src(lidar={})
    a = {"class": "1-00", "bldg_sqft": 10059.0, "bldg_sqft_source": "assessor"}
    mark_empty_land(a, LOT, PIN10, src)
    assert a["empty_land"] is True and a["land_kind"] == "vacant" and a["structure"] == "empty"
    assert a["bldg_sqft"] == 0.0 and a["bldg_sqft_source"] == "empty_lot" and a["bldg_sqft_assessor_old"] == 10059.0
    mark_empty_land(a, LOT, PIN10, _src([(HOUSE, 2)], lidar={PIN10: (1140.0, 1140.0)}))  # a rerun, now built
    assert "empty_land" not in a and a["structure"] == "built"
    assert a["bldg_sqft"] == 10059.0 and a["bldg_sqft_source"] == "assessor" and "bldg_sqft_assessor_old" not in a
    g = {"class": "EX"}
    mark_empty_land(g, LOT, PIN10, _src([(GARAGE, 1)], lidar={PIN10: (380.0, 380.0)}))
    assert g["structure"] == "accessory" and g["empty_land"] is True  # a garage or shed alone counts (owner, 2026-11-11)
    o = {"class": "1-00", "bldg_sqft": 2400.0}  # an index built before Item 104: no source named yet
    mark_empty_land(o, LOT, PIN10, src)
    assert o["bldg_sqft"] == 0.0 and o["bldg_sqft_source"] == "empty_lot" and o["bldg_sqft_assessor_old"] == 2400.0
    r = {"class": "2-11"}
    mark_empty_land(r, LOT, PIN10, src)
    assert r["structure"] == "empty" and "empty_land" not in r  # residential class: never offered


def test_enrich_marks_empty_land_and_room_to_build_reads_the_empty_lot():
    a = {"class": "1-00", "is_vacant": True, "land_sqft": 3125.0, "density_band": 1.2, "bldg_sqft": 2000.0,
         "bldg_sqft_source": "assessor"}
    enrich(a, PIN10 + "0000", LOT, _src(lidar={}), set())
    assert a["empty_land"] is True and a["room_sqft"] == 3750.0
    u = {"class": "1-00", "is_vacant": True, "land_sqft": 3125.0, "density_band": 1.2}
    enrich(u, PIN10 + "1001", LOT, _src(lidar={}), set())  # a unit PIN: no land facts of its own
    assert "empty_land" not in u and "land_kind" not in u
