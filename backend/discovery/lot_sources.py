"""Local copies of the City sources Discovery's lots need beyond the Assessor (decision Item 104).

The owner chose "room to build" as the measure the new Discovery map colors every lot by, on the condition that its
coverage be fixed: the index had a building area for 97% of residential lots but 2% of commercial and 9% of large
multifamily lots (the Assessor's characteristics are residential only). This module keeps one SQLite file of:

* **building footprints** (``syp8-uezg``): each active footprint's outline, its stories and its area. The index
  builder sums footprint area x stories for a lot with no other building area (``lot_facts.footprint_area``);
* **vacant-building cases** (``kc9i-wq85``): the City's vacant-building violations, as points;
* **demolition permits** (``ydr8-5enu``, ``PERMIT - WRECKING/DEMOLITION``), as points;
* **Chicago Landmarks** (Zoning MapServer layer 5) and the landmark districts of layer 6 (``LANDMARK = 'Y'``).

The fetch refuses to write a copy that looks partial (row floors below), so "could not read" never becomes "no
building" or "no case". The copy is read only by the index build and ``index_backfill``; the live Profile is unchanged.

    PYTHONPATH=. python -m backend.discovery.lot_sources [--out backend/data/discovery_lot_sources.db]
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
import sqlite3
import time
from pathlib import Path

import httpx
import shapely
from shapely.geometry import shape

log = logging.getLogger(__name__)

PORTAL = "https://data.cityofchicago.org/resource"
FOOTPRINTS = "syp8-uezg"
VACANT_CASES = "kc9i-wq85"
PERMITS = "ydr8-5enu"
ZONING_MAPSERVER = "https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer"
PAGE = 50_000

# Floors under which a read is treated as partial and nothing is written (measured 2026-11-10: 820,606 footprints,
# 5,012 vacant-building cases since 2011, 412 landmarks, 70 historic districts).
MIN_FOOTPRINTS = 700_000
MIN_LANDMARKS = 300
VACANT_CASE_YEARS = 3
DEMOLITION_MONTHS = 24

# Square feet per square degree at Chicago's latitude (an equirectangular scale; error well under 1% across the city).
_LAT0 = 41.84
_M_PER_DEG_LAT = 111_132.0
_M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(_LAT0))
SQFT_PER_SQDEG = _M_PER_DEG_LAT * _M_PER_DEG_LON * 10.7639

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "discovery_lot_sources.db"


def area_sqft(geom) -> float:
    """Area of a lon/lat geometry in square feet (local scale)."""
    return float(geom.area) * SQFT_PER_SQDEG


def _pages(client: httpx.Client, dataset: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        r = client.get(f"{PORTAL}/{dataset}.json", params={**params, "$limit": PAGE, "$offset": offset})
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        log.info("lot sources: %s %d rows", dataset, len(rows))
        if len(batch) < PAGE:
            return rows
        offset += PAGE


def _point(row: dict) -> tuple[float, float] | None:
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lon) if 41.6 < lat < 42.1 and -88.0 < lon < -87.5 else None


def _arcgis_polygons(client: httpx.Client, layer: int, where: str) -> list[tuple[str, object]]:
    r = client.get(f"{ZONING_MAPSERVER}/{layer}/query", params={
        "where": where, "outFields": "NAME", "outSR": 4269, "f": "geojson", "returnGeometry": "true"})
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"zoning layer {layer}: {body['error']}")
    out = []
    for f in body.get("features", []):
        if not f.get("geometry"):
            continue
        g = shape(f["geometry"])
        out.append(((f.get("properties") or {}).get("NAME") or "", g if g.is_valid else shapely.make_valid(g)))
    return out


def fetch(out: Path = DEFAULT_PATH, *, token: str = "", today: datetime.date | None = None) -> dict:
    """Read every source and write ``out`` atomically (beside it, then renamed over it)."""
    t0 = time.monotonic()
    today = today or datetime.date.today()
    headers = {"X-App-Token": token} if token else {}
    with httpx.Client(timeout=300, headers=headers) as client:
        fp_rows = _pages(client, FOOTPRINTS, {
            "$select": "bldg_id,the_geom,stories,bldg_statu", "$where": "bldg_statu = 'ACTIVE'", "$order": "bldg_id"})
        since_cases = (today - datetime.timedelta(days=365 * VACANT_CASE_YEARS)).isoformat()
        cases = _pages(client, VACANT_CASES, {
            "$select": "docket_number,issued_date,latitude,longitude",
            "$where": f"issued_date >= '{since_cases}'", "$order": "issued_date"})
        since_demo = (today - datetime.timedelta(days=30 * DEMOLITION_MONTHS)).isoformat()
        demos = _pages(client, PERMITS, {
            "$select": "permit_,issue_date,latitude,longitude",
            "$where": f"permit_type = 'PERMIT - WRECKING/DEMOLITION' AND issue_date >= '{since_demo}'",
            "$order": "issue_date"})
        landmarks = _arcgis_polygons(client, 5, "1=1")
        districts = _arcgis_polygons(client, 6, "LANDMARK = 'Y'")
    if len(fp_rows) < MIN_FOOTPRINTS:
        raise RuntimeError(f"{FOOTPRINTS} returned {len(fp_rows)} active footprints: refusing to write")
    if len(landmarks) < MIN_LANDMARKS:
        raise RuntimeError(f"zoning layer 5 returned {len(landmarks)} landmarks: refusing to write")

    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE footprints (bldg_id TEXT, stories INTEGER, area_sqft REAL, wkb BLOB NOT NULL);
        CREATE TABLE points (kind TEXT NOT NULL, ref TEXT, date TEXT, lat REAL NOT NULL, lon REAL NOT NULL);
        CREATE TABLE areas (kind TEXT NOT NULL, name TEXT, wkb BLOB NOT NULL);
        CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT);
    """)
    bad = 0
    fps = []
    for row in fp_rows:
        geom = row.get("the_geom")
        if not geom:
            bad += 1
            continue
        g = shape(geom)
        if not g.is_valid:
            g = shapely.make_valid(g)
        try:
            stories = int(float(row.get("stories") or 0)) or None
        except ValueError:
            stories = None
        fps.append((row.get("bldg_id"), stories, round(area_sqft(g), 1), shapely.to_wkb(g)))
    db.executemany("INSERT INTO footprints VALUES (?, ?, ?, ?)", fps)
    pts = []
    for kind, rows, ref, date in (("vacant_case", cases, "docket_number", "issued_date"),
                                  ("demolition", demos, "permit_", "issue_date")):
        for row in rows:
            p = _point(row)
            if p:
                pts.append((kind, row.get(ref), (row.get(date) or "")[:10], p[0], p[1]))
    db.executemany("INSERT INTO points VALUES (?, ?, ?, ?, ?)", pts)
    db.executemany("INSERT INTO areas VALUES (?, ?, ?)",
                   [("landmark", n, shapely.to_wkb(g)) for n, g in landmarks]
                   + [("landmark_district", n, shapely.to_wkb(g)) for n, g in districts])
    summary = {
        "fetched": today.isoformat(), "footprints": len(fps), "footprints_with_stories": sum(1 for f in fps if f[1]),
        "footprints_skipped": bad, "vacant_cases": sum(1 for p in pts if p[0] == "vacant_case"),
        "demolition_permits": sum(1 for p in pts if p[0] == "demolition"), "landmarks": len(landmarks),
        "landmark_districts": len(districts), "seconds": round(time.monotonic() - t0, 1),
    }
    db.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in summary.items()])
    db.commit()
    db.close()
    tmp.replace(out)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_PATH)
    args = ap.parse_args()
    from backend.config import get_settings
    print(json.dumps(fetch(args.out, token=get_settings().socrata_app_token or ""), indent=1))


if __name__ == "__main__":
    main()
