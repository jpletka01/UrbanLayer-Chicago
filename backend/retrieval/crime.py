import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import grouped_count, socrata_get
from backend.retrieval.utils import cutoff_iso

_cache = TTLCache(ttl_seconds=900, maxsize=256, name="crime")


def _year_earlier(dt: datetime) -> datetime:
    """Same calendar date one year earlier; Feb 29 clamps to Feb 28 (a bare
    .replace(year=...) raises ValueError on leap days and took the whole
    YoY card down for the day)."""
    try:
        return dt.replace(year=dt.year - 1)
    except ValueError:
        return dt.replace(year=dt.year - 1, day=28)


async def crime_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"crime:{community_area}:{days}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    cutoff = cutoff_iso(days, lag_days=settings.crime_lag_days)

    crimes_task = grouped_count(
        settings.dataset_crime,
        where=f"community_area='{community_area}' AND date > '{cutoff}'",
        group="primary_type",
        select="primary_type",
        limit=settings.limit_crime,
        client=client,
    )
    arrests_params = {
        "$where": f"community_area='{community_area}' AND date > '{cutoff}' AND arrest=true",
        "$group": "primary_type",
        "$select": "primary_type,count(*) as arrests",
        "$limit": settings.limit_crime,
    }
    arrests_task = socrata_get(settings.dataset_crime, arrests_params, client=client)
    crimes, arrests = await asyncio.gather(crimes_task, arrests_task)

    arrest_map = {r["primary_type"]: r["arrests"] for r in arrests}
    for row in crimes:
        row["arrests"] = arrest_map.get(row["primary_type"], "0")

    _cache.set(key, crimes)
    return crimes


async def crime_yoy_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch crime counts for the same date range in the current and prior year."""
    key = f"crime_yoy:{community_area}:{days}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    lag = settings.crime_lag_days
    now = datetime.now(timezone.utc)
    end = now - timedelta(days=lag)
    start = end - timedelta(days=days)
    prior_end = _year_earlier(end)
    prior_start = _year_earlier(start)

    fmt = "%Y-%m-%dT00:00:00.000"

    async def _counts(after: str, before: str) -> list[dict[str, Any]]:
        return await grouped_count(
            settings.dataset_crime,
            where=(
                f"community_area='{community_area}'"
                f" AND date > '{after}' AND date < '{before}'"
            ),
            group="primary_type",
            select="primary_type",
            limit=settings.limit_crime,
            client=client,
        )

    current, prior = await asyncio.gather(
        _counts(start.strftime(fmt), end.strftime(fmt)),
        _counts(prior_start.strftime(fmt), prior_end.strftime(fmt)),
    )

    current_month = f"{start.strftime('%b')}–{end.strftime('%b %Y')}"
    prior_month = f"{prior_start.strftime('%b')}–{prior_end.strftime('%b %Y')}"

    result = {
        "current": current,
        "prior": prior,
        "current_label": current_month,
        "prior_label": prior_month,
    }
    _cache.set(key, result)
    return result
