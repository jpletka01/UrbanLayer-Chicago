"""WS8 Phase 0 slice 3: the panel comparison's pure parts."""

import pytest

from eval import capacity_panel as cp


def test_dashed_pin():
    assert cp.dashed("20331000020000") == "20-33-100-002-0000"
    assert cp.dashed("20-33-100-002-0000") == "20-33-100-002-0000"


@pytest.mark.parametrize(
    "index_val, profile_val, relation",
    [
        (None, None, "both_missing"),
        (0, None, "both_missing"),
        (None, 5000, "profile_only"),
        (5000, None, "index_only"),
        (5000, 5200, "agree"),
        (5000, 5300, "differ"),
    ],
)
def test_area_relation(index_val, profile_val, relation):
    assert cp.area_relation(index_val, profile_val) == relation


def _row():
    return {"address": "1 N Test St", "truth_pin": "14331030110000", "township": "14"}


def _attrs(**kw):
    base = {"zoning_group": "business", "class": "5-17", "land_sqft": 6000.0, "bldg_sqft": None, "density_band": 2.2}
    base.update(kw)
    return base


def _facts(**kw):
    base = {"pin14": "14331030110000", "class": "5-17", "bldg_sqft": 9000, "bldg_source": "commercial_valuation",
            "land_sqft": 6000, "allowed_far": 2.2, "nearest_unverified": False}
    base.update(kw)
    return base


def test_an_index_gap_the_chain_fills_is_a_state_flip_not_a_contradiction():
    out = cp.compare(_row(), _facts(), _attrs())
    assert out["outcome"] == "compared" and out["bldg"] == "profile_only"
    assert (out["index_state"], out["profile_state"]) == ("unknown_gfa", "computable")


def test_a_nearest_parcel_stand_in_is_set_aside():
    assert cp.compare(_row(), _facts(nearest_unverified=True), _attrs())["outcome"] == "pin_mismatch"
    assert cp.compare(_row(), _facts(pin14="14331030120000"), _attrs())["outcome"] == "pin_mismatch"


def test_failed_fetch_and_missing_index_row_are_never_a_disagreement():
    assert cp.compare(_row(), None, _attrs(), "ReadTimeout")["outcome"] == "fetch_error"
    assert cp.compare(_row(), _facts(), None)["outcome"] == "not_in_index"


def test_zone_far_difference_is_reported_apart_from_area():
    out = cp.compare(_row(), _facts(allowed_far=1.2), _attrs(bldg_sqft=9000.0))
    assert out["far"] == "differ" and out["bldg"] == "agree"


def test_vacant_class_in_the_profile_is_vacant_land():
    facts = _facts(**{"class": "1-00"}, bldg_sqft=None)
    assert cp.profile_state(facts, _attrs(**{"class": "1-00"})) == "vacant_land"


def test_summarize_counts_state_flips():
    rows = [cp.compare(_row(), _facts(), _attrs()), cp.compare(_row(), _facts(), _attrs(bldg_sqft=9000.0))]
    s = cp.summarize(rows)
    assert s["compared"] == 2 and s["state_agree"] == 1
    assert s["state_flips"] == {"unknown_gfa -> computable": 1}
    assert s["bldg_source_when_profile_only"] == {"commercial_valuation": 1}
