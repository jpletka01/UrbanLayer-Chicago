from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval.regulatory import regulatory_domain


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_assembles_full_summary(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = [
        (5, {"NAME": "Gold Coast", "ORDINANCE": "2005-100"}),
        (20, {"AREA_NAME": "Near North ARO"}),
    ]
    mock_flood.return_value = {"fld_zone": "AE", "zone_subty": "FLOODWAY", "sfha_tf": "T"}
    mock_brownfield.return_value = [{"site_name": "Old Factory", "epa_id": "123"}]

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert len(result.overlays) == 2
    assert result.in_landmark_district is True
    assert result.in_aro_zone is True
    assert result.flood_zone == "AE"
    assert result.in_special_flood_hazard is True
    assert len(result.brownfield_sites) == 1
    assert result.brownfield_sites[0]["site_name"] == "Old Factory"


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_boolean_flags_mapped_correctly(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = [
        (2, {"PD_NAME": "Lincoln Yards"}),
        (3, {}),
        (4, {"NAME": "Milwaukee Ave"}),
        (7, {"NAME": "Wrigley Building"}),
        (13, {"NAME": "Damen CTA"}),
        (17, {}),
    ]
    mock_flood.return_value = None
    mock_brownfield.return_value = []

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_planned_development is True
    assert result.in_lakefront_protection is True
    assert result.on_pedestrian_street is True
    assert result.is_landmark_building is True
    assert result.in_tod_area is True
    assert result.in_adu_area is True
    assert result.in_landmark_district is False
    assert result.in_historic_district is False
    assert result.flood_zone is None
    assert result.in_special_flood_hazard is False


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_handles_partial_failure(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.side_effect = Exception("MapServer down")
    mock_flood.return_value = {"fld_zone": "X", "zone_subty": None, "sfha_tf": "F"}
    mock_brownfield.return_value = [{"site_name": "Site A", "epa_id": "1"}]

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert len(result.overlays) == 0
    assert result.flood_zone == "X"
    assert result.in_special_flood_hazard is False
    assert len(result.brownfield_sites) == 1


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_returns_empty_when_all_fail(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.side_effect = Exception("fail")
    mock_flood.side_effect = Exception("fail")
    mock_brownfield.side_effect = Exception("fail")

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert len(result.overlays) == 0
    assert result.flood_zone is None
    assert result.in_special_flood_hazard is False
    assert len(result.brownfield_sites) == 0


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_ssa_name_extraction(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = [
        (23, {"SSA_NAME": "Andersonville SSA #22", "SSA": "22"}),
    ]
    mock_flood.return_value = None
    mock_brownfield.return_value = []

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_ssa is True
    assert result.ssa_name == "Andersonville SSA #22"


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_tod_from_metra(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = [
        (24, {"NAME": "Western Ave Metra"}),
    ]
    mock_flood.return_value = None
    mock_brownfield.return_value = []

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert result.in_tod_area is True


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_sfha_false_for_non_t_value(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = []
    mock_flood.return_value = {"fld_zone": "X", "zone_subty": None, "sfha_tf": "F"}
    mock_brownfield.return_value = []

    result = await regulatory_domain(41.93, -87.65, client=AsyncMock())

    assert result.flood_zone == "X"
    assert result.in_special_flood_hazard is False


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_business_launch_skips_brownfield(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = [(4, {"NAME": "Milwaukee Ave"})]
    mock_flood.return_value = None
    mock_brownfield.return_value = [{"site_name": "Should Not Be Called"}]

    result = await regulatory_domain(41.93, -87.65, workflow="business_launch", client=AsyncMock())

    assert result.on_pedestrian_street is True
    mock_brownfield.assert_not_awaited()
    assert result.brownfield_sites == []


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites")
@patch("backend.retrieval.regulatory.query_flood_zone")
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_general_workflow_includes_brownfield(mock_overlays, mock_flood, mock_brownfield):
    mock_overlays.return_value = []
    mock_flood.return_value = None
    mock_brownfield.return_value = [{"site_name": "Old Plant"}]

    result = await regulatory_domain(41.93, -87.65, workflow="general", client=AsyncMock())

    mock_brownfield.assert_awaited_once()
    assert len(result.brownfield_sites) == 1
