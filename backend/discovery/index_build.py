"""Offline prospecting-index builder (strategy Part B).

Builds the PIN-keyed parcel snapshot `parcel_source` loads. Bounded by community area so
it is runnable + testable now (`--community-areas 24`); `--all` scales to the full ~1.8M set.

Per community area: spine (Parcel Universe) → chunked batch joins (characteristics /
assessments / sales) → a *local* spatial pass over preloaded shapely layers (TIF, EZ, that
CA's zoning polygons, community-area polygons) → per-parcel field assembly → upsert. The
per-parcel assembly (`assemble_parcel`) is a pure function of already-fetched data + loaded
layers, so it is unit-tested without network. Only the MVP + free-byproduct fields are
populated (see the plan / strategy doc); everything else stays NULL → `unknownPolicy`.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import time
from typing import Any, Iterable

import httpx
from shapely.geometry import Point, shape

from backend.config import get_settings
from backend.discovery.parcel_index import default_index_path, write_index
from backend.retrieval.explore import _format_pin
from backend.retrieval.geo import community_area_bounds, community_area_by_point
from backend.retrieval.incentives.enterprise_zones import _load_ez_boundaries
from backend.retrieval.incentives.tif import _load_tif_boundaries
from backend.retrieval.socrata import socrata_get
from backend.retrieval.zoning import zoning_polygons_for_map
from backend.retrieval.zoning_definitions import get_zone_definition

log = logging.getLogger(__name__)

_BATCH = 100  # PINs per chunked `pin in (...)` join query

_LAND_USE_BY_PREFIX = {
    "0": "exempt", "1": "vacant", "2": "residential",
    "3": "multi_family", "5": "commercial", "6": "industrial",
}


# --- pure field derivations --------------------------------------------------


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _land_use(class_code: str | None) -> str | None:
    return _LAND_USE_BY_PREFIX.get((class_code or "").strip()[:1])


def _is_vacant(class_code: str | None) -> bool:
    return (class_code or "").strip().startswith("1")


def _zoning_group(zone_class: str | None) -> str | None:
    z = (zone_class or "").upper().strip()
    if not z:
        return None
    if z.startswith("PMD"):
        return "manufacturing"
    if z.startswith("PD"):
        return "planned_development"
    head = z[0]
    return {
        "R": "residential", "B": "business", "C": "commercial",
        "M": "manufacturing", "D": "downtown",
    }.get(head)


def _recency_days(sale_date: str | None, as_of: datetime.date) -> int | None:
    if not sale_date:
        return None
    try:
        d = datetime.date.fromisoformat(str(sale_date)[:10])
    except ValueError:
        return None
    return (as_of - d).days


def _point_in_any(polys: Iterable[Any], lat: float, lon: float) -> bool:
    point = Point(lon, lat)
    return any(poly.contains(point) for poly in polys)


def _zone_at(zoning_polys: list[tuple[str, Any]], lat: float, lon: float) -> str | None:
    point = Point(lon, lat)
    for zone_class, poly in zoning_polys:
        if poly.contains(point):
            return zone_class
    return None


def assemble_parcel(
    spine: dict,
    chars: dict | None,
    assess: dict | None,
    sale: dict | None,
    *,
    zoning_polys: list[tuple[str, Any]],
    tif_polys: Iterable[Any],
    ez_polys: Iterable[Any],
    neighborhood_ca: int | None,
    as_of: datetime.date,
) -> tuple[str, float, float, dict[str, Any], list[str]]:
    """Pure: assemble one parcel's (pin, lat, lon, attrs, regions) from fetched inputs."""
    lat, lon = spine["lat"], spine["lon"]
    cls = spine.get("class", "")

    attrs: dict[str, Any] = {
        "land_use_class": _land_use(cls),
        "is_vacant": _is_vacant(cls),
    }

    if chars:
        attrs["land_sqft"] = _num(chars.get("char_land_sf"))
        attrs["bldg_sqft"] = _num(chars.get("char_bldg_sf"))
        attrs["year_built"] = _int(chars.get("char_yrblt"))
        attrs["units"] = _int(chars.get("char_apts"))

    if assess:
        attrs["total_assessed_value"] = _num(
            assess.get("mailed_tot") or assess.get("certified_tot") or assess.get("board_tot")
        )
        bldg = _num(assess.get("mailed_bldg") or assess.get("certified_bldg"))
        land = _num(assess.get("mailed_land") or assess.get("certified_land"))
        if bldg is not None and land:
            attrs["improvement_ratio"] = round(bldg / land, 4)

    if sale:
        price = _num(sale.get("sale_price"))
        attrs["last_sale_price"] = price
        attrs["sale_recency_days"] = _recency_days(sale.get("sale_date"), as_of)
        bsf = attrs.get("bldg_sqft")
        if price and bsf:
            attrs["price_per_sf"] = round(price / bsf, 2)

    # Local spatial pass (no per-parcel API calls).
    attrs["in_tif_district"] = _point_in_any(tif_polys, lat, lon)
    attrs["in_enterprise_zone"] = _point_in_any(ez_polys, lat, lon)
    zone = _zone_at(zoning_polys, lat, lon)
    if zone:
        attrs["zoning_group"] = _zoning_group(zone)
        zdef = get_zone_definition(zone)
        attrs["density_band"] = zdef.far if zdef else None

    regions = [f"neighborhood:{neighborhood_ca}"] if neighborhood_ca is not None else []
    return spine["pin"], lat, lon, attrs, regions


# --- async orchestration -----------------------------------------------------


def _chunks(seq: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


async def _safe_polys(loader, label: str, client) -> list[Any]:
    """Load a global shapely layer's polygons, returning [] (and warning) on failure."""
    try:
        return [b[2] for b in await loader(client=client)]
    except Exception as exc:
        log.warning("discovery index: %s layer unavailable (%s); its flag stays False", label, exc)
        return []


async def _fetch_spine(ca: int, *, client: httpx.AsyncClient | None) -> list[dict]:
    bounds = community_area_bounds(ca)
    if bounds is None:
        return []
    settings = get_settings()
    min_lat, min_lon, max_lat, max_lon = bounds
    where = (
        f"lat between '{min_lat}' and '{max_lat}' and lon between '{min_lon}' and '{max_lon}'"
    )
    out: list[dict] = []
    offset, page = 0, 50000
    while True:
        rows = await socrata_get(
            settings.dataset_ccao_parcels,
            {"$select": "pin,class,lat,lon", "$where": where, "$order": "pin",
             "$limit": page, "$offset": offset},
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not rows:
            break
        for r in rows:
            pin_raw = (r.get("pin") or "").replace("-", "")
            lat, lon = r.get("lat"), r.get("lon")
            if not pin_raw or lat is None or lon is None:
                continue
            out.append({
                "pin": _format_pin(pin_raw),
                "pin_digits": pin_raw.zfill(14),
                "class": r.get("class", ""),
                "lat": float(lat),
                "lon": float(lon),
            })
        if len(rows) < page:
            break
        offset += page
    return out


async def _batch_latest(
    dataset: str, pins: list[str], order_field: str, client, settings
) -> dict[str, dict]:
    """Latest row per PIN across chunked `pin in (...)` queries (DESC + first-seen wins)."""
    out: dict[str, dict] = {}
    for chunk in _chunks(pins, _BATCH):
        in_list = ",".join(f"'{p}'" for p in chunk)
        try:
            rows = await socrata_get(
                dataset,
                {"$where": f"pin in ({in_list})", "$order": f"{order_field} DESC", "$limit": 50000},
                client=client,
                base_url=settings.cook_county_socrata_base,
                app_token=settings.cook_county_socrata_token or None,
            )
        except Exception as exc:
            log.warning("discovery index: batch join %s failed: %s", dataset, exc)
            continue
        for r in rows:
            p = r.get("pin")
            if p and p not in out:
                out[p] = r
    return out


def _zoning_index(fc: dict) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for feat in fc.get("features", []):
        zc = (feat.get("properties") or {}).get("ZONE_CLASS")
        geom = feat.get("geometry")
        if zc and geom:
            try:
                out.append((zc, shape(geom)))
            except Exception:
                continue
    return out


async def build_index(
    community_areas: list[int],
    *,
    client: httpx.AsyncClient | None = None,
    as_of: datetime.date | None = None,
) -> tuple[str, int]:
    """Build/refresh the index for the given community areas. Returns (data_version, count)."""
    settings = get_settings()
    as_of = as_of or datetime.date.today()

    # Graceful degradation: a transient failure of a global layer leaves its flag False
    # rather than aborting the whole (possibly 77-CA) build.
    tif_polys = await _safe_polys(_load_tif_boundaries, "TIF", client)
    ez_polys = await _safe_polys(_load_ez_boundaries, "enterprise zone", client)

    rows: list[tuple] = []
    for ca in community_areas:
        try:
            spine = await _fetch_spine(ca, client=client)
        except Exception as exc:
            log.warning("discovery index: spine fetch for CA %s failed: %s", ca, exc)
            continue
        if not spine:
            log.info("discovery index: CA %s — no parcels", ca)
            continue
        pins = [s["pin_digits"] for s in spine]
        chars = await _batch_latest(settings.dataset_ccao_characteristics, pins, "year", client, settings)
        assess = await _batch_latest(settings.dataset_ccao_assessments, pins, "year", client, settings)
        sales = await _batch_latest(settings.dataset_ccao_sales, pins, "sale_date", client, settings)
        zoning_polys = _zoning_index(await zoning_polygons_for_map(ca, client=client))

        for s in spine:
            ca_real = community_area_by_point(s["lat"], s["lon"]) or ca
            rows.append(assemble_parcel(
                s, chars.get(s["pin_digits"]), assess.get(s["pin_digits"]), sales.get(s["pin_digits"]),
                zoning_polys=zoning_polys, tif_polys=tif_polys, ez_polys=ez_polys,
                neighborhood_ca=ca_real, as_of=as_of,
            ))
        log.info("discovery index: CA %s — assembled %s parcels", ca, len(spine))

    built_at = int(time.time())
    data_version = f"idx-{as_of:%Y%m%d}-{built_at}-{len(rows)}p"
    total = write_index(
        default_index_path(),
        data_version=data_version, built_at=built_at,
        community_areas=community_areas, rows=rows,
    )
    log.info("discovery index: wrote %s parcels (total %s) as %s", len(rows), total, data_version)
    return data_version, total


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the Property Discovery prospecting index.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--community-areas", help="comma-separated CA ids, e.g. 22,24")
    g.add_argument("--all", action="store_true", help="all 77 community areas (~1.8M parcels)")
    return ap.parse_args(argv)


async def _amain(args: argparse.Namespace) -> None:
    cas = list(range(1, 78)) if args.all else [int(x) for x in args.community_areas.split(",")]
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        data_version, total = await build_index(cas, client=client)
    print(f"Built index {data_version}: {total} parcels across {len(cas)} community area(s)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_amain(_parse_args()))
