"""Enterprise Zone boundary check via Socrata GeoJSON."""

import asyncio
import logging
from typing import Any

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings

log = logging.getLogger(__name__)

_ez_boundaries: list[tuple[str, dict, Any, dict]] | None = None
_ez_lock = asyncio.Lock()


async def _load_ez_boundaries(
    *, client: httpx.AsyncClient | None = None,
) -> list[tuple[str, dict, Any, dict]]:
    """Download Enterprise Zone GeoJSON from Socrata and build shapely polygons.

    Returns list of (zone_name, properties_dict, shapely_geometry, geojson_geometry).
    """
    global _ez_boundaries
    async with _ez_lock:
        if _ez_boundaries is not None:
            return _ez_boundaries

        settings = get_settings()
        url = f"{settings.socrata_base}/{settings.dataset_enterprise_zones}.geojson"

        owns = client is None
        if owns:
            client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            fc = resp.json()
        finally:
            if owns:
                await client.aclose()

        boundaries: list[tuple[str, dict, Any, dict]] = []
        for feat in fc.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue
            name = (
                props.get("zone_name")
                or props.get("name")
                or props.get("ez_name")
                or "Unknown Enterprise Zone"
            )
            try:
                poly = shape(geom)
                boundaries.append((name, props, poly, geom))
            except Exception:
                continue

        _ez_boundaries = boundaries
        log.info("Loaded %d Enterprise Zone boundaries", len(boundaries))
        return _ez_boundaries


async def check_enterprise_zone(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a point is within an Enterprise Zone.

    Returns ``{"zone_name": "..."}`` or ``None``.
    """
    try:
        boundaries = await _load_ez_boundaries(client=client)
    except Exception as exc:
        log.warning("Failed to load Enterprise Zone boundaries: %s", exc)
        return None

    point = Point(lon, lat)
    for name, _props, poly, _geom in boundaries:
        if poly.contains(point):
            return {"zone_name": name}
    return None


async def ez_geojson_feature(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Return a GeoJSON Feature for the Enterprise Zone at a point, or None."""
    try:
        boundaries = await _load_ez_boundaries(client=client)
    except Exception as exc:
        log.warning("Failed to load EZ boundaries for geometry: %s", exc)
        return None

    point = Point(lon, lat)
    for name, props, poly, geom in boundaries:
        if poly.contains(point):
            return {
                "type": "Feature",
                "geometry": geom,
                "properties": {"name": name, "zone_type": "enterprise_zone", **props},
            }
    return None


async def preload(*, client: httpx.AsyncClient | None = None) -> None:
    """Pre-warm Enterprise Zone boundary cache at startup."""
    await _load_ez_boundaries(client=client)
