"""FAR-normalized comparable sales — price per buildable square foot.

Two lots that sold for the same price per land square foot are not comparable if one
is zoned RS-3 (FAR 0.9) and the other B3-2 (FAR 2.2): the second carries almost two
and a half times the buildable area for the same dirt. Developers therefore price land
per *buildable* foot, not per land foot, and the 2026-08-17 market analysis flags
density-normalized comps as a real analytical gap that raw Cook County comps don't fill.

    price_per_buildable_sqft = sale_price / (land_sqft * FAR)

Everything needed is already on hand, so this costs one extra request:

- comps already carry ``sale_price``, ``land_sqft`` and coordinates (``sales.py``);
- ``zoning_polygons_near`` already returns a GeoJSON quilt of zoning districts with
  ``ZONE_CLASS`` (it backs the Profile's zoning map);
- ``zoning_definitions.get_zone_definition`` is the deterministic Title-17 FAR table.

So each comp's district is a local point-in-polygon against the quilt — no per-comp
network call.

**Land area is the binding constraint, and it is filled here.** CCAO characteristics is
residential-only, so most comps arrive with ``land_sqft`` null — which is the same
"missing comp land-area" that has blocked land-value work before. The lot-info arc added
an all-class source for exactly this: ptaxsim ``pin_geometry_raw`` polygons, read locally
in milliseconds by ``parcel_geometry.get_parcel_geometry_facts``. Missing land areas are
backfilled from it for **base PINs only** (suffix ``0000``); a condo unit-PIN must never
claim its whole building's lot, the same guard the Discovery index build applies. Filled
values are marked ``land_sqft_source="geometry"`` and only ever fill a null — an existing
figure is never overwritten.

**What this is NOT.** The metric is a LAND basis. When a comp sold with a building on
it, the price includes that building, so its price-per-buildable-foot overstates land
value. `sale_type` is three-state (`sales.py`): "LAND", "LAND AND BUILDING", or None for
unknown — the characteristics dataset is residential-only, so most non-residential comps
are genuinely unknown. Rather than silently mixing, the per-comp figure is computed
wherever the inputs exist and the SUMMARY median is computed over land-only comps,
falling back to all priced comps with `median_basis` saying which happened. A reader can
always tell what the median is made of.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from typing import Any

import httpx

from backend.retrieval.property.parcel_geometry import get_parcel_geometry_facts
from backend.retrieval.zoning import zoning_polygons_near
from backend.retrieval.zoning_definitions import get_zone_definition

log = logging.getLogger(__name__)

# The quilt must cover the comps, which reach ~0.55 mi once the comp search widens.
# Sized from the comps actually returned, with margin, and capped so a stray far-flung
# comp can't demand a giant ArcGIS envelope.
QUILT_MARGIN_MI = 0.1
QUILT_MIN_MI = 0.25
QUILT_MAX_MI = 0.8


def _f(val) -> float | None:
    try:
        f = float(val)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _quilt_radius_mi(sales: list[dict]) -> float:
    dists = [d for s in sales if (d := _f(s.get("distance_mi"))) is not None]
    if not dists:
        return QUILT_MIN_MI
    return max(QUILT_MIN_MI, min(QUILT_MAX_MI, max(dists) + QUILT_MARGIN_MI))


def _zone_index(fc: dict) -> list[tuple[Any, str]]:
    """(shapely geometry, ZONE_CLASS) pairs from the zoning GeoJSON."""
    try:
        from shapely.geometry import shape
    except Exception:  # pragma: no cover - shapely is a hard dep in practice
        return []

    out: list[tuple[Any, str]] = []
    for feat in (fc or {}).get("features") or []:
        zone = ((feat.get("properties") or {}).get("ZONE_CLASS") or "").strip()
        geom = feat.get("geometry")
        if not zone or not geom:
            continue
        try:
            out.append((shape(geom), zone))
        except Exception:
            continue
    return out


async def _fill_missing_land_area(sales: list[dict]) -> None:
    """Backfill null ``land_sqft`` from the local ptaxsim parcel polygons.

    Base PINs only: a condo unit-PIN shares its building's footprint, so filling it
    would hand every unit the whole lot and badly understate price per buildable foot.
    """
    targets = [
        s for s in sales
        if not _f(s.get("land_sqft"))
        and (pin := str(s.get("pin") or "").replace("-", ""))
        and pin.endswith("0000")
    ]
    if not targets:
        return

    results = await asyncio.gather(
        *(get_parcel_geometry_facts(str(s["pin"])) for s in targets),
        return_exceptions=True,
    )
    for sale, res in zip(targets, results):
        if isinstance(res, Exception) or not res:
            continue
        area = res.get("land_sqft_geom")
        if area and area > 0:
            sale["land_sqft"] = int(area)
            sale["land_sqft_source"] = "geometry"


def _zone_at(index: list[tuple[Any, str]], lat: float, lon: float) -> str | None:
    if not index:
        return None
    try:
        from shapely.geometry import Point
    except Exception:  # pragma: no cover
        return None
    pt = Point(lon, lat)
    for geom, zone in index:
        try:
            if geom.contains(pt):
                return zone
        except Exception:
            continue
    return None


async def annotate_far_normalized(
    comps: dict[str, Any],
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Add zone/FAR/price-per-buildable-sqft to each comp and to the summary.

    Mutates and returns the ``{"summary": ..., "sales": [...]}`` dict from
    ``nearby_comparable_sales``. Always degrades quietly: a failed quilt fetch or a
    zone with no published FAR simply leaves the new fields None.
    """
    source_sales = (comps or {}).get("sales") or []
    if not source_sales:
        return comps

    # Work on copies. `nearby_comparable_sales` returns a CACHED dict, and mutating it
    # in place leaks annotations back into the cache: the second request finds
    # land_sqft already filled, so `land_sqft_source` never gets set and the same
    # parcel reports different provenance on a cache hit than on a miss.
    comps = dict(comps)
    sales = [dict(s) for s in source_sales]
    comps["sales"] = sales
    comps["summary"] = dict(comps.get("summary") or {})

    try:
        fc = await zoning_polygons_near(
            lat, lon, radius_mi=_quilt_radius_mi(sales), client=client,
        )
    except Exception as exc:
        log.warning("FAR normalization skipped (zoning quilt failed): %s", exc)
        return comps

    index = _zone_index(fc)
    if not index:
        return comps

    await _fill_missing_land_area(sales)

    per_buildable_land_only: list[float] = []
    per_buildable_all: list[float] = []

    for s in sales:
        s_lat, s_lon = _f(s.get("lat")), _f(s.get("lon"))
        if s_lat is None or s_lon is None or (s_lat == 0 and s_lon == 0):
            continue
        zone = _zone_at(index, s_lat, s_lon)
        if not zone:
            continue
        s["zone_class"] = zone

        far = get_zone_definition(zone).far
        if far is None or far <= 0:
            # PDs and a few districts publish no FAR — honest gap, not a zero.
            continue
        s["far"] = far

        price = _f(s.get("sale_price"))
        land = _f(s.get("land_sqft"))
        if not price or not land or land <= 0:
            continue

        ppbf = round(price / (land * far), 2)
        s["price_per_buildable_sqft"] = ppbf
        per_buildable_all.append(ppbf)
        if s.get("sale_type") == "LAND":
            per_buildable_land_only.append(ppbf)

    summary = comps["summary"]
    if per_buildable_land_only:
        summary["median_price_per_buildable_sqft"] = round(
            statistics.median(per_buildable_land_only), 2
        )
        summary["buildable_median_basis"] = "land_only"
        summary["buildable_median_n"] = len(per_buildable_land_only)
    elif per_buildable_all:
        # No vacant-land comps in the set. Still useful, but the median now includes
        # improved sales whose price carries a building — say so rather than imply
        # a clean land basis.
        summary["median_price_per_buildable_sqft"] = round(
            statistics.median(per_buildable_all), 2
        )
        summary["buildable_median_basis"] = "mixed"
        summary["buildable_median_n"] = len(per_buildable_all)

    return comps
