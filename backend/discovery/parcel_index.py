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
import sys
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


def upsert_parcels(
    path: Path,
    rows: Iterable[tuple[str, float | None, float | None, dict[str, Any], list[str]]],
) -> None:
    """Upsert parcel rows (incremental by PIN). No meta, no cross-parcel fields.

    `rows` are (pin, lat, lon, attrs, regions). Only non-empty attrs are stored so a missing
    field reads back as None (driving `unknownPolicy`). This is the per-batch ingest half of a
    build: the chunked builder calls it once per community area so peak memory is one CA's rows,
    never the whole set. Cross-parcel fields (e.g. `value_percentile`) and the meta row are added
    afterward by the finalize pass (`index_build.finalize_index`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
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
        conn.commit()
    finally:
        conn.close()


def write_meta(
    path: Path,
    *,
    data_version: str,
    built_at: int,
    community_areas: list[int],
    populated_fields: list[str] | None = None,
    recipe_counts: dict[str, int] | None = None,
) -> int:
    """Write/refresh the index `meta` row. Returns the current total parcel count.

    `populated_fields` are the filter ids the build actually populated (drives the registry's
    populatedFields — the rest read "coming with the next data update"). `recipe_counts` is
    per-recipe result counts for honest "Live · N" / "No matches yet" shelf badges. Both are
    cumulative over the whole index (the finalize pass computes them over every parcel present).
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
    """Upsert parcel rows and refresh the meta row in one shot. Returns the total parcel count.

    Thin wrapper over `upsert_parcels` + `write_meta` — convenient for small/test builds that
    have all rows in memory. The production chunked builder calls the two halves separately
    (per-CA `upsert_parcels`, then one `finalize_index` that ends in `write_meta`).
    """
    upsert_parcels(path, rows)
    return write_meta(
        path,
        data_version=data_version,
        built_at=built_at,
        community_areas=community_areas,
        populated_fields=populated_fields,
        recipe_counts=recipe_counts,
    )


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


def _interned_attrs(attrs_json: str) -> dict[str, Any]:
    """Parse an `attrs` cell, interning the field-name *keys*.

    json.loads mints a fresh str for every key on every row, so across ~949k
    parcels the same ~25 field names become tens of millions of duplicate string
    objects (a large chunk of the resident index). Interning collapses them to one
    shared object per name. The sort-only key derive_sort_fields adds is interned
    here too. Values are deliberately left untouched — they include high-cardinality
    strings (e.g. addresses) whose interning would only bloat the never-collected
    intern table for zero dedup benefit.
    """
    derived = derive_sort_fields(json.loads(attrs_json))
    return {sys.intern(k): v for k, v in derived.items()}


def _interned_regions(regions_json: str) -> list[str]:
    """Parse a `regions` cell, interning each ref.

    Region refs (community-area / ward / flag labels) repeat across nearly every
    parcel, so interning collapses ~949k×N duplicate strings to a handful.
    """
    return [sys.intern(r) for r in json.loads(regions_json)]


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
            IndexedParcel(pin, lat, lon, _interned_attrs(attrs), _interned_regions(regions))
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


def iter_parcel_rows(
    path: Path,
) -> Iterable[tuple[str, float | None, float | None, dict[str, Any], list[str]]]:
    """Stream stored parcel rows as (pin, lat, lon, attrs, regions) — bounded memory.

    Yields the RAW stored attrs (no `derive_sort_fields`), so the finalize pass can compute
    cross-parcel fields and write them straight back. Uses a SQLite cursor (rows are pulled
    lazily), so it works over the full ~1.8M-parcel index without materializing it.
    """
    if not path.exists():
        return
    conn = sqlite3.connect(path)
    try:
        for pin, lat, lon, attrs, regions in conn.execute(
            "SELECT pin, lat, lon, attrs, regions FROM parcels"
        ):
            yield pin, lat, lon, json.loads(attrs), json.loads(regions)
    finally:
        conn.close()


def update_parcel_attrs(path: Path, updates: Iterable[tuple[str, dict[str, Any]]]) -> None:
    """Overwrite the stored attrs of specific parcels: `updates` = (pin, attrs) pairs (executemany).

    Used by the cross-parcel finalize pass to persist computed fields (e.g. `value_percentile`):
    finalize already holds each row's attrs from its streamed scan, so it passes the merged dict
    back here directly — no per-row read needed. Only non-null attrs are stored (a value set to
    None drops the key, matching `upsert_parcels`).
    """
    conn = sqlite3.connect(path)
    try:
        conn.executemany(
            "UPDATE parcels SET attrs = ? WHERE pin = ?",
            [
                (json.dumps({k: v for k, v in attrs.items() if v is not None}, sort_keys=True), pin)
                for pin, attrs in updates
            ],
        )
        conn.commit()
    finally:
        conn.close()
