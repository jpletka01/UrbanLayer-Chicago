"""The History tab's sources (decision Item 103): the City's permits and violations at the address, and every
source's value per building fact. All external calls mocked."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval import buildings
from backend.retrieval.property import building_records as br

pytestmark = pytest.mark.asyncio


async def test_address_permits_match_the_street_name_with_its_suffix():
    """The permits dataset's street_name is "SPAULDING AVE"; an exact match on "SPAULDING" found nothing for every
    address (live 2026-11-10), including the $25 report's address permits."""
    with patch.object(buildings, "socrata_get", new=AsyncMock(return_value=[])) as get:
        await buildings.address_specific_permits("2541", "N", "SPAULDING", suffix="AVE")
    where = get.call_args[0][1]["$where"]
    assert "upper(street_name) in ('SPAULDING', 'SPAULDING AVE')" in where


async def test_address_permits_without_a_suffix_take_the_name_and_any_one_suffix():
    with patch.object(buildings, "socrata_get", new=AsyncMock(return_value=[])) as get:
        await buildings.address_specific_permits("100", "E", "GRAND")
    assert "(upper(street_name)='GRAND' OR upper(street_name) like 'GRAND %')" in get.call_args[0][1]["$where"]


def test_street_suffix_reads_the_suffix_and_leaves_parse_unchanged():
    assert buildings.street_suffix("2541 N Spaulding Ave, Chicago, IL") == "AVE"
    assert buildings.street_suffix("100 E Grand") is None
    assert buildings.parse_chicago_address("2541 N Spaulding Ave") == {"number": "2541", "direction": "N", "name": "SPAULDING"}


async def test_permits_at_address_shape_every_year_and_the_permit_type():
    row = {"permit_": "100384380", "permit_type": "PERMIT - EASY PERMIT PROCESS", "issue_date": "2011-03-09T00:00:00.000",
           "reported_cost": "17000", "work_description": "GARAGE", "street_number": "2541", "street_direction": "N",
           "street_name": "SPAULDING AVE", "permit_status": "COMPLETE", "processing_time": "0"}
    with patch.object(buildings, "socrata_get", new=AsyncMock(return_value=[row])) as get:
        got = await buildings.permits_at_address("2541 N SPAULDING AVE")
    params = get.call_args[0][1]
    assert params["$limit"] == buildings.HISTORY_PERMITS_LIMIT
    p = got["projects"][0]
    assert p["kind"] == "other" and p["permit_type"] == "EASY PERMIT PROCESS" and p["issued"] == "2011-03-09"
    assert p["cost"] == 17000 and p["address"] == "2541 N Spaulding Ave" and p["distance_mi"] is None
    assert got["capped"] is False


@pytest.mark.parametrize("ptype,kind", [
    ("PERMIT - NEW CONSTRUCTION", "new"), ("PERMIT - WRECKING/DEMOLITION", "demolition"),
    ("PERMIT - RENOVATION/ALTERATION", "renovation"), ("PERMIT - SIGNS", "other"),
])
def test_permit_kind(ptype, kind):
    assert buildings._permit_kind(ptype) == kind


async def test_a_failed_address_lookup_raises_never_none():
    with patch.object(buildings, "socrata_get", new=AsyncMock(side_effect=RuntimeError("503"))):
        with pytest.raises(RuntimeError):
            await buildings.permits_at_address("2541 N SPAULDING AVE")
        with pytest.raises(RuntimeError):
            await buildings.violations_at_address("2541 N SPAULDING AVE")
        # The Profile's own callers keep their old behavior.
        assert await buildings.address_specific_permits("2541", "N", "SPAULDING") == []


async def test_an_unreadable_address_asks_nothing():
    with patch.object(buildings, "socrata_get", new=AsyncMock()) as get:
        assert await buildings.permits_at_address("Somewhere") is None
        assert await buildings.violations_at_address(None) is None
    get.assert_not_awaited()


async def test_history_violations_dont_share_a_cache_entry_with_the_profiles_five_years():
    with patch.object(buildings, "socrata_get", new=AsyncMock(side_effect=[[{"violation_date": "2024-01-01"}], []])) as get:
        await buildings.address_specific_violations("1", "N", "STATE")
        got = await buildings.violations_at_address("1 N STATE ST")
    assert get.await_count == 2 and got["violations"] == []


@pytest.mark.parametrize("fact,values,differ", [
    ("year_built", [1920, 1921], False), ("year_built", [1992, 1899], True),
    ("stories", [2, 2.5], False), ("stories", [2, 3], True),
    ("bldg_sqft", [2268, 2400], False), ("bldg_sqft", [2000, 2400], True),
    ("year_built", [1920], False),
])
def test_records_differ_rule(fact, values, differ):
    assert br.differs(fact, values) is differ


def _prop(**kw):
    base = dict(bldg_class="211", pin14="14331030110000", parcel_geometry=None, energy=None, land_sqft=3225,
                year_built=1992, year_built_source="assessor", stories=2.0, stories_source="assessor",
                bldg_sqft=2268, bldg_sqft_source="assessor")
    base.update(kw)
    return SimpleNamespace(**base)


async def test_building_records_list_each_source_beside_the_summary():
    fp = AsyncMock(return_value={"year_built": 1899, "stories": 2, "bldg_sqft": 2268})
    cv = AsyncMock()
    with patch("backend.retrieval.property.building_facts.get_footprint_facts", new=fp), \
            patch("backend.retrieval.property.building_facts.get_commercial_facts", new=cv):
        got = await br.building_records(_prop(), 41.9, -87.7)
    assert got["facts"]["year_built"] == [{"source": "assessor", "value": 1992, "as_of": None},
                                          {"source": "footprint", "value": 1899, "as_of": None}]
    assert got["differ"] == ["year_built"] and got["unanswered"] == []
    cv.assert_not_awaited()  # a 2xx class is the Assessor's residential characteristics' own


async def test_building_records_take_the_commercial_valuations_year_and_name_a_failed_source():
    fp = AsyncMock(side_effect=RuntimeError("503"))
    cv = AsyncMock(return_value={"year_built": 1920, "bldg_sqft": None, "valuation_year": 2024})
    prop = _prop(bldg_class="592", year_built=1920, year_built_source="commercial_valuation", stories=None,
                 stories_source=None, bldg_sqft=None, bldg_sqft_source=None)
    with patch("backend.retrieval.property.building_facts.get_footprint_facts", new=fp), \
            patch("backend.retrieval.property.building_facts.get_commercial_facts", new=cv):
        got = await br.building_records(prop, 41.9, -87.7)
    assert got["facts"]["year_built"] == [{"source": "commercial_valuation", "value": 1920, "as_of": 2024}]
    assert got["unanswered"] == ["footprint"] and got["differ"] == []


async def test_vacant_land_has_no_building_records():
    assert await br.building_records(_prop(bldg_class="100"), 41.9, -87.7) is None
    assert await br.building_records(None, 41.9, -87.7) is None


async def test_a_footprint_spanning_several_lots_gives_no_floor_area():
    """The Profile's own rule (1601 N Milwaukee: a 21,800 sq ft footprint on an 11,951 sq ft lot)."""
    fp = AsyncMock(return_value={"year_built": 1921, "stories": 2, "bldg_sqft": 21800})
    prop = _prop(land_sqft=11951, bldg_sqft=None, bldg_sqft_source=None)
    with patch("backend.retrieval.property.building_facts.get_footprint_facts", new=fp):
        got = await br.building_records(prop, 41.9, -87.7)
    assert got["facts"]["bldg_sqft"] == [] and got["facts"]["stories"][1]["source"] == "footprint"
