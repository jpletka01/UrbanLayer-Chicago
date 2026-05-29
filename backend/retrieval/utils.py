"""Shared helpers for the retrieval modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def cutoff_iso(days_ago: int, *, lag_days: int = 0) -> str:
    """Return a Socrata floating-timestamp cutoff `days_ago` (+ optional lag) in the past."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_ago + lag_days)
    return cutoff.strftime("%Y-%m-%dT00:00:00.000")
