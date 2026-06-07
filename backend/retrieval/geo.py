import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings
from backend.retrieval.cache import TTLCache


log = logging.getLogger(__name__)

_geocoder_client: httpx.AsyncClient | None = None


def _get_geocoder_client() -> httpx.AsyncClient:
    global _geocoder_client
    if _geocoder_client is None or _geocoder_client.is_closed:
        _geocoder_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
    return _geocoder_client


_tract_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="census_tracts")
_geocode_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="geocoded_addresses")
_TRACT_NOT_FOUND = object()

FCC_CENSUS_URL = "https://geo.fcc.gov/api/census/area"

# Official Chicago community areas, integer 1–77.
COMMUNITY_AREAS: dict[int, str] = {
    1: "Rogers Park", 2: "West Ridge", 3: "Uptown", 4: "Lincoln Square",
    5: "North Center", 6: "Lake View", 7: "Lincoln Park", 8: "Near North Side",
    9: "Edison Park", 10: "Norwood Park", 11: "Jefferson Park", 12: "Forest Glen",
    13: "North Park", 14: "Albany Park", 15: "Portage Park", 16: "Irving Park",
    17: "Dunning", 18: "Montclare", 19: "Belmont Cragin", 20: "Hermosa",
    21: "Avondale", 22: "Logan Square", 23: "Humboldt Park", 24: "West Town",
    25: "Austin", 26: "West Garfield Park", 27: "East Garfield Park",
    28: "Near West Side", 29: "North Lawndale", 30: "South Lawndale",
    31: "Lower West Side", 32: "Loop", 33: "Near South Side", 34: "Armour Square",
    35: "Douglas", 36: "Oakland", 37: "Fuller Park", 38: "Grand Boulevard",
    39: "Kenwood", 40: "Washington Park", 41: "Hyde Park", 42: "Woodlawn",
    43: "South Shore", 44: "Chatham", 45: "Avalon Park", 46: "South Chicago",
    47: "Burnside", 48: "Calumet Heights", 49: "Roseland", 50: "Pullman",
    51: "South Deering", 52: "East Side", 53: "West Pullman", 54: "Riverdale",
    55: "Hegewisch", 56: "Garfield Ridge", 57: "Archer Heights",
    58: "Brighton Park", 59: "McKinley Park", 60: "Bridgeport",
    61: "New City", 62: "West Elsdon", 63: "Gage Park", 64: "Clearing",
    65: "West Lawn", 66: "Chicago Lawn", 67: "West Englewood", 68: "Englewood",
    69: "Greater Grand Crossing", 70: "Ashburn", 71: "Auburn Gresham",
    72: "Beverly", 73: "Washington Heights", 74: "Mount Greenwood",
    75: "Morgan Park", 76: "O'Hare", 77: "Edgewater",
}

NEIGHBORHOOD_ALIASES: dict[str, int] = {
    "wicker park": 24,
    "ukrainian village": 24,
    "noble square": 24,
    "river west": 24,
    "east village": 24,
    "bucktown": 22,
    "old town": 8,
    "river north": 8,
    "gold coast": 8,
    "streeterville": 8,
    "andersonville": 77,
    "boystown": 6,
    "wrigleyville": 6,
    "lakeview east": 6,
    "north center": 5,
    "roscoe village": 5,
    "ravenswood": 4,
    "the loop": 32,
    "downtown": 32,
    "south loop": 33,
    "west loop": 28,
    "fulton market": 28,
    "ukrainian-village": 24,
    "pilsen": 31,
    "little italy": 28,
    "bronzeville": 35,
    "kenwood": 39,
    "chinatown": 34,
}


@lru_cache
def _polygon_index() -> list[tuple[int, str, Any]]:
    settings = get_settings()
    path = settings.data_dir / "community_areas.geojson"
    if not path.exists():
        log.warning("Community-area polygons missing at %s — run ingestion.load_community_areas", path)
        return []
    fc = json.loads(path.read_text())
    out: list[tuple[int, str, Any]] = []
    for feat in fc["features"]:
        ca = int(feat["properties"]["community_area"])
        name = feat["properties"]["name"]
        out.append((ca, name, shape(feat["geometry"])))
    return out


def community_area_by_name(query: str) -> int | None:
    """Resolve a neighborhood name or community-area name to its integer id."""
    if not query:
        return None
    q = query.strip().lower()
    if q in NEIGHBORHOOD_ALIASES:
        return NEIGHBORHOOD_ALIASES[q]
    for ca, name in COMMUNITY_AREAS.items():
        if name.lower() == q:
            return ca
    for ca, name in COMMUNITY_AREAS.items():
        if q in name.lower() or name.lower() in q:
            return ca
    return None


def community_area_by_point(lat: float, lon: float) -> int | None:
    point = Point(lon, lat)
    for ca, _name, poly in _polygon_index():
        if poly.contains(point):
            return ca
    return None


def community_area_name(ca: int) -> str | None:
    """Return the community area name for a given integer id."""
    for ca_id, name, _poly in _polygon_index():
        if ca_id == ca:
            return name
    return None


def community_area_bounds(ca: int) -> tuple[float, float, float, float] | None:
    """Return bounding box (min_lat, min_lon, max_lat, max_lon) for a community area."""
    for ca_id, _name, poly in _polygon_index():
        if ca_id == ca:
            minx, miny, maxx, maxy = poly.bounds
            return (miny, minx, maxy, maxx)
    return None


async def geocode_address(
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[float, float] | None:
    """Use the free Census Geocoder to resolve a Chicago address to lat/lon."""
    normalized = address.strip().lower()
    cached = _geocode_cache.get(normalized)
    if cached is not None:
        return cached if cached != _TRACT_NOT_FOUND else None

    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": f"{address}, Chicago, IL",
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    if client is None:
        client = _get_geocoder_client()
    for attempt in range(2):
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            matches = data.get("result", {}).get("addressMatches") or []
            if not matches:
                _geocode_cache.set(normalized, _TRACT_NOT_FOUND)
                return None
            coords = matches[0]["coordinates"]
            result = float(coords["y"]), float(coords["x"])
            _geocode_cache.set(normalized, result)
            return result
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt == 0:
                log.warning("Geocoder attempt 1 failed for %s: %s, retrying", address, exc)
                continue
            log.warning("Geocoder failed after retry for %s: %s", address, exc)
            return None


async def resolve_address_to_community_area(
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[int | None, tuple[float, float] | None]:
    coords = await geocode_address(address, client=client)
    if not coords:
        return None, None
    return community_area_by_point(*coords), coords


async def geocode_address_suggestions(
    partial: str,
    *,
    limit: int = 5,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Return address suggestions from Census Geocoder.

    Returns list of {address, lat, lon} dicts.
    """
    if not partial or len(partial.strip()) < 3:
        return []

    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": f"{partial}, Chicago, IL",
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    if client is None:
        client = _get_geocoder_client()
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        matches = data.get("result", {}).get("addressMatches") or []
        results = []
        for match in matches[:limit]:
            coords = match.get("coordinates", {})
            results.append({
                "address": match.get("matchedAddress", ""),
                "lat": float(coords.get("y", 0)),
                "lon": float(coords.get("x", 0)),
            })
        return results
    except Exception as exc:
        log.warning("Geocode suggestions failed: %s", exc)
        return []


async def resolve_census_tract(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Resolve lat/lon to an 11-character census tract FIPS code via the FCC API."""
    key = f"tract:{round(lat, 5)}:{round(lon, 5)}"
    cached = _tract_cache.get(key)
    if cached is _TRACT_NOT_FOUND:
        return None
    if cached is not None:
        return cached

    if client is None:
        client = _get_geocoder_client()
    try:
        resp = await client.get(
            FCC_CENSUS_URL,
            params={"lat": str(lat), "lon": str(lon), "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            _tract_cache.set(key, _TRACT_NOT_FOUND)
            return None
        fips = results[0].get("block_fips", "")
        if len(fips) >= 11:
            result = fips[:11]
            _tract_cache.set(key, result)
            return result
        _tract_cache.set(key, _TRACT_NOT_FOUND)
        return None
    except Exception as exc:
        log.warning("FCC census tract resolution failed for (%s, %s): %s", lat, lon, exc)
        return None
