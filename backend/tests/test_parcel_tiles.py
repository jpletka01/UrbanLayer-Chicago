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
