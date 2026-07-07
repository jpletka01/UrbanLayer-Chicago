"""Per-community-area benchmark aggregates for the Property Profile KPI band.

Computed from the Property Discovery index (the only citywide per-parcel AV/sqft
source we hold) in ONE full pass that builds all 77 areas at once, then cached
in-process for a day — the index itself only changes on the monthly refresh.
Computed on demand rather than at ``finalize_index`` so shipping this needs no
off-box index rebuild; if the index is absent (fresh dev box) every stat is None
and the UI simply renders no benchmark.

Honesty notes (2026-07-07 audit — the first cut of this file failed all three):
- The $/ft² benchmark is **market value** per land ft² (AV ÷ the parcel's class
  assessment level), never raw AV/ft². Raw AV mixes 10% residential with 25%
  commercial levels, which INVERTED the comparison for commercial subjects (a
  class-517 read "above the area median" while sitting at half the area's
  market $/ft²). Exempt parcels (no level) are excluded.
- Every median ships its own ``n``. The index's ``land_sqft`` is sparse (~4% of
  Uptown), so ``n_parcels`` alone badly overstated the sample behind the $/ft²
  median; the frontend suppresses the line under a floor.
- No area effective-tax-rate median (the index holds no bills) — that
  comparison is served by the deterministic class-norm constant on the
  frontend. Per-class medians are only emitted at n ≥ 20; below that a
  "median" is an anecdote.
"""

import asyncio
import json
import logging
import sqlite3
import time

from backend.config import get_settings
from backend.retrieval.property.assessment_level import assessment_level_for_class

log = logging.getLogger(__name__)

_TTL_S = 24 * 3600
# A failed scan (index mid-refresh, transient I/O) must not blank the benchmark
# for a whole day — retry soon.
_FAIL_TTL_S = 300
_MIN_CLASS_N = 20

_cache: dict[int, dict] | None = None
_cache_expires: float = 0.0
_lock = asyncio.Lock()


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def _scan_index(path: str) -> dict[int, dict]:
    """Single pass over the discovery index → stats for every community area."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        acc: dict[int, dict] = {}
        for attrs_json, regions_json in conn.execute("SELECT attrs, regions FROM parcels"):
            try:
                regions = json.loads(regions_json)
                ca = next(
                    (int(r.split(":", 1)[1]) for r in regions if r.startswith("neighborhood:")),
                    None,
                )
                if ca is None:
                    continue
                attrs = json.loads(attrs_json)
            except (ValueError, TypeError, IndexError):
                continue
            a = acc.setdefault(ca, {"n": 0, "av": [], "mv_psf": [], "by_use": {}})
            a["n"] += 1
            av = attrs.get("total_assessed_value")
            land = attrs.get("land_sqft")
            if isinstance(av, (int, float)) and av > 0:
                a["av"].append(float(av))
                level = assessment_level_for_class(attrs.get("class"))
                if level and isinstance(land, (int, float)) and land > 0:
                    psf = (float(av) / level) / float(land)
                    a["mv_psf"].append(psf)
                    use = attrs.get("land_use_class")
                    if isinstance(use, str) and use:
                        a["by_use"].setdefault(use, []).append(psf)

        out: dict[int, dict] = {}
        for ca, a in acc.items():
            out[ca] = {
                "community_area": ca,
                "n_parcels": a["n"],
                "median_assessed": _median(a["av"]),
                "n_assessed": len(a["av"]),
                "median_mv_per_land_sqft": _median(a["mv_psf"]),
                "n_mv_psf": len(a["mv_psf"]),
                "by_land_use": {
                    use: {"n": len(vals), "median_mv_per_land_sqft": _median(vals)}
                    for use, vals in a["by_use"].items()
                    if len(vals) >= _MIN_CLASS_N
                },
            }
        return out
    finally:
        conn.close()


async def get_area_stats(community_area: int) -> dict | None:
    """Benchmark aggregates for one community area, or None when unavailable."""
    global _cache, _cache_expires
    if _cache is None or time.monotonic() > _cache_expires:
        async with _lock:
            if _cache is None or time.monotonic() > _cache_expires:
                path = str(get_settings().discovery_index_path)
                try:
                    loop = asyncio.get_running_loop()
                    _cache = await loop.run_in_executor(None, _scan_index, path)
                    _cache_expires = time.monotonic() + _TTL_S
                    log.info("Area stats computed for %d community areas", len(_cache))
                except Exception as exc:
                    log.warning("Area stats scan failed (%s): %s", path, exc)
                    _cache = {}
                    _cache_expires = time.monotonic() + _FAIL_TTL_S
    return _cache.get(community_area)


def _reset_cache_for_tests() -> None:
    global _cache, _cache_expires
    _cache = None
    _cache_expires = 0.0
