"""WS0 confidence states (guide §3): the thresholds are pinned at their boundaries.

A value exactly at a constant is not past it: 10.00% coverage is not withheld, 25.00% is not
faded, n = 30 is enough, CV = 30.0% is not faded. One place decides (``confidence_state``);
these tests are why nothing else needs to."""

import pytest

from backend import provenance as P
from backend.provenance import confidence_state, make_entry

QD = "2026-10-20"


def _state(fact="zoning.far", *, coverage=None, precision=None, **kw):
    e = make_entry(fact, query_date=QD, coverage=coverage, precision=precision, **kw)
    return e["confidence"], e["confidence_reasons"]


def test_the_constants_are_the_guides():
    assert (P.HIDE_COVERAGE_BELOW, P.FADE_COVERAGE_BELOW) == (0.10, 0.25)
    assert (P.FADE_CV_ABOVE, P.HIDE_CV_ABOVE, P.HIDE_N_BELOW) == (0.30, 0.50, 30)
    assert (P.COMPS_FADE_N_BELOW, P.COMPS_HIDE_N_BELOW) == (5, 3)
    assert (P.AI_CORROBORATED_RATE, P.AI_CORROBORATED_MIN_N) == (0.95, 30)


def test_a_figure_with_nothing_wrong_is_standard():
    assert _state() == ("standard", [])
    assert _state(coverage={"n": 12, "share": 0.9}, precision={"moe": 3, "moe_level": 0.9, "cv": 0.05}) == ("standard", [])


@pytest.mark.parametrize("share,state", [
    (0.0999, "withheld"), (0.0999999, "withheld"), (0.10, "low"), (0.1001, "low"),
    (0.2499, "low"), (0.25, "standard"), (0.2501, "standard"), (1.0, "standard"),
])
def test_coverage_share_boundaries(share, state):
    got, reasons = _state(coverage={"share": share})
    assert got == state
    assert ("low_coverage" in reasons) == (state != "standard")


@pytest.mark.parametrize("n,state", [(0, "withheld"), (29, "withheld"), (30, "standard"), (31, "standard")])
def test_the_n_rule_applies_to_area_samples(n, state):
    assert _state(coverage={"n": n, "sample": "area_sample"})[0] == state


def test_the_n_rule_does_not_apply_to_lists_or_to_a_figure_with_no_sample_kind():
    # every record is shown (a list of 12 violations), or ACS publishes no per-tract n
    assert _state(coverage={"n": 12})[0] == "standard"
    assert _state(coverage={"n": 0})[0] == "standard"


@pytest.mark.parametrize("n,state", [(0, "withheld"), (2, "withheld"), (3, "low"), (4, "low"), (5, "standard"), (20, "standard")])
def test_comps_fade_under_five_and_withhold_under_three(n, state):
    got, reasons = _state(coverage={"n": n, "sample": "comps"})
    assert got == state
    assert ("small_sample" in reasons) == (state != "standard")


@pytest.mark.parametrize("cv,state", [
    (0.0, "standard"), (0.299, "standard"), (0.30, "standard"), (0.301, "low"),
    (0.50, "low"), (0.501, "withheld"), (0.9, "withheld"),
])
def test_cv_boundaries(cv, state):
    got, reasons = _state(precision={"cv": cv})
    assert got == state
    assert ("high_cv" in reasons) == (state != "standard")


def test_the_worst_rule_wins_and_every_reason_is_listed():
    got, reasons = _state(coverage={"share": 0.2}, precision={"cv": 0.6})
    assert got == "withheld" and reasons == ["high_cv", "low_coverage"]
    got, reasons = _state(coverage={"share": 0.2}, precision={"cv": 0.4})
    assert got == "low" and reasons == ["low_coverage", "high_cv"]


# --- method rules that do not depend on numbers ------------------------------------------------------------------

def test_a_bracket_median_with_no_published_error_is_low():
    got, reasons = _state(tier="our_calculation", method_key="bracket_median")
    assert (got, reasons) == ("low", ["bracket_median"])
    # a published error makes it an ordinary precision question
    assert _state(tier="our_calculation", method_key="bracket_median", precision={"moe": 4000, "cv": 0.1})[0] == "standard"


def test_an_ai_reading_is_low_until_corroborated():
    kw = dict(tier="ai_extracted", method_key="ai_read_code")
    assert _state(**kw) == ("low", ["ai_unverified"])
    assert _state(**kw, corroborated=True) == ("standard", [])
    # measured agreement: at least 95% on at least 30 hand-checked items
    assert _state(**kw, precision={"agreement": {"n": 30, "agree": 29}})[0] == "standard"   # 96.7%
    assert _state(**kw, precision={"agreement": {"n": 40, "agree": 38}})[0] == "standard"   # 95.0%
    assert _state(**kw, precision={"agreement": {"n": 40, "agree": 37}})[0] == "low"        # 92.5%
    assert _state(**kw, precision={"agreement": {"n": 29, "agree": 29}})[0] == "low"        # 100% on too few


def test_the_ai_rule_follows_the_method_key_too():
    # an ordinance reader is AI whatever tier the caller put on it
    assert _state(tier="official_record", method_key="ai_read_ordinance")[0] == "low"


# --- old_source informs the caption but never changes the state ------------------------------------------------

def test_old_source_is_a_reason_for_an_old_dataset_not_a_state():
    old = _state(as_of="2015-08-14", as_of_basis="source_updated")
    assert old == ("standard", ["old_source"])
    assert _state(as_of="2024-10-21", as_of_basis="source_updated") == ("standard", [])  # 729 days
    assert _state(as_of="2024-10-20", as_of_basis="source_updated")[1] == []             # exactly 730
    assert _state(as_of="2024-10-19", as_of_basis="source_updated")[1] == ["old_source"]  # 731


def test_a_records_own_edit_date_or_code_currency_is_not_a_dataset_age():
    assert _state(as_of="2015-01-01", as_of_basis="record_updated")[1] == []
    assert _state(as_of="2015-01-01", as_of_basis="current_through")[1] == []
    assert _state(as_of=None)[1] == []  # no date: we only know when we asked


def test_a_frozen_survey_older_than_two_years_is_flagged():
    assert _state(as_of="2018-12-31", as_of_basis="vintage")[1] == ["old_source"]


# --- the function takes an entry or a dict -------------------------------------------------------------------------

def test_confidence_state_reads_a_wire_dict_the_same_as_a_model():
    e = make_entry("zoning.far", query_date=QD, coverage={"share": 0.2})
    assert confidence_state(e) == ("low", ["low_coverage"])
    assert confidence_state({"coverage": {"share": 0.05}}) == ("withheld", ["low_coverage"])
    assert confidence_state({}) == ("standard", [])
