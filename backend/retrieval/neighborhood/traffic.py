"""Street traffic volume near a point — Chicago traffic counts ``gc7y-n4xa``.

A LIVE daily dataset (one row per road segment per day, both directions as
separate segments). Retail/CRE context: "the fronting street carries ~N
vehicles/day". Method:

1. Pull the last 7 days of segments whose midpoint is within 250 m.
2. Average each segment's daily counts (weekday/weekend smoothing).
3. The nearest segment picks the road; per direction on that road, keep only
   the segment nearest to the subject (consecutive block segments of the same
   direction would double-count); sum directions → daily vehicles.
"""

from __future__ import annotations

import datetime
import logging
import math

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=43200, maxsize=512, name="traffic_counts")
_NOT_FOUND = object()

DATASET_TRAFFIC_COUNTS = "gc7y-n4xa"
RADIUS_M = 250
WINDOW_DAYS = 7


def _f(val) -> float | None:
    try:
        n = float(val)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _dist_sq(mid: tuple[float, float] | None, lat: float, lon: float) -> float:
    if mid is None:
        return float("inf")
    dlon = (mid[1] - lon) * math.cos(math.radians(lat))
    return (mid[0] - lat) ** 2 + dlon**2


async def get_traffic_context(
    lat: float, lon: float, *, client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Daily traffic on the nearest counted street, or None (most side streets
    aren't counted — an expected absence, not a gap)."""
    key = f"{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    since = (datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS + 1)).isoformat()
    # NOT within_circle: this dataset stores its point columns as [lat, lon]
    # (swapped vs GeoJSON), so spatial functions silently match nothing
    # (verified live 2026-07-02). Numeric bbox on midpointlat/midpointlon.
    dlat = RADIUS_M / 111_320
    dlon = RADIUS_M / (111_320 * math.cos(math.radians(lat)))
    try:
        rows = await socrata_get(
            DATASET_TRAFFIC_COUNTS,
            {
                "$where": (
                    f"midpointlat between {lat - dlat} and {lat + dlat} "
                    f"AND midpointlon between {lon - dlon} and {lon + dlon} "
                    f"AND timestamp >= '{since}'"
                ),
                "$select": ("segmentid,roadname,direction,fromsegment,tosegment,"
                            "vehiclecount,midpointlat,midpointlon,timestamp"),
                "$limit": 2000,
            },
            client=client,
            base_url=settings.socrata_base,
            app_token=settings.socrata_app_token or None,
        )
    except Exception as exc:
        log.warning("Traffic counts lookup failed at (%s, %s): %s", lat, lon, exc)
        return None

    # Aggregate per segment: mean daily count + metadata.
    segments: dict[str, dict] = {}
    for row in rows or []:
        sid = row.get("segmentid")
        count = _f(row.get("vehiclecount"))
        if not sid or count is None:
            continue
        seg = segments.setdefault(sid, {
            "counts": [], "roadname": row.get("roadname"),
            "direction": row.get("direction"),
            "fromsegment": row.get("fromsegment"), "tosegment": row.get("tosegment"),
            "mid": ((_f(row.get("midpointlat")), _f(row.get("midpointlon")))
                    if _f(row.get("midpointlat")) is not None else None),
            "as_of": "",
        })
        seg["counts"].append(count)
        ts = str(row.get("timestamp") or "")[:10]
        if ts > seg["as_of"]:
            seg["as_of"] = ts

    if not segments:
        _cache.set(key, _NOT_FOUND)
        return None

    nearest = min(segments.values(), key=lambda s: _dist_sq(s["mid"], lat, lon))
    road = nearest["roadname"]
    # One segment per direction on the fronting road — the one nearest to us.
    by_direction: dict[str, dict] = {}
    for seg in segments.values():
        if seg["roadname"] != road:
            continue
        d = seg["direction"] or "?"
        cur = by_direction.get(d)
        if cur is None or _dist_sq(seg["mid"], lat, lon) < _dist_sq(cur["mid"], lat, lon):
            by_direction[d] = seg

    daily = sum(sum(s["counts"]) / len(s["counts"]) for s in by_direction.values())
    result = {
        "road": road,
        "daily_vehicles": int(round(daily)),
        "directions": len(by_direction),
        "from_street": nearest.get("fromsegment"),
        "to_street": nearest.get("tosegment"),
        "as_of": max((s["as_of"] for s in by_direction.values()), default=None) or None,
    }
    _cache.set(key, result)
    return result
