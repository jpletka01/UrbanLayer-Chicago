"""Vacant and abandoned buildings from Chicago Data Portal."""

import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds
from backend.retrieval.socrata import socrata_aggregate, socrata_get

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="vacant_buildings")


async def vacant_buildings_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"vacant:{community_area}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    bounds = community_area_bounds(community_area)
    if not bounds:
        return {"grouped": [], "detail": []}
    min_lat, min_lon, max_lat, max_lon = bounds

    settings = get_settings()
    where = (
        f"latitude between '{min_lat}' and '{max_lat}' "
        f"AND longitude between '{min_lon}' and '{max_lon}'"
    )

    grouped_task = socrata_aggregate(
        settings.dataset_vacant_buildings,
        where=where,
        group="issuing_department",
        select="issuing_department,count(*) as count",
        limit=20,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_vacant_buildings,
        {
            "$where": where,
            "$select": "property_address,issued_date,violation_type,entity_or_person_s_,current_amount_due,latitude,longitude",
            "$order": "issued_date DESC",
            "$limit": settings.limit_vacant_buildings_detail,
        },
        client=client,
    )

    grouped, detail = await asyncio.gather(grouped_task, detail_task)
    result = {"grouped": grouped, "detail": detail}
    _cache.set(key, result)
    return result
