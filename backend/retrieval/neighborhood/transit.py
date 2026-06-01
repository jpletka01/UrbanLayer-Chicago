"""Transit proximity: nearest stations and TOD eligibility."""

import asyncio
import json
import logging
import math

import httpx

from backend.config import get_settings
from backend.models import TransitAccess
from backend.retrieval.cache import TTLCache
from backend.retrieval.regulatory.overlays import query_overlay

log = logging.getLogger(__name__)

_tod_cache = TTLCache(ttl_seconds=3600, maxsize=256)

_stations: list[dict] | None = None
_stations_lock = asyncio.Lock()

TOD_CTA_LAYER = 13
TOD_METRA_LAYER = 24


async def _load_stations() -> list[dict]:
    global _stations
    async with _stations_lock:
        if _stations is not None:
            return _stations
        path = get_settings().data_dir / "transit_stations.json"
        try:
            _stations = json.loads(path.read_text())
        except Exception:
            log.warning("Failed to load transit stations from %s", path, exc_info=True)
            _stations = []
        return _stations


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


async def find_nearest_stations(
    lat: float,
    lon: float,
    *,
    radius_mi: float | None = None,
) -> dict:
    if radius_mi is None:
        radius_mi = get_settings().transit_search_radius_mi
    stations = await _load_stations()

    nearest_cta: dict | None = None
    nearest_metra: dict | None = None
    best_cta_dist = float("inf")
    best_metra_dist = float("inf")

    for s in stations:
        dist = _haversine_mi(lat, lon, s["lat"], s["lon"])
        if dist > radius_mi:
            continue
        if s["type"] == "cta_rail" and dist < best_cta_dist:
            best_cta_dist = dist
            nearest_cta = {**s, "distance_mi": round(dist, 2)}
        elif s["type"] == "metra" and dist < best_metra_dist:
            best_metra_dist = dist
            nearest_metra = {**s, "distance_mi": round(dist, 2)}

    return {"nearest_cta_rail": nearest_cta, "nearest_metra": nearest_metra}


async def check_tod_eligibility(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    key = f"tod:{round(lat, 5)}:{round(lon, 5)}"
    cached = _tod_cache.get(key)
    if cached is not None:
        return cached

    results = await asyncio.gather(
        query_overlay(lat, lon, TOD_CTA_LAYER, client=client),
        query_overlay(lat, lon, TOD_METRA_LAYER, client=client),
        return_exceptions=True,
    )
    cta_tod = results[0] if not isinstance(results[0], Exception) else None
    metra_tod = results[1] if not isinstance(results[1], Exception) else None

    if isinstance(results[0], Exception):
        log.warning("TOD CTA layer query failed: %s", results[0])
    if isinstance(results[1], Exception):
        log.warning("TOD Metra layer query failed: %s", results[1])

    if cta_tod:
        result = {"tod_eligible": True, "tod_type": "CTA rail"}
    elif metra_tod:
        result = {"tod_eligible": True, "tod_type": "Metra"}
    else:
        result = {"tod_eligible": False, "tod_type": None}
    _tod_cache.set(key, result)
    return result


async def preload() -> None:
    """Pre-warm transit station cache at startup."""
    await _load_stations()


def build_transit_access(
    station_result: dict | None,
    tod_result: dict | None,
) -> TransitAccess | None:
    if station_result is None and tod_result is None:
        return None

    cta = (station_result or {}).get("nearest_cta_rail")
    metra = (station_result or {}).get("nearest_metra")
    tod = tod_result or {}

    return TransitAccess(
        nearest_cta_rail=cta["name"] if cta else None,
        cta_rail_distance_mi=cta["distance_mi"] if cta else None,
        cta_lines=cta.get("lines", []) if cta else [],
        nearest_metra=metra["name"] if metra else None,
        metra_distance_mi=metra["distance_mi"] if metra else None,
        metra_line=metra.get("line") if metra else None,
        tod_eligible=tod.get("tod_eligible", False),
        tod_type=tod.get("tod_type"),
    )
