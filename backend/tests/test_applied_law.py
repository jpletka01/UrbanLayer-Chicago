"""WS1 M4b: law passed after the code text's vintage, applied to a parcel ahead of codification.

The rules are transcribed from the passed ordinances (fixtures/ordinances, read from scans in
session) and pinned here. Until the code text carries a change, each test pins the code to the
transcription and checks the code text still shows the OLD rows; once a refresh codifies it,
the same test pins the code to the code text instead (so a refresh can't silently desync them).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.legislation import applied, currency
from backend.models import ContextObject, OverlayDistrict, RegulatorySummary, ZoningSummary
from backend.retrieval import tod_streets

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ROOT / "ingestion" / "data" / "sections"
ORD = json.loads((Path(__file__).parent / "fixtures" / "ordinances" / "passed_2026-07_to_10.json").read_text())
REVIEWS = json.loads((ROOT / "backend" / "code_amendments.json").read_text())["amendments"]


def _section(section_id: str) -> dict | None:
    path = SECTIONS / f"{section_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _rows(table: int) -> list[list[str]]:
    s = _section("17-3-0500")
    if s is None:
        pytest.skip("ordinance corpus not present")
    return s["tables"][table]["data_rows"]


def _ctx(address: str, overlays=()) -> ContextObject:
    return ContextObject(
        resolved_address=address, parcel_zoning=ZoningSummary(zone_class="B3-2"),
        regulatory=RegulatorySummary(overlays=list(overlays)),
    )


def _ids(ctx: ContextObject) -> list[str]:
    return [n["id"] for n in ctx.coverage_notes]


# --- TOD streets ------------------------------------------------------------------------------

def test_tod_segments_match_the_transcribed_table():
    t = ORD["SO2026-0025391"]
    got = [(s.street.title(), s.from_cross.split()[0], s.to_cross.split()[0], f"{s.frm}{s.direction}", f"{s.to}{s.direction}")
           for s in tod_streets.SEGMENTS]
    want = [(s["street"], s["from"].split()[0], s["to"].split()[0], s["coord_from"], s["coord_to"]) for s in t["segments"]]
    assert sorted(got) == sorted(want)
    assert list(tod_streets.PROHIBITED_USES) == t["prohibited_uses"]


def test_tod_review_map_effects_agree_with_the_segment_table():
    effects = REVIEWS["SO2026-0025391"]["map_effects"]
    assert sorted(e["suffix"] for e in effects) == sorted(s.suffix for s in tod_streets.SEGMENTS)
    assert sorted((e["street"], e["from"], e["to"]) for e in effects) == sorted(
        (s.street, s.frm, s.to) for s in tod_streets.SEGMENTS
    )


def test_tod_matches_the_code_text_once_codified():
    section = _section("17-3-0600") or _section("17-3-0603")
    if section is None:
        assert REVIEWS["SO2026-0025391"]["codified"] is False  # not in our text, and the review says so
        return
    text = " ".join(section["body_paragraphs"]) + json.dumps(section.get("tables"))
    for seg in tod_streets.SEGMENTS:
        assert f"{seg.frm}N" in text and f"{seg.to}N" in text, seg
    for use in tod_streets.PROHIBITED_USES:
        assert use.split(" involving")[0].split(" with any")[0] in text.lower()
    assert REVIEWS["SO2026-0025391"]["codified"] is True


@pytest.mark.parametrize("address,on", [
    ("4000 N Western Ave", True), ("3600 N Western Ave", True), ("4858 N Western Ave", True), ("4859 N Western Ave", True),
    ("3598 N Western Ave", False), ("4860 N Western Ave", False), ("4000 S Western Ave", False),
    ("4001 N Ravenswood Ave", True), ("4799 N Ravenswood Ave", True), ("4000 N Ravenswood Ave", False),
    ("4000 N Damen Ave", False), ("1601 N Milwaukee Ave", False),
    ("4000 N Western Blvd", False), ("4000 N Western", True),
])
def test_tod_matches_by_street_and_number_range(address, on):
    assert bool(tod_streets.tod_street_status(address)) is on


def test_a_western_ave_parcel_shows_the_tod_rules_with_the_ordinance_link():
    ctx = _ctx("4000 N Western Ave")
    note = next(n for n in ctx.coverage_notes if n["id"] == "tod_street")
    assert note["applies"] == "parcel" and note["ahead_of_code"] is True and note["section"] == "17-3-0600"
    assert "SO2026-0025391" in note["text"] and "Oct 14, 2026" in note["text"] and "not yet in the published code" in note["text"]
    assert "electronic data storage centers" in note["text"] and "FAR of at least 3" in note["text"]
    assert "cross street" in note["text"]
    assert note["link"].startswith("https://chicityclerkelms.chicago.gov/Matter/?matterId=")
    # an applied amendment is not also listed as "not reflected on this page"
    assert "code_amendments_parcel" not in [n["id"] for n in ctx.coverage_notes] or "SO2026-0025391" not in next(
        n for n in ctx.coverage_notes if n["id"] == "code_amendments_parcel")["text"]


def test_a_parcel_off_the_tod_streets_has_no_tod_note():
    assert "tod_street" not in _ids(_ctx("4000 N Damen Ave"))


def test_after_codification_the_tod_note_cites_the_section_not_the_ordinance(monkeypatch):
    reviews = {**currency.load_reviews(), "SO2026-0025391": {**REVIEWS["SO2026-0025391"], "codified": True}}
    monkeypatch.setattr(currency, "load_reviews", lambda: reviews)
    note = next(n for n in _ctx("4000 N Western Ave").coverage_notes if n["id"] == "tod_street")
    assert note["ahead_of_code"] is False and "under §17-3-0600" in note["text"] and "not yet in the published code" not in note["text"]


def test_an_unreviewed_tod_amendment_applies_nothing(monkeypatch):
    reviews = {**currency.load_reviews(), "SO2026-0025391": {**REVIEWS["SO2026-0025391"], "review_status": "unreviewed", "product_effect": "pending"}}
    monkeypatch.setattr(currency, "load_reviews", lambda: reviews)
    assert "tod_street" not in _ids(_ctx("4000 N Western Ave"))


# --- pedestrian streets -------------------------------------------------------------------------

def _row(r: list[str]) -> list[str]:
    return [c.strip() for c in r]


def test_belmont_row_pins_to_the_transcription_or_the_code_text():
    t = ORD["O2026-0025464"]
    rows = [_row(r) for r in _rows(1)]
    codified = REVIEWS["O2026-0025464"]["codified"]
    assert (t["new_row"] in rows) is codified and (t["old_row"] in rows) is not codified
    e = REVIEWS["O2026-0025464"]["map_effects"][0]
    assert (e["from"], e["to"]) == (531, 800)  # new_row start .. old_row start


def test_clark_rows_pin_to_the_transcription_or_the_code_text():
    t = ORD["O2026-0025463"]
    rows = [_row(r) for r in _rows(1)]
    codified = REVIEWS["O2026-0025463"]["codified"]
    assert (t["new_row"] in rows) is codified
    assert all((old in rows) is not codified for old in t["old_rows"])
    spans = sorted((e["from"], e["to"]) for e in REVIEWS["O2026-0025463"]["map_effects"])
    assert spans == [(3000, 3432), (3600, 3800)]  # the gaps between the old rows, and the new end


def test_lawrence_rows_pin_to_the_transcription_or_the_code_text():
    t = ORD["O2026-0026042"]
    rows = [_row(r) for r in _rows(0)]
    codified = REVIEWS["O2026-0026042"]["codified"]
    assert (t["old_row"] in rows) is not codified
    assert all((new in rows) is codified for new in t["new_rows"])
    e = REVIEWS["O2026-0026042"]["map_effects"][0]
    assert (e["from"], e["to"]) == (3034, 3042)  # inside the removed 3032W-3042W gap


PED = OverlayDistrict(layer_type="pedestrian_street", name="Pedestrian Streets")


@pytest.mark.parametrize("address", ["3100 N Clark St", "3700 N Clark St", "700 W Belmont Ave", "531 W Belmont Ave", "3000 N Clark St", "3800 N Clark St"])
def test_a_newly_designated_segment_gets_the_pedestrian_standards_note(address):
    note = next((n for n in _ctx(address).coverage_notes if n["id"] == "pedestrian_street_added"), None)
    assert note is not None
    assert note["ahead_of_code"] is True and "§17-3-0504" in note["text"] and "may not show it yet" in note["text"]


@pytest.mark.parametrize("address", ["3500 N Clark St", "3434 N Clark St", "900 W Belmont Ave", "2400 N Clark St", "3050 W Lawrence Ave", "3100 S Clark St"])
def test_addresses_outside_the_new_ranges_get_no_added_note(address):
    assert "pedestrian_street_added" not in _ids(_ctx(address))


def test_a_lawrence_parcel_in_the_removed_segment_says_the_designation_was_removed():
    ctx = _ctx("3036 W Lawrence Ave")  # the overlay lookup can't see pedestrian streets: no overlay needed
    note = next(n for n in ctx.coverage_notes if n["id"] == "pedestrian_street_removed")
    assert "O2026-0026042" in note["text"] and "removed the pedestrian-street designation" in note["text"] and "no longer apply" in note["text"]
    assert applied.pedestrian_street_removed("3036 W Lawrence Ave", []) is True


@pytest.mark.parametrize("address", ["3200 W Lawrence Ave", "3044 W Lawrence Ave", "3032 W Lawrence Ave", "3036 W Lawrence Pl"])
def test_no_removed_note_outside_the_removed_gap(address):
    assert "pedestrian_street_removed" not in _ids(_ctx(address))
    assert applied.pedestrian_street_removed(address, []) is False


def test_once_codified_a_removal_goes_quiet_and_an_addition_cites_the_code(monkeypatch):
    reviews = {k: dict(v) for k, v in currency.load_reviews().items()}
    reviews["O2026-0026042"]["codified"] = True
    reviews["O2026-0025463"]["codified"] = True
    monkeypatch.setattr(currency, "load_reviews", lambda: reviews)
    assert "pedestrian_street_removed" not in _ids(_ctx("3036 W Lawrence Ave"))
    note = next(n for n in _ctx("3100 N Clark St").coverage_notes if n["id"] == "pedestrian_street_added")
    assert note["ahead_of_code"] is False and "now in §17-3-0503-D" in note["text"]


# --- Milwaukee Avenue Special Character Overlay -----------------------------------------------------

SCO = OverlayDistrict(layer_type="special_district", name="Milwaukee Avenue Special Character Overlay District")


def test_sco_prohibited_list_pins_to_the_transcription_or_the_code_text():
    s = _section("17-7-1500")
    if s is None:
        pytest.skip("ordinance corpus not present")
    text = " ".join(s["body_paragraphs"])
    new = ORD["SO2026-0027187"]["new_text"]
    codified = REVIEWS["SO2026-0027187"]["codified"]
    assert ("adaptive reuse or rehabilitation of an existing building" in text) is codified
    assert "1. Strip centers ;" in text or codified
    assert new.startswith("Strip centers")


def test_a_milwaukee_overlay_parcel_gets_the_strip_center_exception_note():
    note = next(n for n in _ctx("1601 N Milwaukee Ave", [SCO]).coverage_notes if n["id"] == "milwaukee_sco_strip_centers")
    assert "§17-7-1506" in note["text"] and "SO2026-0027187" in note["text"] and "not yet in the published code" in note["text"]


def test_other_special_districts_get_no_sco_note():
    other = OverlayDistrict(layer_type="special_district", name="Predominance of the Block (606) District")
    assert "milwaukee_sco_strip_centers" not in _ids(_ctx("1601 N Milwaukee Ave", [other]))


# --- the reviews ------------------------------------------------------------------------------------

PASSED_AFTER_JUNE_17_TITLE17 = {
    "O2026-0025429", "O2026-0025463", "O2026-0025464", "O2026-0026278", "SO2026-0026276", "O2026-0026042",
    "SO2026-0024882", "SO2026-0027187", "SO2026-0025391", "SO2026-0028463",
}


def test_every_title17_amendment_after_the_vintage_is_reviewed_with_a_source_pdf():
    for rec in PASSED_AFTER_JUNE_17_TITLE17:
        a = REVIEWS[rec]
        assert a["review_status"] == "reviewed" and a["product_effect"] in ("applied", "none"), rec
        assert a["summary"] and a["summary_basis"] == "ordinance" and a["source_pdf"].endswith(".pdf"), rec


def test_the_applied_ones_are_exactly_those_with_a_product_surface():
    applied_records = {r for r in PASSED_AFTER_JUNE_17_TITLE17 if REVIEWS[r]["product_effect"] == "applied"}
    assert applied_records == {"SO2026-0025391", "O2026-0025464", "O2026-0025463", "O2026-0026042", "SO2026-0027187"}


def test_the_amended_gas_station_summaries_stay_pinned_to_the_use_table():
    # M4 (SO2026-0024923) moved the C1/C2 summaries; the July EV-charger trigger adds nothing to them.
    assert REVIEWS["O2026-0025429"]["product_effect"] == "none"
    assert re.search(r"7 or more", REVIEWS["O2026-0025429"]["summary"])


# --- the report ---------------------------------------------------------------------------------------

def _report_signals(address: str, overlays=()):
    from backend.models import ReportData
    from backend.report_builder import _synthesize_opportunities_constraints

    ctx = _ctx(address, overlays)
    r = ReportData(context=ctx, report_date="2026-10-21", address=address)
    opps, cons = _synthesize_opportunities_constraints(r)
    return [o["signal"] for o in opps], [c["signal"] for c in cons]


def test_the_report_lists_a_tod_street_as_a_constraint():
    _, cons = _report_signals("4000 N Western Ave")
    assert "TOD street — use limits and rezoning rule" in cons
    assert "TOD street — use limits and rezoning rule" not in _report_signals("4000 N Damen Ave")[1]


def test_the_report_drops_the_pedestrian_opportunity_where_the_designation_was_removed():
    assert "Pedestrian street overlay" not in _report_signals("3036 W Lawrence Ave", [PED])[0]
    assert "Pedestrian street overlay" in _report_signals("3200 W Lawrence Ave", [PED])[0]


def test_the_chat_prompt_tells_the_model_to_restate_applied_law_as_not_yet_codified():
    from backend.prompts import SYNTHESIZER_SYSTEM

    assert "ahead_of_code: true" in SYNTHESIZER_SYSTEM and "not yet in the published code" in SYNTHESIZER_SYSTEM
