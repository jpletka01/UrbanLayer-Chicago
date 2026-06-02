import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_aggregate, socrata_get

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="business")


async def businesses_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"business:{community_area}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    where = (
        f"community_area='{community_area}' "
        "AND license_status='AAI'"
    )

    grouped_task = socrata_aggregate(
        settings.dataset_business,
        where=where,
        group="license_description",
        select="license_description,count(*) as count",
        limit=100,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_business,
        {
            "$where": where,
            "$select": "business_activity,date_issued",
            "$order": "date_issued DESC",
            "$limit": settings.limit_business_detail,
        },
        client=client,
    )

    grouped, detail = await asyncio.gather(grouped_task, detail_task)
    result = {"grouped": grouped, "detail": detail}
    _cache.set(key, result)
    return result
