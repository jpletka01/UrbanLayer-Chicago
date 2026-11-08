"""The new UI's own map tiles (Phase 5, decision Items 90-91): the encoder's lines and points, the base built
from the City's streets, parks and water, the zoning tiles with their source attributes, the boundary accuracy
of the zoning tiles on a recorded fixture, and the endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, shape

from backend.map_tiles import base_tiles, zoning_tiles
from backend.map_tiles.mvt_decode import decode_tile
from backend.map_tiles.tiler import Feature, read_tile, tiles_for_zoom, to_mercator, write_mbtiles

FIXTURE = Path(__file__).parent / "fixtures" / "ws3_milwaukee_zoning_adjacent.geojson"
# 1601 N Milwaukee Ave, inside the fixture's two districts' area.
LON, LAT = -87.6773, 41.9097


def _tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    import math

    n = 1 << z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


# ---------------------------------------------------------------- encoder: lines, points, layers


def test_a_line_and_a_point_round_trip_through_one_tile():
    line = LineString([(LON - 0.001, LAT), (LON + 0.001, LAT + 0.0005)])
    feats = [
        Feature("road", to_mercator(line), {"kind": "major", "name": "N Milwaukee Ave"}),
        Feature("label", to_mercator(Point(LON, LAT)), {"zone_class": "B3-2"}),
    ]
    x, y = _tile_xy(LON, LAT, 16)
    tiles, skipped = tiles_for_zoom(feats, 16, 16, ["road", "label"])
    assert skipped == 0
    layers = decode_tile(tiles[(x, y)], 16, x, y)
    road = layers["road"][0]
    assert road["type"] == 2 and road["props"] == {"kind": "major", "name": "N Milwaukee Ave"}
    assert road["geometry"].hausdorff_distance(line) < 1e-5  # a tile unit at z16 is ~0.1 m
    label = layers["label"][0]
    assert label["type"] == 1 and label["geometry"].distance(Point(LON, LAT)) < 1e-5


def test_a_point_goes_only_in_its_own_tile():
    """A label inside a neighbor's buffer would be drawn twice; it must land in exactly one tile."""
    feats = [Feature("label", to_mercator(Point(LON, LAT)), {"zone_class": "RS-3"})]
    tiles, _ = tiles_for_zoom(feats, 15, 16, ["label"])
    assert len(tiles) == 1


def test_minzoom_keeps_a_feature_out_of_lower_zooms():
    feats = [Feature("road", to_mercator(LineString([(LON, LAT), (LON + 0.001, LAT)])), {"kind": "local"}, 13)]
    assert tiles_for_zoom(feats, 12, 16, ["road"])[0] == {}
    assert tiles_for_zoom(feats, 13, 16, ["road"])[0]


# ---------------------------------------------------------------- the base


def test_street_names_read_like_signs():
    assert base_tiles.street_name("N", "MILWAUKEE", "AVE") == "N Milwaukee Ave"
    assert base_tiles.street_name("W", "79TH", "ST") == "W 79TH St"
    assert base_tiles.street_name(None, "LAKE SHORE", "DR") == "Lake Shore Dr"
    assert base_tiles.street_name("S", None, "AVE") == ""


def _road(cls: str, status: str = "N", name: str = "MILWAUKEE") -> dict:
    return {"the_geom": {"type": "MultiLineString", "coordinates": [[[LON, LAT], [LON + 0.001, LAT]]]},
            "class": cls, "status": status, "pre_dir": "N", "street_nam": name, "street_typ": "AVE"}


def test_base_keeps_streets_by_class_and_status_and_says_what_it_left_out():
    sources = {
        "city": [{"the_geom": {"type": "Polygon", "coordinates": [[[LON - 1, LAT - 1], [LON + 1, LAT - 1],
                                                                    [LON + 1, LAT + 1], [LON - 1, LAT - 1]]]}}],
        "water": [], "park": [],
        "road": [_road("1"), _road("2"), _road("3"), _road("4"), _road("9"), _road("7"), _road("RIV"),
                 _road("99"), _road("2", status="P"), _road("2", status="V")],
    }
    feats, left_out = base_tiles.build_features(sources)
    roads = [f for f in feats if f.layer == "road"]
    assert [f.props["kind"] for f in roads] == ["highway", "major", "minor", "local", "ramp"]
    assert [f.minzoom for f in roads] == [10, 10, 12, 13, 12]
    assert roads[4].props["name"] == ""  # ramps carry no label
    assert left_out == {"road_class": 3, "road_status": 2, "no_geometry": 0}


def test_base_refuses_an_empty_source(tmp_path, monkeypatch):
    monkeypatch.setattr(base_tiles, "_fetch", lambda dataset, select, **kw: [] if dataset == "ejsh-fztr" else [{}])
    with pytest.raises(RuntimeError, match="ejsh-fztr"):
        base_tiles.load_sources(tmp_path, offline=False)


# ---------------------------------------------------------------- zoning


@pytest.mark.parametrize("zc,fam,lvl", [
    ("RS-3", "residential", "1"), ("RT-4", "residential", "2"), ("RM-5", "residential", "3"),
    ("RM-6.5", "residential", "4"), ("B3-2", "business", "1"), ("C1-3", "business", "2"),
    ("B3-5", "business", "3"), ("DX-12", "downtown", "4"), ("DC-16", "downtown", "4"), ("M2-3", "manufacturing", "2"),
    ("PMD 9", "manufacturing", "1"), ("PD 233", "planned", "1"), ("POS-1", "park", "1"), ("T", "transport", "1"),
])
def test_zoning_family_and_level(zc, fam, lvl):
    assert zoning_tiles.family(zc) == fam
    assert zoning_tiles.level(zc) == lvl


def test_zoning_keeps_source_attributes_and_no_staff_ids():
    props = zoning_tiles.source_props({
        "ZONE_CLASS": "B3-2", "ZONE_TYPE": 3, "ORDINANCE_NUM": "19239", "ORDINANCE_DATE": 1592352000000,
        "CASE_NUMBER": 37977, "PD_NUM": None, "CLERK_DOCNO": "SO2020-1893", "ZONING_ID": 66,
        "CREATE_USERID": "someone", "UPDATE_USERID": "someone",
    })
    assert props == {"zone_class": "B3-2", "family": "business", "level": "1", "zone_type": "3",
                     "zoning_id": "66", "ordinance_num": "19239", "ordinance_date": "2020-06-17",
                     "case_number": "37977", "clerk_docno": "SO2020-1893"}


def test_zoning_tiles_keep_every_district_where_the_source_has_it(tmp_path):
    """The boundary accuracy test on the recorded Milwaukee fixture (two districts sharing an edge): a grid of
    points across both districts reads the same district from the tiles at every zoom as from the source."""
    src = json.loads(FIXTURE.read_text())["features"]
    feats, report = zoning_tiles.build_features(src)
    assert report["districts"] == len(src)
    out = tmp_path / "z.mbtiles"
    write_mbtiles(out, feats, name="z", minzoom=13, maxzoom=16, layer_order=zoning_tiles.LAYERS,
                  fields={"zoning": {}, "zoning_label": {}}, extra_meta={})
    shapes = [(f["properties"]["ZONE_CLASS"], shape(f["geometry"])) for f in src]
    minx = min(g.bounds[0] for _, g in shapes)
    miny = min(g.bounds[1] for _, g in shapes)
    maxx = max(g.bounds[2] for _, g in shapes)
    maxy = max(g.bounds[3] for _, g in shapes)
    checked = 0
    for z in (13, 14, 15, 16):
        for i in range(25):
            for j in range(25):
                lon = minx + (maxx - minx) * (i + 0.5) / 25
                lat = miny + (maxy - miny) * (j + 0.5) / 25
                p = Point(lon, lat)
                want = [zc for zc, g in shapes if g.contains(p)]
                # Tile coordinates move an edge by up to about one tile unit (0.9 m at zoom 13, 0.1 m at 16):
                # points that close to an edge have no single answer to compare.
                unit_deg = 360 / (1 << z) / 4096 * 1.5
                if len(want) != 1 or min(g.boundary.distance(p) for _, g in shapes) < unit_deg:
                    continue
                x, y = _tile_xy(lon, lat, z)
                data = read_tile(out, z, x, y)
                got = [f["props"]["zone_class"] for f in decode_tile(data, z, x, y)["zoning"]
                       if f["geometry"].buffer(0).contains(p)]
                assert got == want, (z, lon, lat, got, want)
                checked += 1
    assert checked > 1000


def test_labels_start_later_for_smaller_districts():
    assert zoning_tiles.label_minzoom(500_000) == 13
    assert zoning_tiles.label_minzoom(50_000) == 14
    assert zoning_tiles.label_minzoom(10_000) == 15
    assert zoning_tiles.label_minzoom(500) == 16


# ---------------------------------------------------------------- endpoints


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.config import get_settings
    from backend.main import app

    s = get_settings()
    monkeypatch.setattr(s, "map_base_tiles_path", tmp_path / "base.mbtiles")
    monkeypatch.setattr(s, "map_zoning_tiles_path", tmp_path / "zoning.mbtiles")
    monkeypatch.setattr(s, "discovery_tiles_path", tmp_path / "parcels.mbtiles")
    return TestClient(app)


def test_tiles_404_when_not_installed_then_serve(client, tmp_path):
    assert client.get("/api/map/tiles/base/16/16808/24344.mvt").status_code == 404
    assert client.get("/api/map/tiles/nope/16/1/1.mvt").status_code == 404
    assert client.get("/api/map/info").json() == {"parcels": None, "base": None, "zoning": None}

    line = LineString([(LON - 0.001, LAT), (LON + 0.001, LAT)])
    write_mbtiles(tmp_path / "base.mbtiles", [Feature("road", to_mercator(line), {"kind": "major", "name": "x"})],
                  name="map_base", minzoom=15, maxzoom=16, layer_order=["road"], fields={"road": {}},
                  extra_meta={"built_at": "2026-11-08"})
    x, y = _tile_xy(LON, LAT, 16)
    hit = client.get(f"/api/map/tiles/base/16/{x}/{y}.mvt")
    assert hit.status_code == 200 and hit.headers["cache-control"] == "public, max-age=86400"
    assert decode_tile(hit.content, 16, x, y)["road"][0]["props"]["kind"] == "major"
    assert client.get("/api/map/tiles/base/16/1/1.mvt").status_code == 204
    assert client.get("/api/map/tiles/base/30/1/1.mvt").status_code == 400
    info = client.get("/api/map/info").json()
    assert info["base"] == {"minZoom": 15, "maxZoom": 16, "builtAt": "2026-11-08"}
    assert info["zoning"] is None


# ---------------------------------------------------------------- full-precision outlines (Item 92)


def test_a_county_outline_is_used_only_while_it_still_matches_todays_lot():
    from shapely.geometry import box

    from backend.map_tiles.county_outlines import still_matches

    ptaxsim = box(-87.67800, 41.91060, -87.67760, 41.91100)          # today's lot, 1 m rounding
    precise = box(-87.678004, 41.910603, -87.677597, 41.910998)      # the same lot at full precision
    split = box(-87.67800, 41.91060, -87.67780, 41.91100)            # half of it: the lot was split since 2021
    shifted = box(-87.67750, 41.91060, -87.67710, 41.91100)          # a neighbor
    assert still_matches(precise, ptaxsim)
    assert not still_matches(split, ptaxsim)
    assert not still_matches(shifted, ptaxsim)


def test_lot_endpoint_prefers_the_matching_county_outline(tmp_path, monkeypatch):
    import sqlite3 as sq

    import shapely
    from shapely.geometry import box

    from backend.config import get_settings
    from backend.main import app
    from backend.map_tiles import county_outlines

    pt = tmp_path / "ptaxsim.db"
    db = sq.connect(pt)
    db.execute("CREATE TABLE pin_geometry_raw (pin10 TEXT, start_year INT, end_year INT, longitude REAL, latitude REAL, geometry TEXT)")
    db.execute("INSERT INTO pin_geometry_raw VALUES ('1431332018', 2006, 2024, 0, 0, ?)",
               (box(-87.67800, 41.91060, -87.67760, 41.91100).wkt,))
    db.commit()
    db.close()
    co = tmp_path / "county.db"
    db = sq.connect(co)
    db.execute("CREATE TABLE outlines (pin10 TEXT PRIMARY KEY, wkb BLOB)")
    db.execute("INSERT INTO outlines VALUES ('1431332018', ?)", (shapely.to_wkb(box(-87.678004, 41.910603, -87.677597, 41.910998)),))
    db.commit()
    db.close()
    s = get_settings()
    monkeypatch.setattr(s, "ptaxsim_db_path", pt)
    monkeypatch.setattr(county_outlines, "default_outlines", lambda: county_outlines.Outlines(co))
    client = TestClient(app)
    r = client.get("/api/map/lot?pin10=1431332018")
    assert r.status_code == 200 and r.json()["source"] == "county_2021"
    assert r.json()["geometry"]["coordinates"][0][0][0] == pytest.approx(-87.677597)
    monkeypatch.setattr(county_outlines, "default_outlines", lambda: county_outlines.Outlines(tmp_path / "missing.db"))
    assert client.get("/api/map/lot?pin10=1431332018").json()["source"] == "ptaxsim"
    assert client.get("/api/map/lot?pin10=0000000000").status_code == 404
    assert client.get("/api/map/lot?pin10=12").status_code == 400
