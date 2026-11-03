"""Enterprise Zone boundary check via Socrata GeoJSON.

The source is the map's backing dataset (``bwpt-y235``), not the map view ``64xf-pyvh``: since the
City's 2026-02-23 republish the view's GeoJSON returns its 6 features with ``geometry: null`` and no
properties (decision Item 64). A response with no usable polygon raises like any failed source, so
the Profile says "Not checked" instead of "Not in an Enterprise Zone".
"""

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
            if not isinstance(fc, dict) or not isinstance(fc.get("features"), list):
                raise RuntimeError("Enterprise Zone response has no GeoJSON feature list")
        finally:
            if owns:
                await client.aclose()

        boundaries: list[tuple[str, dict, Any, dict]] = []
        for feat in fc.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not geom:
                continue
            try:
                poly = shape(geom)
            except Exception:
                continue
            if poly.is_empty:
                continue
            boundaries.append((_zone_name(props), props, poly, geom))

        if not boundaries:
            # An empty layer is a failed source, never "no zone here"; not cached, so the next call retries.
            raise RuntimeError(
                f"Enterprise Zone response has no usable geometry ({len(fc['features'])} features)"
            )

        _ez_boundaries = boundaries
        log.info("Loaded %d Enterprise Zone boundaries", len(boundaries))
        return _ez_boundaries


def _zone_name(props: dict) -> str:
    """The zone's name; the City's layer names Chicago's six zones by number ("5")."""
    name = props.get("zone_name") or props.get("name") or props.get("ez_name")
    if not name:
        return "Unknown Enterprise Zone"
    name = str(name).strip()
    try:
        number = float(name)
    except ValueError:
        return name
    return f"Chicago Enterprise Zone {int(number)}" if number.is_integer() else name


async def check_enterprise_zone(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a point is within an Enterprise Zone.

    Returns ``{"zone_name": "..."}`` or ``None`` (checked, not in a zone). A boundary-load
    failure raises, so the caller can report the zone as not checked rather than "not in one".
    """
    boundaries = await _load_ez_boundaries(client=client)

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
    """Return a GeoJSON Feature for the Enterprise Zone at a point, or None.

    Boundary-load failures intentionally raise: ``None`` is reserved for a
    successful lookup that found no Enterprise Zone.
    """
    boundaries = await _load_ez_boundaries(client=client)

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
