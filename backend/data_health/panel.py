"""What the admin "Data health" panel shows (WS6 M3; plan §3.8).

The registry joined with the checker's stored status, read through the same read-only handle
the ``/health`` block uses. Pure and offline: no network, no probes, and it imports none of
the serving stack. A missing or unreadable store is a "checker late" payload, never an error
(an admin looking at a red panel must not meet a 500).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.data_health.registry import PORTAL_HOSTS, SOURCES, SourceSpec
from backend.data_health.store import LATE_AFTER_HOURS, iso, last_run_finished, open_readonly

HISTORY_DAYS = 90
RECENT_RUNS = 10
# deploy/data-health-check.timer: 05:37 UTC daily (plus up to 2 minutes of random delay).
RUN_HOUR, RUN_MINUTE = 5, 37

# Worst first. The plan lists alarm before error; both are red, and the critical ones lead each state.
STATE_ORDER = ("alarm", "error", "warn", "unknown", "acked", "ok", "frozen_ok")
_RANK = {s: i for i, s in enumerate(STATE_ORDER)}


def publisher_link(spec: SourceSpec) -> str | None:
    """Where a person reads the source: the portal's dataset page, the ArcGIS service, or the API."""
    if spec.kind == "socrata":
        portal, _, dataset = spec.locator.partition(":")
        host = PORTAL_HOSTS.get(portal)
        return f"{host}/d/{dataset}" if host else None
    return spec.locator if spec.locator.startswith("http") else None


def next_run(now: datetime) -> datetime:
    today = now.astimezone(timezone.utc).replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    return today if today > now else today + timedelta(days=1)


def _row(spec: SourceSpec | None, stored: sqlite3.Row | None, source_id: str) -> dict[str, Any]:
    ack = spec.ack if spec else None
    contract = spec.contract if spec else None
    return {
        "id": source_id,
        "name": spec.name if spec else source_id,
        "publisher": spec.publisher if spec else None,
        "link": publisher_link(spec) if spec else None,
        "tier": spec.tier if spec else None,
        "kind": spec.kind if spec else None,
        "severity": (stored["severity"] if stored else None) or (spec.severity if spec else "standard"),
        "owner_modules": list(spec.owner_modules) if spec else [],
        "surfaces": list(spec.surfaces) if spec else [],
        "state": stored["state"] if stored else "unknown",
        "reason": stored["reason"] if stored else "not checked yet",
        "as_of": stored["as_of"] if stored else None,
        "basis": stored["basis"] if stored else None,
        "age_days": stored["age_days"] if stored else None,
        "warn_days": spec.warn_days if spec else None,
        "alarm_days": spec.alarm_days if spec else None,
        "frozen": spec.frozen.label if spec and spec.frozen else None,
        "contract": (
            {"layer_name": contract.layer_name, "required_fields": list(contract.required_fields),
             "count_band": list(contract.count_band) if contract.count_band else None,
             "values": [v.field for v in contract.values]}
            if contract else None
        ),
        "ack": {"reason": ack.reason, "until": ack.until.isoformat(), "owner": ack.owner} if ack else None,
        "state_since": stored["state_since"] if stored else None,
        "checked_at": stored["checked_at"] if stored else None,
        "probe_error": bool(stored["probe_error"]) if stored else False,
        "latency_ms": stored["latency_ms"] if stored else None,
        "requests": stored["requests"] if stored else None,
        "note": spec.note if spec else "",
    }


def _sort_key(r: dict[str, Any]) -> tuple:
    return (_RANK.get(r["state"], len(_RANK)), r["severity"] != "critical", r["id"])


def late_payload() -> dict[str, Any]:
    return {
        "checker": {"state": "late", "last_run": None, "age_h": None, "late_after_h": LATE_AFTER_HOURS,
                    "next_run": None, "last_error": None, "runs": []},
        "counts": {}, "sources": [],
    }


def build_panel(path: Path | str, now: datetime | None = None) -> dict[str, Any]:
    """The whole panel: the checker's health, counts by state, and one row per source."""
    now = now or datetime.now(timezone.utc)
    try:
        with open_readonly(path) as con:
            if con is None:
                return {**late_payload(), "checker": {**late_payload()["checker"], "next_run": iso(next_run(now))}}
            stored = {r["source_id"]: r for r in con.execute("SELECT * FROM source_status")}
            finished = last_run_finished(con)
            runs = [dict(r) for r in con.execute(
                "SELECT started_at, finished_at, sources, alarms, requests, error FROM check_runs"
                " ORDER BY id DESC LIMIT ?", (RECENT_RUNS,)
            )]
    except Exception:
        return late_payload()

    specs = {s.id: s for s in SOURCES if not s.retired}
    rows = [_row(spec, stored.get(sid), sid) for sid, spec in specs.items()]
    # Stored rows with no registry entry (a fault drill's synthetic source): shown, never hidden.
    rows += [_row(None, r, sid) for sid, r in stored.items() if sid not in specs]
    rows.sort(key=_sort_key)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    age_h = (now - finished).total_seconds() / 3600 if finished else None
    return {
        "checker": {
            "state": "ok" if age_h is not None and age_h <= LATE_AFTER_HOURS else "late",
            "last_run": iso(finished) if finished else None,
            "age_h": round(age_h, 1) if age_h is not None else None,
            "late_after_h": LATE_AFTER_HOURS,
            "next_run": iso(next_run(now)),
            "last_error": runs[0]["error"] if runs else None,
            "runs": runs,
        },
        "counts": counts,
        "sources": rows,
    }


def build_history(path: Path | str, source_id: str, now: datetime | None = None, days: int = HISTORY_DAYS) -> dict[str, Any]:
    """One source's status strip: a point per run for the last ``days`` days, oldest first."""
    now = now or datetime.now(timezone.utc)
    cutoff = iso(now - timedelta(days=days))
    try:
        with open_readonly(path) as con:
            if con is None:
                return {"source": source_id, "history": []}
            rows = con.execute(
                "SELECT checked_at, state, reason, as_of, age_days FROM source_history"
                " WHERE source_id = ? AND checked_at >= ? ORDER BY checked_at", (source_id, cutoff),
            ).fetchall()
    except Exception:
        return {"source": source_id, "history": []}
    return {"source": source_id, "history": [dict(r) for r in rows]}
