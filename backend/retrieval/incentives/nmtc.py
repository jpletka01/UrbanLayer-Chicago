"""New Markets Tax Credit (NMTC) Low-Income Community lookup via HUD ArcGIS."""

import logging

import httpx

from backend.retrieval.cache import TTLCache
from backend.retrieval.incentives._hud_tracts import HudLayerError, tract_features

log = logging.getLogger(__name__)

_nmtc_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="nmtc_status")

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

    Returns ``{"tract": ..., "qualifying": True, ...}`` if eligible, or
    ``{"tract": ..., "qualifying": False, ...}`` if listed but not eligible. The layer lists every
    tract (1,331 in Cook County, 708 not qualifying; measured 2026-11-03), so a tract it doesn't list,
    like a failed or malformed response, raises: "not checked", never "not eligible" (Item 65).
    """
    cache_key = f"nmtc:{tract_fips}"
    cached = _nmtc_cache.get(cache_key)
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
        features = tract_features(resp.json(), "NMTC")
        if not features:
            raise HudLayerError(f"NMTC: tract {tract_fips} is not in the layer")
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
    finally:
        if owns:
            await client.aclose()
