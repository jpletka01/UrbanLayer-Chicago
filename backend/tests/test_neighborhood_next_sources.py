"""The new UI's Neighborhood sources (decision Item 102): assigned schools with the state's report card,
construction within ½ mile, and the community area's top 311 requests. Network mocked."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval import buildings, three11
from backend.retrieval.neighborhood import schools

pytestmark = pytest.mark.asyncio

LAT, LON = 41.9098, -87.6774


async def test_assigned_schools_join_the_report_card_by_cps_id():
    es = [{"school_id": "610229", "school_add": "2009 W SCHILLER ST  CHICAGO, IL 60622", "boundarygr": "K, 1, 2"}]
    hs = [{"school_id": "609759", "school_add": "1147 N WESTERN AVE", "boundarygr": "9, 10, 11, 12"}]
    with patch.object(schools, "socrata_get", new=AsyncMock(side_effect=[es, hs])):
        out = await schools.assigned_schools(LAT, LON)
    e, h = out["elementary"], out["high"]
    assert e["name"] == "A.N. Pritzker School" and e["level"] == "elementary"
    assert e["report_card"]["designation"] == "Commendable" and e["report_card"]["year"] == 2025
    assert "Schoolid=150162990252510" in e["report_card_url"]
    assert h["report_card"]["graduation_4yr_pct"] is not None
    assert h["report_card"]["math_source"] == "hs_assessment"  # suppressed in the combined sheet


async def test_no_boundary_is_a_checked_none_and_an_unknown_school_is_still_named():
    es = [{"school_id": "999999", "school_add": "1 MAIN ST", "boundarygr": "K"}]
    with patch.object(schools, "socrata_get", new=AsyncMock(side_effect=[es, []])):
        out = await schools.assigned_schools(LAT + 0.001, LON)
    assert out["high"] is None
    assert out["elementary"]["school_id"] == "999999" and out["elementary"]["report_card"] is None


async def test_a_failed_boundary_query_raises_and_caches_nothing():
    with patch.object(schools, "socrata_get", new=AsyncMock(side_effect=RuntimeError("503"))):
        with pytest.raises(RuntimeError):
            await schools.assigned_schools(LAT, LON)
    assert schools._cache.get(f"schools:{round(LAT, 5)}:{round(LON, 5)}") is None


async def test_the_artifact_covers_cps_and_holds_only_state_figures():
    art = schools._artifact()
    assert len(art["schools"]) >= 600
    allowed = {"name", "category", "cps_url", "rcdts", "isbe_name", "type", "grades", "designation", "enrollment",
               "graduation_4yr_pct", "ela_pct", "math_pct", "ela_source", "math_source"}
    for rec in art["schools"].values():
        assert set(rec) <= allowed  # no demographic breakdowns (Item 102: race and ethnicity left out)


async def test_construction_within_keeps_distance_kind_and_units():
    rows = [
        {"permit_": "1", "permit_type": "PERMIT - NEW CONSTRUCTION", "work_description": "ERECT 4-STORY 8-UNIT",
         "issue_date": "2026-05-01T00:00:00.000", "reported_cost": "2400000", "residential_unit_change": "8",
         "street_number": "1700", "street_direction": "N", "street_name": "MILWAUKEE AVE",
         "latitude": "41.9110", "longitude": "-87.6780"},
        {"permit_": "2", "permit_type": "PERMIT - RENOVATION/ALTERATION", "work_description": "GUT REHAB",
         "issue_date": "2025-12-01T00:00:00.000", "reported_cost": "300000", "residential_unit_change": "",
         "latitude": "41.9050", "longitude": "-87.6774"},
        {"permit_": "3", "permit_type": "PERMIT - NEW CONSTRUCTION"},  # no location: dropped
    ]
    with patch.object(buildings, "socrata_get", new=AsyncMock(return_value=rows)) as get:
        out = await buildings.construction_within(LAT, LON)
    where = get.call_args.args[1]["$where"]
    assert "within_circle(location" in where and "reported_cost >= 250000" in where
    a, b = out["projects"]
    assert a["kind"] == "new" and a["units_added"] == 8 and a["address"] == "1700 N Milwaukee Ave"
    assert 0 < a["distance_mi"] < 0.2
    assert b["kind"] == "renovation" and b["units_added"] is None
    assert out["capped"] is False


async def test_area_311_drops_non_concerns_and_cleans_names():
    rows = [
        {"sr_type": "Graffiti Removal Request", "count": "70"},
        {"sr_type": "311 INFORMATION ONLY CALL", "count": "60"},
        {"sr_type": "Tree Trim Request (NO LONGER BEING ACCEPTED)", "count": "20"},
        {"sr_type": "Finance Parking Code Enforcement Review", "count": "10"},
    ]
    with patch.object(three11, "socrata_get", new=AsyncMock(return_value=rows)):
        out = await three11.top_311_by_community_area(24)
    assert out["total"] == 90
    assert out["top"] == [{"type": "Graffiti Removal Request", "count": 70}, {"type": "Tree Trim Request", "count": 20}]
