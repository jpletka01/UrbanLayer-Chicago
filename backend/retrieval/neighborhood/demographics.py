"""Community area demographics from Chicago Data Portal ACS dataset.

Merges two Socrata datasets:
- t68z-cikk: ACS demographics (population, income brackets, age/sex, race)
- kn9c-c2s2: Census selected socioeconomic indicators (poverty, unemployment,
  per capita income, education, hardship index)
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

_INCOME_BRACKETS: list[tuple[str, float, float]] = [
    ("under_25_000", 0, 25_000),
    ("_25_000_to_49_999", 25_000, 50_000),
    ("_50_000_to_74_999", 50_000, 75_000),
    ("_75_000_to_125_000", 75_000, 125_000),
    ("_125_000", 125_000, 200_000),
]

_AGE_FIELDS: list[tuple[str, float]] = [
    ("male_0_to_17", 8.5), ("female_0_to_17", 8.5),
    ("male_18_to_24", 21.0), ("female_18_to_24", 21.0),
    ("male_25_to_34", 29.5), ("female_25_to_34", 29.5),
    ("male_35_to_49", 42.0), ("female_35_to_49", 42.0),
    ("male_50_to_64", 57.0), ("female_50_to_64", 57.0),
    ("male_65", 75.0), ("female_65", 75.0),
]


async def _load_all(*, client: httpx.AsyncClient | None = None) -> dict[int, dict]:
    global _cache
    async with _lock:
        if _cache is not None:
            return _cache
        settings = get_settings()

        acs_coro = socrata_get(settings.dataset_demographics, {"$limit": 100}, client=client)
        socio_coro = socrata_get(settings.dataset_socioeconomic, {"$limit": 100}, client=client)
        results = await asyncio.gather(acs_coro, socio_coro, return_exceptions=True)
        acs_rows = results[0] if not isinstance(results[0], Exception) else []
        socio_rows = results[1] if not isinstance(results[1], Exception) else []
        if isinstance(results[0], Exception):
            log.warning("Failed to load ACS demographics: %s", results[0])
        if isinstance(results[1], Exception):
            log.warning("Failed to load socioeconomic indicators: %s", results[1])
        if not acs_rows and not socio_rows:
            return {}

        result: dict[int, dict] = {}
        for row in acs_rows:
            ca_raw = row.get("community_area") or row.get("community_area_number")
            ca = _safe_int(ca_raw)
            if ca is None and isinstance(ca_raw, str):
                ca = _NAME_TO_CA.get(ca_raw.upper())
            if ca is not None:
                result[ca] = row

        for row in socio_rows:
            ca = _safe_int(row.get("ca"))
            if ca is not None and ca in result:
                result[ca]["_socio"] = row
            elif ca is not None:
                result[ca] = {"_socio": row}

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


def _pct(numerator: object, denominator: object) -> float | None:
    n = _safe_float(numerator)
    d = _safe_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return round(n / d * 100, 1)


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


def _estimate_median_age(row: dict) -> float | None:
    """Estimate median age from age/sex bracket distribution."""
    buckets: list[tuple[float, float]] = []
    for field, midpoint in _AGE_FIELDS:
        count = _safe_float(row.get(field))
        if count is not None and count > 0:
            buckets.append((midpoint, count))
    if not buckets:
        return None
    total = sum(c for _, c in buckets)
    if total <= 0:
        return None
    buckets.sort(key=lambda x: x[0])
    target = total / 2.0
    cumulative = 0.0
    for midpoint, count in buckets:
        cumulative += count
        if cumulative >= target:
            return round(midpoint, 1)
    return None


def _build_demographics(row: dict, community_area: int) -> DemographicsSummary:
    socio = row.get("_socio") or {}
    population = _safe_int(row.get("total_population") or row.get("population"))

    median_income = (
        _safe_int(row.get("median_household_income"))
        or _estimate_median_income(row)
    )
    per_capita = _safe_int(socio.get("per_capita_income_"))
    if median_income is None and per_capita is not None:
        median_income = int(per_capita * 1.8)

    poverty_rate = _safe_float(socio.get("percent_households_below_poverty"))
    unemployment_rate = _safe_float(socio.get("percent_aged_16_unemployed"))

    below_poverty = _safe_int(row.get("below_poverty_level"))
    if poverty_rate is None and below_poverty is not None and population:
        poverty_rate = _pct(below_poverty, population)

    unemployed = _safe_int(row.get("unemployed"))
    in_labor_force = _safe_int(row.get("in_labor_force") or row.get("civilian_labor_force"))
    if unemployment_rate is None and unemployed is not None:
        unemployment_rate = _pct(unemployed, in_labor_force)

    owner_occupied = _safe_int(row.get("owner_occupied_housing_units") or row.get("owner_occupied"))
    total_housing = _safe_int(row.get("total_housing_units") or row.get("housing_units"))
    bachelors = _safe_int(
        row.get("bachelors_degree_or_higher")
        or row.get("bachelor_s_degree_or_higher")
    )
    pop_25_plus = _safe_int(row.get("population_25_years_and_over") or row.get("pop_25_over"))
    vacant = _safe_int(row.get("vacant_housing_units") or row.get("vacant"))

    ca_name = (
        row.get("community_area_name")
        or row.get("name")
        or socio.get("community_area_name")
        or COMMUNITY_AREAS.get(community_area)
    )

    return DemographicsSummary(
        community_area=community_area,
        community_area_name=ca_name,
        population=population,
        median_household_income=median_income,
        median_home_value=_safe_int(
            row.get("median_home_value")
            or row.get("median_value_owner_occupied")
        ),
        median_gross_rent=_safe_int(row.get("median_gross_rent") or row.get("median_rent")),
        median_age=_safe_float(row.get("median_age")) or _estimate_median_age(row),
        poverty_rate=poverty_rate,
        unemployment_rate=unemployment_rate,
        owner_occupied_pct=_pct(owner_occupied, total_housing),
        bachelors_degree_pct=_pct(bachelors, pop_25_plus),
        vacancy_rate=_pct(vacant, total_housing),
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
