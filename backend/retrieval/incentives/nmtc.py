"""New Markets Tax Credit (NMTC) Low-Income Community lookup via HUD ArcGIS."""

import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_nmtc_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="nmtc_status")
_NOT_FOUND = object()

HUD_NMTC_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/NMTC20/FeatureServer/0/query"
)


async def check_nmtc(
    tract_fips: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a census tract qualifies as an NMTC Low-Income Community.

    Returns ``{"tract": ..., "qualifying": True, ...}`` if eligible,
    ``{"tract": ..., "qualifying": False}`` if in data but not eligible,
    or ``None`` if lookup fails.
    """
    cache_key = f"nmtc:{tract_fips}"
    cached = _nmtc_cache.get(cache_key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "where": f"GEOID='{tract_fips}'",
        "outFields": "GEOID,NMTC_LIC_INC,SEVERE_DISTRESS,DEEP_DISTRESS,POV_RATE_16_20_ACS",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(HUD_NMTC_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            _nmtc_cache.set(cache_key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        qualifying = attrs.get("NMTC_LIC_INC") == 1
        result = {
            "tract": attrs.get("GEOID", tract_fips),
            "qualifying": qualifying,
            "severe_distress": attrs.get("SEVERE_DISTRESS") == 1,
            "deep_distress": attrs.get("DEEP_DISTRESS") == 1,
            "poverty_rate": attrs.get("POV_RATE_16_20_ACS"),
        }
        _nmtc_cache.set(cache_key, result)
        return result
    except Exception as exc:
        log.warning("HUD NMTC query failed for tract %s: %s", tract_fips, exc)
        return None
    finally:
        if owns:
            await client.aclose()
