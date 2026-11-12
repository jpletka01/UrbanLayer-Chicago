"""Land in use on a Discovery lot (decision Item 112): surface parking and road right-of-way."""

from __future__ import annotations

import dataclasses
import json
import sqlite3

import pytest
import shapely
from shapely.geometry import box

from backend.discovery import cmap_land_use, lot_sources
from backend.discovery.index_build import unusual_rule
from backend.discovery.lot_facts import LotSources, mark_land_use
from backend.tests.test_discovery_lot_facts import _sources

PIN10 = "1234567890"


def _src(cmap=None):
    return dataclasses.replace(_sources([], []), cmap_on_lot=cmap)


@pytest.mark.parametrize("attrs, parking", [
    ({"land_kind": "parking", "structure": "empty"}, True),
    ({"land_kind": "parking", "structure": "accessory"}, True),  # a garage or shed only
    ({"land_kind": "parking", "structure": "built"}, False),
    ({"land_kind": "parking", "structure": "disagree"}, False),
    ({"land_kind": "parking", "structure": "demolished_since_2022"}, False),  # not measured
    ({"land_kind": "vacant", "structure": "empty"}, False),  # OSM / CMAP parking is not used (Item 112)
    ({"land_kind": "city_owned", "structure": "empty"}, False),
    ({"land_kind": "parking"}, False),  # no structure table
])
def test_surface_parking_is_the_assessor_class_with_no_building(attrs, parking):
    mark_land_use(attrs, PIN10, _src())
    assert bool(attrs.get("surface_parking")) is parking
    assert attrs.get("surface_parking_source") == ("assessor_class" if parking else None)


@pytest.mark.parametrize("attrs, cmap, road", [
    ({"land_kind": "exempt", "empty_land": True}, ("1512", 0.9), True),
    ({"land_kind": "exempt", "empty_land": True}, ("1512", 0.5), True),
    ({"land_kind": "exempt", "empty_land": True}, ("1512", 0.49), False),  # under half the lot
    ({"land_kind": "exempt", "empty_land": True}, ("3100", 0.9), False),  # a park: 2 of 6, not used
    ({"land_kind": "exempt", "empty_land": True}, ("1511", 0.9), False),  # rail: not measured
    ({"land_kind": "exempt"}, ("1512", 0.9), False),  # something stands on it
    ({"land_kind": "vacant", "empty_land": True}, ("1512", 0.9), False),  # only exempt land was measured
    ({"land_kind": "exempt", "empty_land": True}, None, False),
])
def test_road_land_is_cmap_road_on_empty_exempt_land(attrs, cmap, road):
    mark_land_use(attrs, PIN10, _src({PIN10: cmap} if cmap else {}))
    assert (attrs.get("infrastructure") == "road") is road
    assert attrs.get("infrastructure_source") == ("cmap_2023" if road else None)


def test_a_copy_without_the_table_marks_no_road_and_a_rerun_clears():
    attrs = {"land_kind": "exempt", "empty_land": True}
    mark_land_use(attrs, PIN10, _src(None))
    assert "infrastructure" not in attrs
    attrs = {"land_kind": "parking", "structure": "built", "surface_parking": True, "infrastructure": "road"}
    mark_land_use(attrs, PIN10, _src({}))
    assert "surface_parking" not in attrs and "infrastructure" not in attrs


def test_road_land_is_hidden_by_default():
    assert unusual_rule({"infrastructure": "road", "land_kind": "exempt"}) is True
    assert unusual_rule({"land_kind": "exempt", "surface_parking": True}) is False


def _minimal_sources(path, with_cmap: bool):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE footprints (bldg_id TEXT, stories INTEGER, area_sqft REAL, wkb BLOB);
        CREATE TABLE points (kind TEXT, ref TEXT, date TEXT, lat REAL, lon REAL);
        CREATE TABLE areas (kind TEXT, name TEXT, wkb BLOB);
        CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT);
    """)
    if with_cmap:
        db.executescript(lot_sources.LAND_USE_TABLES)
        db.execute("INSERT INTO cmap_on_lot VALUES (?, ?, ?)", (PIN10, "1512", 0.97))
    db.commit()
    db.close()


def test_lot_sources_load_reads_the_table_or_none(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    _minimal_sources(a, True)
    _minimal_sources(b, False)
    assert LotSources.load(a).cmap_on_lot == {PIN10: ("1512", 0.97)}
    assert LotSources.load(b).cmap_on_lot is None


def _cmap_copy(path, polys):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE lui (oid INTEGER PRIMARY KEY, landuse TEXT, landuse2 TEXT, modifier TEXT, os_mgmt TEXT, "
               "wkb BLOB)")
    db.executemany("INSERT INTO lui VALUES (?, ?, NULL, NULL, NULL, ?)",
                   [(i, code, shapely.to_wkb(g)) for i, (code, g) in enumerate(polys)])
    db.execute("CREATE TABLE meta (value TEXT)")
    db.execute("INSERT INTO meta VALUES (?)", (json.dumps({"vintage": "2023 test", "fetched": "2026-11-12"}),))
    db.commit()
    db.close()


def _ptaxsim(path, lots):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE pin_geometry_raw (pin10 TEXT, start_year INTEGER, end_year INTEGER, longitude REAL, "
               "latitude REAL, geometry TEXT)")
    for pin10, g in lots:
        c = g.centroid
        db.execute("INSERT INTO pin_geometry_raw VALUES (?, 2020, 2024, ?, ?, ?)", (pin10, c.x, c.y, g.wkt))
    db.commit()
    db.close()


def test_codes_on_lots_takes_the_code_covering_most_of_the_lot(tmp_path):
    x, y, d = -87.70, 41.84, 0.0002
    lot_a = box(x, y, x + d, y + d)  # 3/4 road, 1/4 park
    lot_b = box(x + 0.01, y, x + 0.01 + d, y + d)  # wholly inside a residential polygon
    _cmap_copy(tmp_path / "cmap.db", [
        ("1512", box(x - 1e-3, y - 1e-3, x + 0.75 * d, y + 1e-3)),
        ("3100", box(x + 0.75 * d, y - 1e-3, x + 2e-3, y + 1e-3)),
        ("1111", box(x + 0.009, y - 1e-3, x + 0.012, y + 1e-3)),
    ])
    _ptaxsim(tmp_path / "ptaxsim.db", [("1111111111", lot_a), ("2222222222", lot_b)])
    got = {p: (c, s) for p, c, s in cmap_land_use.codes_on_lots(tmp_path / "cmap.db", tmp_path / "ptaxsim.db")}
    assert got["1111111111"][0] == "1512" and got["1111111111"][1] == pytest.approx(0.75, abs=0.01)
    assert got["2222222222"] == ("1111", 1.0)


def test_a_short_land_use_table_is_refused(tmp_path):
    _cmap_copy(tmp_path / "cmap.db", [])
    db = sqlite3.connect(":memory:")
    with pytest.raises(RuntimeError, match="refusing"):
        lot_sources._write_land_use(db, [(PIN10, "1512", 1.0)], tmp_path / "cmap.db")
