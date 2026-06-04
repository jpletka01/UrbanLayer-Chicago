"""Food establishment inspections from Chicago Data Portal."""

import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds
from backend.retrieval.socrata import socrata_aggregate, socrata_get
from backend.retrieval.utils import cutoff_iso

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="food_inspections")


async def food_inspections_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"food_inspections:{community_area}:{days}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    bounds = community_area_bounds(community_area)
    if not bounds:
        return {"by_result": [], "by_risk": [], "detail": []}
    min_lat, min_lon, max_lat, max_lon = bounds

    settings = get_settings()
    where = (
        f"latitude between '{min_lat}' and '{max_lat}' "
        f"AND longitude between '{min_lon}' and '{max_lon}' "
        f"AND inspection_date > '{cutoff_iso(days)}'"
    )

    result_task = socrata_aggregate(
        settings.dataset_food_inspections,
        where=where,
        group="results",
        select="results,count(*) as count",
        limit=20,
        client=client,
    )
    risk_task = socrata_aggregate(
        settings.dataset_food_inspections,
        where=where,
        group="risk",
        select="risk,count(*) as count",
        limit=10,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_food_inspections,
        {
            "$where": where,
            "$select": "dba_name,facility_type,risk,results,inspection_date,violations,latitude,longitude",
            "$order": "inspection_date DESC",
            "$limit": settings.limit_food_inspections_detail,
        },
        client=client,
    )

    by_result, by_risk, detail = await asyncio.gather(result_task, risk_task, detail_task)
    result = {"by_result": by_result, "by_risk": by_risk, "detail": detail}
    _cache.set(key, result)
    return result
