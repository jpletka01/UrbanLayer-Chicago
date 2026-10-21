"""Community area demographics from the Chicago Data Portal's ACS dataset.

t68z-cikk ("ACS 5 Year Data by Community Area") publishes population, 5 household-
income brackets, age/sex and race counts for one ACS vintage, with no margins of
error. It has no rent, home value, tenure, education, vacancy, poverty or
unemployment column, so this module reports only what it holds: population and a
median household income interpolated from the brackets (a weak estimate; see
``_TOP_BRACKET_ASSUMED_CEILING``).

kn9c-c2s2 (poverty/unemployment) is no longer read: its figures are 2008–2012 and
it was last updated in 2014. Poverty and unemployment come from the census tract
(``census_tract.py``, current ACS) until community-area figures are aggregated
from tracts with their margins of error.
"""

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.models import DemographicsSummary
from backend.retrieval.geo import COMMUNITY_AREAS
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache: dict[int, dict] | None = None
_lock = asyncio.Lock()

_NAME_TO_CA: dict[str, int] = {
    name.upper(): num for num, name in COMMUNITY_AREAS.items()
}

# The top ACS bracket is open-ended ("$125,000 and over"); linear interpolation
# needs an upper bound, so we assume $200k. In CAs where most households sit in
# the top bracket the estimated median saturates toward this cap — i.e. the
# estimate is biased LOW for the wealthiest areas. Known limitation (see
# known-issues: demographics medians are estimates, not published values).
_TOP_BRACKET_ASSUMED_CEILING = 200_000

_INCOME_BRACKETS: list[tuple[str, float, float]] = [
    ("under_25_000", 0, 25_000),
    ("_25_000_to_49_999", 25_000, 50_000),
    ("_50_000_to_74_999", 50_000, 75_000),
    ("_75_000_to_125_000", 75_000, 125_000),
    ("_125_000", 125_000, _TOP_BRACKET_ASSUMED_CEILING),
]


async def _load_all(*, client: httpx.AsyncClient | None = None) -> dict[int, dict]:
    global _cache
    async with _lock:
        if _cache is not None:
            return _cache
        settings = get_settings()

        try:
            acs_rows = await socrata_get(settings.dataset_demographics, {"$limit": 100}, client=client)
        except Exception as exc:
            log.warning("Failed to load ACS demographics: %s", exc)
            return {}
        if not acs_rows:
            return {}

        result: dict[int, dict] = {}
        for row in acs_rows:
            ca_raw = row.get("community_area") or row.get("community_area_number")
            ca = _safe_int(ca_raw)
            if ca is None and isinstance(ca_raw, str):
                ca = _NAME_TO_CA.get(ca_raw.upper())
            if ca is not None:
                result[ca] = row

        _cache = result
        return _cache


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _estimate_median_income(row: dict) -> int | None:
    """Estimate median household income from bracket distribution."""
    brackets = []
    for field, lo, hi in _INCOME_BRACKETS:
        count = _safe_float(row.get(field))
        if count is not None:
            brackets.append((lo, hi, count))
    if not brackets:
        return None
    total = sum(c for _, _, c in brackets)
    if total <= 0:
        return None
    target = total / 2.0
    cumulative = 0.0
    for lo, hi, count in brackets:
        cumulative += count
        if cumulative >= target:
            overshoot = cumulative - target
            frac = (count - overshoot) / count if count > 0 else 0.5
            return int(lo + frac * (hi - lo))
    return None


def _acs_period(acs_year: object) -> str | None:
    """'2023' → '2019–2023': the 5-year window a 5-year ACS vintage covers."""
    year = _safe_int(acs_year)
    return f"{year - 4}–{year}" if year else None


def _build_demographics(row: dict, community_area: int) -> DemographicsSummary:
    ca_name = (
        row.get("community_area_name")
        or row.get("name")
        or COMMUNITY_AREAS.get(community_area)
    )
    return DemographicsSummary(
        community_area=community_area,
        community_area_name=ca_name,
        population=_safe_int(row.get("total_population") or row.get("population")),
        median_household_income=_estimate_median_income(row),
        acs_period=_acs_period(row.get("acs_year")),
    )


async def fetch_demographics(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> DemographicsSummary | None:
    cache = await _load_all(client=client)
    row = cache.get(community_area)
    if row is None:
        return None
    return _build_demographics(row, community_area)


async def preload(*, client: httpx.AsyncClient | None = None) -> None:
    """Pre-warm demographics cache at startup."""
    await _load_all(client=client)
