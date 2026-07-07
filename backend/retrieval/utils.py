"""Shared helpers for the retrieval modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Ground-distance scale of ONE DEGREE OF LATITUDE. Longitude degrees shrink by
# cos(latitude) (~0.74 at Chicago) — always apply cos(lat) for east-west
# distances. Derive, don't redeclare: modules previously carried independent
# copies (69.0 mi vs 364,567.2 ft) that could drift (2026-07-06 audit).
# parcel_geometry.py keeps its metric constants (documented equirectangular
# projection) — everything imperial routes through these.
FT_PER_DEG_LAT = 364_567.2
MI_PER_DEG_LAT = FT_PER_DEG_LAT / 5_280  # ≈ 69.05


def cutoff_iso(days_ago: int, *, lag_days: int = 0) -> str:
    """Return a Socrata floating-timestamp cutoff `days_ago` (+ optional lag) in the past."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_ago + lag_days)
    return cutoff.strftime("%Y-%m-%dT00:00:00.000")


def format_pin(raw: str) -> str:
    """Format a 14-digit PIN as XX-XX-XXX-XXX-XXXX."""
    p = raw.replace("-", "").zfill(14)
    return f"{p[:2]}-{p[2:4]}-{p[4:7]}-{p[7:10]}-{p[10:14]}"
