"""WS8 Phase 1: how much of each capacity-map view can be colored, on a fixed set of views?

No model calls.  For each parcel of the 100-address panel (``eval/lot_panel.json``) and for a fixed set of
downtown points (the Loop, Near South Side, Near West Side, where Item 36 projected the lowest coverage), build
the Profile's capacity map in-process (``backend.capacity_map.build_capacity_map``: the Discovery index, the local
ptaxsim polygons, the committed Commercial Valuation artifact, and the City's zoning layer over the network) and
record the share of the view's polygons that can be colored, its verdict and its state counts.

Item 36 projected about 70-75% colorable citywide and far less downtown.  A view far from that is a reason to
stop and look before the map ships; the script prints the views sorted by share so the outliers are on top.

The panel was built for field coverage across classes (about half its parcels are commercial, against 8% of the
city's base parcels), so it is not a population sample.  ``--random N`` adds N base parcels drawn uniformly from
the index with a fixed seed: those views are the check against the citywide projection.  Views overlap, so a
pooled share describes the views only.

Usage:  PYTHONPATH=. python -m eval.capacity_map_panel [--index <discovery_index.db>] [--radius-mi 0.1] [--random 200] \
            [--out eval/results/2026-10-31-ws8/capacity_map_panel.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from eval.capacity_panel import dashed
from eval.lot_coverage import PANEL_FILE

CONCURRENCY = 2

# Fixed downtown points (lat, lon): street intersections, so the sample is reproducible.
DOWNTOWN = {
    "Loop: State & Madison": (41.88206, -87.62781),
    "Loop: LaSalle & Jackson": (41.87792, -87.63229),
    "Loop: Wells & Lake": (41.88569, -87.63391),
    "Near South Side: Michigan & 18th": (41.85797, -87.62420),
    "Near South Side: State & Cermak": (41.85302, -87.62696),
    "Near South Side: Prairie & 16th": (41.86027, -87.62126),
    "Near West Side: Halsted & Randolph": (41.88426, -87.64755),
    "Near West Side: Ashland & Madison": (41.88148, -87.66650),
    "Near West Side: Racine & Taylor": (41.86956, -87.65705),
}


def view_row(label: str, body: dict, seconds: float) -> dict:
    s = body.get("summary") or {}
    return {
        "view": label,
        "polygons": s.get("polygons", 0),
        "colorable": s.get("colorable", 0),
        "colorable_share": s.get("colorable_share", 0.0),
        "verdict": s.get("verdict"),
        "states": {k: v for k, v in (s.get("states") or {}).items() if v},
        "unchecked": body.get("unchecked") or [],
        "reason": body.get("reason"),
        "seconds": round(seconds, 2),
    }


def pooled(rows: list[dict]) -> dict:
    """Totals over the views that drew a map (a view that could not be drawn is counted apart)."""
    drawn = [r for r in rows if r["polygons"] and not r["unchecked"]]
    n = sum(r["polygons"] for r in drawn)
    c = sum(r["colorable"] for r in drawn)
    states: Counter = Counter()
    for r in drawn:
        states.update(r["states"])
    return {
        "views": len(rows),
        "drawn": len(drawn),
        "not_drawn": Counter((r["reason"] or ",".join(r["unchecked"]) or "empty") for r in rows if r not in drawn),
        "polygons": n,
        "colorable_share_pooled": round(c / n, 4) if n else None,
        "colorable_share_median": round(statistics.median(r["colorable_share"] for r in drawn), 4) if drawn else None,
        "verdicts": Counter(r["verdict"] for r in drawn),
        "states": dict(states.most_common()),
        "seconds_p50": round(statistics.median(r["seconds"] for r in rows), 2) if rows else None,
        "seconds_max": max((r["seconds"] for r in rows), default=None),
    }


def random_pins(n: int, seed: int) -> list[str]:
    """``n`` base-parcel PINs drawn uniformly from the loaded index (sorted first, so the seed reproduces)."""
    import random

    from backend.discovery import parcel_source
    from backend.discovery.parcel import default_source

    pins = sorted(p.pin for p in default_source.get(parcel_source.current_version()) if p.pin.endswith("-0000"))
    return random.Random(seed).sample(pins, min(n, len(pins)))


async def run(radius_mi: float, random_n: int = 0, seed: int = 31) -> dict:
    from backend.capacity_map import build_capacity_map

    panel = json.loads(Path(PANEL_FILE).read_text())["addresses"]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(label: str, **kw) -> dict:
        async with sem:
            t = time.perf_counter()
            body = await build_capacity_map(radius_mi=radius_mi, **kw)
            return view_row(label, body, time.perf_counter() - t)

    seen: set[str] = set()
    panel_jobs = []
    for a in panel:
        pin = dashed(a["truth_pin"])
        if pin[:13] in seen:
            continue
        seen.add(pin[:13])
        panel_jobs.append(one(f"{a['address']} ({pin})", pin=pin, lat=None, lon=None))
    panel_rows = await asyncio.gather(*panel_jobs)
    downtown_rows = await asyncio.gather(*(one(k, pin=None, lat=v[0], lon=v[1]) for k, v in DOWNTOWN.items()))
    random_rows = await asyncio.gather(*(one(pin, pin=pin, lat=None, lon=None) for pin in random_pins(random_n, seed)))
    return {
        "radius_mi": radius_mi,
        "panel": {"summary": pooled(panel_rows), "views": sorted(panel_rows, key=lambda r: r["colorable_share"])},
        "downtown": {"summary": pooled(downtown_rows), "views": sorted(downtown_rows, key=lambda r: r["colorable_share"])},
        "random": {"n": random_n, "seed": seed, "summary": pooled(random_rows),
                   "views": sorted(random_rows, key=lambda r: r["colorable_share"])},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, help="a Discovery index file (default: settings.discovery_index_path)")
    ap.add_argument("--radius-mi", type=float, default=0.1)
    ap.add_argument("--random", type=int, default=0, help="also N uniformly drawn base parcels (fixed seed)")
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    from backend.config import get_settings

    if args.index:
        get_settings().discovery_index_path = args.index
    from backend.discovery import parcel_source
    from backend.discovery.parcel_index import read_meta

    parcel_source.ensure_loaded()
    meta = read_meta(get_settings().discovery_index_path)
    result = {"index": {"data_version": getattr(meta, "data_version", None), "community_areas": getattr(meta, "community_areas", None)},
              **asyncio.run(run(args.radius_mi, args.random, args.seed))}
    for part in ("panel", "downtown", "random"):
        s = result[part]["summary"]
        print(f"{part}: {s['drawn']} of {s['views']} views drawn ({dict(s['not_drawn'])} not); pooled colorable "
              f"{s['colorable_share_pooled']}, median {s['colorable_share_median']}; verdicts {dict(s['verdicts'])}; "
              f"p50 {s['seconds_p50']} s, max {s['seconds_max']} s")
        for r in [v for v in result[part]["views"] if v["polygons"]][:5]:
            print(f"  {r['colorable_share']:6.1%} {r['verdict']:8s} n={r['polygons']:3d} {r['view']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True, default=dict))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
