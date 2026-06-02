"""CCAO parcel sales history by PIN."""

import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="property_sales")


async def get_sales(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch sales history for a PIN (most recent 10 sales)."""
    key = f"sales:{pin14}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "sale_date DESC",
        "$limit": settings.limit_ccao_sales,
    }
    try:
        result = await socrata_get(
            settings.dataset_ccao_sales,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("CCAO sales failed for PIN %s: %s", pin14, exc)
        return []
