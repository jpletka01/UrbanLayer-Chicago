"""Community area demographics from Chicago Data Portal ACS dataset."""

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.models import DemographicsSummary
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache: dict[int, dict] | None = None
_lock = asyncio.Lock()


async def _load_all(*, client: httpx.AsyncClient | None = None) -> dict[int, dict]:
    global _cache
    async with _lock:
        if _cache is not None:
            return _cache
        settings = get_settings()
        try:
            rows = await socrata_get(
                settings.dataset_demographics,
                {"$limit": 100},
                client=client,
            )
        except Exception:
            log.warning("Failed to load demographics dataset", exc_info=True)
            _cache = {}
            return _cache

        result: dict[int, dict] = {}
        for row in rows:
            ca = _safe_int(row.get("community_area") or row.get("community_area_number"))
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


def _pct(numerator: object, denominator: object) -> float | None:
    n = _safe_float(numerator)
    d = _safe_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return round(n / d * 100, 1)


def _build_demographics(row: dict, community_area: int) -> DemographicsSummary:
    population = _safe_int(row.get("population") or row.get("total_population"))
    below_poverty = _safe_int(row.get("below_poverty_level"))
    unemployed = _safe_int(row.get("unemployed"))
    in_labor_force = _safe_int(row.get("in_labor_force") or row.get("civilian_labor_force"))
    owner_occupied = _safe_int(row.get("owner_occupied_housing_units") or row.get("owner_occupied"))
    total_housing = _safe_int(row.get("total_housing_units") or row.get("housing_units"))
    bachelors = _safe_int(
        row.get("bachelors_degree_or_higher")
        or row.get("bachelor_s_degree_or_higher")
    )
    pop_25_plus = _safe_int(row.get("population_25_years_and_over") or row.get("pop_25_over"))
    vacant = _safe_int(row.get("vacant_housing_units") or row.get("vacant"))

    return DemographicsSummary(
        community_area=community_area,
        community_area_name=row.get("community_area_name") or row.get("name"),
        population=population,
        median_household_income=_safe_int(row.get("median_household_income")),
        median_home_value=_safe_int(
            row.get("median_home_value")
            or row.get("median_value_owner_occupied")
        ),
        median_gross_rent=_safe_int(row.get("median_gross_rent") or row.get("median_rent")),
        median_age=_safe_float(row.get("median_age")),
        poverty_rate=_pct(below_poverty, population),
        unemployment_rate=_pct(unemployed, in_labor_force),
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
