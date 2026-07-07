"""Second authoritative address→PIN source: Cook County Assessor Parcel Addresses (3723-97qp).

Consulted by `_resolve_location` only when Address Points (78yw-iddh) has no
confident match. The Assessor's Parcel Addresses dataset is the property
address-of-record per PIN and covers parcels absent from Address Points — e.g.
481 W Deming Pl resolves here (unique `14283190070000`) but returns nothing from
78yw-iddh. It carries **no coordinates**, so the caller backfills the parcel
centroid from Parcel Universe (`pabr-t5kh`), the same source the PIN branch uses.

Contract (mirrors `address_points.address_to_pin`, truth-model §5 / INV-3):
return a PIN only on a *unique, confident* match. The dataset stores the full
address string (`prop_address_full`, e.g. "481 W DEMING PL"), so a coarse SoQL
`like` prefix is **re-parsed per row** and kept only on an exact
number+direction+name match — this defeats the `481` vs `481`-prefixed-street
collision ("481 W DEMINGWOOD") and unit-suffixed variants of *other* parcels.
No match, an unparseable address, a multi-PIN address (condo / multi-parcel), or
a query error all return None so the caller falls through to the degraded path —
we never pick a parcel arbitrarily.
"""

import logging

import httpx

from backend.config import get_settings
from backend.retrieval.buildings import parse_chicago_address
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

# Addresses are stable; a long TTL keeps the resolver cheap on the request path.
_cache = TTLCache(ttl_seconds=86400, maxsize=2048, name="parcel_addresses")
_NOT_FOUND = object()


async def assessor_address_to_pin(
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Resolve an address to its PIN via Assessor Parcel Addresses (3723-97qp).

    Returns the 14-digit PIN on a unique confident match, else None (no match,
    unparseable, multi-PIN, or query error). No coordinates — the caller resolves
    the parcel centroid from Parcel Universe.
    """
    parsed = parse_chicago_address(address)
    if not parsed:
        return None

    number = parsed["number"]
    direction = parsed["direction"]
    name = parsed["name"]
    name_upper = name.upper()

    key = f"assessor_addr_pin:{number}:{direction}:{name_upper}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    # `prop_address_full` stores the full string with the abbreviated directional
    # ("481 W DEMING PL"). Prefix-match on number+dir+name (a coarse server-side
    # filter), then re-parse each row below to keep only exact-component matches.
    # The dataset is per-YEAR (one address-of-record row per PIN per year); no
    # year equality here — a hard `year=<current>` missed addresses whose rows
    # stop earlier (1425 N Wells St ends at 2001; the parcel was redeveloped).
    # Rows are ordered newest-first and only the newest matching year is used
    # (below), so a re-addressed parcel resolves to its CURRENT mapping and a
    # retired PIN is later rejected by the caller's Parcel Universe centroid
    # requirement (a PIN with no current PU row never becomes identity).
    like = f"{number} {direction} {name_upper}%"
    params = {
        "$select": "pin,prop_address_full,year",
        "$where": (
            f"upper(prop_address_full) like '{like}' "
            # County-wide dataset: scope to Chicago so a same-named suburban
            # street can't collide into a false multi-match or, worse, a unique
            # suburban parcel (same defect class as 78yw-iddh's inc_muni,
            # fixed 2026-07-07).
            "AND upper(prop_address_city_name)='CHICAGO'"
        ),
        "$order": "year DESC",
        "$limit": settings.limit_assessor_addresses,
    }
    try:
        rows = await socrata_get(
            settings.dataset_assessor_addresses,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Assessor address→PIN lookup failed for %r: %s", address, exc)
        return None

    if not rows:
        _cache.set(key, _NOT_FOUND)
        return None

    # Keep only rows whose own address re-parses to the SAME number+direction+name.
    # Numbered streets share a stripped name across suffixes ("87TH ST"/"87TH PL"),
    # so they can still multi-match here → conservative fall-through (same limit as
    # Address Points), never a wrong pick. Matches are bucketed by dataset year and
    # only the NEWEST year with any exact match counts — a parcel re-addressed in
    # 2019 must resolve to the current mapping, not multi-match against its history.
    matches_by_year: dict[str, set[str]] = {}
    for r in rows:
        rp = parse_chicago_address(r.get("prop_address_full", "") or "")
        if not rp:
            continue
        if (
            rp["number"] == number
            and rp["direction"] == direction
            and rp["name"].upper() == name_upper
        ):
            # Exactly 14 digits or it isn't a PIN — never repaired by padding
            # (same corrupt-PIN hazard as Address Points, fixed 2026-07-07).
            cleaned = str(r.get("pin", "")).replace("-", "")
            if len(cleaned) == 14 and cleaned.isdigit():
                year = str(r.get("year", "") or "")
                matches_by_year.setdefault(year, set()).add(cleaned)
    def _year_num(y: str) -> float:
        # The portal renders the year column inconsistently ("2026.0" vs "2025").
        try:
            return float(y)
        except ValueError:
            return float("-inf")

    newest_year = max(matches_by_year, key=_year_num, default=None)
    distinct_pins = (
        matches_by_year[newest_year] if newest_year is not None else set()
    )
    distinct_pins.discard("00000000000000")

    # A confident match is a single distinct PIN. Zero (no exact match survived the
    # re-parse) or multiple (multi-parcel / condo / suffix ambiguity) → not confident.
    if len(distinct_pins) != 1:
        log.info(
            "Assessor address multi/zero-match for %r (%d distinct PINs) — not confident",
            address, len(distinct_pins),
        )
        _cache.set(key, _NOT_FOUND)
        return None

    pin14 = distinct_pins.pop()
    _cache.set(key, pin14)
    return pin14
