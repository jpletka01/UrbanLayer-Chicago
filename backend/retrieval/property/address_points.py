"""Authoritative address→PIN resolution via Cook County Address Points (78yw-iddh).

This dataset is the system-of-record map from a street address to its parcel's
14-digit PIN (plus the parcel's lat/long). It is served from the Cook County
Socrata portal and is **independent of the broken GIS spatial index**, so it
resolves correctly throughout the GIS outage — the property that closes R7.

Contract: return a PIN only on a *unique, confident* match. No match, an
unparseable address, or a multi-match (≥2 distinct PINs for the same address
components) all return None so the caller falls through to the degraded path —
we never pick a parcel arbitrarily (truth-model §5 fallback rule, INV-3).
"""

import logging
import re

import httpx

from backend.config import get_settings
from backend.retrieval.buildings import parse_chicago_address
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

# Addresses are stable; a long TTL keeps the resolver cheap on the request path.
_cache = TTLCache(ttl_seconds=86400, maxsize=2048, name="address_points")
_NOT_FOUND = object()

# 78yw-iddh stores the predirectional as the spelled-out word (e.g. "WEST"),
# while parse_chicago_address yields the single letter ("W"). Match either form
# so the query is robust to mixed encodings but still direction-constrained.
_DIRECTION_WORD = {"N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST"}


async def address_to_pin(
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Resolve an address to its authoritative parcel via Address Points (78yw-iddh).

    Returns {"pin14", "lat", "lon", "address"} on a unique confident match,
    else None (no match, unparseable, multi-match, or query error).
    """
    parsed = parse_chicago_address(address)
    if not parsed:
        return None

    number = parsed["number"]
    direction = parsed["direction"]
    name = parsed["name"]

    key = f"addr_pin:{number}:{direction}:{name}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    # Columns confirmed against the live 78yw-iddh schema: add_number, st_predir
    # (spelled-out word, e.g. "WEST"), st_name (no suffix), pin, lat, long (note:
    # `long`, not `lon`).
    dir_word = _DIRECTION_WORD.get(direction, direction)
    params = {
        "$where": (
            f"add_number='{number}' "
            f"AND upper(st_predir) in ('{direction}','{dir_word}') "
            f"AND upper(st_name)='{name.upper()}'"
        ),
        "$select": "pin,lat,long",
        "$limit": settings.limit_address_points,
    }
    try:
        rows = await socrata_get(
            settings.dataset_address_points,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Address-point lookup failed for %r: %s", address, exc)
        return None

    if not rows:
        _cache.set(key, _NOT_FOUND)
        return None

    # A confident match is a single distinct PIN. Multiple distinct PINs (address
    # range, multi-PIN building, ambiguous parse) is NOT confident → fall through.
    distinct_pins = {str(r.get("pin", "")).replace("-", "").zfill(14) for r in rows}
    distinct_pins.discard("00000000000000")
    if len(distinct_pins) != 1:
        log.info(
            "Address-point multi/zero-match for %r (%d distinct PINs) — not confident",
            address, len(distinct_pins),
        )
        _cache.set(key, _NOT_FOUND)
        return None

    row = rows[0]
    pin14 = distinct_pins.pop()
    try:
        lat = float(row["lat"])
        lon = float(row["long"])
    except (KeyError, TypeError, ValueError):
        # Authoritative PIN but no usable point — let the caller geocode for coords.
        _cache.set(key, _NOT_FOUND)
        return None

    result = {"pin14": pin14, "lat": lat, "lon": lon, "address": address}
    _cache.set(key, result)
    return result


_ORDINAL_RE = re.compile(r"^(\d+)(ST|ND|RD|TH)$")


def _format_display_address(raw: str) -> str:
    """Format an ALL-CAPS Address Points address for display.

    "642 W BELDEN AVE" → "642 W Belden Ave"; keeps single-letter directionals
    uppercase and lowercases ordinal suffixes ("63RD" → "63rd").
    """
    words = []
    for w in raw.split():
        m = _ORDINAL_RE.match(w)
        if m:
            words.append(f"{m.group(1)}{m.group(2).lower()}")
        elif len(w) == 1 or w.isdigit():
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join(words)


async def pin_to_address(
    pin: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Reverse lookup: 14-digit PIN → display address via Address Points.

    Display-only — never used for coordinate or identity resolution (the parcel
    centroid stays Parcel Universe per truth-model §5). A parcel may carry
    several address points (corner/multi-address buildings); the lowest house
    number is returned for determinism. Returns None on no match or any error.
    """
    key = f"pin_addr:{pin}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    params = {
        "$where": f"pin='{pin}'",
        "$select": "cmpaddabrv",
        "$order": "addrnocom",
        "$limit": 1,
    }
    try:
        rows = await socrata_get(
            settings.dataset_address_points,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Address-point reverse lookup failed for pin %s: %s", pin, exc)
        return None

    raw = (rows[0].get("cmpaddabrv") or "").strip() if rows else ""
    if not raw:
        _cache.set(key, _NOT_FOUND)
        return None

    result = _format_display_address(raw)
    _cache.set(key, result)
    return result
