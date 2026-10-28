"""Durable, rebuildable snapshot of pending City Clerk zoning matters.

The daily legislation sync is the only writer.  The serving app is a read-only
consumer: it never calls Clerk or Address Points while serving a Profile.

Successful refreshes replace every current matter and its children in one SQLite
transaction.  A failed or suspect refresh appends only a ``sync_runs`` row, leaving the
last good matter rows untouched.  DELETE journaling fits the one-writer/rare-write model
and avoids WAL side files on the shared ``backend_data`` volume.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempted_at TEXT NOT NULL,
    checked_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('ok', 'suspect', 'failed')),
    last_error TEXT,
    contract_problems TEXT NOT NULL DEFAULT '[]',
    candidate_count INTEGER,
    detail_count INTEGER,
    pending_count INTEGER,
    zoning_count INTEGER,
    code_count INTEGER,
    title17_count INTEGER,
    placement_ready_count INTEGER,
    placed_matter_count INTEGER,
    unplaced_matter_count INTEGER,
    location_count INTEGER,
    partial_title_count INTEGER,
    unparsed_title_count INTEGER,
    lifecycle_collapses INTEGER,
    excluded_non_pending INTEGER,
    excluded_attachments INTEGER
);

CREATE TABLE IF NOT EXISTS matters (
    matter_id TEXT PRIMARY KEY,
    lifecycle_id TEXT NOT NULL,
    record_number TEXT NOT NULL UNIQUE,
    original_record_number TEXT,
    status TEXT NOT NULL,
    sub_status TEXT NOT NULL,
    category TEXT NOT NULL,
    matter_type TEXT,
    title TEXT NOT NULL,
    introduced_at TEXT,
    created_at TEXT,
    last_published_at TEXT,
    superseded_by TEXT,
    source_url TEXT NOT NULL,
    title_parse_status TEXT,
    application_number TEXT,
    touches_title17 INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pending_matters_lifecycle ON matters (lifecycle_id);
CREATE INDEX IF NOT EXISTS idx_pending_matters_category ON matters (category);

CREATE TABLE IF NOT EXISTS actions (
    matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    action_at TEXT,
    body TEXT NOT NULL,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    meeting_id TEXT NOT NULL,
    PRIMARY KEY (matter_id, position)
);

CREATE TABLE IF NOT EXISTS attachments (
    matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    url TEXT NOT NULL,
    attachment_type TEXT NOT NULL,
    PRIMARY KEY (matter_id, position)
);

CREATE TABLE IF NOT EXISTS relations (
    matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
    related_record_number TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    PRIMARY KEY (matter_id, related_record_number, relation_type)
);

CREATE TABLE IF NOT EXISTS segments (
    matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    direction TEXT NOT NULL,
    street_name TEXT NOT NULL,
    street_type TEXT,
    lo INTEGER NOT NULL,
    hi INTEGER NOT NULL,
    side TEXT NOT NULL,
    raw TEXT NOT NULL,
    maps TEXT,
    parser_version INTEGER NOT NULL,
    PRIMARY KEY (matter_id, position)
);

CREATE TABLE IF NOT EXISTS locations (
    matter_id TEXT NOT NULL REFERENCES matters(matter_id) ON DELETE CASCADE,
    segment_position INTEGER NOT NULL,
    pin TEXT NOT NULL,
    lat REAL,
    lon REAL,
    address_number INTEGER,
    address_name TEXT,
    method TEXT NOT NULL CHECK (method = 'address_points_range'),
    PRIMARY KEY (matter_id, segment_position, pin)
);
CREATE INDEX IF NOT EXISTS idx_pending_locations_pin ON locations (pin);
CREATE INDEX IF NOT EXISTS idx_pending_locations_lat_lon ON locations (lat, lon);
"""


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class ActionRow:
    action_at: datetime | None
    body: str
    name: str
    text: str
    meeting_id: str


@dataclass(frozen=True)
class AttachmentRow:
    file_name: str
    url: str
    attachment_type: str


@dataclass(frozen=True)
class RelationRow:
    related_record_number: str
    relation_type: str


@dataclass(frozen=True)
class SegmentRow:
    direction: str
    street_name: str
    street_type: str | None
    lo: int
    hi: int
    side: str
    raw: str
    maps: str | None
    parser_version: int


@dataclass(frozen=True)
class LocationRow:
    segment_position: int
    pin: str
    lat: float | None
    lon: float | None
    address_number: int | None
    address_name: str | None
    method: str = "address_points_range"


@dataclass(frozen=True)
class MatterRow:
    matter_id: str
    lifecycle_id: str
    record_number: str
    original_record_number: str | None
    status: str
    sub_status: str
    category: str
    matter_type: str | None
    title: str
    introduced_at: datetime | None
    created_at: datetime | None
    last_published_at: datetime | None
    superseded_by: str | None
    source_url: str
    title_parse_status: str | None
    application_number: str | None
    touches_title17: bool
    actions: tuple[ActionRow, ...] = ()
    attachments: tuple[AttachmentRow, ...] = ()
    relations: tuple[RelationRow, ...] = ()
    segments: tuple[SegmentRow, ...] = ()
    locations: tuple[LocationRow, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    checked_at: datetime
    matters: tuple[MatterRow, ...]
    candidate_count: int
    detail_count: int
    lifecycle_collapses: int
    excluded_non_pending: int
    excluded_attachments: int
    placement_ready_count: int
    partial_title_count: int
    unparsed_title_count: int

    @property
    def counts(self) -> dict[str, int]:
        zoning = [m for m in self.matters if m.category.startswith("ZONING RECLASSIFICATIONS")]
        return {
            "candidates": self.candidate_count,
            "details": self.detail_count,
            "pending": len(self.matters),
            "zoning": len(zoning),
            "code": sum(1 for m in self.matters if m.category.startswith("MUNICIPAL CODE AMENDMENTS")),
            "title17": sum(1 for m in self.matters if m.touches_title17),
            "placement_ready": self.placement_ready_count,
            "placed_matters": sum(1 for m in zoning if m.locations),
            "unplaced_matters": sum(1 for m in zoning if not m.locations),
            "locations": sum(len(m.locations) for m in zoning),
            "partial_titles": self.partial_title_count,
            "unparsed_titles": self.unparsed_title_count,
            "lifecycle_collapses": self.lifecycle_collapses,
            "excluded_non_pending": self.excluded_non_pending,
            "excluded_attachments": self.excluded_attachments,
        }


@dataclass(frozen=True)
class StoreStatus:
    latest_status: str
    last_attempt_at: datetime
    checked_at: datetime | None
    last_error: str | None
    contract_problems: tuple[str, ...]
    counts: dict[str, int | None] = field(default_factory=dict)


def _configure(con: sqlite3.Connection) -> None:
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=DELETE")
    version = int(con.execute("PRAGMA user_version").fetchone()[0])
    if version not in (0, 1, SCHEMA_VERSION):
        raise sqlite3.DatabaseError(
            f"pending legislation schema {version} is not supported (expected {SCHEMA_VERSION})"
        )
    con.executescript(_SCHEMA)
    if version == 1:
        con.execute("ALTER TABLE sync_runs ADD COLUMN placed_matter_count INTEGER")
        con.execute("ALTER TABLE sync_runs ADD COLUMN unplaced_matter_count INTEGER")
        con.execute("ALTER TABLE sync_runs ADD COLUMN location_count INTEGER")
    if version < SCHEMA_VERSION:
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        con.commit()


class Store:
    """The daily sync's read-write handle. Use as a context manager."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30)
        _configure(self.con)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc) -> None:
        self.con.close()

    def replace(self, snapshot: Snapshot) -> None:
        """Replace the current snapshot and record its run in one transaction."""
        counts = snapshot.counts
        try:
            self.con.execute("BEGIN IMMEDIATE")
            self.con.execute("DELETE FROM matters")
            for matter in snapshot.matters:
                self.con.execute(
                    """INSERT INTO matters (
                           matter_id, lifecycle_id, record_number, original_record_number, status, sub_status,
                           category, matter_type, title, introduced_at, created_at, last_published_at,
                           superseded_by, source_url, title_parse_status, application_number, touches_title17
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        matter.matter_id, matter.lifecycle_id, matter.record_number,
                        matter.original_record_number, matter.status, matter.sub_status, matter.category,
                        matter.matter_type, matter.title, iso(matter.introduced_at), iso(matter.created_at),
                        iso(matter.last_published_at), matter.superseded_by, matter.source_url,
                        matter.title_parse_status, matter.application_number, int(matter.touches_title17),
                    ),
                )
                self.con.executemany(
                    "INSERT INTO actions VALUES (?,?,?,?,?,?,?)",
                    [
                        (matter.matter_id, i, iso(a.action_at), a.body, a.name, a.text, a.meeting_id)
                        for i, a in enumerate(matter.actions)
                    ],
                )
                self.con.executemany(
                    "INSERT INTO attachments VALUES (?,?,?,?,?)",
                    [
                        (matter.matter_id, i, a.file_name, a.url, a.attachment_type)
                        for i, a in enumerate(matter.attachments)
                    ],
                )
                self.con.executemany(
                    "INSERT INTO relations VALUES (?,?,?)",
                    [
                        (matter.matter_id, r.related_record_number, r.relation_type)
                        for r in matter.relations
                    ],
                )
                self.con.executemany(
                    "INSERT INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [
                        (
                            matter.matter_id, i, s.direction, s.street_name, s.street_type,
                            s.lo, s.hi, s.side, s.raw, s.maps, s.parser_version,
                        )
                        for i, s in enumerate(matter.segments)
                    ],
                )
                self.con.executemany(
                    "INSERT INTO locations VALUES (?,?,?,?,?,?,?,?)",
                    [
                        (
                            matter.matter_id, loc.segment_position, loc.pin, loc.lat, loc.lon,
                            loc.address_number, loc.address_name, loc.method,
                        )
                        for loc in matter.locations
                    ],
                )
            self.con.execute(
                """INSERT INTO sync_runs (
                       attempted_at, checked_at, status, candidate_count, detail_count, pending_count,
                       zoning_count, code_count, title17_count, placement_ready_count,
                       placed_matter_count, unplaced_matter_count, location_count,
                       partial_title_count, unparsed_title_count, lifecycle_collapses,
                       excluded_non_pending, excluded_attachments
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    iso(snapshot.checked_at), iso(snapshot.checked_at), "ok", counts["candidates"],
                    counts["details"], counts["pending"], counts["zoning"], counts["code"],
                    counts["title17"], counts["placement_ready"],
                    counts["placed_matters"], counts["unplaced_matters"], counts["locations"],
                    counts["partial_titles"], counts["unparsed_titles"], counts["lifecycle_collapses"],
                    counts["excluded_non_pending"], counts["excluded_attachments"],
                ),
            )
            self.con.commit()
        except BaseException:
            self.con.rollback()
            raise

    def record_problem(
        self,
        attempted_at: datetime,
        *,
        status: str,
        error: str,
        contract_problems: tuple[str, ...] = (),
    ) -> None:
        if status not in {"suspect", "failed"}:
            raise ValueError(f"invalid pending sync problem status {status!r}")
        self.con.execute(
            "INSERT INTO sync_runs (attempted_at, status, last_error, contract_problems) VALUES (?,?,?,?)",
            (iso(attempted_at), status, error[:500], json.dumps(contract_problems)),
        )
        self.con.commit()


def read_status(path: Path | str) -> StoreStatus | None:
    """Latest attempt plus the last successful snapshot's date/counts; no file means not run."""
    p = Path(path)
    if not p.exists():
        return None
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2)) as con:
        con.row_factory = sqlite3.Row
        latest = con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        if latest is None:
            return None
        success = con.execute(
            "SELECT * FROM sync_runs WHERE status='ok' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    count_columns = {
        "candidates": "candidate_count",
        "details": "detail_count",
        "pending": "pending_count",
        "zoning": "zoning_count",
        "code": "code_count",
        "title17": "title17_count",
        "placement_ready": "placement_ready_count",
        "placed_matters": "placed_matter_count",
        "unplaced_matters": "unplaced_matter_count",
        "locations": "location_count",
        "partial_titles": "partial_title_count",
        "unparsed_titles": "unparsed_title_count",
        "lifecycle_collapses": "lifecycle_collapses",
        "excluded_non_pending": "excluded_non_pending",
        "excluded_attachments": "excluded_attachments",
    }
    raw_problems = json.loads(latest["contract_problems"] or "[]")
    return StoreStatus(
        latest_status=latest["status"],
        last_attempt_at=parse_iso(latest["attempted_at"]),
        checked_at=parse_iso(success["checked_at"]) if success else None,
        last_error=latest["last_error"],
        contract_problems=tuple(str(p) for p in raw_problems),
        counts={
            key: success[column] if success is not None and column in success.keys() else None
            for key, column in count_columns.items()
        },
    )
