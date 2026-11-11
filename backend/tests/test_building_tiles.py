"""The 3D mode's building heights (Phase 7 M6 spike, Items 105-106): County 2022 LiDAR footprints inside Chicago,
height in whole feet, invalid outlines repaired, a short source refused."""
from __future__ import annotations

import sqlite3

import pytest
import shapely
from shapely.geometry import Polygon, box

from backend.map_tiles import building_tiles
from backend.map_tiles.mvt_decode import decode_tile
from backend.map_tiles.tiler import read_tile

LON, LAT = -87.6773, 41.9097  # Wicker Park, inside the city
OUTSIDE = (-87.80, 42.02)  # in Chicago's box, outside the city (Niles side)


def _source(path, rows):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE buildings (oid INTEGER PRIMARY KEY, ground_ft REAL, max_ft REAL, height_ft REAL, wkb BLOB)")
    db.executemany("INSERT INTO buildings VALUES (?,?,?,?,?)",
                   [(i, 600.0, 600.0 + h, h, shapely.to_wkb(g)) for i, (h, g) in enumerate(rows)])
    db.commit()
    db.close()


def _square(lon, lat, d=0.00008):
    return box(lon - d, lat - d, lon + d, lat + d)


def test_keeps_city_buildings_rounds_height_and_repairs_outlines(tmp_path, monkeypatch):
    monkeypatch.setattr(building_tiles, "MIN_IN_CITY", 1)
    bowtie = Polygon([(LON + 0.001, LAT), (LON + 0.0012, LAT + 0.0002), (LON + 0.0012, LAT), (LON + 0.001, LAT + 0.0002)])
    src = tmp_path / "src.db"
    _source(src, [(28.56, _square(LON, LAT)), (40.0, _square(*OUTSIDE)), (12.0, bowtie)])
    feats, counts = building_tiles.build_features(src)
    assert counts["in_box"] == 3 and counts["in_city"] == 2
    assert counts["invalid_fixed"] == 1 and counts["dropped_empty"] == 0
    assert sorted(f.props["h"] for f in feats) == ["12", "29"]
    assert all(f.props["m"] == "l" and "f" not in f.props for f in feats)  # no zoning given: untinted
    assert all(f.layer == "building" and f.minzoom == building_tiles.MIN_ZOOM for f in feats)


def test_refuses_a_short_city(tmp_path):
    src = tmp_path / "src.db"
    _source(src, [(20.0, _square(LON, LAT))])
    with pytest.raises(RuntimeError, match="inside the city"):
        building_tiles.build_features(src)


def test_offline_build_writes_tiles_with_heights(tmp_path, monkeypatch):
    monkeypatch.setattr(building_tiles, "MIN_IN_CITY", 1)
    (tmp_path / "map_sources").mkdir()
    _source(tmp_path / "map_sources" / building_tiles.SOURCE_DB, [(35.2, _square(LON, LAT))])
    out = tmp_path / "map_buildings.mbtiles"
    summary = building_tiles.build_file(out, offline=True, minzoom=16, maxzoom=16)
    assert summary["counts"]["in_city"] == 1 and summary["pieces_unclipped"] == 0
    import math
    n = 1 << 16
    x = int((LON + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(LAT)) + 1 / math.cos(math.radians(LAT))) / math.pi) / 2 * n)
    tile = decode_tile(read_tile(out, 16, x, y), 16, x, y)
    assert tile["building"][0]["props"]["h"] in ("35", 35)


def test_fetch_refuses_a_short_read(tmp_path):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"objectIds": [1, 2, 3]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(RuntimeError, match="expected"):
            building_tiles.fetch(tmp_path / "x.db", client=c)
    assert not (tmp_path / "x.db").exists()


# ---------------------------------------------------------------- merged outlines (owner's review, 616 W Diversey)

def _row(x0, x1, y0=LAT, y1=LAT + 0.0003):
    return box(LON + x0, y0, LON + x1, y1)


def test_a_tall_outline_is_split_along_the_city_footprints():
    tower, low_known, low_unknown = _row(0, 0.0004), _row(0.0004, 0.0006), _row(0.0006, 0.0008)
    outline = _row(0, 0.0008)
    parts = building_tiles.split_outline(outline, 173.0, [(tower, 16), (low_known, 1), (low_unknown, None)])
    by_kind = sorted((k, round(h)) for _, h, k in parts)
    assert by_kind == [("l", 173), ("s", 18), ("u", building_tiles.UNMEASURED_FT)]


def test_no_split_when_short_single_or_no_stories():
    a, b = _row(0, 0.0004), _row(0.0004, 0.0008)
    outline = _row(0, 0.0008)
    assert len(building_tiles.split_outline(outline, 40.0, [(a, 3), (b, 1)])) == 1  # under SPLIT_MIN_FT
    assert len(building_tiles.split_outline(outline, 173.0, [(a, 16)])) == 1  # one footprint
    assert len(building_tiles.split_outline(outline, 173.0, [(a, None), (b, None)])) == 1  # nothing to anchor on


def test_leftover_outline_keeps_the_height_only_beside_the_tower():
    tower, low = _row(0, 0.0003), _row(0.0005, 0.0006)
    # The outline covers both plus a wide gap between them (touching the tower) and a far piece past the low one.
    outline = _row(0, 0.0009)
    parts = building_tiles.split_outline(outline, 150.0, [(tower, 12), (low, 1)])
    leftovers = [(round(h), k) for g, h, k in parts if not g.equals(shapely.intersection(tower, outline))
                 and not g.equals(shapely.intersection(low, outline))]
    assert (150, "l") in leftovers  # the gap touching the tower
    assert (building_tiles.UNMEASURED_FT, "u") in leftovers  # the far piece


def test_story_heights_follow_item_105s_fit():
    assert building_tiles.stories_ft(1) == pytest.approx(17.75)
    assert building_tiles.stories_ft(10) == 140


def test_buildings_carry_the_zoning_family_under_them(tmp_path, monkeypatch):
    monkeypatch.setattr(building_tiles, "MIN_IN_CITY", 1)
    src = tmp_path / "src.db"
    _source(src, [(30.0, _square(LON, LAT))])
    zoning = [{"type": "Feature", "properties": {"ZONE_CLASS": "B3-2"}, "geometry": shapely.geometry.mapping(_square(LON, LAT, 0.001))}]
    feats, counts = building_tiles.build_features(src, zoning=zoning)
    assert feats[0].props["f"] == "business" and feats[0].props["m"] == "l"
    assert counts["zoning_unmatched"] == 0


# ---------------------------------------------------------------- the Assessor's one-story lots (616 W Diversey)

def test_a_one_story_lot_is_cut_out_of_a_tall_piece():
    piece = _row(0, 0.0008)
    shop = _row(0.0006, 0.0008, LAT - 0.0001, LAT + 0.0004)  # the lot reaches past the building
    lots = (shapely.STRtree([shop]), [shop])
    parts = building_tiles.cut_one_story(piece, 173.0, lots)
    kinds = sorted((k, round(h)) for _, h, k in parts)
    assert kinds == [("a", building_tiles.ONE_STORY_FT), ("l", 173)]


def test_a_one_story_cut_leaves_the_tall_building_when_it_would_take_most_of_it():
    piece = _row(0, 0.0008)
    big = _row(-0.0001, 0.0009, LAT - 0.0001, LAT + 0.0004)  # the "one-story" lot holds the whole tall building
    assert building_tiles.cut_one_story(piece, 173.0, (shapely.STRtree([big]), [big])) == [(piece, 173.0, "l")]
    assert building_tiles.cut_one_story(piece, 40.0, (shapely.STRtree([big]), [big])) == [(piece, 40.0, "l")]
