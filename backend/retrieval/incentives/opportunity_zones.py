"""Opportunity Zone lookup via HUD ArcGIS.

Census tract resolution lives in ``backend.retrieval.geo.resolve_census_tract``.
"""

import logging

import httpx

from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import resolve_census_tract  # noqa: F401 – re-export for back-compat

log = logging.getLogger(__name__)

_oz_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="oz_status")
_NOT_FOUND = object()

# HUD's Opportunity Zones FeatureServer now exposes the tract polygons on
# layer 13 (was 0), keyed by GEOID10. The layer contains *only* designated
# zones — a tract appearing in it is designated; absence means it is not.
HUD_OZ_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/Opportunity_Zones/FeatureServer/13/query"
)


async def check_opportunity_zone(
    tract_fips: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a census tract is a designated Opportunity Zone via HUD ArcGIS.

    Returns ``{"tract": "17031...", "designated": True}`` or ``None``.
    """
    oz_key = f"oz:{tract_fips}"
    cached = _oz_cache.get(oz_key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "where": f"GEOID10='{tract_fips}'",
        "outFields": "GEOID10",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(HUD_OZ_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            _oz_cache.set(oz_key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        result = {
            "tract": attrs.get("GEOID10", tract_fips),
            "designated": True,
        }
        _oz_cache.set(oz_key, result)
        return result
    except Exception as exc:
        log.warning("HUD Opportunity Zone query failed for tract %s: %s", tract_fips, exc)
        return None
    finally:
        if owns:
            await client.aclose()
