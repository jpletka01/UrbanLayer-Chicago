import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds
from backend.retrieval.socrata import socrata_aggregate, socrata_get
from backend.retrieval.utils import cutoff_iso

_permits_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="permits")
_violations_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="violations")


async def permits_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"permits:{community_area}:{days}"
    cached = _permits_cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    where = (
        f"community_area='{community_area}' "
        f"AND issue_date > '{cutoff_iso(days)}'"
    )

    grouped_task = socrata_aggregate(
        settings.dataset_permits,
        where=where,
        group="permit_type",
        select="permit_type,count(*) as count,sum(reported_cost) as total_cost",
        limit=50,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_permits,
        {
            "$where": where,
            "$select": "work_description,issue_date",
            "$order": "issue_date DESC",
            "$limit": settings.limit_permits_detail,
        },
        client=client,
    )

    grouped, detail = await asyncio.gather(grouped_task, detail_task)
    result = {"grouped": grouped, "detail": detail}
    _permits_cache.set(key, result)
    return result


async def violations_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"violations:{community_area}:{days}"
    cached = _violations_cache.get(key)
    if cached is not None:
        return cached

    bounds = community_area_bounds(community_area)
    if not bounds:
        return {"status_counts": [], "detail": []}
    min_lat, min_lon, max_lat, max_lon = bounds

    settings = get_settings()
    where = (
        f"latitude between '{min_lat}' and '{max_lat}' "
        f"AND longitude between '{min_lon}' and '{max_lon}' "
        f"AND violation_date > '{cutoff_iso(days)}'"
    )

    status_task = socrata_aggregate(
        settings.dataset_violations,
        where=where,
        group="violation_status",
        select="violation_status,count(*) as count",
        limit=10,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_violations,
        {
            "$where": where,
            "$select": (
                "violation_date,violation_code,violation_description,"
                "violation_status,"
                "street_number,street_direction,street_name,latitude,longitude"
            ),
            "$order": "violation_status ASC,violation_date DESC",
            "$limit": settings.limit_violations,
        },
        client=client,
    )

    status_counts, detail = await asyncio.gather(status_task, detail_task)
    result = {"status_counts": status_counts, "detail": detail}
    _violations_cache.set(key, result)
    return result
