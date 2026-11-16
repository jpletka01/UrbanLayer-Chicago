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
    ({"land_kind": "exempt", "empty_land": True}, ("1570", 0.9), "rail"),  # an intermodal yard (owner's look)
    ({"land_kind": "exempt", "empty_land": True}, ("1520", 0.9), None),  # "other linear": an active line in 17% only
])
def test_rail_land_is_cmap_rail_or_yard_over_half_the_lot(attrs, cmap, want):
    mark_land_use(attrs, PIN10, _src({PIN10: cmap}))
    assert attrs.get("infrastructure") == want
    assert attrs.get("infrastructure_source") == ("cmap_2023" if want else None)


@pytest.mark.parametrize("cmap", [("1511", 0.98), ("4140", 0.9), ("1520", 0.9), None])
def test_the_assessors_railroad_class_is_rail_land_whatever_cmap_says(cmap):
    # Fuller Park's yard (owner's look): RR lots read "unknown", and a built one showed room to build
    attrs = {"land_kind": "railroad", "structure": "built", "density_band": 2.0, "land_sqft": 5_000.0, "bldg_sqft": 0.0}
    mark_land_use(attrs, PIN10, _src({PIN10: cmap} if cmap else {}))
    assert attrs["infrastructure"] == "rail" and attrs["infrastructure_source"] == "assessor_class"
    derive_capacity(attrs)
    assert "room_sqft" not in attrs and attrs["room_scope"] == "right_of_way"
    assert measure_bands(attrs)["r"] == "t"


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
    attrs = {"infrastructure": kind, "land_kind": "exempt", "empty_land": True, "density_band": 3.0, "land_sqft": 10_000.0,
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
    assert "cta_subway" in kinds and kinds.count("metra") == 2  # the subway is drawn too (owner: the Blue Line "just stopped")
    zoom = {f.props["kind"]: f.minzoom for f in feats}
    assert zoom["cta"] == 10 and zoom["yard"] == 13 and zoom["spur"] == 14
    assert outside == 0
    # a line wholly outside the City is left out; one crossing its edge is cut at it
    small = box(-87.6900, 41.95, -87.60, 41.97)
    feats, outside = base_tiles.rail_features(lines, small)
    assert [f.props["kind"] for f in feats] == ["cta"] and outside == 7
    assert feats[0].props["name"] == "Brown, Purple (Express)"
    whole = shapely.length(LineString([(-87.6905, 41.96), (-87.6895, 41.96)]))
    assert feats[0].geom is not None and whole > 0


# --- parks, cemeteries and water (the owner's map review, 2026-11-16) ---------------------------------------------

def _open(park=0.0, water=0.0, cmap=None):
    return dataclasses.replace(_sources([], []), cmap_on_lot={PIN10: cmap} if cmap else {},
                               open_land_on_lot={PIN10: (park, water)})


@pytest.mark.parametrize("attrs, src, want", [
    ({"land_kind": "city_owned", "structure": "built"}, _open(park=0.999), ("park", "park_district")),  # 7059 S South Shore
    ({"land_kind": "exempt"}, _open(cmap=("1360", 0.998)), ("cemetery", "cmap_2023")),  # Graceland
    ({"land_kind": "commercial"}, _open(cmap=("1360", 0.99)), ("cemetery", "cmap_2023")),  # Rosehill, taxed
    ({"land_kind": "exempt"}, _open(water=0.84, cmap=("5000", 0.99)), ("water", "city_water")),  # North Branch bed
    ({"land_kind": "exempt"}, _open(cmap=("5000", 0.9)), ("water", "cmap_2023")),
    ({"land_kind": "exempt"}, _open(park=0.9, water=0.6), ("water", "city_water")),  # a lagoon inside a park
    ({"land_kind": "residential"}, _open(park=0.72), None),  # a home inside a park's outline stays a home
    ({"land_kind": "exempt"}, _open(park=0.49), None),
])
def test_open_land(attrs, src, want):
    mark_land_use(attrs, PIN10, src)
    assert (attrs.get("open_land"), attrs.get("open_land_source")) == (want or (None, None))


def test_rail_wins_over_open_land_and_open_land_over_road():
    attrs = {"land_kind": "railroad"}
    mark_land_use(attrs, PIN10, _open(park=0.9))
    assert attrs["infrastructure"] == "rail" and "open_land" not in attrs
    attrs = {"land_kind": "exempt", "empty_land": True}
    mark_land_use(attrs, PIN10, _open(water=0.7, cmap=("1512", 0.9)))
    assert attrs["open_land"] == "water" and "infrastructure" not in attrs


@pytest.mark.parametrize("kind, scope, band, use", [("park", "open_space", "p", "park"),
                                                     ("cemetery", "open_space", "p", "park"),
                                                     ("water", "water", "w", "water")])
def test_open_land_has_no_room_is_hidden_and_draws_as_itself(kind, scope, band, use):
    attrs = {"open_land": kind, "density_band": 2.0, "land_sqft": 9_000.0, "bldg_sqft": 0.0, "empty_land": True}
    derive_capacity(attrs)
    assert "room_sqft" not in attrs and attrs["room_scope"] == scope
    assert unusual_rule(attrs) is True
    b = measure_bands(attrs)
    assert b["r"] == band and b["l"] == str(LAND_IN_USE.index(use))


def test_open_land_table_is_read_or_none(tmp_path):
    _minimal(tmp_path / "a.db")
    db = sqlite3.connect(tmp_path / "a.db")
    db.executescript(lot_sources.OPEN_LAND_TABLES)
    db.execute("INSERT INTO open_land_on_lot VALUES (?, ?, ?)", (PIN10, 0.95, 0.0))
    db.commit()
    db.close()
    _minimal(tmp_path / "b.db")
    assert LotSources.load(tmp_path / "a.db").open_land_on_lot == {PIN10: (0.95, 0.0)}
    assert LotSources.load(tmp_path / "b.db").open_land_on_lot is None


def test_open_land_shares_from_the_base_maps_copies(tmp_path):
    from backend.discovery import open_land

    sq = lambda x0, y0, x1, y1: {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}  # noqa: E731
    (tmp_path / open_land.PARKS_FILE).write_text(json.dumps([{"the_geom": sq(0, 0, 10, 10)}]))
    (tmp_path / open_land.WATER_FILE).write_text(json.dumps([{"the_geom": sq(10, 0, 20, 10)}]))
    lots = [box(1, 1, 3, 3), box(9, 1, 11, 3), box(30, 30, 31, 31)]
    got = {p: (pk, w) for p, pk, w in open_land.open_land_on_lots(tmp_path, ["in_park", "edge", "away"], lots)}
    assert got == {"in_park": (1.0, 0.0), "edge": (0.5, 0.5)}


def test_base_tiles_carry_the_l_line_rail_land_and_stations(tmp_path):
    lines = rail_lines.load(_rail_folder(tmp_path))
    feats, _ = base_tiles.rail_features(lines, box(-87.95, 41.64, -87.52, 42.03))
    assert feats[0].props["line"] == "" and feats[0].props["kind"] == "cta"  # the fixture has no legend
    st = base_tiles.station_features([
        {"name": "Western", "lat": 41.966, "lon": -87.688, "type": "cta_rail", "lines": ["Brown Line"]},
        {"name": "Ravenswood", "lat": 41.968, "lon": -87.674, "type": "metra", "lines": ["UP-N"]},
        {"name": "Bus", "lat": 41.9, "lon": -87.6, "type": "bus"}, {"name": "No point", "type": "metra"}])
    assert [(f.props["kind"], f.props["name"], f.props["lines"]) for f in st] == [
        ("cta", "Western", "Brown Line"), ("metra", "Ravenswood", "UP-N")]
    assert {f.minzoom for f in st} == {12}
    cmap = tmp_path / "cmap.db"
    db = sqlite3.connect(cmap)
    db.execute("CREATE TABLE lui (oid INTEGER PRIMARY KEY, landuse TEXT, landuse2 TEXT, modifier TEXT, os_mgmt TEXT, wkb BLOB)")
    for code, g in (("1511", box(-87.70, 41.90, -87.69, 41.91)), ("1570", box(-87.65, 41.80, -87.64, 41.81)),
                    ("1111", box(-87.60, 41.80, -87.59, 41.81)), ("1511", box(-88.5, 41.0, -88.4, 41.1))):
        db.execute("INSERT INTO lui (landuse, wkb) VALUES (?, ?)", (code, shapely.to_wkb(g)))
    db.commit()
    db.close()
    land = base_tiles.rail_land_features(cmap, box(-87.95, 41.64, -87.52, 42.03))
    assert sorted(f.props["kind"] for f in land) == ["row", "yard"]  # homes and the polygon outside the City left out


def test_islands_in_the_citys_hydro_layer_are_land():
    # display 2 = islands in lagoons (Wooded Island in Jackson Park drew as water: owner's map review)
    assert base_tiles.is_island({"display": "2"}) and base_tiles.is_island({"display": 2})
    assert not any(base_tiles.is_island({"display": d}) for d in ("0", "1", "4", None))
    rows = {"city": [], "park": [], "road": [], "water": [
        {"the_geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, "display": "0"},
        {"the_geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, "display": "2"}]}
    feats, left_out = base_tiles.build_features(rows)
    assert sum(f.layer == "water" for f in feats) == 1 and left_out["water_islands"] == 1


def test_shared_l_track_splits_into_one_line_per_color_side_by_side(tmp_path):
    folder = _rail_folder(tmp_path)  # one segment carries "Brown, Purple (Exp)"
    per = [p for k, _g, p in rail_lines.load(folder, per_line=True) if k == "cta"]
    assert [(p["line"], p["o"]) for p in per] == [("BR", "-0.5"), ("PR", "0.5")]
    assert [p["line"] for k, _g, p in rail_lines.load(folder) if k == "cta"] == [""]  # the lot measure: one track
    assert rail_lines.cta_lines_of("Brown, Green, Orange, Pink, Purple (Exp)") == ["BR", "GR", "OR", "PK", "PR"]
    assert rail_lines.cta_lines_of("Red Line") == ["RD"]


def test_metra_from_its_gtfs_replaces_the_federal_commuter_segments(tmp_path):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("routes.txt", "route_id, route_long_name, route_color\n" + "".join(
            f"R{i}, Line {i}, 29C233\n" for i in range(8)))
        z.writestr("trips.txt", "route_id,shape_id\n" + "".join(f"R{i},S{i}\n" for i in range(8)))
        z.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n" + "".join(
            f"S{i},41.8{i},-87.7,1\nS{i},41.8{i},-87.69,2\n" for i in range(8)))
    fc = rail_lines.metra_from_gtfs(buf.getvalue())
    assert len(fc["features"]) == 8 and fc["features"][0]["properties"]["color"] == "#29C233"
    folder = _rail_folder(tmp_path)
    (folder / rail_lines.METRA_FILE).write_text(json.dumps(fc))
    kinds = [(k, p.get("line")) for k, _g, p in rail_lines.load(folder, per_line=True) if k == "metra"]
    assert kinds == [("metra", f"R{i}") for i in range(8)]  # the two federal commuter segments are gone
    with pytest.raises(RuntimeError, match="Metra GTFS"):
        rail_lines.metra_from_gtfs(_one_route_zip())


def _one_route_zip():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("routes.txt", "route_id,route_long_name,route_color\nR0,Line,29C233\n")
        z.writestr("trips.txt", "route_id,shape_id\nR0,S0\n")
        z.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nS0,41.8,-87.7,1\nS0,41.81,-87.7,2\n")
    return buf.getvalue()


def test_stations_outside_the_city_are_left_off():
    st = [{"name": "Western", "lat": 41.966, "lon": -87.688, "type": "cta_rail"},
          {"name": "South Boulevard", "lat": 42.027, "lon": -87.678, "type": "cta_rail"}]
    city = box(-87.94, 41.64, -87.52, 42.02)
    assert [f.props["name"] for f in base_tiles.station_features(st, city)] == ["Western"]


@pytest.mark.parametrize("code, kind, attrs, want", [
    ("1321", "exempt", {}, "institution"),  # 2851 N Seminary: a school with no story count
    ("1350", "city_owned", {}, "institution"),
    ("1321", "exempt", {"zoning_group": "planned_development"}, "own_rules"),  # its own ordinance says more
    ("1321", "commercial", {}, None),  # a taxed lot isn't named
    ("1215", "exempt", {}, None),
])
def test_an_exempt_institution_with_no_area_is_named_not_unknown(code, kind, attrs, want):
    a = {"land_kind": kind, "structure": "built", "land_sqft": 70_000.0, "density_band": 1.2} | attrs
    if "zoning_group" in attrs:
        a.pop("density_band")
    mark_land_use(a, PIN10, _src({PIN10: (code, 0.98)}))
    derive_capacity(a)
    assert a.get("room_scope") == want and "room_sqft" not in a
    a2 = {"land_kind": "exempt", "structure": "built", "land_sqft": 70_000.0, "density_band": 1.2, "bldg_sqft": 50_000.0}
    mark_land_use(a2, PIN10, _src({PIN10: ("1321", 0.98)}))
    derive_capacity(a2)
    assert a2["room_sqft"] == 34_000.0 and "room_scope" not in a2  # a computable room is never replaced
    assert measure_bands({"room_scope": "institution"})["r"] == "i"
