"""Walk Score, Transit Score, and Bike Score from the Walk Score API.

``None`` only means the feature is off (no API key). Every answer that isn't a score (a failed request,
"still calculating", quota, a bad key, any other status) raises ``WalkScoreError`` and is not cached, so
the Profile says the score wasn't checked instead of dropping the tile; a bad key used to be cached as
"not found" for 48 hours (decision Item 65).
"""

import logging

import httpx

from backend.config import get_settings
from backend.models import WalkScoreSummary
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=172800, maxsize=256, name="walkscore")


class WalkScoreError(RuntimeError):
    """Walk Score gave no score: "not checked", never "no score"."""


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
    except Exception as exc:
        # Type only: httpx's message carries the request URL, and the URL carries the API key.
        raise WalkScoreError(f"Walk Score request failed ({type(exc).__name__})") from None
    finally:
        if owns:
            await client.aclose()

    status = data.get("status") if isinstance(data, dict) else None
    if status != 1:
        # 2 = still calculating, 40 = bad key, 41 = quota, 30/31 = bad point / their error (API docs)
        raise WalkScoreError(f"Walk Score returned status {status}")

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
