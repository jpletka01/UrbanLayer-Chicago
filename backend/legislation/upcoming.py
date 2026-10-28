"""Read-only parcel summaries from the daily pending-zoning snapshot.

The serving path opens SQLite in read-only mode and performs no network calls.
Exact subject matches are ordered before nearby filings; nearby placement is the
minimum Address Points distance for each matter within the fixed half-mile radius.
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.legislation import address_titles, currency
from backend.legislation.pending_store import read_status
from backend.models import UpcomingZoningFiling, UpcomingZoningProvenance, UpcomingZoningSummary


RADIUS_MI = 0.5
STALE_AFTER = timedelta(days=3)
UNAVAILABLE_AFTER = timedelta(days=14)


def _miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_mi = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return earth_mi * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _segment(row: sqlite3.Row | None) -> str | None:
    if row is None:
        return None
    return " ".join(
        str(value).strip()
        for value in (row["raw"], row["direction"], row["street_name"], row["street_type"])
        if value
    )


def _range_matches(row: sqlite3.Row, address: str | None) -> bool:
    parts = currency.address_parts(address)
    if parts is None:
        return False
    number, direction, name = parts
    if row["direction"] != direction or name not in address_titles.name_candidates(row["street_name"]):
        return False
    if not row["lo"] <= number <= row["hi"]:
        return False
    if row["side"] == "odd" and number % 2 == 0:
        return False
    if row["side"] == "even" and number % 2 == 1:
        return False
    return not currency.suffix_conflicts(row["street_type"], address)


def _empty(status: str, checked_at: str | None = None) -> UpcomingZoningSummary:
    confidence = "standard" if status == "ready" else "low"
    return UpcomingZoningSummary(
        status=status,
        placement_status="partial",
        checked_at=checked_at,
        record_provenance=UpcomingZoningProvenance(
            source_id="chi.clerk.legislation", as_of=checked_at,
            method="Current non-final zoning matters recorded by the City Clerk", confidence=confidence,
        ),
        placement_provenance=UpcomingZoningProvenance(
            source_id="cook.address_points", as_of=checked_at,
            method="Not available for deterministic parcel placement", confidence="low",
        ),
    )


def summary_for(
    path: Path | str,
    *,
    lat: float,
    lon: float,
    pin: str | None,
    address: str | None,
    authoritative_pin: bool,
    now: datetime | None = None,
) -> UpcomingZoningSummary:
    """Return the Profile's upcoming-zoning contract from last-good local data."""
    now = now or datetime.now(timezone.utc)
    try:
        status = read_status(path)
    except Exception:
        # A corrupt/half-copied local artifact is unavailable evidence. It must
        # not turn the otherwise independent Property Profile into a 500.
        return _empty("unavailable")
    if status is None or status.checked_at is None:
        return _empty("unavailable")
    checked_at = status.checked_at.astimezone(timezone.utc)
    age = now - checked_at
    if age > UNAVAILABLE_AFTER:
        return _empty("unavailable", checked_at.isoformat(timespec="seconds"))
    freshness = "stale" if status.latest_status != "ok" or age > STALE_AFTER else "ready"

    p = Path(path)
    try:
        with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2)) as con:
            con.row_factory = sqlite3.Row
            if int(con.execute("PRAGMA user_version").fetchone()[0]) < 2:
                return _empty("unavailable", checked_at.isoformat(timespec="seconds"))
            matters = con.execute(
                """SELECT * FROM matters
                   WHERE category LIKE 'ZONING RECLASSIFICATIONS%'
                   ORDER BY COALESCE(introduced_at, created_at) DESC, record_number DESC"""
            ).fetchall()
            actions = {
                row["matter_id"]: row["latest_action_at"]
                for row in con.execute(
                    "SELECT matter_id, MAX(action_at) AS latest_action_at FROM actions GROUP BY matter_id"
                )
            }
            segments: dict[str, list[sqlite3.Row]] = {}
            for row in con.execute("SELECT * FROM segments ORDER BY matter_id, position"):
                segments.setdefault(row["matter_id"], []).append(row)
            located_ids = {
                row["matter_id"] for row in con.execute("SELECT DISTINCT matter_id FROM locations")
            }
            locations: dict[str, list[sqlite3.Row]] = {}
            lat_delta = RADIUS_MI / 69.0
            lon_delta = RADIUS_MI / max(1.0, 69.0 * math.cos(math.radians(lat)))
            nearby_rows = con.execute(
                """SELECT * FROM locations
                   WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
                   ORDER BY matter_id, segment_position, pin""",
                (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta),
            ).fetchall()
            pin_rows = con.execute(
                "SELECT * FROM locations WHERE pin=? ORDER BY matter_id, segment_position",
                (pin,),
            ).fetchall() if authoritative_pin and pin else []
            for row in [*nearby_rows, *pin_rows]:
                locations.setdefault(row["matter_id"], []).append(row)
    except (OSError, sqlite3.Error):
        return _empty("unavailable", checked_at.isoformat(timespec="seconds"))

    matter_by_id = {row["matter_id"]: row for row in matters}
    exact: dict[str, tuple[str, sqlite3.Row | None]] = {}
    for matter in matters:
        mid = matter["matter_id"]
        if authoritative_pin and pin:
            hit = next((loc for loc in locations.get(mid, []) if loc["pin"] == pin), None)
            if hit is not None:
                seg = next((s for s in segments.get(mid, []) if s["position"] == hit["segment_position"]), None)
                exact[mid] = ("subject_pin", seg)
                continue
        hit = next((seg for seg in segments.get(mid, []) if _range_matches(seg, address)), None)
        if hit is not None:
            exact[mid] = ("subject_range", hit)

    nearby: dict[str, tuple[float, sqlite3.Row | None]] = {}
    for mid, rows in locations.items():
        if mid in exact:
            continue
        best: tuple[float, sqlite3.Row] | None = None
        for loc in rows:
            if loc["lat"] is None or loc["lon"] is None:
                continue
            distance = _miles(lat, lon, float(loc["lat"]), float(loc["lon"]))
            if distance <= RADIUS_MI and (best is None or distance < best[0]):
                best = (distance, loc)
        if best is not None:
            seg = next((s for s in segments.get(mid, []) if s["position"] == best[1]["segment_position"]), None)
            nearby[mid] = (best[0], seg)

    def filing(mid: str, kind: str, segment: sqlite3.Row | None, distance: float | None = None):
        row = matter_by_id[mid]
        return UpcomingZoningFiling(
            record_number=row["record_number"], title=row["title"], status=row["status"],
            sub_status=row["sub_status"], introduced_at=row["introduced_at"],
            latest_action_at=actions.get(mid), url=row["source_url"],
            application_number=row["application_number"], segment=_segment(segment),
            match_kind=kind, distance_mi=round(distance, 3) if distance is not None else None,
        )

    subject_rows = [filing(mid, kind, segment) for mid, (kind, segment) in exact.items()]
    subject_rows.sort(key=lambda row: (row.introduced_at or "", row.record_number), reverse=True)
    nearby_rows = [filing(mid, "nearby", segment, distance) for mid, (distance, segment) in nearby.items()]
    nearby_rows.sort(key=lambda row: (row.distance_mi or 0, -(datetime.fromisoformat(row.introduced_at).timestamp() if row.introduced_at else 0), row.record_number))

    unplaced = sum(
        1 for matter in matters
        if matter["title_parse_status"] != "clean" or matter["matter_id"] not in located_ids
    )
    placement_status = "partial" if unplaced else "complete"
    placed_count = len(matters) - unplaced
    placement_coverage = placed_count / len(matters) if matters else 1.0
    checked = checked_at.isoformat(timespec="seconds")
    confidence = "standard" if freshness == "ready" else "low"
    return UpcomingZoningSummary(
        status=freshness,
        placement_status=placement_status,
        checked_at=checked,
        subject_filings=subject_rows,
        nearby_filings=nearby_rows,
        placed_count=placed_count,
        unplaced_count=unplaced,
        placement_coverage=placement_coverage,
        record_provenance=UpcomingZoningProvenance(
            source_id="chi.clerk.legislation", as_of=checked,
            method="Current non-final zoning matters recorded by the City Clerk", confidence=confidence,
        ),
        placement_provenance=UpcomingZoningProvenance(
            source_id="cook.address_points", as_of=checked,
            method="Title address ranges resolved to parcels with Cook County Address Points; nearby distance calculated from stored coordinates",
            confidence="low" if freshness == "stale" or placement_status == "partial" else "standard",
        ),
    )
