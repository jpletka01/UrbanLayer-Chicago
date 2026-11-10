"""Building area fallbacks, room to build, card warnings and the tiles' measure bands (decision Item 104)."""

from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Point, box
from shapely.strtree import STRtree

from backend.discovery import api as discovery_api
from backend.discovery.index_backfill import enrich
from backend.discovery.lot_facts import (
    LotSources, derive_capacity, fill_building_area, footprint_area, lot_warnings, measure_bands,
)
from backend.discovery.lot_sources import SQFT_PER_SQDEG, area_sqft

# A 25 x 125 ft city lot near 41.84 N, in degrees.
FT_LAT = 1 / 364_600
FT_LON = 1 / 271_700
LOT = box(-87.70, 41.84, -87.70 + 25 * FT_LON, 41.84 + 125 * FT_LAT)


def _sources(footprints=(), points=(), areas=()):
    geoms = np.array([g for g, _ in footprints], dtype=object)
    reps = shapely.point_on_surface(geoms) if len(geoms) else np.array([], dtype=object)
    by_kind: dict[str, tuple[list, list]] = {}
    for kind, date, g in points:
        gs, ds = by_kind.setdefault(kind, ([], []))
        gs.append(g)
        ds.append(date)
    return LotSources(
        fp_tree=STRtree(reps), fp_geoms=geoms, fp_points=reps,
        fp_stories=[s for _, s in footprints], fp_area=[area_sqft(g) for g, _ in footprints],
        pt_tree={k: (STRtree(g), d) for k, (g, d) in by_kind.items()},
        area_tree=(STRtree([g for _, g in areas]), [n for n, _ in areas]) if areas else None, meta={},
    )


def test_lot_is_a_city_lot():
    assert 3_000 < area_sqft(LOT) < 3_250
    assert SQFT_PER_SQDEG > 1e10


def test_footprints_inside_the_lot_sum_area_times_stories():
    house = box(-87.70 + 3 * FT_LON, 41.84 + 10 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 70 * FT_LAT)
    garage = box(-87.70 + 3 * FT_LON, 41.84 + 100 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 120 * FT_LAT)
    neighbor = shapely.affinity.translate(house, xoff=30 * FT_LON)
    src = _sources([(house, 3), (garage, 1), (neighbor, 2)])
    sqft, why = footprint_area(LOT, area_sqft(LOT), src)
    assert why == "footprint"
    assert abs(sqft - (19 * 60 * 3 + 19 * 20)) < 30


def test_a_footprint_without_stories_withholds_the_area():
    house = box(-87.70 + 3 * FT_LON, 41.84 + 10 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 70 * FT_LAT)
    assert footprint_area(LOT, 3_125, _sources([(house, None)])) == (None, "stories_missing")


def test_a_footprint_larger_than_the_lot_spans_several_lots():
    big = LOT.buffer(20 * FT_LON)
    assert footprint_area(LOT, area_sqft(LOT), _sources([(big, 4)])) == (None, "spans_lots")


def test_no_footprint_is_unknown_not_zero():
    assert footprint_area(LOT, 3_125, _sources([])) == (None, "no_footprint")


def test_the_assessor_wins_then_commercial_then_footprints():
    from backend.retrieval.property.commercial_artifact import UnitArea

    a = {"bldg_sqft": 2_400.0}
    fill_building_area(a)
    assert a["bldg_sqft_source"] == "assessor"
    a = {}
    fill_building_area(a, commercial=UnitArea(9_000.0, ("x",), "2024"))
    assert a == {"bldg_sqft": 9_000.0, "bldg_sqft_source": "commercial_valuation"}
    a = {"is_vacant": True}
    fill_building_area(a, lot=LOT, src=_sources([]))
    assert "bldg_sqft" not in a


def test_room_to_build_needs_every_input_and_never_goes_below_zero():
    a = {"density_band": 1.2, "land_sqft": 3_125.0, "bldg_sqft": 2_000.0}
    derive_capacity(a)
    assert a["room_sqft"] == 1_750.0
    a = {"density_band": 1.2, "land_sqft": 3_125.0, "bldg_sqft": 9_000.0}
    derive_capacity(a)
    assert a["room_sqft"] == 0.0
    a = {"density_band": 1.2, "land_sqft": 3_125.0, "is_vacant": True}
    derive_capacity(a)
    assert a["room_sqft"] == 3_750.0
    a = {"density_band": 1.2, "land_sqft": 3_125.0}
    derive_capacity(a)
    assert "room_sqft" not in a


def test_warnings_from_points_on_the_lot_and_landmark_areas():
    mid = shapely.point_on_surface(LOT)
    elsewhere = Point(-87.60, 41.90)
    src = _sources(points=[("demolition", "2025-06-01", mid), ("vacant_case", "2024-01-02", elsewhere)],
                   areas=[("Wicker Park District", LOT.buffer(0.001))])
    w = lot_warnings(LOT, src, {"1234567890"}, "1234567890")
    assert w == {"warn_demolition": "2025-06-01", "warn_pending_rezoning": True,
                 "warn_landmark": "Wicker Park District"}


def test_a_condo_unit_pin_gets_warnings_but_no_building_area():
    house = box(-87.70 + 3 * FT_LON, 41.84 + 10 * FT_LAT, -87.70 + 22 * FT_LON, 41.84 + 70 * FT_LAT)
    src = _sources([(house, 3)])
    unit = {"land_sqft": 3_125.0, "density_band": 1.2}
    enrich(unit, "12345678901001", LOT, src, {"1234567890"})
    assert unit.get("warn_pending_rezoning") is True and "bldg_sqft" not in unit and "room_sqft" not in unit
    base = {"land_sqft": 3_125.0, "density_band": 1.2}
    enrich(base, "99999999990000", LOT, src, set())
    assert base["bldg_sqft_source"] == "footprint" and 300 < base["room_sqft"] < 350  # 3,750 allowed - 3,420 built


def test_measure_bands():
    assert measure_bands({"room_sqft": 0, "land_sqft": 3_125, "sale_recency_days": 400,
                          "land_use_class": "residential"}) == {"r": "0", "s": "1", "y": "1", "u": "1"}
    assert measure_bands({"room_sqft": 12_000, "land_sqft": 50_000, "class": "EX"}) == {"r": "4", "s": "4", "u": "5"}
    assert measure_bands({}) == {}


def test_one_warning_per_card_in_the_owners_order():
    attrs = {"warn_landmark": "X", "warn_vacant_case": "2024-05-01"}
    assert discovery_api._warning(attrs.get, True) == {"kind": "vacant_case", "detail": "2024-05-01"}
    assert discovery_api._warning({}.get, True) == {"kind": "nominal", "detail": None}
    assert discovery_api._warning({"warn_pending_rezoning": True}.get, False) == {
        "kind": "pending_rezoning", "detail": None}


def test_area_outlines_cover_the_city():
    import json as _json

    fc = _json.loads(discovery_api._areas_geojson())
    assert len(fc["features"]) == 77
    assert {"ca", "name", "lx", "ly"} <= set(fc["features"][0]["properties"])


def test_community_area_comes_from_the_region_handle():
    from backend.discovery.parcel import DictParcel

    assert discovery_api._community_area_of(DictParcel("1", {}, regions=["neighborhood:24"])) == 24
    assert discovery_api._community_area_of(DictParcel("2", {})) is None
