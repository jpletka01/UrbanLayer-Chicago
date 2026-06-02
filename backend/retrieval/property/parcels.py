"""Cook County GIS parcel lookup — lat/lon to PIN14.

Primary: ArcGIS spatial query on Cook County GIS MapServer layer 44.
Fallback: Socrata Parcel Universe (pabr-t5kh) bounding-box query when GIS
is down or returns no results.
"""

import asyncio
import logging
import math

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="parcels")
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

_BBOX_DELTA = 0.002  # ~220m at Chicago's latitude


async def lookup_parcel(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query Cook County for the parcel at a point.

    Tries ArcGIS first, falls back to Socrata Parcel Universe if GIS
    returns nothing (service has been intermittently/fully down since
    mid-2026 due to broken spatial index).
    """
    key = f"parcel:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    result = await _lookup_parcel_gis(lat, lon, client=client)
    if result is None:
        result = await _lookup_parcel_socrata(lat, lon, client=client)
    if result is None:
        _cache.set(key, _NOT_FOUND)
    else:
        _cache.set(key, result)
    return result


async def _lookup_parcel_gis(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Primary: ArcGIS spatial point query on Cook County GIS."""
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
        features = []
        for attempt in range(2):
            resp = await client.get(PARCEL_QUERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            if features:
                break
            if attempt == 0:
                await asyncio.sleep(0.5)
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        pin_raw = attrs.get("PIN14") or attrs.get("PIN")
        if not pin_raw:
            return None
        pin14 = str(pin_raw).replace("-", "").zfill(14)
        geometry = _esri_to_geojson(features[0].get("geometry"))
        return {
            "pin14": pin14,
            "bldg_class": attrs.get("BLDGClass"),
            "bldg_sqft": attrs.get("BldgSqft"),
            "land_sqft": attrs.get("LandSqft"),
            "total_value": attrs.get("TotalValue"),
            "address": attrs.get("Address"),
            "geometry": geometry,
        }
    except Exception as exc:
        log.warning("GIS parcel lookup failed for (%s, %s): %s", lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()


async def _lookup_parcel_socrata(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Fallback: bounding-box query on Socrata Parcel Universe, pick closest."""
    settings = get_settings()
    params = {
        "$where": (
            f"lat between '{lat - _BBOX_DELTA}' and '{lat + _BBOX_DELTA}' "
            f"and lon between '{lon - _BBOX_DELTA}' and '{lon + _BBOX_DELTA}'"
        ),
        "$select": "pin,pin10,class,lat,lon",
        "$limit": settings.limit_ccao_parcels,
    }
    try:
        rows = await socrata_get(
            settings.dataset_ccao_parcels,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not rows:
            return None
        closest = min(rows, key=lambda r: _distance_sq(lat, lon, r))
        pin_raw = closest.get("pin", "")
        if not pin_raw:
            return None
        pin14 = str(pin_raw).replace("-", "").zfill(14)
        return {
            "pin14": pin14,
            "bldg_class": closest.get("class"),
            "bldg_sqft": None,
            "land_sqft": None,
            "total_value": None,
            "address": None,
            "geometry": None,
        }
    except Exception as exc:
        log.warning("Socrata parcel fallback failed for (%s, %s): %s", lat, lon, exc)
        return None


def _distance_sq(lat: float, lon: float, row: dict) -> float:
    """Squared Euclidean distance — good enough for nearest-neighbor in a small box."""
    try:
        rlat = float(row["lat"])
        rlon = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return math.inf
    return (lat - rlat) ** 2 + (lon - rlon) ** 2
