"""Query Chicago Zoning MapServer overlay layers (2-24).

All layers share the same ArcGIS REST endpoint with a variable layer ID.
This generalizes the point-query pattern from ``zoning.py`` (layer 1).
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_arcgis_client: httpx.AsyncClient | None = None


def _get_arcgis_client() -> httpx.AsyncClient:
    global _arcgis_client
    if _arcgis_client is None or _arcgis_client.is_closed:
        _arcgis_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=15, max_keepalive_connections=10),
        )
    return _arcgis_client


_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="overlays")
_geojson_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="overlay_geojson")


class OverlayLayerError(Exception):
    """A layer couldn't be checked: HTTP error, timeout, or a 200 body carrying ``error``.

    Distinct from "no feature here". ArcGIS answers a missing or renumbered layer with
    HTTP 200 + ``{"error": {"code": 404, ...}}``, which used to read as "not in it".
    """


@dataclass
class OverlayResults:
    """Every layer is a hit, clear (absent from both lists), or failed."""

    hits: list[tuple[int, dict]] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)


def _faulted_layers() -> set[int]:
    """Layers forced to fail via ``DATA_HEALTH_FAULT=overlay:5[,6]`` (never in production)."""
    spec = os.environ.get("DATA_HEALTH_FAULT", "")
    if not spec.startswith("overlay:"):
        return set()
    from backend.config import get_settings
    if get_settings().environment == "production":
        return set()
    return {int(x) for x in spec.split(":", 1)[1].split(",") if x.strip().isdigit()}

ZONING_BASE_URL = (
    "https://gisapps.chicago.gov/arcgis/rest/services"
    "/ExternalApps/Zoning/MapServer"
)

OVERLAY_LAYERS: dict[int, dict[str, str]] = {
    2:  {"type": "planned_development", "name": "Planned Developments"},
    3:  {"type": "lakefront_protection", "name": "Lakefront Protection District"},
    4:  {"type": "pedestrian_street", "name": "Pedestrian Streets"},
    # Layer 5 ("Landmark Boundaries") is the designated Chicago Landmarks: it hit 59 of 60 buildings on
    # the City's official landmark list (data portal tdab-kixi). Layer 6 is the landmark/historic
    # districts. Layer 7 ("Landmark Buildings") is NOT designations: it is the Chicago Historic
    # Resources Survey's 9,298 orange/red-rated buildings (9,108 with no designation date) and hit
    # only 39 of those 60, so it is deliberately not queried. The survey rating is read from
    # property/chrs.py, which carries the right rule (a demolition delay, not Commission approval).
    5:  {"type": "landmark_building", "name": "Chicago Landmarks"},
    6:  {"type": "historic_district", "name": "Historic Districts"},
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


async def query_overlay_checked(
    lat: float,
    lon: float,
    layer_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query a single overlay layer at a point, retrying once.

    Returns the first feature's attributes dict, or ``None`` when the point is in no
    feature. Raises :class:`OverlayLayerError` when the layer couldn't be checked.
    """
    if layer_id in _faulted_layers():
        raise OverlayLayerError(f"layer {layer_id}: forced by DATA_HEALTH_FAULT")
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
    if client is None:
        client = _get_arcgis_client()
    last_exc: Exception | None = None
    for _attempt in range(2):
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or data.get("error"):
                raise OverlayLayerError(f"layer {layer_id}: {data.get('error') if isinstance(data, dict) else data!r}")
            features = data.get("features")
            if features is None:
                raise OverlayLayerError(f"layer {layer_id}: no 'features' in response")
            if not features:
                return None
            return features[0].get("attributes", {})
        except Exception as exc:
            last_exc = exc
    log.warning("Overlay query layer %d failed for (%s, %s): %s", layer_id, lat, lon, last_exc)
    raise OverlayLayerError(str(last_exc)) from last_exc


async def query_overlay(
    lat: float,
    lon: float,
    layer_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Like :func:`query_overlay_checked`, but a failed layer returns ``None``.

    Only for callers that treat a miss as "unknown" anyway; anything that states
    "not in this overlay" must use the checked form.
    """
    try:
        return await query_overlay_checked(lat, lon, layer_id, client=client)
    except OverlayLayerError:
        return None


async def query_overlay_with_geometry(
    lat: float,
    lon: float,
    layer_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query a single overlay layer at a point, returning GeoJSON with geometry."""
    url = f"{ZONING_BASE_URL}/{layer_id}/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    if client is None:
        client = _get_arcgis_client()
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        return features[0]
    except Exception as exc:
        log.warning("Overlay geometry query layer %d failed for (%s, %s): %s", layer_id, lat, lon, exc)
        return None


async def overlay_geojson_features(
    lat: float,
    lon: float,
    layer_ids: list[int],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch GeoJSON features with geometry for specific overlay layers.

    Returns a GeoJSON FeatureCollection with overlay metadata injected
    into each feature's properties.
    """
    if not layer_ids:
        return {"type": "FeatureCollection", "features": []}

    key = f"overlay_geo:{round(lat, 5)}:{round(lon, 5)}"
    cached = _geojson_cache.get(key)
    if cached is not None:
        return cached

    if client is None:
        client = _get_arcgis_client()

    coros = [
        query_overlay_with_geometry(lat, lon, lid, client=client)
        for lid in layer_ids
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)

    features = []
    for lid, result in zip(layer_ids, results):
        if isinstance(result, Exception) or result is None:
            continue
        meta = OVERLAY_LAYERS.get(lid, {})
        props = result.get("properties", {})
        props["overlay_type"] = meta.get("type", f"layer_{lid}")
        props["overlay_name"] = meta.get("name", f"Layer {lid}")
        result["properties"] = props
        features.append(result)

    fc = {"type": "FeatureCollection", "features": features}
    _geojson_cache.set(key, fc)
    return fc


async def query_overlays_checked(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> OverlayResults:
    """Query all overlay layers in parallel, keeping failed layers apart from clear ones.

    Only a result with no failed layer is cached: a failure must never be served
    for an hour as "not in that overlay".
    """
    key = f"overlays:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    if client is None:
        client = _get_arcgis_client()

    tasks = {
        lid: asyncio.create_task(query_overlay_checked(lat, lon, lid, client=client))
        for lid in OVERLAY_LAYERS
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    out = OverlayResults()
    for lid, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            if not isinstance(result, OverlayLayerError):
                log.warning("Overlay layer %d raised: %s", lid, result)
            out.failed.append(lid)
        elif result is not None:
            out.hits.append((lid, result))
    if not out.failed:
        _cache.set(key, out)
    return out


async def query_all_overlays(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[tuple[int, dict]]:
    """The hits from :func:`query_overlays_checked` (map highlighting only)."""
    return (await query_overlays_checked(lat, lon, client=client)).hits
