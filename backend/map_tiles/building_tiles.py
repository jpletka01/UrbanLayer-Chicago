"""Building heights for the map's 3D mode (Phase 7 M6, decision Items 105-106).

Cook County's 2022 building footprints, made from its spring-2022 LiDAR: each polygon carries its ground
elevation and its highest LiDAR return, so ``Height`` is a measured height in feet (the roof's highest point,
not its roof line; structures under 7 ft are not in it). Only buildings whose interior point is inside Chicago
(the City's 98 neighborhoods) are kept.

    PYTHONPATH=. python -m backend.map_tiles.building_tiles [--offline] [--out <map_buildings.mbtiles>]

The fetched copy is kept in ``backend/data/map_sources/county_buildings_2022.db``; ``--offline`` rebuilds from it.
A read that comes back short is refused (nothing written), like the other map sources.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import shapely
from shapely.geometry import shape

from backend.map_tiles.tiler import CHICAGO_BOUNDS, Feature, to_mercator, write_mbtiles

log = logging.getLogger(__name__)

SERVICE = "https://gis.cookcountyil.gov/traditional/rest/services/buildingFootprint_2022/MapServer/0/query"
SOURCE_DB = "county_buildings_2022.db"
LAYER = "building"
MIN_ZOOM = 14  # 3D is a close-up mode; the city view has no buildings
MAX_ZOOM = 16
# Measured 2026-11-10 (Item 105): 1,254,045 polygons in Chicago's bounding box, 779,930 inside the city.
MIN_IN_BBOX = 1_100_000
MIN_IN_CITY = 700_000
CHUNK = 1000


def fetch(dest: Path, *, client: httpx.Client | None = None) -> int:
    """Copy every County building polygon in Chicago's bounding box into ``dest`` (SQLite). Raises on a short read."""
    own = client is None
    c = client or httpx.Client(timeout=120)
    try:
        w, s, e, n = CHICAGO_BOUNDS
        r = c.get(SERVICE, params={"where": "1=1", "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope",
                                   "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true",
                                   "f": "json"})
        r.raise_for_status()
        ids = sorted(r.json().get("objectIds") or [])
        if len(ids) < MIN_IN_BBOX:
            raise RuntimeError(f"County buildings: {len(ids)} ids in Chicago's box, expected {MIN_IN_BBOX}+")
        rows = []
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            for attempt in range(5):
                try:
                    resp = c.post(SERVICE, data={"objectIds": ",".join(map(str, chunk)), "f": "geojson",
                                                 "outFields": "OBJECTID,Ground_Z,Max_Point,Height", "outSR": 4326,
                                                 "geometryPrecision": 7})
                    resp.raise_for_status()
                    feats = resp.json()["features"]
                    break
                except (httpx.HTTPError, KeyError, ValueError):
                    if attempt == 4:
                        raise
                    time.sleep(2 ** attempt)
            for f in feats:
                p = f.get("properties") or {}
                if f.get("geometry") and p.get("Height") is not None:
                    rows.append((p["OBJECTID"], p.get("Ground_Z"), p.get("Max_Point"), p["Height"],
                                 shapely.to_wkb(shape(f["geometry"]))))
        if len(rows) < MIN_IN_BBOX:
            raise RuntimeError(f"County buildings: read {len(rows)}, expected {MIN_IN_BBOX}+")
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.unlink(missing_ok=True)
        db = sqlite3.connect(tmp)
        db.execute("CREATE TABLE buildings (oid INTEGER PRIMARY KEY, ground_ft REAL, max_ft REAL, height_ft REAL, wkb BLOB)")
        db.executemany("INSERT INTO buildings VALUES (?,?,?,?,?)", rows)
        db.execute("CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO meta VALUES ('fetched', ?)", (date.today().isoformat(),))
        db.commit()
        db.close()
        tmp.replace(dest)
        return len(rows)
    finally:
        if own:
            c.close()


def city_outline():
    """Chicago as the union of the City's 98 neighborhoods (committed with Discovery, Item 104)."""
    path = Path(__file__).resolve().parents[1] / "discovery" / "neighborhoods.geojson"
    feats = json.loads(path.read_text())["features"]
    return shapely.union_all([shape(f["geometry"]) for f in feats])


def build_features(src: Path) -> tuple[list[Feature], dict[str, int]]:
    """One extrusion feature per County building inside the city, height in whole feet (``h``)."""
    db = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT height_ft, wkb FROM buildings").fetchall()
    finally:
        db.close()
    geoms = shapely.from_wkb([r[1] for r in rows])
    heights = np.array([r[0] for r in rows], dtype=float)
    inside = shapely.contains_xy(city_outline(), *shapely.get_coordinates(shapely.point_on_surface(geoms)).T)
    counts = {"in_box": len(rows), "in_city": int(inside.sum()), "invalid_fixed": 0, "dropped_empty": 0}
    if counts["in_city"] < MIN_IN_CITY:
        raise RuntimeError(f"County buildings: {counts['in_city']} inside the city, expected {MIN_IN_CITY}+")
    feats: list[Feature] = []
    for g, h in zip(geoms[inside], heights[inside]):
        if not g.is_valid:
            g = shapely.make_valid(g)
            counts["invalid_fixed"] += 1
            polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")]
            g = shapely.union_all(polys) if polys else None
        if g is None or g.is_empty:
            counts["dropped_empty"] += 1
            continue
        feats.append(Feature(LAYER, to_mercator(g), {"h": str(int(round(h)))}, MIN_ZOOM))
    return feats, counts


def build_file(out: Path, *, offline: bool = False, minzoom: int = MIN_ZOOM, maxzoom: int = MAX_ZOOM) -> dict:
    t0 = time.monotonic()
    src = out.parent / "map_sources" / SOURCE_DB
    if not offline or not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        log.info("County buildings: fetched %d", fetch(src))
    feats, counts = build_features(src)
    stats = write_mbtiles(
        out, feats, name="map_buildings", minzoom=minzoom, maxzoom=maxzoom, layer_order=[LAYER],
        fields={LAYER: {"h": "Number"}},
        extra_meta={"built_at": date.today().isoformat(), "counts": json.dumps(counts),
                    "source": SERVICE.rsplit("/query", 1)[0], "vintage": "2022"},
        log=log,
    )
    summary = {
        "counts": counts, "tiles": stats.tiles,
        "mb_gz": {z: round(b / 1e6, 2) for z, b in stats.bytes_gz.items()},
        "max_tile_kb_gz": {z: round(b / 1e3, 1) for z, b in stats.max_tile_gz.items()},
        "pieces_unclipped": sum(stats.unclipped.values()),
        "seconds": round(time.monotonic() - t0, 1), "file_mb": round(out.stat().st_size / 1e6, 2),
    }
    log.info("map building tiles: %s", json.dumps(summary))
    return summary


def main() -> None:
    from backend.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="default: settings.map_buildings_tiles_path")
    ap.add_argument("--offline", action="store_true", help="rebuild from backend/data/map_sources/ only")
    ap.add_argument("--minzoom", type=int, default=MIN_ZOOM)
    ap.add_argument("--maxzoom", type=int, default=MAX_ZOOM)
    args = ap.parse_args()
    out = args.out or get_settings().map_buildings_tiles_path
    print(json.dumps(build_file(out, offline=args.offline, minzoom=args.minzoom, maxzoom=args.maxzoom), indent=1))


if __name__ == "__main__":
    main()
