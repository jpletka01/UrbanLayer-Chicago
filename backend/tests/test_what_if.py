"""WS5 PR2: "What if this were rezoned?" — district table arithmetic beside the parcel's own district."""

import pytest
from fastapi.testclient import TestClient

from backend import what_if as wi
from backend.main import app


def test_suggestions_step_up_within_the_family():
    assert wi.suggestions("RS-3") == ["RT-3.5", "RT-4", "RM-4.5"]
    assert wi.suggestions("B1-1")[0] == "B3-1"  # B1/B2 step to B3 at the same intensity first
    assert wi.suggestions("B3-2") == ["B3-3", "B3-5"]
    assert wi.suggestions("RM-6.5") == []  # the top of the ladder


@pytest.mark.parametrize("zone", ["PD 1235", "PMD 6", "POS-2", "XX-9", "", None])
def test_no_suggestions_for_pd_or_unknown(zone):
    assert wi.suggestions(zone) == []


def test_every_comparable_district_is_in_the_table_and_none_is_pd():
    zones = wi.comparable_districts()
    assert zones and all(not z.startswith(("PD", "PMD", "POS")) for z in zones)
    for z in zones:
        assert wi.district_figures(z, 5_000)["zone_class"] == z


def test_figures_are_the_table_times_this_lot():
    f = wi.district_figures("RT-4", 3_125)
    assert f["far"] == 1.2 and f["max_floor_area_sqft"] == 3_750 and f["units_by_lot_area"] == 3
    assert f["max_height"] and f["code_section"].startswith("§17-2")


def test_unknown_lot_gives_no_floor_area_or_units():
    f = wi.district_figures("RT-4", None)
    assert f["max_floor_area_sqft"] is None and f["units_by_lot_area"] is None and f["far"] == 1.2


def test_606_rule_carries_into_an_rs3_comparison():
    assert wi.district_figures("RS-3", 3_125, in_606=True)["units_by_lot_area"] == 2
    assert wi.district_figures("RS-3", 3_125, in_606=False)["units_by_lot_area"] == 1


def test_pd_target_is_refused_with_the_reason():
    with pytest.raises(wi.WhatIfError, match="own ordinance"):
        wi.district_figures("PD 12", 5_000)


def test_pd_parcel_can_still_look_at_a_district():
    out = wi.compare("PD 1235", "B3-3", 5_000)
    assert out["current"] is None and out["target"]["zone_class"] == "B3-3" and out["suggestions"] == []


def test_endpoint():
    c = TestClient(app)
    r = c.get("/api/what-if", params={"current": "RS-3"})
    assert r.status_code == 200 and r.json()["suggestions"][0] == "RT-3.5" and "RT-4" in r.json()["districts"]
    r = c.get("/api/what-if", params={"current": "RS-3", "district": "RT-4", "lot_sqft": 3125, "in_606": "false"})
    body = r.json()
    assert body["current"]["units_by_lot_area"] == 1 and body["target"]["units_by_lot_area"] == 3
    assert c.get("/api/what-if", params={"current": "RS-3", "district": "PD 5"}).status_code == 422
    assert c.get("/api/what-if").status_code == 422
