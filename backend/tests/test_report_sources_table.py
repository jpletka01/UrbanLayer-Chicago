"""WS0 M5: per-figure confidence in the $25 report, and a Data Sources table built from what the report used.

The report's own provenance is the Profile's plus the AI-read setbacks/uses/parking/notes and the envelope built
on them. Everything renders through the same quiet-by-default rule as the Profile. No static source row survives.
"""

import json
import re
from pathlib import Path

import pytest

from backend import report_i18n, report_provenance as rp
from backend.data_health.registry import BY_ID
from backend.main import render_report_html
from backend.models import ContextObject, ReportData, ZoningStandards, ZoningSummary
from backend.report_builder import _apply_mock_overrides

REPO = Path(__file__).resolve().parents[2]
T = report_i18n.make_translator("en")
BASELINE = REPO / "eval" / "kit" / "baseline" / "2026-10-01"


def mock_report(**over) -> ReportData:
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    r = _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", context=ctx, resolved_pin="14313320180000",
                                         resolved_confidence="authoritative"))
    for k, v in over.items():
        setattr(r, k, v)
    return r


def html(report: ReportData, lang: str = "en") -> str:
    return render_report_html(report, lang, report_date="October 22, 2026")


def rows_of(page: str) -> list[str]:
    return re.findall(r'<tr data-source="([^"]+)">', page)


# --- the provenance map -------------------------------------------------------------------------------

def test_ai_read_fields_get_ai_entries_with_the_code_section_and_are_not_verified():
    r = mock_report()
    prov = rp.entries_for_report(r, {"sections": ["17-3-0400"], "code_vintage": "2026-06-17"}, "2026-10-22")
    for fact in ("zoning.setbacks", "zoning.permitted_uses", "zoning.special_uses", "zoning.parking", "zoning.notes"):
        e = prov[fact]
        assert e["tier"] == "ai_extracted" and e["method_key"] == "ai_read_code" and e["section"] == "17-3-0400"
        assert e["confidence"] == "low" and "ai_unverified" in e["confidence_reasons"]
        assert e["as_of"] == "2026-06-17" and e["as_of_basis"] == "current_through"


def test_the_envelope_is_our_calculation_built_on_the_ai_read_setbacks():
    r = mock_report(buildable_footprint_sqft=3210.0)
    env = rp.entries_for_report(r, {"sections": ["17-3-0400"], "code_vintage": "2026-06-17"})["zoning.envelope"]
    assert env["tier"] == "our_calculation" and env["basis_tier"] == "ai_extracted"
    assert env["inputs"] == ["zoning.setbacks", "property.land_sqft"]


def test_table_derived_standards_claim_no_ai_reading():
    """When the standards came from the Title 17 table (no cache), nothing is called AI-read."""
    r = mock_report()
    r.zoning_standards = ZoningStandards(far=2.2, max_height_ft=50, extraction_confidence="definitions")
    prov = rp.entries_for_report(r, None)
    assert not any(k in prov for k in ("zoning.setbacks", "zoning.permitted_uses", "zoning.envelope"))
    low = mock_report()
    low.zoning_standards = ZoningStandards(extraction_confidence="low")
    assert "zoning.setbacks" not in rp.entries_for_report(low, {"sections": [], "code_vintage": None})


# --- captions -------------------------------------------------------------------------------------------

def test_the_ai_caption_names_the_section_and_says_not_verified():
    prov = rp.entries_for_report(mock_report(buildable_footprint_sqft=3000.0), {"sections": ["17-3-0400"], "code_vintage": "2026-06-17"})
    c = rp.caption(prov["zoning.setbacks"], T)
    assert c["ai"] is True and c["lead"] is None and c["text"].startswith("Read by AI from §17-3-0400")
    assert c["text"].endswith("not verified")
    env = rp.caption(prov["zoning.envelope"], T)
    assert "built on AI-read setbacks" in env["text"] and env["ai"] is False


def test_a_standard_official_record_prints_no_caption_and_a_low_or_withheld_figure_does():
    quiet = {"tier": "official_record", "confidence": "standard", "confidence_reasons": [], "method_key": "recorded"}
    assert rp.caption(quiet, T) is None and rp.caption(None, T) is None
    stale = {**quiet, "confidence_reasons": ["old_source"], "as_of": "2015-08-15", "as_of_basis": "source_updated", "age_days": 4085}
    assert rp.caption(stale, T)["text"] == "2015"
    withheld = {"tier": "our_calculation", "confidence": "withheld", "confidence_reasons": ["small_sample"],
                "coverage": {"n": 2, "unit": "sales", "sample": "comps"}}
    c = rp.caption(withheld, T)
    assert c["withheld"] and c["text"] == "Not shown: only 2 sales (needs 3)."
    one = {**withheld, "coverage": {"n": 1, "unit": "sales", "sample": "comps"}}
    assert rp.caption(one, T)["text"] == "Not shown: only 1 sale (needs 3)."
    low = {"tier": "our_calculation", "confidence": "low", "confidence_reasons": ["small_sample"], "method_key": "calculation",
           "scope": "radius", "coverage": {"n": 4, "unit": "sales", "sample": "comps"},
           "method_params": {"radius_mi": 0.28, "window_years": 3}}
    assert rp.caption(low, T) == {"ai": False, "lead": "Low confidence", "text": "4 sales · 0.28 mi · 3 yr", "withheld": False}


# --- the sources table ----------------------------------------------------------------------------------------

def test_the_sources_table_lists_exactly_the_sources_the_report_used():
    r = mock_report(buildable_footprint_sqft=3000.0)
    page = html(r)
    used = {e["source_id"] for e in r.provenance.values() if e.get("source_id")}
    assert set(rows_of(page)) == used and len(used) >= 5
    assert "artifact.zoning_cache" in used and "chi.zoning.districts" in used


def test_no_static_source_row_survives():
    """The old table named eight categories whether or not the report used them (and gave wrong years)."""
    page = html(mock_report())
    for stale in ("Census Reporter", "Chicago Data Portal — Crime", "ARO housing", "Cook County Assessor, Cook County GIS"):
        assert stale not in page, stale
    for key in [k for k in report_i18n.MESSAGES["en"] if k.startswith("data.row_")]:
        pytest.fail(f"static row key still in the catalog: {key}")


def test_a_source_the_report_did_not_use_is_not_listed():
    r = mock_report()
    r.context.parcel_zoning = ZoningSummary(zone_class="B3-2")
    page = html(r)
    assert "private.walkscore" not in rows_of(page)             # no Walk Score in this report
    assert "chi.tif.boundaries" not in rows_of(page)


def test_each_row_has_publisher_authority_date_and_what_it_supplied():
    rows = rp.sources_rows(mock_report(buildable_footprint_sqft=3000.0).provenance or rp.entries_for_report(mock_report(), {"sections": [], "code_vintage": "2026-06-17"}), T)
    by = {r["source_id"]: r for r in rows}
    z = by["artifact.zoning_cache"]
    assert z["authority"] == "Read by AI" and z["publisher"] == "UrbanLayer" and "Required setbacks" in z["used"]
    d = by["chi.zoning.districts"]
    assert d["authority"] == "Official record" and d["name"] == BY_ID["chi.zoning.districts"].name
    tiers = [r["tier"] for r in rows]
    order = ["official_record", "official_publication", "official_estimate", "our_calculation", "ai_extracted", "non_government", "internal"]
    assert tiers == sorted(tiers, key=order.index), "rows run strongest authority first"


def test_the_ai_note_appears_only_when_an_ai_source_is_listed():
    assert "Figures marked AI were read from the Municipal Code" in html(mock_report())
    plain = mock_report()
    plain.zoning_standards = ZoningStandards(far=2.2, extraction_confidence="definitions")
    assert "Figures marked AI" not in html(plain)


# --- the rendered page ------------------------------------------------------------------------------------------

def test_the_page_labels_every_ai_read_field_and_the_envelope():
    page = html(mock_report(buildable_footprint_sqft=3000.0, envelope_summary="x", envelope_map_b64="aGk="))
    for fact in ("zoning.setbacks", "zoning.permitted_uses", "zoning.special_uses", "zoning.parking", "zoning.notes"):
        assert f'data-conf="{fact}"' in page, fact
    assert page.count('class="conf-ai"') >= 5
    assert "Read by AI from §17-3-0400" in page                          # the district's bulk section, from the cache entry
    assert 'data-conf="zoning.envelope"' in page and "Drawn from the AI-read setbacks above" in page


def test_a_standard_record_has_no_caption_on_the_page():
    page = html(mock_report())
    assert 'data-conf="zoning.far"' not in page and 'data-conf="property.assessed_value"' not in page


def test_withheld_comps_figures_are_not_printed_but_the_reason_is():
    r = mock_report()
    prov = rp.entries_for_report(r, {"sections": [], "code_vintage": None})
    prov["property.comps.median_price_per_bldg_sqft"] = {**prov.get("property.comps.median_price_per_bldg_sqft", {"tier": "our_calculation", "label": "x"}),
                                                         "confidence": "withheld", "confidence_reasons": ["small_sample"],
                                                         "coverage": {"n": 2, "unit": "sales", "sample": "comps"}}
    assert rp.state(prov["property.comps.median_price_per_bldg_sqft"]) == "withheld"
    r.provenance = prov
    # the template reads state from the same map render builds, so assert through the helper it uses
    h = rp.helpers(prov, T, "en")
    assert h["conf_state"]("property.comps.median_price_per_bldg_sqft") == "withheld"
    assert h["conf_caption"]("property.comps.median_price_per_bldg_sqft")["text"].startswith("Not shown")


def test_spanish_report_renders_the_same_structure_with_english_text_until_translated():
    es = html(mock_report(buildable_footprint_sqft=3000.0), "es")
    assert 'data-testid="sources-table"' in es and 'class="conf-ai"' in es
    assert "Read by AI from §17-3-0400" in es                            # English until WS7 (listed in _UNTRANSLATED_ES)


def test_a_failure_building_the_map_never_blocks_the_report(monkeypatch):
    monkeypatch.setattr(rp, "entries_for_report", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    page = html(mock_report())
    assert "Development Feasibility Report" in page and 'data-conf="zoning.setbacks"' not in page


def test_conf_keys_exist_in_both_catalogs_and_the_untranslated_list():
    en = {k for k in report_i18n.MESSAGES["en"] if k.startswith("conf.")}
    assert en and en == {k for k in report_i18n.MESSAGES["es"] if k.startswith("conf.")}
    assert en <= report_i18n._UNTRANSLATED_ES


def test_the_recorded_production_profile_provenance_gives_a_clean_sources_table():
    """The live Profile provenance for 1601 N Milwaukee (56 entries, 2026-10-21) is a valid input: every row resolves
    to a registry name, publisher and authority, strongest first, and the quiet rule prints few captions."""
    prov = json.loads((Path(__file__).parent / "fixtures" / "profile_provenance_1601_milwaukee.json").read_text())["provenance"]
    rows = rp.sources_rows(prov, T)
    assert len(rows) >= 20 and all(r["name"] and r["publisher"] and r["authority"] for r in rows)
    by = {r["source_id"]: r for r in rows}
    assert by["census.reporter.acs"]["as_of"] == "2020–2024" or by["census.reporter.acs"]["as_of"]
    assert by["private.walkscore"]["authority"] == "Private company"
    captioned = [k for k, e in prov.items() if rp.caption(e, T)]
    assert 5 <= len(captioned) < len(prov)                               # quiet by default: official records print nothing


def test_a_survey_or_tax_year_is_shown_as_its_period_not_a_december_31_date():
    prov = json.loads((Path(__file__).parent / "fixtures" / "profile_provenance_1601_milwaukee.json").read_text())["provenance"]
    by = {r["source_id"]: r for r in rp.sources_rows(prov, T)}
    assert by["census.reporter.acs"]["as_of"] == "2020–2024"
    assert by["cook.ptaxsim"]["as_of"] == "2024"
    assert rp._period_text("2003–2003") == "2003" and rp._period_text("2004–2024") == "2004–2024"
    # a record with a plain date is that date; one with no date from the publisher says it was queried
    assert by["chi.zoning.districts"]["as_of"] == "December 15, 2021"
    assert by["private.walkscore"]["as_of"] == "queried October 21, 2026"
