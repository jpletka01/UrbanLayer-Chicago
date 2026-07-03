"""Distress / opportunity flags for a parcel.

Five cheap, PIN- or point-keyed lookups that change how a buyer reads the
parcel, gathered in parallel:

- Treasurer Annual Tax Sale ``55ju-2fs9`` + Scavenger Sale ``ydgz-vkrp``
  (Cook County): the PIN appeared in a delinquent-tax sale. NOTE the datasets
  end around 2014 — a real title-history fact, but a DATED one; always
  presented with the years so it can't read as current distress.
- City-Owned Land Inventory ``aksk-kvfp`` (city): the parcel is city-owned,
  with status + application URL (ChiBlockBuilder) — an acquisition opportunity.
- Building Code Scofflaw List ``crg5-4zyp`` (city): court-involved chronic
  code violators; matched by proximity (no PIN column, ~20 m on ``location``).
- House Share Prohibited Buildings ``7bzs-jsyj`` (city): the building opted
  out of short-term rentals — investor-relevant. PIN prefix match (rows carry
  unit-suffixed pins). The companion "restricted residential zone" dataset has
  no geometry (precinct numbers only) and is NOT flagged here.
- CHRS orange/red rating (LOCAL committed artifact, 1996 survey — the API
  asset is 403-restricted): either rating triggers the 90-day
  demolition-permit hold. See ``chrs.py`` / ``ingestion.build_chrs_artifact``.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.models import ParcelFlags
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get
from backend.retrieval.utils import format_pin

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=512, name="parcel_flags")

DATASET_ANNUAL_TAX_SALE = "55ju-2fs9"
DATASET_SCAVENGER_SALE = "ydgz-vkrp"
DATASET_CITY_OWNED = "aksk-kvfp"
DATASET_SCOFFLAW = "crg5-4zyp"
DATASET_STR_PROHIBITED = "7bzs-jsyj"

SCOFFLAW_RADIUS_M = 20


def _i(val) -> int | None:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


async def get_parcel_flags(
    pin14: str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> ParcelFlags | None:
    """Return ParcelFlags, or None when every flag is clear (nothing to say)."""
    pin_clean = pin14.replace("-", "").zfill(14)
    dashed = format_pin(pin_clean)
    key = f"flags:{pin_clean}"
    cached = _cache.get(key)
    if cached is not None:
        return cached or None  # falsy sentinel = known-clear

    settings = get_settings()
    county = dict(
        client=client,
        base_url=settings.cook_county_socrata_base,
        app_token=settings.cook_county_socrata_token or None,
    )
    city = dict(
        client=client,
        base_url=settings.socrata_base,
        app_token=settings.socrata_app_token or None,
    )

    coros: dict[str, object] = {
        "tax_sale": socrata_get(DATASET_ANNUAL_TAX_SALE, {
            "$where": f"pin='{dashed}'",
            "$select": "tax_sale_year,sold_at_sale",
            "$limit": 25,
        }, **county),
        "scavenger": socrata_get(DATASET_SCAVENGER_SALE, {
            "$where": f"pin='{dashed}'",
            "$select": "tax_sale_year",
            "$limit": 25,
        }, **county),
        # The inventory keeps DISPOSED parcels (property_status "Sold" etc.) —
        # only current city ownership is a flag; a past disposition is noise.
        "city_owned": socrata_get(DATASET_CITY_OWNED, {
            "$where": f"pin='{dashed}' AND property_status='Owned by City'",
            "$select": "property_status,sales_status,application_url,application_deadline",
            "$limit": 1,
        }, **city),
        "str_prohibited": socrata_get(DATASET_STR_PROHIBITED, {
            "$where": f"starts_with(pin, '{dashed}')",
            "$select": "pin",
            "$limit": 1,
        }, **city),
    }
    if lat is not None and lon is not None:
        coros["scofflaw"] = socrata_get(DATASET_SCOFFLAW, {
            "$where": f"within_circle(location, {lat}, {lon}, {SCOFFLAW_RADIUS_M})",
            "$select": "address,circuit_court_case_number,defendant_owner",
            "$limit": 1,
        }, **city)
        # CHRS orange/red (1996 survey, frozen) — LOCAL committed artifact,
        # no network; the thread hop only matters on the first call (tree build).
        from backend.retrieval.property.chrs import lookup_chrs
        coros["chrs"] = asyncio.to_thread(lookup_chrs, lat, lon)

    done = await asyncio.gather(*coros.values(), return_exceptions=True)
    results: dict[str, list | None] = {}
    for name, value in zip(coros.keys(), done):
        if isinstance(value, Exception):
            log.warning("Parcel flag %s lookup failed for %s: %s", name, pin_clean, value)
            results[name] = None
        else:
            results[name] = value

    tax_years = sorted({y for r in results.get("tax_sale") or []
                        if (y := _i(r.get("tax_sale_year")))})
    scavenger_years = sorted({y for r in results.get("scavenger") or []
                              if (y := _i(r.get("tax_sale_year")))})
    city_owned_row = (results.get("city_owned") or [None])[0]
    scofflaw_row = (results.get("scofflaw") or [None])[0]
    str_prohibited = bool(results.get("str_prohibited"))
    chrs = results.get("chrs")  # dict from lookup_chrs, not a Socrata row list

    flags = ParcelFlags(
        tax_sale_years=tax_years,
        scavenger_sale_years=scavenger_years,
        city_owned=bool(city_owned_row),
        city_owned_status=(city_owned_row or {}).get("property_status"),
        city_owned_sales_status=(city_owned_row or {}).get("sales_status"),
        city_owned_application_url=_url((city_owned_row or {}).get("application_url")),
        scofflaw=bool(scofflaw_row),
        scofflaw_case=(scofflaw_row or {}).get("circuit_court_case_number"),
        str_prohibited=str_prohibited,
        chrs_rating=(chrs or {}).get("color") if isinstance(chrs, dict) else None,
        chrs_name=(chrs or {}).get("name") if isinstance(chrs, dict) else None,
    )

    if not flags.any_flag():
        _cache.set(key, False)
        return None
    _cache.set(key, flags)
    return flags


def _url(val) -> str | None:
    """Socrata URL columns arrive as {'url': ...} objects."""
    if isinstance(val, dict):
        return val.get("url")
    return val or None
