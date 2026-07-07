"""Server-side analytics: month-over-month trends from raw Socrata rows.

Ported from frontend/src/lib/analytics.ts. The results are attached to the
ContextObject so Claude can cite trend data in its synthesis.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from backend.models import AnalyticsSummary, TrendItem

_PERMIT_NORMALIZE = [
    ("EXPRESS", "EXPRESS PERMIT"),
    ("RENOVATION", "RENOVATION/ALTERATION"),
    ("ALTERATION", "RENOVATION/ALTERATION"),
    ("SIGN", "SIGNS"),
    ("NEW CONSTRUCTION", "NEW CONSTRUCTION"),
    ("WRECK", "WRECKING/DEMOLITION"),
    ("DEMOLITION", "WRECKING/DEMOLITION"),
    ("ELEVATOR", "ELEVATOR EQUIPMENT"),
    ("REINSTATE", "REINSTATE REVOKED PMT"),
    ("EASY PERMIT", "EASY PERMIT PROCESS"),
]


def _normalize_permit_type(raw: str) -> str:
    upper = (raw or "").upper()
    for keyword, label in _PERMIT_NORMALIZE:
        if keyword in upper:
            return label
    return re.sub(r"^PERMIT\s*[-–—]\s*", "", upper).strip() or "OTHER"


def _to_year_month(date_str: str) -> str | None:
    """Parse an ISO-ish date string and return 'YYYY-MM'."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return f"{dt.year}-{dt.month:02d}"
    except (ValueError, TypeError):
        return None


def _current_year_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"


def _format_month(ym: str) -> str:
    """'2026-04' -> \"Apr '26\""""
    try:
        y, m = ym.split("-")
        dt = datetime(int(y), int(m), 1)
        return dt.strftime("%b '%y")
    except (ValueError, IndexError):
        return ym


def compute_trends(
    records: list[dict[str, Any]],
    get_date: Callable[[dict], str],
    get_category: Callable[[dict], str],
    max_categories: int = 8,
    capped: bool = False,
) -> tuple[list[TrendItem], str | None]:
    """Compute month-over-month trends. Returns (trends, period_label).

    ``capped``: the source query hit its row limit. Rows arrive date-DESC, so
    the cap truncates the OLDEST month mid-month — comparing against it
    fabricates an increase. Dropping that month keeps every remaining month
    complete (in a busy area 2,500 crime rows can span under two months, so
    this is not a theoretical case).
    """
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for r in records:
        ym = _to_year_month(get_date(r))
        if not ym:
            continue
        cat = get_category(r)
        by_month[ym][cat] += 1

    months = sorted(by_month.keys())
    if capped and months:
        del by_month[months[0]]
        months = months[1:]
    if len(months) < 2:
        return [], None

    current_cal = _current_year_month()
    if months[-1] == current_cal and len(months) >= 3:
        current_month = months[-2]
        prior_month = months[-3]
    else:
        current_month = months[-1]
        prior_month = months[-2]

    current_data = by_month[current_month]
    prior_data = by_month[prior_month]
    all_cats = set(current_data.keys()) | set(prior_data.keys())

    items: list[TrendItem] = []
    for cat in all_cats:
        curr = current_data.get(cat, 0)
        prev = prior_data.get(cat, 0)
        # prior 0 → the percentage is undefined, not "+100%". None renders as
        # "new" downstream; the counts themselves carry the magnitude.
        pct = None if prev == 0 else round(((curr - prev) / prev) * 100)
        items.append(TrendItem(
            category=cat,
            current_count=curr,
            prior_count=prev,
            change_pct=pct,
        ))

    items.sort(key=lambda t: t.current_count, reverse=True)
    period = f"{_format_month(current_month)} vs {_format_month(prior_month)}"
    return items[:max_categories], period


def compute_analytics(
    crime_rows: list[dict[str, Any]] | None = None,
    three11_rows: list[dict[str, Any]] | None = None,
    permit_rows: list[dict[str, Any]] | None = None,
    capped: dict[str, bool] | None = None,
) -> AnalyticsSummary:
    """Compute an AnalyticsSummary from raw map data rows.

    ``capped`` mirrors MapDataResponse.capped ("crimes"/"requests_311"/
    "building_permits") so a row-limited fetch doesn't fabricate trends from
    its truncated oldest month.
    """
    capped = capped or {}
    crime_trends = None
    three11_trends = None
    permit_trends = None
    period = None

    if crime_rows:
        crime_trends, period = compute_trends(
            crime_rows,
            get_date=lambda r: r.get("date", ""),
            get_category=lambda r: r.get("primary_type", "UNKNOWN"),
            capped=capped.get("crimes", False),
        )

    if three11_rows:
        three11_trends, p = compute_trends(
            three11_rows,
            get_date=lambda r: r.get("created_date", ""),
            get_category=lambda r: r.get("sr_type", "UNKNOWN"),
            capped=capped.get("requests_311", False),
        )
        period = period or p

    if permit_rows:
        permit_trends, p = compute_trends(
            permit_rows,
            get_date=lambda r: r.get("issue_date", ""),
            get_category=lambda r: _normalize_permit_type(r.get("permit_type", "")),
            capped=capped.get("building_permits", False),
        )
        period = period or p

    return AnalyticsSummary(
        crime_trends=crime_trends or None,
        three11_trends=three11_trends or None,
        permit_trends=permit_trends or None,
        trend_period=period,
    )
