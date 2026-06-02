"""Walk Score, Transit Score, and Bike Score from the Walk Score API."""

import logging
from urllib.parse import quote

import httpx

from backend.config import get_settings
from backend.models import WalkScoreSummary
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=172800, maxsize=256, name="walkscore")
_NOT_FOUND = object()

WALKSCORE_API_URL = "https://api.walkscore.com/score"


async def fetch_walkscore(
    lat: float,
    lon: float,
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> WalkScoreSummary | None:
    key = f"walkscore:{round(lat, 4)}:{round(lon, 4)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    api_key = get_settings().walkscore_api_key
    if not api_key:
        return None

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(
            WALKSCORE_API_URL,
            params={
                "format": "json",
                "address": address,
                "lat": str(lat),
                "lon": str(lon),
                "transit": "1",
                "bike": "1",
                "wsapikey": api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        log.warning("Walk Score API request failed", exc_info=True)
        return None
    finally:
        if owns:
            await client.aclose()

    status = data.get("status")
    if status == 2:
        log.debug("Walk Score still calculating for %s", address)
        return None
    if status == 40:
        log.error("Walk Score API: invalid API key")
        _cache.set(key, _NOT_FOUND)
        return None
    if status == 41:
        log.warning("Walk Score API: daily quota exceeded")
        return None
    if status != 1:
        log.warning("Walk Score API returned status %s for %s", status, address)
        _cache.set(key, _NOT_FOUND)
        return None

    transit_obj = data.get("transit") or {}
    bike_obj = data.get("bike") or {}

    result = WalkScoreSummary(
        walk_score=data.get("walkscore"),
        walk_description=data.get("description"),
        transit_score=transit_obj.get("score"),
        transit_description=transit_obj.get("description"),
        bike_score=bike_obj.get("score"),
        bike_description=bike_obj.get("description"),
        ws_link=data.get("ws_link"),
    )
    _cache.set(key, result)
    return result
