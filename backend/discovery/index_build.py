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
import sqlite3
import time
from collections import defaultdict
from typing import Any, Iterable

import httpx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from backend.config import get_settings
from backend.discovery.parcel_index import (
    default_index_path,
    iter_parcel_rows,
    update_parcel_attrs,
    upsert_parcels,
    write_meta,
)
from backend.discovery.registry import load as load_registry
from backend.retrieval.geo import community_area_bounds, community_area_by_point
from backend.retrieval.utils import format_pin
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


def _load_geometry_land(db_path, pin10s: set[str]) -> dict[str, float]:
    """pin10 → polygon land sqft from the local PTAXSIM ``pin_geometry_raw`` table.

    The only all-class land source (CCAO chars is residential-only — before this
    fill, land_sqft was populated on ~4% of e.g. Uptown, starving the Profile's
    area $/ft² benchmark and every land-based Discovery filter/derived field).
    Same source the live profile uses (`property/parcel_geometry.py`); the
    newest boundary per pin10 wins. Returns {} when ptaxsim is absent — the
    build proceeds and `populated_fields` reflects reality.
    """
    from backend.retrieval.property.parcel_geometry import _polygon_area_sqft

    if not pin10s:
        return {}
    out: dict[str, float] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        log.warning("discovery index: pin_geometry unavailable (%s); land fill skipped", exc)
        return {}
    try:
        pins = sorted(pin10s)
        for i in range(0, len(pins), 900):
            chunk = pins[i:i + 900]
            marks = ",".join("?" * len(chunk))
            # ASC + dict-overwrite → the newest end_year's boundary wins.
            for pin10, wkt in conn.execute(
                f"SELECT pin10, geometry FROM pin_geometry_raw "
                f"WHERE pin10 IN ({marks}) AND geometry IS NOT NULL "
                "ORDER BY end_year ASC",
                chunk,
            ):
                parsed = _polygon_area_sqft(wkt)
                if parsed:
                    out[pin10] = parsed[0]
    except sqlite3.Error as exc:
        log.warning("discovery index: pin_geometry scan failed (%s); partial land fill", exc)
    finally:
        conn.close()
    return out


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
    geom_land_sqft: float | None = None,
    zoning_polys: list[tuple[str, Any]],
    tif_polys: Iterable[Any],
    ez_polys: Iterable[Any],
    rail_stations: list[tuple[float, float]],
    neighborhood_ca: int | None,
    as_of: datetime.date,
) -> tuple[str, float, float, dict[str, Any], list[str]]:
    """Pure: assemble one parcel's (pin, lat, lon, attrs, regions) from fetched inputs.

    ``geom_land_sqft`` is the PTAXSIM-polygon land area, filled only into the
    hole CCAO chars leaves (assessor-stated area wins). Callers must pass it
    ONLY for base parcels (PIN suffix 0000) — a condo unit-PIN sharing the
    building's pin10 would otherwise claim the whole lot as its own land,
    polluting land-based filters and the area $/ft² medians.
    """
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
    if attrs.get("land_sqft") is None and geom_land_sqft and geom_land_sqft > 0:
        attrs["land_sqft"] = float(round(geom_land_sqft))

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
                "pin": format_pin(pin_raw),
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


# --- value_percentile shared core (used by both the in-memory pass and the streaming finalize) ---


def _value_ppsf_qualifies(attrs: dict) -> bool:
    """A parcel contributes to / receives a value_percentile only with a qualifying recent sale."""
    ppsf = attrs.get("price_per_sf")
    rec = attrs.get("sale_recency_days")
    return ppsf is not None and ppsf > 0 and rec is not None and rec <= _SALE_RECENCY_MAX_DAYS


def _value_percentile_for(
    attrs: dict,
    ca: int | None,
    ca_ppsf: dict[tuple[int, str], list[float]],
    city_ppsf: dict[str, list[float]],
    *,
    min_peers: int,
) -> int | None:
    """Percentile-rank a parcel's $/sqft among same-use peers, given prebuilt SORTED peer maps.

    Peer set = community_area x land_use; below `min_peers` it widens to citywide x land_use;
    still below → None (NULL, no noise). Pure + deterministic (bisect). Lower = cheaper than peers.
    """
    if not _value_ppsf_qualifies(attrs):
        return None  # no qualifying sale -> NULL (never back-filled from assessment)
    lu = attrs.get("land_use_class")
    if lu is None:
        return None
    ppsf = attrs["price_per_sf"]
    peers = ca_ppsf.get((ca, lu)) if ca is not None else None
    if peers is None or len(peers) < min_peers:
        peers = city_ppsf.get(lu)  # widen to citywide x use
    if peers is None or len(peers) < min_peers:
        return None  # still too thin -> NULL
    rank = bisect.bisect_left(peers, ppsf)  # parcels strictly cheaper than this one
    return round(100 * rank / len(peers))


def _value_ppsf_groups(
    rows: Iterable[tuple],
) -> tuple[dict[tuple[int, str], list[float]], dict[str, list[float]]]:
    """Collect SORTED $/sqft peer maps (community_area x use, and citywide x use) from `rows`.

    Only the floats are held — bounded (~MBs even at ~1.8M parcels) — so this is safe to run over
    a streamed scan of the whole index, not just an in-memory batch.
    """
    ca_ppsf: dict[tuple[int, str], list[float]] = defaultdict(list)
    city_ppsf: dict[str, list[float]] = defaultdict(list)
    for (_pin, _lat, _lon, attrs, regions) in rows:
        if not _value_ppsf_qualifies(attrs):
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
    return ca_ppsf, city_ppsf


def _compute_value_percentile(rows: list[tuple], *, min_peers: int = _VALUE_PERCENTILE_MIN_PEERS) -> None:
    """In-place 2nd pass: percentile-rank each parcel's SALE-based $/sqft among same-use peers.

    Peer set = community_area x land_use among parcels with a qualifying recent sale, so the
    distribution is purely sale-based — assessed $/sqft is never pooled in. Below `min_peers`
    the peer set widens to citywide x land_use; still below, value_percentile stays NULL (no
    noise). Deterministic (sorted + bisect, no clock/RNG). Lower percentile = cheaper than peers.
    """
    ca_ppsf, city_ppsf = _value_ppsf_groups(rows)
    for (_pin, _lat, _lon, attrs, regions) in rows:
        pct = _value_percentile_for(attrs, _ca_of(regions), ca_ppsf, city_ppsf, min_peers=min_peers)
        if pct is not None:
            attrs["value_percentile"] = pct


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


def _recipe_cqs_list() -> list[tuple[str, Any]]:
    """The merged canonical CQS for each prospecting recipe → [(topic_id, cqs)]. Built once."""
    from backend.discovery.compile_merge import merge
    from backend.discovery.cqs import CqsFragment

    registry = load_registry()
    empty = CqsFragment()
    out: list[tuple[str, Any]] = []
    for topic in registry.topics:
        user_frag = CqsFragment.model_validate(
            {"filters": {fid: {"predicate": p, "source": "user"} for fid, p in topic.presets.items()}}
        )
        cqs, _dropped = merge(user_frag, empty, sort=topic.defaultSort)
        out.append((topic.id, cqs))
    return out


def _count_recipes(parcels: list, recipe_cqs: list[tuple[str, Any]], *, version: str) -> dict[str, int]:
    """Evaluate each recipe CQS against `parcels` (registered under `version`) → result counts.

    Recipe counts are row-local (each parcel independently matches a recipe's filters), so a
    caller can sum counts across disjoint parcel partitions — which is how the streaming finalize
    counts the whole index in bounded-memory chunks while reusing the one true `evaluate()`.
    """
    from backend.discovery import parcel as parcel_mod
    from backend.discovery.evaluator import evaluate

    parcel_mod.default_source.register(version, parcels)
    try:
        return {tid: evaluate(cqs, version).total for tid, cqs in recipe_cqs}
    finally:
        parcel_mod.default_source._snapshots.pop(version, None)


def _recipe_counts(rows: list[tuple]) -> dict[str, int]:
    """Evaluate each recipe against the just-built snapshot and count results.

    Stored in meta so the shelf can show "Live · N" / "No matches yet" rather than inferring
    LIVE from field-presence alone — which mislabels a recipe whose FIELDS are populated but
    whose specific subset is empty (e.g. multifamily value_percentile in a thin neighborhood).
    """
    from backend.discovery.parcel_index import IndexedParcel, derive_sort_fields

    recipe_cqs = _recipe_cqs_list()
    if not recipe_cqs:
        return {}
    parcels = [
        IndexedParcel(pin, lat, lon, derive_sort_fields(attrs), regions)
        for (pin, lat, lon, attrs, regions) in rows
    ]
    return _count_recipes(parcels, recipe_cqs, version="__recipe_count__")


async def _assemble_ca(
    ca: int,
    *,
    settings,
    tif_polys,
    ez_polys,
    rail_stations,
    as_of: datetime.date,
    client: httpx.AsyncClient | None,
) -> list[tuple]:
    """Assemble one community area's parcel rows (the per-CA half of a build).

    Pure-ish per-CA work: spine → chunked batch joins → local spatial pass → `assemble_parcel`.
    Returns the CA's row tuples; the caller upserts and drops them, so build memory is bounded by
    one CA, never the whole set. A transient spine failure warns + returns [] (does not abort the
    larger run).
    """
    try:
        spine = await _fetch_spine(ca, client=client)
    except Exception as exc:
        log.warning("discovery index: spine fetch for CA %s failed: %s", ca, exc)
        return []
    if not spine:
        log.info("discovery index: CA %s — no parcels", ca)
        return []
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

    # Geometry land for BASE parcels only (suffix 0000) — see assemble_parcel.
    geom_land: dict[str, float] = {}
    if settings.ptaxsim_enabled and settings.ptaxsim_db_path.exists():
        base10s = {p[:10] for p in pins if p[10:] == "0000"}
        geom_land = _load_geometry_land(settings.ptaxsim_db_path, base10s)

    rows: list[tuple] = []
    for s in spine:
        ca_real = community_area_by_point(s["lat"], s["lon"]) or ca
        pd = s["pin_digits"]
        rows.append(assemble_parcel(
            s, chars.get(pd), assess.get(pd), sales.get(pd),
            address=_address_for(
                pd, s["lat"], s["lon"], addrs, base_addrs, addr_tree, addr_list
            ),
            geom_land_sqft=geom_land.get(pd[:10]) if pd[10:] == "0000" else None,
            zoning_polys=zoning_polys, tif_polys=tif_polys, ez_polys=ez_polys,
            rail_stations=rail_stations, neighborhood_ca=ca_real, as_of=as_of,
        ))
    log.info("discovery index: CA %s — assembled %s parcels", ca, len(rows))
    return rows


# Parcels per chunk in the streaming finalize. Bounds peak memory of the recipe-count pass (which
# materializes a chunk of IndexedParcels) and the value_percentile UPDATE batch — independent of
# total index size.
_FINALIZE_CHUNK = 50_000


def finalize_index(
    path,
    *,
    community_areas: list[int],
    as_of: datetime.date,
    chunk_size: int = _FINALIZE_CHUNK,
) -> tuple[str, int]:
    """Cross-parcel pass + manifest + meta, computed by STREAMING the index (bounded memory).

    Runs after the per-CA upserts. Recomputes the cross-parcel fields over the WHOLE accumulated
    index (so incremental `--community-areas` adds are correct, not just the last batch):
      * value_percentile — collect SORTED $/sqft peer maps (floats only) over a streamed scan,
        then a second streamed pass assigns + persists each parcel's percentile in batches.
      * populated_fields — stream-union of non-null attr keys (drives registry.populatedFields).
      * recipe_counts — `evaluate()` over fixed-size chunks, summed (counts are partition-additive).
    Meta's `community_areas` is the UNION of the existing footprint and the just-built set.
    Returns (data_version, total_parcel_count).
    """
    from backend.discovery.parcel_index import IndexedParcel, derive_sort_fields, read_meta

    # 1) value_percentile — global peer maps (bounded: floats only), assign, then persist.
    # Collect updates while streaming but apply them only AFTER the read cursor is exhausted: a
    # writer on a second connection would otherwise hit "database is locked" mid-scan. Only
    # qualifying parcels (a recent-sale subset) carry an update, so the held set stays small.
    ca_ppsf, city_ppsf = _value_ppsf_groups(iter_parcel_rows(path))
    pct_updates: list[tuple[str, dict]] = []
    for (pin, _lat, _lon, attrs, regions) in iter_parcel_rows(path):
        pct = _value_percentile_for(
            attrs, _ca_of(regions), ca_ppsf, city_ppsf, min_peers=_VALUE_PERCENTILE_MIN_PEERS
        )
        if pct is None:
            continue
        attrs["value_percentile"] = pct
        pct_updates.append((pin, attrs))
    for i in range(0, len(pct_updates), chunk_size):
        update_parcel_attrs(path, pct_updates[i:i + chunk_size])

    # 2) populated_fields (stream union) + recipe_counts (chunked evaluate) over the finalized rows.
    recipe_cqs = _recipe_cqs_list()
    counts = {tid: 0 for tid, _ in recipe_cqs}
    present: set[str] = set()
    has_neighborhood = False
    total = 0
    chunk: list = []
    chunk_idx = 0

    def _flush_chunk() -> None:
        nonlocal chunk_idx
        if recipe_cqs and chunk:
            sub = _count_recipes(chunk, recipe_cqs, version=f"__finalize_{chunk_idx}__")
            for tid, n in sub.items():
                counts[tid] += n
        chunk_idx += 1
        chunk.clear()

    for (pin, lat, lon, attrs, regions) in iter_parcel_rows(path):
        total += 1
        for k, v in attrs.items():
            if v is not None:
                present.add(k)
        if not has_neighborhood and any(r.startswith("neighborhood:") for r in regions):
            has_neighborhood = True
        chunk.append(IndexedParcel(pin, lat, lon, derive_sort_fields(attrs), regions))
        if len(chunk) >= chunk_size:
            _flush_chunk()
    _flush_chunk()

    ids = [f.id for f in load_registry().filters if f.field in present]
    if has_neighborhood:
        ids.append("neighborhood")
    populated = sorted(set(ids))

    # 3) meta — union the just-built CAs with the existing footprint so an incremental add doesn't
    # under-claim coverage (the clobber bug the old write_index had).
    existing = read_meta(path)
    cas = sorted(set(community_areas) | set(existing.community_areas if existing else []))
    built_at = int(time.time())
    data_version = f"idx-{as_of:%Y%m%d}-{built_at}-{total}p"
    written = write_meta(
        path,
        data_version=data_version, built_at=built_at,
        community_areas=cas, populated_fields=populated, recipe_counts=counts,
    )
    log.info(
        "discovery index: finalized %s parcels as %s; CAs %s; populated: %s; recipe counts: %s",
        written, data_version, cas, ", ".join(populated), counts,
    )
    return data_version, written


async def build_index(
    community_areas: list[int],
    *,
    client: httpx.AsyncClient | None = None,
    as_of: datetime.date | None = None,
) -> tuple[str, int]:
    """Build/refresh the index for the given community areas. Returns (data_version, count).

    Memory-bounded by construction: each CA is assembled + upserted then dropped (peak = one CA),
    and the cross-parcel pass + meta are computed by `finalize_index` streaming the SQLite index
    (peak = one chunk + the $/sqft float maps). Safe for `--all`/`--refresh` regardless of total size.
    """
    settings = get_settings()
    as_of = as_of or datetime.date.today()

    # Graceful degradation: a transient failure of a global layer leaves its flag False
    # rather than aborting the whole (possibly 77-CA) build.
    tif_polys = await _safe_polys(_load_tif_boundaries, "TIF", client)
    ez_polys = await _safe_polys(_load_ez_boundaries, "enterprise zone", client)
    rail_stations = _load_rail_stations()

    path = default_index_path()
    for ca in community_areas:
        rows = await _assemble_ca(
            ca, settings=settings, tif_polys=tif_polys, ez_polys=ez_polys,
            rail_stations=rail_stations, as_of=as_of, client=client,
        )
        if rows:
            upsert_parcels(path, rows)
        # rows dropped here — peak build memory is one CA, not the whole set.

    return finalize_index(path, community_areas=community_areas, as_of=as_of)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the Property Discovery prospecting index.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--community-areas", help="comma-separated CA ids, e.g. 22,24")
    g.add_argument("--all", action="store_true", help="all 77 community areas (~1.8M parcels)")
    g.add_argument("--refresh", action="store_true",
                   help="rebuild the community areas already in the current index (for the periodic timer)")
    return ap.parse_args(argv)


def _resolve_cas(args: argparse.Namespace) -> list[int]:
    """CA list from args. --refresh reads the current index's footprint so a scheduled rebuild
    auto-follows the live coverage (no hardcoded CA list to keep in sync)."""
    if args.refresh:
        from backend.discovery.parcel_index import read_meta
        meta = read_meta(default_index_path())
        if not meta or not meta.community_areas:
            raise SystemExit("--refresh: no existing index to refresh — build one first with --community-areas")
        return meta.community_areas
    if args.all:
        return list(range(1, 78))
    return [int(x) for x in args.community_areas.split(",")]


async def _amain(args: argparse.Namespace) -> None:
    cas = _resolve_cas(args)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        data_version, total = await build_index(cas, client=client)
    print(f"Built index {data_version}: {total} parcels across {len(cas)} community area(s)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_amain(_parse_args()))
