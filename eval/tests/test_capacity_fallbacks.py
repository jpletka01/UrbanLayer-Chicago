"""WS8 Phase 0 slice 2: the Profile's merge rules applied to a parcel with no building area, and the sample math."""

import pytest

from eval import capacity_fallbacks as cf


def test_commercial_valuation_wins_over_energy_and_footprint():
    res = cf.resolve_gfa(
        {"commercial": {"bldg_sqft": 8000}, "energy": {"gross_floor_area": 60000}, "footprint": {"bldg_sqft": 3000}},
        land_sqft=10000, allowed_far=2.0,
    )
    assert (res["source"], res["sqft"], res["outcome"]) == ("commercial_valuation", 8000, "resolved")


def test_multi_pin_member_gets_no_area_from_the_complex_total():
    res = cf.resolve_gfa({"commercial": {"bldg_sqft": None, "complex_bldg_sqft": 43790}}, land_sqft=4347, allowed_far=3.0)
    assert res["outcome"] == "unresolved" and "complex_total_only" in res["flags"]


def test_energy_fills_when_commercial_is_absent():
    res = cf.resolve_gfa({"energy": {"gross_floor_area": 90000}}, land_sqft=40000, allowed_far=5.0)
    assert (res["source"], res["outcome"]) == ("energy_benchmark", "resolved")


def test_footprint_larger_than_the_lot_belongs_to_a_building_spanning_lots():
    res = cf.resolve_gfa({"footprint": {"bldg_sqft": 5000}}, land_sqft=4000, allowed_far=2.0)
    assert res["outcome"] == "unresolved" and "footprint_spans_lots" in res["flags"]
    ok = cf.resolve_gfa({"footprint": {"bldg_sqft": 4400}}, land_sqft=4000, allowed_far=2.0)  # exactly the 10% slack
    assert ok["outcome"] == "resolved" and ok["source"] == "footprint"


def test_footprint_with_stories_but_no_area_is_not_an_area():
    res = cf.resolve_gfa({"footprint": {"bldg_sqft": None, "stories": 3}}, land_sqft=4000, allowed_far=2.0)
    assert res["outcome"] == "unresolved" and "footprint_no_area" in res["flags"]


def test_a_resolved_area_with_an_implausible_far_is_flagged_not_counted():
    res = cf.resolve_gfa({"commercial": {"bldg_sqft": 100000}}, land_sqft=4000, allowed_far=2.0)
    assert res["outcome"] == "implausible" and "implausible_far" in res["flags"]


def test_nothing_fetched_is_unresolved():
    assert cf.resolve_gfa({}, land_sqft=4000, allowed_far=2.0)["outcome"] == "unresolved"


def test_wilson_interval():
    assert cf.wilson(0, 0) == (0.0, 0.0)
    lo, hi = cf.wilson(5, 10)
    assert lo < 0.5 < hi and 0.23 < lo < 0.24 and 0.76 < hi < 0.77


def test_draw_sample_is_seeded_and_takes_all_of_a_small_area():
    cands = {1: [f"p{i}" for i in range(50)], 2: ["a", "b"]}
    one = cf.draw_sample(cands, {}, per_area=5, condo_per_area=1, seed=7)
    two = cf.draw_sample(dict(reversed(list(cands.items()))), {}, per_area=5, condo_per_area=1, seed=7)
    assert one == two
    assert len(one["unknown_gfa"]) == 7 and {"a", "b"} <= set(one["unknown_gfa"])


def test_summarize_never_rates_a_fetch_error():
    recs = [
        {"stratum": "unknown_gfa", "ca": 1, "outcome": "resolved", "source": "footprint", "flags": []},
        {"stratum": "unknown_gfa", "ca": 1, "outcome": "unresolved", "source": None, "flags": ["footprint_no_area"]},
        {"stratum": "unknown_gfa", "ca": 1, "outcome": "fetch_error", "source": None, "flags": ["HTTPError"]},
    ]
    s = cf.summarize(recs)["unknown_gfa"]
    assert s["sampled"] == 3 and s["fetch_errors"] == 1
    assert s["citywide"]["n"] == 2 and s["citywide"]["resolved_share"] == pytest.approx(0.5)
    assert s["citywide"]["by_source"] == {"footprint": 1}
