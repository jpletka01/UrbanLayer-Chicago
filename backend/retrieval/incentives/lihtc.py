"""LIHTC Qualified Census Tract (QCT) lookup via HUD ArcGIS."""

import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_qct_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="qct_status")
_NOT_FOUND = object()

HUD_QCT_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/Qualified_Census_Tracts/FeatureServer/0/query"
)


async def check_qct(
    tract_fips: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a census tract is a HUD Qualified Census Tract.

    QCTs receive enhanced LIHTC basis boost (up to 130%).
    Returns ``{"tract": "17031...", "designated": True, "name": "..."}``
    or ``None``.
    """
    cache_key = f"qct:{tract_fips}"
    cached = _qct_cache.get(cache_key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "where": f"GEOID='{tract_fips}'",
        "outFields": "GEOID,NAME",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(HUD_QCT_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            _qct_cache.set(cache_key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        result = {
            "tract": attrs.get("GEOID", tract_fips),
            "designated": True,
            "name": attrs.get("NAME"),
        }
        _qct_cache.set(cache_key, result)
        return result
    except Exception as exc:
        log.warning("HUD QCT query failed for tract %s: %s", tract_fips, exc)
        return None
    finally:
        if owns:
            await client.aclose()
