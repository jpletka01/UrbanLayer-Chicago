"""Which Chicago lots are rail land? Four sources measured against each other and the lot outlines before use.

Read-only over local copies, no model calls. Subcommands:

* ``fetch``: the rail lines, into one folder (outside the repo, then installed as ``backend/data/map_sources/``):
  - **CTA 'L' lines**, City of Chicago ``xbyr-jnvx`` (153 segments; ``type`` "Elevated or At Grade" or "Subway";
    "Lines representing approximately where the CTA rail lines are").
  - **North American Rail Network lines** (FRA, in the USDOT/BTS National Transportation Atlas Database; updated
    2026-10-19; public domain, 17 U.S.C. § 101): every railroad in Chicago's box with owner, trackage rights,
    passenger service (``PASSNGR`` A Amtrak, C commuter, B both) and ``NET`` (M main, Y yard, I industry,
    O other, S siding; A abandoned, T trail, X out of service, R rail-banked are left out).
* ``measure``: for every base lot of a Discovery index, against its newest PTAXSIM outline:
  - CMAP 2023's **rail right-of-way** (code 1511) share of the lot (``cmap_lui_2023.db``, Item 112);
  - the length of CTA elevated/at-grade line, CTA subway and NARN active line inside the lot, in feet;
  - the Assessor's class (RR = railroad), Item 110's ``land_kind`` / ``structure`` / ``empty_land``, and whether the
    lot shows room to build today.
  And, line by line, how far each source's lines sit from the other sources (the lines are drawn "approximately").

    PYTHONPATH=. python -I -m eval.rail_land fetch --out <dir>
    PYTHONPATH=. python -m eval.rail_land measure --index <discovery_index.db> --cmap <cmap_lui_2023.db> \\
        --rail <dir> [--ptaxsim backend/data/ptaxsim.db] [--out eval/results/2026-11-13-rail-land] \\
        [--lots-out <lots.json, outside the repo>]
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sqlite3
import time
from pathlib import Path

import httpx
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from backend.discovery.cmap_land_use import CHICAGO_BBOX, _get

CTA_DATASET = "xbyr-jnvx"
NARN_URL = ("https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
            "NTAD_North_American_Rail_Network_Lines/FeatureServer/0/query")
NARN_FIELDS = "FRAARCID,RROWNER1,RROWNER2,TRKRGHTS1,TRKRGHTS2,TRKRGHTS3,PASSNGR,NET,TRACKS,YARDNAME,SUBDIV"
NARN_ACTIVE = {"M": "main", "O": "main", "S": "main", "Y": "yard", "I": "industry"}
CMAP_RAIL = "1511"  # TCU_ROW_RAIL: rail right-of-way

# Local flat projection in feet (Chicago is small; error under 0.1%).
_LAT0 = 41.85
_FT_PER_DEG_LAT = 364_000.0
_FT_PER_DEG_LON = _FT_PER_DEG_LAT * math.cos(math.radians(_LAT0))


def to_feet(g):
    return shapely.transform(g, lambda xy: np.column_stack([(xy[:, 0] + 87.65) * _FT_PER_DEG_LON,
                                                            (xy[:, 1] - _LAT0) * _FT_PER_DEG_LAT]))


# --- fetch -------------------------------------------------------------------------------------------------------

def fetch(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, headers={"User-Agent": "rail-land-eval/1.0"}) as c:
        cta = _get(c, f"https://data.cityofchicago.org/resource/{CTA_DATASET}.json",
                   params={"$limit": 5000}).json()
        if len(cta) < 100:
            raise RuntimeError(f"CTA lines: only {len(cta)} rows")
        (out / "cta_lines.json").write_text(json.dumps(cta))
        feats: list[dict] = []
        while True:
            page = _get(c, NARN_URL, params={
                "where": "1=1", "geometry": ",".join(map(str, CHICAGO_BBOX)), "geometryType": "esriGeometryEnvelope",
                "inSR": 4326, "outSR": 4326, "outFields": NARN_FIELDS, "resultOffset": len(feats),
                "resultRecordCount": 2000, "f": "geojson"}).json()
            batch = page.get("features")
            if batch is None:
                raise RuntimeError(f"NARN answered without features: {str(page)[:200]}")
            feats += batch
            if len(batch) < 2000:
                break
        if len(feats) < 1500:
            raise RuntimeError(f"NARN lines: only {len(feats)} in Chicago's box")
        (out / "narn_lines.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    meta = {"fetched": time.strftime("%Y-%m-%d"), "cta_rows": len(cta), "narn_rows": len(feats)}
    (out / "rail_meta.json").write_text(json.dumps(meta))
    return meta


def load_lines(rail: Path) -> dict[str, list[tuple[shapely.Geometry, dict]]]:
    """kind → [(line in lon/lat, props)] for kinds cta_elevated, cta_subway, narn_main, narn_yard, narn_industry."""
    out: dict[str, list] = collections.defaultdict(list)
    for r in json.loads((rail / "cta_lines.json").read_text()):
        if not r.get("the_geom"):
            continue
        kind = "cta_subway" if (r.get("type") or "").lower().startswith("subway") else "cta_elevated"
        out[kind].append((shape(r["the_geom"]), {"lines": r.get("lines"), "legend": r.get("legend"),
                                                 "description": r.get("description")}))
    for f in json.loads((rail / "narn_lines.geojson").read_text())["features"]:
        p = f["properties"]
        kind = NARN_ACTIVE.get(p.get("NET") or "")
        if kind and f.get("geometry"):
            out[f"narn_{kind}"].append((shape(f["geometry"]), p))
    return out


# --- measure -----------------------------------------------------------------------------------------------------

def _cmap_rail(cmap: Path) -> list:
    db = sqlite3.connect(f"file:{cmap}?mode=ro", uri=True)
    rows = db.execute("SELECT wkb FROM lui WHERE landuse = ?", (CMAP_RAIL,)).fetchall()
    db.close()
    gs = [shapely.from_wkb(r[0]) for r in rows]
    return [g if g.is_valid else shapely.make_valid(g) for g in gs]


def _samples(line_ft, step: float = 50.0) -> list:
    out = []
    for part in shapely.get_parts(line_ft):
        n = max(1, int(part.length // step))
        out += [part.interpolate(i * step) for i in range(n + 1) if i * step <= part.length]
    return out


def line_agreement(lines_ft: list, other_ft: STRtree, other_geoms: np.ndarray) -> dict:
    """How far one source's lines sit from another's geometry: points every 50 ft, distance to the nearest."""
    pts = [p for g in lines_ft for p in _samples(g)]
    if not pts:
        return {"points": 0}
    arr = np.array(pts, dtype=object)
    _idx, dist = other_ft.query_nearest(arr, return_distance=True, all_matches=False)
    d = np.asarray(dist)
    return {"points": len(pts), "inside": round(float(np.mean(d == 0)), 3),
            "within_25ft": round(float(np.mean(d <= 25)), 3), "within_50ft": round(float(np.mean(d <= 50)), 3),
            "within_100ft": round(float(np.mean(d <= 100)), 3), "p50_ft": round(float(np.quantile(d, 0.5)), 1),
            "p90_ft": round(float(np.quantile(d, 0.9)), 1), "p99_ft": round(float(np.quantile(d, 0.99)), 1)}


def measure(index: Path, cmap: Path, rail: Path, ptaxsim: Path) -> tuple[list[dict], dict]:
    from backend.discovery.index_backfill import lot_outlines

    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    lots = db.execute(
        "SELECT pin, lat, lon, json_extract(attrs,'$.class'), json_extract(attrs,'$.land_kind'), "
        "json_extract(attrs,'$.structure'), json_extract(attrs,'$.empty_land'), json_extract(attrs,'$.unusual'), "
        "json_extract(attrs,'$.address'), json_extract(attrs,'$.zone_class'), json_extract(attrs,'$.room_sqft'), "
        "json_extract(attrs,'$.infrastructure'), json_extract(attrs,'$.surface_parking'), "
        "json_extract(attrs,'$.land_sqft') FROM parcels WHERE pin LIKE '%0000'"
    ).fetchall()
    db.close()
    outlines = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in lots})
    out, geo_i, geo = [], [], []
    for pin, lat, lon, cls, kind, structure, empty, unusual, addr, zone, room, infra, park, land in lots:
        lot = outlines.get(pin.replace("-", "")[:10])
        rec = {"pin": pin, "lat": lat, "lon": lon, "class": cls, "land_kind": kind, "structure": structure,
               "empty_land": bool(empty), "unusual": bool(unusual), "zone": zone, "room_sqft": room,
               "infrastructure": infra, "surface_parking": bool(park), "land_sqft": land,
               "approx_address": not addr or str(addr).startswith("~")}
        if lot is None or lot.area <= 0:
            rec["no_outline"] = True
        else:
            geo_i.append(len(out))
            geo.append(to_feet(lot))
        out.append(rec)
    lot_arr = np.array(geo, dtype=object)
    lot_tree = STRtree(lot_arr)

    # CMAP rail right-of-way share of each lot.
    crail = np.array([to_feet(g) for g in _cmap_rail(cmap)], dtype=object)
    pairs = STRtree(crail).query(lot_arr, predicate="intersects")
    share = collections.defaultdict(float)
    for a, b in zip(pairs[0], pairs[1]):
        try:
            share[int(a)] += lot_arr[a].intersection(crail[b]).area / lot_arr[a].area
        except shapely.errors.GEOSException:
            continue
    for a, s in share.items():
        if s > 0:
            out[geo_i[a]]["cmap_rail_share"] = round(min(s, 1.0), 3)

    # Line length inside each lot, per source kind.
    lines = load_lines(rail)
    lines_ft = {k: [to_feet(g) for g, _ in v] for k, v in lines.items()}
    for kind, gs in lines_ft.items():
        arr = np.array(gs, dtype=object)
        pairs = lot_tree.query(arr, predicate="intersects")
        acc = collections.defaultdict(float)
        for b, a in zip(pairs[0], pairs[1]):
            acc[int(a)] += arr[b].intersection(lot_arr[a]).length
        for a, length in acc.items():
            if length > 0:
                out[geo_i[a]][f"{kind}_ft"] = round(length, 1)

    # Line by line: how far each source sits from the others.
    rr_lots = np.array([lot_arr[i] for i, j in enumerate(geo_i) if (out[j].get("class") or "").upper() == "RR"],
                       dtype=object)
    rail_land = np.concatenate([crail, rr_lots])
    rail_tree = STRtree(rail_land)
    narn_all = [g for k in ("narn_main", "narn_yard") for g in lines_ft.get(k, [])]
    narn_tree = STRtree(np.array(narn_all, dtype=object))
    agree = {
        "cta_elevated_vs_cmap_rail_or_rr_lot": line_agreement(lines_ft.get("cta_elevated", []), rail_tree, rail_land),
        "cta_elevated_vs_narn": line_agreement(lines_ft.get("cta_elevated", []), narn_tree, narn_all),
        "narn_main_vs_cmap_rail_or_rr_lot": line_agreement(lines_ft.get("narn_main", []), rail_tree, rail_land),
        "narn_yard_vs_cmap_rail_or_rr_lot": line_agreement(lines_ft.get("narn_yard", []), rail_tree, rail_land),
        "narn_industry_vs_cmap_rail_or_rr_lot": line_agreement(lines_ft.get("narn_industry", []), rail_tree, rail_land),
    }
    # And where a CTA elevated line isn't on rail land: is it over a lot at all, or over a street?
    pts = [p for g in lines_ft.get("cta_elevated", []) for p in _samples(g)]
    on_lot = lot_tree.query(np.array(pts, dtype=object), predicate="within")
    on_rail = rail_tree.query(np.array(pts, dtype=object), predicate="within")
    lot_pts, rail_pts = set(on_lot[0].tolist()), set(on_rail[0].tolist())
    agree["cta_elevated_points"] = {"points": len(pts), "on_cmap_rail_or_rr": len(rail_pts),
                                    "on_other_lot": len(lot_pts - rail_pts),
                                    "on_no_lot (street, expressway, river)": len(set(range(len(pts))) - lot_pts - rail_pts)}
    meta = {"rail": json.loads((rail / "rail_meta.json").read_text()) if (rail / "rail_meta.json").exists() else {},
            "line_counts": {k: len(v) for k, v in lines.items()},
            "line_miles": {k: round(sum(g.length for g in v) / 5280, 1) for k, v in lines_ft.items()},
            "cmap_rail_polygons": len(crail)}
    return out, {"sources": meta, "line_agreement": agree}


# --- summarize ---------------------------------------------------------------------------------------------------

CMAP_HALF = 0.5
LINE_MIN_FT = 25.0  # a line runs at least this far through the lot


def signals(r: dict) -> dict[str, bool]:
    return {"cmap": r.get("cmap_rail_share", 0) >= CMAP_HALF,
            "cta": r.get("cta_elevated_ft", 0) >= LINE_MIN_FT,
            "narn": (r.get("narn_main_ft", 0) + r.get("narn_yard_ft", 0)) >= LINE_MIN_FT,
            "rr_class": (r.get("class") or "").upper() == "RR"}


def combo(r: dict) -> str:
    s = signals(r)
    return "+".join(k for k in ("cmap", "cta", "narn", "rr_class") if s[k]) or "none"


def summarize(rows: list[dict], extra: dict) -> dict:
    measured = [r for r in rows if not r.get("no_outline")]
    s: dict = {"lots": len(rows), "with_outline": len(measured), **extra}

    def shown_room(r: dict) -> bool:
        return not r["unusual"] and (r.get("room_sqft") or 0) > 0

    by = collections.defaultdict(lambda: collections.Counter())
    for r in measured:
        k = combo(r)
        if k == "none":
            continue
        c = by[k]
        c["lots"] += 1
        c[f"kind:{r.get('land_kind') or 'none'}"] += 1
        c[f"structure:{r.get('structure') or 'none'}"] += 1
        c["empty_land"] += r["empty_land"]
        c["hidden_unusual_today"] += r["unusual"]
        c["shown_with_room_today"] += shown_room(r)
        c["shown_empty_land_today"] += r["empty_land"] and not r["unusual"]
        c["surface_parking"] += r["surface_parking"]
        c["road_land_today"] += r.get("infrastructure") == "road"
    s["by_sources"] = {k: dict(v) for k, v in sorted(by.items(), key=lambda kv: -kv[1]["lots"])}

    # The candidate rule: any rail source on the lot, by what stands on it.
    any_sig = [r for r in measured if combo(r) not in ("none", "rr_class")]
    s["any_line_or_cmap_not_rr"] = {
        "lots": len(any_sig),
        "by_structure": dict(collections.Counter(r.get("structure") or "none" for r in any_sig).most_common()),
        "by_kind": dict(collections.Counter(r.get("land_kind") or "none" for r in any_sig).most_common()),
        "shown_with_room_today": sum(shown_room(r) for r in any_sig),
        "shown_empty_land_today": sum(r["empty_land"] and not r["unusual"] for r in any_sig),
    }
    # The subway: a lot over a subway is buildable; counted, never marked.
    sub = [r for r in measured if r.get("cta_subway_ft", 0) >= LINE_MIN_FT]
    s["over_cta_subway"] = {"lots": len(sub), "built": sum(r.get("structure") == "built" for r in sub)}
    # Industry spurs run into factories: counted, never marked.
    spur = [r for r in measured if r.get("narn_industry_ft", 0) >= LINE_MIN_FT and combo(r) == "none"]
    s["industry_spur_only"] = {"lots": len(spur), "built": sum(r.get("structure") == "built" for r in spur)}
    # CMAP share bands where a line runs through (is half the right bar?).
    bands = collections.Counter()
    for r in measured:
        if r.get("cta_elevated_ft", 0) >= LINE_MIN_FT or (r.get("narn_main_ft", 0) + r.get("narn_yard_ft", 0)) >= LINE_MIN_FT:
            sh = r.get("cmap_rail_share", 0)
            bands["0" if sh == 0 else "<0.25" if sh < 0.25 else "0.25-0.5" if sh < 0.5 else "0.5-0.9" if sh < 0.9 else ">=0.9"] += 1
    s["line_lots_by_cmap_rail_share"] = dict(bands)
    return s


def _plain(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("measure")
    m.add_argument("--index", type=Path)
    m.add_argument("--cmap", type=Path)
    m.add_argument("--rail", type=Path)
    m.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    m.add_argument("--out", type=Path, default=Path("eval/results/2026-11-13-rail-land"))
    m.add_argument("--lots-out", type=Path, default=None)
    m.add_argument("--from-lots", type=Path, default=None)
    a = ap.parse_args()
    if a.cmd == "fetch":
        print(json.dumps(fetch(a.out), indent=1))
        return
    if a.from_lots:
        saved = json.loads(a.from_lots.read_text())
        rows, extra = saved["lots"], saved["extra"]
    else:
        rows, extra = measure(a.index, a.cmap, a.rail, a.ptaxsim)
        if a.lots_out:
            a.lots_out.write_text(json.dumps({"extra": extra, "lots": rows}, default=_plain))
    summary = summarize(rows, extra)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=_plain))
    print(json.dumps(summary, indent=1, default=_plain))


if __name__ == "__main__":
    main()
