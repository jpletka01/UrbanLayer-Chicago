from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds
from backend.retrieval.socrata import socrata_get
from backend.retrieval.utils import cutoff_iso

_permits_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="permits")
_violations_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="violations")


async def permits_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"permits:{community_area}:{days}"
    cached = _permits_cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            f"AND issue_date > '{cutoff_iso(days)}'"
        ),
        "$select": (
            "permit_type,work_description,issue_date,"
            "street_number,street_direction,street_name,reported_cost"
        ),
        "$order": "issue_date DESC",
        "$limit": settings.limit_permits,
    }
    result = await socrata_get(settings.dataset_permits, params, client=client)
    _permits_cache.set(key, result)
    return result


async def violations_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"violations:{community_area}:{days}"
    cached = _violations_cache.get(key)
    if cached is not None:
        return cached

    bounds = community_area_bounds(community_area)
    if not bounds:
        return []
    min_lat, min_lon, max_lat, max_lon = bounds

    settings = get_settings()
    params = {
        "$where": (
            f"latitude between '{min_lat}' and '{max_lat}' "
            f"AND longitude between '{min_lon}' and '{max_lon}' "
            f"AND violation_date > '{cutoff_iso(days)}'"
        ),
        "$select": (
            "violation_date,violation_description,violation_status,"
            "street_number,street_direction,street_name,latitude,longitude"
        ),
        "$order": "violation_date DESC",
        "$limit": settings.limit_violations,
    }
    result = await socrata_get(settings.dataset_violations, params, client=client)
    _violations_cache.set(key, result)
    return result
