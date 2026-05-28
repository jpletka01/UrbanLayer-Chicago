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
    cutoff = _cutoff_iso(days)

    crimes_params = {
        "$where": f"community_area='{community_area}' AND date > '{cutoff}'",
        "$group": "primary_type",
        "$select": "primary_type,count(*) as count",
        "$order": "count DESC",
        "$limit": 35,
    }
    arrests_params = {
        "$where": f"community_area='{community_area}' AND date > '{cutoff}' AND arrest=true",
        "$group": "primary_type",
        "$select": "primary_type,count(*) as arrests",
        "$limit": 35,
    }

    import asyncio
    crimes_task = socrata_get(settings.dataset_crime, crimes_params, client=client)
    arrests_task = socrata_get(settings.dataset_crime, arrests_params, client=client)
    crimes, arrests = await asyncio.gather(crimes_task, arrests_task)

    arrest_map = {r["primary_type"]: r["arrests"] for r in arrests}
    for row in crimes:
        row["arrests"] = arrest_map.get(row["primary_type"], "0")

    return crimes


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
