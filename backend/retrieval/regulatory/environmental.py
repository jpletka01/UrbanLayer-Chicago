"""Query EPA Facility Registry Service for nearby brownfield sites.

EPA decommissioned the old geopub.epa.gov OEI/FRS_INTERESTS MapServer. The FRS
data is now published as national hosted feature services on EPA's ArcGIS
Online org. ACRES (Assessment, Cleanup and Redevelopment Exchange System) is
the brownfields registry, exposed at FRS_INTERESTS_ACRES — a point layer that
supports the same lat/lon + radius query we already build.
"""

import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=256)

EPA_BROWNFIELDS_URL = (
    "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services"
    "/FRS_INTERESTS_ACRES/FeatureServer/0/query"
)


async def query_brownfield_sites(
    lat: float,
    lon: float,
    *,
    radius_meters: int = 1000,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query for brownfield sites within *radius_meters* of a point.

    Returns a list of site dicts (may be empty).
    """
    key = f"brownfield:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(radius_meters),
        "units": "esriSRUnit_Meter",
        "outFields": "PRIMARY_NAME,REGISTRY_ID,INTEREST_TYPE,LATITUDE83,LONGITUDE83",
        "returnGeometry": "false",
        "resultRecordCount": "10",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(EPA_BROWNFIELDS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        sites: list[dict] = []
        for feat in features:
            attrs = feat.get("attributes", {})
            name = attrs.get("PRIMARY_NAME")
            if not name:
                continue
            sites.append({
                "site_name": name,
                "epa_id": attrs.get("REGISTRY_ID"),
                "interest_type": attrs.get("INTEREST_TYPE"),
                "latitude": attrs.get("LATITUDE83"),
                "longitude": attrs.get("LONGITUDE83"),
            })
        _cache.set(key, sites)
        return sites
    except Exception as exc:
        log.warning("EPA brownfield query failed for (%s, %s): %s", lat, lon, exc)
        return []
    finally:
        if owns:
            await client.aclose()
