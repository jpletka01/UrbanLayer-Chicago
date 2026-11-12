"""Parcel-shape vector tiles for the Discovery map (WS8 Phase 2, decision Item 68).

Writes Mapbox Vector Tiles (MVT v2) of County parcel outlines into one MBTiles file (SQLite), with no
tile tool to install: the protobuf encoding is small enough to write by hand, and shapely does the
clipping and simplification. The tiles hold geometry and the PIN only. Which parcels a search matched
is NOT baked in: the map colors matches by PIN (Mapbox feature-state), so one tile set serves every
query and caches forever between index rebuilds.

Sources: parcels (PIN10) from the Discovery index, so the tiles cover exactly what Discovery can return;
outlines from PTAXSIM ``pin_geometry_raw`` (the latest year per PIN10), the same polygons the Profile
draws. A PIN10 with no polygon is left out and counted.

The monthly index rebuild builds the file after the index (``index_build``, unless ``--no-tiles``). By hand:

    PYTHONPATH=. python -m backend.discovery.parcel_tiles [--index <discovery_index.db>] \\
        [--community-areas 22,24] [--out <parcel_tiles.mbtiles>]
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import shapely
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from shapely import wkt as shapely_wkt
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient

from backend.discovery.lot_facts import measure_bands

log = logging.getLogger(__name__)

EXTENT = 4096
# Clip each feature a little past its tile so outline strokes don't show seams at tile edges.
BUFFER = 64
MIN_ZOOM = 14  # the map draws outlines from zoom 14; below that it keeps its dots
MAX_ZOOM = 16
LAYER = "parcels"


# ---------------------------------------------------------------- MVT encoding (protobuf by hand)


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _key(field_no: int, wire: int) -> bytes:
    return _varint((field_no << 3) | wire)


def _len_field(field_no: int, payload: bytes) -> bytes:
    return _key(field_no, 2) + _varint(len(payload)) + payload


def _zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 31)


def _command(cmd: int, count: int) -> int:
    return (count << 3) | cmd


def _ring_commands(ring: np.ndarray, cursor: list[int]) -> list[int]:
    """MoveTo + LineTo... + ClosePath for one ring of integer tile coordinates (closing point dropped)."""
    pts = ring[:-1] if len(ring) > 1 and (ring[0] == ring[-1]).all() else ring
    out = [_command(1, 1)]
    x, y = int(pts[0][0]), int(pts[0][1])
    out += [_zigzag(x - cursor[0]), _zigzag(y - cursor[1])]
    cursor[0], cursor[1] = x, y
    out.append(_command(2, len(pts) - 1))
    for px, py in pts[1:]:
        px, py = int(px), int(py)
        out += [_zigzag(px - cursor[0]), _zigzag(py - cursor[1])]
        cursor[0], cursor[1] = px, py
    out.append(_command(7, 1))
    return out


def _clean_ring(coords: np.ndarray) -> np.ndarray | None:
    """Round to the tile grid and drop repeated points; None when fewer than 3 distinct points remain."""
    pts = np.rint(coords).astype(np.int64)
    keep = np.ones(len(pts), dtype=bool)
    keep[1:] = (pts[1:] != pts[:-1]).any(axis=1)
    pts = pts[keep]
    if len(pts) and not (pts[0] == pts[-1]).all():
        pts = np.vstack([pts, pts[:1]])
    if len(pts) < 4:
        return None
    x, y = pts[:, 0].astype(float), pts[:, 1].astype(float)
    if abs(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1])) < 1:  # zero area after rounding
        return None
    return pts


def _polygon_geometry(geom) -> list[int]:
    """Encode a (Multi)Polygon already in tile coordinates. MVT wants exterior rings with positive area in
    tile space (y down), which is shapely's sign=1.0 orientation on these coordinates."""
    cursor = [0, 0]
    out: list[int] = []
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for poly in polys:
        if poly.is_empty:
            continue
        poly = orient(poly, sign=1.0)
        ext = _clean_ring(np.asarray(poly.exterior.coords))
        if ext is None:
            continue
        out += _ring_commands(ext, cursor)
        for hole in poly.interiors:
            h = _clean_ring(np.asarray(hole.coords))
            if h is not None:
                out += _ring_commands(h, cursor)
    return out


def _packed(values: list[int]) -> bytes:
    return b"".join(_varint(v) for v in values)


POLYGON, LINESTRING = 3, 2


def encode_layer(features: list[tuple], name: str = LAYER) -> bytes:
    """One MVT layer from (id, geometry commands, string properties[, geometry type]) tuples; the type defaults
    to POLYGON (the parcel outlines). The map tiles (``backend.map_tiles``) pass LINESTRING for roads."""
    keys: dict[str, int] = {}
    values: dict[str, int] = {}
    body = bytearray()
    for fid, geometry, props, *rest in features:
        gtype = rest[0] if rest else POLYGON
        tags: list[int] = []
        for k, v in props.items():
            tags += [keys.setdefault(k, len(keys)), values.setdefault(v, len(values))]
        feat = _key(1, 0) + _varint(fid)
        if tags:
            feat += _len_field(2, _packed(tags))
        feat += _key(3, 0) + _varint(gtype)
        feat += _len_field(4, _packed(geometry))
        body += _len_field(2, feat)
    layer = _key(15, 0) + _varint(2) + _len_field(1, name.encode())
    layer += bytes(body)
    for k in keys:
        layer += _len_field(3, k.encode())
    for v in values:
        layer += _len_field(4, _len_field(1, v.encode()))  # Value.string_value
    layer += _key(5, 0) + _varint(EXTENT)
    return _len_field(3, layer)  # Tile.layers


# ---------------------------------------------------------------- projection and tiling


def _to_unit_mercator(coords: np.ndarray) -> np.ndarray:
    """lon/lat → Web Mercator in [0, 1] (x right, y down), the space every zoom's tile grid divides."""
    lon, lat = coords[:, 0], np.clip(coords[:, 1], -85.0511, 85.0511)
    x = (lon + 180.0) / 360.0
    s = np.sin(np.radians(lat))
    y = 0.5 - np.log((1 + s) / (1 - s)) / (4 * math.pi)
    return np.column_stack([x, y])


@dataclass
class Parcel:
    pin10: str
    geom: Polygon | MultiPolygon  # unit-Mercator
    props: dict[str, str]


@dataclass
class BuildStats:
    parcels: int = 0
    no_polygon: int = 0
    unclipped: dict[int, int] = field(default_factory=dict)
    tiles: dict[int, int] = field(default_factory=dict)
    bytes_gz: dict[int, int] = field(default_factory=dict)
    max_tile_gz: dict[int, int] = field(default_factory=dict)
    seconds: float = 0.0


def _clip(geom, rect):
    """Clip to the tile rectangle. A ring that simplification collapsed below 4 points makes GEOS refuse: retry
    on the repaired shape, else None (the caller counts it)."""
    try:
        return shapely.clip_by_rect(geom, *rect)
    except shapely.errors.GEOSException:
        try:
            fixed = _polygonal(shapely.make_valid(geom))
            return shapely.clip_by_rect(fixed, *rect) if fixed is not None else None
        except shapely.errors.GEOSException:
            return None


def tiles_for_zoom(parcels: list[Parcel], z: int, layer: str = LAYER) -> tuple[dict[tuple[int, int], bytes], int]:
    """Gzipped tiles at zoom z, and how many (parcel, tile) pieces could not be clipped and were left out."""
    n = 1 << z
    scale = n * EXTENT
    buf = BUFFER / scale
    tol = 1.0 / scale  # one tile unit: invisible at this zoom
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    simplified: list = []
    for i, p in enumerate(parcels):
        g = p.geom.simplify(tol, preserve_topology=True) if z < MAX_ZOOM else p.geom
        simplified.append(g)
        minx, miny, maxx, maxy = g.bounds
        # Include the tiles whose buffer reaches the parcel, so outlines continue across tile edges.
        for tx in range(int((minx - buf) * n), int((maxx + buf) * n) + 1):
            for ty in range(int((miny - buf) * n), int((maxy + buf) * n) + 1):
                buckets[(tx, ty)].append(i)
    out: dict[tuple[int, int], bytes] = {}
    skipped = 0
    for (tx, ty), idxs in buckets.items():
        x0, y0 = tx / n, ty / n
        rect = (x0 - buf, y0 - buf, x0 + 1 / n + buf, y0 + 1 / n + buf)
        feats = []
        for i in idxs:
            clipped = _clip(simplified[i], rect)
            if clipped is None:
                skipped += 1
                continue
            if clipped.is_empty:
                continue
            local = shapely.transform(clipped, lambda c, x0=x0, y0=y0: (c - (x0, y0)) * scale)
            if local.geom_type not in ("Polygon", "MultiPolygon"):
                local = MultiPolygon([g for g in getattr(local, "geoms", []) if g.geom_type == "Polygon"])
            geometry = _polygon_geometry(local)
            if geometry:
                feats.append((int(parcels[i].pin10), geometry, parcels[i].props))
        if feats:
            out[(tx, ty)] = gzip.compress(encode_layer(feats, layer), compresslevel=9)
    return out, skipped


# ---------------------------------------------------------------- inputs and MBTiles output


def _polygonal(g):
    """The polygon parts of a geometry (make_valid can return a collection with lines), or None."""
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    return MultiPolygon(parts) if parts else None


def load_parcels(
    index_path: Path, ptaxsim_path: Path, community_areas: list[int] | None, county_outlines: Path | None = None,
    stats: dict | None = None,
) -> tuple[list[Parcel], int, int]:
    """PIN10s from the Discovery index (optionally a few community areas) with their latest PTAXSIM outline.
    Returns the parcels, the PIN10s with no usable outline, and the outlines repaired with make_valid.

    With ``county_outlines`` (the local copy of the County's full-precision 2021 layer, Item 92) a lot draws the
    County's outline where it still matches PTAXSIM's newest one; PTAXSIM rounds to about 1 m, which makes
    straight edges step. ``stats["county_outlines"]`` counts the lots that use it."""
    from backend.map_tiles.county_outlines import Outlines, still_matches

    county = Outlines(county_outlines) if county_outlines else None
    used = 0
    idx = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    want: dict[str, dict[str, str]] = {}
    rows = idx.execute("SELECT pin, attrs, regions FROM parcels")
    regions_wanted = {f"neighborhood:{ca}" for ca in community_areas} if community_areas else None
    for pin, attrs, regions in rows:
        if regions_wanted and not regions_wanted.intersection(json.loads(regions)):
            continue
        p = pin.replace("-", "")
        pin10 = p[:10]
        # The base parcel (suffix 0000) speaks for the lot when the index has it; else the first row seen.
        if pin10 in want and p[10:] != "0000":
            continue
        a = json.loads(attrs)
        props = {"g": str(a.get("zoning_group"))} if a.get("zoning_group") else {}
        props.update(measure_bands(a))  # Item 104: the Explore map's measures, banded
        want[pin10] = props
    idx.close()

    geo = sqlite3.connect(f"file:{ptaxsim_path}?mode=ro", uri=True)
    pins = sorted(want)
    parcels: list[Parcel] = []
    repaired = 0
    for i in range(0, len(pins), 900):
        chunk = pins[i:i + 900]
        marks = ",".join("?" * len(chunk))
        latest: dict[str, str] = {}
        for pin10, text in geo.execute(
            f"SELECT pin10, geometry FROM pin_geometry_raw WHERE pin10 IN ({marks}) ORDER BY end_year ASC", chunk
        ):
            latest[pin10] = text  # ascending end_year: the last one written wins
        precise = county.many(list(latest)) if county else {}
        for pin10, text in latest.items():
            try:
                g = shapely_wkt.loads(text)
                if not g.is_empty and not g.is_valid:
                    # The County layer has a few broken rings (one with 3 points stops GEOS clipping).
                    g = _polygonal(shapely.make_valid(g))
                    repaired += 1
            except (shapely.errors.GEOSException, ValueError):  # unreadable even after repair: no outline
                continue
            if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            c = precise.get(pin10)
            if c is not None and still_matches(c, g):
                c = _polygonal(c)
                if c is not None and not c.is_empty:
                    g = c
                    used += 1
            g = shapely.transform(g, _to_unit_mercator)
            parcels.append(Parcel(pin10, g, want[pin10]))
    geo.close()
    if stats is not None:
        stats["county_outlines"] = used
    return parcels, len(want) - len(parcels), repaired


def write_mbtiles(
    out: Path, parcels: list[Parcel], minzoom: int, maxzoom: int, extra_meta: dict[str, str] | None = None,
) -> BuildStats:
    stats = BuildStats(parcels=len(parcels))
    t0 = time.monotonic()
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    for z in range(minzoom, maxzoom + 1):
        tiles, stats.unclipped[z] = tiles_for_zoom(parcels, z)
        flip = (1 << z) - 1
        db.executemany(
            "INSERT INTO tiles VALUES (?,?,?,?)", [(z, x, flip - y, data) for (x, y), data in tiles.items()]
        )
        sizes = [len(d) for d in tiles.values()]
        stats.tiles[z] = len(sizes)
        stats.bytes_gz[z] = sum(sizes)
        stats.max_tile_gz[z] = max(sizes, default=0)
        log.info("z%d: %d tiles, %.1f MB, max %.0f KB", z, len(sizes), sum(sizes) / 1e6, max(sizes, default=0) / 1e3)
    meta = {
        "name": "parcels", "format": "pbf", "minzoom": str(minzoom), "maxzoom": str(maxzoom),
        "json": json.dumps({"vector_layers": [{"id": LAYER, "fields": {"g": "String", "r": "String", "s": "String", "y": "String", "u": "String"}}]}),
        "pieces_unclipped": str(sum(stats.unclipped.values())),
        **(extra_meta or {}),
    }
    db.executemany("INSERT INTO metadata VALUES (?,?)", list(meta.items()))
    db.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")
    db.commit()
    db.close()
    stats.seconds = time.monotonic() - t0
    return stats


def build_file(
    index_path: Path, ptaxsim_path: Path, out: Path, *, community_areas: list[int] | None = None,
    minzoom: int = MIN_ZOOM, maxzoom: int = MAX_ZOOM, county_outlines: Path | None = None,
) -> dict:
    """Build the tile file for an index and swap it in atomically: written beside ``out`` and renamed over it
    only when complete, so the endpoint never reads a half-written file and a failed build leaves the previous
    tiles serving. The metadata records the build date, the index version it was built from and the counts of
    what was left out, for data health and the registry. Returns that summary."""
    from datetime import date

    from backend.discovery.parcel_index import read_meta

    meta = read_meta(index_path)
    t0 = time.monotonic()
    if county_outlines is None:
        from backend.config import get_settings

        county_outlines = get_settings().county_outlines_path  # absent file = PTAXSIM outlines only
    extra: dict = {}
    parcels, missing, repaired = load_parcels(index_path, ptaxsim_path, community_areas, county_outlines, extra)
    if not parcels:
        raise RuntimeError(f"no parcel outlines for {index_path}: refusing to replace the tile file with an empty one")
    count = len(parcels)
    tmp = out.with_name(out.name + ".tmp")
    stats = write_mbtiles(tmp, parcels, minzoom, maxzoom, extra_meta={
        "built_at": date.today().isoformat(),
        "index_version": meta.data_version if meta else "",
        "parcels": str(count),
        "pin10_without_outline": str(missing),
        "outlines_repaired": str(repaired),
        "county_outlines": str(extra.get("county_outlines", 0)),
    })
    tmp.replace(out)
    grid: dict | str
    try:  # the zoomed-out grid (Item 104); a failure here never costs the lot tiles
        grid = build_grid_file(index_path, grid_path(out))
    except Exception as exc:  # noqa: BLE001
        log.warning("grid tiles not built: %s", exc)
        grid = f"failed: {exc}"
    summary = {
        "grid": grid,
        "parcels_with_outline": count, "pin10_without_outline": missing, "outlines_repaired": repaired,
        "county_outlines": extra.get("county_outlines", 0),
        "pieces_unclipped": stats.unclipped, "tiles": stats.tiles,
        "mb_gz": {z: round(b / 1e6, 2) for z, b in stats.bytes_gz.items()},
        "max_tile_kb_gz": {z: round(b / 1e3, 1) for z, b in stats.max_tile_gz.items()},
        "seconds": round(time.monotonic() - t0, 1), "file_mb": round(out.stat().st_size / 1e6, 2),
    }
    log.info("parcel tiles: %s", json.dumps(summary))
    return summary


# ---------------------------------------------------------------- the zoomed-out grid (Item 104)

GRID_LAYER = "grid"
GRID_MIN_ZOOM = 10
GRID_MAX_ZOOM = 13
GRID_DLAT = 0.0018  # about 200 m: roughly a Chicago block (a 1/8 mile)
GRID_DLON = 0.0024
GRID_MIN_LOTS = 3
GRID_MIN_KNOWN = 0.5  # a cell's measure is drawn only when at least half its lots have it


def grid_cells(rows) -> list[Parcel]:
    """The city as squares of about a block, each carrying its lots' measure bands (the lot tiles' r/s/y/u/l/g):
    the median band for room, lot size and last sale, the most common for land use and zoning family. A cell
    with fewer than 3 lots is left out; a measure known for under half a cell's lots is left off it (drawn dotted),
    so a few known lots never speak for the block. Display only, like the lot bands (Item 104)."""
    from collections import Counter

    from backend.discovery.lot_facts import measure_bands

    cells: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for pin, lat, lon, attrs in rows:
        if lat is None or lon is None or not pin.replace("-", "").endswith("0000"):
            continue
        bands = measure_bands(attrs)
        if attrs.get("zoning_group"):
            bands["g"] = str(attrs["zoning_group"])
        cells[(math.floor(lat / GRID_DLAT), math.floor(lon / GRID_DLON))].append(bands)
    out: list[Parcel] = []
    for (iy, ix), lots in cells.items():
        if len(lots) < GRID_MIN_LOTS:
            continue
        props: dict[str, str] = {"n": str(len(lots))}
        for key in ("r", "s", "y"):
            vals = [b[key] for b in lots if key in b]
            nums = sorted(int(v) for v in vals if v.isdigit())
            named = [v for v in vals if not v.isdigit()]  # room's "own rules", "open space", "transport"
            if len(nums) >= GRID_MIN_KNOWN * len(lots):
                props[key] = str(nums[len(nums) // 2])
            elif named and len(vals) >= GRID_MIN_KNOWN * len(lots) and len(named) >= len(nums):
                props[key] = Counter(named).most_common(1)[0][0]
        for key in ("u", "l", "g"):
            vals = [b[key] for b in lots if key in b]
            if len(vals) >= GRID_MIN_KNOWN * len(lots):
                props[key] = Counter(vals).most_common(1)[0][0]
        x0, y0 = ix * GRID_DLON, iy * GRID_DLAT
        g = shapely.transform(shapely.box(x0, y0, x0 + GRID_DLON, y0 + GRID_DLAT), _to_unit_mercator)
        out.append(Parcel(str((iy + 100_000) * 1_000_000 + (ix + 500_000)), g, props))
    return out


def build_grid_file(index_path: Path, out: Path) -> dict:
    """Write the grid tiles (zooms 10-13) beside ``out`` and swap them in atomically."""
    from datetime import date

    from backend.discovery.parcel_index import iter_parcel_rows, read_meta

    t0 = time.monotonic()
    cells = grid_cells((pin, lat, lon, attrs) for pin, lat, lon, attrs, _ in iter_parcel_rows(index_path))
    if not cells:
        raise RuntimeError(f"no grid cells from {index_path}: refusing to write an empty grid")
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    sizes: dict[int, list[int]] = {}
    for z in range(GRID_MIN_ZOOM, GRID_MAX_ZOOM + 1):
        tiles, _ = tiles_for_zoom(cells, z, GRID_LAYER)
        flip = (1 << z) - 1
        db.executemany("INSERT INTO tiles VALUES (?,?,?,?)", [(z, x, flip - y, d) for (x, y), d in tiles.items()])
        sizes[z] = [len(d) for d in tiles.values()]
    meta = read_meta(index_path)
    db.executemany("INSERT INTO metadata VALUES (?,?)", list({
        "name": "grid", "format": "pbf", "minzoom": str(GRID_MIN_ZOOM), "maxzoom": str(GRID_MAX_ZOOM),
        "json": json.dumps({"vector_layers": [{"id": GRID_LAYER, "fields": {k: "String" for k in "nrsyug"}}]}),
        "built_at": date.today().isoformat(), "index_version": meta.data_version if meta else "", "cells": str(len(cells)),
    }.items()))
    db.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")
    db.commit()
    db.close()
    tmp.replace(out)
    summary = {"cells": len(cells), "seconds": round(time.monotonic() - t0, 1),
               "kb_gz": {z: round(sum(v) / 1e3) for z, v in sizes.items()},
               "max_tile_kb_gz": {z: round(max(v, default=0) / 1e3, 1) for z, v in sizes.items()}}
    log.info("grid tiles: %s", json.dumps(summary))
    return summary


def grid_path(tiles_path: Path) -> Path:
    """The grid file lives beside the lot tiles."""
    return tiles_path.with_name("parcel_grid.mbtiles")


_info_cache: dict[tuple[str, float], dict | None] = {}


def tiles_info(path: Path) -> dict | None:
    """The installed tile file's metadata (build date, zooms, counts, index version), or None when there is no
    usable file. Re-read only when the file changes."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    key = (str(path), mtime)
    if key not in _info_cache:
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                meta = dict(db.execute("SELECT name, value FROM metadata").fetchall())
            finally:
                db.close()
            _info_cache.clear()
            _info_cache[key] = meta if meta.get("format") == "pbf" else None
        except sqlite3.Error as exc:
            log.warning("parcel tiles: unreadable %s: %s", path, exc)
            return None
    return _info_cache[key]


# ---------------------------------------------------------------- serving


router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/tiles/{z}/{x}/{y}.mvt")
def parcel_tile(z: int, x: int, y: int) -> Response:
    """One parcel-outline tile. 404 when no tile file is installed (the map keeps its dots); 204 for a tile
    with no parcels. The file changes only when it is rebuilt, so a day of caching is safe."""
    from backend.config import get_settings

    return _serve_tile(get_settings().discovery_tiles_path, z, x, y, "parcel tiles not installed")


@router.get("/grid/{z}/{x}/{y}.mvt")
def grid_tile(z: int, x: int, y: int) -> Response:
    """One tile of the zoomed-out grid (zooms 10-13, Item 104); 404 when the grid file isn't installed."""
    from backend.config import get_settings

    return _serve_tile(grid_path(get_settings().discovery_tiles_path), z, x, y, "grid tiles not installed")


def _serve_tile(path: Path, z: int, x: int, y: int, missing: str) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail=missing)
    if not (0 <= z <= 22 and 0 <= x < (1 << z) and 0 <= y < (1 << z)):
        raise HTTPException(status_code=400, detail="tile out of range")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, (1 << z) - 1 - y),
        ).fetchone()
    finally:
        db.close()
    headers = {"Cache-Control": "public, max-age=86400"}
    if row is None:
        return Response(status_code=204, headers=headers)
    headers["Content-Encoding"] = "gzip"
    return Response(content=row[0], media_type="application/vnd.mapbox-vector-tile", headers=headers)


def main() -> None:
    from backend.config import get_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", type=Path, default=None)
    ap.add_argument("--community-areas", default="")
    ap.add_argument("--out", type=Path, default=None, help="default: settings.discovery_tiles_path")
    ap.add_argument("--minzoom", type=int, default=MIN_ZOOM)
    ap.add_argument("--maxzoom", type=int, default=MAX_ZOOM)
    ap.add_argument("--grid-only", action="store_true", help="rebuild only the zoomed-out grid (Item 104)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    cas = [int(c) for c in args.community_areas.split(",") if c.strip()] or None
    if args.grid_only:
        out = args.out or settings.discovery_tiles_path
        print(json.dumps(build_grid_file(args.index or settings.discovery_index_path, grid_path(out)), indent=1))
        return
    summary = build_file(
        args.index or settings.discovery_index_path, settings.ptaxsim_db_path, args.out or settings.discovery_tiles_path,
        community_areas=cas, minzoom=args.minzoom, maxzoom=args.maxzoom,
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
