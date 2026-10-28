"""The WS4 method proof's math: bracket parsing, interpolated medians, margins of error, and the verdict rules."""

import math

import pytest

from backend import provenance
from eval import rent_method as rm


def test_parse_bracket_reads_census_labels():
    assert rm.parse_bracket("Estimate!!Total:!!With cash rent:!!Less than $100") == (0.0, 100.0)
    assert rm.parse_bracket("Estimate!!Total:!!With cash rent:!!$1,000 to $1,249") == (1000.0, 1250.0)
    assert rm.parse_bracket("Estimate!!Total:!!With cash rent:!!$3,500 or more") == (3500.0, None)
    for label in ("Estimate!!Total:", "Estimate!!Total:!!With cash rent:", "Estimate!!Total:!!No cash rent"):
        assert rm.parse_bracket(label) is None


def _uniform() -> list[rm.Bracket]:
    return [(i * 100.0, (i + 1) * 100.0, 1000.0) for i in range(10)]


def test_median_interpolates_inside_the_bracket():
    assert rm.bracket_median(_uniform()) == pytest.approx(500.0)
    # 25 / 75 in the first two brackets: the median sits a third of the way into the second one
    assert rm.bracket_median([(0.0, 100.0, 25.0), (100.0, 200.0, 75.0), (200.0, None, 0.0)]) == pytest.approx(133.33, abs=0.01)


def test_a_median_in_the_open_ended_bracket_is_not_invented():
    assert rm.bracket_median([(0.0, 1500.0, 10.0), (1500.0, None, 90.0)]) is None
    assert rm.bracket_median([(0.0, 1500.0, 0.0), (1500.0, None, 0.0)]) is None


def test_handbook_margin_matches_a_hand_computation():
    # B = 10,000 -> SE(50%) = sqrt(99/10000 * 2500) = 4.975 points, so the 68% interval of a uniform 0-1000 runs
    # from the 45.025th to the 54.975th percentile (450.25 to 549.75): SE(median) = 49.75, MOE90 = 1.645 * 49.75
    se_points = math.sqrt(99 / 10000 * 2500)
    assert rm.handbook_median_moe(_uniform()) == pytest.approx(1.645 * 1000 * se_points / 100, rel=1e-9)
    assert rm.handbook_median_moe(_uniform(), design_factor=1.5) == pytest.approx(1.5 * 1.645 * 1000 * se_points / 100, rel=1e-9)


def test_handbook_margin_is_none_when_it_cannot_be_bounded():
    assert rm.handbook_median_moe([]) is None
    assert rm.handbook_median_moe([(0.0, 100.0, 4.0), (100.0, None, 4.0)]) is None  # interval leaves 0-100%
    # the upper percentile lands in the open-ended bracket
    assert rm.handbook_median_moe([(0.0, 1500.0, 5000.0), (1500.0, None, 5000.0)]) is None


def test_simulated_margin_is_reproducible_and_tracks_the_published_error():
    edges = [(lo, hi) for lo, hi, _ in _uniform()]
    est = [[100.0] * 10, [100.0] * 10]
    tight = rm.simulated_median_moe(edges, est, [[1.0] * 10, [1.0] * 10])
    loose = rm.simulated_median_moe(edges, est, [[80.0] * 10, [80.0] * 10])
    assert tight == rm.simulated_median_moe(edges, est, [[1.0] * 10, [1.0] * 10])
    assert tight[0] == pytest.approx(500.0) and loose[0] == pytest.approx(500.0)
    assert tight[1] < 5 and loose[1] > 5 * tight[1]


def test_simulated_margin_reports_none_when_the_median_is_top_coded():
    edges = [(0.0, 1500.0), (1500.0, None)]
    median, moe = rm.simulated_median_moe(edges, [[10.0, 90.0]], [[5.0, 5.0]])
    assert median is None and moe is None


def test_verdict_uses_the_confidence_standards_cv_rules():
    def moe_for(cv: float) -> float:
        return cv * 1000 * rm.MOE_Z

    assert rm.judge(1000, moe_for(0.30)) == "standard"  # boundary: > 0.30 fades
    assert rm.judge(1000, moe_for(0.31)) == "low"
    assert rm.judge(1000, moe_for(0.50)) == "low"  # boundary: > 0.50 withholds
    assert rm.judge(1000, moe_for(0.51)) == "withheld"
    assert rm.judge(1000, None) == "no_moe"
    assert rm.judge(None, None) == "unavailable" and rm.judge(0, 5) == "unavailable"


def test_coverage_verdict_boundaries():
    assert rm.judge_coverage(0.0999) == "withheld" and rm.judge_coverage(0.10) == "low"
    assert rm.judge_coverage(0.2499) == "low" and rm.judge_coverage(0.25) == "standard"
    assert rm.judge_coverage(None) == "unknown"


def test_the_proofs_thresholds_are_the_standards():
    assert (rm.FADE_CV_ABOVE, rm.HIDE_CV_ABOVE) == (provenance.FADE_CV_ABOVE, provenance.HIDE_CV_ABOVE)
    assert (rm.FADE_COVERAGE_BELOW, rm.HIDE_COVERAGE_BELOW) == (provenance.FADE_COVERAGE_BELOW, provenance.HIDE_COVERAGE_BELOW)
    assert rm.HIDE_N_BELOW == provenance.HIDE_N_BELOW
    assert math.isclose(rm.MOE_Z, 1.645)


def test_each_tract_goes_to_the_community_area_holding_most_of_its_parcels():
    out = rm.assign_tracts({("t1", "5"): 90, ("t1", "6"): 10, ("t2", "7"): 3})
    assert out["t1"] == ("5", pytest.approx(0.9)) and out["t2"] == ("7", 1.0)
