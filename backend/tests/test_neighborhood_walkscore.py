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


@pytest.fixture(autouse=True)
def _mock_api_key(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.walkscore_api_key = "fake-key-for-tests"
    monkeypatch.setattr(
        "backend.retrieval.neighborhood.walkscore.get_settings",
        lambda: mock_settings,
    )


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


# --- live integration tests (real Walk Score API, requires WALKSCORE_API_KEY) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_walkscore_live_lincoln_park():
    """Hit the real Walk Score API for a known walkable Lincoln Park address."""
    result = await fetch_walkscore(41.9307, -87.6411, "443 W Wrightwood Ave, Chicago, IL")
    if result is None:
        pytest.skip("Walk Score API unavailable (quota exceeded or key missing)")
    assert isinstance(result, WalkScoreSummary)
    assert result.walk_score is not None and result.walk_score > 0
    assert result.walk_description is not None
    assert result.transit_score is not None
    assert result.bike_score is not None
    assert result.ws_link is not None and "walkscore.com" in result.ws_link


@pytest.mark.integration
@pytest.mark.asyncio
async def test_walkscore_live_returns_high_scores_for_urban():
    """Lincoln Park is highly walkable — scores should reflect that."""
    result = await fetch_walkscore(41.9307, -87.6411, "443 W Wrightwood Ave, Chicago, IL")
    if result is None:
        pytest.skip("Walk Score API unavailable (quota exceeded or key missing)")
    assert result.walk_score >= 70, f"Expected high Walk Score for Lincoln Park, got {result.walk_score}"
    assert result.bike_score >= 60, f"Expected high Bike Score for Lincoln Park, got {result.bike_score}"
