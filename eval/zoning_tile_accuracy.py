"""Boundary accuracy test for the new map's zoning tiles (map track M3, decision Item 91).

For every parcel in the validation panel (the 100-address lot panel, the data-health sentinels with their
expected districts) plus a seeded sample of BOUNDARY parcels (a PTAXSIM outline that touches two or more
districts: the known sliver problem), the parcel's district is read three ways and compared:

1. the source: the City's zoning layer (the cached GeoJSON the tile build read);
2. the tiles: the same parcel against the polygons decoded back out of ``map_zoning.mbtiles`` at each zoom;
3. for sentinels, the district in the answer key.

A parcel's district = the district covering the largest share of its outline (as the capacity map does) and,
separately, the district at its representative point. Any difference is a failure. No network, no model.

    PYTHONPATH=. python -m eval.zoning_tile_accuracy [--tiles backend/data/map_zoning.mbtiles]
        [--source backend/data/map_sources/zoning_layer1.geojson] [--boundary 400] [--out results.json]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
from collections import defaultdict
from pathlib import Path

import shapely
from shapely import wkt
from shapely.geometry import shape
from shapely.strtree import STRtree

from backend.map_tiles.mvt_decode import decode_tile
from backend.map_tiles.tiler import read_tile

ROOT = Path(__file__).resolve().parents[1]


def _tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 1 << z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


class Districts:
    """Polygons with their zone class and an STRtree, for majority-area and point lookups."""

    def __init__(self, geoms: list, classes: list[str]):
        self.geoms, self.classes = geoms, classes
        self.tree = STRtree(geoms)

    def by_area(self, outline) -> str | None:
        best, best_area = None, 0.0
        for i in self.tree.query(outline, predicate="intersects"):
            a = self.geoms[i].intersection(outline).area
            if a > best_area:
                best, best_area = self.classes[i], a
        return best

    def at_point(self, pt) -> str | None:
        hits = [self.classes[i] for i in self.tree.query(pt, predicate="intersects")]
        return hits[0] if hits else None

    def distance_to_line(self, pt) -> float:
        """Degrees from a point to the nearest district boundary."""
        near = self.tree.query(pt.buffer(0.001))
        return min((self.geoms[i].boundary.distance(pt) for i in near), default=1.0)

    def count_touching(self, outline) -> int:
        return len({self.classes[i] for i in self.tree.query(outline, predicate="intersects")
                    if self.geoms[i].intersection(outline).area > outline.area * 0.01})


def tile_unit_deg(z: int) -> float:
    """One tile unit (1/4096 of a tile) at zoom z, in degrees of latitude-ish size (generous: longitude units)."""
    return 360.0 / (1 << z) / 4096


def source_districts(path: Path) -> Districts:
    feats = json.loads(path.read_text())["features"]
    geoms, classes = [], []
    for f in feats:
        if not f.get("geometry"):
            continue
        g = shape(f["geometry"])
        if not g.is_valid:
            g = shapely.make_valid(g)
        geoms.append(g)
        classes.append((f["properties"].get("ZONE_CLASS") or "").strip())
    return Districts(geoms, classes)


_tile_cache: dict[tuple[int, int, int], list[tuple]] = {}  # (feature id, zone class, geometry)


def tile_districts(tiles: Path, outline, z: int) -> Districts:
    """The zoning polygons decoded from every tile the outline touches at zoom z (a district cut by a tile edge
    is united across tiles by its feature id: the build numbers features once, so the id is the same in every
    tile; the layer's ZONING_ID is a shared code, not unique)."""
    minx, miny, maxx, maxy = outline.bounds
    x0, y1 = _tile_xy(minx, miny, z)
    x1, y0 = _tile_xy(maxx, maxy, z)
    parts: dict[int, list] = defaultdict(list)
    cls: dict[int, str] = {}
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            key = (z, x, y)
            if key not in _tile_cache:
                data = read_tile(tiles, z, x, y)
                _tile_cache[key] = [] if data is None else [
                    (f["id"], f["props"].get("zone_class", ""), f["geometry"])
                    for f in decode_tile(data, z, x, y).get("zoning", [])]
            for zid, zc, g in _tile_cache[key]:
                parts[zid].append(g.buffer(0) if not g.is_valid else g)
                cls[zid] = zc
    geoms = [shapely.union_all(v) for v in parts.values()]
    return Districts(geoms, [cls[k] for k in parts])


def panel_pins() -> list[tuple[str, str | None, str]]:
    """(pin14, expected district or None, which panel)."""
    out = []
    lot = json.loads((ROOT / "eval" / "lot_panel.json").read_text())
    for a in lot["addresses"]:
        if a.get("truth_pin"):
            out.append((a["truth_pin"], None, "lot_panel"))
    sent = json.loads((ROOT / "backend" / "data_health" / "sentinels.json").read_text())
    for s in sent["sentinels"]:
        if s.get("pin"):
            out.append((s["pin"], s.get("district"), f"sentinel {s['id']}"))
    return out


def outlines(ptaxsim: Path, pin10s: list[str]) -> dict[str, object]:
    db = sqlite3.connect(f"file:{ptaxsim}?mode=ro", uri=True)
    got: dict[str, object] = {}
    for i in range(0, len(pin10s), 500):
        chunk = pin10s[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for pin10, text in db.execute(
            f"SELECT pin10, geometry FROM pin_geometry_raw WHERE pin10 IN ({marks}) ORDER BY end_year ASC", chunk
        ):
            try:
                g = wkt.loads(text)
            except Exception:  # noqa: BLE001
                continue
            got[pin10] = g if g.is_valid else shapely.make_valid(g)
    db.close()
    return got


def boundary_sample(index: Path, ptaxsim: Path, src: Districts, n: int, seed: int) -> list[str]:
    """n PIN10s whose outline touches two or more districts, drawn reproducibly from the index."""
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    pins = sorted({"".join(ch for ch in p if ch.isdigit())[:10] for (p,) in db.execute("SELECT pin FROM parcels")})
    db.close()
    rng = random.Random(seed)
    rng.shuffle(pins)
    picked: list[str] = []
    for i in range(0, len(pins), 2000):
        polys = outlines(ptaxsim, pins[i:i + 2000])
        for pin10, g in polys.items():
            if src.count_touching(g) >= 2:
                picked.append(pin10)
                if len(picked) >= n:
                    return picked
    return picked


def run(tiles: Path, source: Path, index: Path, ptaxsim: Path, n_boundary: int, seed: int,
        zooms: list[int]) -> dict:
    src = source_districts(source)
    cases: list[tuple[str, str | None, str]] = [(p[:10], exp, which) for p, exp, which in panel_pins()]
    cases += [(p, None, "boundary") for p in boundary_sample(index, ptaxsim, src, n_boundary, seed)]
    polys = outlines(ptaxsim, sorted({c[0] for c in cases}))
    failures: list[dict] = []
    checked = defaultdict(int)
    key_mismatch: list[dict] = []
    for pin10, expected, which in cases:
        g = polys.get(pin10)
        if g is None:
            checked["no_outline"] += 1
            continue
        pt = g.representative_point()
        s_area, s_pt = src.by_area(g), src.at_point(pt)
        if expected and s_area != expected:
            key_mismatch.append({"pin10": pin10, "panel": which, "key": expected, "source": s_area})
        near_line = src.distance_to_line(pt)
        for z in zooms:
            t = tile_districts(tiles, g, z)
            t_area, t_pt = t.by_area(g), t.at_point(pt)
            checked[f"z{z}"] += 1
            # A point closer to a district line than one tile unit at this zoom has no single answer in the tiles
            # (tile coordinates move an edge by up to about one unit): counted, and only its by-area district is
            # compared.
            if near_line < tile_unit_deg(z):
                checked[f"z{z}_point_within_one_tile_unit"] += 1
                t_pt = s_pt
            if (t_area, t_pt) != (s_area, s_pt):
                failures.append({"pin10": pin10, "panel": which, "zoom": z, "source": [s_area, s_pt],
                                 "tiles": [t_area, t_pt]})
        checked[which.split()[0]] += 1
    return {"checked": dict(checked), "failures": failures, "key_vs_source": key_mismatch,
            "boundary_requested": n_boundary, "seed": seed}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tiles", type=Path, default=ROOT / "backend/data/map_zoning.mbtiles")
    ap.add_argument("--source", type=Path, default=ROOT / "backend/data/map_sources/zoning_layer1.geojson")
    ap.add_argument("--index", type=Path, default=ROOT / "backend/data/discovery_index.db")
    ap.add_argument("--ptaxsim", type=Path, default=ROOT / "backend/data/ptaxsim.db")
    ap.add_argument("--boundary", type=int, default=400)
    ap.add_argument("--seed", type=int, default=91)
    ap.add_argument("--zooms", default="13,14,15,16")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    res = run(a.tiles, a.source, a.index, a.ptaxsim, a.boundary, a.seed, [int(z) for z in a.zooms.split(",")])
    text = json.dumps(res, indent=1)
    if a.out:
        a.out.write_text(text)
    print(json.dumps({"checked": res["checked"], "failures": len(res["failures"]),
                      "key_vs_source": res["key_vs_source"]}, indent=1))
    for f in res["failures"][:20]:
        print(f)


if __name__ == "__main__":
    main()
