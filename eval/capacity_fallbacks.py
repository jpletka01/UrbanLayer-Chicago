"""WS8 Phase 0 slice 2: how much building area does the Profile's fallback chain add over the Discovery index?

The index takes building area from the Assessor's regression-class characteristics only.  The Profile adds
three fallbacks (commercial valuation, energy benchmarking, building footprints; ``property/__init__.py``
and ``building_facts.py``).  This script draws a seeded sample of index parcels whose building area is
missing, runs the Profile's own fetchers on them, and applies the Profile's own merge rules, so the answer is
what a Profile for that parcel would show.  No model calls.

Strata (base parcels, suffix 0000, inside a community-area polygon):
  unknown_gfa  index state ``unknown_gfa``: the parcels the chain could turn into utilization figures
  condo_bldg   buildings whose unit PINs are condos: a unit's area (condo characteristics) is NOT the building's,
               so only commercial valuation, energy benchmarking and footprints can supply a building area

A resolved area counts only when it is the parcel's own (not a multi-PIN complex total, not a footprint larger
than the lot) and implies an existing FAR no more than 3x the zone cap (``classify``'s guard).  A fetch that
failed is never read as "no record": the parcel is set aside as ``fetch_error`` and left out of every rate.

Usage:  PYTHONPATH=. python -m eval.capacity_fallbacks --index <discovery_index.db> \
            [--per-area 25] [--condo-per-area 10] [--seed 28] [--out eval/results/2026-10-28-ws8/fallback_chain.json]
Reads the shared Socrata client (app tokens from .env); about three requests per sampled parcel, 4 in flight.
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import math
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from eval.capacity_coverage import CONDO_CLASSES, IMPLAUSIBLE_FAR_MULTIPLE, classify

FOOTPRINT_SPAN_SLACK = 1.1  # mirrors backend/retrieval/property/__init__.py::_FOOTPRINT_SPAN_SLACK
CONCURRENCY = 4
SOURCES = ("commercial_valuation", "energy_benchmark", "footprint")

_FAILS: contextvars.ContextVar[list[str]] = contextvars.ContextVar("fetch_failures")


# ---------------------------------------------------------------------------------------------------------
# Pure logic (unit-tested in eval/tests/test_capacity_fallbacks.py)
# ---------------------------------------------------------------------------------------------------------


def resolve_gfa(fallbacks: dict, land_sqft: float | None, allowed_far: float | None) -> dict:
    """Apply the Profile's merge rules (``_build_summary``) to a parcel with NO building area.

    Order is the Profile's: commercial valuation, energy benchmarking, footprint (condo unit area is the
    unit's, not a building's, and is not a candidate here).  Returns ``{"source", "sqft", "flags", "outcome"}``
    where outcome is ``resolved``, ``implausible`` (a value exists but implies a FAR over the guard) or
    ``unresolved``.  Flags name what was seen and refused: ``complex_total_only`` (multi-PIN member),
    ``footprint_spans_lots``, ``footprint_no_area`` (a footprint with stories/year but no area)."""
    flags: list[str] = []
    source, sqft = None, None
    commercial = fallbacks.get("commercial") or {}
    if commercial.get("bldg_sqft"):
        source, sqft = "commercial_valuation", commercial["bldg_sqft"]
    elif commercial.get("complex_bldg_sqft"):
        flags.append("complex_total_only")
    energy = fallbacks.get("energy") or {}
    if not sqft and energy.get("gross_floor_area"):
        source, sqft = "energy_benchmark", energy["gross_floor_area"]
    footprint = fallbacks.get("footprint") or {}
    if footprint:
        area = footprint.get("bldg_sqft")
        spans = bool(land_sqft and area and area > land_sqft * FOOTPRINT_SPAN_SLACK)
        if spans:
            flags.append("footprint_spans_lots")
        elif not area:
            flags.append("footprint_no_area")
        elif not sqft:
            source, sqft = "footprint", area
    if not sqft:
        return {"source": None, "sqft": None, "flags": flags, "outcome": "unresolved"}
    if land_sqft and allowed_far and sqft / land_sqft > IMPLAUSIBLE_FAR_MULTIPLE * allowed_far:
        return {"source": source, "sqft": sqft, "flags": flags + ["implausible_far"], "outcome": "implausible"}
    return {"source": source, "sqft": sqft, "flags": flags, "outcome": "resolved"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a share; (0, 0) for n = 0."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def draw_sample(
    unknown_gfa: dict[int, list[str]], condo: dict[int, list[str]], per_area: int, condo_per_area: int, seed: int
) -> dict[str, list[str]]:
    """A seeded sample of PINs per stratum, ``per_area`` / ``condo_per_area`` per community area (all of them
    when an area has fewer).  Candidate lists are sorted first so the draw depends only on the seed."""
    rng = random.Random(seed)
    out: dict[str, list[str]] = {"unknown_gfa": [], "condo_bldg": []}
    for stratum, cands, k in (("unknown_gfa", unknown_gfa, per_area), ("condo_bldg", condo, condo_per_area)):
        for ca in sorted(cands):
            pool = sorted(cands[ca])
            out[stratum].extend(pool if len(pool) <= k else rng.sample(pool, k))
    return out


def summarize(records: list[dict]) -> dict:
    """Rates per stratum, citywide and per community area.  ``fetch_error`` parcels are counted, never rated."""
    out: dict = {}
    for stratum in ("unknown_gfa", "condo_bldg"):
        recs = [r for r in records if r["stratum"] == stratum]
        usable = [r for r in recs if r["outcome"] != "fetch_error"]
        block = {"sampled": len(recs), "fetch_errors": len(recs) - len(usable), "citywide": _rates(usable), "by_community_area": {}}
        by_ca: dict[int, list[dict]] = defaultdict(list)
        for r in usable:
            by_ca[r["ca"]].append(r)
        for ca in sorted(by_ca):
            block["by_community_area"][str(ca)] = _rates(by_ca[ca])
        out[stratum] = block
    return out


def _rates(usable: list[dict]) -> dict:
    n = len(usable)
    c = Counter(r["outcome"] for r in usable)
    resolved = c.get("resolved", 0)
    lo, hi = wilson(resolved, n)
    return {
        "n": n,
        "resolved": resolved,
        "resolved_share": round(resolved / n, 4) if n else 0.0,
        "resolved_ci95": [lo, hi],
        "implausible": c.get("implausible", 0),
        "unresolved": c.get("unresolved", 0),
        "by_source": dict(Counter(r["source"] for r in usable if r["outcome"] == "resolved")),
        "flags": dict(Counter(f for r in usable for f in r["flags"])),
    }


# ---------------------------------------------------------------------------------------------------------
# Sampling from the index and fetching (network)
# ---------------------------------------------------------------------------------------------------------


def candidates(path: Path) -> tuple[dict[int, list[str]], dict[int, list[str]], dict[str, tuple]]:
    """Candidate base-parcel PINs per community area for both strata, plus the row facts the fetch needs."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    unknown: dict[int, list[str]] = defaultdict(list)
    condo: dict[int, list[str]] = defaultdict(list)
    facts: dict[str, tuple] = {}
    condo_pin10: set[str] = set()
    # A condo building usually has no base-PIN row in the index, only its unit PINs.  The building is sampled
    # from its first unit row (the units share the building's point and zone) under the synthesized base PIN
    # ("-0000"), which is what a map polygon is keyed by.  Planned-development buildings are left out: the
    # census classes them planned_development, not condo_unit.
    for pin, lat, lon, attrs_json, regions in con.execute(
        "select pin, lat, lon, attrs, regions from parcels where json_extract(attrs,'$.class') in (%s) order by pin"
        % ",".join("?" * len(CONDO_CLASSES)),
        tuple(CONDO_CLASSES),
    ):
        attrs = json.loads(attrs_json)
        ca = _ca(regions)
        base = pin[:13] + "-0000"
        if ca is None or base in facts or attrs.get("zoning_group") in (None, "planned_development"):
            continue
        condo_pin10.add(pin[:13])
        condo[ca].append(base)
        facts[base] = (lat, lon, None, attrs.get("density_band"), attrs.get("class"))
    for pin, lat, lon, attrs_json, regions in con.execute("select pin, lat, lon, attrs, regions from parcels where pin like '%-0000'"):
        attrs = json.loads(attrs_json)
        ca = _ca(regions)
        if ca is None or pin[:13] in condo_pin10 or classify(attrs) != "unknown_gfa":
            continue
        unknown[ca].append(pin)
        facts[pin] = (lat, lon, attrs.get("land_sqft"), attrs.get("density_band"), attrs.get("class"))
    return unknown, condo, facts


def _ca(regions: str) -> int | None:
    for r in json.loads(regions):
        if r.startswith("neighborhood:"):
            return int(r.split(":", 1)[1])
    return None


def _instrument(module) -> None:
    """Make a failed Socrata call visible: the Profile's fetchers log and return None, which would read as 'no record'."""
    original = module.socrata_get

    async def wrapped(*a, **kw):
        try:
            return await original(*a, **kw)
        except Exception as exc:  # noqa: BLE001
            _FAILS.get().append(f"{type(exc).__name__}")
            raise

    module.socrata_get = wrapped


async def _fetch_one(pin: str, facts: tuple, stratum: str, ca: int, sem: asyncio.Semaphore, client) -> dict:
    from backend.retrieval.property import building_facts as bf
    from backend.retrieval.property import energy
    from backend.retrieval.property.parcel_geometry import get_parcel_geometry_facts

    lat, lon, land, far, cls = facts
    digits = pin.replace("-", "")
    async with sem:
        _FAILS.set([])
        geom = await get_parcel_geometry_facts(digits)
        geojson = (geom or {}).get("parcel_geometry")
        commercial, en, fp = await asyncio.gather(
            bf.get_commercial_facts(digits, client=client),
            energy.get_energy_benchmark(lat, lon, client=client),
            bf.get_footprint_facts(lat, lon, parcel_geojson=geojson, client=client),
        )
        failed = list(_FAILS.get())
    base = {"pin": pin, "ca": ca, "stratum": stratum, "class": cls, "land_sqft": land, "allowed_far": far}
    if failed:
        return {**base, "outcome": "fetch_error", "source": None, "sqft": None, "flags": sorted(set(failed))}
    land_for_check = land or (geom or {}).get("land_sqft_geom")
    res = resolve_gfa({"commercial": commercial, "energy": en, "footprint": fp}, land_for_check, far)
    return {**base, **res}


async def run(index: Path, per_area: int, condo_per_area: int, seed: int, cache: Path | None) -> list[dict]:
    from backend.retrieval import socrata
    from backend.retrieval.property import building_facts as bf
    from backend.retrieval.property import energy, parcel_geometry

    unknown, condo, facts = candidates(index)
    sample = draw_sample(unknown, condo, per_area, condo_per_area, seed)
    done: dict[str, dict] = {}
    if cache and cache.exists():
        done = {r["pin"] + "|" + r["stratum"]: r for r in map(json.loads, cache.read_text().splitlines())}
    _instrument(bf)
    _instrument(energy)
    sem = asyncio.Semaphore(CONCURRENCY)
    client = socrata.get_shared_client()
    todo = [(p, s) for s, pins in sample.items() for p in pins if p + "|" + s not in done]
    ca_of = {p: ca for cands in (unknown, condo) for ca, pins in cands.items() for p in pins}
    print(f"sample {sum(map(len, sample.values()))} parcels, {len(todo)} to fetch", file=sys.stderr)
    out = list(done.values())
    try:
        for i in range(0, len(todo), 200):
            batch = await asyncio.gather(*[_fetch_one(p, facts[p], s, ca_of[p], sem, client) for p, s in todo[i : i + 200]])
            out.extend(batch)
            if cache:
                with cache.open("a") as fh:
                    fh.writelines(json.dumps(r) + "\n" for r in batch)
            print(f"  {min(i + 200, len(todo))}/{len(todo)}", file=sys.stderr)
    finally:
        await parcel_geometry.close()  # its aiosqlite thread would otherwise keep the process alive
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--per-area", type=int, default=25)
    ap.add_argument("--condo-per-area", type=int, default=10)
    ap.add_argument("--seed", type=int, default=28)
    ap.add_argument("--cache", type=Path, help="JSONL of fetched parcels; makes the run resumable")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    records = asyncio.run(run(args.index, args.per_area, args.condo_per_area, args.seed, args.cache))
    result = {"seed": args.seed, "per_area": args.per_area, "condo_per_area": args.condo_per_area, **summarize(records), "parcels": records}
    for stratum in ("unknown_gfa", "condo_bldg"):
        b = result[stratum]
        c = b["citywide"]
        print(f"{stratum}: sampled {b['sampled']} (fetch errors {b['fetch_errors']}); resolved {c['resolved']}/{c['n']} "
              f"= {c['resolved_share']:.1%} (95% CI {c['resolved_ci95'][0]:.1%}-{c['resolved_ci95'][1]:.1%}); "
              f"implausible {c['implausible']}; sources {c['by_source']}; flags {c['flags']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
