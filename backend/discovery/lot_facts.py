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
from shapely.strtree import STRtree

from backend.discovery.lot_sources import area_sqft

FOOTPRINT_SPAN_SLACK = 1.1  # the Profile's _FOOTPRINT_SPAN_SLACK (retrieval/property/__init__.py)
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
        finally:
            db.close()
        reps = shapely.point_on_surface(geoms)
        area_geoms = shapely.from_wkb([a[2] for a in areas]) if areas else []
        return cls(
            fp_tree=STRtree(reps), fp_geoms=geoms, fp_points=reps,
            fp_stories=[r[0] for r in fps], fp_area=[r[1] for r in fps],
            pt_tree={k: (STRtree(g), d) for k, (g, d) in pts.items()},
            area_tree=(STRtree(area_geoms), [a[1] or "" for a in areas]) if areas else None,
            meta=meta,
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
    if far and lsf and lsf > 0 and bsf is not None:
        attrs["room_sqft"] = float(max(0.0, round(far * lsf - bsf)))


def fill_building_area(attrs: dict[str, Any], *, commercial=None, lot=None, src: LotSources | None = None) -> None:
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
        else:
            attrs["bldg_sqft_unknown"] = why


__all__ = [
    "LotSources", "footprint_area", "lot_warnings", "pending_rezoning_pin10s", "derive_capacity",
    "fill_building_area", "WARNING_ORDER", "area_sqft",
]


# --- the lot tiles' measure bands (Item 104): what the Explore map colors a lot by. A band is display only; which
# lots MATCH a search is never in the tiles (Item 68). Absent = unknown (drawn hatched).
ROOM_BANDS = (0, 2_500, 5_000, 10_000)  # sq ft of room: "0" = built out, then <2.5k, 2.5-5k, 5-10k, 10k+
LOT_BANDS = (2_500, 5_000, 10_000, 43_560)  # sq ft: <2.5k, 2.5-5k (the city lot), 5-10k, 10k-1 acre, 1 acre+
SALE_YEARS = (1, 3, 5, 10)  # years since the last recorded sale: <1, 1-3, 3-5, 5-10, 10+
LAND_USES = ("vacant", "residential", "multi_family", "commercial", "industrial", "exempt")


def measure_bands(attrs: dict[str, Any]) -> dict[str, str]:
    """The tile properties for one lot: r (room), s (lot size), y (last sale), u (land use); absent = unknown."""
    out: dict[str, str] = {}
    room = attrs.get("room_sqft")
    if room is not None:
        out["r"] = str(0 if room <= 0 else 1 + sum(room >= e for e in ROOM_BANDS[1:]))
    lot = attrs.get("land_sqft")
    if lot:
        out["s"] = str(sum(lot >= e for e in LOT_BANDS))
    days = attrs.get("sale_recency_days")
    if days is not None:
        out["y"] = str(sum(days >= y * 365 for y in SALE_YEARS))
    use = attrs.get("land_use_class") or ("exempt" if str(attrs.get("class") or "").upper().startswith("EX") else None)
    if use in LAND_USES:
        out["u"] = str(LAND_USES.index(use))
    return out
