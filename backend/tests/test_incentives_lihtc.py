from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.retrieval.incentives.lihtc import check_qct


@pytest.mark.asyncio
async def test_check_qct_designated():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {"GEOID": "17031829402", "NAME": "Census Tract 8294.02"}}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_qct("17031829402", client=mock_client)
    assert result is not None
    assert result["designated"] is True
    assert result["tract"] == "17031829402"
    assert result["name"] == "Census Tract 8294.02"


@pytest.mark.asyncio
async def test_check_qct_not_designated():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"features": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await check_qct("17031839100", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_qct_error():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("HUD down")

    result = await check_qct("17031829402", client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_qct_caches_result():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"attributes": {"GEOID": "17031999999", "NAME": "Test Tract"}}],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result1 = await check_qct("17031999999", client=mock_client)
    result2 = await check_qct("17031999999", client=mock_client)
    assert result1 == result2
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_check_qct_caches_not_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"features": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result1 = await check_qct("17031000001", client=mock_client)
    result2 = await check_qct("17031000001", client=mock_client)
    assert result1 is None
    assert result2 is None
    assert mock_client.get.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_qct_designated_live():
    result = await check_qct("17031829402")
    assert result is not None
    assert result["designated"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_qct_not_designated_live():
    result = await check_qct("17031839100")
    assert result is None
