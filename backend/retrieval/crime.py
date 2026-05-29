import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import grouped_count, socrata_get
from backend.retrieval.utils import cutoff_iso


async def crime_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
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

    return crimes


async def crime_recent_by_block(
    block: str,
    *,
    days: int = 30,
    limit: int = 20,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    cutoff = cutoff_iso(days, lag_days=settings.crime_lag_days)
    params = {
        "$where": f"block='{block}' AND date > '{cutoff}'",
        "$order": "date DESC",
        "$limit": limit,
    }
    return await socrata_get(settings.dataset_crime, params, client=client)
