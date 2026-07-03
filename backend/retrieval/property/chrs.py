"""CHRS orange/red-rated building lookup — local artifact, no network.

The Chicago Historic Resources Survey (1996, frozen) rates ~9,100 orange and
~150 red buildings; either rating triggers the Municipal Code's 90-day
demolition-permit hold (§ 2-120-740 review) — a real teardown-risk fact.
The Socrata asset is API-restricted, so the footprints ship as a committed
artifact (``ingestion/data/chrs_orange_red.json.gz``, built by
``ingestion.build_chrs_artifact``) and are matched here by point-in-polygon
via a lazily built shapely STRtree (~9.3k tiny rings, loads in well under a
second, once per process).
"""

from __future__ import annotations

import gzip
import json
import logging
import threading

from backend.config import get_settings

log = logging.getLogger(__name__)

ARTIFACT_FILENAME = "chrs_orange_red.json.gz"

# ~2.5 m tolerance: address points sit on the building, but rooftop snapping
# can land a few meters off a small footprint's edge.
MATCH_TOLERANCE_DEG = 0.000025

_lock = threading.Lock()
_loaded = False
_tree = None  # shapely STRtree
_records: list[dict] = []
_geoms: list = []


def _load() -> None:
    """Build the STRtree once per process; a missing/invalid artifact degrades
    to 'no CHRS data' (flag absent) rather than failing parcel flags."""
    global _loaded, _tree, _records, _geoms
    with _lock:
        if _loaded:
            return
        try:
            from shapely.geometry import Polygon
            from shapely.strtree import STRtree

            path = get_settings().data_dir / ARTIFACT_FILENAME
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                raw = json.load(fh)
            records, geoms = [], []
            for rec in raw:
                try:
                    geoms.append(Polygon(rec["ring"]))
                    records.append(rec)
                except Exception:  # noqa: BLE001 — skip a malformed ring
                    continue
            _records, _geoms = records, geoms
            _tree = STRtree(geoms)
            log.info("CHRS artifact loaded: %d orange/red footprints", len(records))
        except Exception as exc:  # noqa: BLE001
            log.warning("CHRS artifact unavailable (%s) — flag disabled", exc)
            _records, _geoms, _tree = [], [], None
        finally:
            _loaded = True


def lookup_chrs(lat: float, lon: float) -> dict | None:
    """The orange/red CHRS building at this point, or None.

    Returns ``{"color": "orange"|"red", "name": ..., "address": ...}``.
    Not being surveyed is the normal state — an expected absence.
    """
    if not _loaded:
        _load()
    if _tree is None:
        return None

    from shapely.geometry import Point

    point = Point(lon, lat)
    try:
        idxs = _tree.query(point.buffer(MATCH_TOLERANCE_DEG))
    except Exception as exc:  # noqa: BLE001
        log.warning("CHRS tree query failed at (%s, %s): %s", lat, lon, exc)
        return None
    best = None
    best_dist = float("inf")
    for i in idxs:
        geom = _geoms[int(i)]
        dist = geom.distance(point)
        if dist <= MATCH_TOLERANCE_DEG and dist < best_dist:
            best, best_dist = _records[int(i)], dist
    if best is None:
        return None
    return {"color": best["color"], "name": best.get("name"), "address": best.get("address")}


def reset_for_tests() -> None:
    global _loaded, _tree, _records, _geoms
    with _lock:
        _loaded = False
        _tree = None
        _records = []
        _geoms = []
