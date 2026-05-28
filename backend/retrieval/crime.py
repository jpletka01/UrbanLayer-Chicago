from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get


def _cutoff_iso(days_ago: int) -> str:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_ago + settings.crime_lag_days)
    return cutoff.strftime("%Y-%m-%dT00:00:00.000")


async def crime_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": f"community_area='{community_area}' AND date > '{_cutoff_iso(days)}'",
        "$group": "primary_type",
        "$select": "primary_type,count(*) as count,sum(case(arrest='true',1,0)) as arrests",
        "$order": "count DESC",
        "$limit": 35,
    }
    return await socrata_get(settings.dataset_crime, params, client=client)


async def crime_recent_by_block(
    block: str,
    *,
    days: int = 30,
    limit: int = 20,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": f"block='{block}' AND date > '{_cutoff_iso(days)}'",
        "$order": "date DESC",
        "$limit": limit,
    }
    return await socrata_get(settings.dataset_crime, params, client=client)
