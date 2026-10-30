"""Backtest of the landmark-designation title parser, the address resolver and the map's lag (WS1 M5b).

For every Chicago Landmark designation Council passed in the last 400 days, parse the title, resolve the
listed addresses and blocks to parcels (Address Points), then ask the City's landmark layers (5 individual
landmarks, 6 landmark and historic districts) whether each parcel is on the map as a landmark today.

- **Parse rate** = designation titles that parse clean. Gate: >= 90%. The rest are listed.
- **Wrong street** = a resolved parcel whose own address is not on a street the title names (asked of Address
  Points by PIN, independent of the range query that found it). Gate: 0.
- **On the map, by age** = of the resolved parcels (a sample for a district), the share the landmark layers show
  today, bucketed by the ordinance's age. This is the measurement behind the lookback: it says how long the map
  really takes, so the Profile does not keep flagging an ordinance the map long ago caught up to. A building
  designation's parcel should be on the map once the map catches up; a district's listed blocks include parcels
  outside its boundary, so its share is reported separately and never gated.
- Nothing here compares a name: the layers are asked about the parcel's own point.

Uses only the City Clerk API, Cook County Address Points and the City's zoning MapServer: public, free, and no
model call. Requests are paced and concurrency is low.

    PYTHONPATH=. python -m eval.designation_backtest [--per-record 12] [--out eval/results/designation_backtest.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from backend.legislation import designations
from backend.retrieval import clerk
from backend.retrieval.regulatory import overlays
from eval.rezoning_backtest import _wrong_street

DAYS = 400
CONCURRENCY = 4
BUCKETS = ((0, 30), (30, 90), (90, 180), (180, 400))


def _sample(pins: list[list], k: int, seed: str) -> list[list]:
    return pins if len(pins) <= k else random.Random(seed).sample(pins, k)


def _bucket(age: int) -> str:
    for lo, hi in BUCKETS:
        if lo <= age < hi:
            return f"{lo}-{hi} days"
    return f"{BUCKETS[-1][1]}+ days"


async def run(per_record: int) -> dict:
    today = date.today()
    matters = await clerk.passed_since(today - timedelta(days=DAYS), (designations.CATEGORY,))
    rows = await designations.build_rows(matters, [])
    client = overlays._get_arcgis_client()
    sem = asyncio.Semaphore(CONCURRENCY)

    async def on_map(lat: float, lon: float) -> bool | None:
        async with sem:
            try:
                hits = [await overlays.query_overlay_checked(lat, lon, lid, client=client) for lid in (5, 6)]
            except Exception:
                return None  # a failed lookup is not a miss
        return any(h is not None for h in hits)

    per: list[dict] = []
    wrong = checked = 0
    for r in rows:
        age = (today - date.fromisoformat(r["passed_on"])).days
        rec = {"record": r["record"], "passed_on": r["passed_on"], "age_days": age, "status": r["parse"]["status"],
               "kind": r["parse"].get("kind"), "name": r["parse"].get("name"), "pins": len(r.get("pins") or []),
               "unresolved": r.get("unresolved") or [], "tested": 0, "on_map": 0, "lookup_failed": 0}
        if r["parse"]["status"] == "clean" and r.get("pins"):
            sample = _sample(r["pins"], per_record, r["record"])
            checked += len(sample)
            wrong += await _wrong_street(r, sample)
            results = await asyncio.gather(*(on_map(p[1], p[2]) for p in sample if p[1] is not None))
            rec["tested"] = sum(1 for x in results if x is not None)
            rec["on_map"] = sum(1 for x in results if x)
            rec["lookup_failed"] = sum(1 for x in results if x is None)
        per.append(rec)

    by_age: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"tested": 0, "on_map": 0}))
    for rec in per:
        for kind in (rec["kind"] or "building",):
            b = by_age[_bucket(rec["age_days"])][kind]
            b["tested"] += rec["tested"]
            b["on_map"] += rec["on_map"]
    clean = sum(1 for r in per if r["status"] == "clean")
    return {
        "since": (today - timedelta(days=DAYS)).isoformat(), "designations": len(per), "clean": clean,
        "parse_rate": round(clean / len(per), 3) if per else None,
        "unparsed": [r["record"] for r in per if r["status"] != "clean"],
        "wrong_street": wrong, "street_checked": checked,
        "with_parcels": sum(1 for r in per if r["pins"]), "no_parcels": [r["record"] for r in per if r["status"] == "clean" and not r["pins"]],
        "on_map_by_age": {k: dict(v) for k, v in sorted(by_age.items())},
        "records": per,
    }


def report(res: dict) -> str:
    lines = [
        f"designations since {res['since']}: {res['designations']}  clean {res['clean']} ({res['parse_rate']:.0%})  unparsed {res['unparsed']}",
        f"parcels resolved for {res['with_parcels']} of {res['clean']} clean; no address point for {res['no_parcels']}",
        f"wrong street: {res['wrong_street']} of {res['street_checked']} sampled parcels (gate 0)",
        "on the landmark map today, by the ordinance's age:",
    ]
    for bucket, kinds in res["on_map_by_age"].items():
        for kind, c in kinds.items():
            share = f"{c['on_map'] / c['tested']:.0%}" if c["tested"] else "n/a"
            lines.append(f"  {bucket:>13} {kind:>9}: {c['on_map']} of {c['tested']} ({share})")
    lines.append("per record (age, parcels, on map / tested):")
    for r in sorted(res["records"], key=lambda r: r["age_days"]):
        lines.append(f"  {r['record']:>14} {r['age_days']:>4} d {r['kind'] or '-':>9} {r['status']:>8} pins {r['pins']:>3}  {r['on_map']}/{r['tested']}  {(r['name'] or '')[:42]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-record", type=int, default=12)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    res = asyncio.run(run(args.per_record))
    print(report(res))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res, indent=2) + "\n")
    ok = res["wrong_street"] == 0 and (res["parse_rate"] or 0) >= 0.90
    print("\nGATES:", "pass" if ok else "FAIL")
    sys.stdout.flush()
    os._exit(0 if ok else 1)  # the shared HTTP clients keep the process alive otherwise


if __name__ == "__main__":
    main()
