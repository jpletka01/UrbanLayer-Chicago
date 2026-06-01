"""Cook County GIS parcel lookup — lat/lon to PIN14."""

import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=512)
_NOT_FOUND = object()

def _esri_to_geojson(esri_geom: dict | None) -> dict | None:
    """Convert Esri JSON rings to GeoJSON Polygon."""
    if not esri_geom:
        return None
    rings = esri_geom.get("rings")
    if not rings:
        return None
    return {"type": "Polygon", "coordinates": rings}


PARCEL_QUERY_URL = (
    "https://gis.cookcountyil.gov/traditional/rest/services"
    "/cookVwrDynmc/MapServer/44/query"
)


async def lookup_parcel(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query Cook County GIS for the parcel at a point.

    Returns a dict with pin14, bldg_class, bldg_sqft, land_sqft,
    total_value, and address — or None if no parcel found.
    """
    key = f"parcel:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(PARCEL_QUERY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            _cache.set(key, _NOT_FOUND)
            return None
        attrs = features[0].get("attributes", {})
        pin_raw = attrs.get("PIN14") or attrs.get("PIN")
        if not pin_raw:
            _cache.set(key, _NOT_FOUND)
            return None
        pin14 = str(pin_raw).replace("-", "").zfill(14)
        geometry = _esri_to_geojson(features[0].get("geometry"))
        result = {
            "pin14": pin14,
            "bldg_class": attrs.get("BLDGClass"),
            "bldg_sqft": attrs.get("BldgSqft"),
            "land_sqft": attrs.get("LandSqft"),
            "total_value": attrs.get("TotalValue"),
            "address": attrs.get("Address"),
            "geometry": geometry,
        }
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("Parcel lookup failed for (%s, %s): %s", lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()
