"""Tests for server-side analytics computation."""

import pytest

from backend.analytics import compute_analytics, compute_trends
from backend.models import TrendItem


class TestComputeTrends:
    def test_basic_two_months(self):
        records = [
            {"date": "2026-03-15T00:00:00", "type": "THEFT"},
            {"date": "2026-03-20T00:00:00", "type": "THEFT"},
            {"date": "2026-03-25T00:00:00", "type": "BATTERY"},
            {"date": "2026-04-10T00:00:00", "type": "THEFT"},
            {"date": "2026-04-15T00:00:00", "type": "BATTERY"},
            {"date": "2026-04-20T00:00:00", "type": "BATTERY"},
        ]
        trends, period = compute_trends(
            records,
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
        )
        assert period is not None
        assert len(trends) == 2
        theft = next(t for t in trends if t.category == "THEFT")
        assert theft.current_count == 1
        assert theft.prior_count == 2
        assert theft.change_pct == -50

        battery = next(t for t in trends if t.category == "BATTERY")
        assert battery.current_count == 2
        assert battery.prior_count == 1
        assert battery.change_pct == 100

    def test_empty_records(self):
        trends, period = compute_trends(
            [],
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
        )
        assert trends == []
        assert period is None

    def test_single_month(self):
        records = [
            {"date": "2026-04-10T00:00:00", "type": "THEFT"},
            {"date": "2026-04-15T00:00:00", "type": "THEFT"},
        ]
        trends, period = compute_trends(
            records,
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
        )
        assert trends == []
        assert period is None

    def test_max_categories(self):
        records = []
        for i in range(20):
            records.append({"date": "2026-03-10T00:00:00", "type": f"TYPE_{i}"})
            records.append({"date": "2026-04-10T00:00:00", "type": f"TYPE_{i}"})

        trends, _ = compute_trends(
            records,
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
            max_categories=5,
        )
        assert len(trends) == 5

    def test_new_category_has_undefined_pct(self):
        """Prior-month 0 → the percentage is undefined (None, renders "new"),
        not a fabricated "+100%" (2026-07-06 audit)."""
        records = [
            {"date": "2026-03-10T00:00:00", "type": "OLD"},
            {"date": "2026-04-10T00:00:00", "type": "OLD"},
            {"date": "2026-04-15T00:00:00", "type": "NEW"},
        ]
        trends, _ = compute_trends(
            records,
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
        )
        new = next(t for t in trends if t.category == "NEW")
        assert new.change_pct is None
        assert new.prior_count == 0

    def test_capped_fetch_drops_truncated_oldest_month(self):
        """A row-capped, date-DESC fetch truncates the oldest month mid-month;
        that month must not seed a fake month-over-month increase."""
        records = [
            # March looks tiny only because the cap cut it off.
            {"date": "2026-03-30T00:00:00", "type": "A"},
            {"date": "2026-04-05T00:00:00", "type": "A"},
            {"date": "2026-04-10T00:00:00", "type": "A"},
            {"date": "2026-05-01T00:00:00", "type": "A"},
            {"date": "2026-05-02T00:00:00", "type": "A"},
            {"date": "2026-05-03T00:00:00", "type": "A"},
        ]
        kwargs = dict(get_date=lambda r: r["date"], get_category=lambda r: r["type"])
        capped_trends, capped_period = compute_trends(records, capped=True, **kwargs)
        # March dropped → May vs April (3 vs 2), not April vs truncated March.
        a = next(t for t in capped_trends if t.category == "A")
        assert (a.current_count, a.prior_count) == (3, 2)
        assert "Mar" not in (capped_period or "")
        # And with only two months present, a capped fetch yields no trend at all.
        two_months = [r for r in records if not r["date"].startswith("2026-03")]
        trends, period = compute_trends(two_months, capped=True, **kwargs)
        assert trends == [] and period is None

    def test_sorted_by_current_count(self):
        records = [
            {"date": "2026-03-01T00:00:00", "type": "A"},
            {"date": "2026-04-01T00:00:00", "type": "B"},
            {"date": "2026-04-02T00:00:00", "type": "B"},
            {"date": "2026-04-03T00:00:00", "type": "B"},
            {"date": "2026-04-04T00:00:00", "type": "A"},
        ]
        trends, _ = compute_trends(
            records,
            get_date=lambda r: r["date"],
            get_category=lambda r: r["type"],
        )
        assert trends[0].category == "B"
        assert trends[1].category == "A"


class TestComputeAnalytics:
    def test_with_crime_rows(self):
        crime = [
            {"date": "2026-03-10T00:00:00", "primary_type": "THEFT"},
            {"date": "2026-04-10T00:00:00", "primary_type": "THEFT"},
            {"date": "2026-04-15T00:00:00", "primary_type": "BATTERY"},
        ]
        result = compute_analytics(crime_rows=crime)
        assert result.crime_trends is not None
        assert len(result.crime_trends) > 0
        assert result.trend_period is not None

    def test_with_no_data(self):
        result = compute_analytics()
        assert result.crime_trends is None
        assert result.three11_trends is None
        assert result.permit_trends is None
        assert result.trend_period is None

    def test_with_311_rows(self):
        rows = [
            {"created_date": "2026-03-10T00:00:00", "sr_type": "Pothole"},
            {"created_date": "2026-03-15T00:00:00", "sr_type": "Pothole"},
            {"created_date": "2026-04-10T00:00:00", "sr_type": "Graffiti"},
        ]
        result = compute_analytics(three11_rows=rows)
        assert result.three11_trends is not None

    def test_with_permit_rows(self):
        rows = [
            {"issue_date": "2026-03-10T00:00:00", "permit_type": "RENOVATION"},
            {"issue_date": "2026-04-10T00:00:00", "permit_type": "RENOVATION"},
        ]
        result = compute_analytics(permit_rows=rows)
        assert result.permit_trends is not None

    def test_all_sources(self):
        crime = [
            {"date": "2026-03-10T00:00:00", "primary_type": "THEFT"},
            {"date": "2026-04-10T00:00:00", "primary_type": "THEFT"},
        ]
        three11 = [
            {"created_date": "2026-03-10T00:00:00", "sr_type": "Pothole"},
            {"created_date": "2026-04-10T00:00:00", "sr_type": "Pothole"},
        ]
        permits = [
            {"issue_date": "2026-03-10T00:00:00", "permit_type": "RENOVATION"},
            {"issue_date": "2026-04-10T00:00:00", "permit_type": "RENOVATION"},
        ]
        result = compute_analytics(crime, three11, permits)
        assert result.crime_trends is not None
        assert result.three11_trends is not None
        assert result.permit_trends is not None
