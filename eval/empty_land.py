"""Which Chicago lots are physically empty? Measured from what stands on each lot, not its tax class (decision Item 110).

Read-only over local copies, no model calls. For every base lot (PIN suffix 0000) of a Discovery index, against the
lot's PTAXSIM outline, two independent building sources and recent permits:

* **City footprints** (``discovery_lot_sources.db``, ``syp8-uezg``, active): a footprint is on the lot when its own
  interior point is inside the outline (``lot_facts``' rule, so a neighbor's wall on the line doesn't count);
* **County 2022 LiDAR outlines** (``county_buildings_2022.db``, Item 105): on the lot when at least
  ``LIDAR_MIN_ON_LOT_SQFT`` of it lies inside the outline AND that is at least ``LIDAR_MIN_SHARE`` of the outline
  (an overhanging neighbor or a sliver is not a building on this lot), OR it covers ``LIDAR_MIN_LOT_COVER`` of the lot
  (the County often draws one outline over a row of houses or a building spanning lots), and it stands at least
  ``LIDAR_MIN_HEIGHT_FT``;
* **new-construction permits** issued since the LiDAR flight (``ydr8-5enu``, points, no contact fields).

A lot is **empty** when neither source puts a structure on it, or LiDAR shows nothing and a demolition permit
(``ydr8-5enu``, since 2006) says the City's footprint is out of date; **demolished since 2022** when a demolition
permit was issued after the flight; either becomes **new construction** when a new building was permitted since; **accessory only** when every structure on it is
smaller than ``ACCESSORY_MAX_SQFT`` (a garage or shed); otherwise **built**. The two sources' agreement is the
measure of how far "empty" can be trusted. Results are split by kind of land (Assessor class, the City's land
inventory) and checked against the owner's M4 labels (what he judged built on each lot).

    PYTHONPATH=. python -m eval.empty_land --index <discovery_index.db> --sources <discovery_lot_sources.db> \\
        --lidar <county_buildings_2022.db> [--ptaxsim backend/data/ptaxsim.db] [--labels <m4 labels.json>] \\
        [--permits <cache.json>] [--out eval/results/2026-11-11-empty-land]
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

from backend.discovery.index_backfill import lot_outlines
from backend.discovery.lot_sources import area_sqft

LIDAR_MIN_ON_LOT_SQFT = 150.0
LIDAR_MIN_SHARE = 0.5  # of the LiDAR outline on this lot ...
LIDAR_MIN_LOT_COVER = 0.3  # ... or of this lot covered by it (one outline often spans a row of houses or several lots)
LIDAR_MIN_HEIGHT_FT = 8.0
ACCESSORY_MAX_SQFT = 700.0  # a two-car garage is ~400-600 sq ft
PERMITS_SINCE = "2022-06-01"  # after the County's 2022 flight
PERMIT_BUFFER_DEG = 0.00003  # ~3 m, as lot_facts' point rule


def kind_of(cls: str | None, city_owned: bool) -> str:
    """The kind of land, from the Assessor's class (and the City's inventory)."""
    c = (cls or "").strip()
    if city_owned:
        return "city_owned"
    if c.startswith("1"):
        return "vacant_class"
    if c == "2-41":
        return "side_yard_2-41"
    if c in ("5-90", "5-80", "5-93", "5-97", "5-17"):
        return f"commercial_{c}"
    if c.startswith("5"):
        return "commercial_other"
    if c == "EX":
        return "exempt"
    if c == "RR":
        return "railroad"
    if c.startswith("2") or c.startswith("3") or c.startswith("9"):
        return "residential"
    return "other"


def _permits(cache: Path, permit_type: str = "PERMIT - NEW CONSTRUCTION",
             since: str = PERMITS_SINCE) -> list[tuple[float, float, str]]:
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text())]
    rows, offset = [], 0
    with httpx.Client(timeout=120) as c:
        while True:
            for attempt in range(6):  # the portal answers 503 now and then
                r = c.get("https://data.cityofchicago.org/resource/ydr8-5enu.json", params={
                    "$select": "issue_date,latitude,longitude",
                    "$where": f"permit_type = '{permit_type}' AND issue_date >= '{since}' "
                              "AND latitude IS NOT NULL",
                    "$order": "issue_date", "$limit": 50000, "$offset": offset})
                if r.status_code < 500:
                    break
                time.sleep(5 * (attempt + 1))
            r.raise_for_status()
            batch = r.json()
            rows += [(float(x["longitude"]), float(x["latitude"]), x["issue_date"][:10]) for x in batch]
            if len(batch) < 50000:
                break
            offset += 50000
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rows))
    return rows


def measure(index: Path, sources: Path, lidar: Path, ptaxsim: Path, permits_cache: Path) -> list[dict]:
    pmt = _permits(permits_cache)
    demo = _permits(permits_cache.with_name("demolitions_cache.json"), "PERMIT - WRECKING/DEMOLITION", "2006-01-01")
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    lots = db.execute(
        "SELECT pin, lat, lon, json_extract(attrs, '$.class'), json_extract(attrs, '$.bldg_sqft'), "
        "json_extract(attrs, '$.bldg_sqft_source'), json_extract(attrs, '$.unusual'), json_extract(attrs, '$.address'), "
        "json_extract(attrs, '$.land_sqft'), json_extract(attrs, '$.zoning_group') FROM parcels WHERE pin like '%0000'"
    ).fetchall()
    db.close()
    src = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    fp = src.execute("SELECT area_sqft, wkb FROM footprints").fetchall()
    city = {r[0] for r in src.execute("SELECT pin10 FROM city_land")}
    src.close()
    fp_geoms = shapely.from_wkb([r[1] for r in fp])
    fp_pts = shapely.point_on_surface(fp_geoms)
    fp_area = np.array([r[0] for r in fp])
    fp_tree = STRtree(fp_pts)

    ld = sqlite3.connect(f"file:{lidar}?mode=ro", uri=True)
    lrows = ld.execute("SELECT height_ft, wkb FROM buildings WHERE height_ft >= ?", (LIDAR_MIN_HEIGHT_FT,)).fetchall()
    ld.close()
    l_geoms = shapely.from_wkb([r[1] for r in lrows])
    l_geoms = np.array([g if g.is_valid else shapely.make_valid(g) for g in l_geoms], dtype=object)
    l_tree = STRtree(l_geoms)

    p_tree = STRtree([shapely.Point(lo, la) for lo, la, _d in pmt])
    d_tree = STRtree([shapely.Point(lo, la) for lo, la, _d in demo])
    d_dates = [d for _lo, _la, d in demo]

    outlines = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in lots})
    out = []
    for pin, lat, lon, cls, bldg, bsrc, unusual, addr, land, zg in lots:
        p10 = pin.replace("-", "")[:10]
        lot = outlines.get(p10)
        rec = {"pin": pin, "class": cls, "kind": kind_of(cls, p10 in city), "bldg_sqft": bldg, "bldg_src": bsrc,
               "unusual": bool(unusual), "approx_address": not addr or str(addr).startswith("~"),
               "land_sqft": land, "zoning": zg, "lat": lat, "lon": lon}
        if lot is None:
            rec["state"] = "no_outline"
            out.append(rec)
            continue
        f_idx = fp_tree.query(lot, predicate="contains")
        f_sizes = [float(fp_area[i]) for i in f_idx]
        l_sizes = []
        lot_sqft = area_sqft(lot)
        for i in l_tree.query(lot, predicate="intersects"):
            g = l_geoms[i]
            try:
                inter = area_sqft(g.intersection(lot))
            except shapely.errors.GEOSException:
                continue
            own = area_sqft(g)
            if inter >= LIDAR_MIN_ON_LOT_SQFT and own > 0 and (
                    inter / own >= LIDAR_MIN_SHARE or (lot_sqft > 0 and inter / lot_sqft >= LIDAR_MIN_LOT_COVER)):
                l_sizes.append(inter)
        near = lot.buffer(PERMIT_BUFFER_DEG)
        permit = len(p_tree.query(near, predicate="intersects")) > 0
        demos = [d_dates[i] for i in d_tree.query(near, predicate="intersects")]

        def state(sizes: list[float]) -> str:
            if not sizes:
                return "empty"
            return "accessory" if max(sizes) < ACCESSORY_MAX_SQFT else "built"

        rec.update(fp=state(f_sizes), lidar=state(l_sizes), fp_sqft=round(sum(f_sizes)), lidar_sqft=round(sum(l_sizes)),
                   new_permit=permit, lot_sqft=round(lot_sqft), demolished=bool(demos),
                   demolished_after_flight=any(d >= PERMITS_SINCE for d in demos))
        both = {rec["fp"], rec["lidar"]}
        # empty: neither source has a structure; accessory: neither has more than a garage or shed; built: both
        # have a building; disagree: one has a building and the other doesn't.
        rec["state"] = ("empty" if both == {"empty"} else "built" if both == {"built"} else
                        "accessory" if "built" not in both else "disagree")
        # The City's footprints keep many demolished buildings (74.5% of vacant-class lots with a footprint and no
        # LiDAR building have a demolition permit on record, vs 7.6% of built houses): a demolition permit on the lot
        # and nothing in the 2022 LiDAR means the footprint is out of date.
        if rec["state"] == "disagree" and rec["fp"] != "empty" and rec["lidar"] == "empty" and demos:
            rec["state"] = "empty"
            rec["footprint_outdated"] = True
        # Demolished after the 2022 flight: LiDAR still shows it, but it is gone (unless rebuilt: the permit check below).
        if rec["state"] in ("built", "disagree", "accessory") and rec["demolished_after_flight"]:
            rec["state"] = "demolished_since_2022"
        if rec["state"] in ("empty", "accessory", "demolished_since_2022") and permit:
            rec["state"] = "new_construction"  # a new building permitted since the flight
        out.append(rec)
    return out


def summarize(rows: list[dict], labels: dict | None) -> dict:
    by_kind: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        k = r["kind"]
        by_kind[k]["lots"] += 1
        by_kind[k][r["state"]] += 1
        if r["state"] == "disagree":
            by_kind[k][f"fp_{r['fp']}__lidar_{r['lidar']}"] += 1
        if r["state"] == "empty":
            by_kind[k]["empty_with_new_permit"] += r["new_permit"]
            by_kind[k]["empty_hidden_unusual"] += r["unusual"]
            by_kind[k]["empty_approx_address"] += r["approx_address"]
            by_kind[k]["empty_with_assessor_bldg_area"] += bool(r["bldg_sqft"]) and r["bldg_src"] == "assessor"
            by_kind[k]["empty_footprint_outdated"] += bool(r.get("footprint_outdated"))
    agree = collections.Counter()
    for r in rows:
        if "fp" in r:
            fe, le = r["fp"] == "empty", r["lidar"] == "empty"
            agree["both_empty" if fe and le else "both_structure" if not fe and not le else
                  "footprint_only_empty" if fe else "lidar_only_empty"] += 1
    out = {"lots": len(rows), "source_agreement": dict(agree),
           "by_kind": {k: dict(v) for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1]["lots"])}}
    vac = [r for r in rows if r["kind"] == "vacant_class" and r.get("bldg_src") == "assessor" and r.get("bldg_sqft")]
    out["vacant_class_with_assessor_building_area"] = dict(collections.Counter(r["state"] for r in vac))
    if labels:
        cmp = collections.Counter()
        cases = []
        idx = {r["pin"]: r for r in rows}
        for pin, lab in labels.items():
            r = idx.get(pin)
            if r is None or "fp" not in r or lab.get("built_sqft") is None:
                continue
            human_empty = lab["built_sqft"] == 0
            ours = r["state"]
            key = f"human_{'empty' if human_empty else 'built'}__ours_{ours}"
            cmp[key] += 1
            if (ours == "empty") != human_empty:
                cases.append({"pin": pin, "ours": ours, "fp": r["fp"], "lidar": r["lidar"], "human_built_sqft": lab["built_sqft"],
                              "stratum": lab.get("stratum"), "note": lab.get("note")})
        # Counts only: the labels file is the owner's working copy and stays out of the repo (its notes describe
        # specific houses). The per-lot disagreements go to --private-out, outside the repo.
        out["vs_owner_m4_labels"] = {"counts": dict(cmp)}
        out["_private_disagreements"] = cases
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--lidar", type=Path, required=True)
    ap.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    ap.add_argument("--labels", type=Path, default=None)
    ap.add_argument("--permits", type=Path, default=Path("eval/results/2026-11-11-empty-land/permits_cache.json"))
    ap.add_argument("--out", type=Path, default=Path("eval/results/2026-11-11-empty-land"))
    ap.add_argument("--lots-out", type=Path, default=None, help="write every lot's evidence here (large; not committed)")
    ap.add_argument("--private-out", type=Path, default=None,
                    help="write the per-lot disagreements with the owner's labels here (outside the repo)")
    args = ap.parse_args()
    rows = measure(args.index, args.sources, args.lidar, args.ptaxsim, args.permits)
    labels = json.loads(args.labels.read_text()) if args.labels else None
    summary = summarize(rows, labels)
    private = summary.pop("_private_disagreements", None)
    if private is not None and args.private_out:
        args.private_out.write_text(json.dumps(private, indent=1))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    if args.lots_out:
        args.lots_out.write_text(json.dumps(rows))
    print(json.dumps({k: summary[k] for k in summary if k != "by_kind"}, indent=1)[:4000])


if __name__ == "__main__":
    main()
