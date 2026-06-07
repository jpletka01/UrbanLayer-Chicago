"""Bulk parcel exploration via Cook County Parcel Universe (pabr-t5kh)."""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds, community_area_name
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=600, maxsize=256, name="explore_parcels")

CLASS_DESCRIPTIONS: dict[str, str] = {
    "000": "Exempt property",
    "100": "Vacant land",
    "190": "Vacant land — industrial/commercial",
    "200": "Residential — one-story",
    "201": "Residential — one-story, small lot",
    "202": "Residential — one-story, large lot",
    "203": "Residential — one-story, frame",
    "204": "Residential — A-frame",
    "205": "Residential — one-story, town/row house",
    "206": "Residential — one-story, modular",
    "207": "Residential — partial completion",
    "208": "Residential — old style",
    "209": "Residential — old style with attic",
    "210": "Residential — two-story",
    "211": "Residential — two-story, older",
    "212": "Residential — two-story, newer",
    "218": "Residential — two-story, old style",
    "225": "Residential — split-level",
    "234": "Residential — split-level, newer",
    "241": "Residential — single-family, larger lot",
    "278": "Residential — three-story, single-family",
    "295": "Residential — coach house",
    "299": "Residential — misc single-family",
    "300": "Multi-family — two units",
    "311": "Multi-family — two-to-six units",
    "312": "Multi-family — two-to-six units, newer",
    "313": "Multi-family — two-to-six units, mixed use",
    "314": "Multi-family — two-to-six units, townhouse",
    "315": "Multi-family — two-to-six units, cooperative",
    "318": "Multi-family — two-to-six units, old style",
    "390": "Multi-family — seven+ units",
    "391": "Multi-family — condominiums",
    "399": "Multi-family — condominium, individual unit",
    "500": "Commercial",
    "501": "Commercial — one-story store",
    "516": "Commercial — one/two-story store/office",
    "517": "Commercial — multi-story, mixed use",
    "522": "Commercial — single-story, strip center",
    "528": "Commercial — office building",
    "535": "Commercial — hotel/motel",
    "550": "Commercial — parking structure",
    "590": "Commercial — misc",
    "597": "Commercial — condominium, individual unit",
    "600": "Industrial — one-story",
    "613": "Industrial — multi-story",
    "631": "Industrial — warehouse, one-story",
    "637": "Industrial — warehouse, multi-story",
    "650": "Industrial — misc",
}

CLASS_GROUPS: dict[str, list[str]] = {
    "vacant": ["0", "1"],
    "residential": ["2"],
    "multi-family": ["3"],
    "commercial": ["5"],
    "industrial": ["6"],
}


def _format_pin(raw: str) -> str:
    """Format a 14-digit PIN as XX-XX-XXX-XXX-XXXX."""
    p = raw.replace("-", "").zfill(14)
    return f"{p[:2]}-{p[2:4]}-{p[4:7]}-{p[7:10]}-{p[10:14]}"


def _describe_class(code: str) -> str:
    if code in CLASS_DESCRIPTIONS:
        return CLASS_DESCRIPTIONS[code]
    prefix = code[:1] if len(code) >= 1 else ""
    groups = {
        "0": "Vacant/Exempt", "1": "Vacant land",
        "2": "Residential", "3": "Multi-family",
        "5": "Commercial", "6": "Industrial",
    }
    return groups.get(prefix, f"Class {code}")


async def explore_parcels(
    community_area: int,
    class_prefix: str | None = None,
    limit: int = 200,
    offset: int = 0,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[dict], int, str | None]:
    """Query Parcel Universe for parcels in a community area.

    Returns (parcels, total_count, community_area_name).
    """
    bounds = community_area_bounds(community_area)
    if bounds is None:
        return [], 0, None

    ca_name = community_area_name(community_area)
    min_lat, min_lon, max_lat, max_lon = bounds

    where = (
        f"lat between '{min_lat}' and '{max_lat}' "
        f"and lon between '{min_lon}' and '{max_lon}'"
    )
    if class_prefix:
        prefixes = CLASS_GROUPS.get(class_prefix)
        if prefixes and len(prefixes) > 1:
            conditions = " OR ".join(f"class like '{p}%'" for p in prefixes)
            where += f" and ({conditions})"
        elif prefixes:
            where += f" and class like '{prefixes[0]}%'"
        else:
            where += f" and class like '{class_prefix}%'"

    settings = get_settings()

    cache_key = f"explore:{community_area}:{class_prefix}:{limit}:{offset}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    count_params = {
        "$select": "count(pin) as cnt",
        "$where": where,
        "$limit": 1,
    }
    data_params = {
        "$select": "pin, class, lat, lon",
        "$where": where,
        "$order": "pin",
        "$limit": limit,
        "$offset": offset,
    }

    count_task = socrata_get(
        settings.dataset_ccao_parcels,
        count_params,
        client=client,
        base_url=settings.cook_county_socrata_base,
        app_token=settings.cook_county_socrata_token or None,
    )
    data_task = socrata_get(
        settings.dataset_ccao_parcels,
        data_params,
        client=client,
        base_url=settings.cook_county_socrata_base,
        app_token=settings.cook_county_socrata_token or None,
    )

    count_rows, data_rows = await asyncio.gather(count_task, data_task)

    total = int(count_rows[0]["cnt"]) if count_rows else 0

    parcels = []
    for row in data_rows:
        pin_raw = row.get("pin", "")
        if not pin_raw:
            continue
        cls = row.get("class", "")
        lat = row.get("lat") or row.get("latitude")
        lon = row.get("lon") or row.get("longitude")
        if lat is None or lon is None:
            continue
        parcels.append({
            "pin": _format_pin(str(pin_raw)),
            "class": cls,
            "class_description": _describe_class(cls),
            "lat": float(lat),
            "lon": float(lon),
        })

    result = (parcels, total, ca_name)
    _cache.set(cache_key, result)
    return result
