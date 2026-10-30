"""The status store: ``data_health.db``, a SQLite file the checker writes and the app reads.

Plain ``sqlite3`` (no aiosqlite), journal mode DELETE rather than WAL: one writer, one write a
day, so the app's read-only connection (another container, the same volume) never needs the
``-wal``/``-shm`` side files. The checker is the only writer.

Tables:
- ``source_status``: the latest row per source, plus what the alerting needs to remember
  (the state we last notified about, when, and whether the last probe failed).
- ``source_history``: append-only, pruned after 180 days.
- ``check_runs``: one row per run.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

RETENTION_DAYS = 180
LATE_AFTER_HOURS = 36

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_status (
    source_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL,
    as_of TEXT,
    basis TEXT,
    age_days INTEGER,
    checked_at TEXT NOT NULL,
    state_since TEXT NOT NULL,
    probe_error INTEGER NOT NULL DEFAULT 0,
    alerted_state TEXT,
    alerted_at TEXT,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS source_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    as_of TEXT,
    age_days INTEGER,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_source_history_source ON source_history (source_id, checked_at);
CREATE TABLE IF NOT EXISTS check_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sources INTEGER NOT NULL DEFAULT 0,
    alarms INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
"""


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)


@dataclass(frozen=True)
class Stored:
    """What the last run left for one source."""

    source_id: str
    state: str
    reason: str
    severity: str
    checked_at: datetime
    state_since: datetime
    probe_error: bool
    alerted_state: str | None
    alerted_at: datetime | None


def _stored(row: sqlite3.Row) -> Stored:
    return Stored(
        source_id=row["source_id"], state=row["state"], reason=row["reason"], severity=row["severity"],
        checked_at=parse_iso(row["checked_at"]), state_since=parse_iso(row["state_since"]),
        probe_error=bool(row["probe_error"]), alerted_state=row["alerted_state"],
        alerted_at=parse_iso(row["alerted_at"]) if row["alerted_at"] else None,
    )


class Store:
    """The checker's read-write handle. Use as a context manager."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=DELETE")
        self.con.executescript(_SCHEMA)

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.con.close()

    # --- reads -------------------------------------------------------------------------
    def previous(self) -> dict[str, Stored]:
        return {r["source_id"]: _stored(r) for r in self.con.execute("SELECT * FROM source_status")}

    def first_run_at(self) -> datetime | None:
        row = self.con.execute("SELECT MIN(started_at) AS t FROM check_runs").fetchone()
        return parse_iso(row["t"]) if row and row["t"] else None

    def last_run_finished(self) -> datetime | None:
        return last_run_finished(self.con)

    # --- writes ------------------------------------------------------------------------
    def start_run(self, now: datetime) -> int:
        cur = self.con.execute("INSERT INTO check_runs (started_at) VALUES (?)", (iso(now),))
        self.con.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, now: datetime, *, sources: int, alarms: int, requests: int,
                   error: str | None = None) -> None:
        self.con.execute(
            "UPDATE check_runs SET finished_at=?, sources=?, alarms=?, requests=?, error=? WHERE id=?",
            (iso(now), sources, alarms, requests, error, run_id),
        )
        self.con.commit()

    def record(self, *, source_id: str, state: str, reason: str, severity: str, as_of: str | None,
               basis: str | None, age_days: int | None, now: datetime, probe_error: bool,
               latency_ms: int, requests: int, prev: Stored | None,
               alerted_state: str | None, alerted_at: datetime | None) -> None:
        since = prev.state_since if prev and prev.state == state else now
        self.con.execute(
            """INSERT INTO source_status (source_id, state, reason, severity, as_of, basis, age_days, checked_at,
                   state_since, probe_error, alerted_state, alerted_at, latency_ms, requests)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_id) DO UPDATE SET state=excluded.state, reason=excluded.reason,
                   severity=excluded.severity, as_of=excluded.as_of, basis=excluded.basis,
                   age_days=excluded.age_days, checked_at=excluded.checked_at, state_since=excluded.state_since,
                   probe_error=excluded.probe_error, alerted_state=excluded.alerted_state,
                   alerted_at=excluded.alerted_at, latency_ms=excluded.latency_ms, requests=excluded.requests""",
            (source_id, state, reason, severity, as_of, basis, age_days, iso(now), iso(since), int(probe_error),
             alerted_state, iso(alerted_at) if alerted_at else None, latency_ms, requests),
        )
        self.con.execute(
            "INSERT INTO source_history (source_id, checked_at, state, reason, as_of, age_days, latency_ms, requests)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (source_id, iso(now), state, reason, as_of, age_days, latency_ms, requests),
        )

    def forget_missing(self, keep: set[str]) -> list[str]:
        """Drop rows for sources no longer in the run (a retired source, or a finished drill)."""
        gone = [sid for sid in self.previous() if sid not in keep]
        for sid in gone:
            self.con.execute("DELETE FROM source_status WHERE source_id = ?", (sid,))
        return gone

    def forget(self, source_id: str) -> bool:
        cur = self.con.execute("DELETE FROM source_status WHERE source_id = ?", (source_id,))
        self.con.execute("DELETE FROM source_history WHERE source_id = ?", (source_id,))
        self.con.commit()
        return cur.rowcount > 0

    def prune(self, now: datetime) -> None:
        cutoff = iso(now - timedelta(days=RETENTION_DAYS))
        self.con.execute("DELETE FROM source_history WHERE checked_at < ?", (cutoff,))
        self.con.execute("DELETE FROM check_runs WHERE started_at < ?", (cutoff,))

    def commit(self) -> None:
        self.con.commit()


def last_run_finished(con: sqlite3.Connection) -> datetime | None:
    row = con.execute("SELECT MAX(finished_at) AS t FROM check_runs WHERE error IS NULL").fetchone()
    return parse_iso(row[0]) if row and row[0] else None


@contextmanager
def open_readonly(path: Path | str) -> Iterator[sqlite3.Connection | None]:
    """A read-only handle for the app, or None when the file doesn't exist yet."""
    p = Path(path)
    if not p.exists():
        yield None
        return
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2)) as con:
        con.row_factory = sqlite3.Row
        yield con


def health_block(path: Path | str, now: datetime | None = None) -> dict:
    """The informational ``/health`` block. Never raises: a broken store reads as a late checker."""
    now = now or datetime.now(timezone.utc)
    late = {"checker": "late", "last_run_age_h": None, "alarms": 0}
    try:
        with open_readonly(path) as con:
            if con is None:
                return late
            finished = last_run_finished(con)
            alarms = con.execute(
                "SELECT COUNT(*) FROM source_status WHERE state IN ('alarm','error')"
            ).fetchone()[0]
    except Exception:
        return late
    if finished is None:
        return {**late, "alarms": int(alarms)}
    age_h = (now - finished).total_seconds() / 3600
    return {"checker": "ok" if age_h <= LATE_AFTER_HOURS else "late",
            "last_run_age_h": round(age_h, 1), "alarms": int(alarms)}
