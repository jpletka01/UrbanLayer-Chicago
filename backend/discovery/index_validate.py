"""Non-blocking validation harness for the prospecting index (PR-VAL).

Reports the `upside_score` / `value_percentile` distributions (a degeneracy guard — catches a
metric gone all-null or all-one-value) plus a DIRECTIONAL cross-check: do parcels with a recent
NEW-CONSTRUCTION permit — sites the market actually chose to develop — skew high on `upside_score`
in the index?

This is directional, not rigorous. It is confounded (vacant land both scores high AND attracts new
construction) and permit-vs-assessment timing is noisy, AND a parcel redeveloped long ago now shows
its built-out state (low upside). So treat the cross-check as a sanity signal + a tuning aid for the
v1 0.6/0.4 `upside_score` weighting — never a publish gate. Run it any time against a built index:

    python -m backend.discovery.index_validate
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import re
import statistics
from bisect import bisect_left
from typing import Iterable

import httpx

from backend.config import get_settings
from backend.discovery.parcel_index import default_index_path, read_index, read_meta
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_RECENT_PERMIT_DAYS = 730  # new-construction permits within ~2 years
_REDEV_PERMIT_TYPES = ("PERMIT - NEW CONSTRUCTION", "PERMIT - WRECKING/DEMOLITION")


# --- pure stats --------------------------------------------------------------


def _distribution(vals: list[float]) -> dict:
    """min / p25 / p50 / p75 / max / n for a list of numbers (empty → all None)."""
    xs = sorted(vals)
    if not xs:
        return {"n": 0, "min": None, "p25": None, "p50": None, "p75": None, "max": None}
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return {"n": len(xs), "min": xs[0], "p25": q(0.25), "p50": q(0.50), "p75": q(0.75), "max": xs[-1]}


def _percentile_rank(sorted_pop: list[float], v: float) -> float:
    """Percentile rank (0–100) of `v` within an ascending population."""
    if not sorted_pop:
        return 0.0
    return 100.0 * bisect_left(sorted_pop, v) / len(sorted_pop)


def _parcel_key(pin: str) -> str:
    """The 10-digit parcel id (area+sub+block+parcel) — the part shared by all unit-PINs in a
    parcel/building. Permits carry 10-digit PINs while the index has 14-digit unit-PINs, so the
    cross-check matches on this prefix (same idea as the condo address fallback)."""
    return "".join(ch for ch in str(pin) if ch.isdigit())[:10]


def _extract_parcel_keys(pin_list: str | None) -> list[str]:
    """Permit `pin_list` cell → 10-digit parcel keys.

    Split on separators between PINs (whitespace/comma/semicolon), strip intra-PIN dashes within
    each token, and take the 10-digit parcel id — so "13-36-301-006, 17083200160000" → two keys,
    not shattered on dashes nor wrongly left-padded.
    """
    if not pin_list:
        return []
    out: list[str] = []
    for tok in re.split(r"[\s,;]+", str(pin_list)):
        digits = "".join(ch for ch in tok if ch.isdigit())
        if len(digits) >= 10:
            out.append(digits[:10])
    return out


def cross_check(upside_by_pin: dict[str, float], redev_pins: Iterable[str]) -> dict:
    """Directional signal: median upside-percentile of redevelopment-permit parcels.

    50 ≈ no signal (redev parcels are average); >55 ≈ upside skews toward the parcels the
    market actually developed. Returns counts + the median percentile, or n=0 when no overlap.
    """
    pop = sorted(upside_by_pin.values())
    ranks = [
        _percentile_rank(pop, upside_by_pin[p]) for p in set(redev_pins) if p in upside_by_pin
    ]
    return {
        "matched": len(ranks),
        "median_upside_percentile": round(statistics.median(ranks), 1) if ranks else None,
        "signal": "elevated" if ranks and statistics.median(ranks) >= 55 else "weak/none",
    }


# --- permit fetch (network) --------------------------------------------------


async def _fetch_redev_pins(cas: list[int], *, client: httpx.AsyncClient | None = None) -> set[str]:
    settings = get_settings()
    since = (datetime.date.today() - datetime.timedelta(days=_RECENT_PERMIT_DAYS)).isoformat()
    types = ",".join(f"'{t}'" for t in _REDEV_PERMIT_TYPES)
    ca_list = ",".join(f"'{c}'" for c in cas)
    pins: set[str] = set()
    try:
        rows = await socrata_get(
            settings.dataset_permits,
            {"$select": "pin_list", "$where": f"permit_type in ({types}) "
             f"and community_area in ({ca_list}) and issue_date >= '{since}'", "$limit": 50000},
            client=client, base_url="https://data.cityofchicago.org/resource",
        )
    except Exception as exc:  # non-blocking: a permit-fetch failure just skips the cross-check
        log.warning("index_validate: permit fetch failed (%s); skipping cross-check", exc)
        return pins
    for r in rows:
        pins.update(_extract_parcel_keys(r.get("pin_list")))
    return pins


# --- report ------------------------------------------------------------------


def _upside_by_parcel(parcels) -> dict[str, float]:
    """Max upside_score per 10-digit parcel key (so a permit's parcel matches its index units)."""
    out: dict[str, float] = {}
    for p in parcels:
        u = p.get("upside_score")
        if u is None:
            continue
        key = _parcel_key(p.pin)
        if key not in out or u > out[key]:
            out[key] = u
    return out


async def validate(path=None, *, client: httpx.AsyncClient | None = None) -> dict:
    path = path or default_index_path()
    data_version, parcels = read_index(path)
    meta = read_meta(path)
    if data_version is None:
        return {"error": "no index built", "path": str(path)}

    upside = [p.get("upside_score") for p in parcels if p.get("upside_score") is not None]
    vpct = [p.get("value_percentile") for p in parcels if p.get("value_percentile") is not None]
    n = len(parcels)
    report = {
        "dataVersion": data_version,
        "parcels": n,
        "upside": {**_distribution(upside), "coverage_pct": round(100 * len(upside) / n, 1) if n else 0,
                   "degenerate": len(set(upside)) <= 1},
        "value_percentile": {**_distribution(vpct),
                             "coverage_pct": round(100 * len(vpct) / n, 1) if n else 0},
    }
    cas = meta.community_areas if meta else []
    redev = await _fetch_redev_pins(cas, client=client) if cas else set()
    report["redev_cross_check"] = cross_check(_upside_by_parcel(parcels), redev)
    report["redev_permit_pins"] = len(redev)
    return report


def _print(report: dict) -> None:
    if "error" in report:
        print(f"NO INDEX: {report['error']} ({report['path']})")
        return
    u, v, x = report["upside"], report["value_percentile"], report["redev_cross_check"]
    print(f"index {report['dataVersion']} — {report['parcels']} parcels")
    print(f"  upside_score      : {u['coverage_pct']}% pop · p25={u['p25']} p50={u['p50']} "
          f"p75={u['p75']} max={u['max']}{'  ⚠ DEGENERATE' if u['degenerate'] else ''}")
    print(f"  value_percentile  : {v['coverage_pct']}% pop · p25={v['p25']} p50={v['p50']} p75={v['p75']}")
    print(f"  redev cross-check : {report['redev_permit_pins']} recent new-construction/demo PINs, "
          f"{x['matched']} in index; median upside pctile = {x['median_upside_percentile']} "
          f"→ {x['signal']}  (directional; 50≈no signal)")


async def _amain(args) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        report = await validate(client=client)
    _print(report)


def _parse_args(argv=None):
    return argparse.ArgumentParser(description="Validate the Property Discovery index (non-blocking).").parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_amain(_parse_args()))
