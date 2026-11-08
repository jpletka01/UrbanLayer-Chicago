"""Build ``fema_flood_chicago.json.gz``: FEMA's flood hazard zones (NFHL layer 28) clipped to Chicago.

Decision Item 84. FEMA's hazards.fema.gov resets every TLS handshake from the production server (a German
Hetzner address; measured 2026-11-07: 10 of 10 resets on both of FEMA's IPs, www.fema.gov answers 403), so the
Profile's live flood lookup failed on every lot. The zones change only when FEMA issues a map revision or a LOMR,
so the polygons that cover the city ship as a committed artifact and are matched by point-in-polygon
(``backend/retrieval/regulatory/flood.py``). Points outside the city's coverage still ask FEMA live.

The service is FEMA's own (the government source), queried tile by tile over the city's bounding box (one big
page makes the server answer 500), deduplicated by ``OBJECTID``, clipped to the city boundary plus a margin (the
union of ``community_areas.geojson``), and lightly simplified (~0.5 m). The build refuses to write anything if a
page fails or the polygons leave a sizeable part of the city uncovered: a partial artifact would read as
"no mapped flood zone" where FEMA has one.

Usage (from a machine FEMA answers, not the production server):
    PYTHONPATH=. python -m ingestion.build_flood_artifact
Production never runs this; it reads the committed artifact.
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from datetime import date
from pathlib import Path

import httpx
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "ingestion" / "data"
OUTPUT_PATH = DATA_DIR / "fema_flood_chicago.json.gz"
META_PATH = DATA_DIR / "fema_flood_chicago.meta.json"
COMMUNITY_AREAS = DATA_DIR / "community_areas.geojson"

LAYER_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
FIELDS = ("OBJECTID", "FLD_ZONE", "ZONE_SUBTY", "SFHA_TF", "DFIRM_ID", "VERSION_ID")

# Coverage = the city boundary grown by ~200 m, so a lot on the city line is still answered from the artifact.
COVERAGE_MARGIN_DEG = 0.002
SIMPLIFY_DEG = 0.000005  # ~0.5 m
TILES = 6  # per side of the city bbox
PAGE = 100
# Share of the city's land that must lie inside some FEMA polygon (NFHL maps Cook County wall to wall, zone X
# included). Below this the artifact is not trusted to say "no mapped zone".
MIN_COVERED_SHARE = 0.98


def city_coverage():
    gj = json.loads(COMMUNITY_AREAS.read_text(encoding="utf-8"))
    city = unary_union([shape(f["geometry"]) for f in gj["features"]])
    return city, city.buffer(COVERAGE_MARGIN_DEG)


def fetch_tile(client: httpx.Client, env: tuple[float, float, float, float]) -> list[dict]:
    """Every feature intersecting one envelope, paged. Raises on any failed page (never a partial tile)."""
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": ",".join(f"{v:.6f}" for v in env),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": ",".join(FIELDS),
            "returnGeometry": "true",
            "geometryPrecision": "6",
            "orderByFields": "OBJECTID",
            "resultOffset": str(offset),
            "resultRecordCount": str(PAGE),
            "f": "geojson",
        }
        for attempt in range(4):
            try:
                resp = client.get(f"{LAYER_URL}/query", params=params)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data or not isinstance(data.get("features"), list):
                    raise RuntimeError(f"service error at offset {offset}: {str(data)[:200]}")
                break
            except (httpx.HTTPError, RuntimeError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        feats = data["features"]
        out.extend(feats)
        if len(feats) < PAGE:
            return out
        offset += PAGE


def build() -> tuple[dict, dict]:
    city, coverage = city_coverage()
    minx, miny, maxx, maxy = coverage.bounds
    dx, dy = (maxx - minx) / TILES, (maxy - miny) / TILES
    raw: dict[int, dict] = {}
    with httpx.Client(timeout=120.0, headers={"User-Agent": "UrbanLayer flood artifact build"}) as client:
        for i in range(TILES):
            for j in range(TILES):
                tile = box(minx + i * dx, miny + j * dy, minx + (i + 1) * dx, miny + (j + 1) * dy)
                if not tile.intersects(coverage):
                    continue
                for f in fetch_tile(client, tile.bounds):
                    raw.setdefault(int(f["properties"]["OBJECTID"]), f)
                print(f"tile {i},{j}: {len(raw)} distinct features so far", flush=True)

    features, geoms, versions, dfirms = [], [], set(), set()
    for _oid, f in sorted(raw.items()):
        if not f.get("geometry"):
            continue
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        g = g.intersection(coverage)
        if g.is_empty or g.area == 0:
            continue
        g = g.simplify(SIMPLIFY_DEG, preserve_topology=True)
        p = f["properties"]
        if not p.get("FLD_ZONE"):
            continue
        versions.add(p.get("VERSION_ID") or "")
        dfirms.add(p.get("DFIRM_ID") or "")
        geoms.append(g)
        features.append({
            "z": p["FLD_ZONE"], "s": p.get("ZONE_SUBTY"), "t": p.get("SFHA_TF"),
            "g": json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 6)),
        })

    covered = unary_union(geoms).intersection(city).area / city.area
    if covered < MIN_COVERED_SHARE:
        raise SystemExit(f"FEMA polygons cover only {covered:.1%} of the city: refusing to write a partial artifact")

    retrieved = date.today().isoformat()
    art = {
        "source": "FEMA National Flood Hazard Layer, Flood Hazard Zones (layer 28)",
        "source_url": LAYER_URL,
        "retrieved": retrieved,
        "coverage": mapping(coverage.simplify(0.0005)),
        "features": features,
    }
    meta = {
        "builder": "ingestion/build_flood_artifact.py",
        "built_at": retrieved,
        "retrieved": retrieved,
        "features": len(features),
        "city_share_covered": round(covered, 4),
        "dfirm_ids": sorted(d for d in dfirms if d),
        "version_ids": sorted(v for v in versions if v),
    }
    return art, meta


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    art, meta = build()
    with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(art, fh, separators=(",", ":"))
    META_PATH.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.name}: {meta['features']} zones, {meta['city_share_covered']:.1%} of the city covered, "
          f"{OUTPUT_PATH.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
