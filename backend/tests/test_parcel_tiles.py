"""Parcel-outline vector tiles (WS8 Phase 2 prototype, decision Item 68): the hand-written MVT encoding,
tiling, the MBTiles file and the tile endpoint."""

from __future__ import annotations

import gzip
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from backend.discovery import parcel_tiles as pt


# A minimal protobuf reader, enough to read back what encode_layer writes.
def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = n = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _fields(buf: bytes) -> list[tuple[int, int | bytes]]:
    out, i = [], 0
    while i < len(buf):
        key, i = _read_varint(buf, i)
        field_no, wire = key >> 3, key & 7
        if wire == 0:
            v, i = _read_varint(buf, i)
        else:
            ln, i = _read_varint(buf, i)
            v, i = buf[i:i + ln], i + ln
        out.append((field_no, v))
    return out


def _packed(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _read_varint(buf, i)
        out.append(v)
    return out


def _decode(tile: bytes) -> dict:
    (field_no, layer), = _fields(tile)
    assert field_no == 3
    parsed = {"features": [], "keys": [], "values": []}
    for f, v in _fields(layer):
        if f == 15:
            parsed["version"] = v
        elif f == 1:
            parsed["name"] = v.decode()
        elif f == 5:
            parsed["extent"] = v
        elif f == 3:
            parsed["keys"].append(v.decode())
        elif f == 4:
            parsed["values"].append(dict(_fields(v))[1].decode())
        elif f == 2:
            feat = {}
            for ff, vv in _fields(v):
                feat[ff] = vv if ff in (1, 3) else _packed(vv)
            parsed["features"].append(feat)
    return parsed


def test_ring_matches_the_mvt_spec_example():
    # MVT 2.1 spec, 4.3.4.4: a polygon (3,6) (8,12) (20,34) encodes as [9 6 12 18 10 12 24 44 15].
    ring = np.array([[3, 6], [8, 12], [20, 34], [3, 6]])
    assert pt._ring_commands(ring, [0, 0]) == [9, 6, 12, 18, 10, 12, 24, 44, 15]


def test_layer_round_trips_id_properties_and_geometry():
    square = Polygon([(10, 10), (20, 10), (20, 20), (10, 20)])
    geometry = pt._polygon_geometry(square)
    layer = _decode(pt.encode_layer([(1234567890, geometry, {"g": "residential"})]))
    assert layer["version"] == 2 and layer["name"] == "parcels" and layer["extent"] == 4096
    (feat,) = layer["features"]
    assert feat[1] == 1234567890 and feat[3] == 3
    assert [layer["keys"][feat[2][0]], layer["values"][feat[2][1]]] == ["g", "residential"]
    cmds = feat[4]
    assert cmds[0] == 9 and cmds[-1] == 15 and cmds[3] == (3 << 3) | 2  # MoveTo, 3 LineTos, ClosePath


def test_exterior_ring_has_positive_area_in_tile_space():
    # Whatever the source winding, the exterior comes out with positive shoelace area (y down).
    for coords in ([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (0, 10), (10, 10), (10, 0)]):
        cmds = pt._polygon_geometry(Polygon(coords))
        pts, x, y, i = [], 0, 0, 1
        while i < len(cmds) - 1:
            if i in (1,):
                x, y = cmds[1] >> 1 ^ -(cmds[1] & 1), cmds[2] >> 1 ^ -(cmds[2] & 1)
                pts.append((x, y))
                i = 4
                continue
            dx, dy = cmds[i] >> 1 ^ -(cmds[i] & 1), cmds[i + 1] >> 1 ^ -(cmds[i + 1] & 1)
            x, y = x + dx, y + dy
            pts.append((x, y))
            i += 2
        area = sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1] for k in range(len(pts)))
        assert area > 0


def test_degenerate_rings_are_dropped():
    sliver = Polygon([(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)])  # rounds to a single point
    assert pt._polygon_geometry(sliver) == []


def _parcel(pin10: str, lon: float, lat: float, size: float = 0.0002) -> pt.Parcel:
    poly = Polygon([(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)])
    import shapely

    return pt.Parcel(pin10, shapely.transform(poly, pt._to_unit_mercator), {"g": "residential"})


def test_tiles_land_in_the_right_tile_and_carry_the_pin():
    # 1601 N Milwaukee Ave is in z14 tile (4201, 6087).
    parcel = _parcel("1431300000", -87.6765, 41.9097)
    tiles, skipped = pt.tiles_for_zoom([parcel], 14)
    assert skipped == 0
    assert list(tiles) == [(4201, 6087)]
    layer = _decode(gzip.decompress(tiles[(4201, 6087)]))
    assert [f[1] for f in layer["features"]] == [1431300000]


def test_mbtiles_and_endpoint(tmp_path, monkeypatch):
    out = tmp_path / "t.mbtiles"
    stats = pt.write_mbtiles(out, [_parcel("1431300000", -87.6765, 41.9097)], 14, 14)
    assert stats.tiles == {14: 1}

    app = FastAPI()
    app.include_router(pt.router)
    client = TestClient(app)
    import backend.config as config

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(discovery_tiles_path=out))
    hit = client.get("/api/discovery/tiles/14/4201/6087.mvt")
    assert hit.status_code == 200
    assert hit.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert _decode(hit.content)["features"][0][1] == 1431300000  # the client undid the gzip
    assert client.get("/api/discovery/tiles/14/4202/6087.mvt").status_code == 204
    assert client.get("/api/discovery/tiles/14/99999/6087.mvt").status_code == 400

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(discovery_tiles_path=tmp_path / "none"))
    assert client.get("/api/discovery/tiles/14/4201/6087.mvt").status_code == 404


@pytest.mark.parametrize("n", [0, 1, 127, 128, 300, 2**35])
def test_varint_round_trip(n):
    assert _read_varint(pt._varint(n), 0) == (n, len(pt._varint(n)))


def test_broken_outlines_are_repaired_not_fatal():
    import shapely
    from shapely import wkt

    bowtie = wkt.loads("POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))")  # self-crossing: invalid
    fixed = pt._polygonal(shapely.make_valid(bowtie))
    assert fixed is not None and fixed.is_valid and fixed.area > 0
    assert pt._polygonal(shapely.make_valid(wkt.loads("LINESTRING (0 0, 1 1)"))) is None


# ---------------------------------------------------------------- the built file, the registry, the rebuild hook


def _index_and_ptaxsim(tmp_path, *, data_version="v1"):
    """A two-parcel index and a PTAXSIM outline table: one PIN10 with an outline, one without."""
    import json
    import sqlite3

    from backend.discovery.parcel_index import _SCHEMA

    idx = tmp_path / "discovery_index.db"
    con = sqlite3.connect(idx)
    con.executescript(_SCHEMA)
    con.executemany("INSERT INTO parcels VALUES (?,?,?,?,?)", [
        ("14-31-300-012-0000", 41.9097, -87.6765, json.dumps({"zoning_group": "business"}), '["neighborhood:24"]'),
        ("14-31-300-013-0000", 41.9098, -87.6766, "{}", '["neighborhood:24"]'),
    ])
    con.execute("INSERT INTO meta VALUES (1, ?, 0, '24', 2, '[]', '{}')", (data_version,))
    con.commit()
    con.close()
    geo = tmp_path / "ptaxsim.db"
    con = sqlite3.connect(geo)
    con.execute("CREATE TABLE pin_geometry_raw (pin10 TEXT, start_year INT, end_year INT, longitude REAL, latitude REAL, geometry TEXT)")
    con.execute("INSERT INTO pin_geometry_raw VALUES ('1431300012', 2006, 2024, -87.6765, 41.9097, "
                "'POLYGON ((-87.6766 41.9096, -87.6764 41.9096, -87.6764 41.9098, -87.6766 41.9098, -87.6766 41.9096))')")
    con.commit()
    con.close()
    return idx, geo


def test_build_file_swaps_in_a_finished_file_with_its_provenance(tmp_path):
    idx, geo = _index_and_ptaxsim(tmp_path)
    out = tmp_path / "parcel_tiles.mbtiles"
    out.write_bytes(b"previous")
    summary = pt.build_file(idx, geo, out, minzoom=14, maxzoom=15)
    assert summary["parcels_with_outline"] == 1 and summary["pin10_without_outline"] == 1
    assert not out.with_name(out.name + ".tmp").exists()
    info = pt.tiles_info(out)
    assert info["index_version"] == "v1" and info["parcels"] == "1" and info["pin10_without_outline"] == "1"
    assert info["minzoom"] == "14" and info["maxzoom"] == "15" and info["built_at"]


def test_build_file_refuses_to_replace_tiles_with_nothing(tmp_path):
    idx, geo = _index_and_ptaxsim(tmp_path)
    import sqlite3

    con = sqlite3.connect(geo)
    con.execute("DELETE FROM pin_geometry_raw")
    con.commit()
    con.close()
    out = tmp_path / "parcel_tiles.mbtiles"
    out.write_bytes(b"previous")
    with pytest.raises(RuntimeError, match="refusing"):
        pt.build_file(idx, geo, out)
    assert out.read_bytes() == b"previous"


def test_tiles_info_none_without_a_usable_file(tmp_path):
    assert pt.tiles_info(tmp_path / "none.mbtiles") is None
    junk = tmp_path / "junk.mbtiles"
    junk.write_bytes(b"not sqlite")
    assert pt.tiles_info(junk) is None


def test_registry_block_says_whether_tiles_match_the_index(tmp_path, monkeypatch):
    import backend.config as config
    from backend.discovery import api

    idx, geo = _index_and_ptaxsim(tmp_path, data_version="v1")
    out = tmp_path / "parcel_tiles.mbtiles"
    pt.build_file(idx, geo, out, minzoom=14, maxzoom=16)
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(discovery_tiles_path=out))
    block = api._parcel_tiles("v1")
    assert block.minZoom == 14 and block.maxZoom == 16 and block.parcels == 1 and block.current
    assert api._parcel_tiles("v2").current is False
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(discovery_tiles_path=tmp_path / "none"))
    assert api._parcel_tiles("v1") is None


def test_index_rebuild_never_fails_on_a_tile_failure(monkeypatch, capsys):
    from backend.discovery import index_build

    def boom(*a, **k):
        raise RuntimeError("ptaxsim gone")

    monkeypatch.setattr(pt, "build_file", boom)
    index_build._rebuild_tiles()  # no exception
    assert "NOT rebuilt: ptaxsim gone" in capsys.readouterr().out


def test_rebuild_flag_parses():
    from backend.discovery import index_build

    assert index_build._parse_args(["--refresh"]).no_tiles is False
    assert index_build._parse_args(["--refresh", "--no-tiles"]).no_tiles is True


def test_data_health_findings():
    from backend.data_health.probes import parcel_tiles_findings

    meta = {"parcels": "604220", "pin10_without_outline": "854", "outlines_repaired": "806", "pieces_unclipped": "1",
            "minzoom": "14", "maxzoom": "16", "index_version": "v1"}
    info, findings = parcel_tiles_findings(meta, "v1")
    assert "604,220 outlines" in info and findings == []
    _, stale = parcel_tiles_findings(meta, "v2")
    assert [f.level for f in stale] == ["warn"] and "built from index v1" in stale[0].text and "serving is v2" in stale[0].text
    _, bad = parcel_tiles_findings({**meta, "pin10_without_outline": "20000", "pieces_unclipped": "500"}, "v1")
    assert len(bad) == 2
