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


def test_a_predicate_can_include_lots_with_no_data():
    from backend.discovery import parcel as parcel_mod
    from backend.discovery.cqs import CQS, FilterAssignment, RangePredicate, SortSpec
    from backend.discovery.evaluator import evaluate

    parcel_mod.default_source.register("v-unknown", [
        parcel_mod.DictParcel("A", {"land_sqft": 6000.0}),
        parcel_mod.DictParcel("B", {"land_sqft": 2000.0}),
        parcel_mod.DictParcel("C", {}),
    ])

    def run(include):
        cqs = CQS(filters={"lot_size": FilterAssignment(predicate=RangePredicate(min=5000, includeUnknown=include), source="user")},
                  sort=SortSpec(key="pin", dir="asc"))
        return list(evaluate(cqs, "v-unknown").pins)

    assert run(None) == ["A"]
    assert run(True) == ["A", "C"]


def test_distribution_counts_unknowns_apart(monkeypatch):
    from backend.discovery import parcel as parcel_mod

    rows = {"A": parcel_mod.DictParcel("A", {"land_sqft": 3000.0, "is_vacant": True}),
            "B": parcel_mod.DictParcel("B", {"land_sqft": 60000.0}), "C": parcel_mod.DictParcel("C", {})}
    monkeypatch.setattr(discovery_api.parcel_source, "pin_lookup", lambda v: rows)
    discovery_api._distribution.cache_clear()
    d = discovery_api._distribution("v-dist", "lot_size")
    assert d["total"] == 3 and d["unknown"] == 1 and sum(b["n"] for b in d["bins"]) == 2
    assert d["bins"][-1]["n"] == 1  # above the domain lands in the last bin
    v = discovery_api._distribution("v-dist", "vacancy")
    assert v["values"] == {"true": 1} and v["unknown"] == 2


def test_a_complex_is_read_as_one_site(monkeypatch):
    from backend.discovery import index_backfill
    from backend.retrieval.property.commercial_artifact import MultiPinMember

    unit = MultiPinMember(complex_bldg_sqft=10_000.0, unit_pins=("1111111111", "2222222222"), year="2024")
    monkeypatch.setattr("backend.discovery.index_build._commercial_area", lambda pin14: unit)
    a = {"land_sqft": 5_000.0, "density_band": 2.2}
    b = {"land_sqft": 5_000.0, "density_band": 2.2}
    rows = [("11111111110000", 0, 0, a, []), ("22222222220000", 0, 0, b, [])]
    index_backfill.complex_room(rows)
    assert a["room_sqft"] == 12_000.0 and a["room_scope"] == "complex" and a["complex_lots"] == 2
    c = {"density_band": 2.2}  # a member with no land leaves the site unknown
    rows = [("11111111110000", 0, 0, {"land_sqft": 5_000.0, "density_band": 2.2}, []), ("22222222220000", 0, 0, c, [])]
    index_backfill.complex_room(rows)
    assert "room_sqft" not in rows[0][3]


def test_the_grid_gives_a_block_its_lots_median_and_leaves_thin_measures_off():
    from backend.discovery.parcel_tiles import grid_cells

    base = 41.9001, -87.7001
    rows = [(f"{i:010d}0000", base[0], base[1], {"room_sqft": r, "land_sqft": 3125, "land_use_class": "residential"})
            for i, r in enumerate([0, 1000, 3000])]
    rows.append(("99999999990000", base[0], base[1], {"land_sqft": 3125, "land_use_class": "vacant"}))
    rows.append(("99999999991001", base[0], base[1], {"room_sqft": 90000}))  # a condo unit PIN never counts
    (cell,) = grid_cells(rows)
    assert cell.props["n"] == "4"
    assert cell.props["r"] == "1"  # median of bands 0, 1, 2 (3 of 4 known)
    assert cell.props["u"] == "1"  # most lots residential
    assert grid_cells(rows[:2]) == []  # fewer than 3 lots: no cell
    thin = [(f"{i:010d}0000", base[0], base[1], {"land_sqft": 3125} if i else {"room_sqft": 0, "land_sqft": 3125}) for i in range(4)]
    assert "r" not in grid_cells(thin)[0].props  # 1 of 4 known: left off, drawn dotted


def test_a_strip_under_16_ft_is_unusual_and_a_city_lot_is_not():
    from backend.discovery.lot_facts import lot_width_ft

    assert 24 < lot_width_ft(LOT) < 26  # a 25 x 125 ft lot
    strip = box(-87.70, 41.84, -87.70 + 8 * FT_LON, 41.84 + 125 * FT_LAT)
    assert 7 < lot_width_ft(strip) < 9
    a = {"land_sqft": 1000.0, "density_band": 1.2}
    enrich(a, "12345678900000", strip, _sources([]), set())
    assert a["narrow_strip"] is True and a["unusual"] is True
    b = {"land_sqft": 3125.0, "density_band": 1.2, "own_address": True}
    enrich(b, "12345678910000", LOT, _sources([]), set())
    assert "narrow_strip" not in b and b["unusual"] is False


def test_no_base_far_is_named_not_unknown():
    a = {"land_sqft": 9000.0, "bldg_sqft": 2000.0, "zoning_group": "planned_development"}
    derive_capacity(a)
    assert "room_sqft" not in a and a["room_scope"] == "own_rules"
    assert measure_bands(a)["r"] == "x"
    b = {"land_sqft": 9000.0, "zone_class": "POS-1"}
    derive_capacity(b)
    assert b["room_scope"] == "open_space" and measure_bands(b)["r"] == "p"
    c = {"land_sqft": 9000.0}
    derive_capacity(c)
    assert "room_scope" not in c and "r" not in measure_bands(c)


def test_a_city_owned_lot_with_no_footprint_has_no_building():
    import dataclasses

    src = dataclasses.replace(_sources([]), city_land=frozenset({"1234567890"}))
    a = {"land_sqft": 3125.0, "density_band": 1.2}
    enrich(a, "12345678900000", LOT, src, set())
    assert a["bldg_sqft"] == 0.0 and a["bldg_sqft_source"] == "city_land_inventory" and a["room_sqft"] == 3750.0
    b = {"land_sqft": 3125.0, "density_band": 1.2}
    enrich(b, "99999999990000", LOT, src, set())
    assert "bldg_sqft" not in b and b["bldg_sqft_unknown"] == "no_footprint"


def test_neighborhoods_are_places_the_reader_understands_and_a_region_the_index_matches():
    from backend.discovery.compile_text import parse
    from backend.discovery.neighborhoods import names, neighborhood_of
    from backend.discovery.parcel import DictParcel

    assert len(names()) == 98 and names()["wicker_park"] == "Wicker Park"
    assert neighborhood_of(41.9097, -87.6773) == "wicker_park"  # 1601 N Milwaukee Ave
    f = parse("vacant lots in Wicker Park or Bucktown")
    assert f.filters["neighborhood"].predicate.regions == ["hood:wicker_park", "hood:bucktown"]
    assert f.filters["vacancy"] and f.meta.textResidual == []
    assert parse("teardowns in austin").filters["is_teardown_candidate"]
    assert DictParcel("1", {"hood": "wicker_park"}).in_region("hood:wicker_park")
    assert not DictParcel("2", {"hood": "bucktown"}).in_region("hood:wicker_park")


def test_lot_context_gives_the_lot_and_its_neighbors_with_their_room_bands(monkeypatch, tmp_path):
    import sqlite3

    from backend.discovery.parcel import DictParcel

    lat, lon = 41.9100, -87.6800
    parcels = {
        "11111111110000": DictParcel("11111111110000", {"room_sqft": 6000.0}, lat=lat, lon=lon),
        "22222222220000": DictParcel("22222222220000", {"room_sqft": 0.0}, lat=lat, lon=lon + 0.0001),
        "33333333330000": DictParcel("33333333330000", {"room_sqft": 900.0}, lat=lat + 0.01, lon=lon),  # far away
    }
    monkeypatch.setattr(discovery_api.parcel_source, "pin_lookup", lambda v: parcels)
    db_path = tmp_path / "ptaxsim.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE pin_geometry_raw (pin10 TEXT, end_year INT, geometry TEXT)")
    for p, (la, lo) in {"1111111111": (lat, lon), "2222222222": (lat, lon + 0.0001), "3333333333": (lat + 0.01, lon)}.items():
        db.execute("INSERT INTO pin_geometry_raw VALUES (?, 2024, ?)", (p, box(lo, la, lo + 0.00008, la + 0.0003).wkt))
    db.commit()
    db.close()
    monkeypatch.setattr("backend.config.get_settings", lambda: type("S", (), {"ptaxsim_db_path": db_path})())
    discovery_api._pin10_grid.cache_clear()
    discovery_api._lot_context.cache_clear()
    fc = discovery_api._lot_context("v-ctx", "1111111111")
    by = {f["properties"]["pin10"]: f["properties"] for f in fc["features"]}
    assert set(by) == {"1111111111", "2222222222"}
    assert by["1111111111"] == {"pin10": "1111111111", "r": "3", "me": True}
    assert by["2222222222"]["r"] == "0" and by["2222222222"]["me"] is False
