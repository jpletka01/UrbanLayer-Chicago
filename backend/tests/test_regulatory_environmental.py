from unittest.mock import AsyncMock

import httpx
import pytest

from backend.retrieval.regulatory.environmental import EPA_BROWNFIELDS_URL, query_brownfield_sites


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", EPA_BROWNFIELDS_URL),
    )


@pytest.mark.asyncio
async def test_returns_brownfield_sites():
    resp_data = {
        "features": [
            {
                "attributes": {
                    "SITE_NAME": "Former Gas Station",
                    "REGISTRY_ID": "110012345",
                    "INTEREST_TYPE": "BROWNFIELDS SITE",
                    "LATITUDE83": 41.931,
                    "LONGITUDE83": -87.651,
                }
            },
            {
                "attributes": {
                    "SITE_NAME": "Industrial Yard",
                    "REGISTRY_ID": "110067890",
                    "INTEREST_TYPE": "BROWNFIELDS SITE",
                    "LATITUDE83": 41.932,
                    "LONGITUDE83": -87.652,
                }
            },
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_brownfield_sites(41.93, -87.65, client=client)

    assert len(result) == 2
    assert result[0]["site_name"] == "Former Gas Station"
    assert result[0]["epa_id"] == "110012345"
    assert result[1]["site_name"] == "Industrial Yard"


@pytest.mark.asyncio
async def test_returns_empty_when_no_sites():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    result = await query_brownfield_sites(41.93, -87.65, client=client)
    assert result == []


@pytest.mark.asyncio
async def test_skips_features_without_site_name():
    resp_data = {
        "features": [
            {"attributes": {"REGISTRY_ID": "123", "INTEREST_TYPE": "X"}},
            {"attributes": {"SITE_NAME": "Real Site", "REGISTRY_ID": "456"}},
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_brownfield_sites(41.93, -87.65, client=client)
    assert len(result) == 1
    assert result[0]["site_name"] == "Real Site"


@pytest.mark.asyncio
async def test_handles_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_mock_response({"error": "fail"}, status_code=500)
    )

    result = await query_brownfield_sites(41.93, -87.65, client=client)
    assert result == []


@pytest.mark.asyncio
async def test_handles_connection_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    result = await query_brownfield_sites(41.93, -87.65, client=client)
    assert result == []


@pytest.mark.asyncio
async def test_sends_distance_buffer_params():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_brownfield_sites(41.93, -87.65, radius_meters=500, client=client)

    params = client.get.call_args.kwargs.get("params") or client.get.call_args[1].get("params")
    assert params["distance"] == "500"
    assert params["units"] == "esriSRUnit_Meter"
    assert params["resultRecordCount"] == "10"
