from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.retrieval.incentives.nmtc import check_nmtc


@pytest.mark.asyncio
async def test_check_nmtc_qualifying():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {
            "GEOID": "17031540101",
            "NMTC_LIC_INC": 1,
            "SEVERE_DISTRESS": 0,
            "DEEP_DISTRESS": 0,
            "POV_RATE_16_20_ACS": 32.5,
        }}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_nmtc("17031540101", client=mock_client)
    assert result is not None
    assert result["qualifying"] is True
    assert result["tract"] == "17031540101"
    assert result["severe_distress"] is False
    assert result["poverty_rate"] == 32.5


@pytest.mark.asyncio
async def test_check_nmtc_not_qualifying():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {
            "GEOID": "17031839100",
            "NMTC_LIC_INC": 0,
            "SEVERE_DISTRESS": 0,
            "DEEP_DISTRESS": 0,
            "POV_RATE_16_20_ACS": 10.5,
        }}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_nmtc("17031839100", client=mock_client)
    assert result is not None
    assert result["qualifying"] is False


@pytest.mark.asyncio
async def test_check_nmtc_severe_distress():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {
            "GEOID": "17031540101",
            "NMTC_LIC_INC": 1,
            "SEVERE_DISTRESS": 1,
            "DEEP_DISTRESS": 1,
            "POV_RATE_16_20_ACS": 45.0,
        }}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_nmtc("17031540101", client=mock_client)
    assert result is not None
    assert result["qualifying"] is True
    assert result["severe_distress"] is True
    assert result["deep_distress"] is True


@pytest.mark.asyncio
async def test_check_nmtc_not_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"features": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_nmtc("99999999999", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_nmtc_error():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("HUD down")

    result = await check_nmtc("17031540101", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_nmtc_caches_result():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {
            "GEOID": "17031888888",
            "NMTC_LIC_INC": 1,
            "SEVERE_DISTRESS": 0,
            "DEEP_DISTRESS": 0,
            "POV_RATE_16_20_ACS": 25.0,
        }}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result1 = await check_nmtc("17031888888", client=mock_client)
    result2 = await check_nmtc("17031888888", client=mock_client)
    assert result1 == result2
    assert mock_client.get.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_nmtc_live():
    result = await check_nmtc("17031839100")
    assert result is not None
    assert isinstance(result["qualifying"], bool)
    assert result["tract"] == "17031839100"
