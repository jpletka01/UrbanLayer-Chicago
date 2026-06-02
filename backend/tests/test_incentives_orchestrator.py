from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval.incentives import incentives_domain


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_full_assembly(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = {
        "tif_name": "Elston/Armstrong",
        "properties": {
            "approval_d": "2005-06-01T00:00:00.000",
            "expiration": "2029-12-31T00:00:00.000",
        },
    }
    mock_ez.return_value = {"zone_name": "Chicago Enterprise Zone"}
    mock_tract.return_value = "17031839100"
    mock_fin.return_value = [
        {"report_year": "2024", "tif_district": "Elston/Armstrong", "public_funds": "500000", "current_year_payments": "300000"},
    ]
    mock_fund.return_value = [
        {
            "report_year": "2024",
            "property_tax_increment_current": "6976459",
            "property_tax_increment_cumulative": "62882259",
            "total_expenditure": "6408288",
            "fund_balance": "28296330",
            "net_income": "990331",
        },
    ]
    mock_oz.return_value = {"tract": "17031839100", "designated": True}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Elston/Armstrong"
    assert result.tif_year_start == 2005
    assert result.tif_end_year == 2029
    assert len(result.tif_financials) == 1
    assert result.tif_property_tax_revenue == 6976459.0
    assert result.tif_cumulative_revenue == 62882259.0
    assert result.tif_fund_balance == 28296330.0
    assert result.tif_annual_expenditure == 6408288.0
    assert len(result.tif_fund_history) == 1
    assert result.in_opportunity_zone is True
    assert result.oz_tract == "17031839100"
    assert result.in_enterprise_zone is True
    assert result.enterprise_zone_name == "Chicago Enterprise Zone"
    assert result.census_tract == "17031839100"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_no_incentives(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = "17031111111"
    mock_fin.return_value = []
    mock_fund.return_value = []
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
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_tif_hit_triggers_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"report_year": "2024", "public_funds": "100000", "current_year_payments": "50000"}]
    mock_fund.return_value = [
        {"report_year": "2024", "property_tax_increment_current": "500000", "total_expenditure": "400000", "fund_balance": "1000000", "net_income": "100000"},
    ]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    mock_fin.assert_called_once()
    mock_fund.assert_called_once()
    assert result.in_tif_district is True
    assert result.tif_property_tax_revenue == 500000.0
    assert result.tif_annual_expenditure == 400000.0
    assert result.tif_fund_balance == 1000000.0


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_no_tif_skips_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    mock_fin.assert_not_called()
    mock_fund.assert_not_called()
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_partial_failure_phase_a(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.side_effect = Exception("TIF boundary load failed")
    mock_ez.return_value = {"zone_name": "Test EZ"}
    mock_tract.return_value = "17031839100"
    mock_fin.return_value = []
    mock_fund.return_value = []
    mock_oz.return_value = {"tract": "17031839100", "designated": True}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is False
    assert result.in_enterprise_zone is True
    assert result.in_opportunity_zone is True


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_all_fail_returns_empty(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
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
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_oz_not_designated(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = None
    mock_ez.return_value = None
    mock_tract.return_value = "17031111111"
    mock_fin.return_value = []
    mock_fund.return_value = []
    mock_oz.return_value = {"tract": "17031111111", "designated": False}

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_opportunity_zone is False
    assert result.oz_tract == "17031111111"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_phase_b_financials_failure(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.side_effect = Exception("Socrata down")
    mock_fund.side_effect = Exception("Socrata down")
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Test TIF"
    assert result.tif_financials == []
    assert result.tif_fund_history == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_business_launch_skips_tif_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {"approval_d": "2010-01-01T00:00:00.000"}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"report_year": "2024", "public_funds": "5000000"}]
    mock_fund.return_value = [{"report_year": "2024", "property_tax_increment_current": "500000"}]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, workflow="business_launch", client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_name == "Test TIF"
    mock_fin.assert_not_awaited()
    mock_fund.assert_not_awaited()
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.check_opportunity_zone")
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.fetch_tif_financials")
@patch("backend.retrieval.incentives.resolve_census_tract")
@patch("backend.retrieval.incentives.check_enterprise_zone")
@patch("backend.retrieval.incentives.check_tif")
async def test_general_workflow_fetches_tif_financials(mock_tif, mock_ez, mock_tract, mock_fin, mock_fund, mock_oz):
    mock_tif.return_value = {"tif_name": "Test TIF", "properties": {}}
    mock_ez.return_value = None
    mock_tract.return_value = None
    mock_fin.return_value = [{"report_year": "2024", "public_funds": "5000000"}]
    mock_fund.return_value = [{"report_year": "2024", "property_tax_increment_current": "500000"}]
    mock_oz.return_value = None

    result = await incentives_domain(41.93, -87.65, workflow="general", client=AsyncMock())

    assert result.in_tif_district is True
    mock_fin.assert_awaited_once()
    mock_fund.assert_awaited_once()
    assert len(result.tif_financials) == 1


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.tif_districts_by_community_area")
async def test_community_area_only_path(mock_tif_ca, mock_fund):
    mock_tif_ca.return_value = [
        {"tif_name": "Fullerton/Milwaukee", "start_year": 2000, "end_year": 2027, "type": "Existing", "tif_ref": "T-087"},
        {"tif_name": "Pulaski Corridor", "start_year": 1999, "end_year": 2035, "type": "Existing", "tif_ref": "T-075"},
    ]
    mock_fund.return_value = [
        {"report_year": "2024", "property_tax_increment_current": "21911518", "fund_balance": "63162041", "total_expenditure": "24619936"},
    ]

    result = await incentives_domain(ca=22, client=AsyncMock())

    assert result.in_tif_district is True
    assert result.tif_districts_in_area is not None
    assert len(result.tif_districts_in_area) == 2
    assert result.tif_districts_in_area[0]["property_tax_revenue"] == 21911518.0
    assert result.tif_districts_in_area[0]["fund_balance"] == 63162041.0
    assert result.tif_name is None
    assert result.tif_financials == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.fetch_tif_fund_analysis")
@patch("backend.retrieval.incentives.tif_districts_by_community_area")
async def test_community_area_no_tifs(mock_tif_ca, mock_fund):
    mock_tif_ca.return_value = []

    result = await incentives_domain(ca=99, client=AsyncMock())

    assert result.in_tif_district is False
    assert result.tif_districts_in_area is None
    mock_fund.assert_not_called()
