"""Read our Mapbox Vector Tiles back into shapely geometry (lon/lat), for the zoning boundary accuracy test and
the tests. Handles what our encoder writes: string properties, points, lines and polygons."""

from __future__ import annotations

import gzip
import math

import numpy as np
import shapely

from shapely.geometry import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = n = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _fields(buf: bytes) -> list[tuple[int, int | bytes]]:
    out: list[tuple[int, int | bytes]] = []
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            v, i = _varint(buf, i)
            out.append((field, v))
        elif wire == 2:
            ln, i = _varint(buf, i)
            out.append((field, buf[i:i + ln]))
            i += ln
        else:
            raise ValueError(f"unsupported wire type {wire}")
    return out


def _packed(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _unzig(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _paths(cmds: list[int]) -> list[tuple[list[tuple[int, int]], bool]]:
    """Command stream → [(points, closed)] in tile coordinates."""
    paths: list[tuple[list[tuple[int, int]], bool]] = []
    x = y = 0
    i = 0
    cur: list[tuple[int, int]] = []
    while i < len(cmds):
        cmd, count = cmds[i] & 7, cmds[i] >> 3
        i += 1
        if cmd == 1:
            for _ in range(count):
                if cur:
                    paths.append((cur, False))
                x += _unzig(cmds[i])
                y += _unzig(cmds[i + 1])
                i += 2
                cur = [(x, y)]
        elif cmd == 2:
            for _ in range(count):
                x += _unzig(cmds[i])
                y += _unzig(cmds[i + 1])
                i += 2
                cur.append((x, y))
        elif cmd == 7:
            paths.append((cur, True))
            cur = []
    if cur:
        paths.append((cur, False))
    return paths


def _geometry(gtype: int, cmds: list[int]):
    paths = _paths(cmds)
    if gtype == 1:
        pts = [Point(p) for path, _ in paths for p in path]
        return pts[0] if len(pts) == 1 else MultiPoint(pts)
    if gtype == 2:
        lines = [LineString(p) for p, _ in paths if len(p) >= 2]
        return lines[0] if len(lines) == 1 else MultiLineString(lines)
    polys: list[tuple[list, list]] = []
    for ring, _ in paths:
        if len(ring) < 3:
            continue
        # The spec: an exterior ring has positive shoelace area in tile coordinates (y down), a hole negative.
        area = sum(ring[k][0] * ring[(k + 1) % len(ring)][1] - ring[(k + 1) % len(ring)][0] * ring[k][1]
                   for k in range(len(ring)))
        if area > 0 or not polys:
            polys.append((ring, []))
        else:
            polys[-1][1].append(ring)
    shapes = [Polygon(ext, holes) for ext, holes in polys]
    return shapes[0] if len(shapes) == 1 else MultiPolygon(shapes)


def decode_tile(data: bytes, z: int, x: int, y: int) -> dict[str, list[dict]]:
    """{layer name: [{id, props, geometry (lon/lat shapely)}]}. ``data`` may be gzipped."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    out: dict[str, list[dict]] = {}
    n = 1 << z
    for field, layer_buf in _fields(data):
        if field != 3:
            continue
        name, keys, values, feats, extent = "", [], [], [], 4096
        for f, v in _fields(layer_buf):
            if f == 1:
                name = v.decode()
            elif f == 2:
                feats.append(v)
            elif f == 3:
                keys.append(v.decode())
            elif f == 4:
                values.append(dict(_fields(v)).get(1, b"").decode())
            elif f == 5:
                extent = v
        decoded = []
        for fb in feats:
            fd: dict = {"id": 0, "tags": [], "type": 0, "geom": []}
            for f, v in _fields(fb):
                if f == 1:
                    fd["id"] = v
                elif f == 2:
                    fd["tags"] = _packed(v)
                elif f == 3:
                    fd["type"] = v
                elif f == 4:
                    fd["geom"] = _packed(v)
            props = {keys[fd["tags"][j]]: values[fd["tags"][j + 1]] for j in range(0, len(fd["tags"]), 2)}
            g = _geometry(fd["type"], fd["geom"])

            def to_lonlat(px: float, py: float) -> tuple[float, float]:
                ux, uy = (x + px / extent) / n, (y + py / extent) / n
                lon = ux * 360.0 - 180.0
                lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * uy))))
                return lon, lat

            g = shapely.transform(g, lambda c: np.array([to_lonlat(px, py) for px, py in c]))
            decoded.append({"id": fd["id"], "props": props, "geometry": g, "type": fd["type"]})
        out[name] = decoded
    return out
