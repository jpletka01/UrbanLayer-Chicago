"""WS6 M6: the data dates behind an answer, a report and a Profile.

One builder (``data_health/vintages.py``) over the provenance map; the chat footer, the report cover and the
Profile payload all show its list. A date we don't have is never invented, and no vintage is typed into the
catalogs: a lint pins that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend import report_i18n
from backend.chat_sources import build_sources_footer
from backend.data_health.vintages import DatedSource, as_dicts, phrase, phrases, vintages_for
from backend.legislation.currency import fmt_day
from backend.main import render_report_html
from backend.models import ContextObject, ReportData, ZoningSummary
from backend.report_builder import _apply_mock_overrides

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "backend" / "tests" / "fixtures" / "profile_provenance_1601_milwaukee.json"
T, TN = report_i18n.make_translator("en"), report_i18n.make_plural("en")
FRESH = {"current_through": "2026-06-17", "check_state": "fresh", "since": {"title17": 10}, "checked_at": "2026-10-22T10:00:00Z"}


def profile() -> dict[str, dict]:
    d = json.loads(FIXTURE.read_text())
    return d.get("provenance", d)


def entry(**kw) -> dict:
    base = {"label": "x", "query_date": "2026-10-22", "as_of_basis": "queried", "confidence": "standard", "confidence_reasons": []}
    return {**base, **kw}


def keys(items) -> list[str]:
    return [d.key for d in items]


# --- the builder -----------------------------------------------------------------------------------------

def test_a_parcel_profile_gets_its_headline_dates_in_reading_order():
    items = vintages_for(profile(), code_currency=FRESH)
    assert keys(items) == ["zoning_map", "code_text", "assessor", "tax_year", "sales", "acs_tract", "crime", "violations"]
    by = {d.key: d for d in items}
    assert (by["zoning_map"].kind, by["zoning_map"].as_of) == ("record", "2021-12-15")  # this district's map record
    assert (by["assessor"].kind, by["assessor"].period) == ("period", "2026")
    assert (by["acs_tract"].period, by["acs_tract"].source_id) == ("2020–2024", "census.reporter.acs")
    assert by["sales"].kind == "through" and by["crime"].as_of == "2026-10-14"


def test_the_words_read_the_same_everywhere():
    got = phrases(vintages_for(profile(), code_currency=FRESH), T, TN, fmt_day)
    assert got[:3] == [
        "Zoning map record edited Dec 15, 2021",
        "Code text current through Jun 17, 2026 (+10 later zoning amendments)",
        "Assessor values 2026",
    ]
    assert "ACS (tract) 2020–2024" in got and "Crime through Oct 14, 2026" in got


def test_a_source_with_no_date_says_when_we_asked_never_a_made_up_date():
    prov = {"area.311": entry(source_id="chi.311"), "area.crime": entry(source_id="chi.crime", as_of="2026-10-14", as_of_basis="period_end")}
    got = {d.key: d for d in vintages_for(prov)}
    assert (got["c311"].kind, got["c311"].as_of) == ("checked", "2026-10-22")
    assert phrase(got["c311"], T, TN, fmt_day) == "Open 311 requests checked Oct 22, 2026"
    assert phrase(got["crime"], T, TN, fmt_day) == "Crime through Oct 14, 2026"


def test_a_period_without_a_year_falls_back_to_checked():
    got = vintages_for({"property.assessed_value": entry(source_id="cook.assessor.values")})
    assert got[0].kind == "checked"


def test_the_code_date_appears_only_when_the_answer_rests_on_the_code():
    crime_only = {"code.vintage": entry(as_of="2026-06-17", as_of_basis="current_through"), "area.crime": entry(as_of="2026-10-14", as_of_basis="period_end")}
    assert keys(vintages_for(crime_only)) == ["crime"]
    with_zoning = {**crime_only, "zoning.far": entry(as_of="2026-06-17", as_of_basis="current_through")}
    assert "code_text" in keys(vintages_for(with_zoning))


def test_amendments_since_follow_the_check_state():
    base = {"zoning.far": entry(), "code.vintage": entry(as_of="2026-06-17", as_of_basis="current_through")}

    def line(cc):
        return phrases(vintages_for(base, code_currency=cc), T, TN, fmt_day)[0]

    assert line({**FRESH, "since": {"title17": 1}}).endswith("(+1 later zoning amendment)")
    assert line({**FRESH, "check_state": "aging", "since": {"title17": 3}, "checked_at": "2026-10-15T10:00:00Z"}).endswith("(+3 later zoning amendments as of Oct 15, 2026)")
    # past 14 days, or never checked: never a count
    unknown = line({"current_through": "2026-06-17", "check_state": "unknown", "since": None, "checked_at": None})
    assert unknown.endswith("(couldn't check recently for later amendments)") and "+" not in unknown
    assert line(None) == "Code text current through Jun 17, 2026"  # no currency block at all: the date alone


def test_the_wire_form_drops_empty_fields():
    d = as_dicts([DatedSource("crime", "through", "chi.crime", "2026-10-14")])[0]
    assert d == {"key": "crime", "kind": "through", "source_id": "chi.crime", "as_of": "2026-10-14"}


# --- the chat footer -------------------------------------------------------------------------------------------

def test_a_parcel_answer_ends_with_its_data_dates():
    footer = build_sources_footer(profile(), [], "2026-06-17", FRESH)
    line = next(x for x in footer.splitlines() if x.startswith("- **Data dates:**"))
    assert "Zoning map record edited Dec 15, 2021" in line and "Assessor values 2026" in line
    assert "Sales through Aug 12, 2026" in line and "ACS (tract) 2020–2024" in line
    # the standards rest on the code, so the code's date and amendments are in the currency line, once
    assert "Code text current" not in line
    assert "**Code text current through Jun 17, 2026** · 10 later zoning amendments" in footer


def test_a_crime_answer_shows_how_far_the_data_runs():
    prov = {"area.crime": entry(source_id="chi.crime", as_of="2026-10-14", as_of_basis="period_end", period="last 90 days", geography="Logan Square", scope="community_area")}
    footer = build_sources_footer(prov, [], None)
    assert "- **Data dates:** Crime through Oct 14, 2026" in footer
    assert "Logan Square; last 90 days" in footer  # the span the count covers, in the source line


def test_the_code_date_is_not_said_twice_when_cited_code_already_carries_it():
    class Chunk:
        section, section_title = "17-3-0400", "Bulk"

    footer = build_sources_footer(profile(), [(1, Chunk())], "2026-06-17", FRESH)
    dates = next(x for x in footer.splitlines() if x.startswith("- **Data dates:**"))
    assert "Code text current" not in dates
    assert "Code text current through Jun 17, 2026" in footer  # the currency line says it, with the amendments


# --- the report cover ---------------------------------------------------------------------------------------------

def _mock_report() -> ReportData:
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="B3-2", map_updated="2021-12-15T00:00:00.000"))
    return _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", context=ctx, resolved_pin="14313320180000", resolved_confidence="authoritative"))


def test_the_cover_says_when_it_was_generated_and_lists_each_vintage():
    page = render_report_html(_mock_report(), "en", report_date="October 22, 2026")
    cover = page[: page.index("TABLE OF CONTENTS")]
    assert "Generated on: October 22, 2026" in cover and "Report Date" not in cover
    box = re.search(r'data-testid="data-dates">(.*?)</div>\s*(?:<div class="dates-missing"|</div>)', cover, re.S)
    assert box, "the cover has a Data as of box"
    items = re.findall(r"<li>(.*?)</li>", cover[cover.index('data-testid="data-dates"'):], re.S)
    assert "Zoning map record edited December 15, 2021" in items
    assert any(i.startswith("Code text current through ") for i in items)


def test_the_cover_names_what_was_not_checked():
    r = _mock_report()
    r.partial_failures = ["property tax estimate", "comparable sales"]
    page = render_report_html(r, "en", report_date="October 22, 2026")
    cover = page[: page.index("TABLE OF CONTENTS")]
    assert "Not checked in this report: property tax estimate, comparable sales" in cover


def test_the_cover_is_localized_without_a_translator_for_the_dates_yet():
    page = render_report_html(_mock_report(), "es", report_date="22 de octubre de 2026")
    assert "Zoning map record edited 15 de diciembre de 2021" in page  # English words, the reader's date format


# --- no vintage is typed into the wording ---------------------------------------------------------------------------

_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*[–-]\s*(?:19|20)\d{2}\b")
# A year range that is not a data vintage: none today. Add one here, with the reason, rather than loosening the lint.
_ALLOWED: set[tuple[str, str]] = set()


def test_no_data_vintage_is_typed_into_the_catalogs_the_template_or_the_footer():
    files = [REPO / "backend" / "report_i18n.py", REPO / "backend" / "templates" / "zoning_report.html",
             REPO / "backend" / "chat_sources.py", REPO / "backend" / "prompts.py",
             *sorted((REPO / "frontend" / "src" / "locales").glob("*/*.json"))]
    found = [(f.name, m.group(0)) for f in files for m in _RANGE.finditer(f.read_text()) if (f.name, m.group(0)) not in _ALLOWED]
    assert not found, f"a year range typed into the wording (take it from the data): {found}"


# --- the backend and the Profile word the dates the same way ---------------------------------------------------------

def test_the_frontend_wording_matches_the_backend_catalog():
    fe = json.loads((REPO / "frontend" / "src" / "locales" / "en" / "common.json").read_text())["dataDates"]
    be = report_i18n.MESSAGES["en"]
    for key, text in fe["noun"].items():
        assert be[f"dates.noun.{key}"] == text, key
    for kind in ("record", "through", "period", "checked"):
        assert be[f"dates.{kind}"] == fe[kind].replace("{{", "{").replace("}}", "}"), kind
    assert be["dates.since__one"] == fe["since_one"].replace("{{count}}", "{n}")
    assert be["dates.since__other"] == fe["since_other"].replace("{{count}}", "{n}")
    assert be["dates.since_aging__other"] == fe["sinceAging_other"].replace("{{count}}", "{n}").replace("{{d}}", "{d}")
    assert be["dates.since_unknown"] == fe["sinceUnknown"]
    # every noun a DatedSource can carry has wording
    from backend.data_health import vintages

    used = {k for k, _ in vintages._AREA_FEEDS} | {"zoning_map", "code_text", "assessor", "tax_year", "sales", "acs_tract", "acs_community_area"}
    assert used == set(fe["noun"])
