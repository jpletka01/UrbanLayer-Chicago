"""Regression tests for the 2026-07-06 calculation-audit money-path fixes.

Covers: comparable sale_type three-state (unknown building ≠ vacant land),
price-less comps dropped from the disclosed n, assessment stage preference
(board > certified > mailed — appeals must not be ignored), the same-year
effective-tax-rate pairing (bill ÷ the bill year's OWN assessed value),
the class-scaled fallback tax estimate, and the class-relative high-tax
constraint threshold.
"""

from unittest.mock import patch

import pytest

from backend.main import (
    _resolve_market_value_and_tax,
    _synthesize_opportunities_constraints,
)
from backend.models import ContextObject, PropertySummary, ReportData
from backend.retrieval.property import _build_summary
from backend.retrieval.property.sales import nearby_comparable_sales


# --- comparable sales: sale_type + price-less comps --------------------------

@pytest.mark.asyncio
async def test_comp_sale_type_three_state_and_priceless_dropped():
    parcels = [
        {"pin": "1111111111", "class": "100", "lat": "41.901", "lon": "-87.701"},
        {"pin": "2222222222", "class": "211", "lat": "41.899", "lon": "-87.699"},
        {"pin": "3333333333", "class": "590", "lat": "41.900", "lon": "-87.700"},
        {"pin": "4444444444", "class": "211", "lat": "41.902", "lon": "-87.702"},
    ]
    sales = [
        # Vacant-land sale: chars say building = 0.
        {"pin": "1111111111", "sale_date": "2025-01-15", "sale_price": "200000", "class": "100"},
        # Improved sale: chars carry a building.
        {"pin": "2222222222", "sale_date": "2024-06-01", "sale_price": "300000", "class": "211"},
        # No characteristics row at all → improvement status UNKNOWN, not LAND.
        {"pin": "3333333333", "sale_date": "2024-03-01", "sale_price": "400000", "class": "590"},
        # Price-less row → contributes nothing; must not inflate sales_volume.
        {"pin": "4444444444", "sale_date": "2024-02-01", "class": "211"},
    ]
    chars = [
        {"pin": "1111111111", "char_land_sf": "3000", "char_bldg_sf": "0"},
        {"pin": "2222222222", "char_land_sf": "2500", "char_bldg_sf": "1200"},
    ]

    call_count = [0]

    async def mock_socrata(*args, **kwargs):
        call_count[0] += 1
        return [parcels, sales, chars][call_count[0] - 1]

    with patch("backend.retrieval.property.sales.socrata_get", side_effect=mock_socrata):
        result = await nearby_comparable_sales(41.9, -87.7, "2")

    by_pin = {c["pin"]: c for c in result["sales"]}
    assert by_pin["1111111111"]["sale_type"] == "LAND"
    assert by_pin["2222222222"]["sale_type"] == "LAND AND BUILDING"
    assert by_pin["3333333333"]["sale_type"] is None  # unknown, NOT "LAND"
    assert "4444444444" not in by_pin
    assert result["summary"]["sales_volume"] == 3  # priced comps only


# --- assessment stage preference ---------------------------------------------

def test_build_summary_prefers_board_over_mailed():
    """A won appeal (board < mailed) must drive AV → implied market value."""
    parcel = {"pin14": "1", "bldg_class": "211"}
    assessments = [{
        "year": "2024",
        "mailed_tot": "100000", "mailed_land": "20000", "mailed_bldg": "80000",
        "certified_tot": "90000",
        "board_tot": "80000", "board_land": "20000", "board_bldg": "60000",
    }]
    s = _build_summary(parcel, None, assessments, [])
    assert s.total_assessed_value == 80000
    assert s.assessment_history[0].building == 60000
    assert s.implied_market_value == round(80000 / 0.10)


def test_build_summary_mailed_only_year_still_works():
    """The in-progress year carries only mailed values — they must still count."""
    parcel = {"pin14": "1", "bldg_class": "211"}
    assessments = [{"year": "2026", "mailed_tot": "120000"}]
    s = _build_summary(parcel, None, assessments, [])
    assert s.total_assessed_value == 120000


# --- same-year effective rate --------------------------------------------------

def test_build_summary_effective_rate_pairs_bill_with_its_own_year_av():
    """Rate = bill ÷ (bill-year av_clerk ÷ level), NOT ÷ the newest post-
    reassessment market value; market value still reflects the newest AV."""
    parcel = {"pin14": "1", "bldg_class": "211"}
    assessments = [{"year": "2025", "mailed_tot": "200000"}]  # post-reassessment
    tax_result = {
        "year": 2024,
        "tax_code": "73001",
        "tax_bill_total": 21000.0,
        "assessed_value": 100000,  # av_clerk for the 2024 bill
        "line_items": [],
        "exemptions": [],
    }
    s = _build_summary(parcel, None, assessments, [], tax_result)
    assert s.implied_market_value == round(200000 / 0.10)  # newest AV
    assert s.effective_tax_rate == round(21000.0 / (100000 / 0.10), 4)  # 0.021
    assert s.effective_tax_rate != round(21000.0 / s.implied_market_value, 4)


def test_build_summary_rate_falls_back_to_latest_av_without_av_clerk():
    parcel = {"pin14": "1", "bldg_class": "211"}
    assessments = [{"year": "2024", "mailed_tot": "100000"}]
    tax_result = {
        "year": 2024, "tax_code": "73001", "tax_bill_total": 21000.0,
        "line_items": [], "exemptions": [],
    }
    s = _build_summary(parcel, None, assessments, [], tax_result)
    assert s.effective_tax_rate == round(21000.0 / (100000 / 0.10), 4)


# --- report-side resolve: rate reuse + class-scaled fallback -------------------

def test_resolve_prefers_summary_same_year_rate():
    prop = PropertySummary(
        pin14="1", bldg_class="211", assessment_level=0.10,
        total_assessed_value=200000, estimated_annual_tax=21000,
        effective_tax_rate=0.021,  # same-year pairing from _build_summary
    )
    rate, mv, level = _resolve_market_value_and_tax(prop)
    assert mv == 2_000_000
    assert rate == 0.021  # not 21000/2000000 = 0.0105


def test_fallback_tax_scales_with_assessment_level():
    """No PTAXSIM bill: class-5 (level 0.25) pays ~2.5× the residential
    fallback rate — the flat multiply understated commercial bills 2.5×."""
    commercial = PropertySummary(
        pin14="1", bldg_class="517", assessment_level=0.25,
        total_assessed_value=250000,
    )
    rate, mv, level = _resolve_market_value_and_tax(commercial)
    assert rate is None and mv == 1_000_000 and level == 0.25
    assert commercial.estimated_annual_tax == round(1_000_000 * 0.021 * 2.5)
    assert commercial.tax_estimate_is_fallback is True

    residential = PropertySummary(
        pin14="2", bldg_class="211", assessment_level=0.10,
        total_assessed_value=100000,
    )
    _resolve_market_value_and_tax(residential)
    assert residential.estimated_annual_tax == round(1_000_000 * 0.021)


# --- class-relative high-tax constraint ----------------------------------------

def _report_with_rate(rate: float, level: float) -> ReportData:
    r = ReportData(context=ContextObject())
    r.effective_tax_rate = rate
    r.assessment_level = level
    return r


def _has_high_tax_constraint(report: ReportData) -> bool:
    _, constraints = _synthesize_opportunities_constraints(report)
    return any(c["category"] == "financial" and "%" in c["signal"] for c in constraints)


def test_high_tax_constraint_is_class_relative():
    # ~5% is NORMAL for class-5 commercial (level 0.25) — no constraint.
    assert not _has_high_tax_constraint(_report_with_rate(0.0515, 0.25))
    # ~5% on a residential parcel (level 0.10) IS high — constraint fires.
    assert _has_high_tax_constraint(_report_with_rate(0.05, 0.10))
    # Genuinely high commercial (>2.5 × 3.5% = 8.75%) still fires.
    assert _has_high_tax_constraint(_report_with_rate(0.10, 0.25))


# --- comps radius honesty (Phase 4) --------------------------------------------

@pytest.mark.asyncio
async def test_comps_outside_disclosed_radius_are_filtered():
    """comp_basis discloses 'within X mi' — a bbox-corner comp beyond that
    distance must not ride along."""
    # Base radius 0.004° ≈ 0.28 mi. Put one parcel ~0.1 mi north (kept) and
    # one at the bbox corner ~0.39 mi out (filtered).
    parcels = [
        {"pin": "1111111111", "class": "211", "lat": "41.9014", "lon": "-87.7"},
        {"pin": "2222222222", "class": "211", "lat": "41.9040", "lon": "-87.70538"},
    ]
    sales = [
        {"pin": "1111111111", "sale_date": "2025-01-15", "sale_price": "300000", "class": "211"},
        {"pin": "2222222222", "sale_date": "2024-06-01", "sale_price": "250000", "class": "211"},
    ]

    call_count = [0]

    async def mock_socrata(*args, **kwargs):
        call_count[0] += 1
        return [parcels, sales, []][call_count[0] - 1]

    with patch("backend.retrieval.property.sales.socrata_get", side_effect=mock_socrata):
        result = await nearby_comparable_sales(41.9, -87.7, "2")

    pins = {c["pin"] for c in result["sales"]}
    assert "1111111111" in pins
    assert "2222222222" not in pins


# --- crime YoY leap-day safety (Phase 4) ----------------------------------------

def test_year_earlier_handles_leap_day():
    from datetime import datetime, timezone

    from backend.retrieval.crime import _year_earlier

    leap = datetime(2028, 2, 29, tzinfo=timezone.utc)
    assert _year_earlier(leap) == datetime(2027, 2, 28, tzinfo=timezone.utc)
    normal = datetime(2026, 7, 6, tzinfo=timezone.utc)
    assert _year_earlier(normal) == datetime(2025, 7, 6, tzinfo=timezone.utc)


# --- ownership signals: homeowner exemption (Phase 5) ---------------------------

def test_homeowner_signal_reads_tax_exemptions():
    """The signal must come from tax_exemptions (PTAXSIM exe_* kinds) — the old
    check scanned tax_breakdown AGENCY names for 'HOMEOWNER', which are taxing
    districts, so it could never fire."""
    from backend.main import _derive_ownership_signals
    from backend.models import TaxExemption

    with_exe = PropertySummary(
        pin14="1",
        tax_exemptions=[TaxExemption(kind="Homeowner", eav_reduction=10000)],
    )
    names = {s["signal"] for s in _derive_ownership_signals(with_exe)}
    assert "Owner-Occupied (Homeowner Exemption)" in names

    without = PropertySummary(pin14="2")
    names = {s["signal"] for s in _derive_ownership_signals(without)}
    assert "Owner-Occupied (Homeowner Exemption)" not in names


# --- tax incentive class interpretation (Phase 5) -------------------------------

def test_interpret_tax_class_matches_numeric_ccao_codes():
    """CCAO's numeric incentive codes (6xx-9xx) must classify as incentives —
    they previously fell through to 'standard classification'."""
    from backend.assembler import _interpret_tax_class

    cls, desc = _interpret_tax_class("663")
    assert cls == "6" and "Reduced assessment" in desc
    cls, desc = _interpret_tax_class("913")
    assert cls == "9" and "affordab" in desc.lower()
    # Letter forms still work; standard classes still pass through.
    assert _interpret_tax_class("6b")[0] == "6B"
    assert _interpret_tax_class("9")[0] == "9"
    assert _interpret_tax_class("L")[0] == "L"
    assert _interpret_tax_class("211") == (None, None)
    assert _interpret_tax_class("517") == (None, None)
