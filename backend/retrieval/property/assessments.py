"""CCAO assessed values by PIN."""

import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="assessments")
_NOT_FOUND = object()


async def get_assessments(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch assessment history for a PIN (most recent 5 years)."""
    key = f"assessments:{pin14}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return []
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "tax_year DESC",
        "$limit": settings.limit_ccao_assessments,
    }
    try:
        result = await socrata_get(
            settings.dataset_ccao_assessments,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("CCAO assessments failed for PIN %s: %s", pin14, exc)
        _cache.set(key, _NOT_FOUND)
        return []
