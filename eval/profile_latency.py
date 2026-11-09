"""Property Profile latency per retrieval task, cold and warm (front-end rewrite Phase 2, decision Item 81).

Runs `/api/scorecard`'s handler in-process with the per-task timing collector (`backend/timing.py`) open, on
the four page-budget parcels (`frontend/e2e/profile-budget.spec.ts`) plus fresh parcels, and records every
span of every run. No model is called anywhere on this path (the Profile is deterministic); the run does hit
the same public City/County/federal APIs a real visit does, sequentially, one Profile at a time.

  cold  = every in-process TTL cache emptied first: a parcel nobody has opened since the server started
          (its community-area caches empty too, so this is the slow end of a first visit). Shared HTTP
          connections and the static artifacts loaded at startup stay warm, as on a running server.
  warm  = the same parcel again straight after: what a second visitor, or a reload, gets.
  The process's very first Profile also pays one-time loads (artifact reads, index memoization); it is
  recorded as round 0 and left out of the cold percentiles (`--rounds` counts the rounds after it).

Usage (the repo's .env is read for the Socrata app token and Walk Score key, as the server does):
  PYTHONPATH=. python -m eval.profile_latency --label local-2026-11-07 --rounds 5
  PYTHONPATH=. python -m eval.profile_latency --label quick --rounds 1 --parcels milwaukee,pin1
Results: eval/results/2026-11-profile-latency/<label>.{json,md}.

`--parts` (Phase 4, decision Item 89) times the new Profile as the page loads it: `/api/scorecard/first` and the
Overview part together, then every late part the Overview names, together; per visit it records the first
screen, the Overview, each part, the whole Profile ("complete"), and the sources past the late deadline. The
Overview's p50/p95 is reported for exactly resolved parcels and for approximate ones apart (Item 81, point 3).
  PYTHONPATH=. python -m eval.profile_latency --parts --label parts-local-2026-11-08 --rounds 5
  PYTHONPATH=. python -m eval.profile_latency --parts --base https://urbanlayerchicago.com --rounds 1 \
      --label parts-prod-2026-11-09 --parcels <fresh keys>     (production: the owner's go, one visit at a time)

`--base URL` instead times whole requests against a running server (total wall time only, plus the
`_timings` breakdown when that server runs with PROFILE_TIMINGS=true). Caches there can't be emptied from
outside, so "cold" means the first request for a parcel in this run; use parcels nobody has opened since the
server started. Production only with the owner's go.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parent / "results" / "2026-11-profile-latency"

# (key, query, why it is in the panel)
PARCELS: list[tuple[str, dict[str, str], str]] = [
    ("twoflat", {"address": "2541 N Spaulding Ave"}, "budget: RS-3 two-flat (block-face test runs)"),
    ("milwaukee", {"address": "1601 N Milwaukee Ave"}, "budget: B3 corner commercial, pending filings"),
    ("downtown", {"address": "233 S Wacker Dr"}, "budget: downtown tower (DX, many PINs)"),
    ("pin1", {"pin": "14-28-319-102-0000"}, "budget: PIN-keyed entry"),
    ("fresh_south", {"address": "7600 S Halsted St"}, "fresh: South Side commercial strip"),
    ("fresh_west", {"address": "3300 W Armitage Ave"}, "fresh: Logan Square mixed street"),
    ("fresh_north", {"address": "5600 N Clark St"}, "fresh: Andersonville commercial"),
]

# Fresh parcels for Phase 4 (not in Items 81-87's runs), to be added to the panel with --parts.
PHASE4_FRESH: list[tuple[str, dict[str, str], str]] = [
    ("p4_uptown", {"address": "4800 N Broadway"}, "fresh (Phase 4): Uptown commercial"),
    ("p4_westtown", {"address": "2200 W Chicago Ave"}, "fresh (Phase 4): West Town corridor"),
    ("p4_woodlawn", {"address": "6300 S Cottage Grove Ave"}, "fresh (Phase 4): Woodlawn corridor"),
    ("p4_bridgeport", {"address": "3500 S Halsted St"}, "fresh (Phase 4): Bridgeport"),
]

# Fresh addresses for a production pass (never opened by these runs), one visit at a time (Item 87's method).
PROD_FRESH: list[tuple[str, dict[str, str], str]] = [
    ("prod_lakeview", {"address": "1100 W Belmont Ave"}, "fresh (prod): Lakeview corridor"),
    ("prod_humboldt", {"address": "4300 W North Ave"}, "fresh (prod): Humboldt Park corridor"),
    ("prod_auburn", {"address": "8000 S Ashland Ave"}, "fresh (prod): Auburn Gresham corridor"),
    ("prod_littlevillage", {"address": "2800 W 26th St"}, "fresh (prod): Little Village corridor"),
]

# The Profile's top-level tasks, in the order Item 81's table lists them. Everything else is a sub-span.
TOP_LEVEL = [
    "resolution", "property", "regulatory", "zoning", "incentives", "neighborhood", "aro_housing",
    "crime", "crime_yoy", "violations", "address_311", "assemble", "comparables.sales", "comparables.far",
    "block_face", "identity.address_round_trip", "upcoming_zoning", "candidates.wait", "provenance",
    "upcoming_zoning.text_impacts", "serialize",
]


# Phase 4 what-ifs, read from each run's span end times (both include resolution). Upper bounds: the spans ran
# inside the full request, beside everything else.
#   first_content = the lot on the map with its district: resolution, the zoning point, the PTAXSIM outline.
#   overview      = what the Overview reads (answer sentence + verdict + one tile per tab): those, plus the
#                   property record it shows (characteristics, assessments, sales, tax), the overlays the verdict
#                   and the 606 rule read, Walk Score, and the RS-3 block-face test.
SUBSETS = {
    "first_content": ["resolution", "zoning", "property.parcel_by_pin", "property.parcel_by_point",
                      "property.geometry"],
    "overview": ["resolution", "zoning", "property.parcel_by_pin", "property.parcel_by_point",
                 "property.geometry", "property.characteristics", "property.assessments", "property.sales",
                 "property.tax", "property.building_facts", "regulatory.overlays", "neighborhood.walkscore",
                 "block_face"],
    # The same minus the two steps that start late for reasons a split can remove: the building-facts
    # fallback (waits today for the whole first property batch, parcel flags included) and the RS-3
    # block-face test (runs after the fetch). A lower bound for a Phase 4 Overview part.
    "overview_unblocked": ["resolution", "zoning", "property.parcel_by_pin", "property.parcel_by_point",
                           "property.geometry", "property.characteristics", "property.assessments",
                           "property.sales", "property.tax", "regulatory.overlays", "neighborhood.walkscore"],
}


def subset_end(run: dict, names: list[str]) -> float | None:
    ends = [run["spans"][n]["end_ms"] for n in names if n in run["spans"]]
    return max(ends) if ends else None


def pct(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (no interpolation: with n=35 the p95 is the 34th value)."""
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def _clear_caches() -> int:
    from backend.retrieval.cache import TTLCache

    n = 0
    for c in TTLCache._instances:
        n += len(c._store)
        c._store.clear()
    return n


def _critical(run: dict) -> str | None:
    """The fetch-phase task that finished last: what the whole response waited on."""
    spans = run["spans"]
    fetch_tasks = [k for k in ("property", "regulatory", "zoning", "incentives", "neighborhood", "aro_housing",
                               "crime", "crime_yoy", "violations", "address_311") if k in spans]
    if not fetch_tasks:
        return None
    return max(fetch_tasks, key=lambda k: spans[k]["end_ms"])


async def _preload() -> None:
    """The server's startup preloads, minus the chat's embedding model (`main._preload_datasets` also loads
    it; the Profile never embeds anything)."""
    from backend.discovery import parcel_source
    import httpx
    from backend.retrieval.incentives import enterprise_zones, tif
    from backend.retrieval.neighborhood import demographics, transit, wards

    t = time.perf_counter()
    parcel_source.ensure_loaded()
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        done = await asyncio.gather(
            tif.preload(client=client), enterprise_zones.preload(client=client), transit.preload(),
            demographics.preload(client=client), wards.preload(client=client), return_exceptions=True,
        )
    for name, res in zip(("tif", "ez", "transit", "demographics", "wards"), done):
        if isinstance(res, Exception):
            print(f"preload {name} failed: {res!r}", file=sys.stderr)
    print(f"startup preload {time.perf_counter() - t:.1f}s", file=sys.stderr)


async def _in_process(parcels: list[tuple[str, dict, str]], rounds: int) -> list[dict]:
    from backend import main
    from backend import timing

    await _preload()

    runs: list[dict] = []
    for rnd in range(rounds + 1):
        for key, query, _why in parcels:
            for mode in ("cold", "warm"):
                if mode == "cold":
                    _clear_caches()
                with timing.collect() as c:
                    ok, err = True, None
                    try:
                        payload = await main._scorecard_payload(
                            query.get("address"), None, None, query.get("pin"),
                        )
                    except Exception as exc:  # a 422/502 is a result too
                        ok, err, payload = False, repr(exc)[:200], None
                    total = c.now_ms()
                run = {
                    "parcel": key, "round": rnd, "mode": mode, "ok": ok, "error": err,
                    "total_ms": round(total, 1), "spans": c.summary(),
                    "failed_sources": [f.get("key") for f in (payload or {}).get("failed_sources") or []],
                    "resolution": (payload or {}).get("resolution", {}).get("method") if payload else None,
                    "bytes": len(json.dumps(payload, default=str)) if payload else 0,
                }
                run["critical"] = _critical(run)
                runs.append(run)
                print(f"r{rnd} {key:12s} {mode:4s} {total / 1000:6.2f}s critical={run['critical']}"
                      f" failed={run['failed_sources']}", file=sys.stderr)
    return runs


async def _isolate(parcel: tuple[str, dict, str], repeats: int) -> list[dict]:
    """Each slow lookup ALONE, cold, ``repeats`` times: is a task slow by itself, or only inside a crowded
    Profile? Also a one-row query to each portal as the network baseline."""
    from backend import main
    from backend.config import get_settings
    from backend.retrieval import crime, three11
    from backend.retrieval.geo import community_area_by_point, community_area_name
    from backend.retrieval.incentives.grant_programs import grant_programs_by_community_area
    from backend.retrieval.neighborhood.divvy import find_nearest_divvy
    from backend.retrieval.neighborhood.traffic import get_traffic_context
    from backend.retrieval.property.appeals import get_appeals
    from backend.retrieval.property.assessor_permits import get_assessor_permits
    from backend.retrieval.property.energy import get_energy_benchmark
    from backend.retrieval.property.parcel_flags import get_parcel_flags
    from backend.retrieval.regulatory.aro_housing import aro_housing_by_community_area
    from backend.retrieval.socrata import socrata_get

    settings = get_settings()
    _clear_caches()
    rl = await main._resolve_location(parcel[1].get("address"), None, None, parcel[1].get("pin"))
    lat, lon, pin = rl.lat, rl.lon, rl.pin
    ca = community_area_by_point(lat, lon)
    jobs = {
        "baseline.city_portal_1_row": lambda: socrata_get(settings.dataset_crime, {"$limit": 1}),
        "baseline.county_portal_1_row": lambda: socrata_get(
            settings.dataset_ccao_parcels, {"$limit": 1}, base_url=settings.cook_county_socrata_base),
        "crime": lambda: crime.crime_by_community_area(ca),
        "crime_yoy": lambda: crime.crime_yoy_by_community_area(ca),
        "aro_housing": lambda: aro_housing_by_community_area(ca),
        "address_311": lambda: three11.address_311_complaints(lat, lon),
        "incentives.grants": lambda: grant_programs_by_community_area(community_area_name(ca)),
        "neighborhood.divvy": lambda: find_nearest_divvy(lat, lon),
        "neighborhood.traffic": lambda: get_traffic_context(lat, lon),
        "property.flags": lambda: get_parcel_flags(pin, lat, lon),
        "property.appeals": lambda: get_appeals(pin, lat, lon),
        "property.assessor_permits": lambda: get_assessor_permits(pin),
        "property.building_facts.energy": lambda: get_energy_benchmark(lat, lon),
    }
    out = []
    for name, job in jobs.items():
        times = []
        for _ in range(repeats):
            _clear_caches()
            t = time.perf_counter()
            try:
                await job()
                ok = True
            except Exception:
                ok = False
            times.append(round((time.perf_counter() - t) * 1000, 1))
        out.append({"task": name, "ms": times, "ok": ok})
        print(f"{name:32s} " + " ".join(f"{x / 1000:6.2f}s" for x in times), file=sys.stderr)
    return out


async def _over_http(base: str, parcels: list[tuple[str, dict, str]], rounds: int) -> list[dict]:
    import httpx

    runs: list[dict] = []
    async with httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(120.0)) as client:
        for rnd in range(rounds):
            for key, query, _why in parcels:
                for mode in ("cold", "warm") if rnd == 0 else ("warm",):
                    t = time.perf_counter()
                    r = await client.get("/api/scorecard", params=query)
                    total = (time.perf_counter() - t) * 1000
                    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    tm = body.get("_timings") or {}
                    run = {"parcel": key, "round": rnd + 1, "mode": mode, "ok": r.status_code == 200,
                           "error": None if r.status_code == 200 else str(r.status_code),
                           "total_ms": round(total, 1), "server_ms": tm.get("total_ms"),
                           "spans": tm.get("spans", {}), "bytes": len(r.content),
                           "failed_sources": [f.get("key") for f in body.get("failed_sources") or []]}
                    run["critical"] = _critical(run) if run["spans"] else None
                    runs.append(run)
                    print(f"r{rnd + 1} {key:12s} {mode:4s} {total / 1000:6.2f}s", file=sys.stderr)
    return runs


def summarize(runs: list[dict]) -> dict:
    measured = [r for r in runs if r["round"] >= 1 and r["ok"]]
    out: dict[str, Any] = {"n_runs": len(measured), "tasks": {}, "total": {}, "critical": {}, "per_parcel": {}}
    for mode in ("cold", "warm"):
        rs = [r for r in measured if r["mode"] == mode]
        tot = [r["total_ms"] for r in rs]
        out["total"][mode] = {"n": len(tot), "p50": pct(tot, 50), "p95": pct(tot, 95), "max": max(tot, default=None)}
        crit: dict[str, int] = {}
        for r in rs:
            if r.get("critical"):
                crit[r["critical"]] = crit.get(r["critical"], 0) + 1
        out["critical"][mode] = dict(sorted(crit.items(), key=lambda kv: -kv[1]))
    names = sorted({k for r in measured for k in r["spans"]})
    for name in names:
        row: dict[str, Any] = {}
        for mode in ("cold", "warm"):
            vals = [r["spans"][name]["ms"] for r in measured if r["mode"] == mode and name in r["spans"]]
            waits = [r["spans"][name].get("wait_ms") or 0.0 for r in measured
                     if r["mode"] == mode and name in r["spans"]]
            row[mode] = {"n": len(vals), "p50": pct(vals, 50), "p95": pct(vals, 95), "max": max(vals, default=None),
                         "wait_p95": pct(waits, 95) if any(waits) else None}
        row["failed_runs"] = sum(1 for r in measured if name in r["spans"] and not r["spans"][name]["ok"])
        out["tasks"][name] = row
    for key in sorted({r["parcel"] for r in measured}):
        out["per_parcel"][key] = {
            mode: statistics.median([r["total_ms"] for r in measured if r["parcel"] == key and r["mode"] == mode])
            for mode in ("cold", "warm") if any(r["parcel"] == key and r["mode"] == mode for r in measured)
        }
    out["subsets"] = {}
    for sub, names in SUBSETS.items():
        out["subsets"][sub] = {}
        for mode in ("cold", "warm"):
            vals = [v for r in measured if r["mode"] == mode and (v := subset_end(r, names)) is not None]
            out["subsets"][sub][mode] = {"n": len(vals), "p50": pct(vals, 50), "p95": pct(vals, 95),
                                         "max": max(vals, default=None)}
    first = [r for r in runs if r["round"] == 0 and r["mode"] == "cold"]
    if first:
        out["process_first_ms"] = first[0]["total_ms"]
    return out


def _s(ms: float | None) -> str:
    return "–" if ms is None else (f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms")


def render_md(meta: dict, summary: dict, parcels: list[tuple[str, dict, str]]) -> str:
    lines = [f"# Profile latency: {meta['label']}", "",
             f"- When: {meta['when']} · host: {meta['host']} · git {meta['git']}",
             f"- Mode: {meta['mode']} · rounds: {meta['rounds']} · measured runs: {summary['n_runs']} "
             f"(n per mode = parcels x rounds)", ""]
    lines += ["| Parcel | Query | Why | cold p50 | warm p50 |", "|---|---|---|---|---|"]
    for key, query, why in parcels:
        pp = summary["per_parcel"].get(key, {})
        lines.append(f"| {key} | {next(iter(query.values()))} | {why} | {_s(pp.get('cold'))} | {_s(pp.get('warm'))} |")
    t = summary["total"]
    lines += ["", "**Whole response:** "
              f"cold p50 {_s(t['cold']['p50'])} / p95 {_s(t['cold']['p95'])} (n={t['cold']['n']}); "
              f"warm p50 {_s(t['warm']['p50'])} / p95 {_s(t['warm']['p95'])} (n={t['warm']['n']})."]
    if "process_first_ms" in summary:
        lines.append(f"First Profile after process start (round 0, not in the percentiles): "
                     f"{_s(summary['process_first_ms'])}.")
    for sub, row in summary.get("subsets", {}).items():
        lines.append(f"If only `{sub}` were awaited ({', '.join(SUBSETS[sub])}): cold p50 {_s(row['cold']['p50'])}"
                     f" / p95 {_s(row['cold']['p95'])}; warm p50 {_s(row['warm']['p50'])} / p95 {_s(row['warm']['p95'])}.")
    lines += ["", "**Critical path** (the fetch task that finished last): "
              f"cold {summary['critical']['cold']}; warm {summary['critical']['warm']}.", ""]
    lines += ["| Task | cold p50 | cold p95 | cold max | warm p50 | warm p95 | queue wait p95 (cold) | failed |",
              "|---|---|---|---|---|---|---|---|"]
    order = [n for n in TOP_LEVEL if n in summary["tasks"]] + sorted(
        n for n in summary["tasks"] if n not in TOP_LEVEL and n not in ("fetch",))
    for name in order:
        r = summary["tasks"][name]
        c, w = r["cold"], r["warm"]
        indent = "" if name in TOP_LEVEL else "&nbsp;&nbsp;"
        lines.append(f"| {indent}{name} | {_s(c['p50'])} | {_s(c['p95'])} | {_s(c['max'])} | {_s(w['p50'])} | "
                     f"{_s(w['p95'])} | {_s(c['wait_p95'])} | {r['failed_runs'] or ''} |")
    return "\n".join(lines) + "\n"


# ── Phase 4: the Profile in parts (Item 89) ────────────────────────────────────────────────────────────

async def _timed(coro) -> tuple[float, Any]:
    """(milliseconds, result) — or the exception as the result: a failed request is a result too."""
    t = time.perf_counter()
    try:
        result = await coro
    except Exception as exc:  # noqa: BLE001
        result = exc
    return (time.perf_counter() - t) * 1000, result


def _visit_record(key: str, rnd: int, mode: str, t_first, t_ov, late: dict, complete_ms: float, ov,
                  *, over_http: bool = False) -> dict:
    ok = not isinstance(ov, Exception) and isinstance(ov, dict)
    rl_conf = None
    if ok and not over_http:  # a server's lookup is signed with its own key; only in-process can read it
        from backend import profile_parts
        rl_conf = profile_parts.read_lookup(ov["lookup"])["rl"][4]
    return {
        "parcel": key, "round": rnd, "mode": mode, "ok": ok, "error": None if ok else repr(ov)[:200],
        "first_ms": round(t_first, 1), "overview_ms": round(t_ov, 1), "complete_ms": round(complete_ms, 1),
        "exact": rl_conf == "authoritative",
        "parts": {n: round(ms, 1) for n, (ms, _r) in late.items()},
        "part_end_ms": {n: round(t_ov + ms, 1) for n, (ms, _r) in late.items()},
        "timed_out": {n: r.get("timed_out", []) for n, (_ms, r) in late.items() if isinstance(r, dict)},
        "failed_parts": [n for n, (_ms, r) in late.items() if not isinstance(r, dict)],
        "failed_sources": [f.get("key") for f in ((ov or {}).get("profile") or {}).get("failed_sources") or []] if ok else [],
        # the Overview's own per-task spans (only when the server runs with PROFILE_TIMINGS=true)
        "overview_spans": ((ov.get("_timings") or {}).get("spans") if ok else None) or {},
    }


async def _parts_main(parcels, rounds: int) -> list[dict]:
    await _preload()
    return await _parts_in_process(parcels, rounds)


async def _parts_in_process(parcels, rounds: int) -> list[dict]:
    from backend import main, profile_parts

    runs: list[dict] = []
    for rnd in range(rounds + 1):
        for key, query, _why in parcels:
            for mode in ("cold", "warm"):
                if mode == "cold":
                    _clear_caches()
                addr, pin = query.get("address"), query.get("pin")
                t0 = time.perf_counter()
                (t_first, _first), (t_ov, ov) = await asyncio.gather(
                    _timed(main.scorecard_first(address=addr, pin=pin)),
                    _timed(profile_parts.overview(addr, None, None, pin)),
                )
                late: dict = {}
                if isinstance(ov, dict):
                    names = ov["parts_pending"]
                    got = await asyncio.gather(*(_timed(profile_parts.part(n, ov["lookup"], None)) for n in names))
                    late = dict(zip(names, got))
                run = _visit_record(key, rnd, mode, t_first, t_ov, late, (time.perf_counter() - t0) * 1000, ov)
                runs.append(run)
                print(f"r{rnd} {key:13s} {mode:4s} first {t_first / 1000:5.2f}s overview {t_ov / 1000:5.2f}s "
                      f"complete {run['complete_ms'] / 1000:5.2f}s exact={run['exact']} timed_out="
                      f"{ {k: v for k, v in run['timed_out'].items() if v} }", file=sys.stderr)
    return runs


async def _parts_over_http(base: str, parcels, rounds: int) -> list[dict]:
    import httpx

    runs: list[dict] = []
    async with httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(120.0)) as client:
        async def get(path, params):
            r = await client.get(path, params=params)
            if r.status_code != 200:
                raise RuntimeError(f"{path} {r.status_code}")
            return r.json()

        for rnd in range(rounds):
            for key, query, _why in parcels:
                for mode in ("cold", "warm"):
                    t0 = time.perf_counter()
                    (t_first, _f), (t_ov, ov) = await asyncio.gather(
                        _timed(get("/api/scorecard/first", query)), _timed(get("/api/profile/overview", query)),
                    )
                    late: dict = {}
                    if isinstance(ov, dict):
                        names = ov["parts_pending"]
                        got = await asyncio.gather(*(
                            _timed(get(f"/api/profile/part/{n}", {"lookup": ov["lookup"]})) for n in names))
                        late = dict(zip(names, got))
                    run = _visit_record(key, rnd + 1, mode, t_first, t_ov, late,
                                        (time.perf_counter() - t0) * 1000, ov, over_http=True)
                    if isinstance(ov, dict):
                        # the HTTP client can't read the signing key; exact = the resolution's own record
                        run["exact"] = (ov["profile"].get("resolution") or {}).get("method") in ("address_points", "pin", "coordinates", "assessor_addresses")
                    runs.append(run)
                    print(f"r{rnd + 1} {key:13s} {mode:4s} first {t_first / 1000:5.2f}s overview {t_ov / 1000:5.2f}s "
                          f"complete {run['complete_ms'] / 1000:5.2f}s", file=sys.stderr)
    return runs


def summarize_parts(runs: list[dict]) -> dict:
    measured = [r for r in runs if r["round"] >= 1 and r["ok"]]
    out: dict[str, Any] = {"n_runs": len(measured), "rows": {}, "timed_out": {}, "failed_parts": {}}

    def row(vals):
        return {"n": len(vals), "p50": pct(vals, 50), "p95": pct(vals, 95), "max": max(vals, default=None)}

    for mode in ("cold", "warm"):
        rs = [r for r in measured if r["mode"] == mode]
        rows = {
            "first screen": row([r["first_ms"] for r in rs]),
            "Overview, exact parcels": row([r["overview_ms"] for r in rs if r["exact"]]),
            "Overview, approximate parcels": row([r["overview_ms"] for r in rs if not r["exact"]]),
            "whole Profile (every part)": row([r["complete_ms"] for r in rs]),
        }
        for name in sorted({n for r in rs for n in r["parts"]}):
            rows[f"part {name} (own time)"] = row([r["parts"][name] for r in rs if name in r["parts"]])
            rows[f"part {name} (from visit start)"] = row([r["part_end_ms"][name] for r in rs if name in r["parts"]])
        out["rows"][mode] = rows
        to: dict[str, int] = {}
        for r in rs:
            for srcs in r["timed_out"].values():
                for s_ in srcs:
                    to[s_] = to.get(s_, 0) + 1
        out["timed_out"][mode] = {"visits": len(rs), "by_source": dict(sorted(to.items(), key=lambda kv: -kv[1]))}
        fp: dict[str, int] = {}
        for r in rs:
            for n in r["failed_parts"]:
                fp[n] = fp.get(n, 0) + 1
        out["failed_parts"][mode] = fp
    first = [r for r in runs if r["round"] == 0 and r["mode"] == "cold"]
    if first:
        out["process_first"] = {"overview_ms": first[0]["overview_ms"], "complete_ms": first[0]["complete_ms"]}
    return out


def render_parts_md(meta: dict, summary: dict, parcels) -> str:
    lines = [f"# Profile in parts: {meta['label']}", "",
             f"- When: {meta['when']} · host: {meta['host']} · git {meta['git']}",
             f"- Mode: {meta['mode']} · rounds: {meta['rounds']} · measured visits: {summary['n_runs']}",
             f"- Parcels: {', '.join(k for k, _q, _w in parcels)}", ""]
    for mode in ("cold", "warm"):
        lines += [f"## {mode}", "", "| | n | p50 | p95 | max |", "|---|---|---|---|---|"]
        for name, r in summary["rows"][mode].items():
            lines.append(f"| {name} | {r['n']} | {_s(r['p50'])} | {_s(r['p95'])} | {_s(r['max'])} |")
        to = summary["timed_out"][mode]
        lines += ["", f"Sources past the late deadline: {to['by_source'] or 'none'} (of {to['visits']} visits). "
                  f"Failed parts: {summary['failed_parts'][mode] or 'none'}.", ""]
    if "process_first" in summary:
        pf = summary["process_first"]
        lines.append(f"First visit after process start (round 0, not in the percentiles): Overview "
                     f"{_s(pf['overview_ms'])}, whole Profile {_s(pf['complete_ms'])}.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--parcels", help="comma-separated keys (default: all)")
    ap.add_argument("--base", help="time a running server over HTTP instead of in-process")
    ap.add_argument("--from-json", action="store_true",
                    help="re-summarize results/<label>.json without running anything")
    ap.add_argument("--parts", action="store_true",
                    help="time the Profile in parts (first screen, Overview, each late part; Item 89)")
    ap.add_argument("--isolate", action="store_true",
                    help="run each slow lookup alone, cold, --rounds times, on the first parcel")
    args = ap.parse_args()

    parcels = PARCELS + PHASE4_FRESH if args.parts else PARCELS
    if args.parcels:
        want = set(args.parcels.split(","))
        parcels = [p for p in PARCELS + PHASE4_FRESH + PROD_FRESH if p[0] in want]

    if args.parts:
        import logging
        logging.basicConfig(level=logging.WARNING)
        if args.base:
            runs = asyncio.run(_parts_over_http(args.base.rstrip("/"), parcels, args.rounds))
        else:
            runs = asyncio.run(_parts_main(parcels, args.rounds))
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        meta = {"label": args.label, "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "host": f"{platform.system()} {platform.machine()}, py{platform.python_version()}",
                "git": git, "mode": f"parts over http {args.base}" if args.base else "parts in-process",
                "rounds": args.rounds}
        summary = summarize_parts(runs)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / f"{args.label}.json").write_text(
            json.dumps({"meta": meta, "summary": summary, "runs": runs}, separators=(",", ":"), default=str))
        md = render_parts_md(meta, summary, parcels)
        (RESULTS_DIR / f"{args.label}.md").write_text(md)
        print(md)
        return

    if args.from_json:
        saved = json.loads((RESULTS_DIR / f"{args.label}.json").read_text())
        summary = summarize(saved["runs"])
        saved["summary"] = summary
        (RESULTS_DIR / f"{args.label}.json").write_text(json.dumps(saved, separators=(",", ":"), default=str))
        md = render_md(saved["meta"], summary, parcels)
        (RESULTS_DIR / f"{args.label}.md").write_text(md)
        print(md)
        return

    if args.isolate:
        import logging
        logging.basicConfig(level=logging.WARNING)
        rows = asyncio.run(_isolate(parcels[0], args.rounds))
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        lines = [f"# Lookups run alone, cold: {args.label}", "",
                 f"Parcel {parcels[0][0]} · {args.rounds} runs each · "
                 f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
                 "| Task | min | median | max | every run |", "|---|---|---|---|---|"]
        for r in rows:
            ms = r["ms"]
            lines.append(f"| {r['task']} | {_s(min(ms))} | {_s(statistics.median(ms))} | {_s(max(ms))} | "
                         + ", ".join(_s(x) for x in ms) + " |")
        (RESULTS_DIR / f"{args.label}.json").write_text(json.dumps(rows, indent=1))
        (RESULTS_DIR / f"{args.label}.md").write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        return

    if args.base:
        runs = asyncio.run(_over_http(args.base.rstrip("/"), parcels, args.rounds))
    else:
        import logging
        logging.basicConfig(level=logging.WARNING)
        runs = asyncio.run(_in_process(parcels, args.rounds))

    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"label": args.label, "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "host": f"{platform.system()} {platform.machine()}, py{platform.python_version()}",
            "git": git, "mode": f"http {args.base}" if args.base else "in-process", "rounds": args.rounds}
    summary = summarize(runs)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"meta": meta, "summary": summary, "runs": runs}
    (RESULTS_DIR / f"{args.label}.json").write_text(json.dumps(out, separators=(",", ":"), default=str))
    md = render_md(meta, summary, parcels)
    (RESULTS_DIR / f"{args.label}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
