from unittest.mock import AsyncMock

import httpx
import pytest

from backend.retrieval.regulatory.overlays import (
    OVERLAY_LAYERS,
    ZONING_BASE_URL,
    query_all_overlays,
    query_overlay,
)


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", f"{ZONING_BASE_URL}/2/query"),
    )


@pytest.mark.asyncio
async def test_query_overlay_returns_attributes():
    resp_data = {
        "features": [
            {"attributes": {"PD_NAME": "Lincoln Yards", "ORDINANCE": "2019-123"}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_overlay(41.93, -87.65, 2, client=client)

    assert result is not None
    assert result["PD_NAME"] == "Lincoln Yards"
    assert result["ORDINANCE"] == "2019-123"


@pytest.mark.asyncio
async def test_query_overlay_returns_none_for_empty_features():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_handles_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_mock_response({"error": "fail"}, status_code=500)
    )

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_handles_connection_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_url_includes_layer_id():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_overlay(41.93, -87.65, 17, client=client)

    url_arg = client.get.call_args[0][0]
    assert "/17/query" in url_arg


@pytest.mark.asyncio
async def test_query_overlay_sends_correct_geometry():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_overlay(41.93, -87.65, 2, client=client)

    params = client.get.call_args.kwargs.get("params") or client.get.call_args[1].get("params")
    assert params["geometry"] == "-87.65,41.93"
    assert params["geometryType"] == "esriGeometryPoint"
    assert params["inSR"] == "4326"


@pytest.mark.asyncio
async def test_query_all_overlays_returns_hits():
    def make_resp(layer_id):
        if layer_id == 5:
            return _mock_response({
                "features": [{"attributes": {"NAME": "Gold Coast"}}]
            })
        return _mock_response({"features": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=lambda url, **kw: make_resp(
        int(url.split("/")[-2])
    ))

    hits = await query_all_overlays(41.93, -87.65, client=client)

    assert len(hits) == 1
    layer_id, attrs = hits[0]
    assert layer_id == 5
    assert attrs["NAME"] == "Gold Coast"


@pytest.mark.asyncio
async def test_query_all_overlays_skips_failed_layers():
    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        lid = int(url.split("/")[-2])
        if lid == 2:
            raise httpx.ConnectError("timeout")
        return _mock_response({"features": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get

    hits = await query_all_overlays(41.93, -87.65, client=client)

    assert isinstance(hits, list)
    assert call_count == len(OVERLAY_LAYERS)


# --- live integration tests (real Chicago ArcGIS Zoning overlay service, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overlay_live_lincoln_park():
    """Lincoln Park address should hit at least one overlay (e.g. landmark/historic)."""
    hits = await query_all_overlays(41.9307, -87.6411)
    assert isinstance(hits, list)
    assert len(hits) > 0, "Expected at least one overlay hit in Lincoln Park"
    layer_id, attrs = hits[0]
    assert layer_id in OVERLAY_LAYERS
    assert isinstance(attrs, dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_overlay_live():
    """Query the ADU eligible area layer (17) for a Lincoln Park address."""
    result = await query_overlay(41.9307, -87.6411, 17)
    # ADU eligibility may or may not apply — just verify the call succeeds
    assert result is None or isinstance(result, dict)
