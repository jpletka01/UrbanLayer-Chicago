"""Blind owner check for rail land (decision Item 121). No model calls; localhost only.

    PYTHONPATH=. python -m eval.rail_land_label draw --lots <lots.json from eval.rail_land measure --lots-out> \\
        --rail <folder from eval.rail_land fetch> [--exclude eval/land_use_panel.json ...]
    PYTHONPATH=. python -m eval.rail_land_label serve [--port 8035]
    PYTHONPATH=. python -m eval.rail_land_label score [--out eval/results/2026-11-13-rail-land/precision.json]

**Draw** (seeded 121, ``STRATA``): lots shown in Discovery today that a rail source touches, split by which sources
touch them (CMAP 2023's rail right-of-way over half the lot, a CTA elevated/at-grade line or a federal NARN main or
yard line running 25 ft or more through it), so each source and combination is measured on its own; lots CMAP codes
as road land (hidden since Item 112) that a CTA line crosses (rail or road?); and Empty-land lots within 60 ft of a
line that no source marks (what the sources miss).

**Blind.** Item 112's page (``land_use_label_page.html``'s machinery, this module's own answers): the outline, the
neighbors' own addresses, street names, the City's footprints around the lot, Street View, and the lot from above.
Never the rail lines, the sources' answers or the stratum. Labels go to the gitignored
``eval/results/2026-11-13-rail-land/labels.json``; ``score`` prints counts only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval import empty_land_label as ell
from eval import land_use_label as lul
from eval.rail_land import LINE_MIN_FT, combo, load_lines, to_feet

PANEL = Path("eval/rail_land_panel.json")
PAGE = Path(__file__).with_name("rail_land_label_page.html")
LABELS = Path("eval/results/2026-11-13-rail-land/labels.json")
SEED = 121
NEAR_FT = 60.0

STRATA = (
    ("cmap_cta", 10), ("cmap_narn", 8), ("cmap_only", 10), ("cmap_not_empty", 6),
    ("cta_only_empty", 8), ("cta_only_other", 5), ("narn_only_empty", 6), ("narn_only_other", 5),
    ("road_with_cta", 6), ("near_line_no_source", 6),
)
RAIL_ANSWERS = ("rail_under", "rail_yard")


def stratum_of(r: dict) -> str | None:
    if r.get("no_outline"):
        return None
    k = combo(r)
    if "rr_class" in k:
        return None  # railroad-class land is hidden already (Item 60)
    if r.get("infrastructure") == "road":
        return "road_with_cta" if r.get("cta_elevated_ft", 0) >= LINE_MIN_FT else None
    if r.get("unusual"):
        return None  # hidden today for another reason (a strip under 16 ft, common land)
    empty = r.get("empty_land")
    if k.startswith("cmap"):
        if not empty:
            return "cmap_not_empty"
        return {"cmap+cta": "cmap_cta", "cmap+narn": "cmap_narn", "cmap+cta+narn": "cmap_narn",
                "cmap": "cmap_only"}.get(k)
    if k == "cta":
        return "cta_only_empty" if empty else "cta_only_other"
    if k == "narn":
        return "narn_only_empty" if empty else "narn_only_other"
    if k == "none" and empty and r.get("near_line"):
        return "near_line_no_source"
    return None


def mark_near(rows: list[dict], rail: Path, ptaxsim: Path) -> None:
    """``near_line`` on shown Empty-land lots no source marks: a CTA elevated or NARN main/yard line within 60 ft."""
    import numpy as np
    from shapely.strtree import STRtree

    from backend.discovery.index_backfill import lot_outlines

    want = [r for r in rows if not r.get("no_outline") and r.get("empty_land") and not r.get("unusual")
            and combo(r) == "none"]
    lines = load_lines(rail)
    gs = np.array([to_feet(g) for k in ("cta_elevated", "narn_main", "narn_yard") for g, _ in lines.get(k, [])],
                  dtype=object)
    tree = STRtree(gs)
    outlines = lot_outlines(ptaxsim, {r["pin"].replace("-", "")[:10] for r in want})
    for r in want:
        lot = outlines.get(r["pin"].replace("-", "")[:10])
        if lot is not None and len(tree.query(to_feet(lot), predicate="dwithin", distance=NEAR_FT)):
            r["near_line"] = True


def draw(lots: Path, rail: Path, index: Path, sources: Path, ptaxsim: Path, exclude: list[Path], out: Path) -> dict:
    data = json.loads(lots.read_text())
    rows = data["lots"]
    mark_near(rows, rail, ptaxsim)
    tmp = out.with_suffix(".rows.json")
    tmp.write_text(json.dumps(rows))
    try:
        pool = lul.draw(tmp, index, sources, ptaxsim, exclude, out, STRATA, stratum_of, SEED)
    finally:
        tmp.unlink(missing_ok=True)
    by_pin = {r["pin"]: r for r in rows}
    panel = json.loads(out.read_text())
    for lot in panel["lots"]:
        r = by_pin[lot["pin"]]
        lot["truth_keys"] = {"sources": combo(r), "cmap_rail_share": r.get("cmap_rail_share", 0),
                             "cta_elevated_ft": r.get("cta_elevated_ft", 0),
                             "narn_ft": r.get("narn_main_ft", 0) + r.get("narn_yard_ft", 0),
                             "structure": r.get("structure"), "land_kind": r.get("land_kind"),
                             "infrastructure": r.get("infrastructure")}
    out.write_text(json.dumps(panel, separators=(",", ":")))
    return pool


def serve(panel_path: Path, port: int) -> None:
    ell.LABELS = LABELS
    ell.PAGE = PAGE
    panel = json.loads(panel_path.read_text())
    blind = panel_path.with_name(".rail_land_panel_blind.json")
    blind.write_text(json.dumps({"lots": [{k: v for k, v in lot.items() if k not in lul.HIDDEN}
                                          for lot in panel["lots"]]}))
    try:
        ell.serve(blind, port)
    finally:
        blind.unlink(missing_ok=True)


def score(panel_path: Path) -> dict:
    """Counts only: per stratum the owner's answers and the share that is rail land (Wilson 95%), per source the
    precision of "rail land" where that source is on the lot, and the candidate rules' precision weighted by pool."""
    panel = json.loads(panel_path.read_text())
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    per: dict[str, Counter] = {}
    src: dict[str, Counter] = {k: Counter() for k in ("cmap", "cta", "narn")}
    for lot in panel["lots"]:
        ans = (labels.get(lot["pin"]) or {}).get("answer") or "unlabeled"
        per.setdefault(lot["stratum"], Counter())[ans] += 1
        if ans in ("unlabeled", "cant_tell") or lot["stratum"] in ("road_with_cta", "near_line_no_source"):
            continue
        for k in src:
            if k in lot["truth_keys"]["sources"].split("+"):
                src[k]["rail" if ans in RAIL_ANSWERS else "not_rail"] += 1

    def rate(c: Counter, hit=RAIL_ANSWERS) -> dict:
        n = sum(v for k, v in c.items() if k not in ("unlabeled", "cant_tell"))
        k = sum(c[h] for h in hit)
        return {"rail": k, "decided": n, "share": round(k / n, 3) if n else None, "ci95": lul._ci(k, n)}

    out: dict = {"labeled": sum(sum(v for k, v in c.items() if k != "unlabeled") for c in per.values()),
                 "strata": {s: dict(c) | {"_rail": rate(c)} for s, c in per.items()},
                 "by_source": {k: dict(c) | {"precision": rate(Counter(rail_under=c["rail"], empty=c["not_rail"]))}
                               for k, c in src.items()}}
    rules = {"cmap_on_empty_land": ("cmap_cta", "cmap_narn", "cmap_only"),
             "cmap_any": ("cmap_cta", "cmap_narn", "cmap_only", "cmap_not_empty"),
             "cta_only_empty": ("cta_only_empty",), "narn_only_empty": ("narn_only_empty",)}
    for name, strata in rules.items():
        c = sum((per.get(s, Counter()) for s in strata), Counter())
        w = tot = 0.0
        for s in strata:
            r = rate(per.get(s, Counter()))
            if r["decided"]:
                w += r["share"] * panel["pool"].get(s, 0)
                tot += panel["pool"].get(s, 0)
        out.setdefault("rules", {})[name] = rate(c) | {"weighted": round(w / tot, 3) if tot else None,
                                                     "pool": sum(panel["pool"].get(s, 0) for s in strata)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--lots", type=Path, required=True)
    d.add_argument("--rail", type=Path, required=True)
    d.add_argument("--index", type=Path, default=Path("backend/data/discovery_index.db"))
    d.add_argument("--sources", type=Path, default=Path("backend/data/discovery_lot_sources.db"))
    d.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    d.add_argument("--exclude", type=Path, action="append", default=[])
    d.add_argument("--out", type=Path, default=PANEL)
    s = sub.add_parser("serve")
    s.add_argument("--panel", type=Path, default=PANEL)
    s.add_argument("--port", type=int, default=8035)
    c = sub.add_parser("score")
    c.add_argument("--panel", type=Path, default=PANEL)
    c.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if a.cmd == "draw":
        print(json.dumps(draw(a.lots, a.rail, a.index, a.sources, a.ptaxsim, a.exclude, a.out), indent=1))
    elif a.cmd == "serve":
        serve(a.panel, a.port)
    else:
        res = score(a.panel)
        if a.out:
            a.out.write_text(json.dumps(res, indent=1) + "\n")
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
