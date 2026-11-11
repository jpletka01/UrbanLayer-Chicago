"""Measure the Assessor-address tier for Discovery's approximate ("~") addresses (decision Item 109). Read-only, offline.

Runs the production check (``backend.discovery.assessor_address``) over a Discovery index and the local lot-sources
copy (built with ``python -m backend.discovery.lot_sources --addresses-only``):

* **calibration** (lots WITH their own Address Point): does the check accept their real address (false rejections),
  and does it reject the same street's address 20 numbers away (a different lot two or three doors down)?
* **the approximate lots**: how many have an Assessor address, how many pass, why the rest fail, how often the
  Assessor's number equals the "~" one, and when both are on the same street, which number is nearer the number the
  lot's position implies; unit tails; the vacant over-an-acre lots (Item 60's hidden set).

    PYTHONPATH=. python -m eval.assessor_address_check --index <discovery_index.db> --sources <lot_sources.db> \\
        [--ptaxsim backend/data/ptaxsim.db] [--calibration 2000] [--seed 20261111]
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sqlite3
from pathlib import Path

import shapely

from backend.discovery.assessor_address import AddressSources, Parsed, parse, to_ft, verified_address
from backend.discovery.index_backfill import lot_outlines


def _rows(index: Path, approximate: bool) -> list[tuple]:
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    try:
        op = "like" if approximate else "not like"
        return db.execute(
            "SELECT pin, lat, lon, json_extract(attrs, '$.address'), json_extract(attrs, '$.is_vacant'), "
            "json_extract(attrs, '$.land_sqft') FROM parcels WHERE pin like '%0000' "
            f"AND json_extract(attrs, '$.address') {op} '~%' AND json_extract(attrs, '$.address') IS NOT NULL"
        ).fetchall()
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    ap.add_argument("--calibration", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261111)
    args = ap.parse_args()
    src = AddressSources.load(args.sources)
    if src is None:
        raise SystemExit(f"{args.sources} has no address tables")
    out: dict = {}

    # Calibration: lots with their own Address Point.
    own = _rows(args.index, approximate=False)
    random.seed(args.seed)
    cal = random.sample(own, min(args.calibration, len(own)))
    lots = lot_outlines(args.ptaxsim, {r[0].replace("-", "")[:10] for r in cal})
    real = collections.Counter()
    moved = {k: collections.Counter() for k in (4, 8, 20)}
    for pin, lat, lon, addr, _v, _l in cal:
        p = parse(addr)
        if p is None:
            real["unparsed"] += 1
            continue
        lot = lots.get(pin.replace("-", "")[:10]) or shapely.Point(lon, lat)
        real[verified_address(addr, lot, src.streets, None)[1]] += 1
        for k, c in moved.items():  # the same street and side, k numbers on (one lot is about 4)
            far = Parsed(p.number + k, p.predir, p.name, p.typ, "")
            c[verified_address(far.base, lot, src.streets, None)[1]] += 1
    n_real = sum(v for k, v in real.items() if k != "unparsed")
    out["calibration"] = {
        "lots": len(cal), "own_address_accepted": real["ok"], "accept_share": round(real["ok"] / n_real, 4),
        "own_address_reasons": dict(real),
        "accepted_when_moved": {f"+{k}": {"accepted": c["ok"], "share": round(c["ok"] / max(1, sum(c.values())), 4)}
                                for k, c in moved.items()},
    }

    # The approximate lots.
    approx = _rows(args.index, approximate=True)
    lots = lot_outlines(args.ptaxsim, {r[0].replace("-", "")[:10] for r in approx})
    assessor, points = src.lookup(r[0].replace("-", "") for r in approx)
    reasons: collections.Counter = collections.Counter()
    same_number = units = shared_ok = 0
    closer = collections.Counter()  # same street, different number: whose number is nearer the lot's position?
    by_addr = collections.Counter(assessor.values())
    vacant_acre = collections.Counter()
    for pin, lat, lon, tilde, vacant, land in approx:
        p14 = pin.replace("-", "")
        a = assessor.get(p14)
        parsed = parse(a)
        lot = lots.get(p14[:10]) or shapely.Point(lon, lat)
        address, reason = verified_address(a, lot, src.streets, points)
        reasons[reason] += 1
        if address:
            t = parse(tilde[1:])
            same_number += bool(t and src.streets.resolve(t) and src.streets.resolve(t).base == address)
            shown = parse(address)
            t = src.streets.resolve(t) if t else None
            if t and t.street == shown.street and t.number != shown.number:
                _ok, _r, expected = src.streets.check(shown, to_ft(lot))
                da, dt = abs(shown.number - expected), abs(t.number - expected)
                closer["assessor" if da < dt else "tilde" if dt < da else "tie"] += 1
            units += bool(parsed and parsed.unit)
            shared_ok += by_addr[a] > 1
        if vacant and (land or 0) > 43_560:
            vacant_acre["passes" if address else "stays_approximate"] += 1
    n = len(approx)
    out["approximate_lots"] = {
        "lots": n, "with_assessor_address": sum(1 for r in approx if assessor.get(r[0].replace("-", ""))),
        "pass": reasons["ok"], "pass_share": round(reasons["ok"] / n, 4), "reasons": dict(reasons.most_common()),
        "pass_same_as_tilde": same_number, "pass_had_unit_tail": units,
        "pass_address_on_several_pins": shared_ok,
        "pass_same_street_other_number_nearer_position": dict(closer), "vacant_over_an_acre": dict(vacant_acre),
    }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
