"""Regression tests for appeals + exemptions in the $25 report (task #16 follow-up
to the 2026-07-03 lot-info robustness arc).

The Scorecard gained per-PIN tax exemptions (EAV-deduction semantics + the
"doesn't transfer to a buyer" caveat) and appeal history (both stages + the
nearby-BOR aggregate). These tests lock in the report template carrying both:

  * Appeal history table in the Property section (derived stage/outcome labels,
    never raw dataset words) + the nearby-outcomes money sentence.
  * "No appeals on record" note when only nearby stats exist (neighbors win,
    subject never appealed — the strongest tax-upside story).
  * Exemptions rendered with their EAV amounts, plus the buyer-bill caveat in
    the Financial section (the ptaxsim bill is post-exemption, so the headline
    number understates a buyer's bill).
  * No appeals markup at all when the summary is absent (no-appeals is a
    legitimate state, not a data gap).
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.models import (
    AppealRecord,
    AppealsSummary,
    ContextObject,
    PropertySummary,
    ReportData,
    TaxExemption,
)
from backend.retrieval.zoning_definitions import get_zone_name


def _render(report: ReportData) -> str:
    """Render the real PDF template to HTML (GIS-independent)."""
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
    return template.render(report=report, report_date="July 2, 2026")


def _appeals(**over) -> AppealsSummary:
    defaults = dict(
        records=[
            AppealRecord(year=2024, stage="board_of_review", before_total=39900,
                         after_total=33200, result="Decrease", reduction_pct=16.8,
                         appeal_type="Over Valuation"),
            AppealRecord(year=2023, stage="assessor", before_total=37500,
                         after_total=37500, result="no change"),
            AppealRecord(year=2022, stage="board_of_review", before_total=30000,
                         after_total=31500, result="Increase"),
        ],
        nearby_window_years=[2022, 2023, 2024],
        nearby_appeal_count=107,
        nearby_reduced_count=38,
        nearby_median_reduction_pct=16.9,
    )
    defaults.update(over)
    return AppealsSummary(**defaults)


def _report(prop: PropertySummary, **rkw) -> ReportData:
    return ReportData(context=ContextObject(property=prop), **rkw)


# --------------------------------------------------------------------------- #
# Appeal history
# --------------------------------------------------------------------------- #

def test_appeal_table_renders_records_with_derived_labels():
    html = _render(_report(PropertySummary(pin14="1", appeals=_appeals())))
    assert "Assessment Appeal History" in html
    # Stage labels derived from the stage enum, not raw dataset words
    assert "Board of Review" in html
    assert "Assessor" in html
    # Win row: green reduction percentage with before/after dollars
    assert "−16.8%" in html
    assert "status-good" in html
    assert "$39,900" in html and "$33,200" in html
    # No-change and increase rows use derived outcome labels
    assert "No change" in html
    assert "Increased" in html
    # Raw dataset result words never leak into the report
    assert "no change</td>" not in html  # lowercase dataset word
    assert ">Decrease<" not in html and ">Increase<" not in html


def test_nearby_aggregate_sentence_renders():
    html = _render(_report(PropertySummary(pin14="1", appeals=_appeals())))
    assert "Nearby appeal outcomes:" in html
    assert "107 Board of Review appeals within one block" in html
    assert "38 won reductions" in html
    assert "(median −16.9%)" in html
    assert "2022–2024" in html


def test_no_own_appeals_note_when_only_nearby_stats():
    appeals = _appeals(records=[])
    html = _render(_report(PropertySummary(pin14="1", appeals=appeals)))
    assert "No assessment appeals on record for this parcel." in html
    assert "107 Board of Review appeals" in html


def test_no_appeals_markup_when_summary_absent():
    html = _render(_report(PropertySummary(pin14="1", appeals=None)))
    assert "Assessment Appeal History" not in html
    assert "Nearby appeal outcomes" not in html


def test_nearby_years_fallback_when_window_empty():
    appeals = _appeals(nearby_window_years=[])
    html = _render(_report(PropertySummary(pin14="1", appeals=appeals)))
    assert "in recent years" in html


def test_single_year_window_collapses():
    appeals = _appeals(nearby_window_years=[2025])
    html = _render(_report(PropertySummary(pin14="1", appeals=appeals)))
    assert "in 2025 —" in html
    assert "2025–2025" not in html


def test_capped_nearby_count_renders_as_floor():
    """Dense areas saturate NEARBY_ROW_CAP — the count must read as '500+'."""
    appeals = _appeals(nearby_appeal_count=500, nearby_capped=True)
    html = _render(_report(PropertySummary(pin14="1", appeals=appeals)))
    assert "500+ Board of Review appeals" in html


# --------------------------------------------------------------------------- #
# Exemptions
# --------------------------------------------------------------------------- #

def _exempt_prop() -> PropertySummary:
    return PropertySummary(
        pin14="1",
        tax_exemptions=[
            TaxExemption(kind="Homeowner", eav_reduction=10000),
            TaxExemption(kind="Senior Citizen", eav_reduction=8000),
        ],
        estimated_annual_tax=8152.11,
    )


def test_exemptions_row_shows_eav_amounts_and_caveat():
    html = _render(_report(_exempt_prop()))
    assert "Tax Exemptions Applied" in html
    assert "Homeowner (−10,000 EAV)" in html
    assert "Senior Citizen (−8,000 EAV)" in html
    assert "owner-occupancy exemptions do not transfer to a buyer" in html


def test_financial_buyer_note_renders_with_totaled_eav():
    html = _render(_report(_exempt_prop()))
    assert "Owner-occupancy exemptions do not transfer at sale" in html
    assert "−18,000 EAV" in html
    assert "Homeowner, Senior Citizen" in html


def test_financial_buyer_note_absent_without_exemptions():
    prop = PropertySummary(pin14="1", estimated_annual_tax=8152.11)
    html = _render(_report(prop))
    assert "do not transfer at sale" not in html


# --------------------------------------------------------------------------- #
# Spanish parity smoke
# --------------------------------------------------------------------------- #

def test_spanish_render_no_key_leakage():
    prop = _exempt_prop()
    prop.appeals = _appeals()
    html = _render(_report(prop, language="es"))
    assert "Historial de Apelaciones de Avalúo" in html
    assert "Junta de Revisión" in html
    assert "107 apelaciones ante la Junta de Revisión a una cuadra" in html
    assert "no se transfieren en la venta" in html
    # Untranslated key names must never render
    assert "prop.appeal" not in html
    assert "fin.exemptions_buyer_note" not in html
