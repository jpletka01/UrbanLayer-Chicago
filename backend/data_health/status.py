"""The checker's latest finding for one source, for the request path (WS0 M3).

``provenance.resolve_as_of`` asks here for a source-level date when the response itself
carries none. Read-only, cached by the store file's mtime (one read per daily check, not one
per request), and never raises: a missing, unreadable or stale-schema store means "no
answer", and provenance falls through to the registry's frozen vintage, then to "queried".
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.data_health.store import open_readonly

log = logging.getLogger(__name__)

# Tests point this at a temp file; None = settings.data_health_db_path.
DB_FILE: Path | None = None

_cache: tuple[Path, int, dict[str, dict]] | None = None


def _path() -> Path:
    if DB_FILE is not None:
        return DB_FILE
    from backend.config import get_settings

    return get_settings().data_health_db_path


def _load(path: Path) -> dict[str, dict]:
    global _cache
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return {}
    if _cache and _cache[0] == path and _cache[1] == mtime:
        return _cache[2]
    rows: dict[str, dict] = {}
    try:
        with open_readonly(path) as con:
            if con is not None:
                for r in con.execute("SELECT source_id, state, as_of, basis, age_days, checked_at FROM source_status"):
                    rows[r["source_id"]] = dict(r)
    except (sqlite3.Error, OSError) as exc:
        log.warning("data-health store unreadable: %s", exc)
        return {}
    _cache = (path, mtime, rows)
    return rows


def latest(source_id: str) -> dict | None:
    """``{"content_through"|"published_at": "YYYY-MM-DD", "state", "checked_at"}`` for a source
    the checker has probed, else None. ``content_through`` is the newest date in the data;
    ``published_at`` is when the publisher last touched it."""
    row = _load(_path()).get(source_id)
    if not row or not row.get("as_of") or row["state"] == "unknown":
        return None
    key = "content_through" if row.get("basis") == "content" else "published_at"
    return {key: str(row["as_of"])[:10], "state": row["state"], "checked_at": row["checked_at"]}


def reset_cache() -> None:
    global _cache
    _cache = None
