"""CCAO property characteristics by PIN."""

import logging

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="property_chars")
_NOT_FOUND = object()


async def get_characteristics(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Fetch the most recent property characteristics for a PIN."""
    key = f"chars:{pin14}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "year DESC",
        "$limit": settings.limit_ccao_characteristics,
    }
    try:
        rows = await socrata_get(
            settings.dataset_ccao_characteristics,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not rows:
            _cache.set(key, _NOT_FOUND)
            return None
        _cache.set(key, rows[0])
        return rows[0]
    except Exception as exc:
        # Raise (nothing cached): the property domain reports "property characteristics" as a gap instead of
        # treating a failed call as a parcel the Assessor has no building record for (WS6 M7).
        log.warning("CCAO characteristics failed for PIN %s: %s", pin14, exc)
        raise
