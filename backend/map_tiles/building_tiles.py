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


# A County outline is drawn from LiDAR building points clustered into polygons, so touching buildings can merge into
# one outline with one height: its highest point. Where a tall outline (SPLIT_MIN_FT and up) covers two or more of the
# City's footprints and at least one has stories, it is split along them (owner's review, 616 W Diversey: a one-story
# building beside a 16-story tower was drawn 173 ft tall). The footprint with the most stories keeps the measured
# height; one with stories gets a height from them (`stories_ft`, capped at the measured one); one without is drawn
# low and marked not measured. What is left of the outline outside the footprints keeps the measured height when it
# is a real piece (REMAINDER_MIN_SQFT after a 1.5 m opening) touching the tallest footprint, is drawn low and not
# measured when it is a real piece elsewhere, and is dropped as slivers otherwise.
SPLIT_MIN_FT = 60.0
# The City's footprints can merge too (616 W Diversey: the 1926 tower's 2015 footprint covers the one-story shop next
# door). So a tall piece is also cut along the lots the Assessor classes as one-story buildings (2-02/2-03/2-04 houses,
# 5-17 one-story commercial); the cut is drawn at ONE_STORY_FT (the measured median of the City's one-story
# buildings, Item 105). Measured 2026-11-11: on one-story-class lots 80% of the City's recorded stories are 1 and 85%
# of the LiDAR heights are 25 ft or less; only 127 of 317,508 measured buildings there reach 60 ft (0.04%).
ONE_STORY_CLASSES = frozenset({"2-02", "2-03", "2-04", "5-17"})
ONE_STORY_FT = 22
ONE_STORY_MIN_SQFT = 400
ONE_STORY_MAX_SHARE = 0.8  # a cut covering more than this of the tall piece is the tall building itself: left alone
UNMEASURED_FT = 12
REMAINDER_MIN_SQFT = 2_000
_SQFT_PER_DEG2 = 364_000 * 271_000  # Chicago: feet per degree of latitude x of longitude
_OPEN_DEG = 1.4e-5  # about 1.5 m


def stories_ft(stories: int) -> float:
    """A height in feet from a story count: the inverse of Item 105's fit (3 ft + 14.75 ft a story up to 2 stories,
    14 ft a story above)."""
    return 3 + 14.75 * stories if stories <= 2 else 14.0 * stories


def _polys(g):
    if g is None or g.is_empty:
        return None
    if not g.is_valid:
        g = shapely.make_valid(g)
    parts = [p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")]
    if not parts:
        return None
    g = shapely.union_all(parts)
    return None if g.is_empty else g


def _load_city(path: Path | None):
    """The City's footprints (``lot_sources`` copy): their outlines, stories and a tree of their interior points."""
    if path is None or not path.exists():
        return None
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT stories, wkb FROM footprints").fetchall()
    finally:
        db.close()
    geoms = shapely.from_wkb([r[1] for r in rows])
    reps = shapely.point_on_surface(geoms)
    return geoms, [r[0] for r in rows], shapely.STRtree(reps)


def split_outline(outline, height: float, members: list[tuple[object, int | None]]) -> list[tuple[object, float, str]]:
    """``outline`` (a County polygon) split along the City ``members`` (outline, stories) inside it:
    [(piece, height_ft, kind)], kind "l" measured, "s" from stories, "u" not measured. Unsplit when it doesn't apply."""
    known = [s for _, s in members if s]
    if height < SPLIT_MIN_FT or len(members) < 2 or not known:
        return [(outline, height, "l")]
    anchor = max(range(len(members)), key=lambda i: ((members[i][1] or 0), shapely.area(members[i][0])))
    out: list[tuple[object, float, str]] = []
    taken = []
    anchor_piece = None
    for i, (g, st) in enumerate(members):
        piece = _polys(shapely.intersection(_polys(g), outline))
        if piece is None:
            continue
        taken.append(piece)
        if i == anchor:
            anchor_piece = piece
            out.append((piece, height, "l"))
        elif st:
            out.append((piece, min(height, stories_ft(st)), "s"))
        else:
            out.append((piece, float(UNMEASURED_FT), "u"))
    rest = _polys(shapely.difference(outline, shapely.union_all(taken))) if taken else outline
    if rest is not None:
        rest = _polys(rest.buffer(-_OPEN_DEG).buffer(_OPEN_DEG))
        for p in (getattr(rest, "geoms", [rest]) if rest is not None else []):
            if shapely.area(p) * _SQFT_PER_DEG2 < REMAINDER_MIN_SQFT:
                continue
            # Touching the tallest footprint: part of it (a newer wing, an outline drawn wider). Elsewhere it is one
            # of the low buildings the City didn't map: not measured.
            near = anchor_piece is not None and shapely.distance(p, anchor_piece) <= _OPEN_DEG
            out.append((p, height, "l") if near else (p, float(UNMEASURED_FT), "u"))
    return out or [(outline, height, "l")]


def one_story_lots(index_db: Path | None, ptaxsim: Path | None):
    """The outlines of the lots the Assessor classes as one-story buildings, as an STRtree and its geometries."""
    if index_db is None or ptaxsim is None or not index_db.exists() or not ptaxsim.exists():
        return None
    from backend.discovery.index_backfill import lot_outlines

    db = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    try:
        pins = set()
        for pin, attrs in db.execute("SELECT pin, attrs FROM parcels WHERE attrs LIKE '%\"class\"%'"):
            p = pin.replace("-", "")
            if p[10:] == "0000" and json.loads(attrs).get("class") in ONE_STORY_CLASSES:
                pins.add(p[:10])
    finally:
        db.close()
    geoms = [g for g in (_polys(g) for g in lot_outlines(ptaxsim, pins).values()) if g is not None]
    return (shapely.STRtree(geoms), geoms) if geoms else None


def cut_one_story(piece, height: float, lots) -> list[tuple[object, float, str]]:
    """``piece`` (a measured tall piece) cut along the one-story lots under it: [(piece, height_ft, kind)], kind "a"
    for a cut drawn at ONE_STORY_FT. Unchanged when nothing applies."""
    if lots is None or height < SPLIT_MIN_FT:
        return [(piece, height, "l")]
    tree, geoms = lots
    total = shapely.area(piece)
    cuts = []
    for i in tree.query(piece, predicate="intersects"):
        c = _polys(shapely.intersection(piece, geoms[i]))
        if c is not None and shapely.area(c) * _SQFT_PER_DEG2 >= ONE_STORY_MIN_SQFT:
            cuts.append(c)
    if not cuts:
        return [(piece, height, "l")]
    cut = shapely.union_all(cuts)
    if shapely.area(cut) > ONE_STORY_MAX_SHARE * total:
        return [(piece, height, "l")]
    out: list[tuple[object, float, str]] = [(c, float(ONE_STORY_FT), "a") for c in getattr(cut, "geoms", [cut])]
    rest = _polys(shapely.difference(piece, cut))
    if rest is not None:
        rest = _polys(rest.buffer(-_OPEN_DEG).buffer(_OPEN_DEG))
        for p in (getattr(rest, "geoms", [rest]) if rest is not None else []):
            if shapely.area(p) * _SQFT_PER_DEG2 >= REMAINDER_MIN_SQFT:
                out.append((p, height, "l"))
    return out


def _zoning_lookup(zoning: list[dict] | None):
    """A function: points -> (family, level) per point, from the City's zoning districts (layer 1)."""
    if not zoning:
        return None
    from backend.map_tiles.zoning_tiles import family, level

    geoms, props = [], []
    for f in zoning:
        g = _polys(shape(f["geometry"])) if f.get("geometry") else None
        if g is None:
            continue
        zc = ((f.get("properties") or {}).get("ZONE_CLASS") or "").strip()
        geoms.append(g)
        props.append((family(zc), level(zc)))
    tree = shapely.STRtree(geoms)

    def look(points) -> list[tuple[str, str] | None]:
        res: list[tuple[str, str] | None] = [None] * len(points)
        pi, gi = tree.query(points, predicate="within")
        for a, b in zip(pi, gi):
            if res[a] is None:
                res[a] = props[b]
        return res

    return look


def build_features(src: Path, *, city: Path | None = None, zoning: list[dict] | None = None,
                   one_story=None) -> tuple[list[Feature], dict[str, int]]:
    """One extrusion feature per County building inside the city (split along the City's footprints where a tall
    outline merged several, and along the Assessor's one-story lots), with ``h`` = height in whole feet, ``m`` = how it
    is known (l measured, s from stories, a the Assessor's one-story class, u not measured) and the zoning ``f`` family / ``l`` level under it (the style tints by family)."""
    db = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT height_ft, wkb FROM buildings").fetchall()
    finally:
        db.close()
    geoms = shapely.from_wkb([r[1] for r in rows])
    heights = np.array([r[0] for r in rows], dtype=float)
    inside = shapely.contains_xy(city_outline(), *shapely.get_coordinates(shapely.point_on_surface(geoms)).T)
    counts = {"in_box": len(rows), "in_city": int(inside.sum()), "invalid_fixed": 0, "dropped_empty": 0,
              "split_outlines": 0, "pieces_measured": 0, "pieces_from_stories": 0, "pieces_not_measured": 0,
              "one_story_cut_outlines": 0, "pieces_one_story_class": 0,
              "zoning_unmatched": 0}
    if counts["in_city"] < MIN_IN_CITY:
        raise RuntimeError(f"County buildings: {counts['in_city']} inside the city, expected {MIN_IN_CITY}+")
    cityfp = _load_city(city)
    pieces: list[tuple[object, float, str]] = []
    for g, h in zip(geoms[inside], heights[inside]):
        if not g.is_valid:
            counts["invalid_fixed"] += 1
        g = _polys(g)
        if g is None:
            counts["dropped_empty"] += 1
            continue
        parts = [(g, h, "l")]
        if cityfp is not None and h >= SPLIT_MIN_FT:
            cg, cst, tree = cityfp
            idx = tree.query(g, predicate="contains")
            if len(idx) >= 2:
                parts = split_outline(g, h, [(cg[i], cst[i]) for i in idx])
                if len(parts) > 1:
                    counts["split_outlines"] += 1
        if one_story is not None and h >= SPLIT_MIN_FT:
            cut_parts: list[tuple[object, float, str]] = []
            for part in parts:
                cut_parts.extend(cut_one_story(part[0], part[1], one_story) if part[2] == "l" else [part])
            if len(cut_parts) != len(parts):
                counts["one_story_cut_outlines"] += 1
            parts = cut_parts
        pieces.extend(parts)
    look = _zoning_lookup(zoning)
    zones = look(shapely.point_on_surface([p[0] for p in pieces])) if look else [None] * len(pieces)
    kind_key = {"l": "pieces_measured", "s": "pieces_from_stories", "u": "pieces_not_measured", "a": "pieces_one_story_class"}
    feats: list[Feature] = []
    for (g, h, kind), z in zip(pieces, zones):
        counts[kind_key[kind]] += 1
        props = {"h": str(int(round(h))), "m": kind}
        if z:
            props["f"], props["l"] = z
        else:
            counts["zoning_unmatched"] += 1
        feats.append(Feature(LAYER, to_mercator(g), props, MIN_ZOOM))
    return feats, counts


def build_file(out: Path, *, offline: bool = False, minzoom: int = MIN_ZOOM, maxzoom: int = MAX_ZOOM) -> dict:
    t0 = time.monotonic()
    src = out.parent / "map_sources" / SOURCE_DB
    if not offline or not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        log.info("County buildings: fetched %d", fetch(src))
    city = out.parent / "discovery_lot_sources.db"
    if not city.exists():
        log.warning("County buildings: %s missing; tall outlines are not split along the City's footprints", city)
    zoning = None
    zpath = out.parent / "map_sources" / "zoning_layer1.geojson"
    if zpath.exists():
        zoning = json.loads(zpath.read_text())["features"]
    else:
        log.warning("County buildings: %s missing; buildings are not tinted by zoning", zpath)
    one_story = one_story_lots(out.parent / "discovery_index.db", out.parent / "ptaxsim.db")
    if one_story is None:
        log.warning("County buildings: the Discovery index or ptaxsim is missing; one-story lots are not cut out")
    feats, counts = build_features(src, city=city, zoning=zoning, one_story=one_story)
    stats = write_mbtiles(
        out, feats, name="map_buildings", minzoom=minzoom, maxzoom=maxzoom, layer_order=[LAYER],
        fields={LAYER: {"h": "Number", "m": "String", "f": "String", "l": "String"}},
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
