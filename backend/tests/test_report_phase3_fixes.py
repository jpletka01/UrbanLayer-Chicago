"""Regression tests for Phase 3 report decision-quality features.

Covers the decision box (Miss#1), land-value/comp valuation (V5-1b/P2),
FAR utilization (P1), as-of-right unit yield (P8), the deal-shaping
constraint surfaced on page 1 (Exec), and the ownership "so what" (P5).
See claude-context/guides/report-v6-execution-plan.md (Phase 3).
"""

from backend.models import (
    ComparablesSummary,
    ComparableSale,
    ContextObject,
    DevelopmentPotential,
    PropertySummary,
    ReportData,
    ZoningStandards,
    ZoningSummary,
)
from backend.retrieval.zoning_definitions import min_lot_area_per_unit
from backend.main import (
    _build_decision_box,
    _compute_comp_valuation,
    _compute_far_utilization,
    _compute_land_value_range,
    _compute_unit_yield,
    _ownership_interpretation,
)


def _report(**ctx_kwargs) -> ReportData:
    ctx = ContextObject(**ctx_kwargs)
    return ReportData(context=ctx)


# --- P8: minimum lot area per unit (Title 17-2-0303-A) ----------------------

def test_mla_per_unit_known_districts():
    assert min_lot_area_per_unit("RM-5") == 400
    assert min_lot_area_per_unit("RM-6") == 300
    assert min_lot_area_per_unit("RT-4") == 1000
    assert min_lot_area_per_unit("RS-3") == 2500
    # spacing / case variants normalise
    assert min_lot_area_per_unit("rm-5") == 400
    assert min_lot_area_per_unit("RM 6") == 300


def test_mla_per_unit_non_r_districts_none():
    for z in ("B3-2", "C1-1", "M1-2", "DX-5", "PD 100", "", None):
        assert min_lot_area_per_unit(z) is None


def test_unit_yield_rm5_lot():
    r = _report(
        property=PropertySummary(pin="1", land_sqft=3350),
        parcel_zoning=ZoningSummary(zone_class="RM-5"),
    )
    uy = _compute_unit_yield(r)
    assert uy is not None
    assert uy["units"] == 8  # 3350 // 400
    assert uy["mla_per_unit"] == 400
    assert uy["zone_class"] == "RM-5"


def test_unit_yield_non_r_district_none():
    r = _report(
        property=PropertySummary(pin="1", land_sqft=5000),
        parcel_zoning=ZoningSummary(zone_class="B3-2"),
    )
    assert _compute_unit_yield(r) is None


def test_unit_yield_no_lot_size_none():
    r = _report(
        property=PropertySummary(pin="1"),
        parcel_zoning=ZoningSummary(zone_class="RM-5"),
    )
    assert _compute_unit_yield(r) is None


# --- P1: FAR utilization ----------------------------------------------------

def test_far_utilization_partial():
    r = _report(property=PropertySummary(pin="1", land_sqft=3350, bldg_sqft=1950))
    r.zoning_standards = ZoningStandards(far=2.0)
    fu = _compute_far_utilization(r)
    assert fu["allowed_sqft"] == 6700
    assert fu["existing_sqft"] == 1950
    assert fu["utilization_pct"] == 29  # 1950/6700
    assert fu["unused_sqft"] == 4750
    assert fu["vacant"] is False


def test_far_utilization_vacant_lot():
    r = _report(property=PropertySummary(pin="1", land_sqft=5000, bldg_sqft=0))
    r.zoning_standards = ZoningStandards(far=4.4)
    fu = _compute_far_utilization(r)
    assert fu["vacant"] is True
    assert fu["utilization_pct"] == 0


def test_far_utilization_missing_data_none():
    r = _report(property=PropertySummary(pin="1", land_sqft=5000))
    r.zoning_standards = None
    assert _compute_far_utilization(r) is None


# --- V5-1b / P2: land value range + comp valuation --------------------------

def _comps_with_land(n_with_land: int, land_sqft: int = 2500) -> ComparablesSummary:
    sales = []
    for i in range(5):
        ls = land_sqft if i < n_with_land else None
        price = 500_000 + i * 50_000
        sales.append(ComparableSale(
            pin=str(i), sale_price=price, land_sqft=ls,
            price_per_land_sqft=round(price / ls, 2) if ls else None,
        ))
    return ComparablesSummary(
        median_sale_price=600_000, price_range_min=500_000, price_range_max=700_000,
        sales_volume=5, comp_basis="Class 2xx sales within 0.25 mi, last 3 yr (n=5)",
        sales=sales,
    )


def test_land_value_range_requires_three_land_comps():
    # Only 2 comps carry land area → no defensible range.
    r = _report(property=PropertySummary(pin="1", land_sqft=3000))
    r.comparables = _comps_with_land(2)
    assert _compute_land_value_range(r) is None


def test_land_value_range_renders_with_enough_land_comps():
    r = _report(property=PropertySummary(pin="1", land_sqft=3000))
    r.comparables = _comps_with_land(4)
    lv = _compute_land_value_range(r)
    assert lv is not None
    assert lv["sample_size"] == 4  # land-bearing subset, not total volume
    assert lv["low"] > 0 and lv["high"] >= lv["low"]


def test_comp_valuation_data_limited_when_no_land():
    """Condo-dominated market: median sale price renders, land value flagged limited."""
    r = _report(property=PropertySummary(pin="1", land_sqft=3000))
    r.comparables = _comps_with_land(0)
    r.estimated_land_value = _compute_land_value_range(r)  # None
    cv = _compute_comp_valuation(r)
    assert cv is not None
    assert cv["median_sale_price"] == 600_000
    assert cv["data_limited"] is True
    assert "land_value_low" not in cv


def test_comp_valuation_full_with_per_buildable():
    r = _report(property=PropertySummary(pin="1", land_sqft=3000))
    r.comparables = _comps_with_land(4)
    r.development_potential = DevelopmentPotential(max_buildable_sqft=6000)
    r.estimated_land_value = _compute_land_value_range(r)
    cv = _compute_comp_valuation(r)
    assert cv["data_limited"] is False
    assert cv["land_value_low"] > 0
    # per-buildable = land value / max buildable
    assert cv["per_buildable_low"] == round(cv["land_value_low"] / 6000, 2)


# --- Miss#1: cover decision box ---------------------------------------------

def test_decision_box_full():
    r = _report(
        property=PropertySummary(pin="1", land_sqft=3350, bldg_sqft=1950),
        parcel_zoning=ZoningSummary(zone_class="RM-5"),
    )
    r.development_potential = DevelopmentPotential(max_buildable_sqft=6700)
    r.comparables = _comps_with_land(0)
    r.comp_valuation = _compute_comp_valuation(r)
    r.constraints = [
        {"signal": "Thin comparable sales market", "detail": "x", "category": "market"},
        {"signal": "Landmark district — design review required", "detail": "x", "category": "regulatory"},
    ]
    r.approval_pathway = {"complexity": "MODERATE", "timeline": "3-6 months", "detail": "x", "modifiers": []}
    db = _build_decision_box(r)
    assert db["lot"] == "3,350 sq ft"
    assert db["zone"] == "RM-5"
    assert db["buildable"] == "6,700 sq ft"
    # n>=3 nearby sales → labeled as observed market activity, NOT a valuation
    assert db["value_label"] == "Nearby Sales (median)"
    assert "n=5" in db["value"]
    # deal-shaping constraint (regulatory) beats the market caveat
    assert "Landmark" in db["key_constraint"]
    assert db["timeline"].startswith("Moderate")


def test_decision_box_thin_comps_no_median_label():
    # n<3 → range + sale count, never the word "median".
    r = _report(property=PropertySummary(pin="1", land_sqft=3000))
    r.comparables = _comps_with_land(0)
    r.comparables.sales_volume = 2
    r.comp_valuation = _compute_comp_valuation(r)
    db = _build_decision_box(r)
    assert db["value_label"] == "Nearby Sales"
    assert "median" not in db["value"].lower()
    assert "2 sale" in db["value"]


def test_decision_box_exempt_shows_status_not_value():
    # Tax-exempt/institutional parcel must not be given a comp-derived value.
    r = _report(property=PropertySummary(pin="1", bldg_class="EX", tax_exempt=True))
    r.comparables = _comps_with_land(0)
    r.comp_valuation = _compute_comp_valuation(r)
    db = _build_decision_box(r)
    assert db["value_label"] == "Tax Status"
    assert "Exempt" in db["value"]
    assert "$" not in db["value"]


def test_decision_box_honest_na():
    r = _report()  # no property, zoning, dev, comps
    db = _build_decision_box(r)
    assert db["lot"] == "n/a"
    assert db["zone"] == "n/a"
    assert db["buildable"] == "n/a"
    assert db["value"] == "n/a"
    # absence reads as "rule set found nothing", not a guarantee
    assert db["key_constraint"] == "No major constraints flagged"
    assert db["timeline"] == "n/a"


# --- P5: ownership "so what" -------------------------------------------------

def test_ownership_interpretation_long_hold():
    r = _report()
    r.ownership_signals = [
        {"signal": "Long-Term Hold", "detail": "12 years", "category": "ownership_duration"},
    ]
    txt = _ownership_interpretation(r)
    assert txt and "off-market" in txt


def test_ownership_interpretation_duration_renders():
    r = _report()
    r.ownership_signals = [
        {"signal": "Ownership Duration", "detail": "3 years", "category": "ownership_duration"},
    ]
    txt = _ownership_interpretation(r)
    assert txt and "off-market" in txt


def test_ownership_interpretation_empty_none():
    r = _report()
    r.ownership_signals = []
    assert _ownership_interpretation(r) is None


# --- Exec/credibility: ARO only binds when 10+ units are feasible -----------

def _aro_constraints(land_sqft: int, zone: str, max_buildable: int):
    from backend.main import _synthesize_opportunities_constraints
    from backend.models import RegulatorySummary
    r = _report(
        property=PropertySummary(pin="1", land_sqft=land_sqft, bldg_sqft=0),
        parcel_zoning=ZoningSummary(zone_class=zone),
        regulatory=RegulatorySummary(in_aro_zone=True),
    )
    r.development_potential = DevelopmentPotential(max_buildable_sqft=max_buildable)
    _opps, cons = _synthesize_opportunities_constraints(r)
    return [c for c in cons if "ARO" in c["signal"]]


def test_aro_skipped_for_small_lot():
    # RM-5, 962 sf → ~2 units → ARO must NOT be flagged.
    assert _aro_constraints(962, "RM-5", 1924) == []


def test_aro_flagged_for_large_lot():
    # RM-5, 5,000 sf → 12 units → ARO is a real constraint.
    assert len(_aro_constraints(5000, "RM-5", 10000)) == 1
