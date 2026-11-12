"""Building area, room to build and the card warnings for one Discovery lot (decision Item 104).

Pure functions over local copies, shared by the index build (``index_build``) and ``index_backfill``:

* **Building area, one source per lot, named** (``bldg_sqft_source``): the Assessor's residential characteristics
  first (``assessor``), then the Assessor's Commercial Valuation for a building that is this lot's own
  (``commercial_valuation``), then the City's building footprints whose own interior point lies inside the lot,
  summed as footprint area x stories (``footprint``). The footprint answer is withheld (no area, never zero) when a
  footprint has no stories on record, or a footprint is larger than the lot by the Profile's own slack
  (``_FOOTPRINT_SPAN_SLACK``: the building spans several lots). A vacant lot's building area is 0.
* **Room to build** (``room_sqft``): allowed floor area (the base district's FAR x the lot area) minus the building
  area, never below 0. Unknown (absent) when any input is unknown.
* **Serious warnings** (``warn_*``), the owner's four: a demolition permit in the last 24 months, a vacant-building
  case in the last 3 years, a pending rezoning filing listing this lot, a Chicago Landmark or landmark district.
  (A nominal assessment, the fifth card warning, is decided at row time from the assessed value.)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import shapely
import shapely.affinity
from shapely.strtree import STRtree

from backend.discovery.lot_sources import area_sqft

FOOTPRINT_SPAN_SLACK = 1.1
# A lot narrower than this (the widest circle that fits inside it) is a strip, not a building lot: a side yard, a
# vacated alley, a sliver between buildings. Chicago's standard lot is 25 ft wide. Hidden by default (Item 104).
NARROW_STRIP_FT = 16.0
_FT_PER_DEG_LAT = 364_000.0
_LON_SCALE = 0.7447  # cos(41.84°): degrees of longitude to degrees of latitude at Chicago  # the Profile's _FOOTPRINT_SPAN_SLACK (retrieval/property/__init__.py)
POINT_BUFFER_DEG = 0.00003  # ~3 m: an address point on the lot line still counts as this lot's

# One warning per card: the order in which the serious ones win.
WARNING_ORDER = ("warn_demolition", "warn_vacant_case", "warn_pending_rezoning", "warn_landmark")


@dataclass
class LotSources:
    """The local copy (``lot_sources.fetch``) loaded for point-in-lot queries."""

    fp_tree: STRtree
    fp_geoms: np.ndarray
    fp_points: np.ndarray  # each footprint's representative point
    fp_stories: list[int | None]
    fp_area: list[float]
    pt_tree: dict[str, tuple[STRtree, list[str]]]  # kind -> (tree of points, their dates)
    area_tree: tuple[STRtree, list[str]] | None  # landmarks + landmark districts
    meta: dict[str, Any]
    city_land: frozenset[str] = frozenset()  # PIN10s the City owns (its land inventory)
    # PIN10 -> (largest, total) area of the County's 2022 LiDAR structures on the lot (Item 110); None when the copy
    # predates the table, so no lot is called empty.
    lidar_on_lot: dict[str, tuple[float, float]] | None = None
    # PIN10 -> (CMAP 2023 code covering the most of the lot, that share) (Item 112); None when the copy predates the
    # table, so no lot is marked road land.
    cmap_on_lot: dict[str, tuple[str, float]] | None = None

    @classmethod
    def load(cls, path: Path) -> "LotSources":
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            fps = db.execute("SELECT stories, area_sqft, wkb FROM footprints").fetchall()
            geoms = shapely.from_wkb([r[2] for r in fps])
            pts: dict[str, tuple[list, list[str]]] = {}
            for kind, date, lat, lon in db.execute("SELECT kind, date, lat, lon FROM points"):
                g, d = pts.setdefault(kind, ([], []))
                g.append(shapely.Point(lon, lat))
                d.append(date or "")
            areas = db.execute("SELECT kind, name, wkb FROM areas").fetchall()
            meta = {k: json.loads(v) for k, v in db.execute("SELECT name, value FROM meta")}
            try:
                city_land = frozenset(r[0] for r in db.execute("SELECT pin10 FROM city_land"))
            except sqlite3.OperationalError:  # a copy made before the inventory was added
                city_land = frozenset()
            try:
                lidar = {r[0]: (r[1], r[2]) for r in db.execute("SELECT pin10, max_sqft, sum_sqft FROM lidar_on_lot")}
            except sqlite3.OperationalError:  # a copy made before Item 110
                lidar = None
            try:
                cmap = {r[0]: (r[1], r[2]) for r in db.execute("SELECT pin10, code, share FROM cmap_on_lot")}
            except sqlite3.OperationalError:  # a copy made before Item 112
                cmap = None
        finally:
            db.close()
        reps = shapely.point_on_surface(geoms)
        area_geoms = shapely.from_wkb([a[2] for a in areas]) if areas else []
        return cls(
            fp_tree=STRtree(reps), fp_geoms=geoms, fp_points=reps,
            fp_stories=[r[0] for r in fps], fp_area=[r[1] for r in fps],
            pt_tree={k: (STRtree(g), d) for k, (g, d) in pts.items()},
            area_tree=(STRtree(area_geoms), [a[1] or "" for a in areas]) if areas else None,
            meta=meta, city_land=city_land, lidar_on_lot=lidar, cmap_on_lot=cmap,
        )


def footprint_area(lot, lot_sqft: float | None, src: LotSources) -> tuple[float | None, str]:
    """Floor area from the footprints inside ``lot`` (lon/lat), with the reason when there is none."""
    idx = src.fp_tree.query(lot, predicate="contains")
    if len(idx) == 0:
        return None, "no_footprint"
    total = 0.0
    for i in idx:
        stories, fa = src.fp_stories[i], src.fp_area[i]
        if not stories:
            return None, "stories_missing"
        if lot_sqft and fa > lot_sqft * FOOTPRINT_SPAN_SLACK:
            return None, "spans_lots"
        total += fa * stories
    return (float(round(total)), "footprint") if total > 0 else (None, "no_footprint")


def lot_warnings(lot, src: LotSources, pending_pin10: set[str], pin10: str) -> dict[str, Any]:
    """The serious warnings for one lot: each a date / record / True, absent when it does not apply."""
    out: dict[str, Any] = {}
    near = lot.buffer(POINT_BUFFER_DEG)
    for kind, key in (("demolition", "warn_demolition"), ("vacant_case", "warn_vacant_case")):
        tree = src.pt_tree.get(kind)
        if tree is None:
            continue
        hits = tree[0].query(near, predicate="contains")
        if len(hits):
            out[key] = max(tree[1][i] for i in hits) or True
    if pin10 in pending_pin10:
        out["warn_pending_rezoning"] = True
    if src.area_tree is not None:
        rep = shapely.point_on_surface(lot)
        hits = src.area_tree[0].query(rep, predicate="within")
        if len(hits):
            out["warn_landmark"] = src.area_tree[1][hits[0]] or True
    return out


def lot_width_ft(lot) -> float | None:
    """How wide a lot really is: the diameter of the largest circle that fits inside it, in feet (local scale)."""
    try:
        g = shapely.affinity.scale(lot, xfact=_LON_SCALE, yfact=1, origin=(0, 0))
        radius = shapely.maximum_inscribed_circle(g, 0.000005).length
    except Exception:  # noqa: BLE001: a degenerate outline has no width
        return None
    w = 2 * radius * _FT_PER_DEG_LAT
    return round(w, 1) if w > 0 else None


def pending_rezoning_pin10s(db_path: Path) -> set[str]:
    """PIN10s a current (pending, not superseded) zoning reclassification filing lists by address range."""
    if not db_path.exists():
        return set()
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT DISTINCT l.pin FROM locations l JOIN matters m ON m.matter_id = l.matter_id "
            "WHERE m.category LIKE 'ZONING RECLASSIFICATIONS%' AND m.superseded_by IS NULL"
        ).fetchall()
    finally:
        db.close()
    return {str(r[0]).replace("-", "")[:10] for r in rows}


def derive_capacity(attrs: dict[str, Any]) -> None:
    """Room to build and the figures that read the building area, recomputed from ``attrs`` in place.

    ``density_band`` is the base district's FAR (the index's allowed-FAR field)."""
    bsf = attrs.get("bldg_sqft")
    lsf = attrs.get("land_sqft")
    far = attrs.get("density_band")
    if attrs.get("is_vacant") and bsf is None:
        bsf = 0.0
    attrs.pop("room_sqft", None)
    if attrs.get("room_scope") in NO_BASE_FAR:
        attrs.pop("room_scope")
    if far and lsf and lsf > 0 and bsf is not None:
        attrs["room_sqft"] = float(max(0.0, round(far * lsf - bsf)))
    elif not far:
        # No base FAR is not "unknown": a planned development or planned manufacturing district sets its own size by
        # ordinance; parks and transportation zones aren't built on by right (owner's review, Item 104).
        scope = no_far_scope(attrs)
        if scope:
            attrs["room_scope"] = scope


NO_BASE_FAR = ("own_rules", "open_space", "transport")


def no_far_scope(attrs: dict[str, Any]) -> str | None:
    """Why a lot has no base FAR, when the zoning says: its own ordinance, open space, or a transportation zone."""
    zone = str(attrs.get("zone_class") or "").upper()
    if attrs.get("zoning_group") == "planned_development" or zone.startswith(("PD", "PMD")):
        return "own_rules"
    if attrs.get("zoning_group") == "manufacturing" and not attrs.get("density_band"):
        return "own_rules"  # a PMD read as manufacturing by an index built before the exact district
    if zone.startswith("POS"):
        return "open_space"
    if zone.startswith("T"):
        return "transport"
    return None


def fill_building_area(attrs: dict[str, Any], *, commercial=None, lot=None, src: LotSources | None = None,
                       pin10: str | None = None) -> None:
    """Fill ``bldg_sqft`` (and name its source) where the Assessor's characteristics left it empty."""
    from backend.retrieval.property.commercial_artifact import UnitArea

    if attrs.get("bldg_sqft") is not None:
        attrs.setdefault("bldg_sqft_source", "assessor")
        return
    if attrs.get("is_vacant"):
        return
    if isinstance(commercial, UnitArea) and commercial.bldg_sqft > 0:
        attrs["bldg_sqft"] = float(round(commercial.bldg_sqft))
        attrs["bldg_sqft_source"] = "commercial_valuation"
        return
    if lot is not None and src is not None:
        sqft, why = footprint_area(lot, attrs.get("land_sqft"), src)
        if sqft is not None:
            attrs["bldg_sqft"] = sqft
            attrs["bldg_sqft_source"] = "footprint"
        elif why == "no_footprint" and pin10 and pin10 in src.city_land:
            # No footprint, and the City's own land inventory lists the lot as City-owned: vacant land (measured,
            # Item 104: 9,905 exempt lots; a footprint sits on only 8.4% of inventory lots, mostly since demolished).
            attrs["bldg_sqft"] = 0.0
            attrs["bldg_sqft_source"] = "city_land_inventory"
        else:
            attrs["bldg_sqft_unknown"] = why


# --- what stands on a lot (decision Item 110) ----------------------------------------------------------------------
# Physically empty is read from two building sources (the City's footprints, the County's 2022 LiDAR) and the City's
# permits, never the tax class alone. The owner's blind check (60 lots) found 43/43 empty on these kinds of land and
# 6/13 on lots taxed as residential or other commercial, so only these are offered as empty land, and the
# demolition overrides apply only to them.
EMPTY_LAND_KINDS = frozenset({"vacant", "city_owned", "parking", "exempt"})
PARKING_CLASSES = ("5-90", "5-80")  # commercial minor improvement: mostly paved parking
ACCESSORY_MAX_SQFT = 700.0  # every structure smaller than this: a garage or shed
LIDAR_FLIGHT = "2022-06-01"


def land_kind(class_code: str | None, city_owned: bool) -> str:
    """The kind of land a lot is, from the Assessor's class and the City's land inventory."""
    c = (class_code or "").strip().upper()
    if city_owned:
        return "city_owned"
    if c.startswith("1"):
        return "vacant"
    if c in PARKING_CLASSES:
        return "parking"
    if c == "2-41":
        return "side_yard"  # vacant land held with the house next door
    if c == "EX":
        return "exempt"
    if c == "RR":
        return "railroad"
    if c.startswith(("5", "6", "7", "8")):
        return "commercial"
    if c.startswith(("2", "3", "9")):
        return "residential"
    return "other"


def _structure_state(sizes_max: float | None) -> str:
    if not sizes_max:
        return "empty"
    return "accessory" if sizes_max < ACCESSORY_MAX_SQFT else "built"


def structure_on_lot(lot, pin10: str, kind: str, src: LotSources) -> str | None:
    """What stands on the lot: ``empty``, ``accessory`` (garage or shed only), ``built``, ``disagree`` (one source has
    a building, the other doesn't), ``demolished_since_2022`` or ``new_construction``; None when the LiDAR table is
    missing."""
    if src.lidar_on_lot is None:
        return None
    idx = src.fp_tree.query(lot, predicate="contains")
    fp = _structure_state(max((src.fp_area[i] for i in idx), default=None))
    lid = _structure_state((src.lidar_on_lot.get(pin10) or (None, None))[0])
    near = lot.buffer(POINT_BUFFER_DEG)

    def dates(kind_: str) -> list[str]:
        tree = src.pt_tree.get(kind_)
        return [tree[1][i] for i in tree[0].query(near, predicate="contains")] if tree else []

    demos = dates("demolition_history")
    both = {fp, lid}
    state = ("empty" if both == {"empty"} else "built" if both == {"built"} else
             "accessory" if "built" not in both else "disagree")
    if kind in EMPTY_LAND_KINDS:
        # The City's footprints keep demolished buildings: a demolition permit and nothing in the 2022 LiDAR means the
        # footprint is out of date (74.5% of such vacant-class lots have one, vs 7.6% of built houses).
        if state == "disagree" and fp != "empty" and lid == "empty" and demos:
            state = "empty"
        if state in ("built", "disagree", "accessory") and any(d >= LIDAR_FLIGHT for d in demos):
            state = "demolished_since_2022"
    if state in ("empty", "accessory", "demolished_since_2022") and dates("new_construction"):
        state = "new_construction"
    return state


def mark_empty_land(attrs: dict[str, Any], lot, pin10: str, src: LotSources) -> None:
    """``land_kind``, ``structure`` and ``empty_land`` on one base lot, in place; and on a vacant-class lot that is empty,
    the building area the Assessor kept from a demolished building is set aside (``bldg_sqft_assessor_old``), so room
    to build reads the empty lot. Reruns restore it first."""
    if attrs.get("bldg_sqft_source") == "empty_lot":
        old = attrs.pop("bldg_sqft_assessor_old", None)
        if old is None:
            attrs.pop("bldg_sqft", None)
            attrs.pop("bldg_sqft_source", None)
        else:
            attrs["bldg_sqft"] = old
            attrs["bldg_sqft_source"] = "assessor"
    for k in ("land_kind", "structure", "empty_land"):
        attrs.pop(k, None)
    kind = land_kind(attrs.get("class"), pin10 in src.city_land)
    attrs["land_kind"] = kind
    state = structure_on_lot(lot, pin10, kind, src) if lot is not None else None
    if state is None:
        return
    attrs["structure"] = state
    # A garage or shed alone counts (owner, 2026-11-11): wrecking a detached private garage or carport is a stand-alone
    # $125 permit with no drawings and no zoning fee (Table 14A-12-1204.2), not a building's demolition. ``structure``
    # keeps the difference for the card.
    if kind in EMPTY_LAND_KINDS and state in ("empty", "demolished_since_2022", "accessory"):
        attrs["empty_land"] = True
        # An index built before Item 104 has the Assessor's area with no source named yet (the backfill names it later).
        if kind == "vacant" and attrs.get("bldg_sqft") and attrs.get("bldg_sqft_source", "assessor") == "assessor":
            attrs["bldg_sqft_assessor_old"] = attrs["bldg_sqft"]
            attrs["bldg_sqft"] = 0.0
            attrs["bldg_sqft_source"] = "empty_lot"


# --- land in use (decision Item 112) --------------------------------------------------------------------------------
# Measured against the owner's blind checks: surface parking from the Assessor's minor-improvement classes with
# nothing standing on the lot was 23 of 23 (all source combinations together 39 of 42); CMAP's road right-of-way on
# exempt land the Item 110 rule calls empty was 27 of 27 road or rail land. OSM parking (22 of 23) waits for a
# licensing review, CMAP's parking code alone (4 of 6), its parks (2 of 6) and garages (0 of 4) are not used.
NO_BUILDING = ("empty", "accessory")
ROAD_MIN_SHARE = 0.5  # CMAP's road polygon covers at least half the lot


def mark_land_use(attrs: dict[str, Any], pin10: str, src: LotSources) -> None:
    """``surface_parking`` and ``infrastructure`` on one base lot, in place, from the fields ``mark_empty_land`` just
    set; each with its source. Reruns clear them first."""
    from backend.discovery.cmap_land_use import CMAP_ROAD

    for k in ("surface_parking", "surface_parking_source", "infrastructure", "infrastructure_source"):
        attrs.pop(k, None)
    if attrs.get("land_kind") == "parking" and attrs.get("structure") in NO_BUILDING:
        attrs["surface_parking"] = True
        attrs["surface_parking_source"] = "assessor_class"
    cm = src.cmap_on_lot.get(pin10) if src.cmap_on_lot is not None else None
    if cm and cm[0] == CMAP_ROAD and cm[1] >= ROAD_MIN_SHARE and attrs.get("land_kind") == "exempt" \
            and attrs.get("empty_land"):
        attrs["infrastructure"] = "road"
        attrs["infrastructure_source"] = "cmap_2023"


__all__ = [
    "LotSources", "EMPTY_LAND_KINDS", "land_kind", "structure_on_lot", "mark_empty_land", "mark_land_use", "footprint_area", "lot_warnings", "pending_rezoning_pin10s", "derive_capacity",
    "fill_building_area", "WARNING_ORDER", "area_sqft",
]


# --- the lot tiles' measure bands (Item 104): what the Explore map colors a lot by. A band is display only; which
# lots MATCH a search is never in the tiles (Item 68). Absent = unknown (drawn hatched).
ROOM_BANDS = (0, 2_500, 5_000, 10_000)  # sq ft of room: "0" = built out, then <2.5k, 2.5-5k, 5-10k, 10k+
LOT_BANDS = (2_500, 5_000, 10_000, 43_560)  # sq ft: <2.5k, 2.5-5k (the city lot), 5-10k, 10k-1 acre, 1 acre+
SALE_YEARS = (1, 3, 5, 10)  # years since the last recorded sale: <1, 1-3, 3-5, 5-10, 10+
LAND_USES = ("vacant", "residential", "multi_family", "commercial", "industrial", "exempt")
# Land in use (Item 112): what the lot is used for, measured. Empty land is what stands on it (Item 110), surface
# parking and road land the owner's blind checks (23/23, 27/27); the rest is the Assessor's use class. A vacant-class lot
# with a building on it gets no band (drawn dotted, not known), never "vacant".
LAND_IN_USE = ("empty", "parking", "homes", "apartments", "business", "industrial", "exempt", "road_rail")
_IN_USE_FROM_CLASS = {"residential": "homes", "multi_family": "apartments", "commercial": "business",
                      "industrial": "industrial", "exempt": "exempt"}


def land_in_use(attrs: dict[str, Any]) -> str | None:
    if attrs.get("surface_parking"):
        return "parking"
    if attrs.get("empty_land"):
        return "empty"
    if attrs.get("infrastructure") == "road" or attrs.get("land_kind") == "railroad":
        return "road_rail"
    use = attrs.get("land_use_class") or ("exempt" if str(attrs.get("class") or "").upper().startswith("EX") else None)
    return _IN_USE_FROM_CLASS.get(use)


def measure_bands(attrs: dict[str, Any]) -> dict[str, str]:
    """The tile properties for one lot: r (room), s (lot size), y (last sale), u (land use, the tax class), l (land in
    use, Item 112); absent = unknown."""
    out: dict[str, str] = {}
    room = attrs.get("room_sqft")
    if room is not None:
        out["r"] = str(0 if room <= 0 else 1 + sum(room >= e for e in ROOM_BANDS[1:]))
    elif attrs.get("room_scope") in NO_BASE_FAR:
        out["r"] = {"own_rules": "x", "open_space": "p", "transport": "t"}[attrs["room_scope"]]
    lot = attrs.get("land_sqft")
    if lot:
        out["s"] = str(sum(lot >= e for e in LOT_BANDS))
    days = attrs.get("sale_recency_days")
    if days is not None:
        out["y"] = str(sum(days >= y * 365 for y in SALE_YEARS))
    use = attrs.get("land_use_class") or ("exempt" if str(attrs.get("class") or "").upper().startswith("EX") else None)
    if use in LAND_USES:
        out["u"] = str(LAND_USES.index(use))
    in_use = land_in_use(attrs)
    if in_use is not None:
        out["l"] = str(LAND_IN_USE.index(in_use))
    return out
