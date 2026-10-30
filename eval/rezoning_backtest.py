"""Backtest of the rezoning title parser and address resolver (WS1 M5, plan §6.4).

For every rezoning ordinance Council passed in the last year that is ALREADY on the City's
zoning map, parse its title, resolve the listed addresses to parcels, then ask the map what
ordinance each parcel's polygon carries. If the parser and resolver are right, the parcel's
polygon carries that ordinance.

- **Precision** = resolved parcels whose map polygon carries that ordinance's number. Gate: >= 95%.
  A miss is classified: *superseded* (the polygon carries a NEWER ordinance, so the parcel was
  rezoned again), or *other* (a real miss).
- **Wrong street** = a resolved parcel whose own address street is not one the title names.
  Gate: 0.
- **Parse rate** = titles that parse clean. Gate: >= 95%. The rest are listed.
- **Ordinance coverage** = clean on-map ordinances with at least one resolved parcel. Not gated: Address
  Points holds a point only for a built address, so vacant lots resolve to nothing.
- Recall per parcel is not measured here (a polygon is not a parcel).

Uses only the City Clerk API, Cook County Address Points and the City's zoning MapServer: public,
free, and no model call. Requests are paced and concurrency is low.

    PYTHONPATH=. python -m eval.rezoning_backtest [--per-record 8] [--out eval/results/rezoning_backtest.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import httpx

from backend.legislation import address_titles, rezonings
from backend.retrieval import clerk, zoning

CONCURRENCY = 4


async def _polygon_docno(client: httpx.AsyncClient, lat: float, lon: float) -> dict | None:
    params = {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "outFields": "CLERK_DOCNO,ORDINANCE_DATE",
        "returnGeometry": "false", "f": "json",
    }
    resp = await client.get(zoning.ZONING_QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    feats = resp.json().get("features") or []
    return feats[0]["attributes"] if feats else None


async def _wrong_street(r: dict, sample: list[list]) -> int:
    """Independent check: of the sampled parcels, how many have NO address point on a street the title
    names (direction + name)? Asked of Address Points by PIN, not through the range query that found them."""
    from backend.config import get_settings
    from backend.retrieval.socrata import socrata_get

    st = get_settings()
    want = {(s["dir"], n) for s in r["parse"]["segments"] for n in address_titles.name_candidates(s["name"])}
    ids = ",".join(f"'{p[0]}'" for p in sample)
    rows = await socrata_get(
        st.dataset_address_points,
        {"$where": f"pin in ({ids})", "$select": "pin,st_predir,st_name", "$limit": 5000},
        base_url=st.cook_county_socrata_base, app_token=st.cook_county_socrata_token or None,
    )
    good: set[str] = set()
    for row in rows:
        d = str(row.get("st_predir", "")).strip().upper()[:1]
        if (d, str(row.get("st_name", "")).strip().upper()) in want:
            good.add(str(row.get("pin", "")))
    return sum(1 for p in sample if p[0] not in good)


def _sample(pins: list[list], k: int, seed: str) -> list[list]:
    if len(pins) <= k:
        return pins
    return random.Random(seed).sample(pins, k)


async def run(per_record: int) -> dict:
    since = date.today() - timedelta(days=rezonings.LOOKBACK_DAYS)
    matters = await clerk.passed_since(since, (clerk.ZONING_RECLASSIFICATIONS,))
    rows = await rezonings.build_rows(matters, [], overrides={}, resolve_on_map=True)

    parsed = Counter(r["parse"]["status"] for r in rows)
    on_map = [r for r in rows if r["map_status"] == "on_map"]
    testable = [r for r in on_map if r["parse"]["status"] == "clean" and r.get("pins")]

    sem = asyncio.Semaphore(CONCURRENCY)
    hits = misses = superseded = other = no_point = 0
    wrong_street = 0   # parcels with no address point on a street the title names (independent check)
    street_checked = 0
    bad: list[dict] = []
    per_record_result: list[dict] = []
    if True:
        client = zoning._get_arcgis_client()  # the City's server refuses a custom User-Agent (403); this client is the one the app uses

        async def check(r: dict, pin: list):
            nonlocal hits, misses, superseded, other, no_point
            if pin[1] is None:
                no_point += 1
                return
            async with sem:
                try:
                    attrs = await _polygon_docno(client, pin[1], pin[2])
                except Exception as exc:  # a failed lookup is not a miss
                    no_point += 1
                    bad.append({"record": r["record"], "pin": pin[0], "error": str(exc)[:120]})
                    return
            docno = (attrs or {}).get("CLERK_DOCNO") or ""
            if docno == r["record"]:
                hits += 1
                return
            misses += 1
            newer = bool(attrs and attrs.get("ORDINANCE_DATE")
                         and attrs["ORDINANCE_DATE"] / 1000 > _epoch(r["passed_on"]) + 86400)
            if newer:
                superseded += 1
            else:
                other += 1
                bad.append({"record": r["record"], "pin": pin[0], "polygon_docno": docno or None})

        tasks = []
        for r in testable:
            sample = _sample(r["pins"], per_record, r["record"])
            street_checked += len(sample)
            wrong_street += await _wrong_street(r, sample)
            tasks += [check(r, p) for p in sample]
            per_record_result.append({"record": r["record"], "pins": len(r["pins"]), "tested": len(sample),
                                      "unresolved": r.get("unresolved") or []})
        await asyncio.gather(*tasks)

    tested = hits + misses
    return {
        "since": since.isoformat(),
        "ordinances": {"passed": len(rows), "on_map": len(on_map), "off_map": len(rows) - len(on_map)},
        "parse": dict(parsed),
        "parse_clean_pct": round(100 * parsed["clean"] / max(len(rows), 1), 1),
        "unparsed": [{"record": r["record"], "notes": r["parse"]["notes"], "title": r["title"][:200]}
                     for r in rows if r["parse"]["status"] != "clean"],
        "on_map_clean": sum(1 for r in on_map if r["parse"]["status"] == "clean"),
        "on_map_testable": len(testable),
        "ordinances_resolved_pct": round(100 * len(testable) / max(sum(1 for r in on_map if r["parse"]["status"] == "clean"), 1), 1),
        "on_map_no_parcels": [r["record"] for r in on_map if r["parse"]["status"] == "clean" and not r.get("pins")],
        "parcels_tested": tested, "hits": hits, "misses": misses, "superseded": superseded, "other_misses": other,
        "lookup_failures": no_point,
        "precision_pct": round(100 * hits / tested, 1) if tested else None,
        "precision_excluding_superseded_pct": round(100 * hits / (hits + other), 1) if hits + other else None,
        "wrong_street": wrong_street, "street_checked": street_checked,
        "examples_of_other_misses": [b for b in bad if "polygon_docno" in b][:15],
        "per_record": per_record_result,
    }


def _epoch(iso: str) -> float:
    from datetime import datetime, timezone

    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-record", type=int, default=8, help="parcels sampled per ordinance (default 8)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    result = asyncio.run(run(args.per_record))
    slim = {k: v for k, v in result.items() if k != "per_record"}
    print(json.dumps(slim, indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1) + "\n")
    ok = (result["parse_clean_pct"] >= 95 and (result["precision_pct"] or 0) >= 95 and result["wrong_street"] == 0)
    print("GATES:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
