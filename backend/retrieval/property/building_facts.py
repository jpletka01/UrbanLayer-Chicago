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


async def get_commercial_facts(
    pin14: str, *, client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Commercial/large-multifamily facts from the CCAO Commercial Valuation
    dataset: {"bldg_sqft", "year_built", "units"} (each possibly None), or None
    when the PIN appears in no economic unit.

    Matched on the dashed PIN via ``keypin`` or membership in ``pins`` (an
    economic unit's keypin row lists all member PINs; one row PER BUILDING per
    valuation year).

    Field semantics (verified live 2026-07-07):
    - bldg_sqft: sum of ``bldgsf`` over the latest valuation year — the economic
      UNIT's building area (provenance "commercial_valuation" discloses this).
    - year_built: from the latest year's principal building (largest bldgsf).
      ~35% populated dataset-wide but ~72% of the coverage panel's year_built
      misses recovered in the audit probe.
    - units: ``tot_units``, filled ONLY when the economic unit is a single PIN —
      a member parcel of a multi-PIN complex would otherwise be asserted to hold
      the whole complex's units (Presidential Towers: 2,346 on every member).
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
                "$where": f"(keypin='{dashed}' OR pins like '%{dashed}%')",
                "$select": "bldgsf,year,yearbuilt,tot_units,pins,keypin",
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

    # Per-FIELD newest year: a valuation vintage can carry yearbuilt/tot_units
    # but a NULL bldgsf (class-318s do) — pinning every field to one "latest"
    # year loses facts an older vintage still holds (six panel parcels lost
    # bldg_sqft that way on the first cut of this function).
    def _year_num(r: dict) -> float:
        try:
            return float(r.get("year") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _newest_rows_with(field: str) -> list[dict]:
        """All rows of the newest valuation year that has `field` populated."""
        best = [r for r in rows if _pos_float(r.get(field))]
        if not best:
            return []
        top = max(map(_year_num, best))
        return [r for r in rows if _year_num(r) == top]

    sqft_rows = _newest_rows_with("bldgsf")
    sqft = sum(_pos_int(r.get("bldgsf")) or 0 for r in sqft_rows) or None

    # Principal building's year: the largest structure is what "built in ..."
    # should describe on a multi-building unit; vintages disagree across rows.
    year_built = None
    for r in sorted(_newest_rows_with("yearbuilt"),
                    key=lambda r: _pos_float(r.get("bldgsf")) or 0.0,
                    reverse=True):
        year_built = _pos_int(r.get("yearbuilt"))
        if year_built:
            break
    if year_built is not None and year_built < 1800:
        year_built = None

    # Units only when every row's member list is exactly this PIN (its year's
    # rows — tot_units describes the whole economic unit).
    def _members(r: dict) -> set[str]:
        raw = str(r.get("pins") or r.get("keypin") or "")
        return {p.strip() for p in raw.split(",") if p.strip()}

    units_rows = _newest_rows_with("tot_units")
    units = None
    if units_rows and all(_members(r) <= {dashed} for r in units_rows):
        units = max((_pos_int(r.get("tot_units")) or 0 for r in units_rows),
                    default=0) or None

    if not (sqft or year_built or units):
        _commercial_cache.set(pin14, _NOT_FOUND)
        return None
    result = {"bldg_sqft": sqft, "year_built": year_built, "units": units}
    _commercial_cache.set(pin14, result)
    return result


def _pip_query_geometry(parcel_geojson: dict, lat: float, lon: float):
    """(shapely polygon, circle radius m covering it) or None on parse failure."""
    try:
        import math

        from shapely.geometry import shape

        poly = shape(parcel_geojson)
        if poly.is_empty:
            return None
        minx, miny, maxx, maxy = poly.bounds
        m_per_deg_lon = 111_320 * math.cos(math.radians(lat))
        corners_m = max(
            math.hypot((cx - lon) * m_per_deg_lon, (cy - lat) * 111_320)
            for cx in (minx, maxx)
            for cy in (miny, maxy)
        )
        # Cover the whole parcel from the query point; bounded for sanity.
        radius = min(max(corners_m + 10, 25), 600)
        return poly, radius
    except Exception as exc:  # noqa: BLE001 — malformed geometry is data, not outage
        log.warning("Parcel geojson parse failed for footprint match: %s", exc)
        return None


async def get_footprint_facts(
    lat: float, lon: float, *,
    parcel_geojson: dict | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Building footprint facts: {"stories", "year_built", "bldg_sqft"} (each
    possibly None) or None when no footprint matches.

    With ``parcel_geojson`` (the PTAXSIM parcel polygon) the match is
    point-in-parcel: only footprints whose own centroid falls INSIDE the parcel
    count. The old fixed 25 m circle around the Parcel Universe centroid missed
    large parcels entirely (centroid >25 m from any structure) and widening it
    would grab a neighbor's building on ~7.6 m-wide lots (2026-07-07 audit).
    Without a polygon the legacy 25 m nearest-circle behavior stands.

    Chicago's footprint layer is city-maintained with uneven freshness; values
    from here carry the "footprint" provenance label.
    """
    pip = _pip_query_geometry(parcel_geojson, lat, lon) if parcel_geojson else None
    key = f"{round(lat, 5)}:{round(lon, 5)}:{'pip' if pip else 'r25'}"
    cached = _footprint_cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    radius = round(pip[1]) if pip else 25
    select = "stories,year_built,bldg_sq_fo,bldg_statu"
    if pip:
        select += ",the_geom"

    settings = get_settings()
    try:
        rows = await socrata_get(
            DATASET_BUILDING_FOOTPRINTS,
            {
                "$where": f"within_circle(the_geom, {lat}, {lon}, {radius})",
                "$select": select,
                "$limit": 25 if pip else 5,
            },
            client=client,
            base_url=settings.socrata_base,
            app_token=settings.socrata_app_token or None,
        )
    except Exception as exc:
        log.warning("Building footprint lookup failed at (%s, %s): %s", lat, lon, exc)
        return None

    if pip:
        from shapely.geometry import shape

        poly = pip[0]
        contained = []
        for r in rows or []:
            try:
                fp = shape(r["the_geom"])
                # The footprint's own interior point must be in the parcel — a
                # neighbor's abutting footprint touches the lot line but its
                # center doesn't cross it.
                if poly.contains(fp.representative_point()):
                    contained.append(r)
            except Exception:  # noqa: BLE001 — skip malformed footprint rows
                continue
        rows = contained

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
