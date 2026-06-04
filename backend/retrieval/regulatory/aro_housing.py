"""Affordable Requirements Ordinance (ARO) housing project data."""

import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="aro_housing")


async def aro_housing_by_community_area(
    community_area_number: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch ARO housing projects for a community area."""
    key = f"aro:{community_area_number}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "$where": f"community_area_number='{community_area_number}'",
        "$select": (
            "property_name,address,units,property_type,"
            "management_company,latitude,longitude"
        ),
        "$order": "property_name",
        "$limit": settings.limit_aro_housing,
    }
    try:
        rows = await socrata_get(
            settings.dataset_aro_housing,
            params,
            client=client,
        )
        _cache.set(key, rows)
        return rows
    except Exception as exc:
        log.warning("ARO housing query failed for CA %s: %s", community_area_number, exc)
        return []
