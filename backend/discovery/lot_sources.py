"""Local copies of the City sources Discovery's lots need beyond the Assessor (decision Item 104).

The owner chose "room to build" as the measure the new Discovery map colors every lot by, on the condition that its
coverage be fixed: the index had a building area for 97% of residential lots but 2% of commercial and 9% of large
multifamily lots (the Assessor's characteristics are residential only). This module keeps one SQLite file of:

* **building footprints** (``syp8-uezg``): each active footprint's outline, its stories and its area. The index
  builder sums footprint area x stories for a lot with no other building area (``lot_facts.footprint_area``);
* **vacant-building cases** (``kc9i-wq85``): the City's vacant-building violations, as points;
* **demolition permits** (``ydr8-5enu``, ``PERMIT - WRECKING/DEMOLITION``), as points;
* **Chicago Landmarks** (Zoning MapServer layer 5) and the landmark districts of layer 6 (``LANDMARK = 'Y'``);
* **addresses** (decision Item 109): the Assessor's property address of every Chicago base PIN (``3723-97qp``, latest
  year), the Address Points (``78yw-iddh``) and the City's street centerlines with their block-face ranges
  (``pr57-gg9e``), read by ``assessor_address`` to give a lot with no Address Point the Assessor's address when it
  lands on the lot.

The fetch refuses to write a copy that looks partial (row floors below), so "could not read" never becomes "no
building" or "no case". The copy is read only by the index build and ``index_backfill``; the live Profile is unchanged.

    PYTHONPATH=. python -m backend.discovery.lot_sources [--out backend/data/discovery_lot_sources.db] [--addresses-only]

``--addresses-only`` adds (or replaces) just the address tables in an existing copy.
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
COUNTY_PORTAL = "https://datacatalog.cookcountyil.gov/resource"
ASSESSOR_ADDRESSES = "3723-97qp"  # Cook County Assessor Parcel Addresses: prop_address_full per PIN per year
ADDRESS_POINTS = "78yw-iddh"
CENTERLINES = "pr57-gg9e"
FOOTPRINTS = "syp8-uezg"
VACANT_CASES = "kc9i-wq85"
PERMITS = "ydr8-5enu"
CITY_LAND = "aksk-kvfp"  # the City-Owned Land Inventory: lots the City owns, almost all vacant land for sale
ZONING_MAPSERVER = "https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer"
PAGE = 50_000

# Floors under which a read is treated as partial and nothing is written (measured 2026-11-10: 820,606 footprints,
# 5,012 vacant-building cases since 2011, 412 landmarks, 70 historic districts).
MIN_FOOTPRINTS = 700_000
MIN_LANDMARKS = 300
# Measured 2026-11-11: 590,779 2026 Assessor addresses for Chicago base PINs; 582,501 Chicago Address Points; 56,338
# centerline segments.
MIN_ASSESSOR_ADDRESSES = 500_000
MIN_ADDRESS_POINTS = 500_000
MIN_CENTERLINES = 50_000
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


def _pages(client: httpx.Client, dataset: str, params: dict, portal: str = PORTAL) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        r = client.get(f"{portal}/{dataset}.json", params={**params, "$limit": PAGE, "$offset": offset})
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


ADDRESS_TABLES = """
    DROP TABLE IF EXISTS assessor_address;
    DROP TABLE IF EXISTS address_points;
    DROP TABLE IF EXISTS centerlines;
    CREATE TABLE assessor_address (pin14 TEXT PRIMARY KEY, address TEXT NOT NULL);
    CREATE TABLE address_points (address TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL);
    CREATE TABLE centerlines (pre_dir TEXT, name TEXT, typ TEXT, l_f INTEGER, l_t INTEGER, r_f INTEGER, r_t INTEGER,
                              l_parity TEXT, r_parity TEXT, wkb BLOB NOT NULL);
"""


def _read_addresses(client: httpx.Client) -> tuple[str, list[tuple], list[tuple], list[tuple]]:
    """The Assessor's latest-year addresses (Chicago base PINs; address fields only, never a name), the Address
    Points and the centerlines. Raises on a short read."""
    r = client.get(f"{COUNTY_PORTAL}/{ASSESSOR_ADDRESSES}.json", params={"$select": "max(year) as y"})
    r.raise_for_status()
    year = str(r.json()[0]["y"])
    asr = _pages(client, ASSESSOR_ADDRESSES, {
        "$select": "pin,prop_address_full",
        "$where": f"year = '{year}' AND prop_address_city_name = 'CHICAGO' AND prop_address_full IS NOT NULL "
                  "AND pin like '%0000'",
        "$order": "pin"}, COUNTY_PORTAL)
    assessor = [(str(x["pin"]), x["prop_address_full"].strip().upper()) for x in asr
                if str(x.get("pin", "")).endswith("0000") and len(str(x.get("pin", ""))) == 14]
    aps = _pages(client, ADDRESS_POINTS, {
        "$select": "cmpaddabrv,lat,long", "$where": "inc_muni = 'Chicago' AND cmpaddabrv IS NOT NULL",
        "$order": "objectid"}, COUNTY_PORTAL)
    points = []
    for x in aps:
        try:
            points.append((x["cmpaddabrv"].strip().upper(), float(x["long"]), float(x["lat"])))
        except (KeyError, TypeError, ValueError):
            continue
    cl = _pages(client, CENTERLINES, {
        "$select": "the_geom,pre_dir,street_nam,street_typ,l_f_add,l_t_add,r_f_add,r_t_add,l_parity,r_parity",
        "$order": "objectid"})
    lines = []
    for x in cl:
        if not x.get("the_geom") or not x.get("street_nam"):
            continue
        try:
            nums = [int(float(x.get(k) or 0)) for k in ("l_f_add", "l_t_add", "r_f_add", "r_t_add")]
        except ValueError:
            continue
        lines.append((x.get("pre_dir"), x["street_nam"], x.get("street_typ") or None, *nums,
                      x.get("l_parity"), x.get("r_parity"), shapely.to_wkb(shape(x["the_geom"]))))
    if len(assessor) < MIN_ASSESSOR_ADDRESSES:
        raise RuntimeError(f"{ASSESSOR_ADDRESSES} returned {len(assessor)} Chicago base-PIN addresses: refusing to write")
    if len(points) < MIN_ADDRESS_POINTS:
        raise RuntimeError(f"{ADDRESS_POINTS} returned {len(points)} Chicago address points: refusing to write")
    if len(lines) < MIN_CENTERLINES:
        raise RuntimeError(f"{CENTERLINES} returned {len(lines)} centerline segments: refusing to write")
    return year, assessor, points, lines


def _write_addresses(db: sqlite3.Connection, year: str, assessor: list, points: list, lines: list) -> dict:
    db.executescript(ADDRESS_TABLES)
    db.executemany("INSERT OR REPLACE INTO assessor_address VALUES (?, ?)", assessor)
    db.executemany("INSERT INTO address_points VALUES (?, ?, ?)", points)
    db.execute("CREATE INDEX address_points_address ON address_points (address)")
    db.executemany("INSERT INTO centerlines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", lines)
    return {"assessor_address_year": year, "assessor_addresses": len(assessor), "address_points": len(points),
            "centerlines": len(lines)}


def fetch_addresses(out: Path = DEFAULT_PATH, *, token: str = "") -> dict:
    """Add (or replace) only the address tables in an existing copy, in one transaction."""
    if not out.exists():
        raise FileNotFoundError(f"{out} missing: run without --addresses-only first")
    t0 = time.monotonic()
    headers = {"X-App-Token": token} if token else {}
    with httpx.Client(timeout=300, headers=headers) as client:
        year, assessor, points, lines = _read_addresses(client)
    db = sqlite3.connect(out)
    try:
        with db:
            summary = _write_addresses(db, year, assessor, points, lines)
            summary["addresses_fetched"] = datetime.date.today().isoformat()
            db.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in summary.items()])
    finally:
        db.close()
    summary["seconds"] = round(time.monotonic() - t0, 1)
    return summary


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
        city_land = _pages(client, CITY_LAND, {"$select": "pin", "$where": "property_status = 'Owned by City'", "$order": "pin"})
        landmarks = _arcgis_polygons(client, 5, "1=1")
        districts = _arcgis_polygons(client, 6, "LANDMARK = 'Y'")
        addresses = _read_addresses(client)
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
        CREATE TABLE city_land (pin10 TEXT PRIMARY KEY);
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
    db.executemany("INSERT OR IGNORE INTO city_land VALUES (?)",
                   [(str(r["pin"]).replace("-", "")[:10],) for r in city_land if r.get("pin")])
    db.executemany("INSERT INTO areas VALUES (?, ?, ?)",
                   [("landmark", n, shapely.to_wkb(g)) for n, g in landmarks]
                   + [("landmark_district", n, shapely.to_wkb(g)) for n, g in districts])
    address_summary = _write_addresses(db, *addresses)
    summary = {
        "fetched": today.isoformat(), "footprints": len(fps), "footprints_with_stories": sum(1 for f in fps if f[1]),
        "footprints_skipped": bad, "vacant_cases": sum(1 for p in pts if p[0] == "vacant_case"),
        "demolition_permits": sum(1 for p in pts if p[0] == "demolition"), "landmarks": len(landmarks),
        "landmark_districts": len(districts), "city_owned_lots": len(city_land), **address_summary, "seconds": round(time.monotonic() - t0, 1),
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
    ap.add_argument("--addresses-only", action="store_true", help="add or replace only the address tables (Item 109)")
    args = ap.parse_args()
    from backend.config import get_settings
    token = get_settings().socrata_app_token or ""
    run = fetch_addresses if args.addresses_only else fetch
    print(json.dumps(run(args.out, token=token), indent=1))


if __name__ == "__main__":
    main()
