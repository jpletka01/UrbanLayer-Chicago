"""Server-side analytics: month-over-month trends from raw Socrata rows.

Ported from frontend/src/lib/analytics.ts. The results are attached to the
ContextObject so Claude can cite trend data in its synthesis.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from backend.models import AnalyticsSummary, TrendItem


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
) -> tuple[list[TrendItem], str | None]:
    """Compute month-over-month trends. Returns (trends, period_label)."""
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for r in records:
        ym = _to_year_month(get_date(r))
        if not ym:
            continue
        cat = get_category(r)
        by_month[ym][cat] += 1

    months = sorted(by_month.keys())
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
        if prev == 0:
            pct = 100 if curr > 0 else 0
        else:
            pct = round(((curr - prev) / prev) * 100)
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
) -> AnalyticsSummary:
    """Compute an AnalyticsSummary from raw map data rows."""
    crime_trends = None
    three11_trends = None
    permit_trends = None
    period = None

    if crime_rows:
        crime_trends, period = compute_trends(
            crime_rows,
            get_date=lambda r: r.get("date", ""),
            get_category=lambda r: r.get("primary_type", "UNKNOWN"),
        )

    if three11_rows:
        three11_trends, p = compute_trends(
            three11_rows,
            get_date=lambda r: r.get("created_date", ""),
            get_category=lambda r: r.get("sr_type", "UNKNOWN"),
        )
        period = period or p

    if permit_rows:
        permit_trends, p = compute_trends(
            permit_rows,
            get_date=lambda r: r.get("issue_date", ""),
            get_category=lambda r: r.get("permit_type", "UNKNOWN"),
        )
        period = period or p

    return AnalyticsSummary(
        crime_trends=crime_trends or None,
        three11_trends=three11_trends or None,
        permit_trends=permit_trends or None,
        trend_period=period,
    )
