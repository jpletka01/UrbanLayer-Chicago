"""Deterministic tests for the eval scorers.

The suites that call models or live APIs can't run in CI without keys, but the
code that turns their raw output into pass/fail and grades can. A bug there
silently changes every reported number, so it is tested like any other code.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.lot_coverage import FieldStatus, _classify_fields
from eval.retrieval_benchmark import ChunkAnalysis, _grade_query
from eval.run_eval import _check_plan, _check_retrieval
from eval.source_coverage import CoverageStatus, check_context_field, check_synthesis_patterns, determine_status

FIXTURES = Path(__file__).parent / "fixtures"


# --- router plan checks (run_eval) -------------------------------------------

PLAN = {
    "sources": ["crime_api", "311_api"],
    "intent": "neighborhood_overview",
    "requires_disclaimer": False,
    "location": {"type": "neighborhood", "resolved_community_area": 24},
    "time_range_days": 90,
    "clarification": None,
}


def test_matching_plan_passes():
    expect = {
        "sources_include": ["crime_api"],
        "intent": "neighborhood_overview",
        "expected_community_area": 24,
        "location_resolved": True,
        "time_range_days_at_most": 90,
        "clarification_present": False,
    }
    assert _check_plan(PLAN, expect) == []


def test_each_mismatch_is_reported():
    expect = {
        "sources_include": ["permits_api"],
        "intent": "incident_lookup",
        "expected_community_area": 7,
        "time_range_days_at_most": 30,
    }
    failures = _check_plan(PLAN, expect)
    assert len(failures) == 4


def test_sources_any_of():
    assert _check_plan(PLAN, {"sources_any_of": ["permits_api", "311_api"]}) == []
    assert _check_plan(PLAN, {"sources_any_of": ["permits_api"]})


def test_retrieval_gold_is_substring_match():
    assert _check_retrieval(["17-9-0200", "17-7-0570"], {"retrieval_section_contains_any": ["17-9"]}) == []
    assert _check_retrieval(["13-12-010"], {"retrieval_section_contains_any": ["17-9"]})


# --- source coverage classification ------------------------------------------

def test_coverage_status_matrix():
    assert determine_status(True, True) is CoverageStatus.COVERED
    assert determine_status(True, False) is CoverageStatus.SYNTHESIS_GAP
    assert determine_status(False, True) is CoverageStatus.HALLUCINATION
    assert determine_status(False, False) is CoverageStatus.RETRIEVAL_GAP
    assert determine_status(False, False, optional=True) is CoverageStatus.NOT_TESTED


def test_context_field_or_paths_and_boolean_presence():
    ctx = {"crime_last_90d": None, "open_311_requests": {"total": 5}}
    assert check_context_field(ctx, "crime_last_90d|open_311_requests").present
    assert not check_context_field(ctx, "crime_last_90d").present


def test_synthesis_patterns_required_and_any_of():
    spec = {"patterns": [r"\d+ crimes"], "any_of_groups": [["arrest", "cleared"]]}
    _, ok = check_synthesis_patterns("There were 120 crimes; 15% led to an arrest.", spec)
    assert ok
    _, ok = check_synthesis_patterns("Crime is moderate.", spec)
    assert not ok


# --- retrieval grading ---------------------------------------------------------

def _chunk(rank: int, section: str, gold: bool, body: str = "setback requirements apply") -> ChunkAnalysis:
    return ChunkAnalysis(
        rank=rank, section=section, section_title="", score=0.8, char_count=len(body),
        has_table=False, data_row_count=0, is_table_fragment=False, is_header_only=False,
        is_legend_only=False, is_transitional=False, matches_gold_section=gold,
        body_preview=body, body_text=body,
    )


def test_two_gold_hits_in_top_three_is_an_a():
    chunks = [_chunk(1, "17-2-0300", True), _chunk(2, "17-2-0310", True), _chunk(3, "13-4-010", False)]
    assert _grade_query(chunks, ["setback"])[0] == "A"


def test_gold_only_below_top_three_is_a_d():
    chunks = [_chunk(i, f"13-{i}", False) for i in range(1, 4)] + [_chunk(4, "17-2-0300", True)]
    grade, issues = _grade_query(chunks, [])
    assert grade == "D"
    assert "gold section(s) found but not in top-3" in issues


def test_no_gold_is_an_f_and_missing_terms_cap_at_c():
    assert _grade_query([_chunk(1, "13-1", False)], [])[0] == "F"
    chunks = [_chunk(1, "17-2-0300", True), _chunk(2, "17-2-0310", True)]
    assert _grade_query(chunks, ["variance"])[0] == "C"


# --- lot coverage field classification (recorded /api/scorecard response) ----

def test_lot_fields_from_a_recorded_profile():
    resp = json.loads((FIXTURES / "scorecard_1601_n_milwaukee.json").read_text())
    fields = _classify_fields(resp, {"address": "1601 N Milwaukee Ave", "truth_pin": "14313320180000"})
    for name in ("pin_resolved", "pin_matches_truth", "land_sqft", "bldg_sqft", "tax_bill", "zoning_class", "zoning_far"):
        assert fields[name] == FieldStatus.PRESENT.value, name


def test_wrong_truth_pin_is_not_a_match():
    resp = json.loads((FIXTURES / "scorecard_1601_n_milwaukee.json").read_text())
    fields = _classify_fields(resp, {"address": "1601 N Milwaukee Ave", "truth_pin": "14330000000000"})
    assert fields["pin_matches_truth"] != FieldStatus.PRESENT.value
