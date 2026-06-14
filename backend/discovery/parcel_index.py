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
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)


def default_index_path() -> Path:
    """Location of the prospecting-index SQLite file (sibling of chicago.db)."""
    from backend.config import get_settings

    return get_settings().data_dir / "discovery_index.db"


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
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    data_version    TEXT NOT NULL,
    built_at        INTEGER NOT NULL,
    community_areas TEXT NOT NULL,
    parcel_count    INTEGER NOT NULL
);
"""


def write_index(
    path: Path,
    *,
    data_version: str,
    built_at: int,
    community_areas: list[int],
    rows: Iterable[tuple[str, float | None, float | None, dict[str, Any], list[str]]],
) -> int:
    """Upsert parcel rows (incremental by PIN) and refresh the meta row.

    `rows` are (pin, lat, lon, attrs, regions). Only non-empty attrs are stored so a
    missing field reads back as None (driving `unknownPolicy`). Returns the total
    parcel count after the upsert.
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
        total = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
        cas = ",".join(str(c) for c in sorted(set(community_areas)))
        conn.execute(
            "INSERT OR REPLACE INTO meta (id, data_version, built_at, community_areas, parcel_count) "
            "VALUES (1, ?, ?, ?, ?)",
            (data_version, built_at, cas, total),
        )
        conn.commit()
        return total
    finally:
        conn.close()


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
            IndexedParcel(pin, lat, lon, json.loads(attrs), json.loads(regions))
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
