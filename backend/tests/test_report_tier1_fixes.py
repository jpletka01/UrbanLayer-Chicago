"""Regression tests for Report V6 Tier-1 fixes.

Covers:
  * Comps consolidation — the legacy "Comparable Sales Summary" stat block (with
    its empty `Median $/Land Sq Ft` tile) is gone; the report consolidates on the
    "Comparable Market Activity" presentation; the $/building-sf metric is
    preserved (median in the callout + per-row in the table).
  * Q6 tax clarity — market value is persisted and rendered next to assessed
    value + effective tax rate; the effective rate renders exactly once as a
    labeled value (collapsing the old 3× / D4); an assessment-history fallback
    fills estimated annual tax when the ptaxsim bill is missing.

See claude-context/guides/report-v6-execution-plan.md ("Tier 1").
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.config import get_settings
from backend.models import (
    AssessmentRecord,
    ComparablesSummary,
    ComparableSale,
    ContextObject,
    PropertySummary,
    ReportData,
)
from backend.report_builder import _compute_comp_valuation, _resolve_market_value_and_tax
from backend.retrieval.zoning_definitions import get_zone_name


def _render(report: ReportData) -> str:
    """Render the real PDF template to HTML (GIS-independent, like Phase 3)."""
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    env.filters["fnum"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else "N/A"
    env.filters["fpct"] = lambda v: f"{v * 100:.1f}%" if v is not None else "N/A"
    env.filters["fcur"] = lambda v: f"${v:,.0f}" if v is not None else "N/A"
    env.filters["zone_desc"] = get_zone_name
    from backend import report_i18n
    env.globals["t"] = report_i18n.make_translator(report.language)
    env.globals["tn"] = report_i18n.make_plural(report.language)
    template = env.get_template("zoning_report.html")
    return template.render(report=report, report_date="June 11, 2026")


def _comps(**over) -> ComparablesSummary:
    defaults = dict(
        median_sale_price=425000.0,
        median_price_per_land_sqft=None,  # condo market: no land area
        median_price_per_bldg_sqft=195.0,
        price_range_min=275000.0,
        price_range_max=680000.0,
        sales_volume=4,
        comp_basis="residential sales within 0.25 mi, last 3 yrs",
        sales=[
            ComparableSale(
                pin="14-30-316-001", sale_date="2025-11-14", sale_price=520000,
                land_sqft=None, bldg_sqft=2400, price_per_land_sqft=None,
                price_per_bldg_sqft=216.7, distance_mi=0.08,
            ),
            ComparableSale(
                pin="14-30-314-022", sale_date="2025-08-22", sale_price=450000,
                land_sqft=None, bldg_sqft=1850, price_per_land_sqft=None,
                price_per_bldg_sqft=243.2, distance_mi=0.12,
            ),
            ComparableSale(
                pin="14-30-318-015", sale_date="2025-06-03", sale_price=425000,
                land_sqft=None, bldg_sqft=2200, price_per_land_sqft=None,
                price_per_bldg_sqft=193.2, distance_mi=0.15,
            ),
        ],
    )
    defaults.update(over)
    return ComparablesSummary(**defaults)


def _report(prop: PropertySummary | None = None, comps: ComparablesSummary | None = None,
            **rkw) -> ReportData:
    ctx = ContextObject(property=prop)
    return ReportData(context=ctx, comparables=comps, **rkw)


# --------------------------------------------------------------------------- #
# Comps consolidation
# --------------------------------------------------------------------------- #

def test_comp_valuation_includes_bldg_sf_metric():
    """$/bldg-sf is preserved on the consolidated valuation read."""
    r = _report(comps=_comps())
    cv = _compute_comp_valuation(r)
    assert cv is not None
    assert cv["median_price_per_bldg_sqft"] == 195.0


def test_legacy_comps_summary_block_removed():
    """The legacy stat block and its empty $/land-sf tile no longer render."""
    r = _report(prop=PropertySummary(pin14="1"), comps=_comps())
    r.comp_valuation = _compute_comp_valuation(r)
    html = _render(r)
    assert "Comparable Sales Summary" not in html
    assert "Median $/Land Sq Ft" not in html
    # Consolidated presentation + preserved $/bldg-sf metric are present.
    assert "Comparable Sales (" in html  # neutral section heading w/ count
    assert "Median price per building sq ft" in html


def test_comps_table_uses_bldg_sf_column():
    """The per-row comps table reports $/Bldg SF, not the empty $/Land SF."""
    r = _report(prop=PropertySummary(pin14="1"), comps=_comps())
    r.comp_valuation = _compute_comp_valuation(r)
    html = _render(r)
    assert "$/Bldg SF" in html
    assert "$/Land SF" not in html
    assert "$217" in html  # 216.7 rounded, per-row $/bldg-sf


# --------------------------------------------------------------------------- #
# Q6 tax clarity
# --------------------------------------------------------------------------- #

def test_market_value_persisted_for_taxable_parcel():
    prop = PropertySummary(pin14="1", total_assessed_value=114600,
                           estimated_annual_tax=23024)
    rate, mv, _level = _resolve_market_value_and_tax(prop)
    assert mv == 1146000               # assessed / 0.10
    assert rate == round(23024 / 1146000, 4)
    assert prop.tax_estimate_is_fallback is False


def test_exempt_parcel_no_market_value():
    prop = PropertySummary(pin14="1", tax_exempt=True, total_assessed_value=0)
    rate, mv, _level = _resolve_market_value_and_tax(prop)
    assert rate is None and mv is None


def test_annual_tax_fallback_from_assessment_history():
    """ptaxsim miss: estimate annual tax from assessed value, flag it, no rate."""
    prop = PropertySummary(
        pin14="1",
        estimated_annual_tax=None,
        total_assessed_value=None,
        assessment_history=[AssessmentRecord(year=2024, total=90000)],
    )
    rate, mv, _level = _resolve_market_value_and_tax(prop)
    assert mv == 900000                              # 90000 / 0.10
    assert prop.total_assessed_value == 90000        # backfilled for display
    expected = round(900000 * get_settings().report_fallback_tax_rate)
    assert prop.estimated_annual_tax == expected
    assert prop.tax_estimate_is_fallback is True
    # Effective rate intentionally left None (would circularly echo the assumption)
    assert rate is None


def test_effective_rate_renders_once_as_labeled_value():
    """D4: the effective rate appears exactly once as a value row (the
    traffic-light risk pill is a separate conditional signal, not a value)."""
    prop = PropertySummary(pin14="1", total_assessed_value=114600,
                           estimated_annual_tax=23024)
    rate, mv, _level = _resolve_market_value_and_tax(prop)
    r = _report(prop=prop, effective_tax_rate=rate, market_value=mv)
    html = _render(r)
    # One labeled "Effective Tax Rate" value row.
    assert html.count("Effective Tax Rate") == 1
    # The old standalone financial-section "Effective Rate" dt is gone.
    assert "<dt>Effective Rate</dt>" not in html
    # Market value + assessed value rendered together, rate clarified.
    assert "Est. Market Value" in html
    assert "Assessed Value" in html
    assert "(of market value)" in html


def test_fallback_tax_label_rendered():
    prop = PropertySummary(
        pin14="1",
        estimated_annual_tax=None,
        assessment_history=[AssessmentRecord(year=2024, total=90000)],
    )
    rate, mv, _level = _resolve_market_value_and_tax(prop)
    r = _report(prop=prop, effective_tax_rate=rate, market_value=mv)
    html = _render(r)
    assert "estimated from assessed value" in html
