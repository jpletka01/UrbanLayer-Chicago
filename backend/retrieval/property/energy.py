"""Chicago Energy Benchmarking (``xq83-jr8c``) — buildings ≥ 50,000 sq ft.

Covered buildings must report annually; the dataset carries the city's 0–4
Chicago Energy Rating placard, the ENERGY STAR score, self-reported gross
floor area, year built, and energy-use intensity. Two roles here:

- **CRE opex facts** for large buildings (rating / ENERGY STAR / site EUI /
  GHG intensity — direct operating-cost context for a buyer).
- **Building-sqft and year-built fill** for the ≥50k-sqft segment, where the
  assessor characteristics dataset has nothing (it covers regression-class
  residential only). Fill-only, provenance ``energy_benchmark``.

No PIN column — matched spatially like the footprints layer, nearest point
within ~40 m. ``chicago_energy_rating`` is "0" on non-submitting rows: that is
a compliance placeholder, not a performance score (``not_submitted``).
"""

from __future__ import annotations

import logging
import math

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=86400, maxsize=256, name="energy_benchmark")
_NOT_FOUND = object()

DATASET_ENERGY_BENCHMARKING = "xq83-jr8c"
MATCH_RADIUS_M = 40


def _f(val) -> float | None:
    try:
        n = float(val)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _pos_int(val) -> int | None:
    try:
        n = int(float(val))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _dist_sq(row: dict, lat: float, lon: float) -> float:
    rlat, rlon = _f(row.get("latitude")), _f(row.get("longitude"))
    if rlat is None or rlon is None:
        return float("inf")
    # Planar comparison is fine at 40 m scale; cos-lat scales the lon axis.
    dlon = (rlon - lon) * math.cos(math.radians(lat))
    return (rlat - lat) ** 2 + dlon**2


async def get_energy_benchmark(
    lat: float, lon: float, *, client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Latest benchmarking facts for the property at this point, or None.

    Not being in the dataset is the normal state for <50k-sqft buildings —
    an expected absence, never a data gap.
    """
    key = f"{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    settings = get_settings()
    try:
        rows = await socrata_get(
            DATASET_ENERGY_BENCHMARKING,
            {
                "$where": f"within_circle(location, {lat}, {lon}, {MATCH_RADIUS_M})",
                "$select": (
                    "id,data_year,reporting_status,chicago_energy_rating,"
                    "energy_star_score,gross_floor_area_buildings_sq_ft,"
                    "year_built,primary_property_type,site_eui_kbtu_sq_ft,"
                    "ghg_intensity_kg_co2e_sq_ft,latitude,longitude"
                ),
                "$order": "data_year DESC",
                "$limit": 40,
            },
            client=client,
            base_url=settings.socrata_base,
            app_token=settings.socrata_app_token or None,
        )
    except Exception as exc:
        log.warning("Energy benchmarking lookup failed at (%s, %s): %s", lat, lon, exc)
        return None

    if not rows:
        _cache.set(key, _NOT_FOUND)
        return None

    # One property (id) reports across many data_years; adjacent towers can
    # both fall inside the circle — keep only the nearest property id.
    nearest_id = min(rows, key=lambda r: _dist_sq(r, lat, lon)).get("id")
    mine = [r for r in rows if r.get("id") == nearest_id]
    # Prefer the latest SUBMITTED year (it carries the performance columns);
    # fall back to the latest row so the compliance state still surfaces.
    # Status is "Submitted" OR "Submitted Data" (both live in the dataset).
    def _is_submitted(r: dict) -> bool:
        return str(r.get("reporting_status") or "").startswith("Submitted")

    submitted = [r for r in mine if _is_submitted(r)]
    row = submitted[0] if submitted else mine[0]

    rating = _f(row.get("chicago_energy_rating"))
    not_submitted = not _is_submitted(row)
    result = {
        "chicago_energy_rating": rating if rating and rating > 0 else None,
        "energy_star_score": _pos_int(row.get("energy_star_score")),
        "gross_floor_area": _pos_int(row.get("gross_floor_area_buildings_sq_ft")),
        "year_built": _pos_int(row.get("year_built")),
        "primary_property_type": row.get("primary_property_type") or None,
        "site_eui": _f(row.get("site_eui_kbtu_sq_ft")),
        "ghg_intensity": _f(row.get("ghg_intensity_kg_co2e_sq_ft")),
        "data_year": _pos_int(row.get("data_year")),
        "not_submitted": not_submitted,
    }
    _cache.set(key, result)
    return result
