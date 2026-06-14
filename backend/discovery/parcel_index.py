"""IndexedParcel (concrete Parcel) + SQLite read/write for the prospecting index.

The offline builder (`index_build.py`) writes a PIN-keyed snapshot here; the loader
(`parcel_source.ensure_loaded`) reads it into `IndexedParcel` objects the pure evaluator
iterates. Static region handles (`neighborhood:<ca>`, `ward:<n>`) are precomputed into each
row; `radius:<lat>,<lon>,<mi>` handles are resolved dynamically from the parcel centroid at
query time, matching the spec's RegionRef model (02/03).
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexMeta:
    """The index's `meta` row — drives the registry response's coverage + populatedFields."""

    data_version: str
    community_areas: list[int]
    populated_fields: list[str]  # filter ids the build actually populated (empty = none)
    built_at: int
    # recipe id -> result count in this index; drives "Live · N" / "No matches yet" on the
    # shelf so a recipe whose FIELDS are populated but whose subset is empty isn't mislabeled.
    recipe_counts: dict[str, int] = field(default_factory=dict)


def default_index_path() -> Path:
    """Location of the prospecting-index SQLite file — on the persistent backend/data volume
    (sibling of chicago.db), so a prod-built index survives redeploys."""
    from backend.config import get_settings

    return get_settings().discovery_index_path


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class IndexedParcel:
    """A `Parcel` backed by a precomputed index row."""

    __slots__ = ("pin", "lat", "lon", "_attrs", "_regions")

    def __init__(
        self,
        pin: str,
        lat: float | None,
        lon: float | None,
        attrs: dict[str, Any],
        regions: Iterable[str],
    ) -> None:
        self.pin = pin
        self.lat = lat
        self.lon = lon
        self._attrs = attrs
        self._regions = set(regions)

    def get(self, field: str) -> Any:
        return self._attrs.get(field)

    def in_region(self, region_ref: str) -> bool:
        if region_ref in self._regions:
            return True
        if region_ref.startswith("radius:"):
            if self.lat is None or self.lon is None:
                return False
            try:
                lat_s, lon_s, mi_s = region_ref[len("radius:"):].split(",")
                return _haversine_mi(self.lat, self.lon, float(lat_s), float(lon_s)) <= float(mi_s)
            except (ValueError, TypeError):
                return False
        return False


_SCHEMA = """
CREATE TABLE IF NOT EXISTS parcels (
    pin     TEXT PRIMARY KEY,
    lat     REAL,
    lon     REAL,
    attrs   TEXT NOT NULL,
    regions TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    data_version     TEXT NOT NULL,
    built_at         INTEGER NOT NULL,
    community_areas  TEXT NOT NULL,
    parcel_count     INTEGER NOT NULL,
    populated_fields TEXT NOT NULL DEFAULT '[]',
    recipe_counts    TEXT NOT NULL DEFAULT '{}'
);
"""


def write_index(
    path: Path,
    *,
    data_version: str,
    built_at: int,
    community_areas: list[int],
    rows: Iterable[tuple[str, float | None, float | None, dict[str, Any], list[str]]],
    populated_fields: list[str] | None = None,
    recipe_counts: dict[str, int] | None = None,
) -> int:
    """Upsert parcel rows (incremental by PIN) and refresh the meta row.

    `rows` are (pin, lat, lon, attrs, regions). Only non-empty attrs are stored so a
    missing field reads back as None (driving `unknownPolicy`). `populated_fields` are the
    filter ids this build actually populated (drives the registry's populatedFields — the
    rest read "coming with the next data update"). `recipe_counts` is per-recipe result
    counts for honest "Live · N" / "No matches yet" shelf badges. Returns the total parcel count.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        # Schema evolution: add newer meta columns to a pre-existing table (CREATE IF NOT
        # EXISTS won't), so an index built under an older schema upgrades on the next build.
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(meta)")}
        if "recipe_counts" not in existing_cols:
            conn.execute("ALTER TABLE meta ADD COLUMN recipe_counts TEXT NOT NULL DEFAULT '{}'")
        conn.executemany(
            "INSERT OR REPLACE INTO parcels (pin, lat, lon, attrs, regions) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    pin,
                    lat,
                    lon,
                    json.dumps({k: v for k, v in attrs.items() if v is not None}, sort_keys=True),
                    json.dumps(sorted(regions)),
                )
                for (pin, lat, lon, attrs, regions) in rows
            ],
        )
        total = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
        cas = ",".join(str(c) for c in sorted(set(community_areas)))
        pf = json.dumps(sorted(set(populated_fields or [])))
        rc = json.dumps(recipe_counts or {}, sort_keys=True)
        conn.execute(
            "INSERT OR REPLACE INTO meta "
            "(id, data_version, built_at, community_areas, parcel_count, populated_fields, recipe_counts) "
            "VALUES (1, ?, ?, ?, ?, ?, ?)",
            (data_version, built_at, cas, total, pf, rc),
        )
        conn.commit()
        return total
    finally:
        conn.close()


def read_meta(path: Path) -> IndexMeta | None:
    """Load the index `meta` row → IndexMeta, or None if absent / unreadable / old-schema.

    Returning None is the SAFE default: the registry then reports coverage "none" and
    EMPTY populatedFields, so a pre-index (or schema-mismatched) state reads as fully
    dormant — never as "everything available."
    """
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(meta)")}
        rc_col = "recipe_counts" if "recipe_counts" in cols else "'{}'"  # tolerate older schema
        row = conn.execute(
            f"SELECT data_version, built_at, community_areas, populated_fields, {rc_col} FROM meta WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        data_version, built_at, cas, pf, rc = row
        areas = [int(x) for x in cas.split(",") if x != ""] if cas else []
        fields = json.loads(pf) if pf else []
        recipe_counts = json.loads(rc) if rc else {}
        return IndexMeta(
            data_version=data_version, community_areas=areas, populated_fields=fields,
            built_at=built_at, recipe_counts=recipe_counts,
        )
    except (sqlite3.DatabaseError, ValueError, json.JSONDecodeError) as exc:
        log.warning("discovery: failed to read index meta at %s: %s", path, exc)
        return None
    finally:
        conn.close()


def derive_sort_fields(attrs: dict[str, Any]) -> dict[str, Any]:
    """Materialize sort-only fields the evaluator's comparator reads (PR3 0/exempt rule).

    `total_assessed_value_sortkey` mirrors the real assessed value EXCEPT it is *absent*
    for tax-exempt or $0 assessments. The `assessed_value` sort key points at this field
    (see `registry.json` sortKeys), so the comparator's existing missing-last ordering
    (`evaluator.py` compare: missing sorts last in both dirs) puts those rows last under
    an `assessed_value` sort — with NO comparator change.

    This is a deliberate evaluator-INPUT change (a precomputed sort-only field), NOT a
    change to what the evaluator filters or displays: the real `total_assessed_value` is
    left intact, so the `assessed_value` *filter* (field `total_assessed_value`) still
    matches exempt/$0 by their true value, and a ResultRow still shows the true value
    (exempt rows stay identifiable via `land_use_class == "exempt"`).
    """
    av = attrs.get("total_assessed_value")
    if attrs.get("land_use_class") == "exempt" or av == 0 or av is None:
        return attrs  # no sort key → comparator treats the sort field as missing (last)
    return {**attrs, "total_assessed_value_sortkey": av}


def read_index(path: Path) -> tuple[str | None, list[IndexedParcel]]:
    """Load the index → (data_version, parcels). Returns (None, []) if absent/empty."""
    if not path.exists():
        return None, []
    conn = sqlite3.connect(path)
    try:
        meta = conn.execute("SELECT data_version FROM meta WHERE id = 1").fetchone()
        if not meta:
            return None, []
        data_version = meta[0]
        parcels = [
            IndexedParcel(pin, lat, lon, derive_sort_fields(json.loads(attrs)), json.loads(regions))
            for pin, lat, lon, attrs, regions in conn.execute(
                "SELECT pin, lat, lon, attrs, regions FROM parcels"
            )
        ]
        return data_version, parcels
    except sqlite3.DatabaseError as exc:
        log.warning("discovery: failed to read index at %s: %s", path, exc)
        return None, []
    finally:
        conn.close()
