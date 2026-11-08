"""Serving the new UI's map tiles: ``GET /api/map/tiles/{base|zoning}/{z}/{x}/{y}.mvt`` and
``GET /api/map/info``.

404 = that tile file isn't installed (the map says so and keeps working), 204 = an empty tile, otherwise the
gzipped tile. The files change only when rebuilt, so a day of caching is safe (as Discovery's parcels, Item 68).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.map_tiles.tiler import read_tile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/map", tags=["map"])

_TILESETS = ("base", "zoning")


def _path(name: str) -> Path:
    from backend.config import get_settings

    s = get_settings()
    return {"base": s.map_base_tiles_path, "zoning": s.map_zoning_tiles_path}[name]


_meta_cache: dict[tuple[str, float], dict | None] = {}


def tileset_meta(name: str) -> dict | None:
    """The installed file's metadata, or None; re-read only when the file changes."""
    path = _path(name)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    key = (str(path), mtime)
    if key not in _meta_cache:
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                meta = dict(db.execute("SELECT name, value FROM metadata").fetchall())
            finally:
                db.close()
            _meta_cache[key] = meta if meta.get("format") == "pbf" else None
        except sqlite3.Error as exc:
            log.warning("map tiles: unreadable %s: %s", path, exc)
            _meta_cache[key] = None
    return _meta_cache[key]


@router.get("/info")
def map_info() -> dict:
    """Which tile sets are installed, their zooms and build dates (the map reads this once)."""
    from backend.config import get_settings
    from backend.discovery.parcel_tiles import tiles_info

    out: dict[str, dict | None] = {}
    p = tiles_info(get_settings().discovery_tiles_path)
    # Discovery's parcel outlines (Item 68) are the map's parcel layer; same file, same endpoint.
    out["parcels"] = None if p is None else {
        "minZoom": int(p.get("minzoom", 14)), "maxZoom": int(p.get("maxzoom", 16)), "builtAt": p.get("built_at"),
    }
    for name in _TILESETS:
        m = tileset_meta(name)
        out[name] = None if m is None else {
            "minZoom": int(m.get("minzoom", 0)), "maxZoom": int(m.get("maxzoom", 16)),
            "builtAt": m.get("built_at"),
        }
    return out


@router.get("/tiles/{name}/{z}/{x}/{y}.mvt")
def map_tile(name: str, z: int, x: int, y: int) -> Response:
    if name not in _TILESETS:
        raise HTTPException(status_code=404, detail="unknown tile set")
    path = _path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} tiles not installed")
    if not (0 <= z <= 22 and 0 <= x < (1 << z) and 0 <= y < (1 << z)):
        raise HTTPException(status_code=400, detail="tile out of range")
    data = read_tile(path, z, x, y)
    headers = {"Cache-Control": "public, max-age=86400"}
    if data is None:
        return Response(status_code=204, headers=headers)
    headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type="application/vnd.mapbox-vector-tile", headers=headers)


@router.get("/lot")
def map_lot(pin10: str) -> dict:
    """The outline the new map draws for one lot (Item 92): the County's full-precision 2021 outline when it still
    matches PTAXSIM's newest one, else PTAXSIM's. Drawing only; the Profile's land area reads PTAXSIM as before.
    404 when PTAXSIM has no outline for the PIN10."""
    import shapely
    from shapely import wkt as shapely_wkt
    from shapely.geometry import mapping

    from backend.config import get_settings
    from backend.map_tiles.county_outlines import best_outline, default_outlines

    digits = "".join(ch for ch in pin10 if ch.isdigit())
    if len(digits) != 10:
        raise HTTPException(status_code=400, detail="pin10 must be 10 digits")
    path = get_settings().ptaxsim_db_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="no outline")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT geometry FROM pin_geometry_raw WHERE pin10 = ? ORDER BY end_year DESC LIMIT 1", (digits,)
        ).fetchone()
    finally:
        db.close()
    if not row:
        raise HTTPException(status_code=404, detail="no outline")
    ptaxsim = shapely_wkt.loads(row[0])
    if not ptaxsim.is_valid:
        ptaxsim = shapely.make_valid(ptaxsim)
    geom, source = best_outline(digits, ptaxsim, default_outlines())
    return {"pin10": digits, "source": source, "geometry": mapping(geom)}
