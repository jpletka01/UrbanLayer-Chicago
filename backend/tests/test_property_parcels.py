"""Tests for Cook County GIS parcel lookup."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from backend.retrieval.property.parcels import lookup_parcel, PARCEL_QUERY_URL


def _mock_response(features, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"features": features}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_parcel_returns_pin_and_attributes():
    client = AsyncMock()
    client.get.return_value = _mock_response([{
        "attributes": {
            "PIN14": "14241020170000",
            "BLDGClass": "2-11",
            "BldgSqft": 2400,
            "LandSqft": 3200,
            "TotalValue": 350000,
            "Address": "443 W WRIGHTWOOD AVE",
        }
    }])
    result = await lookup_parcel(41.9307, -87.6411, client=client)
    assert result is not None
    assert result["pin14"] == "14241020170000"
    assert result["bldg_class"] == "2-11"
    assert result["bldg_sqft"] == 2400
    assert result["land_sqft"] == 3200
    assert result["address"] == "443 W WRIGHTWOOD AVE"


@pytest.mark.asyncio
async def test_parcel_returns_none_for_empty_features():
    client = AsyncMock()
    client.get.return_value = _mock_response([])
    result = await lookup_parcel(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_handles_http_error():
    client = AsyncMock()
    client.get.return_value = _mock_response([], status_code=500)
    result = await lookup_parcel(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_handles_connection_error():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("connection refused")
    result = await lookup_parcel(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_sends_correct_geometry():
    """Verify lon comes before lat in the geometry param."""
    client = AsyncMock()
    client.get.return_value = _mock_response([])
    await lookup_parcel(41.93, -87.64, client=client)
    call_args = client.get.call_args
    params = call_args.kwargs.get("params") or call_args[1].get("params")
    assert params["geometry"] == "-87.64,41.93"


@pytest.mark.asyncio
async def test_pin14_zero_padded():
    """Short PINs should be zero-padded to 14 digits."""
    client = AsyncMock()
    client.get.return_value = _mock_response([{
        "attributes": {"PIN14": "1424102017", "Address": "TEST"}
    }])
    result = await lookup_parcel(41.93, -87.64, client=client)
    assert result is not None
    assert result["pin14"] == "00001424102017"
    assert len(result["pin14"]) == 14


@pytest.mark.asyncio
async def test_pin_with_dashes_stripped():
    """PINs with dashes should have them stripped."""
    client = AsyncMock()
    client.get.return_value = _mock_response([{
        "attributes": {"PIN14": "14-24-102-017-0000", "Address": "TEST"}
    }])
    result = await lookup_parcel(41.93, -87.64, client=client)
    assert result is not None
    assert result["pin14"] == "14241020170000"
    assert "-" not in result["pin14"]
