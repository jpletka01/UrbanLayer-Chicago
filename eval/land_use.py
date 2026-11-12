"""What is each Chicago lot used for today? Three sources measured against each other before any is shown (Item 112).

Read-only over local copies, no model calls. Three subcommands:

* ``fetch-cmap``: CMAP's Land Use Inventory for Northeastern Illinois, **2023** (the newest release, published
  2026-03-25; Spring 2023 aerial photography plus the County Assessor's files; 57 codes; "Not restricted. Users are
  expected to cite CMAP"). Its polygons are parcels *dissolved on a common use*, so a lot is matched by area overlap,
  never by PIN. Only the code fields are kept (``LANDUSE``, ``LANDUSE2``, ``MODIFIER``, ``OS_MGMT``): ``FAC_NAME``
  is a facility name and is not needed. Chicago's bounding box is about 231k polygons, ~2 minutes.
* ``fetch-osm``: OpenStreetMap inside the City (relation 122604) through the Overpass API: every ``amenity=parking``
  area (with its ``parking=`` kind) and every ``landuse=*`` area. Kept in its own file, attributed
  "(c) OpenStreetMap contributors" (ODbL), never merged into a government source.
* ``measure``: for every base lot (PIN suffix 0000) of a Discovery index, against its newest PTAXSIM outline: CMAP's
  code covering the most of the lot and its share; OSM's surface-parking and garage shares and its main
  ``landuse``; the Assessor's class and Item 110's ``land_kind`` / ``structure`` (City footprints + 2022 LiDAR +
  permits, already on the index). The three are compared on one crosswalk (``COMMON``), per category.

**Surface parking** is a lot used as parking (CMAP 1540, OSM ``amenity=parking`` that is not a garage, or the
Assessor's minor-improvement classes 5-90 / 5-80) on which Item 110 finds no building (``structure`` empty or a
garage or shed only). CMAP's 1540 covers "off-street parking with or without a multi-level structure", and a lot
serving the building next door is coded to that building's use (classification schema, December 2020), so CMAP alone
can't say "surface" and misses accessory lots; the structure test is what makes it surface.

    PYTHONPATH=. python -I -m eval.land_use fetch-cmap --out <dir>/cmap_lui_2023.db
    PYTHONPATH=. python -I -m eval.land_use fetch-osm --out <dir>/osm_land_use.db
    PYTHONPATH=. python -m eval.land_use measure --index <discovery_index.db> --cmap <cmap_lui_2023.db> \\
        --osm <osm_land_use.db> [--ptaxsim backend/data/ptaxsim.db] [--out eval/results/2026-11-12-land-use] \\
        [--lots-out <lots.json, outside the repo>]
"""

from __future__ import annotations

import argparse
import collections
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
CHICAGO_BBOX = (-87.94, 41.64, -87.52, 42.03)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CHICAGO_OSM_AREA = 3600122604  # relation 122604 + 3600000000
OSM_GARAGE = ("multi-storey", "underground", "rooftop")
OSM_ON_STREET = ("lane", "street_side", "layby", "on_kerb", "half_on_kerb")  # parking on the street, not a lot

# The common categories all three sources are compared on. CMAP's 57 codes, by their first digits.
CMAP_COMMON = {
    "1111": "residential", "1112": "residential", "1130": "residential", "1140": "residential",
    "1151": "residential_common",
    "1211": "commercial", "1212": "commercial", "1214": "commercial", "1215": "commercial", "1216": "mixed_use",
    "1220": "commercial", "1240": "commercial", "1250": "commercial",
    "1310": "institutional", "1321": "institutional", "1322": "institutional", "1330": "institutional",
    "1340": "institutional", "1350": "institutional", "1360": "cemetery", "1370": "institutional",
    "1380": "institutional",
    "1410": "industrial", "1420": "industrial", "1431": "industrial", "1432": "industrial", "1433": "industrial",
    "1450": "industrial",
    "1511": "rail", "1512": "road", "1520": "transport", "1530": "transport", "1540": "parking",
    "1550": "utility", "1561": "utility", "1562": "utility", "1563": "utility", "1564": "utility",
    "1565": "utility", "1570": "transport",
    "2000": "agriculture",
    "3100": "open_space", "3200": "open_space", "3300": "open_space", "3400": "open_space", "3500": "open_space",
    "4110": "vacant", "4120": "vacant", "4130": "vacant", "4140": "vacant",
    "4210": "construction", "4220": "construction", "4230": "construction", "4240": "construction",
    "5000": "water", "6000": "non_parcel", "9999": "uncodeable",
}
OSM_LANDUSE_COMMON = {
    "residential": "residential", "commercial": "commercial", "retail": "commercial", "industrial": "industrial",
    "railway": "rail", "construction": "construction", "brownfield": "vacant", "greenfield": "vacant",
    "grass": "open_space", "recreation_ground": "open_space", "cemetery": "cemetery", "religious": "institutional",
    "education": "institutional", "institutional": "institutional", "garages": "parking",
    "forest": "open_space", "meadow": "open_space", "village_green": "open_space", "flowerbed": "open_space",
    "allotments": "open_space", "basin": "utility", "reservoir": "water", "military": "institutional",
}


INDUSTRIAL_CLASSES = ("5-50", "5-63", "5-70", "5-81", "5-83", "5-87", "5-89", "5-93")  # Class 5B, less 5-80


def assessor_common(cls: str | None, kind: str | None) -> str | None:
    """The Assessor's class on the common crosswalk (classes per the Cook County classification of real property)."""
    c = (cls or "").strip().upper()
    if kind == "city_owned":
        return None  # the City's inventory says who owns it, not what it is used for
    if not c:
        return None
    if c.startswith("1"):
        return "vacant"
    if c in ("5-90", "5-80"):
        return "parking"  # minor improvement: paving, a lot, a sign (Item 110 found 88% physically empty)
    if c == "2-41":
        return "vacant"  # side yard held with the house next door
    if c.startswith(("2", "3", "9")):
        return "residential"
    if c in INDUSTRIAL_CLASSES:
        return "industrial"
    if c.startswith("5"):
        return "commercial"
    if c.startswith(("6", "7", "8")):
        return "commercial"  # incentive classes: commercial or industrial, not told apart here
    if c == "EX":
        return "exempt"
    if c == "RR":
        return "rail"
    return None


# --- fetch -------------------------------------------------------------------------------------------------------

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


def _cmap_rows(feats: list[dict]) -> tuple[list[tuple], int]:
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


def fetch_cmap(out: Path, workers: int = 6, batch: int = 500) -> dict:
    """CMAP 2023 polygons touching Chicago's bounding box, as WKB in lon/lat, into a fresh SQLite file. The ids come
    first (one request), then batches of ids in parallel: paging by offset under a spatial filter was ~13 s a page."""
    from concurrent.futures import ThreadPoolExecutor

    spatial = {"geometry": ",".join(map(str, CHICAGO_BBOX)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
               "spatialRel": "esriSpatialRelIntersects"}
    with httpx.Client(timeout=300) as c:
        ids = _get(c, CMAP_URL, params={"where": "1=1", **spatial, "returnIdsOnly": "true", "f": "json"}).json()
        ids = sorted(ids["objectIds"])
        print(f"{len(ids)} polygons in Chicago's box", flush=True)

        def one(chunk: list[int]) -> list[dict]:
            r = _get(c, CMAP_URL, method="POST", data={
                "objectIds": ",".join(map(str, chunk)), "outSR": 4326, "f": "geojson",
                "outFields": "OBJECTID,LANDUSE,LANDUSE2,MODIFIER,OS_MGMT"})
            feats = r.json().get("features")
            if feats is None:
                raise RuntimeError("CMAP answered without a feature list")
            return feats

        chunks = [ids[i:i + batch] for i in range(0, len(ids), batch)]
        tmp = out.with_suffix(".part")
        tmp.unlink(missing_ok=True)
        db = sqlite3.connect(tmp)
        db.execute("CREATE TABLE lui (oid INTEGER PRIMARY KEY, landuse TEXT, landuse2 TEXT, modifier TEXT, "
                   "os_mgmt TEXT, wkb BLOB)")
        n = bad = 0
        with ThreadPoolExecutor(workers) as ex:
            for k, feats in enumerate(ex.map(one, chunks)):
                rows, b = _cmap_rows(feats)
                db.executemany("INSERT OR REPLACE INTO lui VALUES (?,?,?,?,?,?)", rows)
                db.commit()
                n += len(rows)
                bad += b
                if k % 20 == 0:
                    print(f"{n} / {len(ids)}", flush=True)
    if n < 0.99 * len(ids):
        raise RuntimeError(f"short read: {n} of {len(ids)}")
    meta = {"source": "CMAP Land Use Inventory for Northeastern Illinois", "vintage": CMAP_VINTAGE,
            "url": CMAP_URL, "licence": "Not restricted; cite CMAP", "fetched": time.strftime("%Y-%m-%d"),
            "polygons": n, "unreadable_geometry": bad}
    db.execute("CREATE TABLE meta (value TEXT)")
    db.execute("INSERT INTO meta VALUES (?)", (json.dumps(meta),))
    db.commit()
    db.close()
    tmp.replace(out)
    return meta


def _osm_polygons(el: dict, ways: dict[int, list]) -> shapely.Geometry | None:
    if el["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            g = shapely.Polygon(pts)
            return g if g.is_valid else shapely.make_valid(g)
        return None
    outer, inner = [], []
    for m in el.get("members", []):
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        line = shapely.LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        (inner if m.get("role") == "inner" else outer).append(line)
    if not outer:
        return None
    polys = shapely.polygonize(outer)
    g = shapely.union_all([p for p in shapely.get_parts(polys)]) if not polys.is_empty else None
    if g is None or g.is_empty:
        return None
    if inner:
        holes = shapely.polygonize(inner)
        if not holes.is_empty:
            g = g.difference(holes)
    return g if g.is_valid else shapely.make_valid(g)


def fetch_osm(out: Path) -> dict:
    q = (f"[out:json][timeout:600];area({CHICAGO_OSM_AREA})->.c;"
         '(way["amenity"="parking"](area.c);relation["amenity"="parking"](area.c);'
         'way["landuse"](area.c);relation["landuse"](area.c););out tags geom;')
    with httpx.Client(timeout=900, headers={"User-Agent": "land-use-eval/1.0"}) as c:
        data = _get(c, OVERPASS_URL, method="POST", data={"data": q}).json()
    tmp = out.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("CREATE TABLE osm (id TEXT PRIMARY KEY, kind TEXT, value TEXT, parking TEXT, wkb BLOB)")
    n = collections.Counter()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        g = _osm_polygons(el, {})
        if g is None or g.is_empty:
            n["no_area"] += 1
            continue
        oid = f"{el['type'][0]}{el['id']}"
        if tags.get("amenity") == "parking":
            db.execute("INSERT OR REPLACE INTO osm VALUES (?,?,?,?,?)",
                       (oid + "p", "parking", tags.get("parking") or "", tags.get("access") or "", shapely.to_wkb(g)))
            n["parking"] += 1
        if tags.get("landuse"):
            db.execute("INSERT OR REPLACE INTO osm VALUES (?,?,?,?,?)",
                       (oid + "l", "landuse", tags["landuse"], "", shapely.to_wkb(g)))
            n["landuse"] += 1
    meta = {"source": "OpenStreetMap via Overpass", "attribution": "(c) OpenStreetMap contributors",
            "licence": "ODbL 1.0", "osm_base": data.get("osm3s", {}).get("timestamp_osm_base"),
            "fetched": time.strftime("%Y-%m-%d"), "counts": dict(n)}
    db.execute("CREATE TABLE meta (value TEXT)")
    db.execute("INSERT INTO meta VALUES (?)", (json.dumps(meta),))
    db.commit()
    db.close()
    tmp.replace(out)
    return meta


# --- measure -----------------------------------------------------------------------------------------------------

def _load(path: Path, sql: str) -> tuple[list, np.ndarray, STRtree, dict]:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = db.execute(sql).fetchall()
    meta = json.loads(db.execute("SELECT value FROM meta").fetchone()[0])
    db.close()
    geoms = shapely.from_wkb([r[-1] for r in rows])
    geoms = np.array([g if g.is_valid else shapely.make_valid(g) for g in geoms], dtype=object)
    return [r[:-1] for r in rows], geoms, STRtree(geoms), meta


def _shares(lot, lot_area: float, idx, geoms) -> list[tuple[int, float]]:
    out = []
    for i in idx:
        try:
            a = lot.intersection(geoms[i]).area
        except shapely.errors.GEOSException:
            continue
        if a > 0:
            out.append((int(i), a / lot_area))
    return out


def _pair_shares(lots: np.ndarray, tree: STRtree, geoms: np.ndarray, chunk: int = 20_000):
    """Every (lot, source polygon) pair that overlaps, with the share of the lot it covers. Bulk: a prepared
    containment test first (a lot wholly inside one dissolved polygon is the common case), intersections only for the
    lots crossing an edge."""
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


def _safe_area(a, b) -> float:
    try:
        return a.intersection(b).area
    except shapely.errors.GEOSException:
        return 0.0


def measure(index: Path, cmap: Path, osm: Path, ptaxsim: Path) -> tuple[list[dict], dict]:
    from backend.discovery.index_backfill import lot_outlines

    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    lots = db.execute(
        "SELECT pin, lat, lon, json_extract(attrs,'$.class'), json_extract(attrs,'$.land_kind'), "
        "json_extract(attrs,'$.structure'), json_extract(attrs,'$.empty_land'), json_extract(attrs,'$.unusual'), "
        "json_extract(attrs,'$.address'), json_extract(attrs,'$.zoning_group') FROM parcels WHERE pin LIKE '%0000'"
    ).fetchall()
    db.close()
    c_rows, c_geoms, c_tree, c_meta = _load(cmap, "SELECT landuse, landuse2, modifier, wkb FROM lui")
    o_rows, o_geoms, o_tree, o_meta = _load(osm, "SELECT kind, value, parking, wkb FROM osm")
    outlines = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in lots})
    out, geo_i, geo = [], [], []
    for pin, lat, lon, cls, kind, structure, empty, unusual, addr, zg in lots:
        lot = outlines.get(pin.replace("-", "")[:10])
        rec = {"pin": pin, "lat": lat, "lon": lon, "class": cls, "land_kind": kind, "structure": structure,
               "empty_land": bool(empty), "unusual": bool(unusual), "zoning": zg,
               "approx_address": not addr or str(addr).startswith("~"),
               "assessor": assessor_common(cls, kind)}
        if lot is None or lot.area <= 0:
            rec["no_outline"] = True
        else:
            geo_i.append(len(out))
            geo.append(lot)
        out.append(rec)
    lot_arr = np.array(geo, dtype=object)

    by_code: dict[int, dict[str, float]] = collections.defaultdict(lambda: collections.defaultdict(float))
    multi: set[int] = set()
    for li, gi, sh in zip(*_pair_shares(lot_arr, c_tree, c_geoms)):
        code, code2, mod = c_rows[gi]
        by_code[li][code or "?"] += sh
        if code2 or mod == "M":
            multi.add(li)
    for li, codes in by_code.items():
        code, share = max(codes.items(), key=lambda kv: kv[1])
        out[geo_i[li]].update(cmap_code=code, cmap_share=round(min(share, 1.0), 3), cmap=CMAP_COMMON.get(code),
                              cmap_cover=round(min(sum(codes.values()), 1.0), 3), cmap_multi=li in multi,
                              cmap_parking_share=round(min(codes.get("1540", 0.0), 1.0), 3))

    park: dict[int, list[float]] = collections.defaultdict(lambda: [0.0, 0.0])
    lu: dict[int, dict[str, float]] = collections.defaultdict(lambda: collections.defaultdict(float))
    for li, gi, sh in zip(*_pair_shares(lot_arr, o_tree, o_geoms)):
        k, v, _p = o_rows[gi]
        if k == "parking":
            if v in OSM_GARAGE:
                park[li][1] += sh
            elif v not in OSM_ON_STREET:
                park[li][0] += sh
        else:
            lu[li][v] += sh
    for li in range(len(geo)):
        surf, gar = park.get(li, (0.0, 0.0))
        rec = out[geo_i[li]]
        rec.update(osm_surface_parking_share=round(min(surf, 1.0), 3), osm_garage_share=round(min(gar, 1.0), 3))
        if li in lu:
            v, s = max(lu[li].items(), key=lambda kv: kv[1])
            rec.update(osm_landuse=v, osm_landuse_share=round(min(s, 1.0), 3), osm=OSM_LANDUSE_COMMON.get(v))
    return out, {"cmap": c_meta, "osm": o_meta}


NO_BUILDING = ("empty", "accessory")
PARKING_SHARE = 0.5  # half the lot or more in the source's parking


def parking_signals(r: dict) -> dict[str, bool]:
    return {"cmap": r.get("cmap_parking_share", 0) >= PARKING_SHARE,
            "osm": r.get("osm_surface_parking_share", 0) >= PARKING_SHARE,
            "assessor": r.get("assessor") == "parking"}


def summarize(rows: list[dict], metas: dict) -> dict:
    measured = [r for r in rows if not r.get("no_outline")]
    s: dict = {"lots": len(rows), "with_outline": len(measured), "sources": metas}
    cov = collections.Counter()
    for r in measured:
        cov["cmap_any"] += "cmap_code" in r
        cov["cmap_half"] += r.get("cmap_share", 0) >= 0.5
        cov["cmap_uncodeable_or_nonparcel"] += r.get("cmap") in ("uncodeable", "non_parcel")
        cov["osm_landuse"] += "osm_landuse" in r
        cov["osm_landuse_half"] += r.get("osm_landuse_share", 0) >= 0.5
        cov["osm_parking_any"] += (r.get("osm_surface_parking_share", 0) + r.get("osm_garage_share", 0)) > 0
        cov["assessor"] += r.get("assessor") is not None
        cov["structure"] += r.get("structure") is not None
    s["coverage"] = dict(cov)
    s["cmap_share_quantiles"] = {q: round(float(np.quantile([r["cmap_share"] for r in measured if "cmap_share" in r],
                                                            q)), 3) for q in (0.05, 0.1, 0.25, 0.5)}

    # CMAP vs Assessor, on the common crosswalk, per Assessor category (CMAP's main code over half the lot).
    pair = collections.defaultdict(collections.Counter)
    for r in measured:
        a, c = r.get("assessor"), r.get("cmap")
        if a and c and r.get("cmap_share", 0) >= 0.5:
            pair[a][c] += 1
    s["assessor_vs_cmap"] = {a: dict(v.most_common(8)) | {"_n": sum(v.values())} for a, v in sorted(pair.items())}
    # CMAP's main category by Item 110's structure state.
    st = collections.defaultdict(collections.Counter)
    for r in measured:
        if r.get("cmap") and r.get("cmap_share", 0) >= 0.5:
            st[r["cmap"]][r.get("structure") or "none"] += 1
    s["cmap_by_structure"] = {c: dict(v) | {"_n": sum(v.values())} for c, v in sorted(st.items(), key=lambda kv: -sum(kv[1].values()))}
    # OSM landuse vs CMAP, where OSM tags one.
    oc = collections.defaultdict(collections.Counter)
    for r in measured:
        if r.get("osm") and r.get("osm_landuse_share", 0) >= 0.5 and r.get("cmap") and r.get("cmap_share", 0) >= 0.5:
            oc[r["osm"]][r["cmap"]] += 1
    s["osm_landuse_vs_cmap"] = {o: dict(v.most_common(6)) | {"_n": sum(v.values())} for o, v in sorted(oc.items())}

    # Parking: which sources say parking, and what stands on the lot.
    combo = collections.Counter()
    combo_struct = collections.defaultdict(collections.Counter)
    for r in measured:
        sig = parking_signals(r)
        key = "+".join(k for k in ("cmap", "osm", "assessor") if sig[k]) or "none"
        if key == "none":
            continue
        combo[key] += 1
        combo_struct[key][r.get("structure") or "none"] += 1
    s["parking_signals"] = {k: {"lots": n, **dict(combo_struct[k])} for k, n in combo.most_common()}
    surface = [r for r in measured if any(parking_signals(r).values()) and r.get("structure") in NO_BUILDING]
    s["surface_parking_candidates"] = {
        "lots": len(surface),
        "by_sources": dict(collections.Counter(
            "+".join(k for k, v in parking_signals(r).items() if v) for r in surface).most_common()),
        "by_land_kind": dict(collections.Counter(r.get("land_kind") or "none" for r in surface).most_common()),
        "already_empty_land": sum(r["empty_land"] for r in surface),
        "hidden_unusual": sum(r["unusual"] for r in surface),
        "approx_address": sum(r["approx_address"] for r in surface),
    }
    garages = [r for r in measured if (r.get("cmap_parking_share", 0) >= PARKING_SHARE or r.get("osm_garage_share", 0)
                                       >= PARKING_SHARE) and r.get("structure") == "built"]
    s["parking_with_building"] = {"lots": len(garages), "osm_garage": sum(r.get("osm_garage_share", 0) >= PARKING_SHARE
                                                                         for r in garages)}
    s["surface_parking_not_empty_land"] = dict(collections.Counter(
        r.get("land_kind") or "none" for r in surface if not r["empty_land"]).most_common())

    def cm(r: dict) -> str:
        return (r.get("cmap") or "?") if r.get("cmap_share", 0) >= 0.5 else "no_main_use"

    # Today's Empty land (Item 110) by what CMAP says the land is used for: roads, rail, utilities and parks are empty
    # but not building sites.
    el = collections.defaultdict(collections.Counter)
    for r in measured:
        if r["empty_land"]:
            el[r.get("land_kind") or "none"][cm(r)] += 1
    s["empty_land_by_cmap"] = {k: dict(v.most_common()) | {"_n": sum(v.values())} for k, v in el.items()}
    infra = collections.Counter(cm(r) for r in measured if r["empty_land"] and cm(r) in ("road", "rail", "utility",
                                                                                        "transport", "open_space",
                                                                                        "cemetery", "water"))
    s["empty_land_not_building_site_per_cmap"] = dict(infra) | {"_n": sum(infra.values())}
    # The Assessor's vacant classes split: class 1-xx land vs 2-41 side yards (CMAP codes a lot held with the house
    # next door as residential, by its own rule).
    sp = collections.defaultdict(collections.Counter)
    for r in measured:
        c = (r.get("class") or "").upper()
        if c.startswith("1"):
            sp["class_1"][cm(r)] += 1
        elif c == "2-41":
            sp["side_yard_2-41"][cm(r)] += 1
    s["vacant_classes_vs_cmap"] = {k: dict(v.most_common(8)) | {"_n": sum(v.values())} for k, v in sp.items()}
    # OSM's landuse vs CMAP on the common categories (mixed use counts as commercial).
    same = {("commercial", "mixed_use"), ("residential", "residential_common"), ("open_space", "open_space"),
            ("rail", "transport")}
    n = agree = 0
    for r in measured:
        o, c = (r.get("osm") if r.get("osm_landuse_share", 0) >= 0.5 else None), cm(r)
        if o and c not in ("no_main_use", "?"):
            n += 1
            agree += o == c or (o, c) in same
    s["osm_landuse_vs_cmap_agreement"] = {"lots": n, "agree": agree, "share": round(agree / n, 3) if n else None}
    return s


def _plain(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f1 = sub.add_parser("fetch-cmap")
    f1.add_argument("--out", type=Path, required=True)
    f2 = sub.add_parser("fetch-osm")
    f2.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("measure")
    m.add_argument("--index", type=Path)
    m.add_argument("--cmap", type=Path)
    m.add_argument("--osm", type=Path)
    m.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    m.add_argument("--out", type=Path, default=Path("eval/results/2026-11-12-land-use"))
    m.add_argument("--lots-out", type=Path, default=None, help="every lot's evidence (large; outside the repo)")
    m.add_argument("--from-lots", type=Path, default=None, help="summarize a saved --lots-out file again")
    a = ap.parse_args()
    if a.cmd == "fetch-cmap":
        print(json.dumps(fetch_cmap(a.out), indent=1))
    elif a.cmd == "fetch-osm":
        print(json.dumps(fetch_osm(a.out), indent=1))
    else:
        if a.from_lots:
            saved = json.loads(a.from_lots.read_text())
            rows, metas = saved["lots"], saved["sources"]
        else:
            rows, metas = measure(a.index, a.cmap, a.osm, a.ptaxsim)
            if a.lots_out:
                a.lots_out.write_text(json.dumps({"sources": metas, "lots": rows}, default=_plain))
        summary = summarize(rows, metas)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=_plain))
        print(json.dumps({k: summary[k] for k in ("lots", "with_outline", "coverage", "surface_parking_candidates")},
                         indent=1, default=_plain))


if __name__ == "__main__":
    main()
