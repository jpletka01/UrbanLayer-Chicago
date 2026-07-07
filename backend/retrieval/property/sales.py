"""CCAO parcel sales history by PIN."""

import asyncio
import logging
import math
from statistics import median
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get
from backend.retrieval.utils import MI_PER_DEG_LAT, cutoff_iso

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="property_sales")
_comps_cache = TTLCache(ttl_seconds=3600, maxsize=128, name="comparable_sales")
_NOT_FOUND = object()


async def get_sales(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch sales history for a PIN (most recent 10 sales)."""
    key = f"sales:{pin14}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return []
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "sale_date DESC",
        "$limit": settings.limit_ccao_sales,
    }
    try:
        result = await socrata_get(
            settings.dataset_ccao_sales,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        _cache.set(key, result)
        return result
    except Exception as exc:
        log.warning("CCAO sales failed for PIN %s: %s", pin14, exc)
        _cache.set(key, _NOT_FOUND)
        return []


def _normalize_pin(pin: str) -> str:
    return pin.replace("-", "").strip()


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _deg_to_mi(radius_deg: float) -> float:
    """Latitude-degree radius → miles (shared MI_PER_DEG_LAT scale)."""
    return round(radius_deg * MI_PER_DEG_LAT, 2)


async def nearby_comparable_sales(
    lat: float,
    lon: float,
    class_prefix: str,
    *,
    years: int | None = None,
    radius_deg: float | None = None,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Comparable sales with progressive widening.

    Tries same-class @ base radius/window, then widens radius, then extends the
    window, returning the first non-empty tier with a ``basis`` label so the
    report can disclose comparability. Returns {"summary": {...}, "sales": [...]}.
    """
    settings = get_settings()
    base_years = years or settings.comparable_sales_years
    base_radius = radius_deg or settings.comparable_sales_radius_deg
    limit = limit or settings.limit_comparable_sales

    key = f"comps:{round(lat, 4)}:{round(lon, 4)}:{class_prefix}:{base_years}"
    cached = _comps_cache.get(key)
    if cached is not None:
        return cached

    # Escalating (radius, window) tiers — stop at the first that yields comps.
    tiers = [
        (base_radius, base_years),
        (base_radius * 2, base_years),
        (base_radius * 2, base_years + 2),
    ]
    result: dict[str, Any] = {"summary": {}, "sales": []}
    for rad, yrs in tiers:
        result = await _query_comps(lat, lon, class_prefix, yrs, rad, limit, client)
        if result["sales"]:
            result["summary"]["comp_basis"] = (
                f"Class {class_prefix}xx sales within {_deg_to_mi(rad)} mi, last {yrs} yr "
                f"(n={len(result['sales'])})"
            )
            break

    _comps_cache.set(key, result)
    return result


async def _query_comps(
    lat: float,
    lon: float,
    class_prefix: str,
    years: int,
    radius_deg: float,
    limit: int,
    client: httpx.AsyncClient | None,
) -> dict[str, Any]:
    """Single-pass 3-hop comparable sales query (Parcel Universe → Sales → Characteristics)."""
    settings = get_settings()
    try:
        # Hop 1: Nearby PINs from Parcel Universe. Longitude degrees shrink by
        # cos(lat) (~0.74 at Chicago), so the east-west delta is scaled to keep
        # the box square in ground miles; comps are then haversine-filtered to
        # the disclosed radius below (a bbox corner is √2 × the radius out).
        dlon = radius_deg / math.cos(math.radians(lat))
        parcel_where = (
            f"lat between '{lat - radius_deg}' and '{lat + radius_deg}' "
            f"AND lon between '{lon - dlon}' and '{lon + dlon}' "
            f"AND class LIKE '{class_prefix}%'"
        )
        parcels = await socrata_get(
            settings.dataset_ccao_parcels,
            {
                "$where": parcel_where,
                "$select": "pin,class,lat,lon",
                "$limit": 100,
            },
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not parcels:
            return {"summary": {}, "sales": []}

        pin_list = list({p["pin"] for p in parcels if p.get("pin")})
        pin_coords = {
            _normalize_pin(p["pin"]): (float(p.get("lat", 0)), float(p.get("lon", 0)))
            for p in parcels
            if p.get("pin")
        }

        # Hop 2: Sales for those PINs (arm's-length only)
        pin_in = ",".join(f"'{p}'" for p in pin_list[:50])
        sales_where = (
            f"pin IN ({pin_in}) "
            f"AND sale_date > '{cutoff_iso(years * 365)}' "
            f"AND sale_filter_less_than_10k = 'false' "
            f"AND sale_filter_deed_type = 'false' "
            f"AND is_multisale = 'false'"
        )
        sales_task = socrata_get(
            settings.dataset_ccao_sales,
            {
                "$where": sales_where,
                "$select": "pin,sale_date,sale_price,deed_type,class",
                "$order": "sale_date DESC",
                "$limit": limit * 3,
            },
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )

        # Hop 3 (parallel with hop 2): Characteristics for all PINs
        normalized_pins = [_normalize_pin(p) for p in pin_list[:50]]
        chars_in = ",".join(f"'{p}'" for p in normalized_pins)
        chars_task = socrata_get(
            settings.dataset_ccao_characteristics,
            {
                "$where": f"pin IN ({chars_in})",
                "$select": "pin,char_land_sf,char_bldg_sf",
                "$limit": 100,
            },
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )

        sales_raw, chars_raw = await asyncio.gather(sales_task, chars_task)

        # The characteristics dataset has multiple rows per PIN (cards/years), and
        # many rows null out char_land_sf/char_bldg_sf. Keep the most *complete*
        # row per PIN — (has land, has building) as a lexicographic score — so we
        # recover every dimension the dataset actually has instead of whichever
        # row sorts first. (The previous branch logic kept a land-only row over a
        # later land+building row, silently dropping the building sqft.)
        def _completeness(c: dict) -> tuple[bool, bool]:
            return (bool(c.get("char_land_sf")), bool(c.get("char_bldg_sf")))

        chars_by_pin: dict[str, dict] = {}
        for c in chars_raw:
            np = _normalize_pin(c.get("pin", ""))
            prev = chars_by_pin.get(np)
            if prev is None or _completeness(c) > _completeness(prev):
                chars_by_pin[np] = c

        # Merge and build ComparableSale-shaped dicts
        seen_pins: set[str] = set()
        comps: list[dict] = []
        for s in sales_raw:
            pin = s.get("pin", "")
            if pin in seen_pins:
                continue
            seen_pins.add(pin)

            price = float(s["sale_price"]) if s.get("sale_price") else None
            # A comp without a price contributes nothing to any valuation stat
            # but would still inflate sales_volume (the "n=" the report
            # discloses) — drop it.
            if price is None:
                continue
            norm_pin = _normalize_pin(pin)
            chars = chars_by_pin.get(norm_pin, {})
            land_sf = int(float(chars["char_land_sf"])) if chars.get("char_land_sf") else None
            bldg_sf = int(float(chars["char_bldg_sf"])) if chars.get("char_bldg_sf") else None

            # Three-state: the characteristics dataset is residential-only, so a
            # missing building sqft means UNKNOWN improvement status — it must
            # not be conflated with a vacant-land sale (the old `(bldg_sf or 0)
            # == 0` labeled most non-residential comps "LAND").
            if bldg_sf is None:
                sale_type = None
            elif bldg_sf == 0:
                sale_type = "LAND"
            else:
                sale_type = "LAND AND BUILDING"

            coords = pin_coords.get(norm_pin, (0, 0))
            dist = _haversine_mi(lat, lon, coords[0], coords[1]) if coords[0] else None
            # The comp_basis line discloses "within X mi" — enforce it. Comps
            # with unknown coordinates are kept (distance shows as null).
            if dist is not None and dist > radius_deg * MI_PER_DEG_LAT:
                continue

            comp: dict[str, Any] = {
                "pin": pin,
                "sale_date": s.get("sale_date"),
                "sale_price": price,
                "class_code": s.get("class"),
                "land_sqft": land_sf,
                "bldg_sqft": bldg_sf,
                "price_per_land_sqft": round(price / land_sf, 2) if price and land_sf else None,
                "price_per_bldg_sqft": round(price / bldg_sf, 2) if price and bldg_sf else None,
                "deed_type": s.get("deed_type"),
                "sale_type": sale_type,
                "distance_mi": round(dist, 2) if dist is not None else None,
                "lat": coords[0] if coords[0] else None,
                "lon": coords[1] if coords[1] else None,
            }
            comps.append(comp)
            if len(comps) >= limit:
                break

        # Summary statistics
        prices = [c["sale_price"] for c in comps if c["sale_price"]]
        ppl = [c["price_per_land_sqft"] for c in comps if c["price_per_land_sqft"]]
        ppb = [c["price_per_bldg_sqft"] for c in comps if c["price_per_bldg_sqft"]]

        summary: dict[str, Any] = {
            "median_sale_price": round(median(prices), 0) if prices else None,
            "median_price_per_land_sqft": round(median(ppl), 2) if ppl else None,
            "median_price_per_bldg_sqft": round(median(ppb), 2) if ppb else None,
            "price_range_min": min(prices) if prices else None,
            "price_range_max": max(prices) if prices else None,
            "sales_volume": len(comps),
        }

        return {"summary": summary, "sales": comps}

    except Exception as exc:
        log.warning("Comparable sales failed for (%s, %s): %s", lat, lon, exc)
        return {"summary": {}, "sales": []}
