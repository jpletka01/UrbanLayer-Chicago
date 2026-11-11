"""Fill building areas, room to build and the card warnings into an existing Discovery index (decision Item 104).

The monthly ``index_build --refresh`` does the same through ``enrich_rows`` for every community area it builds; this
tool applies it to an index already on disk without re-reading the County (minutes instead of hours), then runs the
builder's own ``finalize_index`` so ``populated_fields``, recipe counts and ``data_version`` are recomputed.

Needs ``backend/data/discovery_lot_sources.db`` (``python -m backend.discovery.lot_sources``) and PTAXSIM.

    PYTHONPATH=. python -m backend.discovery.index_backfill [--index <discovery_index.db>] [--report-only]
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

import shapely
from shapely import wkt as shapely_wkt

from backend.discovery.lot_facts import (
    NARROW_STRIP_FT, LotSources, derive_capacity, fill_building_area, lot_warnings, lot_width_ft, pending_rezoning_pin10s,
)
from backend.discovery.lot_sources import DEFAULT_PATH as SOURCES_PATH

log = logging.getLogger(__name__)

# Keys this pass owns: cleared before each fill so a rerun never keeps a stale answer.
OWNED = ("hood", "lot_width_ft", "narrow_strip", "bldg_sqft_unknown", "room_sqft", "room_scope", "complex_lots", "warn_demolition", "warn_vacant_case", "warn_pending_rezoning",
         "warn_landmark")


def lot_outlines(ptaxsim: Path, pin10s: Iterable[str]) -> dict[str, Any]:
    """pin10 -> its newest PTAXSIM outline (lon/lat), the same lots the Profile reasons about."""
    out: dict[str, Any] = {}
    geo = sqlite3.connect(f"file:{ptaxsim}?mode=ro", uri=True)
    try:
        pins = sorted(set(pin10s))
        for i in range(0, len(pins), 900):
            chunk = pins[i:i + 900]
            marks = ",".join("?" * len(chunk))
            latest: dict[str, str] = {}
            for pin10, text in geo.execute(
                f"SELECT pin10, geometry FROM pin_geometry_raw WHERE pin10 IN ({marks}) AND geometry IS NOT NULL "
                "ORDER BY end_year ASC", chunk,
            ):
                latest[pin10] = text
            for pin10, text in latest.items():
                try:
                    g = shapely_wkt.loads(text)
                    if not g.is_valid:
                        g = shapely.make_valid(g)
                except (shapely.errors.GEOSException, ValueError):
                    continue
                if not g.is_empty:
                    out[pin10] = g
    finally:
        geo.close()
    return out


def enrich(attrs: dict[str, Any], pin14: str, lot, src: LotSources, pending: set[str]) -> None:
    """One parcel, in place. Base parcels (suffix 0000) only get building areas and room to build: a condo unit
    PIN would claim the whole building's area as its own."""
    from backend.discovery.index_build import _commercial_area, derive_from_building

    for k in OWNED:
        attrs.pop(k, None)
    pin10 = pin14[:10]
    if lot is not None:
        attrs.update(lot_warnings(lot, src, pending, pin10))
    elif pin10 in pending:
        attrs["warn_pending_rezoning"] = True
    if pin14[10:] != "0000":
        return
    if lot is not None:
        width = lot_width_ft(lot)
        if width is not None:
            attrs["lot_width_ft"] = width
            if width < NARROW_STRIP_FT:
                attrs["narrow_strip"] = True
    from backend.discovery.index_build import unusual_rule
    attrs["unusual"] = unusual_rule(attrs)
    if attrs.get("bldg_sqft_source") in ("footprint", "city_land_inventory"):  # a rerun recomputes these
        attrs.pop("bldg_sqft", None)
        attrs.pop("bldg_sqft_source", None)
    if attrs.get("multi_pin_member"):
        commercial = None
    else:
        commercial = _commercial_area(pin14)
    fill_building_area(attrs, commercial=commercial, lot=lot, src=src, pin10=pin10)
    r = attrs.get("improvement_ratio")
    imp_share = r / (1 + r) if isinstance(r, (int, float)) and r >= 0 else None
    derive_from_building(attrs, imp_share)
    derive_capacity(attrs)


def enrich_rows(rows: list[tuple], *, ptaxsim: Path, sources: Path = SOURCES_PATH,
                pending_db: Path | None = None) -> None:
    """Apply ``enrich`` to builder rows ``(pin, lat, lon, attrs, regions)`` in place; a no-op without the copy."""
    if not sources.exists():
        log.warning("discovery index: %s missing; building areas from footprints and card warnings skipped", sources)
        return
    src = LotSources.load(sources)
    pending = pending_rezoning_pin10s(pending_db) if pending_db else set()
    lots = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in rows})
    from backend.discovery.neighborhoods import neighborhood_of

    for pin, lat, lon, attrs, _regions in rows:
        p = pin.replace("-", "")
        enrich(attrs, p, lots.get(p[:10]), src, pending)
        hood = neighborhood_of(lat, lon)  # the City's named neighborhood (Item 104)
        if hood:
            attrs["hood"] = hood
    complex_room(rows)


def complex_room(rows: list[tuple]) -> None:
    """Room to build for the lots of a multi-parcel complex, as one site (Item 104).

    The Assessor's Commercial Valuation gives one building area for a complex spanning several PIN10s (a shopping
    center, a campus), which describes no single lot (Item 40). Read as a site: allowed floor area summed over its
    lots (each lot's own FAR x land) minus the complex's area. Each member lot with no room of its own carries the
    site's figure, marked ``room_scope: complex`` with ``complex_lots``; a member whose land or FAR is unknown, or
    outside these rows, leaves the whole complex unknown."""
    from backend.discovery.index_build import _commercial_area
    from backend.retrieval.property.commercial_artifact import MultiPinMember

    base = {r[0].replace("-", "")[:10]: r[3] for r in rows if r[0].replace("-", "").endswith("0000")}
    done: dict[tuple[str, ...], float | None] = {}
    for pin10, attrs in base.items():
        if attrs.get("room_sqft") is not None:
            continue
        unit = _commercial_area(pin10 + "0000")
        if not isinstance(unit, MultiPinMember) or not unit.complex_bldg_sqft:
            continue
        members = tuple(sorted({u.replace("-", "")[:10] for u in unit.unit_pins}))
        if members not in done:
            allowed = 0.0
            for m in members:
                a = base.get(m)
                if not a or not a.get("land_sqft") or not a.get("density_band"):
                    allowed = -1.0
                    break
                allowed += a["density_band"] * a["land_sqft"]
            done[members] = None if allowed < 0 else float(max(0.0, round(allowed - unit.complex_bldg_sqft)))
        room = done[members]
        if room is not None:
            attrs["room_sqft"] = room
            attrs["room_scope"] = "complex"
            attrs["complex_lots"] = len(members)


def coverage(rows: Iterable[tuple[str, dict]]) -> dict[str, dict[str, Any]]:
    """Room to build known, by land use, over base parcels (the lots a map draws)."""
    tot: collections.Counter = collections.Counter()
    known: collections.Counter = collections.Counter()
    src: collections.Counter = collections.Counter()
    for pin, a in rows:
        if not pin.replace("-", "").endswith("0000"):
            continue
        u = a.get("land_use_class") or "none"
        tot[u] += 1
        tot["all"] += 1
        if a.get("room_sqft") is not None:
            known[u] += 1
            known["all"] += 1
        src[a.get("bldg_sqft_source") or ("vacant" if a.get("is_vacant") else a.get("bldg_sqft_unknown") or "none")] += 1
    out = {u: {"lots": tot[u], "room_known": known[u], "share": round(known[u] / tot[u], 3)} for u in tot}
    out["building_area_source"] = dict(src)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--index", type=Path, default=None)
    ap.add_argument("--report-only", action="store_true", help="measure coverage, write nothing")
    args = ap.parse_args()

    from backend.config import get_settings
    from backend.discovery.index_build import finalize_index
    from backend.discovery.parcel_index import default_index_path, iter_parcel_rows, read_meta, update_parcel_attrs

    settings = get_settings()
    path = args.index or default_index_path()
    t0 = time.monotonic()
    rows = [(pin, lat, lon, attrs, regions) for pin, lat, lon, attrs, regions in iter_parcel_rows(path)]
    meta = read_meta(path)
    built = datetime.date.fromtimestamp(meta.built_at) if meta and meta.built_at else None
    for r in rows:  # indexes built before 2026-11-10 carry the age of the sale, not its date
        a = r[3]
        if built and a.get("last_sale_date") is None and a.get("sale_recency_days") is not None:
            a["last_sale_date"] = (built - datetime.timedelta(days=int(a["sale_recency_days"]))).isoformat()
    before = coverage((r[0], r[3]) for r in rows)
    enrich_rows(rows, ptaxsim=settings.ptaxsim_db_path,
                pending_db=settings.discovery_index_path.parent / "pending_legislation.db")
    after = coverage((r[0], r[3]) for r in rows)
    warn = collections.Counter(k for r in rows for k in r[3] if k.startswith("warn_"))
    print(json.dumps({"before": before, "after": after, "warnings": warn,
                      "seconds": round(time.monotonic() - t0, 1)}, indent=1))
    if args.report_only:
        return
    for i in range(0, len(rows), 50_000):
        update_parcel_attrs(path, [(r[0], r[3]) for r in rows[i:i + 50_000]])
    version, n = finalize_index(path, community_areas=list(meta.community_areas if meta else []),
                                as_of=datetime.date.today())
    print(json.dumps({"data_version": version, "parcels": n}))


if __name__ == "__main__":
    main()
