"""Divvy bike-share proximity.

Divvy Bicycle Stations ``bbyy-e7gq`` (city portal, ~1,205 stations): station name,
dock counts, and in-service status with point geometry.

Queried live rather than baked into a committed artifact like `transit_stations.json`.
Two reasons: the station list churns (docks are added, moved, and taken out of service
in a way CTA rail stops do not), and a committed artifact needs the .gitignore +
.dockerignore + Dockerfile COPY trio that has silently broken a deploy twice. The
dataset is small and the query is a cheap `within_circle`, so a day-long TTL is plenty.

Only IN-SERVICE stations count. A station row that exists but is out of service is not
an amenity you can actually use, and counting it would overstate access.
"""

from __future__ import annotations

import logging

import httpx

from backend.config import get_settings
from backend.models import DivvyAccess
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=512, name="divvy")

DATASET_DIVVY = "bbyy-e7gq"

# Walking distance. A rack 15 minutes away is not a selling point; ~0.5 mi is the
# radius the transit card already uses for "walkable".
SEARCH_RADIUS_MI = 0.5
_MI_TO_M = 1609.34


def _f(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _i(val) -> int | None:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


async def find_nearest_divvy(
    lat: float,
    lon: float,
    *,
    radius_mi: float = SEARCH_RADIUS_MI,
    client: httpx.AsyncClient | None = None,
) -> DivvyAccess | None:
    """Nearest in-service Divvy station and how many are within the radius.

    Returns None when there is nothing within the radius — the caller renders no
    chip rather than an empty one.
    """
    key = f"divvy:{lat:.5f},{lon:.5f},{radius_mi}"
    cached = _cache.get(key)
    if cached is not None:
        return cached or None  # falsy sentinel = known-empty

    settings = get_settings()
    meters = radius_mi * _MI_TO_M
    try:
        rows = await socrata_get(
            DATASET_DIVVY,
            {
                # distance_in_meters lets Socrata do the ordering, so the nearest
                # station is row 0 and we never sort a truncated window client-side.
                "$select": (
                    "station_name,total_docks,docks_in_service,status,latitude,longitude,"
                    f"distance_in_meters(location, 'POINT({lon} {lat})') AS dist_m"
                ),
                "$where": (
                    f"within_circle(location, {lat}, {lon}, {meters})"
                    " AND status='In Service'"
                ),
                "$order": "dist_m ASC",
                # stations_within_radius is len(rows), so it SATURATES at this limit.
                # Densest measured half-mile as of 2026-09-07: Lakeview 28, Loop 24 --
                # comfortable headroom, but raise this before trusting the count if the
                # system expands. The nearest station is unaffected either way ($order
                # is applied server-side, so row 0 is correct regardless of the cap).
                "$limit": 50,
            },
            client=client,
            base_url=settings.socrata_base,
            app_token=settings.socrata_app_token or None,
        )
    except Exception as exc:
        log.warning("Divvy lookup failed for %s,%s: %s", lat, lon, exc)
        return None

    if not rows:
        _cache.set(key, False)
        return None

    nearest = rows[0]
    dist_m = _f(nearest.get("dist_m"))
    access = DivvyAccess(
        nearest_station=(nearest.get("station_name") or "").strip() or None,
        distance_mi=round(dist_m / _MI_TO_M, 2) if dist_m is not None else None,
        docks=_i(nearest.get("docks_in_service")) or _i(nearest.get("total_docks")),
        stations_within_radius=len(rows),
        radius_mi=radius_mi,
    )
    _cache.set(key, access)
    return access
