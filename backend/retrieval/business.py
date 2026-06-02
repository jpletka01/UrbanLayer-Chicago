from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="business")


async def businesses_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"business:{community_area}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND license_status='AAI'"
        ),
        "$select": (
            "legal_name,doing_business_as_name,license_description,"
            "business_activity,address,date_issued"
        ),
        "$order": "date_issued DESC",
        "$limit": settings.limit_business,
    }
    result = await socrata_get(settings.dataset_business, params, client=client)
    _cache.set(key, result)
    return result
