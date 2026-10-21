"""WS0 M1: stale and empty figures stay out of the report, and percentages render as percentages.

The demographics model itself is pinned in test_neighborhood_demographics.py and the
tract's unemployment in test_census_tract.py; these pin the report text and the
percentage scaling on the surfaces that print rates.
"""

import re
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend import report_i18n
from backend.context_manager import summarize_turn
from backend.models import (
    CensusTractDemographics,
    ContextObject,
    CrimeSummary,
    DemographicsSummary,
    NeighborhoodSummary,
    ReportData,
    RetrievalPlan,
)
from backend.retrieval.zoning_definitions import get_zone_name


def _render(report: ReportData) -> str:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    env.filters["fnum"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else "N/A"
    env.filters["fpct"] = lambda v: f"{v * 100:.1f}%" if v is not None else "N/A"
    env.filters["fcur"] = lambda v: f"${v:,.0f}" if v is not None else "N/A"
    env.filters["zone_desc"] = get_zone_name
    env.globals["t"] = report_i18n.make_translator(report.language)
    env.globals["tn"] = report_i18n.make_plural(report.language)
    return env.get_template("zoning_report.html").render(report=report, report_date="October 20, 2026")


def _report_with_area_figures(language: str = "en") -> ReportData:
    # Area figures with percentage-scale rates (4.6 = 4.6%). The old template multiplied
    # these by 100, which would have printed 460%.
    nbr = NeighborhoodSummary(
        demographics=DemographicsSummary(community_area=24, population=87781, median_household_income=82000),
        census_tract=CensusTractDemographics(tract_fips="17031242400", poverty_rate=4.6, unemployment_rate=5.0),
    )
    return ReportData(context=ContextObject(neighborhood=nbr), language=language)


def _pcts(html: str) -> Counter:
    return Counter(float(m) for m in re.findall(r"(\d+(?:\.\d+)?)%", html))


def test_no_rendered_percentage_exceeds_100():
    # Only the percentages the area figures add (static text like the LIHTC "130%"
    # basis boost appears in every report).
    added = _pcts(_render(_report_with_area_figures())) - _pcts(_render(ReportData(context=ContextObject())))
    assert all(p <= 100 for p in added), [p for p in added if p > 100]


def test_report_no_longer_shows_community_area_demographics():
    html = _render(_report_with_area_figures())
    assert "87,781" not in html
    assert "Poverty Rate" not in html


def test_methodology_states_what_is_ai_read():
    for lang in ("en", "es"):
        html = _render(_report_with_area_figures(lang))
        assert "2019–2023" not in html, lang
        assert "Claude Haiku" in html, lang
    en = report_i18n.make_translator("en")
    body = en("data.methodology_body")
    assert "Title 17 tables" in body
    assert "Setbacks" in body and "read from the code text by AI" in body
    assert "Demographics" not in body
    assert "AI-extracted" not in en("data.row_zoning_notes")
    assert "ACS" not in en("data.row_demographics_src")


def test_turn_summary_arrest_rate_is_a_percentage():
    ctx = ContextObject(crime_last_90d=CrimeSummary(total=500, arrest_rate=0.123, by_type={"THEFT": 200}))
    summary = summarize_turn(0, "crime in west town", RetrievalPlan(), ctx)
    assert "12% arrest rate" in summary.key_facts[0]
