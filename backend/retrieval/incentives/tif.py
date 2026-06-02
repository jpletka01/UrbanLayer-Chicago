"""TIF district boundary check and financial data retrieval."""

import asyncio
import logging
from typing import Any

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_tif_boundaries: list[tuple[str, dict, Any, dict]] | None = None
_tif_lock = asyncio.Lock()


async def _load_tif_boundaries(
    *, client: httpx.AsyncClient | None = None,
) -> list[tuple[str, dict, Any, dict]]:
    """Download TIF district GeoJSON from Socrata and build shapely polygons.

    Returns list of (tif_name, properties_dict, shapely_geometry, geojson_geometry).
    Cached in module-level variable after first load.
    """
    global _tif_boundaries
    async with _tif_lock:
        if _tif_boundaries is not None:
            return _tif_boundaries

        settings = get_settings()
        url = f"{settings.socrata_base}/{settings.dataset_tif_boundaries}.geojson"

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
            name = props.get("tif_name") or props.get("name") or "Unknown TIF"
            try:
                poly = shape(geom)
                boundaries.append((name, props, poly, geom))
            except Exception:
                continue

        _tif_boundaries = boundaries
        log.info("Loaded %d TIF district boundaries", len(boundaries))
        return _tif_boundaries


async def check_tif(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a point is within a TIF district.

    Returns ``{"tif_name": "...", "properties": {...}}`` or ``None``.
    """
    try:
        boundaries = await _load_tif_boundaries(client=client)
    except Exception as exc:
        log.warning("Failed to load TIF boundaries: %s", exc)
        return None

    point = Point(lon, lat)
    for name, props, poly, _geom in boundaries:
        if props.get("repealed_d"):
            continue
        if poly.contains(point):
            return {"tif_name": name, "properties": props}
    return None


async def tif_geojson_feature(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Return a GeoJSON Feature for the TIF district at a point, or None."""
    try:
        boundaries = await _load_tif_boundaries(client=client)
    except Exception as exc:
        log.warning("Failed to load TIF boundaries for geometry: %s", exc)
        return None

    point = Point(lon, lat)
    for name, props, poly, geom in boundaries:
        if props.get("repealed_d"):
            continue
        if poly.contains(point):
            return {
                "type": "Feature",
                "geometry": geom,
                "properties": {"name": name, "zone_type": "tif", **props},
            }
    return None


def _parse_year(dt_str: str | None) -> int | None:
    if not dt_str:
        return None
    try:
        return int(dt_str[:4])
    except (ValueError, IndexError):
        return None


async def _active_tif_boundaries_for_ca(
    ca: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[tuple[str, dict, Any, dict]]:
    """Return boundary tuples for all active TIF districts overlapping a community area."""
    try:
        boundaries = await _load_tif_boundaries(client=client)
    except Exception as exc:
        log.warning("Failed to load TIF boundaries for CA lookup: %s", exc)
        return []

    ca_str = str(ca)
    hits: list[tuple[str, dict, Any, dict]] = []
    for name, props, poly, geom in boundaries:
        if props.get("repealed_d"):
            continue
        comm_areas = [c.strip() for c in (props.get("comm_area") or "").split(",")]
        if ca_str in comm_areas:
            hits.append((name, props, poly, geom))
    return hits


async def tif_districts_by_community_area(
    ca: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Return all active (non-repealed) TIF districts overlapping a community area."""
    hits = await _active_tif_boundaries_for_ca(ca, client=client)
    return [
        {
            "tif_name": name,
            "start_year": _parse_year(props.get("approval_d")),
            "end_year": _parse_year(props.get("expiration")),
            "type": props.get("type"),
            "tif_ref": props.get("ref"),
        }
        for name, props, _poly, _geom in hits
    ]


async def tif_geojson_by_community_area(
    ca: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Return GeoJSON Features for all active TIF districts in a community area."""
    hits = await _active_tif_boundaries_for_ca(ca, client=client)
    return [
        {
            "type": "Feature",
            "geometry": geom,
            "properties": {"name": name, "zone_type": "tif", **props},
        }
        for name, props, _poly, geom in hits
    ]


async def fetch_tif_fund_analysis(
    tif_name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch district-level annual fund analysis (revenue, expenditure, balance)."""
    settings = get_settings()
    params = {
        "$where": f"tif_district='{tif_name.replace(chr(39), chr(39)*2)}'",
        "$order": "report_year DESC",
        "$limit": settings.limit_tif_fund_analysis,
    }
    try:
        return await socrata_get(
            settings.dataset_tif_fund_analysis,
            params,
            client=client,
        )
    except Exception as exc:
        log.warning("TIF fund analysis query failed for %r: %s", tif_name, exc)
        return []


async def fetch_tif_financials(
    tif_name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch TIF financial project reports by district name."""
    settings = get_settings()
    params = {
        "$where": f"tif_district='{tif_name.replace(chr(39), chr(39)*2)}'",
        "$order": "report_year DESC",
        "$limit": settings.limit_tif_financials,
    }
    try:
        return await socrata_get(
            settings.dataset_tif_financials,
            params,
            client=client,
        )
    except Exception as exc:
        log.warning("TIF financials query failed for %r: %s", tif_name, exc)
        return []


async def preload(*, client: httpx.AsyncClient | None = None) -> None:
    """Pre-warm TIF boundary cache at startup."""
    await _load_tif_boundaries(client=client)
