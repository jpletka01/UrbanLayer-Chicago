"""Lot-information coverage benchmark.

Measures field-level completeness of the parcel facts customers pay for
(building/land sqft, assessed value, tax bill + rate, zoning, year built, ...)
across a FIXED panel of representative Chicago addresses, exercised through the
real ``/api/scorecard`` surface — the same call the Scorecard page makes.

This is a different axis from ``eval/source_coverage.py`` (which checks whether
each *data source* reaches the chat synthesis for a handful of queries): here
the unit is a parcel and the question is "of N real addresses, what fraction is
missing each lot fact — and is the absence legitimate?"

Every field check resolves to one of:
  PRESENT             the fact is there
  MISSING_PERSISTENT  should exist, absent on the first pass AND on a
                      sequential retry  <- the true data gap
  MISSING_TRANSIENT   absent on the first pass, present on retry — a
                      retrieval-reliability gap, not a data gap (silent
                      external-API failure the customer still experienced)
  EXPECTED_ABSENT     legitimately absent (vacant land has no building sqft;
                      exempt parcels have no tax bill) — not a gap
  FETCH_ERROR         the whole scorecard call failed for this address

Two coverage numbers fall out: FIRST-HIT coverage (what a customer sees on one
page load) and PERSISTENT coverage (what the data can support at best).

The panel (``eval/lot_panel.json``) is sampled once from the authoritative Cook
County Address Points dataset (78yw-iddh), stratified across the 7 Chicago
township PIN prefixes with seeded-random sub-prefix scatter (same portal-safe
technique as eval/r7_audit.py — deep $offset pagination times out), then
COMMITTED so successive runs measure the same parcels over time.

Usage:
  PYTHONPATH=. python -m eval.lot_coverage --build-panel            # regenerate panel (n=100)
  PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001
  PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001 --limit 10
  PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001 \
      --out eval/lot_coverage_report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import httpx

PANEL_FILE = Path(__file__).resolve().parent / "lot_panel.json"
DEFAULT_JSON_OUT = Path(__file__).resolve().parent / "lot_coverage_results.json"
DEFAULT_MD_OUT = Path(__file__).resolve().parent / "lot_coverage_report.md"

ADDRESS_POINTS_URL = "https://datacatalog.cookcountyil.gov/resource/78yw-iddh.json"

# Chicago-proper township PIN prefixes (Rogers Park, Jefferson, Lake View,
# West/North/South Chicago, Hyde Park, Lake) — same buckets r7_audit uses.
PIN_PREFIXES = ["10", "13", "14", "16", "17", "20", "25"]

_DIR_LETTER = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}

PANEL_SEED = 20260702  # deterministic panel regeneration


# --------------------------------------------------------------------------
# Field classification
# --------------------------------------------------------------------------

class FieldStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"  # first-pass raw status, refined by the verify pass
    MISSING_PERSISTENT = "MISSING_PERSISTENT"
    MISSING_TRANSIENT = "MISSING_TRANSIENT"
    EXPECTED_ABSENT = "EXPECTED_ABSENT"
    FETCH_ERROR = "FETCH_ERROR"


def _prop(resp: dict) -> dict:
    return (resp.get("context") or {}).get("property") or {}


# CCAO major-class buckets. First character of the class code, except the
# lettered exempt/railroad codes. Drives both the expected-absent rules and
# the by-class gap breakdown.
_CLASS_GROUPS = {
    "0": "exempt",
    "1": "vacant",
    "2": "residential",
    "3": "multifamily",
    "4": "nonprofit",
    "5": "commercial",
    "6": "industrial",
    "7": "incentive",
    "8": "incentive",
    "9": "multifamily",
}


def class_group(resp: dict) -> str:
    cls = str(_prop(resp).get("bldg_class") or "").strip().upper()
    if not cls:
        return "unknown"
    if cls.startswith(("EX", "RR")):
        return "exempt"
    return _CLASS_GROUPS.get(cls[0], "other")


def _is_vacant(resp: dict) -> str | None:
    if class_group(resp) == "vacant":
        return "vacant land (class 1xx) has no building"
    return None


def _is_exempt(resp: dict) -> str | None:
    if _prop(resp).get("tax_exempt") or class_group(resp) == "exempt":
        return "tax-exempt parcel carries no bill/value by design"
    return None


def _no_building(resp: dict) -> str | None:
    return _is_vacant(resp)


def _positive_num(v: Any) -> bool:
    try:
        return v is not None and float(v) > 0
    except (TypeError, ValueError):
        return False


@dataclass
class FieldSpec:
    name: str
    tier: str  # "identity" | "critical" | "secondary"
    present: Callable[[dict, dict], bool]          # (resp, panel_row) -> bool
    expected_absent: Callable[[dict], str | None] = lambda r: None
    note: str = ""


FIELD_SPECS: list[FieldSpec] = [
    # ---- identity: can we even name the parcel? --------------------------
    FieldSpec(
        "pin_resolved", "identity",
        lambda r, row: bool(r.get("resolved_pin")),
        note="resolved_pin surfaced (not withheld as unverified-nearest)",
    ),
    FieldSpec(
        "pin_authoritative", "identity",
        lambda r, row: r.get("resolved_confidence") == "authoritative",
        note="address→PIN path resolved at the authoritative tier",
    ),
    FieldSpec(
        "pin_matches_truth", "identity",
        lambda r, row: bool(r.get("resolved_pin"))
        and str(r["resolved_pin"]) == str(row.get("truth_pin", "")),
        note="resolved PIN equals the Address Points truth PIN (informational; condo units can legitimately differ)",
    ),
    FieldSpec(
        "property_record", "identity",
        lambda r, row: bool(_prop(r).get("pin14")),
        note="the property domain returned any parcel record at all",
    ),
    # ---- critical lot facts (the paid core) ------------------------------
    FieldSpec(
        "land_sqft", "critical",
        lambda r, row: _positive_num(_prop(r).get("land_sqft")),
        note="every parcel has land area; absence is always a gap",
    ),
    FieldSpec(
        "bldg_sqft", "critical",
        lambda r, row: _positive_num(_prop(r).get("bldg_sqft")),
        expected_absent=_no_building,
    ),
    FieldSpec(
        "bldg_class", "critical",
        lambda r, row: bool(_prop(r).get("bldg_class")),
    ),
    FieldSpec(
        "year_built", "critical",
        lambda r, row: _positive_num(_prop(r).get("year_built")),
        expected_absent=_no_building,
    ),
    FieldSpec(
        "assessed_value", "critical",
        lambda r, row: _positive_num(_prop(r).get("total_assessed_value")),
        expected_absent=_is_exempt,
    ),
    FieldSpec(
        "assessment_history", "critical",
        lambda r, row: len(_prop(r).get("assessment_history") or []) >= 1,
        expected_absent=_is_exempt,
    ),
    FieldSpec(
        "tax_bill", "critical",
        lambda r, row: _prop(r).get("estimated_annual_tax") is not None,
        expected_absent=_is_exempt,
        note="ptaxsim estimated_annual_tax (scorecard has no fallback-rate path)",
    ),
    FieldSpec(
        "tax_rate", "critical",
        lambda r, row: bool(_prop(r).get("tax_code"))
        and len(_prop(r).get("tax_breakdown") or []) > 0,
        expected_absent=_is_exempt,
        note="tax_code + agency-level rate breakdown",
    ),
    FieldSpec(
        "zoning_class", "critical",
        lambda r, row: bool(((r.get("context") or {}).get("parcel_zoning") or {}).get("zone_class")),
    ),
    FieldSpec(
        "zoning_far", "critical",
        lambda r, row: bool((r.get("zone_definition") or {}).get("far")),
        expected_absent=lambda r: (
            "PD/PMD standards are set per-ordinance, and the UI states so "
            "explicitly (since 2026-07-03) instead of showing a blank"
            if str(((r.get("context") or {}).get("parcel_zoning") or {})
                   .get("zone_class") or "").upper().startswith(("PD", "PMD"))
            else None
        ),
        note="Title-17 bulk FAR from zone_definition; PD/PMD = expected-absent now that the card renders 'Set by PD ordinance' + ordinance number",
    ),
    # ---- secondary facts --------------------------------------------------
    FieldSpec(
        "stories", "secondary",
        lambda r, row: _positive_num(_prop(r).get("stories")),
        expected_absent=_no_building,
    ),
    FieldSpec(
        "units", "secondary",
        lambda r, row: _positive_num(_prop(r).get("units")),
        expected_absent=_no_building,
    ),
    FieldSpec(
        "sales_history", "secondary",
        lambda r, row: len(_prop(r).get("sales_history") or []) >= 1,
        note="no expected-absent rule: a parcel with no recorded sale counts as missing; interpret via the by-class table",
    ),
    FieldSpec(
        "comparables", "secondary",
        lambda r, row: bool((r.get("comparables") or {}).get("sales_volume")),
    ),
]


@dataclass
class AddressResult:
    address: str
    truth_pin: str
    township: str
    http_status: int | None = None
    elapsed_ms: int = 0
    error: str = ""
    resolved_pin: str | None = None
    resolved_confidence: str = ""
    nearest_parcel_unverified: bool = False
    bldg_class: str | None = None
    class_group: str = "unknown"
    community_area: str | None = None
    partial_failures: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)  # name -> final FieldStatus
    first_pass: dict[str, str] = field(default_factory=dict)  # raw pass-1 statuses
    retried: bool = False


# --------------------------------------------------------------------------
# Panel building (Address Points, stratified + scattered, deterministic)
# --------------------------------------------------------------------------

def _reconstruct(row: dict) -> str | None:
    """78yw-iddh row -> user-format address, or None if unparseable parts."""
    number = row.get("add_number")
    predir = row.get("st_predir")
    name = row.get("st_name")
    suffix = row.get("lst_type") or row.get("st_postyp")
    if not (number and predir and name):
        return None
    letter = _DIR_LETTER.get(str(predir).upper(), str(predir))
    parts = [str(number), letter, str(name).title()]
    if suffix:
        parts.append(str(suffix).title())
    return " ".join(parts)


def _norm_pin(raw: str) -> str:
    return str(raw or "").replace("-", "").zfill(14)


async def build_panel(n: int, seed: int) -> list[dict]:
    """Stratified sample: n addresses spread over the 7 township prefixes,
    scattered within each via random 4-digit PIN sub-prefixes (avoids both the
    deep-$offset timeout and the geographic clustering of `$order=pin $limit=k`)."""
    rng = random.Random(seed)
    per_town = -(-n // len(PIN_PREFIXES))  # ceil
    panel: list[dict] = []
    seen_addresses: set[str] = set()

    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
        for prefix in PIN_PREFIXES:
            collected: list[dict] = []
            tried: set[str] = set()
            while len(collected) < per_town and len(tried) < 60:
                sub = f"{prefix}{rng.randint(0, 9)}{rng.randint(0, 9)}"
                if sub in tried:
                    continue
                tried.add(sub)
                try:
                    r = await client.get(ADDRESS_POINTS_URL, params={
                        "$select": "add_number,st_predir,st_name,st_postyp,lst_type,pin",
                        "$where": (
                            "inc_muni='Chicago' AND st_predir IS NOT NULL "
                            f"AND starts_with(pin, '{sub}')"
                        ),
                        "$order": "pin",
                        "$limit": 3,
                    })
                    r.raise_for_status()
                    rows = r.json()
                except Exception as exc:  # noqa: BLE001
                    print(f"  (bucket {sub} failed: {type(exc).__name__})")
                    continue
                for row in rows:
                    addr = _reconstruct(row)
                    if not addr or addr in seen_addresses:
                        continue
                    seen_addresses.add(addr)
                    collected.append({
                        "address": addr,
                        "truth_pin": _norm_pin(row.get("pin")),
                        "township": prefix,
                    })
                    if len(collected) >= per_town:
                        break
            print(f"  township {prefix}: {len(collected)} addresses "
                  f"({len(tried)} buckets probed)")
            panel.extend(collected)

    rng.shuffle(panel)
    return panel[:n]


# --------------------------------------------------------------------------
# Benchmark runner
# --------------------------------------------------------------------------

def _classify_fields(resp: dict, row: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in FIELD_SPECS:
        if spec.present(resp, row):
            out[spec.name] = FieldStatus.PRESENT.value
        else:
            reason = spec.expected_absent(resp)
            out[spec.name] = (
                FieldStatus.EXPECTED_ABSENT.value if reason else FieldStatus.MISSING.value
            )
    return out


async def _fetch_scorecard(
    row: dict, base_url: str, http: httpx.AsyncClient,
) -> tuple[dict | None, int, int | None, str]:
    """Returns (response_json | None, elapsed_ms, http_status, error)."""
    started = time.monotonic()
    status: int | None = None
    try:
        r = await http.get(
            f"{base_url}/api/scorecard",
            params={"address": row["address"]},
            timeout=httpx.Timeout(120.0),
        )
        status = r.status_code
        r.raise_for_status()
        resp = r.json()
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.monotonic() - started) * 1000)
        return None, elapsed, status, f"{type(exc).__name__}: {exc}"
    return resp, int((time.monotonic() - started) * 1000), status, ""


async def _run_address(
    row: dict, base_url: str, http: httpx.AsyncClient, sem: asyncio.Semaphore,
) -> AddressResult:
    res = AddressResult(
        address=row["address"], truth_pin=row.get("truth_pin", ""),
        township=row.get("township", ""),
    )
    async with sem:
        resp, res.elapsed_ms, res.http_status, res.error = await _fetch_scorecard(
            row, base_url, http)
    if resp is None:
        res.fields = {spec.name: FieldStatus.FETCH_ERROR.value for spec in FIELD_SPECS}
        res.first_pass = dict(res.fields)
        return res

    res.resolved_pin = resp.get("resolved_pin")
    res.resolved_confidence = resp.get("resolved_confidence") or ""
    res.nearest_parcel_unverified = bool(resp.get("nearest_parcel_unverified"))
    res.community_area = resp.get("community_area_name")
    res.partial_failures = list(resp.get("partial_failures") or [])
    prop = _prop(resp)
    res.bldg_class = prop.get("bldg_class")
    res.class_group = class_group(resp)
    res.data_gaps = list(prop.get("data_gaps") or [])

    res.first_pass = _classify_fields(resp, row)
    # Provisional: every raw MISSING is treated as persistent until the verify
    # pass upgrades/downgrades it.
    res.fields = {
        k: (FieldStatus.MISSING_PERSISTENT.value if v == FieldStatus.MISSING.value else v)
        for k, v in res.first_pass.items()
    }
    return res


async def _verify_pass(
    results: list[AddressResult], panel: list[dict], base_url: str,
    http: httpx.AsyncClient,
) -> None:
    """Sequentially re-fetch every address that had a raw MISSING and split
    each miss into MISSING_TRANSIENT (present on retry) vs MISSING_PERSISTENT.

    Sequential on purpose: the first pass runs concurrently (like real traffic),
    so a silent external-API failure under load looks identical to a data gap.
    A calm second look separates the two. Failed external calls are not cached
    by the retrieval layer (only definitive not-founds are), so the retry is a
    genuine re-query.
    """
    by_address = {row["address"]: row for row in panel}
    to_retry = [
        r for r in results
        if not r.error and FieldStatus.MISSING.value in r.first_pass.values()
    ]
    print(f"\nVerify pass: re-checking {len(to_retry)} addresses with raw misses...")
    for i, res in enumerate(to_retry, 1):
        resp, _, _, err = await _fetch_scorecard(by_address[res.address], base_url, http)
        if resp is None:
            print(f"  [{i}/{len(to_retry)}] {res.address:<36} retry failed ({err}) — "
                  f"misses stay persistent")
            res.retried = True
            continue
        retry_fields = _classify_fields(resp, by_address[res.address])
        res.retried = True
        flipped = []
        for name, first in res.first_pass.items():
            if first != FieldStatus.MISSING.value:
                continue
            if retry_fields.get(name) == FieldStatus.PRESENT.value:
                res.fields[name] = FieldStatus.MISSING_TRANSIENT.value
                flipped.append(name)
        label = f"transient: {', '.join(flipped)}" if flipped else "all persistent"
        print(f"  [{i}/{len(to_retry)}] {res.address:<36} {label}", flush=True)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _field_stats(results: list[AddressResult]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for spec in FIELD_SPECS:
        s = {"present": 0, "missing_persistent": 0, "missing_transient": 0,
             "expected_absent": 0, "fetch_error": 0}
        for r in results:
            s[r.fields[spec.name].lower()] += 1
        stats[spec.name] = s
    return stats


def _first_hit_pct(s: dict[str, int]) -> float:
    """What a customer sees on one page load: present / should-exist."""
    base = s["present"] + s["missing_persistent"] + s["missing_transient"]
    return 100.0 * s["present"] / base if base else 100.0


def _persistent_pct(s: dict[str, int]) -> float:
    """Best the data can support: (present + transient) / should-exist."""
    base = s["present"] + s["missing_persistent"] + s["missing_transient"]
    return 100.0 * (s["present"] + s["missing_transient"]) / base if base else 100.0


def _by_group_matrix(results: list[AddressResult]) -> dict[str, dict[str, dict[str, int]]]:
    """field -> class_group -> {present, missing} using PERSISTENT semantics
    (transient misses count as present — this matrix is about data, not flakiness)."""
    matrix: dict[str, dict[str, dict[str, int]]] = {}
    for spec in FIELD_SPECS:
        per_group: dict[str, dict[str, int]] = {}
        for r in results:
            st = r.fields[spec.name]
            if st in (FieldStatus.PRESENT.value, FieldStatus.MISSING_TRANSIENT.value):
                bucket = "present"
            elif st == FieldStatus.MISSING_PERSISTENT.value:
                bucket = "missing"
            else:
                continue
            g = per_group.setdefault(r.class_group, {"present": 0, "missing": 0})
            g[bucket] += 1
        matrix[spec.name] = per_group
    return matrix


def _print_summary(results: list[AddressResult]) -> None:
    ok = [r for r in results if not r.error]
    stats = _field_stats(results)

    print(f"\n{'=' * 84}")
    print("Lot Information Coverage")
    print(f"{'=' * 84}")
    print(f"Addresses tested: {len(results)}   fetch errors: {len(results) - len(ok)}")
    if ok:
        lat = sorted(r.elapsed_ms for r in ok)
        print(f"Latency ms: p50={lat[len(lat) // 2]}  p90={lat[int(len(lat) * 0.9)]}  max={lat[-1]}")
        auth = sum(1 for r in ok if r.resolved_confidence == "authoritative")
        unv = sum(1 for r in ok if r.nearest_parcel_unverified)
        print(f"Resolution: authoritative {auth}/{len(ok)}, nearest-unverified {unv}/{len(ok)}")

    groups: dict[str, int] = {}
    for r in ok:
        groups[r.class_group] = groups.get(r.class_group, 0) + 1
    print("Class mix: " + ", ".join(f"{k}={v}" for k, v in sorted(groups.items(), key=lambda kv: -kv[1])))

    print(f"\n{'Field':<22} {'Tier':<10} {'Present':>7} {'MissPer':>7} {'MissTra':>7} "
          f"{'ExpAbs':>6} {'FirstHit':>9} {'Persist':>8}")
    print("-" * 84)
    for spec in FIELD_SPECS:
        s = stats[spec.name]
        print(f"{spec.name:<22} {spec.tier:<10} {s['present']:>7} {s['missing_persistent']:>7} "
              f"{s['missing_transient']:>7} {s['expected_absent']:>6} "
              f"{_first_hit_pct(s):>8.1f}% {_persistent_pct(s):>7.1f}%")


def _print_worst(results: list[AddressResult], k: int = 12) -> None:
    critical = [s.name for s in FIELD_SPECS if s.tier == "critical"]

    def gaps(r: AddressResult) -> int:
        return sum(1 for f in critical
                   if r.fields.get(f) == FieldStatus.MISSING_PERSISTENT.value)

    worst = sorted((r for r in results if not r.error), key=gaps, reverse=True)[:k]
    print("\nWorst addresses (persistent critical gaps):")
    for r in worst:
        missing = [f for f in critical
                   if r.fields.get(f) == FieldStatus.MISSING_PERSISTENT.value]
        if not missing:
            break
        print(f"  {r.address:<34} class={r.bldg_class or '—':<5} ({r.class_group:<11}) "
              f"missing: {', '.join(missing)}")


def _write_json(results: list[AddressResult], panel_meta: dict, path: Path) -> None:
    stats = _field_stats(results)
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "panel": panel_meta,
        "addresses_tested": len(results),
        "fetch_errors": sum(1 for r in results if r.error),
        "per_field": {
            name: {
                **s,
                "first_hit_coverage_pct": round(_first_hit_pct(s), 2),
                "persistent_coverage_pct": round(_persistent_pct(s), 2),
            }
            for name, s in stats.items()
        },
        "by_class_group": _by_group_matrix(results),
        "per_address": [
            {
                "address": r.address,
                "truth_pin": r.truth_pin,
                "township": r.township,
                "http_status": r.http_status,
                "elapsed_ms": r.elapsed_ms,
                "error": r.error,
                "resolved_pin": r.resolved_pin,
                "resolved_confidence": r.resolved_confidence,
                "nearest_parcel_unverified": r.nearest_parcel_unverified,
                "bldg_class": r.bldg_class,
                "class_group": r.class_group,
                "community_area": r.community_area,
                "partial_failures": r.partial_failures,
                "data_gaps": r.data_gaps,
                "retried": r.retried,
                "fields": r.fields,
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(out, indent=2))
    print(f"\nJSON results -> {path}")


def _write_markdown(results: list[AddressResult], path: Path) -> None:
    stats = _field_stats(results)
    matrix = _by_group_matrix(results)
    ok = [r for r in results if not r.error]
    groups = sorted({r.class_group for r in ok})

    lines = [
        "# Lot Information Coverage Report",
        "",
        f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')} · "
        f"{len(results)} panel addresses · {len(results) - len(ok)} fetch errors_",
        "",
        "**First-hit coverage** = what one page load shows; **persistent coverage**",
        "= best the data can support (transient retrieval failures excluded). Parcels",
        "where the field is legitimately absent (vacant land → no building sqft,",
        "exempt → no tax) are excluded from both bases.",
        "",
        "## Field Coverage",
        "",
        "| Field | Tier | Present | Missing (persistent) | Missing (transient) | Expected absent | First-hit | Persistent |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for spec in FIELD_SPECS:
        s = stats[spec.name]
        lines.append(
            f"| `{spec.name}` | {spec.tier} | {s['present']} | {s['missing_persistent']} | "
            f"{s['missing_transient']} | {s['expected_absent']} | "
            f"{_first_hit_pct(s):.1f}% | {_persistent_pct(s):.1f}% |"
        )

    lines += ["", "## Persistent Missing Rate by Property Class", "",
              "| Field | " + " | ".join(groups) + " |",
              "|---|" + "---:|" * len(groups)]
    for spec in FIELD_SPECS:
        row = [f"| `{spec.name}`"]
        for g in groups:
            cell = matrix[spec.name].get(g)
            if not cell or (cell["present"] + cell["missing"]) == 0:
                row.append("—")
            else:
                n = cell["present"] + cell["missing"]
                row.append(f"{100.0 * cell['missing'] / n:.0f}% of {n}")
        lines.append(" | ".join(row) + " |")

    critical = [s.name for s in FIELD_SPECS if s.tier == "critical"]
    lines += ["", "## Addresses With Persistent Critical Gaps", "",
              "| Address | Class | Group | Missing critical fields |", "|---|---|---|---|"]
    for r in sorted(ok, key=lambda r: -sum(
            1 for f in critical
            if r.fields.get(f) == FieldStatus.MISSING_PERSISTENT.value)):
        missing = [f for f in critical
                   if r.fields.get(f) == FieldStatus.MISSING_PERSISTENT.value]
        if not missing:
            continue
        lines.append(f"| {r.address} | {r.bldg_class or '—'} | {r.class_group} | "
                     f"{', '.join(f'`{m}`' for m in missing)} |")

    path.write_text("\n".join(lines) + "\n")
    print(f"Markdown report -> {path}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

async def main_async(args: argparse.Namespace) -> int:
    if args.build_panel:
        print(f"Sampling {args.n} addresses from Cook County Address Points "
              f"(seed={PANEL_SEED})...")
        panel = await build_panel(args.n, PANEL_SEED)
        PANEL_FILE.write_text(json.dumps({
            "built": datetime.now(timezone.utc).isoformat(),
            "seed": PANEL_SEED,
            "source": "78yw-iddh (Cook County Address Points)",
            "strata": PIN_PREFIXES,
            "addresses": panel,
        }, indent=2))
        print(f"Panel of {len(panel)} addresses -> {PANEL_FILE}")
        return 0

    if not args.full:
        print("Either --build-panel or --full URL is required.", file=sys.stderr)
        return 2

    data = json.loads(PANEL_FILE.read_text())
    panel: list[dict] = data["addresses"]
    if args.limit:
        panel = panel[: args.limit]

    print(f"Running {len(panel)} addresses against {args.full} "
          f"(concurrency={args.concurrency})...")

    sem = asyncio.Semaphore(args.concurrency)
    done_count = 0

    async with httpx.AsyncClient() as http:
        async def _tracked(row: dict) -> AddressResult:
            nonlocal done_count
            r = await _run_address(row, args.full, http, sem)
            done_count += 1
            marker = "ERR" if r.error else f"{r.elapsed_ms}ms"
            print(f"  [{done_count}/{len(panel)}] {row['address']:<36} {marker}", flush=True)
            return r

        results = await asyncio.gather(*(_tracked(row) for row in panel))
        results = list(results)
        if not args.no_verify:
            await _verify_pass(results, panel, args.full, http)

    _print_summary(results)
    _print_worst(results)

    panel_meta = {"file": str(PANEL_FILE), "built": data.get("built"), "seed": data.get("seed")}
    _write_json(results, panel_meta, args.json_out or DEFAULT_JSON_OUT)
    _write_markdown(results, args.out or DEFAULT_MD_OUT)

    fetch_errors = sum(1 for r in results if r.error)
    return 1 if fetch_errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", metavar="URL",
                        help="Base URL of a running backend (e.g. http://localhost:8001)")
    parser.add_argument("--build-panel", action="store_true",
                        help="Regenerate eval/lot_panel.json from Address Points")
    parser.add_argument("--n", type=int, default=100, help="panel size for --build-panel")
    parser.add_argument("--limit", type=int, help="run only the first N panel addresses")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the sequential retry pass (all misses count persistent)")
    parser.add_argument("--out", type=Path, help=f"markdown report path (default: {DEFAULT_MD_OUT})")
    parser.add_argument("--json-out", type=Path, help=f"JSON output path (default: {DEFAULT_JSON_OUT})")
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
