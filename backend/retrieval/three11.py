from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import grouped_count, socrata_get
from backend.retrieval.utils import cutoff_iso

_cache = TTLCache(ttl_seconds=900, maxsize=256, name="311")


async def open_311_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"311:{community_area}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    result = await grouped_count(
        settings.dataset_311,
        where=(
            f"community_area='{community_area}' "
            "AND status='Open' "
            "AND sr_type!='Open - Dup'"
        ),
        group="owner_department,sr_type",
        select="owner_department,sr_type",
        limit=settings.limit_311,
        client=client,
    )
    _cache.set(key, result)
    return result


async def open_311_oldest(
    community_area: int,
    *,
    limit: int = 1,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = f"311_oldest:{community_area}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND status='Open' "
            "AND sr_type!='Open - Dup'"
        ),
        "$select": "sr_number,sr_type,created_date",
        "$order": "created_date ASC",
        "$limit": limit,
    }
    result = await socrata_get(settings.dataset_311, params, client=client)
    _cache.set(key, result)
    return result


_HIGH_RISK_TYPES = {
    "No Heat", "Rodent Baiting/Rat Complaint", "Water in Basement",
    "Building Dangerous/Hazardous Complaint", "Building Collapse Risk",
    "Water Quality", "No Water", "Fire Safety Inspection Request",
}

_address_cache = TTLCache(ttl_seconds=900, maxsize=256, name="311_address")


async def address_311_complaints(
    lat: float,
    lon: float,
    *,
    days: int = 365,
    limit: int = 50,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """311 complaints within ~50m of an address over the past year."""
    key = f"311_addr:{round(lat, 5)}:{round(lon, 5)}:{days}"
    cached = _address_cache.get(key)
    if cached is not None:
        return cached

    delta = 0.00045
    settings = get_settings()
    cutoff = cutoff_iso(days)
    params = {
        "$where": (
            f"latitude between '{lat - delta}' and '{lat + delta}' "
            f"AND longitude between '{lon - delta}' and '{lon + delta}' "
            f"AND created_date > '{cutoff}' "
            "AND sr_type!='Open - Dup'"
        ),
        "$select": "sr_type,status,created_date",
        "$order": "created_date DESC",
        "$limit": limit,
    }
    rows = await socrata_get(settings.dataset_311, params, client=client)

    by_type: dict[str, int] = {}
    high_risk: list[str] = []
    open_count = 0
    for row in rows:
        sr = row.get("sr_type", "UNKNOWN")
        by_type[sr] = by_type.get(sr, 0) + 1
        if row.get("status") == "Open":
            open_count += 1
        if sr in _HIGH_RISK_TYPES and sr not in high_risk:
            high_risk.append(sr)

    result: dict[str, Any] = {
        "total": len(rows),
        "open_count": open_count,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)[:10]),
        "high_risk_flags": high_risk,
        "recent": rows[:5],
    }
    _address_cache.set(key, result)
    return result


async def response_times_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND status='Closed' "
            f"AND created_date > '{cutoff_iso(days)}'"
        ),
        "$select": "sr_type,avg(date_diff_d(closed_date,created_date)) as avg_days",
        "$group": "sr_type",
        "$order": "avg_days DESC",
        "$limit": 10,
    }
    return await socrata_get(settings.dataset_311, params, client=client)
