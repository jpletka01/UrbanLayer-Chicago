"""Parcel geometry + land area from the local PTAXSIM database.

PTAXSIM ships a ``pin_geometry_raw`` table (WKT polygon per PIN10, PRIMARY KEY
``(pin10, start_year)`` — indexed, ~ms lookups) alongside the tax data. That
makes it the only land-area source that covers EVERY property class locally:
CCAO characteristics (x54s-btds) is residential-only and the Cook County GIS
parcel layer is intermittently down. The 2026-07-02 lot-coverage benchmark
measured land_sqft at 21% (0% outside residential) — this module is the fill.

Area is computed from the polygon with a local equirectangular scaling
(longitude scaled by cos(latitude)) — within ~0.1% of a true projection at
parcel scale, and avoids adding a pyproj dependency.
"""

from __future__ import annotations

import asyncio
import logging
import math

import aiosqlite

from backend.config import get_settings
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_conn: aiosqlite.Connection | None = None
_lock = asyncio.Lock()

# Parcel boundaries are near-static; cache aggressively.
_cache = TTLCache(ttl_seconds=6 * 3600, maxsize=2048, name="parcel_geometry")
_NOT_FOUND = object()

_M_PER_DEG_LAT = 111_132.95
_M_PER_DEG_LON_EQ = 111_319.49
_SQFT_PER_SQM = 10.763910


async def _get_conn() -> aiosqlite.Connection:
    global _conn
    async with _lock:
        if _conn is None:
            settings = get_settings()
            # Read-only: this module must never contend with tax_estimate's
            # connection or accidentally write the 9.4 GB artifact.
            _conn = await aiosqlite.connect(
                f"file:{settings.ptaxsim_db_path}?mode=ro", uri=True
            )
            _conn.row_factory = aiosqlite.Row
        return _conn


async def close() -> None:
    global _conn
    async with _lock:
        if _conn is not None:
            await _conn.close()
            _conn = None


def _polygon_area_sqft(wkt: str) -> tuple[float, dict] | None:
    """Parse WKT, return (area_sqft, geojson_mapping) or None on parse failure."""
    try:
        from shapely import wkt as shapely_wkt
        from shapely.geometry import mapping
        from shapely.ops import transform

        geom = shapely_wkt.loads(wkt)
        if geom.is_empty:
            return None
        lat0 = geom.centroid.y
        mx = _M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
        scaled = transform(lambda x, y, z=None: (x * mx, y * _M_PER_DEG_LAT), geom)
        area_sqft = scaled.area * _SQFT_PER_SQM
        if area_sqft <= 0:
            return None
        return area_sqft, mapping(geom)
    except Exception as exc:  # noqa: BLE001 — malformed WKT is a data problem, not an outage
        log.warning("Parcel WKT parse failed: %s", exc)
        return None


async def get_parcel_geometry_facts(pin14: str) -> dict | None:
    """Return {"land_sqft_geom": int, "parcel_geometry": geojson, "geom_year": int}
    for the parcel's most recent boundary, or None (disabled/missing/not found).
    """
    settings = get_settings()
    if not settings.ptaxsim_enabled or not settings.ptaxsim_db_path.exists():
        return None

    pin10 = pin14.replace("-", "").zfill(14)[:10]
    cached = _cache.get(pin10)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    try:
        conn = await _get_conn()
        async with conn.execute(
            "SELECT geometry, end_year FROM pin_geometry_raw "
            "WHERE pin10 = ? AND geometry IS NOT NULL "
            "ORDER BY end_year DESC LIMIT 1",
            (pin10,),
        ) as cursor:
            row = await cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("pin_geometry lookup failed for %s: %s", pin10, exc)
        return None

    if not row:
        _cache.set(pin10, _NOT_FOUND)
        return None

    parsed = _polygon_area_sqft(row["geometry"])
    if parsed is None:
        _cache.set(pin10, _NOT_FOUND)
        return None

    area_sqft, geojson = parsed
    result = {
        "land_sqft_geom": int(round(area_sqft)),
        "parcel_geometry": geojson,
        "geom_year": row["end_year"],
    }
    _cache.set(pin10, result)
    return result
