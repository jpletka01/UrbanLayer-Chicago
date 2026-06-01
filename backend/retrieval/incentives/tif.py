"""TIF district boundary check and financial data retrieval."""

import asyncio
import logging
from typing import Any

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_tif_boundaries: list[tuple[str, dict, Any]] | None = None
_tif_lock = asyncio.Lock()


async def _load_tif_boundaries(
    *, client: httpx.AsyncClient | None = None,
) -> list[tuple[str, dict, Any]]:
    """Download TIF district GeoJSON from Socrata and build shapely polygons.

    Returns list of (tif_name, properties_dict, shapely_geometry).
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

        boundaries: list[tuple[str, dict, Any]] = []
        for feat in fc.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue
            name = props.get("tif_name") or props.get("name") or "Unknown TIF"
            try:
                poly = shape(geom)
                boundaries.append((name, props, poly))
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
    for name, props, poly in boundaries:
        if poly.contains(point):
            return {"tif_name": name, "properties": props}
    return None


async def fetch_tif_financials(
    tif_name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch TIF financial reports by district name (last N years)."""
    settings = get_settings()
    params = {
        "$where": f"tif_name='{tif_name.replace(chr(39), chr(39)*2)}'",
        "$order": "year DESC",
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
