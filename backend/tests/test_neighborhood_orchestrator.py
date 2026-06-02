from unittest.mock import AsyncMock, patch

import pytest

from backend.models import DemographicsSummary, TransitAccess, WalkScoreSummary
from backend.retrieval.neighborhood import neighborhood_domain


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_full_assembly(mock_demo, mock_stations, mock_tod):
    mock_demo.return_value = DemographicsSummary(
        community_area=24,
        community_area_name="West Town",
        population=87781,
        median_household_income=82000,
    )
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.3, "lines": ["Blue"]},
        "nearest_metra": {"name": "Ravenswood", "distance_mi": 0.8, "line": "UP-North"},
    }
    mock_tod.return_value = {"tod_eligible": True, "tod_type": "CTA rail"}

    result = await neighborhood_domain(41.93, -87.65, community_area=24, client=AsyncMock())

    assert result.demographics is not None
    assert result.demographics.population == 87781
    assert result.demographics.community_area_name == "West Town"
    assert result.transit is not None
    assert result.transit.nearest_cta_rail == "Damen"
    assert result.transit.cta_rail_distance_mi == 0.3
    assert result.transit.tod_eligible is True


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_demographics_only(mock_demo, mock_stations, mock_tod):
    mock_demo.return_value = DemographicsSummary(
        community_area=24, population=87781,
    )

    result = await neighborhood_domain(0.0, 0.0, community_area=24, client=AsyncMock())

    assert result.demographics is not None
    assert result.demographics.population == 87781
    assert result.transit is None
    mock_stations.assert_not_called()
    mock_tod.assert_not_called()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_transit_only(mock_demo, mock_stations, mock_tod):
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Clark/Lake", "distance_mi": 0.1, "lines": ["Blue", "Brown"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}

    result = await neighborhood_domain(41.88, -87.63, community_area=None, client=AsyncMock())

    assert result.demographics is None
    assert result.transit is not None
    assert result.transit.nearest_cta_rail == "Clark/Lake"
    assert result.transit.tod_eligible is False
    mock_demo.assert_not_called()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_no_ca_no_coords(mock_demo, mock_stations, mock_tod):
    result = await neighborhood_domain(0.0, 0.0, community_area=None, client=AsyncMock())

    assert result.demographics is None
    assert result.transit is None
    mock_demo.assert_not_called()
    mock_stations.assert_not_called()
    mock_tod.assert_not_called()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_demographics_failure_transit_ok(mock_demo, mock_stations, mock_tod):
    mock_demo.side_effect = Exception("Socrata down")
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.3, "lines": ["Blue"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}

    result = await neighborhood_domain(41.93, -87.65, community_area=24, client=AsyncMock())

    assert result.demographics is None
    assert result.transit is not None
    assert result.transit.nearest_cta_rail == "Damen"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_transit_failure_demographics_ok(mock_demo, mock_stations, mock_tod):
    mock_demo.return_value = DemographicsSummary(community_area=24, population=50000)
    mock_stations.side_effect = Exception("File not found")
    mock_tod.side_effect = Exception("ArcGIS down")

    result = await neighborhood_domain(41.93, -87.65, community_area=24, client=AsyncMock())

    assert result.demographics is not None
    assert result.demographics.population == 50000
    assert result.transit is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_all_fail(mock_demo, mock_stations, mock_tod):
    mock_demo.side_effect = Exception("fail")
    mock_stations.side_effect = Exception("fail")
    mock_tod.side_effect = Exception("fail")

    result = await neighborhood_domain(41.93, -87.65, community_area=24, client=AsyncMock())

    assert result.demographics is None
    assert result.transit is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_tod_cta_eligible(mock_demo, mock_stations, mock_tod):
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.2, "lines": ["Blue"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": True, "tod_type": "CTA rail"}

    result = await neighborhood_domain(41.96, -87.68, client=AsyncMock())

    assert result.transit.tod_eligible is True
    assert result.transit.tod_type == "CTA rail"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_tod_metra_eligible(mock_demo, mock_stations, mock_tod):
    mock_stations.return_value = {
        "nearest_cta_rail": None,
        "nearest_metra": {"name": "LaSalle St", "distance_mi": 0.4, "line": "Rock Island"},
    }
    mock_tod.return_value = {"tod_eligible": True, "tod_type": "Metra"}

    result = await neighborhood_domain(41.88, -87.63, client=AsyncMock())

    assert result.transit.tod_eligible is True
    assert result.transit.tod_type == "Metra"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_property_intelligence_skips_demographics(mock_demo, mock_stations, mock_tod):
    mock_demo.return_value = DemographicsSummary(community_area=7, population=65000)
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Armitage", "distance_mi": 0.3, "lines": ["Brown", "Purple"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}

    result = await neighborhood_domain(
        41.92, -87.65, community_area=7, workflow="property_intelligence", client=AsyncMock(),
    )

    mock_demo.assert_not_awaited()
    assert result.demographics is None
    assert result.transit is not None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_general_workflow_fetches_demographics(mock_demo, mock_stations, mock_tod):
    mock_demo.return_value = DemographicsSummary(community_area=7, population=65000)
    mock_stations.return_value = {"nearest_cta_rail": None, "nearest_metra": None}
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}

    result = await neighborhood_domain(
        41.92, -87.65, community_area=7, workflow="general", client=AsyncMock(),
    )

    mock_demo.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.fetch_walkscore")
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_full_assembly_with_walkscore(mock_demo, mock_stations, mock_tod, mock_ws):
    mock_demo.return_value = DemographicsSummary(community_area=24, population=87781)
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.3, "lines": ["Blue"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}
    mock_ws.return_value = WalkScoreSummary(
        walk_score=89, walk_description="Very Walkable",
        transit_score=74, bike_score=82,
    )

    result = await neighborhood_domain(
        41.93, -87.65, community_area=24, address="123 N Damen Ave", client=AsyncMock(),
    )

    assert result.demographics is not None
    assert result.transit is not None
    assert result.walkscore is not None
    assert result.walkscore.walk_score == 89
    mock_ws.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.fetch_walkscore")
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_walkscore_skipped_without_address(mock_demo, mock_stations, mock_tod, mock_ws):
    mock_stations.return_value = {"nearest_cta_rail": None, "nearest_metra": None}
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}

    result = await neighborhood_domain(41.93, -87.65, address=None, client=AsyncMock())

    assert result.walkscore is None
    mock_ws.assert_not_called()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.fetch_walkscore")
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_walkscore_called_for_property_intelligence(mock_demo, mock_stations, mock_tod, mock_ws):
    mock_stations.return_value = {"nearest_cta_rail": None, "nearest_metra": None}
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}
    mock_ws.return_value = WalkScoreSummary(walk_score=85, walk_description="Very Walkable")

    result = await neighborhood_domain(
        41.93, -87.65, address="123 Main St",
        workflow="property_intelligence", client=AsyncMock(),
    )

    assert result.walkscore is not None
    assert result.walkscore.walk_score == 85
    mock_ws.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.fetch_walkscore")
@patch("backend.retrieval.neighborhood.check_tod_eligibility")
@patch("backend.retrieval.neighborhood.find_nearest_stations")
@patch("backend.retrieval.neighborhood.fetch_demographics")
async def test_walkscore_failure_others_ok(mock_demo, mock_stations, mock_tod, mock_ws):
    mock_demo.return_value = DemographicsSummary(community_area=24, population=50000)
    mock_stations.return_value = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.3, "lines": ["Blue"]},
        "nearest_metra": None,
    }
    mock_tod.return_value = {"tod_eligible": False, "tod_type": None}
    mock_ws.side_effect = Exception("Walk Score API down")

    result = await neighborhood_domain(
        41.93, -87.65, community_area=24, address="123 Main St", client=AsyncMock(),
    )

    assert result.demographics is not None
    assert result.transit is not None
    assert result.walkscore is None
