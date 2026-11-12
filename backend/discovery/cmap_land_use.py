"""CMAP's Land Use Inventory for Northeastern Illinois (2023) on Discovery's lots (decision Item 112).

CMAP draws parcels *dissolved on a common use* (57 codes), so a lot is matched by area overlap, never by PIN. Two jobs:

* ``fetch(out)``: a local copy of the inventory inside Chicago's box (about 231k polygons, 146 MB, ~2 minutes by id
  batches). Run it on the Mac and install the file beside the other map sources, as with FEMA and the County's LiDAR
  (Items 84, 106); whether CMAP answers the prod server is not yet checked. Only the code fields are kept (no facility
  names). Licence: "Not restricted. Users are expected to cite the Chicago Metropolitan Agency for Planning (CMAP)."
* ``codes_on_lots(cmap, ptaxsim)``: for every lot outline in Chicago's box, CMAP's code covering the most of it and
  that share. ``lot_sources --land-use-only`` writes it as ``cmap_on_lot``; ``lot_facts.mark_land_use`` reads it.

Only one CMAP code reaches the page so far: **1512, road right-of-way**, on exempt land the Item 110 rule calls
empty. The owner's blind checks found 27 of 27 such lots were road or rail land, so they are hidden by default.

    PYTHONPATH=. python -m backend.discovery.cmap_land_use --out backend/data/map_sources/cmap_lui_2023.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import httpx
import numpy as np
import shapely
from shapely.strtree import STRtree

CMAP_URL = "https://services5.arcgis.com/LcMXE3TFhi1BSaCY/arcgis/rest/services/LUI_2023_view/FeatureServer/1/query"
CMAP_VINTAGE = "2023 (Spring 2023 aerials; published 2026-03-25)"
CMAP_ROAD = "1512"  # TCU_ROW_ROAD: road right-of-way
CHICAGO_BBOX = (-87.94, 41.64, -87.52, 42.03)
MIN_POLYGONS = 200_000  # Chicago's box held 231,348 on 2026-11-12: a short read is refused


def _get(client: httpx.Client, url: str, method: str = "GET", **kw) -> httpx.Response:
    for attempt in range(6):
        try:
            r = client.request(method, url, **kw)
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
                return r
        except httpx.TransportError:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url} did not answer after 6 attempts")


def _rows(feats: list[dict]) -> tuple[list[tuple], int]:
    rows, bad = [], 0
    for f in feats:
        try:
            g = shapely.geometry.shape(f["geometry"])
        except (TypeError, ValueError, KeyError, AttributeError):
            bad += 1
            continue
        p = f["properties"]
        rows.append((p["OBJECTID"], p.get("LANDUSE"), (p.get("LANDUSE2") or "").strip() or None,
                     p.get("MODIFIER"), p.get("OS_MGMT"), shapely.to_wkb(g)))
    return rows, bad


def fetch(out: Path, workers: int = 6, batch: int = 500) -> dict:
    """CMAP 2023 polygons touching Chicago's box, as WKB in lon/lat, into a fresh SQLite file (atomic). The ids come
    first, then batches of ids in parallel: paging by offset under a spatial filter was ~13 s a page."""
    from concurrent.futures import ThreadPoolExecutor

    spatial = {"geometry": ",".join(map(str, CHICAGO_BBOX)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
               "spatialRel": "esriSpatialRelIntersects"}
    tmp = out.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    with httpx.Client(timeout=300) as c:
        ids = sorted(_get(c, CMAP_URL, params={"where": "1=1", **spatial, "returnIdsOnly": "true",
                                               "f": "json"}).json()["objectIds"])
        print(f"{len(ids)} polygons in Chicago's box", flush=True)

        def one(chunk: list[int]) -> list[dict]:
            feats = _get(c, CMAP_URL, method="POST", data={
                "objectIds": ",".join(map(str, chunk)), "outSR": 4326, "f": "geojson",
                "outFields": "OBJECTID,LANDUSE,LANDUSE2,MODIFIER,OS_MGMT"}).json().get("features")
            if feats is None:
                raise RuntimeError("CMAP answered without a feature list")
            return feats

        db = sqlite3.connect(tmp)
        db.execute("CREATE TABLE lui (oid INTEGER PRIMARY KEY, landuse TEXT, landuse2 TEXT, modifier TEXT, "
                   "os_mgmt TEXT, wkb BLOB)")
        n = bad = 0
        with ThreadPoolExecutor(workers) as ex:
            for k, feats in enumerate(ex.map(one, [ids[i:i + batch] for i in range(0, len(ids), batch)])):
                rows, b = _rows(feats)
                db.executemany("INSERT OR REPLACE INTO lui VALUES (?,?,?,?,?,?)", rows)
                db.commit()
                n, bad = n + len(rows), bad + b
                if k % 20 == 0:
                    print(f"{n} / {len(ids)}", flush=True)
    if n < max(MIN_POLYGONS, 0.99 * len(ids)):
        db.close()
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"short read: {n} of {len(ids)}")
    meta = {"source": "CMAP Land Use Inventory for Northeastern Illinois", "vintage": CMAP_VINTAGE, "url": CMAP_URL,
            "licence": "Not restricted; cite CMAP", "fetched": time.strftime("%Y-%m-%d"), "polygons": n,
            "unreadable_geometry": bad}
    db.execute("CREATE TABLE meta (value TEXT)")
    db.execute("INSERT INTO meta VALUES (?)", (json.dumps(meta),))
    db.commit()
    db.close()
    tmp.replace(out)
    return meta


def read_meta(cmap: Path) -> dict:
    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    try:
        return json.loads(db.execute("SELECT value FROM meta").fetchone()[0])
    finally:
        db.close()


def _safe_area(a, b) -> float:
    try:
        return a.intersection(b).area
    except shapely.errors.GEOSException:
        return 0.0


def pair_shares(lots: np.ndarray, tree: STRtree, geoms: np.ndarray, chunk: int = 20_000):
    """Every (lot, polygon) pair that overlaps, with the share of the lot it covers. Bulk: a prepared containment test
    first (a lot wholly inside one dissolved polygon is the common case), intersections only for lots on an edge."""
    li, gi = tree.query(lots, predicate="intersects")
    shapely.prepare(geoms)
    share = np.zeros(len(li))
    for a in range(0, len(li), chunk):
        sl = slice(a, a + chunk)
        share[sl] = shapely.contains(geoms[gi[sl]], lots[li[sl]]).astype(float)
    rest = np.nonzero(share == 0)[0]
    for a in range(0, len(rest), chunk):
        r = rest[a:a + chunk]
        try:
            inter = shapely.area(shapely.intersection(lots[li[r]], geoms[gi[r]]))
        except shapely.errors.GEOSException:
            inter = np.array([_safe_area(lots[li[k]], geoms[gi[k]]) for k in r])
        share[r] = inter / shapely.area(lots[li[r]])
    keep = share > 0
    return li[keep], gi[keep], share[keep]


def load_polygons(cmap: Path) -> tuple[list[str], np.ndarray, STRtree]:
    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT landuse, wkb FROM lui").fetchall()
    finally:
        db.close()
    geoms = shapely.from_wkb([r[1] for r in rows])
    geoms = np.array([g if g.is_valid else shapely.make_valid(g) for g in geoms], dtype=object)
    return [r[0] or "" for r in rows], geoms, STRtree(geoms)


def codes_on_lots(cmap: Path, ptaxsim: Path) -> list[tuple[str, str, float]]:
    """(pin10, CMAP's code covering the most of the lot, that share of the lot) for every lot outline in Chicago's box
    (PTAXSIM's newest outline, the same lots the Profile reasons about)."""
    from shapely import wkt as shapely_wkt

    codes, geoms, tree = load_polygons(cmap)
    w, s_, e, n = CHICAGO_BBOX
    geo = sqlite3.connect(f"file:{ptaxsim}?mode=ro", uri=True)
    try:
        latest: dict[str, str] = {}
        for pin10, text in geo.execute(
                "SELECT pin10, geometry FROM pin_geometry_raw WHERE longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ? "
                "AND geometry IS NOT NULL ORDER BY end_year ASC", (w, e, s_, n)):
            latest[pin10] = text
    finally:
        geo.close()
    pins, lots = [], []
    for pin10, text in latest.items():
        try:
            g = shapely_wkt.loads(text)
            if not g.is_valid:
                g = shapely.make_valid(g)
        except (shapely.errors.GEOSException, ValueError):
            continue
        if not g.is_empty and g.area > 0:
            pins.append(pin10)
            lots.append(g)
    by_lot: dict[int, dict[str, float]] = {}
    for li, gi, sh in zip(*pair_shares(np.array(lots, dtype=object), tree, geoms)):
        d = by_lot.setdefault(int(li), {})
        d[codes[gi]] = d.get(codes[gi], 0.0) + float(sh)
    out = []
    for li, d in by_lot.items():
        code, share = max(d.items(), key=lambda kv: kv[1])
        out.append((pins[li], code, round(min(share, 1.0), 3)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Path("backend/data/map_sources/cmap_lui_2023.db"))
    print(json.dumps(fetch(ap.parse_args().out), indent=1))


if __name__ == "__main__":
    main()
