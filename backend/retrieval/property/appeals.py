"""Assessment appeal history — this parcel and its immediate area.

Two stages, two datasets (both Cook County Socrata):
- Assessor appeals ``y282-6ig3``: pin, year, mailed vs certified values,
  ``change`` ("change"/"no change").
- Board of Review decisions ``7pny-nedm``: pin, tax_year, assessor vs BOR
  values, ``result`` ("Decrease"/"No Change"/"Increase"), plus a queryable
  ``centroid_geom`` — which powers the nearby-appeals aggregate ("N appeals
  within a block, median reduction X%"), a direct-dollars fact for the
  Scorecard and the $25 report.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import statistics

import httpx

from backend.config import get_settings
from backend.models import AppealRecord, AppealsSummary
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="appeals")

DATASET_ASSESSOR_APPEALS = "y282-6ig3"
DATASET_BOR_DECISIONS = "7pny-nedm"

NEARBY_RADIUS_M = 250
NEARBY_YEARS = 3
NEARBY_ROW_CAP = 500


def _f(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _i(val) -> int | None:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _reduction_pct(before: float | None, after: float | None) -> float | None:
    if before and after is not None and before > 0 and after < before:
        return round((before - after) / before * 100, 1)
    return None


async def get_appeals(
    pin14: str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> AppealsSummary | None:
    """Appeal history for the parcel + nearby BOR outcome stats, or None when
    nothing was found (no appeals is a legitimate state, not a data gap)."""
    pin_clean = pin14.replace("-", "").zfill(14)
    key = f"appeals:{pin_clean}:{round(lat or 0, 5)}:{round(lon or 0, 5)}"
    cached = _cache.get(key)
    if cached is not None:
        return cached or None  # cached falsy sentinel = known-empty

    settings = get_settings()
    kw = dict(
        client=client,
        base_url=settings.cook_county_socrata_base,
        app_token=settings.cook_county_socrata_token or None,
    )

    coros = [
        socrata_get(DATASET_ASSESSOR_APPEALS, {
            "pin": pin_clean,
            "$select": "year,mailed_tot,certified_tot,change,appeal_type",
            "$order": "year DESC",
            "$limit": 10,
        }, **kw),
        socrata_get(DATASET_BOR_DECISIONS, {
            "pin": pin_clean,
            "$select": "tax_year,assessor_totalvalue,bor_totalvalue,result,appealtypedescription",
            "$order": "tax_year DESC",
            "$limit": 10,
        }, **kw),
    ]
    has_point = lat is not None and lon is not None
    if has_point:
        min_year = datetime.date.today().year - NEARBY_YEARS
        coros.append(socrata_get(DATASET_BOR_DECISIONS, {
            "$where": (
                f"within_circle(centroid_geom, {lat}, {lon}, {NEARBY_RADIUS_M}) "
                f"AND tax_year >= '{min_year}'"
            ),
            "$select": "pin,tax_year,assessor_totalvalue,bor_totalvalue,result",
            "$limit": NEARBY_ROW_CAP,
        }, **kw))

    done = await asyncio.gather(*coros, return_exceptions=True)
    assessor_rows = done[0] if not isinstance(done[0], Exception) else None
    bor_rows = done[1] if not isinstance(done[1], Exception) else None
    nearby_rows = (done[2] if has_point and not isinstance(done[2], Exception) else None)
    for label, r in (("assessor", done[0]), ("bor", done[1])):
        if isinstance(r, Exception):
            log.warning("Appeals %s lookup failed for %s: %s", label, pin_clean, r)
    if has_point and isinstance(done[2], Exception):
        log.warning("Nearby appeals lookup failed at (%s, %s): %s", lat, lon, done[2])

    records: list[AppealRecord] = []
    for row in assessor_rows or []:
        before, after = _f(row.get("mailed_tot")), _f(row.get("certified_tot"))
        records.append(AppealRecord(
            year=_i(row.get("year")),
            stage="assessor",
            before_total=before,
            after_total=after,
            result=row.get("change"),
            reduction_pct=_reduction_pct(before, after),
            appeal_type=row.get("appeal_type"),
        ))
    for row in bor_rows or []:
        before, after = _f(row.get("assessor_totalvalue")), _f(row.get("bor_totalvalue"))
        records.append(AppealRecord(
            year=_i(row.get("tax_year")),
            stage="board_of_review",
            before_total=before,
            after_total=after,
            result=row.get("result"),
            reduction_pct=_reduction_pct(before, after),
            appeal_type=row.get("appealtypedescription"),
        ))
    records.sort(key=lambda r: (r.year or 0), reverse=True)

    nearby_count = 0
    nearby_reduced = 0
    nearby_median = None
    nearby_years: list[int] = []
    nearby_capped = bool(nearby_rows) and len(nearby_rows) >= NEARBY_ROW_CAP
    if nearby_rows:
        reductions: list[float] = []
        years: set[int] = set()
        for row in nearby_rows:
            # Exclude the subject parcel — "nearby" means the neighbors.
            if str(row.get("pin", "")).replace("-", "").zfill(14) == pin_clean:
                continue
            nearby_count += 1
            yr = _i(row.get("tax_year"))
            if yr:
                years.add(yr)
            pct = _reduction_pct(_f(row.get("assessor_totalvalue")), _f(row.get("bor_totalvalue")))
            if pct is not None:
                nearby_reduced += 1
                reductions.append(pct)
        if reductions:
            nearby_median = round(statistics.median(reductions), 1)
        nearby_years = sorted(years)

    if not records and nearby_count == 0:
        _cache.set(key, False)  # known-empty sentinel
        return None

    summary = AppealsSummary(
        records=records,
        nearby_window_years=nearby_years,
        nearby_appeal_count=nearby_count,
        nearby_reduced_count=nearby_reduced,
        nearby_median_reduction_pct=nearby_median,
        nearby_capped=nearby_capped,
    )
    _cache.set(key, summary)
    return summary
