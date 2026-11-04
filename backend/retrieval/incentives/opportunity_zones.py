"""Opportunity Zone lookup via HUD ArcGIS.

Opportunity Zones were designated in 2018 on **2010** census tracts (the layer's key is ``GEOID10``),
but ``resolve_census_tract`` returns the 2020 tract the FCC places a point in. Where a tract was split
or renumbered in 2020, matching by id read a designated tract as "not designated". With a point the
check is a point-in-polygon query against the designated tracts' own outlines, so the tract vintage
no longer matters (decision Item 65). The tract-id path stays for callers with no point.

Census tract resolution lives in ``backend.retrieval.geo.resolve_census_tract``.
"""

import logging

import httpx

from backend.retrieval.cache import TTLCache
from backend.retrieval.incentives._hud_tracts import tract_features
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
    tract_fips: str | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check whether a point (or, with no point, a 2010 census tract) is in a designated Opportunity Zone.

    Returns ``{"tract": "17031...", "designated": True}`` (``tract`` = the designated 2010 tract) or
    ``None`` (checked, not designated). A failed or malformed response raises and caches nothing.
    """
    if lat is not None and lon is not None:
        oz_key = f"oz:pt:{round(lat, 5)}:{round(lon, 5)}"
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "GEOID10",
            "returnGeometry": "false",
            "f": "json",
        }
        fallback_tract = tract_fips
    elif tract_fips:
        oz_key = f"oz:{tract_fips}"
        params = {
            "where": f"GEOID10='{tract_fips}'",
            "outFields": "GEOID10",
            "returnGeometry": "false",
            "f": "json",
        }
        fallback_tract = tract_fips
    else:
        raise ValueError("check_opportunity_zone needs a point or a tract")

    cached = _oz_cache.get(oz_key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(HUD_OZ_URL, params=params)
        resp.raise_for_status()
        features = tract_features(resp.json(), "Opportunity Zones")
        if not features:
            _oz_cache.set(oz_key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        result = {
            "tract": attrs.get("GEOID10", fallback_tract),
            "designated": True,
        }
        _oz_cache.set(oz_key, result)
        return result
    finally:
        if owns:
            await client.aclose()
