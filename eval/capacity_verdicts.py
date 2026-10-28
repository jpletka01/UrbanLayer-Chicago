"""WS8 Phase 0 slice 5: which community areas could be colored, and how sure are we?

Combines the index census (``eval/capacity_coverage.py``) with the fallback-chain sample
(``eval/capacity_fallbacks.py``).  For each community area the share of map polygons with a utilization figure is
projected three ways:

  now        the index as built (state ``computable``)
  standard   plus the sampled share of no-area parcels the chain resolves from sources at standard confidence
  all        plus footprint and energy-benchmark areas too (an upper bound)

The sample is stratified by community area, so a pooled rate would over-weight small areas.  Rates are therefore
taken per Assessor class group (2 residential, 3 multifamily, 5 commercial, other), pooled across areas, and
applied to each area's own count of no-area polygons in that group; the 95% Wilson interval of each rate carries
through to a low and a high projection.  The verdict uses the confidence standard's coverage thresholds.

Source confidence of a resolved area (assumption, stated in the decision record):
  standard  commercial_valuation   Assessor, annual, a valuation of that building
  low       energy_benchmark       owner-reported gross floor area
  low       footprint              City layer last updated 2015; the area column is undocumented

Usage:  PYTHONPATH=. python -m eval.capacity_verdicts --index <discovery_index.db> \
            --census eval/results/2026-10-28-ws8/index_census.json \
            --fallbacks eval/results/2026-10-28-ws8/fallback_chain.json \
            [--out eval/results/2026-10-28-ws8/area_verdicts.json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from eval.capacity_coverage import classify, coverage_verdict
from eval.capacity_fallbacks import _ca, wilson

STANDARD_SOURCES = frozenset({"commercial_valuation"})
ALL_SOURCES = frozenset({"commercial_valuation", "energy_benchmark", "footprint"})
GROUPS = ("2", "3", "5", "other")


def class_group(cls: str | None) -> str:
    major = (cls or "")[:1]
    return major if major in ("2", "3", "5") else "other"


def group_rates(records: list[dict], sources: frozenset[str]) -> dict[str, dict]:
    """Per class group: resolved count / n and its 95% interval, for the no-area stratum, counting only
    resolutions from ``sources``.  A fetch error is never rated (it is excluded from n)."""
    n: Counter = Counter()
    k: Counter = Counter()
    for r in records:
        if r["stratum"] != "unknown_gfa" or r["outcome"] == "fetch_error":
            continue
        g = class_group(r.get("class"))
        n[g] += 1
        k[g] += r["outcome"] == "resolved" and r["source"] in sources
    out = {}
    for g in GROUPS:
        lo, hi = wilson(k[g], n[g])
        out[g] = {"n": n[g], "k": k[g], "rate": (k[g] / n[g]) if n[g] else 0.0, "lo": lo if n[g] else 0.0, "hi": hi if n[g] else 0.0}
    return out


def condo_rate(records: list[dict], sources: frozenset[str]) -> dict:
    usable = [r for r in records if r["stratum"] == "condo_bldg" and r["outcome"] != "fetch_error"]
    k = sum(r["outcome"] == "resolved" and r["source"] in sources for r in usable)
    lo, hi = wilson(k, len(usable))
    return {"n": len(usable), "k": k, "rate": (k / len(usable)) if usable else 0.0, "lo": lo, "hi": hi}


def project_area(
    now_computable: int, polygons: int, unknown_by_group: dict[str, int], condo_polygons: int,
    rates: dict[str, dict], condo: dict,
) -> dict:
    """The three projections for one community area, as shares of its polygons, with the low/high interval."""
    def share(key: str) -> float:
        gain = sum(unknown_by_group.get(g, 0) * rates[g][key] for g in GROUPS) + condo_polygons * condo[key]
        return (now_computable + gain) / polygons if polygons else 0.0

    return {"point": round(share("rate"), 4), "low": round(share("lo"), 4), "high": round(share("hi"), 4)}


def verdict_band(proj: dict) -> dict:
    """The verdict at the point estimate, and whether the interval stays inside one state."""
    states = {coverage_verdict(proj[k]) for k in ("low", "point", "high")}
    return {"verdict": coverage_verdict(proj["point"]), "certain": len(states) == 1, "range": sorted(states)}


def unknown_counts(index: Path) -> dict[int, Counter]:
    """Per community area, no-area parcels (index state ``unknown_gfa``) by class group."""
    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    out: dict[int, Counter] = defaultdict(Counter)
    for _pin, attrs_json, regions in con.execute("select pin, attrs, regions from parcels where pin like '%-0000'"):
        attrs = json.loads(attrs_json)
        ca = _ca(regions)
        if ca is not None and classify(attrs) == "unknown_gfa":
            out[ca][class_group(attrs.get("class"))] += 1
    return out


def build(census: dict, fallbacks: dict, unknown: dict[int, Counter]) -> dict:
    records = fallbacks["parcels"]
    polys = census["polygons"]["by_community_area"]
    result: dict = {"areas": {}, "rates": {}}
    for name, sources in (("standard", STANDARD_SOURCES), ("all", ALL_SOURCES)):
        result["rates"][name] = {"unknown_gfa_by_class_group": group_rates(records, sources), "condo_building": condo_rate(records, sources)}
    for ca, block in polys.items():
        if ca == "None":
            continue
        states = block["states"]
        n = block["n"]
        entry = {"polygons": n, "now": round(states["computable"] / n, 4) if n else 0.0, "now_verdict": block["verdict"]}
        for name in ("standard", "all"):
            r = result["rates"][name]
            proj = project_area(states["computable"], n, dict(unknown.get(int(ca), {})), states["condo_unit"],
                                r["unknown_gfa_by_class_group"], r["condo_building"])
            entry[name] = {**proj, **verdict_band(proj)}
        result["areas"][ca] = entry
    result["summary"] = {
        key: dict(Counter(a[key]["verdict"] if key != "now" else a["now_verdict"] for a in result["areas"].values()))
        for key in ("now", "standard", "all")
    }
    result["uncertain_under_standard"] = sorted(ca for ca, a in result["areas"].items() if not a["standard"]["certain"])
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--fallbacks", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    census = json.loads(args.census.read_text())
    result = build(census, json.loads(args.fallbacks.read_text()), unknown_counts(args.index))
    city_unknown = sum(a["polygons"] for a in result["areas"].values())
    print(f"areas {len(result['areas'])}, polygons {city_unknown}")
    for name in ("standard", "all"):
        for g, v in result["rates"][name]["unknown_gfa_by_class_group"].items():
            print(f"  {name:8s} class {g:5s} {v['k']:>4d}/{v['n']:<4d} = {v['rate']:6.1%} (95% {v['lo']:.1%}-{v['hi']:.1%})")
        c = result["rates"][name]["condo_building"]
        print(f"  {name:8s} condo       {c['k']:>4d}/{c['n']:<4d} = {c['rate']:6.1%} (95% {c['lo']:.1%}-{c['hi']:.1%})")
    print("verdict counts:", result["summary"])
    print("uncertain under standard sources:", result["uncertain_under_standard"])
    if args.out:
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
