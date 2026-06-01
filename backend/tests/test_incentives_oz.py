from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.retrieval.incentives.opportunity_zones import (
    check_opportunity_zone,
    resolve_census_tract,
)


@pytest.mark.asyncio
async def test_resolve_census_tract_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"block_fips": "170318391001234"}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await resolve_census_tract(41.93, -87.65, client=mock_client)
    assert result == "17031839100"


@pytest.mark.asyncio
async def test_resolve_census_tract_no_results():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"results": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await resolve_census_tract(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_census_tract_error():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("FCC down")

    result = await resolve_census_tract(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_census_tract_short_fips():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"results": [{"block_fips": "12345"}]}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await resolve_census_tract(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_oz_designated():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {"GEOID": "17031839100", "DESIGNATED": 1}}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_opportunity_zone("17031839100", client=mock_client)
    assert result is not None
    assert result["designated"] is True
    assert result["tract"] == "17031839100"


@pytest.mark.asyncio
async def test_check_oz_not_designated():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"features": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_opportunity_zone("17031111111", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_oz_error():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("HUD down")

    result = await check_opportunity_zone("17031839100", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_tract_params():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"block_fips": "170310101001000"}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    await resolve_census_tract(41.93, -87.65, client=mock_client)

    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["lat"] == "41.93"
    assert params["lon"] == "-87.65"
    assert params["format"] == "json"
