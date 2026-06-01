from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval.incentives import incentives_domain


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_full_assembly(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = {
        "tif_name": "Elston/Armstrong",
        "properties": {"start_year": "2005", "end_year": "2029"},
    }
    mock_ez.return_value = {"zone_name": "Chicago Enterprise Zone"}
    mock_tract.return_value = "17031839100"
    mock_fin.return_value = [
        {"year": "2023", "revenue": "500000", "expenditure": "300000"},
    ]
    mock_oz.return_value = {"tract": "17031839100", "designated": True}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Elston/Armstrong"
    assert result.tif_year_start == 2005
    assert result.tif_end_year == 2029
    assert len(result.tif_financials) == 1
    assert result.in_opportunity_zone is True
    assert result.oz_tract == "17031839100"
    assert result.in_enterprise_zone is True
    assert result.enterprise_zone_name == "Chicago Enterprise Zone"
    assert result.census_tract == "17031839100"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_no_incentives(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = "17031111111"
    mock_fin.return_value = []
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is False
    assert result.tif_name is None
    assert result.tif_financials == []
    assert result.in_opportunity_zone is False
    assert result.in_enterprise_zone is False
    assert result.census_tract == "17031111111"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_tif_hit_triggers_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"year": "2023", "revenue": "100000"}]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    mock_fin.assert_called_once()
    assert result.in_tif_district is True
    assert result.tif_total_revenue == 100000.0


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_no_tif_skips_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    mock_fin.assert_not_called()
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_partial_failure_phase_a(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.side_effect = Exception("TIF boundary load failed")
    mock_ez.return_value = {"zone_name": "Test EZ"}
    mock_tract.return_value = "17031839100"
    mock_fin.return_value = []
    mock_oz.return_value = {"tract": "17031839100", "designated": True}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is False
    assert result.in_enterprise_zone is True
    assert result.in_opportunity_zone is True


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_all_fail_returns_empty(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.side_effect = Exception("fail")
    mock_ez.side_effect = Exception("fail")
    mock_tract.side_effect = Exception("fail")

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is False
    assert result.in_enterprise_zone is False
    assert result.in_opportunity_zone is False
    assert result.census_tract is None


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_oz_not_designated(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = "17031111111"
    mock_fin.return_value = []
    mock_oz.return_value = {"tract": "17031111111", "designated": False}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_opportunity_zone is False
    assert result.oz_tract == "17031111111"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_phase_b_financials_failure(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.side_effect = Exception("Socrata down")
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Test TIF"
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_business_launch_skips_tif_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {"start_year": "2010"}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"year": "2023", "revenue": "5000000"}]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, workflow="business_launch", client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Test TIF"
    mock_fin.assert_not_awaited()
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_general_workflow_fetches_tif_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"year": "2023", "revenue": "5000000"}]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, workflow="general", client=AsyncMock())

    assert result.in_tif_district is True
    mock_fin.assert_awaited_once()
    assert len(result.tif_financials) == 1
