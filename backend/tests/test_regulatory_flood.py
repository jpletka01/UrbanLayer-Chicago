from unittest.mock import AsyncMock

import httpx
import pytest

from backend.retrieval.regulatory.flood import FEMA_NFHL_URL, query_flood_zone


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", FEMA_NFHL_URL),
    )


@pytest.mark.asyncio
async def test_returns_flood_zone_data():
    resp_data = {
        "features": [
            {"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_flood_zone(41.93, -87.65, client=client)

    assert result is not None
    assert result["fld_zone"] == "AE"
    assert result["zone_subty"] == "FLOODWAY"
    assert result["sfha_tf"] == "T"


@pytest.mark.asyncio
async def test_returns_none_when_not_in_flood_zone():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_for_missing_fld_zone():
    resp_data = {"features": [{"attributes": {"ZONE_SUBTY": "X", "SFHA_TF": "F"}}]}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_handles_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_mock_response({"error": "fail"}, status_code=500)
    )

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_handles_connection_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_sends_correct_params():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_flood_zone(41.93, -87.65, client=client)

    params = client.get.call_args.kwargs.get("params") or client.get.call_args[1].get("params")
    assert params["outFields"] == "FLD_ZONE,ZONE_SUBTY,SFHA_TF"
    assert params["geometry"] == "-87.65,41.93"
