"""Cut features into gzipped Mapbox Vector Tiles and write an MBTiles file.

Shared by the base tiles (roads, parks, water, the city) and the zoning tiles. The protobuf encoding is
Discovery's hand-written one (``backend.discovery.parcel_tiles``, Item 68); this module adds lines, several
layers per tile, per-layer minimum zooms and a fixed area (Chicago), so a feature as large as Lake Michigan
cuts only the tiles the map can show.
"""

from __future__ import annotations

import gzip
import json
import math
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon

from backend.discovery.parcel_tiles import (
    BUFFER,
    EXTENT,
    LINESTRING,
    POLYGON,
    _clip,
    _command,
    _polygon_geometry,
    _polygonal,
    _to_unit_mercator,
    _zigzag,
    encode_layer,
)

# Chicago's extent plus a margin (lon/lat): tiles outside it are never cut.
CHICAGO_BOUNDS = (-87.95, 41.63, -87.50, 42.03)


@dataclass
class Feature:
    layer: str
    geom: object  # shapely geometry in unit Mercator
    props: dict[str, str]
    minzoom: int = 0
    # Polygons and lines are simplified by one tile unit below the top zoom; set False to keep the source
    # geometry at every zoom (zoning's boundary accuracy test reads the tiles against the source).
    simplify: bool = True
    # Per-zoom geometry prepared by the caller (zoning: shared-edge simplification of the whole coverage);
    # when set for a zoom it is used as is.
    zoom_geoms: dict[int, object] | None = None


@dataclass
class TileStats:
    tiles: dict[int, int] = field(default_factory=dict)
    bytes_gz: dict[int, int] = field(default_factory=dict)
    max_tile_gz: dict[int, int] = field(default_factory=dict)
    unclipped: dict[int, int] = field(default_factory=dict)
    seconds: float = 0.0


def to_mercator(geom):
    """lon/lat shapely geometry → unit Mercator (x right, y down)."""
    return shapely.transform(geom, lambda c: _to_unit_mercator(np.asarray(c)))


def _line_geometry(geom) -> list[int]:
    """Encode a (Multi)LineString already in tile coordinates: MoveTo + LineTo per part, repeated points dropped."""
    cursor = [0, 0]
    out: list[int] = []
    parts = geom.geoms if isinstance(geom, MultiLineString) else [geom]
    for part in parts:
        if part.is_empty:
            continue
        pts = np.rint(np.asarray(part.coords)[:, :2]).astype(np.int64)
        keep = np.ones(len(pts), dtype=bool)
        keep[1:] = (pts[1:] != pts[:-1]).any(axis=1)
        pts = pts[keep]
        if len(pts) < 2:
            continue
        x, y = int(pts[0][0]), int(pts[0][1])
        out += [_command(1, 1), _zigzag(x - cursor[0]), _zigzag(y - cursor[1])]
        cursor[0], cursor[1] = x, y
        out.append(_command(2, len(pts) - 1))
        for px, py in pts[1:]:
            px, py = int(px), int(py)
            out += [_zigzag(px - cursor[0]), _zigzag(py - cursor[1])]
            cursor[0], cursor[1] = px, py
    return out


def _lines(g):
    if g.geom_type in ("LineString", "MultiLineString"):
        return g
    parts = [p for p in getattr(g, "geoms", []) if p.geom_type == "LineString"]
    return MultiLineString(parts) if parts else None


POINT = 1


def _point_geometry(geom) -> list[int]:
    pts = list(geom.geoms) if geom.geom_type == "MultiPoint" else [geom]
    out = [_command(1, len(pts))]
    cx = cy = 0
    for p in pts:
        x, y = int(round(p.x)), int(round(p.y))
        out += [_zigzag(x - cx), _zigzag(y - cy)]
        cx, cy = x, y
    return out


def _encode(geom) -> tuple[list[int], int] | None:
    if geom.geom_type in ("Point", "MultiPoint"):
        return _point_geometry(geom), POINT
    if geom.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection") and _polygonal(geom) is not None:
        cmds = _polygon_geometry(_polygonal(geom))
        return (cmds, POLYGON) if cmds else None
    lines = _lines(geom)
    if lines is not None:
        cmds = _line_geometry(lines)
        return (cmds, LINESTRING) if cmds else None
    return None


def _tile_range(bounds, n: int, buf: float, limit: tuple[int, int, int, int]):
    minx, miny, maxx, maxy = bounds
    x0, y0, x1, y1 = limit
    return (
        range(max(int((minx - buf) * n), x0), min(int((maxx + buf) * n), x1) + 1),
        range(max(int((miny - buf) * n), y0), min(int((maxy + buf) * n), y1) + 1),
    )


def tile_limit(z: int, bounds=CHICAGO_BOUNDS) -> tuple[int, int, int, int]:
    """Tile x/y range at zoom z that covers ``bounds`` (lon/lat)."""
    w, s, e, n_ = bounds
    tl = _to_unit_mercator(np.array([[w, n_]]))[0]
    br = _to_unit_mercator(np.array([[e, s]]))[0]
    n = 1 << z
    return int(tl[0] * n), int(tl[1] * n), int(br[0] * n), int(br[1] * n)


def tiles_for_zoom(features: list[Feature], z: int, maxzoom: int, layer_order: list[str],
                   bounds=CHICAGO_BOUNDS) -> tuple[dict[tuple[int, int], bytes], int]:
    """Gzipped tiles at zoom z (one MVT layer per name in ``layer_order`` that has features there) and how many
    pieces could not be clipped."""
    n = 1 << z
    scale = n * EXTENT
    buf = BUFFER / scale
    tol = 1.0 / scale
    limit = tile_limit(z, bounds)
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    shapes: list = []
    for i, f in enumerate(features):
        if z < f.minzoom:
            shapes.append(None)
            continue
        if f.zoom_geoms is not None and z in f.zoom_geoms:
            g = f.zoom_geoms[z]
        elif f.simplify and z < maxzoom and f.geom.geom_type not in ("Point", "MultiPoint"):
            g = f.geom.simplify(tol, preserve_topology=True)
        else:
            g = f.geom
        if g is None or g.is_empty:
            shapes.append(None)
            continue
        shapes.append(g)
        xs, ys = _tile_range(g.bounds, n, buf, limit)
        for tx in xs:
            for ty in ys:
                buckets[(tx, ty)].append(i)
    out: dict[tuple[int, int], bytes] = {}
    skipped = 0
    for (tx, ty), idxs in buckets.items():
        x0, y0 = tx / n, ty / n
        rect = (x0 - buf, y0 - buf, x0 + 1 / n + buf, y0 + 1 / n + buf)
        by_layer: dict[str, list] = defaultdict(list)
        for i in idxs:
            g = shapes[i]
            if g.geom_type == "Point":
                # A label point goes in its own tile only, never in a neighbor's buffer (no doubled labels).
                if not (x0 <= g.x < x0 + 1 / n and y0 <= g.y < y0 + 1 / n):
                    continue
                clipped = g
            elif g.geom_type in ("LineString", "MultiLineString"):
                try:
                    clipped = shapely.clip_by_rect(g, *rect)
                except shapely.errors.GEOSException:
                    clipped = None
            else:
                clipped = _clip(g, rect)
            if clipped is None:
                skipped += 1
                continue
            if clipped.is_empty:
                continue
            local = shapely.transform(clipped, lambda c, x0=x0, y0=y0: (c - (x0, y0)) * scale)
            enc = _encode(local)
            if enc:
                by_layer[features[i].layer].append((i + 1, enc[0], features[i].props, enc[1]))
        body = b"".join(encode_layer(by_layer[name], name) for name in layer_order if by_layer.get(name))
        if body:
            out[(tx, ty)] = gzip.compress(body, compresslevel=9)
    return out, skipped


def write_mbtiles(out: Path, features: list[Feature], *, name: str, minzoom: int, maxzoom: int,
                  layer_order: list[str], fields: dict[str, dict[str, str]], extra_meta: dict[str, str],
                  bounds=CHICAGO_BOUNDS, log=None) -> TileStats:
    """Write every zoom beside ``out`` and rename over it only when finished (the endpoint never reads a half
    file; a failed build keeps the previous tiles serving)."""
    stats = TileStats()
    t0 = time.monotonic()
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    for z in range(minzoom, maxzoom + 1):
        tiles, stats.unclipped[z] = tiles_for_zoom(features, z, maxzoom, layer_order, bounds)
        flip = (1 << z) - 1
        db.executemany("INSERT INTO tiles VALUES (?,?,?,?)", [(z, x, flip - y, d) for (x, y), d in tiles.items()])
        sizes = [len(d) for d in tiles.values()]
        stats.tiles[z], stats.bytes_gz[z], stats.max_tile_gz[z] = len(sizes), sum(sizes), max(sizes, default=0)
        if log:
            log.info("%s z%d: %d tiles, %.2f MB, max %.1f KB", name, z, len(sizes), sum(sizes) / 1e6,
                     max(sizes, default=0) / 1e3)
    w, s, e, n_ = bounds
    meta = {
        "name": name, "format": "pbf", "minzoom": str(minzoom), "maxzoom": str(maxzoom),
        "bounds": f"{w},{s},{e},{n_}",
        "json": json.dumps({"vector_layers": [{"id": k, "fields": v} for k, v in fields.items()]}),
        "pieces_unclipped": str(sum(stats.unclipped.values())),
        **extra_meta,
    }
    db.executemany("INSERT INTO metadata VALUES (?,?)", list(meta.items()))
    db.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")
    db.commit()
    db.close()
    tmp.replace(out)
    stats.seconds = time.monotonic() - t0
    return stats


def read_tile(path: Path, z: int, x: int, y: int) -> bytes | None:
    """One gzipped tile (XYZ y) or None."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, (1 << z) - 1 - y),
        ).fetchone()
    finally:
        db.close()
    return row[0] if row else None


def mercator_meters_per_unit(lat: float) -> float:
    """Ground metres per unit-Mercator unit at a latitude (for tolerances stated in metres)."""
    return 40_075_016.686 * math.cos(math.radians(lat))


__all__ = ["Feature", "TileStats", "to_mercator", "tiles_for_zoom", "write_mbtiles", "read_tile", "tile_limit",
           "CHICAGO_BOUNDS", "LineString", "MultiPolygon"]
