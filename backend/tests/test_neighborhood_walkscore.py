from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models import WalkScoreSummary
from backend.retrieval.neighborhood.walkscore import _cache, fetch_walkscore

MOCK_SUCCESS = {
    "status": 1,
    "walkscore": 89,
    "description": "Very Walkable",
    "transit": {"score": 74, "description": "Excellent Transit", "summary": "Some transit details"},
    "bike": {"score": 82, "description": "Very Bikeable"},
    "ws_link": "https://www.walkscore.com/score/123-main-st",
    "snapped_lat": 41.9123,
    "snapped_lon": -87.6543,
}


@pytest.fixture(autouse=True)
def _clear_cache():
    _cache._store.clear()


def _mock_response(data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_fetch_success():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(MOCK_SUCCESS)

    result = await fetch_walkscore(41.9123, -87.6543, "123 Main St", client=client)

    assert isinstance(result, WalkScoreSummary)
    assert result.walk_score == 89
    assert result.walk_description == "Very Walkable"
    assert result.transit_score == 74
    assert result.transit_description == "Excellent Transit"
    assert result.bike_score == 82
    assert result.bike_description == "Very Bikeable"
    assert result.ws_link == "https://www.walkscore.com/score/123-main-st"
    client.get.assert_called_once()


@pytest.mark.asyncio
async def test_cached_result():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(MOCK_SUCCESS)

    r1 = await fetch_walkscore(41.9123, -87.6543, "123 Main St", client=client)
    r2 = await fetch_walkscore(41.9123, -87.6543, "123 Main St", client=client)

    assert r1 is not None
    assert r2 is not None
    assert r1.walk_score == r2.walk_score
    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_not_found_cached():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response({"status": 30})

    r1 = await fetch_walkscore(41.0, -87.0, "Bad Address", client=client)
    r2 = await fetch_walkscore(41.0, -87.0, "Bad Address", client=client)

    assert r1 is None
    assert r2 is None
    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_api_down():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ConnectError("Connection refused")

    result = await fetch_walkscore(41.9, -87.6, "123 Main St", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_quota_exceeded():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response({"status": 41})

    result = await fetch_walkscore(41.9, -87.6, "123 Main St", client=client)
    assert result is None
    assert len(_cache._store) == 0


@pytest.mark.asyncio
async def test_bad_key():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response({"status": 40})

    result = await fetch_walkscore(41.9, -87.6, "123 Main St", client=client)
    assert result is None
    assert len(_cache._store) == 1


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.walkscore.get_settings")
async def test_no_api_key_configured(mock_settings):
    mock_settings.return_value = MagicMock(walkscore_api_key="")
    client = AsyncMock(spec=httpx.AsyncClient)

    result = await fetch_walkscore(41.9, -87.6, "123 Main St", client=client)
    assert result is None
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_cache_key_rounding():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(MOCK_SUCCESS)

    await fetch_walkscore(41.91231, -87.65432, "123 Main St", client=client)
    await fetch_walkscore(41.91234, -87.65435, "123 Main St", client=client)

    assert client.get.call_count == 1
