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
import bisect
import datetime
import json
import logging
import math
import time
from collections import defaultdict
from typing import Any, Iterable

import httpx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from backend.config import get_settings
from backend.discovery.parcel_index import default_index_path, write_index
from backend.discovery.registry import load as load_registry
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


def _format_class(class_code: str | None) -> str | None:
    """Cook County class code for display: "211" -> "2-11" (major-minor). Raw otherwise."""
    z = (class_code or "").strip()
    if len(z) == 3 and z.isdigit():
        return f"{z[0]}-{z[1:]}"
    return z or None


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


# --- derived "intelligence" fields (round-4 spec) ----------------------------

_TEARDOWN_IMP_SHARE_MAX = 0.25    # building <= 25% of total assessed value -> land play
_SALE_RECENCY_MAX_DAYS = 1095     # "qualifying" sale window for value_percentile (~36 months)
_VALUE_PERCENTILE_MIN_PEERS = 30  # below this, widen to citywide; below that too -> NULL
_UPSIDE_FAR_WEIGHT = 0.6          # v1 heuristic blend (FAR headroom vs land share); tune in PR-VAL
_UPSIDE_LAND_WEIGHT = 0.4


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_rail_mi(rail_stations: list[tuple[float, float]], lat: float, lon: float) -> float | None:
    """Miles to the nearest CTA rail station, or None when no station list is loaded."""
    if not rail_stations:
        return None
    return round(min(_haversine_mi(lat, lon, s_lat, s_lon) for s_lat, s_lon in rail_stations), 2)


def assemble_parcel(
    spine: dict,
    chars: dict | None,
    assess: dict | None,
    sale: dict | None,
    *,
    address: str | None = None,
    zoning_polys: list[tuple[str, Any]],
    tif_polys: Iterable[Any],
    ez_polys: Iterable[Any],
    rail_stations: list[tuple[float, float]],
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
    cls_display = _format_class(cls)  # display-only Cook County class ("2-11"); row-card shows it
    if cls_display:
        attrs["class"] = cls_display
    if address:
        # Display-only street address (Address Points; a "~" prefix marks an approximate
        # nearest-address for parcels with none of their own). Never read by the evaluator.
        attrs["address"] = address
    imp_share: float | None = None  # building's share of total assessed value (0-1), for derived fields

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
            attrs["improvement_ratio"] = round(bldg / land, 4)  # shipped field: building-to-land (unchanged)
        # Building's share of TOTAL value (0-1) — a clean basis for the derived metrics below,
        # independent of improvement_ratio's building-to-land definition (which can exceed 1).
        if bldg is not None and land is not None and (bldg + land) > 0:
            imp_share = bldg / (bldg + land)

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

    # --- derived intelligence fields (value_percentile is a cross-parcel 2nd pass) ---
    rail_mi = _nearest_rail_mi(rail_stations, lat, lon)
    if rail_mi is not None:
        attrs["cta_rail_distance_mi"] = rail_mi

    land_share = (1.0 - imp_share) if imp_share is not None else None
    bsf = attrs.get("bldg_sqft")
    lsf = attrs.get("land_sqft")

    # Teardown candidate: the building is a small share of total value (land dominates) AND a
    # real structure exists. Stored only when determinable; otherwise NULL (excluded by policy).
    if imp_share is not None and bsf and bsf > 0 and attrs.get("year_built") is not None:
        attrs["is_teardown_candidate"] = imp_share <= _TEARDOWN_IMP_SHARE_MAX

    # Redevelopment upside (0-100): unused FAR capacity + land-dominant value. NULL (kept
    # DISTINCT from a low score) when zoning capacity, sizes, or assessment are missing.
    allowed_far = attrs.get("density_band")
    far_headroom = None
    if allowed_far and bsf is not None and lsf and lsf > 0:
        built_far = bsf / lsf
        far_headroom = max(0.0, min(1.0, (allowed_far - built_far) / allowed_far))
    if far_headroom is not None and land_share is not None:
        attrs["upside_score"] = round(
            100 * (_UPSIDE_FAR_WEIGHT * far_headroom + _UPSIDE_LAND_WEIGHT * land_share)
        )

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
    dataset: str, pins: list[str], order_field: str, client, settings, *, where_extra: str | None = None
) -> dict[str, dict]:
    """Latest row per PIN across chunked `pin in (...)` queries (DESC + first-seen wins).

    `where_extra` ANDs an extra predicate into the query — used by the assessment join to skip
    the in-progress assessment year (whose value columns are still null and so are omitted by
    Socrata), so "latest" means the latest year that actually carries values.
    """
    out: dict[str, dict] = {}
    for chunk in _chunks(pins, _BATCH):
        in_list = ",".join(f"'{p}'" for p in chunk)
        where = f"pin in ({in_list})" + (f" AND {where_extra}" if where_extra else "")
        try:
            rows = await socrata_get(
                dataset,
                {"$where": where, "$order": f"{order_field} DESC", "$limit": 50000},
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


async def _fetch_address_points(ca: int, *, client: httpx.AsyncClient | None) -> list[tuple[float, float, str]]:
    """All Address Points in a CA's bounding box as (lon, lat, cmpaddabrv) — for the
    nearest-address fallback that locates parcels (esp. vacant lots) with no address of their own."""
    bounds = community_area_bounds(ca)
    if bounds is None:
        return []
    settings = get_settings()
    min_lat, min_lon, max_lat, max_lon = bounds
    where = f"lat between '{min_lat}' and '{max_lat}' and long between '{min_lon}' and '{max_lon}'"
    out: list[tuple[float, float, str]] = []
    offset, page = 0, 50000
    while True:
        rows = await socrata_get(
            settings.dataset_address_points,
            {"$select": "cmpaddabrv,lat,long", "$where": where, "$order": "objectid",
             "$limit": page, "$offset": offset},
            client=client, base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not rows:
            break
        for r in rows:
            a, la, lo = r.get("cmpaddabrv"), r.get("lat"), r.get("long")
            if a and la is not None and lo is not None:
                try:
                    out.append((float(lo), float(la), a))
                except (TypeError, ValueError):
                    continue
        if len(rows) < page:
            break
        offset += page
    return out


def _address_tree(points: list[tuple[float, float, str]]) -> tuple[STRtree | None, list[str]]:
    """Spatial index of address points → (STRtree of Points, parallel address list)."""
    if not points:
        return None, []
    return STRtree([Point(lon, lat) for lon, lat, _a in points]), [a for _lo, _la, a in points]


def _nearest_address(tree: STRtree | None, addrs: list[str], lat: float, lon: float) -> str | None:
    """Nearest address point's street address, or None when no points are indexed."""
    if tree is None:
        return None
    idx = tree.nearest(Point(lon, lat))
    return addrs[idx] if idx is not None else None


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


def _load_rail_stations() -> list[tuple[float, float]]:
    """CTA rail station coords from transit_stations.json (built by `build_transit_stations`)."""
    path = get_settings().data_dir / "transit_stations.json"
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        log.warning(
            "discovery index: transit stations unavailable (%s); cta_rail_distance_mi stays NULL", exc
        )
        return []
    return [
        (s["lat"], s["lon"])
        for s in data
        if s.get("type") == "cta_rail" and s.get("lat") is not None and s.get("lon") is not None
    ]


def _resolve_address(pin_digits: str, exact: dict[str, dict], base: dict[str, dict]) -> dict | None:
    """A parcel's Address Points row, else its building's (base PIN = 10-digit prefix + 0000).

    Condo unit-PINs (suffix != 0000) usually have no address point of their own; falling back
    to the building's base PIN recovers the building street address instead of a bare PIN
    (~72% of the otherwise-unaddressed parcels in dense condo neighborhoods).
    """
    a = exact.get(pin_digits)
    if a and (a.get("cmpaddabrv") or a.get("addrdeliv")):
        return a
    return base.get(pin_digits[:10] + "0000")


def _address_for(
    pin_digits: str, lat: float, lon: float,
    exact: dict[str, dict], base: dict[str, dict], tree: STRtree | None, addrs: list[str],
) -> str | None:
    """Final display address: own/building Address Point, else the nearest one prefixed "~"
    (approximate — used for vacant lots & parcels with no assigned address; the nearest point
    is typically the adjacent frontage, ~30 ft away)."""
    a = _resolve_address(pin_digits, exact, base)
    if a:
        return a.get("cmpaddabrv") or a.get("addrdeliv")
    near = _nearest_address(tree, addrs, lat, lon)
    return f"~{near}" if near else None


def _ca_of(regions: list[str]) -> int | None:
    for r in regions:
        if r.startswith("neighborhood:"):
            try:
                return int(r.split(":", 1)[1])
            except ValueError:
                return None
    return None


def _compute_value_percentile(rows: list[tuple], *, min_peers: int = _VALUE_PERCENTILE_MIN_PEERS) -> None:
    """In-place 2nd pass: percentile-rank each parcel's SALE-based $/sqft among same-use peers.

    Peer set = community_area x land_use among parcels with a qualifying recent sale, so the
    distribution is purely sale-based — assessed $/sqft is never pooled in. Below `min_peers`
    the peer set widens to citywide x land_use; still below, value_percentile stays NULL (no
    noise). Deterministic (sorted + bisect, no clock/RNG). Lower percentile = cheaper than peers.
    """

    def qualifies(attrs: dict) -> bool:
        ppsf = attrs.get("price_per_sf")
        rec = attrs.get("sale_recency_days")
        return ppsf is not None and ppsf > 0 and rec is not None and rec <= _SALE_RECENCY_MAX_DAYS

    ca_ppsf: dict[tuple[int, str], list[float]] = defaultdict(list)
    city_ppsf: dict[str, list[float]] = defaultdict(list)
    for (_pin, _lat, _lon, attrs, regions) in rows:
        if not qualifies(attrs):
            continue
        lu = attrs.get("land_use_class")
        if lu is None:
            continue
        ppsf = attrs["price_per_sf"]
        city_ppsf[lu].append(ppsf)
        ca = _ca_of(regions)
        if ca is not None:
            ca_ppsf[(ca, lu)].append(ppsf)

    for grp in ca_ppsf.values():
        grp.sort()
    for grp in city_ppsf.values():
        grp.sort()

    for (_pin, _lat, _lon, attrs, regions) in rows:
        if not qualifies(attrs):
            continue  # no qualifying sale -> NULL (never back-filled from assessment)
        lu = attrs.get("land_use_class")
        if lu is None:
            continue
        ppsf = attrs["price_per_sf"]
        ca = _ca_of(regions)
        peers = ca_ppsf.get((ca, lu)) if ca is not None else None
        if peers is None or len(peers) < min_peers:
            peers = city_ppsf.get(lu)  # widen to citywide x use
        if peers is None or len(peers) < min_peers:
            continue  # still too thin -> NULL
        rank = bisect.bisect_left(peers, ppsf)  # parcels strictly cheaper than this one
        attrs["value_percentile"] = round(100 * rank / len(peers))


def _populated_fields(rows: list[tuple]) -> list[str]:
    """Filter ids this build actually populated (>=1 non-null value) — drives registry.populatedFields.

    Derived from the assembled data, so a field that degraded to NULL everywhere (e.g. a thin
    `value_percentile`) is automatically OMITTED — its recipe then shows NEEDS-DATA rather than
    silently returning 0, and the rest read "coming with the next data update".
    """
    present: set[str] = set()
    has_neighborhood = False
    for (_pin, _lat, _lon, attrs, regions) in rows:
        for k, v in attrs.items():
            if v is not None:
                present.add(k)
        if not has_neighborhood and any(r.startswith("neighborhood:") for r in regions):
            has_neighborhood = True
    ids = [f.id for f in load_registry().filters if f.field in present]
    if has_neighborhood:
        ids.append("neighborhood")
    return sorted(set(ids))


def _recipe_counts(rows: list[tuple]) -> dict[str, int]:
    """Evaluate each recipe against the just-built snapshot and count results.

    Stored in meta so the shelf can show "Live · N" / "No matches yet" rather than inferring
    LIVE from field-presence alone — which mislabels a recipe whose FIELDS are populated but
    whose specific subset is empty (e.g. multifamily value_percentile in a thin neighborhood).
    """
    from backend.discovery import parcel as parcel_mod
    from backend.discovery.compile_merge import merge
    from backend.discovery.cqs import CqsFragment
    from backend.discovery.evaluator import evaluate
    from backend.discovery.parcel_index import IndexedParcel, derive_sort_fields

    registry = load_registry()
    if not registry.topics:
        return {}
    parcels = [
        IndexedParcel(pin, lat, lon, derive_sort_fields(attrs), regions)
        for (pin, lat, lon, attrs, regions) in rows
    ]
    version = "__recipe_count__"
    parcel_mod.default_source.register(version, parcels)
    try:
        counts: dict[str, int] = {}
        empty = CqsFragment()
        for topic in registry.topics:
            user_frag = CqsFragment.model_validate(
                {"filters": {fid: {"predicate": p, "source": "user"} for fid, p in topic.presets.items()}}
            )
            cqs, _dropped = merge(user_frag, empty, sort=topic.defaultSort)
            counts[topic.id] = evaluate(cqs, version).total
        return counts
    finally:
        parcel_mod.default_source._snapshots.pop(version, None)


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
    rail_stations = _load_rail_stations()

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
        assess = await _batch_latest(
            settings.dataset_ccao_assessments, pins, "year", client, settings,
            # Skip the in-progress assessment year (value columns still null → omitted by Socrata);
            # take the latest year that actually has a total value.
            where_extra="(mailed_tot IS NOT NULL OR certified_tot IS NOT NULL OR board_tot IS NOT NULL)",
        )
        sales = await _batch_latest(settings.dataset_ccao_sales, pins, "sale_date", client, settings)
        addrs = await _batch_latest(settings.dataset_address_points, pins, "objectid", client, settings)
        # Building-address fallback for unaddressed (mostly condo unit) PINs: join the base PINs
        # (10-digit prefix + 0000) for the misses; deduped to buildings, so far fewer queries.
        base_pins = sorted({p[:10] + "0000" for p in pins if not (addrs.get(p) or {}).get("cmpaddabrv")})
        base_addrs = (
            await _batch_latest(settings.dataset_address_points, base_pins, "objectid", client, settings)
            if base_pins else {}
        )
        addr_tree, addr_list = _address_tree(await _fetch_address_points(ca, client=client))
        zoning_polys = _zoning_index(await zoning_polygons_for_map(ca, client=client))

        for s in spine:
            ca_real = community_area_by_point(s["lat"], s["lon"]) or ca
            rows.append(assemble_parcel(
                s, chars.get(s["pin_digits"]), assess.get(s["pin_digits"]), sales.get(s["pin_digits"]),
                address=_address_for(
                    s["pin_digits"], s["lat"], s["lon"], addrs, base_addrs, addr_tree, addr_list
                ),
                zoning_polys=zoning_polys, tif_polys=tif_polys, ez_polys=ez_polys,
                rail_stations=rail_stations, neighborhood_ca=ca_real, as_of=as_of,
            ))
        log.info("discovery index: CA %s — assembled %s parcels", ca, len(spine))

    # Cross-parcel pass + the field-readiness manifest (drives coverage / populatedFields) +
    # per-recipe result counts (drives honest "Live · N" / "No matches yet" shelf badges).
    _compute_value_percentile(rows)
    populated = _populated_fields(rows)
    recipe_counts = _recipe_counts(rows)

    built_at = int(time.time())
    data_version = f"idx-{as_of:%Y%m%d}-{built_at}-{len(rows)}p"
    total = write_index(
        default_index_path(),
        data_version=data_version, built_at=built_at,
        community_areas=community_areas, rows=rows,
        populated_fields=populated, recipe_counts=recipe_counts,
    )
    log.info(
        "discovery index: wrote %s parcels (total %s) as %s; populated: %s; recipe counts: %s",
        len(rows), total, data_version, ", ".join(populated), recipe_counts,
    )
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
