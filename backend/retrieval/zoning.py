"""Look up zoning classification via Chicago's ArcGIS REST API.

The ArcGIS Zoning MapServer is publicly accessible (no API key required).
Layer 1 ("Zoning Boundaries") returns ZONE_CLASS (e.g. "B2", "RS-3", "DC-16"),
ZONE_TYPE, and ORDINANCE_NUM for spatial queries (point or envelope).
"""

import asyncio
import logging

import httpx

from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds

log = logging.getLogger(__name__)

_arcgis_client: httpx.AsyncClient | None = None


def _get_arcgis_client() -> httpx.AsyncClient:
    global _arcgis_client
    if _arcgis_client is None or _arcgis_client.is_closed:
        _arcgis_client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _arcgis_client


_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="zoning")
_polygon_cache = TTLCache(ttl_seconds=3600, maxsize=77, name="zoning_polygons")
_NOT_FOUND = object()

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
    key = f"zoning:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,ZONE_TYPE,ORDINANCE_NUM",
        "returnGeometry": "false",
        "f": "json",
    }
    if client is None:
        client = _get_arcgis_client()
    # A failed request must RAISE, not return None: every caller runs this in a
    # gather(return_exceptions=True) that maps an exception to the "parcel
    # zoning" partial-failure the UI can caveat. Swallowing made a transient
    # ArcGIS failure indistinguishable from "point has no zone" — the Scorecard
    # rendered silent absence (4/100 first-hit misses in the 2026-07-02 lot
    # coverage benchmark were exactly this). Only a definitive empty/zone-less
    # response means not-found (and only that is negatively cached).
    try:
        resp = await client.get(ZONING_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("Zoning lookup failed for (%s, %s): %s", lat, lon, exc)
        raise
    # ArcGIS reports errors in a 200 body ({"error": {...}}) — that is a failed
    # lookup, not an empty result.
    if isinstance(data.get("error"), dict):
        raise RuntimeError(f"ArcGIS zoning query error: {data['error'].get('message')}")
    features = data.get("features", [])
    if not features:
        _cache.set(key, _NOT_FOUND)
        return None
    attrs = features[0].get("attributes", {})
    zone_class = attrs.get("ZONE_CLASS")
    if not zone_class:
        _cache.set(key, _NOT_FOUND)
        return None
    result = {
        "zone_class": zone_class,
        "zone_type": attrs.get("ZONE_TYPE"),
        "ordinance_num": attrs.get("ORDINANCE_NUM"),
    }
    _cache.set(key, result)
    return result


async def adjacent_parcel_zoning(
    lat: float,
    lon: float,
    *,
    offset_deg: float = 0.001,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str | None]:
    """Look up zoning at 4 cardinal points around a location.

    Returns {"N": "RS-3", "S": "B3-2", "E": "RS-3", "W": "RS-3"}.
    """
    directions = {
        "N": (lat + offset_deg, lon),
        "S": (lat - offset_deg, lon),
        "E": (lat, lon + offset_deg),
        "W": (lat, lon - offset_deg),
    }
    tasks = {
        d: lookup_zoning(coords[0], coords[1], client=client)
        for d, coords in directions.items()
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    adjacent: dict[str, str | None] = {}
    for direction, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            adjacent[direction] = None
        elif result and result.get("zone_class"):
            adjacent[direction] = result["zone_class"]
        else:
            adjacent[direction] = None
    return adjacent


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
    key = f"zoning_poly:{community_area}"
    cached = _polygon_cache.get(key)
    if cached is not None:
        return cached

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
    if client is None:
        client = _get_arcgis_client()
    try:
        resp = await client.get(ZONING_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("exceededTransferLimit"):
            log.warning("Zoning query exceeded transfer limit for CA %s", community_area)
        _polygon_cache.set(key, data)
        return data
    except Exception as exc:
        log.warning("Zoning polygon fetch failed for CA %s: %s", community_area, exc)
        return _EMPTY_FC


async def zoning_polygons_near(
    lat: float,
    lon: float,
    *,
    radius_mi: float = 0.25,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Zoning district polygons in a small envelope around a point, as GeoJSON.

    The parcel-scale variant of ``zoning_polygons_for_map`` (whole community
    areas are ~1 MB; the Property Profile's zoning module map only needs the
    blocks around the parcel). Cache key rounds the point to ~100 m so nearby
    lookups share an entry.
    """
    import math

    key = f"zoning_near:{lat:.3f},{lon:.3f}:{radius_mi}"
    cached = _polygon_cache.get(key)
    if cached is not None:
        return cached

    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(math.cos(math.radians(lat)), 0.2))
    params = {
        "geometry": f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,ZONE_TYPE,ORDINANCE_NUM",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    if client is None:
        client = _get_arcgis_client()
    try:
        resp = await client.get(ZONING_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        _polygon_cache.set(key, data)
        return data
    except Exception as exc:
        log.warning("Zoning polygon fetch failed near (%s, %s): %s", lat, lon, exc)
        return _EMPTY_FC
