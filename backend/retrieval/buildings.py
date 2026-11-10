import asyncio
import logging
import re
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.geo import community_area_bounds
from backend.retrieval.socrata import socrata_aggregate, socrata_get
from backend.retrieval.utils import cutoff_iso

log = logging.getLogger(__name__)

_permits_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="permits")
_violations_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="violations")
_addr_permits_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="addr_permits")
_addr_violations_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="addr_violations")
_construction_cache = TTLCache(ttl_seconds=3600, maxsize=128, name="nearby_construction")


async def permits_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"permits:{community_area}:{days}"
    cached = _permits_cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    where = (
        f"community_area='{community_area}' "
        f"AND issue_date > '{cutoff_iso(days)}'"
    )

    grouped_task = socrata_aggregate(
        settings.dataset_permits,
        where=where,
        group="permit_type",
        select="permit_type,count(*) as count,sum(reported_cost) as total_cost",
        limit=50,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_permits,
        {
            "$where": where,
            "$select": (
                "work_description,issue_date,"
                "contact_1_type,contact_1_name,"
                "contact_2_type,contact_2_name,"
                "contact_3_type,contact_3_name"
            ),
            "$order": "issue_date DESC",
            "$limit": settings.limit_permits_detail,
        },
        client=client,
    )

    grouped, detail = await asyncio.gather(grouped_task, detail_task)
    result = {"grouped": grouped, "detail": detail}
    _permits_cache.set(key, result)
    return result


async def violations_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    key = f"violations:{community_area}:{days}"
    cached = _violations_cache.get(key)
    if cached is not None:
        return cached

    bounds = community_area_bounds(community_area)
    if not bounds:
        return {"status_counts": [], "detail": []}
    min_lat, min_lon, max_lat, max_lon = bounds

    settings = get_settings()
    where = (
        f"latitude between '{min_lat}' and '{max_lat}' "
        f"AND longitude between '{min_lon}' and '{max_lon}' "
        f"AND violation_date > '{cutoff_iso(days)}'"
    )

    status_task = socrata_aggregate(
        settings.dataset_violations,
        where=where,
        group="violation_status",
        select="violation_status,count(*) as count",
        limit=10,
        client=client,
    )
    detail_task = socrata_get(
        settings.dataset_violations,
        {
            "$where": where,
            "$select": (
                "violation_date,violation_code,violation_description,"
                "violation_status,"
                "street_number,street_direction,street_name,latitude,longitude"
            ),
            "$order": "violation_status ASC,violation_date DESC",
            "$limit": settings.limit_violations,
        },
        client=client,
    )

    status_counts, detail = await asyncio.gather(status_task, detail_task)
    result = {"status_counts": status_counts, "detail": detail}
    _violations_cache.set(key, result)
    return result


_SUFFIXES = r"(?:AVE|ST|BLVD|DR|PL|CT|RD|WAY|TER|PKWY|LN|CIR|HWY|SQ)"
_ADDR_RE = re.compile(
    r"^\s*(\d+)\s+(N|S|E|W)\s+(.+?)\s+" + _SUFFIXES + r"(?:\s.*|,.*)?$",
    re.IGNORECASE,
)
_ADDR_RE_NO_SUFFIX = re.compile(
    r"^\s*(\d+)\s+(N|S|E|W)\s+([A-Z]+)(?:\s.*|,.*)?$",
    re.IGNORECASE,
)


def parse_chicago_address(address: str) -> dict[str, str] | None:
    """Parse '2400 N MILWAUKEE AVE' or '2400 N MILWAUKEE AVE, Chicago, IL' into {number, direction, name}."""
    addr = address.strip().upper()
    m = _ADDR_RE.match(addr)
    if m:
        return {
            "number": m.group(1),
            "direction": m.group(2),
            "name": m.group(3).strip(),
        }
    m = _ADDR_RE_NO_SUFFIX.match(addr)
    if m:
        return {
            "number": m.group(1),
            "direction": m.group(2),
            "name": m.group(3).strip(),
        }
    return None


async def address_specific_permits(
    street_number: str,
    street_direction: str,
    street_name: str,
    *,
    years: int | None = None,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Query permits by exact street address fields."""
    settings = get_settings()
    years = years or settings.address_permits_years
    limit = limit or settings.limit_address_permits

    key = f"addr_permits:{street_number}:{street_direction}:{street_name}"
    cached = _addr_permits_cache.get(key)
    if cached is not None:
        return cached

    where = (
        f"street_number='{street_number}' "
        f"AND street_direction='{street_direction}' "
        f"AND upper(street_name)='{street_name.upper()}' "
        f"AND issue_date > '{cutoff_iso(years * 365)}'"
    )
    try:
        result = await socrata_get(
            settings.dataset_permits,
            {
                "$where": where,
                "$select": (
                    "permit_,permit_type,work_description,issue_date,reported_cost,"
                    "contact_1_type,contact_1_name,"
                    "contact_2_type,contact_2_name,"
                    "contact_3_type,contact_3_name"
                ),
                "$order": "issue_date DESC",
                "$limit": limit,
            },
            client=client,
        )
        _addr_permits_cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("Address permits failed for %s %s %s: %s", street_number, street_direction, street_name, exc)
        return []


async def address_specific_violations(
    street_number: str,
    street_direction: str,
    street_name: str,
    *,
    years: int | None = None,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Query violations by exact street address fields."""
    settings = get_settings()
    years = years or settings.address_violations_years
    limit = limit or settings.limit_address_violations

    key = f"addr_violations:{street_number}:{street_direction}:{street_name}"
    cached = _addr_violations_cache.get(key)
    if cached is not None:
        return cached

    where = (
        f"street_number='{street_number}' "
        f"AND street_direction='{street_direction}' "
        f"AND upper(street_name)='{street_name.upper()}' "
        f"AND violation_date > '{cutoff_iso(years * 365)}'"
    )
    try:
        result = await socrata_get(
            settings.dataset_violations,
            {
                "$where": where,
                "$select": (
                    "violation_date,violation_code,violation_description,"
                    "violation_status,violation_status_date,"
                    "inspection_number,inspector_id"
                ),
                "$order": "violation_date DESC",
                "$limit": limit,
            },
            client=client,
        )
        _addr_violations_cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("Address violations failed for %s %s %s: %s", street_number, street_direction, street_name, exc)
        return []


async def nearby_new_construction(
    lat: float,
    lon: float,
    *,
    radius_deg: float | None = None,
    months: int | None = None,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """NEW CONSTRUCTION and WRECKING/DEMOLITION permits within a radius.

    Counts and per-type reported-cost totals come from a grouped aggregate —
    TRUE totals for the area/window, not tallies over the ``limit``-row sample
    (which undercounted active corridors and mixed demolition costs into the
    "investment" figure). ``recent_projects`` stays a most-recent sample for
    the map/list.
    """
    import math

    settings = get_settings()
    radius_deg = radius_deg or settings.nearby_construction_radius_deg
    months = months or settings.nearby_construction_months
    limit = limit or settings.limit_nearby_construction

    # Radius is keyed too — callers with different radii must not share entries.
    key = f"construction:{round(lat, 4)}:{round(lon, 4)}:{months}:{radius_deg}"
    cached = _construction_cache.get(key)
    if cached is not None:
        return cached

    # Longitude degrees shrink by cos(lat) (~0.74 at Chicago): an uncorrected
    # box reaches the labeled miles north-south but only ~3/4 of them east-west.
    dlon = radius_deg / math.cos(math.radians(lat))
    where = (
        f"latitude between '{lat - radius_deg}' and '{lat + radius_deg}' "
        f"AND longitude between '{lon - dlon}' and '{lon + dlon}' "
        f"AND issue_date > '{cutoff_iso(months * 30)}' "
        f"AND (permit_type='PERMIT - NEW CONSTRUCTION' "
        f"OR permit_type='PERMIT - WRECKING/DEMOLITION')"
    )
    try:
        totals_task = socrata_aggregate(
            settings.dataset_permits,
            where=where,
            group="permit_type",
            select="permit_type,count(*) as count,sum(reported_cost) as total_cost",
            order="count DESC",
            limit=5,
            client=client,
        )
        sample_task = socrata_get(
            settings.dataset_permits,
            {
                "$where": where,
                "$select": (
                    "permit_type,work_description,issue_date,reported_cost,"
                    "street_number,street_direction,street_name,latitude,longitude"
                ),
                "$order": "issue_date DESC",
                "$limit": limit,
            },
            client=client,
        )
        totals, rows = await asyncio.gather(totals_task, sample_task)

        new_count = 0
        demo_count = 0
        new_construction_cost = 0.0
        for t in totals:
            ptype = t.get("permit_type") or ""
            count = int(t.get("count", 0) or 0)
            if "NEW CONSTRUCTION" in ptype:
                new_count = count
                try:
                    new_construction_cost = float(t.get("total_cost") or 0)
                except (TypeError, ValueError):
                    new_construction_cost = 0.0
            elif "WRECKING" in ptype:
                demo_count = count

        result: dict[str, Any] = {
            "new_construction_count": new_count,
            "demolition_count": demo_count,
            # Sum of reported_cost over ALL new-construction permits in the
            # area/window (demolition costs excluded — they aren't investment).
            "new_construction_cost": new_construction_cost,
            "recent_projects": rows,
        }
        _construction_cache.set(key, result)
        return result
    except Exception as exc:
        # Raises, caching nothing: zeros here read as "no construction nearby" (Item 65); the report lists
        # "nearby construction activity" as not checked instead.
        log.warning("Nearby construction failed for (%s, %s): %s", lat, lon, exc)
        raise


_construction_within_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="construction_within")
CONSTRUCTION_RADIUS_M = 805  # ½ mile
CONSTRUCTION_MONTHS = 24
RENOVATION_COST_FLOOR = 250_000  # owner's call (Item 102): new construction plus renovations at least this large
CONSTRUCTION_LIMIT = 300


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


async def construction_within(lat: float, lon: float, *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """New construction and major renovations within ½ mile, last 24 months (the new UI's Neighborhood tab,
    decision Item 102). One row per permit, newest first, each with its distance and the homes it adds
    (``residential_unit_change``, the City's own field; negative = units removed). Separate from
    ``nearby_new_construction`` (the report's box query with demolitions), which is unchanged.
    Raises on failure and caches nothing (Item 65): an empty list is a checked "none"."""
    key = f"construction_within:{round(lat, 4)}:{round(lon, 4)}"
    cached = _construction_within_cache.get(key)
    if cached is not None:
        return cached
    settings = get_settings()
    where = (
        f"within_circle(location, {lat}, {lon}, {CONSTRUCTION_RADIUS_M}) "
        f"AND issue_date > '{cutoff_iso(CONSTRUCTION_MONTHS * 30)}' "
        f"AND (permit_type='PERMIT - NEW CONSTRUCTION' OR "
        f"(permit_type='PERMIT - RENOVATION/ALTERATION' AND reported_cost >= {RENOVATION_COST_FLOOR}))"
    )
    rows = await socrata_get(settings.dataset_permits, {
        "$where": where,
        "$select": ("permit_,permit_type,work_description,issue_date,reported_cost,residential_unit_change,"
                    "street_number,street_direction,street_name,latitude,longitude"),
        "$order": "issue_date DESC",
        "$limit": CONSTRUCTION_LIMIT,
    }, client=client)
    projects: list[dict[str, Any]] = []
    for r in rows:
        try:
            plat, plon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            cost = float(r.get("reported_cost")) if r.get("reported_cost") not in (None, "") else None
        except (TypeError, ValueError):
            cost = None
        try:
            units = int(float(r["residential_unit_change"])) if r.get("residential_unit_change") not in (None, "") else None
        except (TypeError, ValueError):
            units = None
        address = " ".join(x for x in (r.get("street_number"), r.get("street_direction"), r.get("street_name")) if x)
        projects.append({
            "permit": r.get("permit_"),
            "kind": "new" if "NEW CONSTRUCTION" in (r.get("permit_type") or "") else "renovation",
            "description": (r.get("work_description") or "").strip() or None,
            "issued": (r.get("issue_date") or "")[:10] or None,
            "cost": cost,
            "units_added": units,
            "address": address.title() or None,
            "lat": plat,
            "lon": plon,
            "distance_mi": round(_haversine_mi(lat, lon, plat, plon), 2),
        })
    result = {
        "radius_mi": 0.5,
        "months": CONSTRUCTION_MONTHS,
        "renovation_cost_floor": RENOVATION_COST_FLOOR,
        "projects": projects,
        "capped": len(rows) >= CONSTRUCTION_LIMIT,
    }
    _construction_within_cache.set(key, result)
    return result
