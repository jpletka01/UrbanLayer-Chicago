"""The Profile's block capacity map: how much of the allowed floor area is built, parcel by parcel (WS8 Phase 1).

``GET /api/capacity-map`` calls ``build_capacity_map``.  No model, and no per-parcel network call:

* **Neighbors** come from the in-memory Discovery index (``parcel_source``), grouped by PIN10 (one map polygon per
  base parcel; a condo building's unit PINs share it).  A spatial grid is built once per index version.
* **Polygons** come from ptaxsim ``pin_geometry_raw`` (the tax-year parcel map), the newest boundary per PIN10.
* **District** per polygon is the one covering the larger share of its area in the zoning quilt the Profile's zoning
  map already fetches (``zoning_polygons_near``).  A parcel's centroid can sit in the wrong district when it
  straddles a boundary (Item 36's 7149 W Belmont case), so the map never uses the point.  When two districts cover
  nearly equal shares the polygon is ``split_zoning`` and is not colored.
* **Allowed FAR** from ``zoning_definitions`` (the table the Profile shows).
* **Building area** from the index (the Assessor's characteristics), else the committed Commercial Valuation
  artifact (``commercial_artifact``), whose multi-parcel totals are never put on one lot.

The rules for each state are ``backend.capacity`` (shared with the Phase 0 census).  ``assemble`` is pure and holds
every truth rule; ``build_capacity_map`` only fetches.  A source that fails lands in ``unchecked``: zoning or
polygons failing leaves no map at all, the artifact failing leaves the parcels that needed it ``unchecked``, and a
response with anything unchecked is never cached.
"""

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from shapely import wkt as shapely_wkt
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform
from shapely.strtree import STRtree

from backend import capacity as cap
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

DEFAULT_RADIUS_MI = 0.1
MIN_RADIUS_MI = 0.05
MAX_RADIUS_MI = 0.25
# The district must cover at least this share of a polygon, or the polygon is outside zoning (a street, a rail
# right-of-way, the quilt's edge).
MIN_ZONED_SHARE = 0.5
# Two districts whose shares of a polygon differ by less than this have no honest single answer.
SPLIT_MARGIN = 0.10
# Below this share for the leading district, a colored polygon is shown at low confidence.
CLEAN_ZONE_SHARE = 0.9

GRID_DEG = 0.002  # about 0.14 mile of latitude: a 0.25-mile radius touches at most a 5 x 5 block of cells
GROUP_PAD_MI = 0.02  # unit PINs of one building lie within metres of each other
PIN_BATCH = 500

# The map's states beyond backend.capacity.MAP_STATES.
SPLIT_ZONING = "split_zoning"  # two districts cover nearly equal shares of the polygon
UNCHECKED = "unchecked"  # the building-area source failed for a polygon that needed it
STATES = (*cap.MAP_STATES[:-1], SPLIT_ZONING, UNCHECKED, "computable")
# States that rest on the leading district's FAR or PD status; a split polygon cannot honestly claim them.
_DISTRICT_DEPENDENT = frozenset({"planned_development", "no_allowed_far", "apparently_overbuilt", "computable"})

SOURCE_INDEX = "internal.discovery_index"
SOURCE_PTAXSIM = "cook.ptaxsim"
SOURCE_ZONING = "chi.zoning.districts"
SOURCE_TABLE = "code.hand_table.zoning_definitions"
SOURCE_ARTIFACT = "artifact.commercial_bldg_by_pin"

_M_PER_DEG_LAT = 111_132.95
_M_PER_DEG_LON_EQ = 111_319.49
_SQFT_PER_SQM = 10.763910

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="capacity_map")


class CapacityGeometryError(RuntimeError):
    """ptaxsim's parcel polygons could not be read."""


def clamp_radius(radius_mi: float | None) -> float:
    if radius_mi is None or not math.isfinite(radius_mi):
        return DEFAULT_RADIUS_MI
    return min(MAX_RADIUS_MI, max(MIN_RADIUS_MI, radius_mi))


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _area_sqft(geom: Polygon | MultiPolygon) -> float:
    """Planar area with longitude scaled by cos(latitude) (the rule ``parcel_geometry`` uses)."""
    mx = _M_PER_DEG_LON_EQ * math.cos(math.radians(geom.centroid.y))
    return transform(lambda x, y, z=None: (x * mx, y * _M_PER_DEG_LAT), geom).area * _SQFT_PER_SQM


# ---------------------------------------------------------------------------------------------------------------
# Neighbors from the Discovery index
# ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Group:
    """One PIN10 polygon's index rows: ``rows`` are (pin14, attrs); ``lat``/``lon`` locate it (the base row's point
    when it has one)."""

    pin10: str
    rows: tuple[tuple[str, dict], ...]
    lat: float
    lon: float


class _Grid:
    """Parcel references bucketed by a lat/lon cell.  Groups are formed per query, from a box padded by
    ``GROUP_PAD_MI`` so a building's unit PINs (which sit within metres of its base row) are never split off."""

    def __init__(self, parcels: Iterable[Any]) -> None:
        self.cells: dict[tuple[int, int], list[Any]] = defaultdict(list)
        for p in parcels:
            if p.lat is not None and p.lon is not None:
                self.cells[(math.floor(p.lat / GRID_DEG), math.floor(p.lon / GRID_DEG))].append(p)

    def _box(self, lat: float, lon: float, radius_mi: float) -> Iterable[Any]:
        dlat = radius_mi / 69.0
        dlon = radius_mi / (69.0 * max(math.cos(math.radians(lat)), 0.2))
        for i in range(math.floor((lat - dlat) / GRID_DEG), math.floor((lat + dlat) / GRID_DEG) + 1):
            for j in range(math.floor((lon - dlon) / GRID_DEG), math.floor((lon + dlon) / GRID_DEG) + 1):
                yield from self.cells.get((i, j), ())

    def near(self, lat: float, lon: float, radius_mi: float) -> list[Group]:
        """The PIN10 groups whose point (the base row's, when it has one) is within ``radius_mi``."""
        rows: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        where: dict[str, tuple[float, float]] = {}
        for p in self._box(lat, lon, radius_mi + GROUP_PAD_MI):
            key = cap.pin10(p.pin)
            rows[key].append((p.pin, getattr(p, "_attrs", None) or {}))
            if key not in where or p.pin.endswith("-0000"):
                where[key] = (p.lat, p.lon)
        out = [Group(k, tuple(v), *where[k]) for k, v in rows.items()
               if _haversine_mi(lat, lon, *where[k]) <= radius_mi]
        return sorted(out, key=lambda g: g.pin10)


_grid: tuple[str, _Grid] | None = None


def grid_for(version: str, parcels: Callable[[], Iterable[Any]]) -> _Grid:
    """The memoized grid for an index version (rebuilt only when the version changes)."""
    global _grid
    if _grid is None or _grid[0] != version:
        _grid = (version, _Grid(parcels()))
    return _grid[1]


# ---------------------------------------------------------------------------------------------------------------
# Polygons from ptaxsim
# ---------------------------------------------------------------------------------------------------------------

def read_polygons(db_path: Any, pin10s: list[str]) -> dict[str, tuple[Polygon | MultiPolygon, int]]:
    """``{dashed PIN10: (geometry, end_year)}``, the newest boundary per PIN10.  Raises ``CapacityGeometryError``
    when the database cannot be read; a PIN10 with no row is simply absent."""
    out: dict[str, tuple[Polygon | MultiPolygon, int]] = {}
    plain = {p.replace("-", ""): p for p in pin10s}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            keys = sorted(plain)
            for i in range(0, len(keys), PIN_BATCH):
                chunk = keys[i:i + PIN_BATCH]
                q = ("SELECT pin10, end_year, geometry FROM pin_geometry_raw WHERE pin10 IN "
                     f"({','.join('?' * len(chunk))}) AND geometry IS NOT NULL ORDER BY pin10, end_year")
                for pin10, end_year, wkt_text in con.execute(q, chunk):
                    try:
                        geom = shapely_wkt.loads(wkt_text)
                    except Exception:  # noqa: BLE001 — one malformed row is that parcel's gap, not an outage
                        continue
                    if isinstance(geom, (Polygon, MultiPolygon)) and not geom.is_empty:
                        out[plain[pin10]] = (geom, int(end_year))  # ascending end_year: the newest wins
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise CapacityGeometryError(f"ptaxsim parcel polygons unreadable: {exc}") from exc
    return out


# ---------------------------------------------------------------------------------------------------------------
# District by overlap
# ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ZoneAnswer:
    zone_class: str | None
    share: float  # the leading district's share of the zoned part of the polygon
    split: bool  # two districts within SPLIT_MARGIN of each other


class ZoningQuilt:
    def __init__(self, feature_collection: dict) -> None:
        self.shapes: list[Any] = []
        self.zones: list[str] = []
        for f in feature_collection.get("features") or []:
            zone = ((f.get("properties") or {}).get("ZONE_CLASS") or "").strip().upper()
            try:
                geom = shape(f["geometry"])
            except Exception:  # noqa: BLE001 — a malformed feature covers nothing
                continue
            if zone and not geom.is_empty:
                self.shapes.append(geom if geom.is_valid else geom.buffer(0))
                self.zones.append(zone)
        self.tree = STRtree(self.shapes) if self.shapes else None

    def zone_of(self, geom: Polygon | MultiPolygon) -> ZoneAnswer:
        if self.tree is None or geom.area <= 0:
            return ZoneAnswer(None, 0.0, False)
        by_zone: Counter = Counter()
        for i in self.tree.query(geom):
            try:
                a = geom.intersection(self.shapes[int(i)]).area
            except Exception:  # noqa: BLE001
                continue
            if a > 0:
                by_zone[self.zones[int(i)]] += a
        covered = sum(by_zone.values())
        if covered < MIN_ZONED_SHARE * geom.area:
            return ZoneAnswer(None, 0.0, False)
        ranked = by_zone.most_common(2)
        top = ranked[0][1] / covered
        second = ranked[1][1] / covered if len(ranked) > 1 else 0.0
        return ZoneAnswer(ranked[0][0], round(top, 4), top - second < SPLIT_MARGIN)


def zoning_group(zone_class: str | None) -> str | None:
    """The index's zoning group of a district (the builder's rule, so the census and the map agree)."""
    from backend.discovery.index_build import _zoning_group

    return _zoning_group(zone_class)


# ---------------------------------------------------------------------------------------------------------------
# Assembly (pure)
# ---------------------------------------------------------------------------------------------------------------

def _base(rows: tuple[tuple[str, dict], ...]) -> tuple[str, dict] | None:
    return next(((p, a) for p, a in rows if p.endswith("-0000")), None)


def _confidence(state: str, zone: ZoneAnswer) -> tuple[str, str | None]:
    if state != "computable":
        return "withheld", state
    if zone.share < CLEAN_ZONE_SHARE:
        return "low", "district_boundary"
    return "standard", None


def polygon_feature(
    group: Group,
    geometry: tuple[Polygon | MultiPolygon, int] | None,
    quilt: ZoningQuilt,
    building_area: Callable[[str], Any],
    *,
    far_of: Callable[[str], float | None],
) -> tuple[dict | None, bool]:
    """One polygon's GeoJSON feature and whether the artifact failed for it.  ``None`` when ptaxsim has no polygon
    for the PIN10 (nothing to draw; counted apart)."""
    from backend.retrieval.property.commercial_artifact import CapacityArtifactError, MultiPinMember, UnitArea

    if geometry is None:
        return None, False
    geom, geom_year = geometry
    has_units = any((a.get("class") or "") in cap.CONDO_CLASSES for _, a in group.rows)
    base = _base(group.rows)
    zone = quilt.zone_of(geom)
    allowed = far_of(zone.zone_class) if zone.zone_class else None
    inputs: dict[str, dict] = {
        "zoning": {"zone_class": zone.zone_class, "share": zone.share, "source": SOURCE_ZONING},
        "allowed_far": {"value": allowed, "source": SOURCE_TABLE},
    }
    artifact_failed = False
    complex_only = False
    attrs: dict = dict(base[1]) if base else {}
    if base is None:
        state = "condo_building" if has_units else "no_base_row"
    else:
        # A district outside the builder's five families (POS parks, T transportation) is still a district: it
        # reads as "no allowed FAR", never as "outside zoning" (the census keeps the builder's rule).
        attrs["zoning_group"] = zoning_group(zone.zone_class) or ("other" if zone.zone_class else None)
        attrs["density_band"] = allowed
        land_source = SOURCE_INDEX
        if attrs.get("land_sqft") is None:
            attrs["land_sqft"] = round(_area_sqft(geom))
            land_source = SOURCE_PTAXSIM
        inputs["lot_sqft"] = {"value": attrs["land_sqft"], "source": land_source}
        bldg_source: str | None = SOURCE_INDEX if attrs.get("bldg_sqft") else None
        if not attrs.get("bldg_sqft") and not has_units:
            try:
                got = building_area(base[0])
            except CapacityArtifactError:
                got, artifact_failed = None, True
            if isinstance(got, UnitArea):
                attrs["bldg_sqft"], bldg_source = got.bldg_sqft, SOURCE_ARTIFACT
                inputs["bldg_sqft_year"] = {"value": got.year, "source": SOURCE_ARTIFACT}
            elif isinstance(got, MultiPinMember):
                complex_only = True
                inputs["complex"] = {"pins": len(got.unit_pins), "complex_bldg_sqft": got.complex_bldg_sqft,
                                     "source": SOURCE_ARTIFACT}
        inputs["bldg_sqft"] = {"value": attrs.get("bldg_sqft") or None, "source": bldg_source}
        state = cap.map_polygon_state(attrs, has_unit_pins=has_units, complex_total_only=complex_only)
        if zone.split and state in _DISTRICT_DEPENDENT:
            state = SPLIT_ZONING
        elif artifact_failed and state == "unknown_gfa":
            state = UNCHECKED
    existing = utilization = None
    if state == "computable":
        existing = attrs["bldg_sqft"] / attrs["land_sqft"]
        utilization = existing / allowed
    confidence, reason = _confidence(state, zone)
    props = {
        "pin10": group.pin10,
        "pin": base[0] if base else None,
        "address": (base[1].get("address") if base else None),
        "state": state,
        "existing_far": round(existing, 3) if existing is not None else None,
        "allowed_far": allowed,
        "utilization": round(utilization, 3) if utilization is not None else None,
        "zone_class": zone.zone_class,
        "confidence": confidence,
        "reason": reason,
        "geometry_year": geom_year,
        "inputs": inputs,
    }
    return {"type": "Feature", "geometry": mapping(geom), "properties": props}, artifact_failed


def summarize(features: list[dict], n_groups: int, no_polygon: int) -> dict:
    """The view's counts per state and its verdict (Item 36 Decision 5: the share of polygons that can be colored,
    against the confidence standard's thresholds)."""
    counts = Counter(f["properties"]["state"] for f in features)
    n = len(features)
    colorable = counts.get("computable", 0)
    share = round(colorable / n, 4) if n else 0.0
    return {
        "polygons": n,
        "index_groups": n_groups,
        "no_polygon": no_polygon,
        "states": {s: counts.get(s, 0) for s in STATES},
        "colorable": colorable,
        "colorable_share": share,
        "verdict": cap.coverage_verdict(share) if n else "withheld",
    }


def assemble(
    groups: list[Group],
    polygons: dict[str, tuple[Polygon | MultiPolygon, int]],
    quilt: ZoningQuilt,
    building_area: Callable[[str], Any],
    *,
    far_of: Callable[[str], float | None],
    subject_pin10: str | None = None,
) -> tuple[dict, dict, bool]:
    """(feature collection, summary, artifact_failed).  A withheld view keeps every state but no utilization, so
    nothing downstream can draw bins from it (truth invariant 7)."""
    features, no_polygon, artifact_failed = [], 0, False
    for g in groups:
        feat, failed = polygon_feature(g, polygons.get(g.pin10), quilt, building_area, far_of=far_of)
        artifact_failed = artifact_failed or failed
        if feat is None:
            no_polygon += 1
            continue
        feat["properties"]["subject"] = g.pin10 == subject_pin10
        features.append(feat)
    summary = summarize(features, len(groups), no_polygon)
    if summary["verdict"] == "withheld":
        for f in features:
            f["properties"]["utilization"] = None
    return {"type": "FeatureCollection", "features": features}, summary, artifact_failed


# ---------------------------------------------------------------------------------------------------------------
# The endpoint's fetch
# ---------------------------------------------------------------------------------------------------------------

def _far_of(zone_class: str) -> float | None:
    from backend.retrieval.zoning_definitions import get_zone_definition

    return get_zone_definition(zone_class).far


def _empty(radius: float, unchecked: list[str], **extra: Any) -> dict:
    return {
        "radius_mi": radius, "features": {"type": "FeatureCollection", "features": []},
        "summary": summarize([], 0, 0) | {"verdict": "unavailable"}, "unchecked": unchecked, **extra,
    }


def _provenance(summary: dict, artifact_year: str | None, index_built: str | None) -> dict:
    from backend.provenance import make_entry

    inputs = [SOURCE_INDEX, SOURCE_PTAXSIM, SOURCE_ZONING, SOURCE_TABLE] + ([SOURCE_ARTIFACT] if artifact_year else [])
    entry = make_entry(
        "capacity.utilization", query_date=date.today().isoformat(), inputs=inputs,
        as_of=index_built, coverage={"n": summary["colorable"], "share": summary["colorable_share"],
                                     "unit": "parcels",
                                     "universe": "parcels within the map radius"},
    )
    return {"capacity.utilization": entry}


async def build_capacity_map(*, pin: str | None, lat: float | None, lon: float | None,
                             radius_mi: float | None = None) -> dict:
    from backend.config import get_settings
    from backend.discovery import parcel_source
    from backend.discovery.parcel import default_source
    from backend.retrieval.property import commercial_artifact as ca
    from backend.retrieval.zoning import zoning_polygons_near

    radius = clamp_radius(radius_mi)
    parcel_source.ensure_loaded()
    version = parcel_source.current_version()
    meta = parcel_source.current_meta()
    if version == parcel_source.EMPTY_VERSION or meta is None:
        return _empty(radius, ["discovery_index"])
    index_built = datetime.fromtimestamp(meta.built_at, tz=timezone.utc).date().isoformat()
    sources = {"index": {"source": SOURCE_INDEX, "data_version": version, "built_at": index_built}}

    grid = grid_for(version, lambda: default_source.get(version))
    subject_pin10 = cap.pin10(pin) if pin else None
    if subject_pin10:
        lookup = parcel_source.pin_lookup(version)
        hit = lookup.get(f"{subject_pin10}-0000") or lookup.get(pin)
        if hit is None:
            # A condo building can be indexed by its unit PINs alone (no -0000 row): any row on the PIN10 places it.
            hit = next((p for k, p in lookup.items() if k.startswith(subject_pin10)), None)
        if hit is not None and hit.lat is not None and hit.lon is not None:
            lat, lon = hit.lat, hit.lon
    if lat is None or lon is None:
        return _empty(radius, [], sources=sources, reason="parcel_not_in_index")

    key = f"{version}:{subject_pin10 or ''}:{lat:.5f},{lon:.5f}:{radius}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    groups = grid.near(lat, lon, radius)
    settings = get_settings()
    from backend.map_geometry import PARCEL_MAP_RADIUS_MI

    quilt_radius = max(PARCEL_MAP_RADIUS_MI, radius + 0.05)  # 0.25 shares the zoning map's cache entry
    loop = asyncio.get_running_loop()
    zoning_task = zoning_polygons_near(lat, lon, radius_mi=quilt_radius)

    async def _polygons() -> dict:
        if not settings.ptaxsim_enabled or not settings.ptaxsim_db_path.exists():
            raise CapacityGeometryError("ptaxsim is disabled or absent")
        return await loop.run_in_executor(None, read_polygons, settings.ptaxsim_db_path, [g.pin10 for g in groups])

    zoning_fc, polygons = await asyncio.gather(zoning_task, _polygons(), return_exceptions=True)
    unchecked = [name for name, r in (("zoning", zoning_fc), ("parcel_geometry", polygons)) if isinstance(r, Exception)]
    for name, r in (("zoning", zoning_fc), ("parcel_geometry", polygons)):
        if isinstance(r, Exception):
            log.warning("capacity map: %s lookup failed: %s", name, r)
    if unchecked:
        return _empty(radius, unchecked, sources=sources)

    try:
        artifact_year: str | None = ca.artifact_year()
    except ca.CapacityArtifactError as exc:
        log.warning("capacity map: %s", exc)
        artifact_year = None
    quilt = ZoningQuilt(zoning_fc)
    features, summary, artifact_failed = await loop.run_in_executor(
        None, lambda: assemble(groups, polygons, quilt, ca.building_area, far_of=_far_of, subject_pin10=subject_pin10))
    if artifact_failed or artifact_year is None:
        unchecked.append("commercial_valuation")

    from backend.map_geometry import simplify_zoning_coverage

    sources["commercial_valuation"] = {"source": SOURCE_ARTIFACT, "year": artifact_year}
    sources["parcel_geometry"] = {"source": SOURCE_PTAXSIM}
    sources["zoning"] = {"source": SOURCE_ZONING, "table": SOURCE_TABLE}
    payload = {
        "subject": {"pin10": subject_pin10, "lat": lat, "lon": lon},
        "radius_mi": radius,
        # Parcel polygons are a coverage too; the same seam simplifies shared edges or returns them unchanged.
        "features": simplify_zoning_coverage(features),
        "summary": summary,
        "sources": sources,
        "unchecked": unchecked,
        "provenance": _provenance(summary, artifact_year, index_built),
    }
    if not unchecked:
        _cache.set(key, payload)
    return payload
