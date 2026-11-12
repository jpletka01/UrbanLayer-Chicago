"""Blind owner check for land use and surface parking (decision Item 112). No model calls; localhost only.

    PYTHONPATH=. python -m eval.land_use_label draw --lots <lots.json from eval.land_use measure --lots-out> \\
        [--index backend/data/discovery_index.db] [--sources backend/data/discovery_lot_sources.db] \\
        [--exclude <earlier panels' PINs, json list or {pin: ...}>...]
    PYTHONPATH=. python -m eval.land_use_label serve [--port 8034]
    PYTHONPATH=. python -m eval.land_use_label score

**Draw** (seeded, ``STRATA``): the surface-parking candidates split by which sources say parking, so each source's
precision is measured on its own; lots called parking by no source but physically empty (what parking the sources
miss); and lots for the general categories, where CMAP and the Assessor agree and where they disagree.

**Blind.** The page shows the lot's outline, its neighbors with their own City addresses, the street names, the
City's footprints AROUND the lot (cut out of the lot itself), a Street View link standing on the nearest street
facing the lot, and "Lot from above" (Google's satellite view pinned on the lot's middle, added at the owner's request
on 2026-11-12; Item 78 governs the product's maps, not this internal check). Never the sources' answers or the stratum.

Labels are saved as they are made to ``eval/results/2026-11-12-land-use/labels.json``, which stays out of the repo
(``.gitignore``); ``score`` prints counts only.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import Counter
from pathlib import Path

from eval import empty_land_label as ell
from eval.assessor_address_label import _FT_LAT, _FT_LON, _viewpoint, _wilson
from eval.assessor_address_label import _ring as _poly_ring

PANEL = Path("eval/land_use_panel.json")
PAGE = Path(__file__).with_name("land_use_label_page.html")
LABELS = Path("eval/results/2026-11-12-land-use/labels.json")
SEED = 112
NEAR_FT = 160.0
NO_BUILDING = ("empty", "accessory")
PARKING_SHARE = 0.5

# stratum -> lots drawn. Parking first: the owner asked for it.
STRATA = (
    ("park_all3", 5), ("park_cmap_assessor", 5), ("park_cmap_osm", 5), ("park_cmap_only", 6),
    ("park_osm_only", 8), ("park_assessor_only", 8), ("park_osm_assessor", 5), ("park_garage", 4),
    ("nobldg_use_no_parking", 6),  # no building, CMAP says a business or institution, no source says parking
    ("empty_infra", 8), ("empty_open_space", 6), ("empty_no_parking_signal", 6),  # today's Empty land
    ("use_agree", 6), ("use_disagree", 8),
)
INFRA = ("road", "rail", "utility", "transport")
# What the owner's answer means for each common category.
ANSWER_CATEGORY = {
    "surface_parking": "parking", "parking_garage": "parking", "empty": "vacant", "accessory": "vacant",
    "homes": "residential", "commercial": "commercial", "industrial": "industrial",
    "institutional": "institutional", "open_space": "open_space", "construction": "construction",
    "rail_utility": "rail_utility",
}
USE_CATEGORIES = ("residential", "commercial", "mixed_use", "industrial", "institutional", "open_space", "vacant",
                  "construction")


def _ring(g) -> list[list[float]] | None:
    """The outline of the largest polygon in ``g`` (a repaired outline can come back as a collection)."""
    polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")]
    if not polys:
        return None
    return _poly_ring(max(polys, key=lambda p: p.area))


def _sig(r: dict) -> dict[str, bool]:
    return {"cmap": r.get("cmap_parking_share", 0) >= PARKING_SHARE,
            "osm": r.get("osm_surface_parking_share", 0) >= PARKING_SHARE,
            "assessor": r.get("assessor") == "parking"}


def _common(c: str | None) -> str | None:
    if c == "mixed_use":
        return "commercial"
    if c in ("rail", "road", "utility", "transport"):
        return "rail_utility"
    if c == "exempt":
        return None  # the Assessor's EX says who pays tax, not the use
    return c


def stratum_of(r: dict) -> str | None:
    if r.get("no_outline") or r.get("unusual"):
        return None
    s = _sig(r)
    no_bldg = r.get("structure") in NO_BUILDING
    cm = r.get("cmap") if r.get("cmap_share", 0) >= 0.5 else None
    if any(s.values()) or r.get("osm_garage_share", 0) >= PARKING_SHARE:
        if no_bldg and any(s.values()):
            key = "+".join(k for k in ("cmap", "osm", "assessor") if s[k])
            return {"cmap+osm+assessor": "park_all3", "cmap+assessor": "park_cmap_assessor",
                    "cmap+osm": "park_cmap_osm", "cmap": "park_cmap_only", "osm": "park_osm_only",
                    "assessor": "park_assessor_only", "osm+assessor": "park_osm_assessor"}[key]
        if r.get("structure") == "built" and (s["cmap"] or r.get("osm_garage_share", 0) >= PARKING_SHARE):
            return "park_garage"
        return None
    if r.get("empty_land"):
        if cm in INFRA:
            return "empty_infra"
        if cm == "open_space":
            return "empty_open_space"
        return "empty_no_parking_signal"
    if no_bldg and cm in ("commercial", "mixed_use", "industrial", "institutional"):
        return "nobldg_use_no_parking"
    a, c = _common(r.get("assessor")), _common(cm)
    if a in USE_CATEGORIES and c in USE_CATEGORIES:
        return "use_agree" if a == c else "use_disagree"
    return None


def _exclusions(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for p in paths:
        d = json.loads(p.read_text())
        if isinstance(d, dict) and "lots" in d:
            out |= {x["pin"] for x in d["lots"]}
        elif isinstance(d, dict):
            out |= set(d)
        else:
            out |= set(d)
    return out


def draw(lots_path: Path, index: Path, sources: Path, ptaxsim: Path, exclude: list[Path], out: Path) -> dict:
    import numpy as np
    import shapely
    from shapely.strtree import STRtree

    from backend.discovery.index_backfill import lot_outlines

    rows = json.loads(lots_path.read_text())
    rows = rows["lots"] if isinstance(rows, dict) else rows
    skip = _exclusions(exclude)
    pool: dict[str, list[dict]] = {}
    for r in rows:
        s = stratum_of(r)
        if s and r["pin"] not in skip:
            pool.setdefault(s, []).append(r)
    rnd = random.Random(SEED)
    picked = []
    for s, n in STRATA:
        got = pool.get(s, [])
        picked += [dict(r, stratum=s) for r in rnd.sample(got, min(n, len(got)))]
    rnd.shuffle(picked)

    lat_a = np.array([r["lat"] for r in rows])
    lon_a = np.array([r["lon"] for r in rows])

    def near_idx(r):
        return np.nonzero(np.hypot((lat_a - r["lat"]) * _FT_LAT, (lon_a - r["lon"]) * _FT_LON) <= NEAR_FT)[0]

    db = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    cl = db.execute("SELECT wkb, pre_dir, name, typ FROM centerlines").fetchall()
    fps = shapely.from_wkb([x[0] for x in db.execute("SELECT wkb FROM footprints")])
    db.close()
    lines = shapely.from_wkb([c[0] for c in cl])
    names = [" ".join(x for x in (c[1], c[2], c[3]) if x) for c in cl]
    tree, fp_tree = STRtree(lines), STRtree(fps)
    addr: dict[str, str] = {}
    ix = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    want = sorted({rows[i]["pin"] for r in picked for i in near_idx(r)})
    for i in range(0, len(want), 900):
        chunk = want[i:i + 900]
        for pin, a in ix.execute(f"SELECT pin, json_extract(attrs, '$.address') FROM parcels WHERE pin IN "
                                 f"({','.join('?' * len(chunk))})", chunk):
            if a and not str(a).startswith("~"):
                addr[pin] = a
    ix.close()
    near = {r["pin"]: near_idx(r) for r in picked}
    outlines = lot_outlines(ptaxsim, {rows[i]["pin"].replace("-", "")[:10] for v in near.values() for i in v})
    out_lots = []
    for k, r in enumerate(picked):
        own10 = r["pin"].replace("-", "")[:10]
        own = outlines.get(own10)
        nb = [{"ring": ring, "address": addr.get(rows[i]["pin"])}
              for i in near[r["pin"]] if (p10 := rows[i]["pin"].replace("-", "")[:10]) in outlines and p10 != own10
              and (ring := _ring(outlines[p10]))]
        c = shapely.Point(r["lon"], r["lat"])
        idx = tree.query(c.buffer(0.0012), predicate="intersects")
        street = [[[round(x, 7), round(y, 7)] for x, y in (g.geoms[0] if g.geom_type == "MultiLineString" else g).coords]
                  for g in (lines[i] for i in idx)]
        buildings = []
        for i in fp_tree.query(c.buffer(0.0007), predicate="intersects"):
            g = fps[i] if fps[i].is_valid else shapely.make_valid(fps[i])
            if own is not None:
                g = g.difference(own.buffer(0.000005))  # never what stands on the lot being checked
            for part in getattr(g, "geoms", [g]):
                if part.geom_type == "Polygon" and not part.is_empty and part.area > 1e-10:
                    buildings.append(_poly_ring(part.simplify(0.000002)))
        lot_sqft = round(own.area * 364_000.0 * 364_000.0 * 0.7447) if own is not None else None
        out_lots.append({"id": k + 1, "pin": r["pin"], "stratum": r["stratum"], "lat": r["lat"], "lon": r["lon"],
                         "lot_sqft": lot_sqft, "ring": _ring(own) if own is not None else None, "neighbors": nb,
                         "street": street, "street_names": [names[i] for i in idx], "buildings": buildings,
                         "viewpoint": _viewpoint(street, r["lat"], r["lon"]),
                         # the sources' answers, for scoring only: never sent to the page
                         "truth_keys": {"cmap": r.get("cmap"), "assessor": r.get("assessor"), "osm": r.get("osm"),
                                        "signals": _sig(r), "structure": r.get("structure"),
                                        "land_kind": r.get("land_kind")}})
    pool_n = {s: len(v) for s, v in pool.items()}
    out.write_text(json.dumps({"seed": SEED, "pool": pool_n, "lots": out_lots}, separators=(",", ":")))
    return pool_n


HIDDEN = ("stratum", "truth_keys")


def serve(panel_path: Path, port: int) -> None:
    ell.LABELS = LABELS
    ell.PAGE = PAGE
    panel = json.loads(panel_path.read_text())
    blind = panel_path.with_name(".land_use_panel_blind.json")
    blind.write_text(json.dumps({"lots": [{k: v for k, v in lot.items() if k not in HIDDEN} for lot in panel["lots"]]}))
    try:
        ell.serve(blind, port)
    finally:
        blind.unlink(missing_ok=True)


SURFACE_STRATA = ("park_all3", "park_cmap_assessor", "park_cmap_osm", "park_cmap_only", "park_osm_only",
                  "park_assessor_only", "park_osm_assessor")
# Use precision is read only where the draw was about use: a parking lot CMAP codes to the business it serves is
# CMAP's own rule, not a wrong use, so the parking strata are left out of it.
USE_STRATA = ("use_agree", "use_disagree", "empty_infra", "empty_open_space")


def _ci(k: int, n: int) -> list[float]:
    return [max(0.0, round(x, 3)) for x in _wilson(k, n)]


def score(panel_path: Path) -> dict:
    """Counts only. Per stratum: the owner's answers. Per source: precision of surface parking (parking strata) and of
    each use category (use strata); on a CMAP/Assessor disagreement, which one the owner's answer matched."""
    panel = json.loads(panel_path.read_text())
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    per_stratum: dict[str, Counter] = {}
    src_park = {k: Counter() for k in ("cmap", "osm", "assessor")}
    src_use = {k: Counter() for k in ("cmap", "assessor")}
    winner = Counter()
    for lot in panel["lots"]:
        ans = (labels.get(lot["pin"]) or {}).get("answer") or "unlabeled"
        s = lot["stratum"]
        per_stratum.setdefault(s, Counter())[ans] += 1
        if ans in ("unlabeled", "cant_tell"):
            if s == "use_disagree":
                winner[ans] += 1
            continue
        t = lot["truth_keys"]
        if s in SURFACE_STRATA:
            for k, said in t["signals"].items():
                if said:
                    src_park[k]["surface_parking" if ans == "surface_parking" else "not_surface_parking"] += 1
        human = ANSWER_CATEGORY.get(ans)
        if s in USE_STRATA:
            for k in src_use:
                c = _common(t.get(k))
                if c in USE_CATEGORIES or c in ("parking", "rail_utility"):
                    src_use[k][f"{c}:{'right' if c == human else 'wrong'}"] += 1
        if s == "use_disagree":
            cm, asr = _common(t.get("cmap")), _common(t.get("assessor"))
            winner["cmap" if cm == human else "assessor" if asr == human else "neither"] += 1
    out: dict = {"labeled": sum(sum(v for k, v in c.items() if k != "unlabeled") for c in per_stratum.values()),
                 "strata": {s: dict(c) for s, c in per_stratum.items()}}
    # The candidate rule (any source says parking, no building): precision, weighted by each stratum's pool share.
    pool = {s: panel["pool"].get(s, 0) for s in SURFACE_STRATA}
    w = tot = 0.0
    rule = Counter()
    for s in SURFACE_STRATA:
        c = per_stratum.get(s, Counter())
        dec = sum(v for k, v in c.items() if k not in ("cant_tell", "unlabeled"))
        rule["surface_parking"] += c["surface_parking"]
        rule["decided"] += dec
        if dec:
            w += c["surface_parking"] / dec * pool[s]
            tot += pool[s]
    out["surface_rule"] = {**dict(rule), "ci95": _ci(rule["surface_parking"], rule["decided"]),
                           "weighted_precision": round(w / tot, 3) if tot else None}
    out["surface_by_source"] = {}
    for k, c in src_park.items():
        n = sum(c.values())
        out["surface_by_source"][k] = {**dict(c), "precision": round(c["surface_parking"] / n, 3) if n else None,
                                       "ci95": _ci(c["surface_parking"], n)}
    g = per_stratum.get("park_garage", Counter())
    gn = sum(v for k, v in g.items() if k not in ("cant_tell", "unlabeled"))
    out["garage"] = {"parking_garage": g["parking_garage"], "decided": gn, "ci95": _ci(g["parking_garage"], gn)}
    m = per_stratum.get("nobldg_use_no_parking", Counter())
    mn = sum(v for k, v in m.items() if k not in ("cant_tell", "unlabeled"))
    out["parking_missed_by_sources"] = {"surface_parking": m["surface_parking"], "decided": mn,
                                        "ci95": _ci(m["surface_parking"], mn),
                                        "pool": panel["pool"].get("nobldg_use_no_parking", 0)}
    out["use_disagree_matched"] = dict(winner)
    out["use_precision"] = {}
    for k, c in src_use.items():
        cats: dict[str, dict] = {}
        for key, v in c.items():
            cat, verdict = key.split(":")
            cats.setdefault(cat, {"right": 0, "wrong": 0})[verdict] += v
        for cat, d in cats.items():
            n = d["right"] + d["wrong"]
            d["precision"] = round(d["right"] / n, 3) if n else None
            d["ci95"] = _ci(d["right"], n)
        out["use_precision"][k] = cats
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--lots", type=Path, required=True)
    d.add_argument("--index", type=Path, default=Path("backend/data/discovery_index.db"))
    d.add_argument("--sources", type=Path, default=Path("backend/data/discovery_lot_sources.db"))
    d.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    d.add_argument("--exclude", type=Path, action="append", default=[])
    d.add_argument("--out", type=Path, default=PANEL)
    s = sub.add_parser("serve")
    s.add_argument("--panel", type=Path, default=PANEL)
    s.add_argument("--port", type=int, default=8034)
    c = sub.add_parser("score")
    c.add_argument("--panel", type=Path, default=PANEL)
    c.add_argument("--out", type=Path, default=None, help="write the counts here (precision.json)")
    a = ap.parse_args()
    if a.cmd == "draw":
        print(json.dumps(draw(a.lots, a.index, a.sources, a.ptaxsim, a.exclude, a.out), indent=1))
    elif a.cmd == "serve":
        serve(a.panel, a.port)
    else:
        result = score(a.panel)
        if a.out:
            a.out.write_text(json.dumps(result, indent=1) + "\n")
        print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
