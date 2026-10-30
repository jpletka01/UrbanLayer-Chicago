"""Live outcomes of the app's own calls to its sources, and the dev fault flag (WS6 M7, plan §4.2).

The daily checker looks at each source once. Between two checks a source can be down for hours and
every answer in that window leaves it out. This catches that: the request path counts, per source,
how many calls it made and how many failed (``record``); an hourly flush writes the counts to
``data_health_live.db``; the checker reads the last 24 hours and turns a high failure rate into
``warn`` (over 20% of at least 10 calls) or ``alarm`` (over 50%).

Two files, two writers. ``data_health.db`` is written only by the checker; this one is written only
by the app, so neither container ever writes the other's file (journal mode DELETE, one writer each).

Counting is in memory, O(1) per call, and never raises: telemetry must not be able to fail an answer.

``DATA_HEALTH_FAULT`` forces a source to fail, for checking that every surface says "couldn't check"
(never in production):

    DATA_HEALTH_FAULT=overlay:5                      # a City map overlay layer (5 = landmark building)
    DATA_HEALTH_FAULT="overlay:5,6;source:chi.crime" # several, ";"-separated, comma-separated ids
    DATA_HEALTH_FAULT=socrata:ijzp-q8t2              # a Socrata dataset by its id
    DATA_HEALTH_FAULT=source:fed.fema.nfhl           # FEMA's flood map (a registry source id)

``source:`` takes a registry source id and covers the Socrata datasets, the overlay layers, the zoning
layer, the census tract call and FEMA's flood lookup that source stands for.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

WARN_RATE = 0.20
ALARM_RATE = 0.50
MIN_CALLS = 10
WINDOW_HOURS = 24
RETENTION_DAYS = 14
FLUSH_SECONDS = 3600

# Tests point this at a temp file; None = settings.data_health_live_db_path.
DB_FILE: Path | None = None

_lock = threading.Lock()
_counts: dict[str, list[int]] = {}  # source_id -> [attempts, failures] since the last flush

_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_calls (
    hour TEXT NOT NULL,
    source_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hour, source_id)
);
"""


def _path() -> Path:
    if DB_FILE is not None:
        return DB_FILE
    from backend.config import get_settings

    return get_settings().data_health_live_db_path


# --- counting ---------------------------------------------------------------------------------------------

def record(source_id: str | None, ok: bool) -> None:
    """Count one call to a source. ``source_id`` is a registry id; None or an unknown id is ignored at flush."""
    if not source_id:
        return
    try:
        with _lock:
            c = _counts.setdefault(source_id, [0, 0])
            c[0] += 1
            if not ok:
                c[1] += 1
    except Exception:  # telemetry never fails an answer
        pass


def pending() -> dict[str, tuple[int, int]]:
    with _lock:
        return {k: (v[0], v[1]) for k, v in _counts.items()}


def reset() -> None:
    with _lock:
        _counts.clear()


def flush(path: Path | None = None, *, now: datetime | None = None) -> int:
    """Add the counts since the last flush to this hour's rows and clear them. Returns the sources written.
    Rows for ids the registry doesn't know are dropped (a typo must not create a phantom source)."""
    from backend.data_health.registry import BY_ID

    with _lock:
        taken = {k: v for k, v in _counts.items() if k in BY_ID}
        _counts.clear()
    if not taken:
        return 0
    now = now or datetime.now(timezone.utc)
    hour = now.strftime("%Y-%m-%dT%H")
    path = path or _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=5)) as con:
            con.execute("PRAGMA journal_mode=DELETE")
            con.executescript(_SCHEMA)
            for sid, (attempts, failures) in taken.items():
                con.execute(
                    "INSERT INTO live_calls (hour, source_id, attempts, failures) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(hour, source_id) DO UPDATE SET attempts = attempts + excluded.attempts, "
                    "failures = failures + excluded.failures",
                    (hour, sid, attempts, failures),
                )
            cutoff = (now - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%dT%H")
            con.execute("DELETE FROM live_calls WHERE hour < ?", (cutoff,))
            con.commit()
        return len(taken)
    except Exception as exc:
        log.warning("live failure flush failed: %s", exc)
        with _lock:  # keep the counts for the next flush rather than lose them
            for sid, (a, f) in taken.items():
                c = _counts.setdefault(sid, [0, 0])
                c[0] += a
                c[1] += f
        return 0


async def flush_loop(interval: float = FLUSH_SECONDS) -> None:
    """The app's hourly flush. Cancelled at shutdown, which flushes once more."""
    try:
        while True:
            await asyncio.sleep(interval)
            await asyncio.get_running_loop().run_in_executor(None, flush)
    except asyncio.CancelledError:
        flush()
        raise


# --- reading (the checker) ----------------------------------------------------------------------------------

def read_window(path: Path | None = None, *, hours: int = WINDOW_HOURS, now: datetime | None = None) -> dict[str, tuple[int, int]]:
    """``{source_id: (attempts, failures)}`` over the last ``hours``. Read-only; {} when there is no file."""
    path = path or _path()
    if not path.exists():
        return {}
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H")
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)) as con:
            rows = con.execute(
                "SELECT source_id, SUM(attempts), SUM(failures) FROM live_calls WHERE hour >= ? GROUP BY source_id", (since,),
            ).fetchall()
    except sqlite3.Error as exc:
        log.warning("live failure read failed: %s", exc)
        return {}
    return {sid: (int(a or 0), int(f or 0)) for sid, a, f in rows}


def rate_finding(attempts: int, failures: int) -> tuple[str, str] | None:
    """``("warn"|"alarm", text)`` when the app's own calls to a source fail too often, else None."""
    if attempts < MIN_CALLS:
        return None
    rate = failures / attempts
    text = f"{failures} of {attempts} live calls failed in the last {WINDOW_HOURS} h ({rate:.0%})"
    if rate > ALARM_RATE:
        return "alarm", text
    if rate > WARN_RATE:
        return "warn", text
    return None


# --- the dev fault flag --------------------------------------------------------------------------------------

def _spec() -> dict[str, set[str]]:
    """``DATA_HEALTH_FAULT`` parsed to ``{kind: {ids}}``. Empty in production, whatever the variable says."""
    raw = os.environ.get("DATA_HEALTH_FAULT", "").strip()
    if not raw:
        return {}
    from backend.config import get_settings

    if get_settings().environment == "production":
        return {}
    out: dict[str, set[str]] = {}
    for part in raw.split(";"):
        kind, _, ids = part.partition(":")
        if kind.strip() and ids.strip():
            out.setdefault(kind.strip(), set()).update(x.strip() for x in ids.split(",") if x.strip())
    return out


def fault_ids(kind: str) -> set[str]:
    return _spec().get(kind, set())


def fault(kind: str, ident: str | int, source_id: str | None = None) -> bool:
    """True when ``kind:ident`` (or the registry source it belongs to) is forced to fail."""
    spec = _spec()
    if not spec:
        return False
    return str(ident) in spec.get(kind, set()) or (source_id is not None and source_id in spec.get("source", set()))


# --- which registry source a call belongs to ----------------------------------------------------------------------

_by_dataset: dict[str, str] | None = None


def source_for_dataset(dataset_id: str) -> str | None:
    """The registry id of a Socrata dataset (``locator`` is ``portal:dataset``)."""
    global _by_dataset
    if _by_dataset is None:
        from backend.data_health.registry import SOURCES

        _by_dataset = {s.locator.split(":", 1)[1]: s.id for s in SOURCES if s.kind == "socrata" and ":" in s.locator}
    return _by_dataset.get(dataset_id)


def source_for_overlay(layer_type: str) -> str:
    return f"chi.zoning.overlay.{layer_type}"
