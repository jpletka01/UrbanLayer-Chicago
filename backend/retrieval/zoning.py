"""Look up zoning classification via Chicago's ArcGIS REST API.

The ArcGIS Zoning MapServer is publicly accessible (no API key required).
Layer 1 ("Zoning Boundaries") returns ZONE_CLASS (e.g. "B2", "RS-3", "DC-16"),
ZONE_TYPE, and ORDINANCE_NUM for spatial queries (point or envelope).
"""

import logging

import httpx

from backend.retrieval.geo import community_area_bounds

log = logging.getLogger(__name__)

ZONING_QUERY_URL = (
    "https://gisapps.chicago.gov/arcgis/rest/services"
    "/ExternalApps/Zoning/MapServer/1/query"
)

ZONING_MAP_URL = "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"


async def lookup_zoning(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query the ArcGIS Zoning MapServer for the zoning classification at a point.

    Returns {"zone_class": "B3-2", "zone_type": 1, "ordinance_num": "..."} or None.
    """
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,ZONE_TYPE,ORDINANCE_NUM",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(ZONING_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        zone_class = attrs.get("ZONE_CLASS")
        if not zone_class:
            return None
        return {
            "zone_class": zone_class,
            "zone_type": attrs.get("ZONE_TYPE"),
            "ordinance_num": attrs.get("ORDINANCE_NUM"),
        }
    except Exception as exc:
        log.warning("Zoning lookup failed for (%s, %s): %s", lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()


_EMPTY_FC: dict = {"type": "FeatureCollection", "features": []}


async def zoning_polygons_for_map(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch all zoning district polygons within a community area as GeoJSON.

    Returns a GeoJSON FeatureCollection with ZONE_CLASS, ZONE_TYPE, and
    ORDINANCE_NUM on each feature. Typically 200-600 polygons, ~1 MB.
    """
    bounds = community_area_bounds(community_area)
    if bounds is None:
        log.warning("No bounds for community area %s", community_area)
        return _EMPTY_FC

    min_lat, min_lon, max_lat, max_lon = bounds
    params = {
        "geometry": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,ZONE_TYPE,ORDINANCE_NUM",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
    try:
        resp = await client.get(ZONING_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("exceededTransferLimit"):
            log.warning("Zoning query exceeded transfer limit for CA %s", community_area)
        return data
    except Exception as exc:
        log.warning("Zoning polygon fetch failed for CA %s: %s", community_area, exc)
        return _EMPTY_FC
    finally:
        if owns:
            await client.aclose()
