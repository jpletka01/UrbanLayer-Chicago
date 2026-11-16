"""Rail land on a Discovery lot and rail on the base map (decision Item 128)."""

from __future__ import annotations

import dataclasses
import json
import sqlite3

import pytest
import shapely
from shapely.geometry import LineString, box

from backend.discovery import lot_sources
from backend.discovery.index_build import unusual_rule
from backend.discovery.lot_facts import (
    LAND_IN_USE, LotSources, derive_capacity, land_in_use, mark_land_use, measure_bands,
)
from backend.map_tiles import base_tiles, rail_lines
from backend.tests.test_discovery_lot_facts import _sources

PIN10 = "1418500008"


def _src(cmap=None, rail=None):
    return dataclasses.replace(_sources([], []), cmap_on_lot=cmap, rail_on_lot=rail)


# --- the rule ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("attrs, cmap, want", [
    # CMAP rail over half the lot, whatever stands on it: 33 of 34 in the owner's blind check.
    ({"land_kind": "exempt", "empty_land": True, "structure": "empty"}, ("1511", 0.95), "rail"),
    ({"land_kind": "exempt", "structure": "disagree"}, ("1511", 0.9), "rail"),  # the L structure in the LiDAR
    ({"land_kind": "exempt", "structure": "built"}, ("1511", 0.97), "rail"),  # a building under the tracks
    ({"land_kind": "commercial", "structure": "accessory"}, ("1511", 1.0), "rail"),
    ({"land_kind": "vacant", "empty_land": True}, ("1511", 0.5), "rail"),
    ({"land_kind": "exempt", "empty_land": True}, ("1511", 0.49), None),  # under half the lot
    ({"land_kind": "railroad", "structure": "empty"}, ("1511", 0.98), None),  # RR class: hidden and named already
])
def test_rail_land_is_cmap_rail_over_half_the_lot(attrs, cmap, want):
    mark_land_use(attrs, PIN10, _src({PIN10: cmap}))
    assert attrs.get("infrastructure") == want
    assert attrs.get("infrastructure_source") == ("cmap_2023" if want else None)


def test_a_line_alone_never_marks_a_lot():
    # the CTA line alone was right on 3 of 8 lots, the federal line on 2 of 5
    attrs = {"land_kind": "exempt", "empty_land": True, "structure": "empty"}
    mark_land_use(attrs, PIN10, _src({PIN10: ("4110", 0.9)}, {PIN10: 400.0}))
    assert "infrastructure" not in attrs


@pytest.mark.parametrize("cta_ft, want, source", [
    (132.0, "road_rail", "cmap_2023+cta"),  # 6 of 6 were "rail and highway"
    (25.0, "road_rail", "cmap_2023+cta"),
    (24.9, "road", "cmap_2023"),  # a line clipping a corner
    (None, "road", "cmap_2023"),
])
def test_road_land_the_l_crosses_is_road_and_rail(cta_ft, want, source):
    attrs = {"land_kind": "exempt", "empty_land": True, "structure": "empty"}
    mark_land_use(attrs, PIN10, _src({PIN10: ("1512", 0.9)}, {PIN10: cta_ft} if cta_ft else {}))
    assert attrs["infrastructure"] == want and attrs["infrastructure_source"] == source


def test_a_copy_without_the_rail_table_still_marks_road():
    attrs = {"land_kind": "exempt", "empty_land": True}
    mark_land_use(attrs, PIN10, _src({PIN10: ("1512", 0.9)}, None))
    assert attrs["infrastructure"] == "road"


def test_parking_under_the_tracks_is_rail_land():
    attrs = {"land_kind": "parking", "structure": "empty", "empty_land": True}
    mark_land_use(attrs, PIN10, _src({PIN10: ("1511", 0.9)}))
    assert attrs["infrastructure"] == "rail"
    assert "surface_parking" not in attrs and "surface_parking_source" not in attrs


@pytest.mark.parametrize("kind", ["rail", "road", "road_rail"])
def test_right_of_way_is_hidden_never_has_room_and_reads_as_road_or_rail(kind):
    attrs = {"infrastructure": kind, "land_kind": "exempt", "density_band": 3.0, "land_sqft": 10_000.0,
             "bldg_sqft": 0.0, "room_sqft": 30_000.0}
    derive_capacity(attrs)
    assert "room_sqft" not in attrs and attrs["room_scope"] == "right_of_way"
    assert unusual_rule(attrs) is True
    assert land_in_use(attrs) == "road_rail"
    bands = measure_bands(attrs)
    assert bands["r"] == "t" and bands["l"] == str(LAND_IN_USE.index("road_rail"))


def test_a_rerun_after_the_rail_mark_is_dropped_gives_room_back():
    attrs = {"infrastructure": "rail", "density_band": 2.0, "land_sqft": 5_000.0, "bldg_sqft": 0.0}
    derive_capacity(attrs)
    attrs.pop("infrastructure")
    derive_capacity(attrs)
    assert attrs["room_sqft"] == 10_000.0 and "room_scope" not in attrs


# --- the lot table -----------------------------------------------------------------------------------------------

def _minimal(path, rail_rows=None):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE footprints (bldg_id TEXT, stories INTEGER, area_sqft REAL, wkb BLOB NOT NULL);
        CREATE TABLE points (kind TEXT NOT NULL, ref TEXT, date TEXT, lat REAL NOT NULL, lon REAL NOT NULL);
        CREATE TABLE areas (kind TEXT NOT NULL, name TEXT, wkb BLOB NOT NULL);
        CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT);
    """)
    if rail_rows is not None:
        db.executescript(lot_sources.RAIL_TABLES)
        db.executemany("INSERT INTO rail_on_lot VALUES (?, ?)", rail_rows)
    db.commit()
    db.close()


def test_lot_sources_load_reads_the_rail_table_or_none(tmp_path):
    _minimal(tmp_path / "a.db", [(PIN10, 120.5)])
    _minimal(tmp_path / "b.db")
    assert LotSources.load(tmp_path / "a.db").rail_on_lot == {PIN10: 120.5}
    assert LotSources.load(tmp_path / "b.db").rail_on_lot is None


def test_a_short_rail_table_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(lot_sources, "MIN_CMAP_LOTS", 1)
    db = sqlite3.connect(tmp_path / "x.db")
    cmap = tmp_path / "cmap.db"
    c = sqlite3.connect(cmap)
    c.execute("CREATE TABLE meta (value TEXT)")
    c.execute("INSERT INTO meta VALUES (?)", (json.dumps({"vintage": "2023"}),))
    c.commit()
    c.close()
    with pytest.raises(RuntimeError, match="CTA lines crossed only"):
        lot_sources._write_land_use(db, [(PIN10, "1511", 1.0)], cmap, [(PIN10, 50.0)])


# --- the rail lines ----------------------------------------------------------------------------------------------

def _rail_folder(tmp_path):
    (tmp_path / rail_lines.CTA_FILE).write_text(json.dumps([
        {"the_geom": {"type": "MultiLineString", "coordinates": [[[-87.6905, 41.96], [-87.6895, 41.96]]]},
         "type": "Elevated or At Grade", "lines": "Brown, Purple (Exp)"},
        {"the_geom": {"type": "LineString", "coordinates": [[-87.63, 41.88], [-87.63, 41.89]]},
         "type": "Subway", "lines": "Red Line"},
    ]))
    line = {"type": "LineString", "coordinates": [[-87.70, 41.80], [-87.70, 41.81]]}
    feats = [
        {"type": "Feature", "geometry": line, "properties": p} for p in (
            {"NET": "M", "RROWNER1": "NIRC"}, {"NET": "M", "RROWNER1": "UP", "TRKRGHTS1": "METX"},
            {"NET": "M", "RROWNER1": "BNSF", "TRKRGHTS1": "AMTK", "PASSNGR": "A"}, {"NET": "M", "RROWNER1": "CSXT"},
            {"NET": "Y", "RROWNER1": "NS"}, {"NET": "I", "RROWNER1": "IHB"}, {"NET": "X", "RROWNER1": "CPKC"},
            {"NET": "A"}, {"NET": "T", "RROWNER1": "XXXX"})]
    (tmp_path / rail_lines.NARN_FILE).write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return tmp_path


def test_rail_kinds_from_the_federal_network_and_the_cta(tmp_path):
    lines = rail_lines.load(_rail_folder(tmp_path))
    assert [k for k, _g, _p in lines] == ["cta", "cta_subway", "metra", "metra", "amtrak", "freight", "yard", "spur"]
    assert lines[0][2]["name"] == "Brown, Purple (Express)"


def test_cta_feet_inside_each_lot(tmp_path):
    folder = _rail_folder(tmp_path)
    under = box(-87.6902, 41.9599, -87.6898, 41.9601)  # the line runs through it
    beside = box(-87.6902, 41.9603, -87.6898, 41.9606)  # next to the tracks
    got = dict(rail_lines.cta_on_lots(folder, ["a", "b"], [under, beside]))
    assert set(got) == {"a"}
    assert got["a"] == pytest.approx(0.0004 * rail_lines._FT_PER_DEG_LON, rel=0.01)  # about 109 ft


def test_rail_fetch_refuses_a_short_read(tmp_path, monkeypatch):
    class R:
        def __init__(self, body):
            self.body = body
            self.status_code = 200

        def json(self):
            return self.body

        def raise_for_status(self):
            return None

    monkeypatch.setattr(rail_lines, "_get", lambda client, url, params: R([{"the_geom": None}] * 3))
    with pytest.raises(RuntimeError, match="CTA lines: only 3"):
        rail_lines.fetch(tmp_path)
    assert not (tmp_path / rail_lines.CTA_FILE).exists()


def test_base_tiles_cut_rail_to_the_city_and_set_zooms(tmp_path):
    lines = rail_lines.load(_rail_folder(tmp_path))
    city = box(-87.95, 41.64, -87.52, 42.03)
    feats, outside = base_tiles.rail_features(lines, city)
    kinds = [f.props["kind"] for f in feats]
    assert "cta_subway" not in kinds and kinds.count("metra") == 2
    zoom = {f.props["kind"]: f.minzoom for f in feats}
    assert zoom["cta"] == 10 and zoom["yard"] == 13 and zoom["spur"] == 14
    assert outside == 0
    # a line wholly outside the City is left out; one crossing its edge is cut at it
    small = box(-87.6900, 41.95, -87.60, 41.97)
    feats, outside = base_tiles.rail_features(lines, small)
    assert [f.props["kind"] for f in feats] == ["cta"] and outside == 6
    assert feats[0].props["name"] == "Brown, Purple (Express)"
    whole = shapely.length(LineString([(-87.6905, 41.96), (-87.6895, 41.96)]))
    assert feats[0].geom is not None and whole > 0
