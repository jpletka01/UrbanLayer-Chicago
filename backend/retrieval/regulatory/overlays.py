"""Query Chicago Zoning MapServer overlay layers (2-24).

All layers share the same ArcGIS REST endpoint with a variable layer ID.
This generalizes the point-query pattern from ``zoning.py`` (layer 1).
"""

import asyncio
import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=512)
_NOT_FOUND = object()

ZONING_BASE_URL = (
    "https://gisapps.chicago.gov/arcgis/rest/services"
    "/ExternalApps/Zoning/MapServer"
)

OVERLAY_LAYERS: dict[int, dict[str, str]] = {
    2:  {"type": "planned_development", "name": "Planned Developments"},
    3:  {"type": "lakefront_protection", "name": "Lakefront Protection District"},
    4:  {"type": "pedestrian_street", "name": "Pedestrian Streets"},
    5:  {"type": "landmark_district", "name": "Landmark District Boundaries"},
    6:  {"type": "historic_district", "name": "Historic Districts"},
    7:  {"type": "landmark_building", "name": "Individual Landmark Buildings"},
    8:  {"type": "national_register", "name": "National Register Districts"},
    9:  {"type": "special_district", "name": "Special Districts"},
    11: {"type": "fema_floodplain", "name": "FEMA Floodplain (Local)"},
    12: {"type": "pmd_subarea", "name": "PMD SubAreas"},
    13: {"type": "tod_cta", "name": "Transit-Oriented Development (CTA)"},
    17: {"type": "adu_area", "name": "ADU Eligible Areas"},
    20: {"type": "aro_zone", "name": "Affordable Requirements Ordinance Zones"},
    23: {"type": "ssa", "name": "Special Service Areas"},
    24: {"type": "tod_metra", "name": "Transit-Oriented Development (Metra)"},
}


async def query_overlay(
    lat: float,
    lon: float,
    layer_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query a single overlay layer at a point.

    Returns the first feature's attributes dict or ``None``.
    """
    url = f"{ZONING_BASE_URL}/{layer_id}/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        return features[0].get("attributes", {})
    except Exception as exc:
        log.warning("Overlay query layer %d failed for (%s, %s): %s", layer_id, lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()


async def query_all_overlays(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[tuple[int, dict]]:
    """Query all overlay layers in parallel.

    Returns a list of ``(layer_id, attributes)`` for layers that returned results.
    """
    key = f"overlays:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return []
    if cached is not None:
        return cached

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        tasks = {
            lid: asyncio.create_task(query_overlay(lat, lon, lid, client=client))
            for lid in OVERLAY_LAYERS
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        hits: list[tuple[int, dict]] = []
        for lid, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                log.warning("Overlay layer %d raised: %s", lid, result)
            elif result is not None:
                hits.append((lid, result))
        _cache.set(key, hits if hits else _NOT_FOUND)
        return hits
    finally:
        if owns:
            await client.aclose()
