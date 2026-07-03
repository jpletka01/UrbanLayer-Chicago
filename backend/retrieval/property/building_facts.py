"""Building-fact fallbacks for parcels x54s-btds doesn't cover.

The CCAO Single/Multi-Family characteristics dataset only covers regression-class
residential (2xx), which left bldg_sqft/year_built/stories at 0% for commercial,
condo, larger multifamily, exempt and industrial parcels (2026-07-02 benchmark).
Three fallbacks, tried only when the primary characteristics left gaps:

- Condo unit characteristics (``3r7i-mrz4``): unit sqft, year built, bedrooms.
- Commercial Valuation (``csik-bsws``): building sqft, keyed by ``keypin`` with a
  ``pins`` fan-out (an economic unit spans multiple PINs). ~92% of Chicago 2024
  commercial rows carry ``bldgsf``.
- Chicago Building Footprints (``syp8-uezg``): stories / year built / building
  sqft for whatever remains, matched spatially. City-maintained with uneven
  freshness — last resort, provenance-labeled.
"""

from __future__ import annotations

import logging

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get
from backend.retrieval.utils import format_pin

log = logging.getLogger(__name__)

_condo_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="condo_chars")
_commercial_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="commercial_valuation")
_footprint_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="building_footprints")
_NOT_FOUND = object()

DATASET_CONDO_CHARS = "3r7i-mrz4"
DATASET_COMMERCIAL_VALUATION = "csik-bsws"
DATASET_BUILDING_FOOTPRINTS = "syp8-uezg"



def _pos_int(val) -> int | None:
    try:
        n = int(float(val))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _pos_float(val) -> float | None:
    try:
        n = float(val)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


async def get_condo_characteristics(
    pin14: str, *, client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Condo UNIT facts: {"unit_sqft", "year_built", "bedrooms"} or None.

    ``char_building_sf`` (whole building) is deliberately not surfaced as the
    unit's bldg_sqft — the parcel IS the unit.
    """
    cached = _condo_cache.get(pin14)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    try:
        rows = await socrata_get(
            DATASET_CONDO_CHARS,
            {"pin": pin14, "$order": "year DESC", "$limit": 1},
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Condo characteristics failed for PIN %s: %s", pin14, exc)
        return None
    if not rows:
        _condo_cache.set(pin14, _NOT_FOUND)
        return None
    row = rows[0]
    result = {
        "unit_sqft": _pos_int(row.get("char_unit_sf")),
        "year_built": _pos_int(row.get("char_yrblt")),
        "bedrooms": _pos_int(row.get("char_bedrooms")),
    }
    _condo_cache.set(pin14, result)
    return result


async def get_commercial_building_sqft(
    pin14: str, *, client: httpx.AsyncClient | None = None,
) -> int | None:
    """Building sqft from the CCAO Commercial Valuation dataset, or None.

    Matched on the dashed PIN via ``keypin`` or membership in ``pins`` (an
    economic unit's keypin row lists all member PINs).
    """
    cached = _commercial_cache.get(pin14)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    dashed = format_pin(pin14)
    settings = get_settings()
    try:
        rows = await socrata_get(
            DATASET_COMMERCIAL_VALUATION,
            {
                "$where": f"(keypin='{dashed}' OR pins like '%{dashed}%') AND bldgsf IS NOT NULL",
                "$select": "bldgsf,year",
                "$order": "year DESC",
                "$limit": 20,
            },
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Commercial valuation lookup failed for PIN %s: %s", pin14, exc)
        return None
    if not rows:
        _commercial_cache.set(pin14, _NOT_FOUND)
        return None
    # An economic unit carries one row PER BUILDING (same keypin/year) — the
    # unit's building area is the sum over the most recent valuation year.
    latest = max(r.get("year", "") for r in rows)
    sqft = sum(_pos_int(r.get("bldgsf")) or 0 for r in rows if r.get("year") == latest)
    if sqft <= 0:
        _commercial_cache.set(pin14, _NOT_FOUND)
        return None
    _commercial_cache.set(pin14, sqft)
    return sqft


async def get_footprint_facts(
    lat: float, lon: float, *, client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Nearest building footprint within ~25m: {"stories", "year_built",
    "bldg_sqft"} (each possibly None) or None when no footprint is close.

    Chicago's footprint layer is city-maintained with uneven freshness; values
    from here carry the "footprint" provenance label.
    """
    key = f"{round(lat, 5)}:{round(lon, 5)}"
    cached = _footprint_cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    try:
        rows = await socrata_get(
            DATASET_BUILDING_FOOTPRINTS,
            {
                "$where": f"within_circle(the_geom, {lat}, {lon}, 25)",
                "$select": "stories,year_built,bldg_sq_fo,bldg_statu",
                "$limit": 5,
            },
            client=client,
            base_url=settings.socrata_base,
            app_token=settings.socrata_app_token or None,
        )
    except Exception as exc:
        log.warning("Building footprint lookup failed at (%s, %s): %s", lat, lon, exc)
        return None

    active = [r for r in rows or [] if str(r.get("bldg_statu", "ACTIVE")).upper() != "DEMOLISHED"]
    if not active:
        _footprint_cache.set(key, _NOT_FOUND)
        return None
    # Principal structure first: most populated facts, then largest footprint
    # (bldg_sq_fo is frequently 0.0 in this layer — stories/year are the
    # reliable columns).
    def _row_rank(r: dict) -> tuple[int, float]:
        facts = sum(1 for v in (_pos_int(r.get("stories")),
                                _pos_int(r.get("year_built")),
                                _pos_float(r.get("bldg_sq_fo"))) if v)
        return (facts, _pos_float(r.get("bldg_sq_fo")) or 0.0)
    active.sort(key=_row_rank, reverse=True)
    row = active[0]
    year = _pos_int(row.get("year_built"))
    result = {
        "stories": _pos_int(row.get("stories")),
        "year_built": year if year and year >= 1800 else None,
        "bldg_sqft": _pos_int(row.get("bldg_sq_fo")),
    }
    if not any(result.values()):
        _footprint_cache.set(key, _NOT_FOUND)
        return None
    _footprint_cache.set(key, result)
    return result
