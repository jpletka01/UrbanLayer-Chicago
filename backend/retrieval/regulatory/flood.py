"""Query FEMA National Flood Hazard Layer (NFHL) via ArcGIS REST."""

import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_fema_client: httpx.AsyncClient | None = None


def _get_fema_client() -> httpx.AsyncClient:
    global _fema_client
    if _fema_client is None or _fema_client.is_closed:
        _fema_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
    return _fema_client


_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="flood")
_NOT_FOUND = object()

# FEMA relocated the public NFHL service from /gis/nfhl/rest/services to
# /arcgis/rest/services. Layer 28 is "Flood Hazard Zones".
FEMA_NFHL_URL = (
    "https://hazards.fema.gov/arcgis/rest/services"
    "/public/NFHL/MapServer/28/query"
)


async def query_flood_zone(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query the FEMA NFHL for the flood zone at a point.

    Returns ``{"fld_zone": "AE", "zone_subty": "...", "sfha_tf": "T"}``
    or ``None`` if the point is outside any mapped flood zone.
    """
    key = f"flood:{round(lat, 5)}:{round(lon, 5)}"
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
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    if client is None:
        client = _get_fema_client()
    try:
        resp = await client.get(FEMA_NFHL_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            _cache.set(key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        fld_zone = attrs.get("FLD_ZONE")
        if not fld_zone:
            _cache.set(key, _NOT_FOUND)
            return None
        result = {
            "fld_zone": fld_zone,
            "zone_subty": attrs.get("ZONE_SUBTY"),
            "sfha_tf": attrs.get("SFHA_TF"),
        }
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("FEMA flood zone query failed for (%s, %s): %s", lat, lon, exc)
        return None
