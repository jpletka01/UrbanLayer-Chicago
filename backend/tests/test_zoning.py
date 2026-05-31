import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.retrieval.zoning import ZONING_MAP_URL, ZONING_QUERY_URL, lookup_zoning, zoning_polygons_for_map


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", ZONING_QUERY_URL),
    )


@pytest.mark.asyncio
async def test_lookup_returns_zone_class():
    resp_data = {
        "features": [
            {"attributes": {"ZONE_CLASS": "B3-2", "ZONE_TYPE": 1, "ORDINANCE_NUM": "12345"}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await lookup_zoning(41.9270, -87.6984, client=client)

    assert result is not None
    assert result["zone_class"] == "B3-2"
    assert result["zone_type"] == 1
    assert result["ordinance_num"] == "12345"

    call_args = client.get.call_args
    assert ZONING_QUERY_URL in str(call_args)


@pytest.mark.asyncio
async def test_lookup_returns_none_for_empty_features():
    resp_data = {"features": []}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await lookup_zoning(41.9270, -87.6984, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_lookup_returns_none_for_missing_zone_class():
    resp_data = {
        "features": [{"attributes": {"ZONE_TYPE": "B"}}]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await lookup_zoning(41.9270, -87.6984, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_lookup_handles_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_mock_response({}, status_code=500)
    )

    result = await lookup_zoning(41.9270, -87.6984, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_lookup_handles_exception():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    result = await lookup_zoning(41.9270, -87.6984, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_lookup_passes_correct_params():
    resp_data = {
        "features": [
            {"attributes": {"ZONE_CLASS": "RS-3", "ZONE_TYPE": 2, "ORDINANCE_NUM": None}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    await lookup_zoning(41.9270, -87.6984, client=client)

    params = client.get.call_args[1].get("params", client.get.call_args[0][1] if len(client.get.call_args[0]) > 1 else {})
    if not params:
        params = client.get.call_args.kwargs.get("params", {})
    assert params["geometryType"] == "esriGeometryPoint"
    assert "-87.6984,41.927" in params["geometry"] or params["geometry"] == "-87.6984,41.927"


def test_zoning_map_url_is_correct():
    assert "gisapps.chicago.gov/ZoningMapWeb" in ZONING_MAP_URL


# --- zoning_polygons_for_map tests ---

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"ZONE_CLASS": "RS-3", "ZONE_TYPE": 2, "ORDINANCE_NUM": None},
            "geometry": {"type": "Polygon", "coordinates": [[[-87.65, 41.93], [-87.64, 41.93], [-87.64, 41.94], [-87.65, 41.93]]]},
        },
        {
            "type": "Feature",
            "properties": {"ZONE_CLASS": "B2-3", "ZONE_TYPE": 1, "ORDINANCE_NUM": "12345"},
            "geometry": {"type": "Polygon", "coordinates": [[[-87.66, 41.92], [-87.65, 41.92], [-87.65, 41.93], [-87.66, 41.92]]]},
        },
    ],
}


@pytest.mark.asyncio
@patch("backend.retrieval.zoning.community_area_bounds", return_value=(41.91, -87.66, 41.95, -87.63))
async def test_polygons_returns_geojson(mock_bounds):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(SAMPLE_GEOJSON))

    result = await zoning_polygons_for_map(7, client=client)

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2
    assert result["features"][0]["properties"]["ZONE_CLASS"] == "RS-3"

    params = client.get.call_args.kwargs.get("params", {})
    assert params["geometryType"] == "esriGeometryEnvelope"
    assert params["returnGeometry"] == "true"
    assert params["f"] == "geojson"


@pytest.mark.asyncio
@patch("backend.retrieval.zoning.community_area_bounds", return_value=(41.91, -87.66, 41.95, -87.63))
async def test_polygons_returns_empty_on_http_error(mock_bounds):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({}, status_code=500))

    result = await zoning_polygons_for_map(7, client=client)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 0


@pytest.mark.asyncio
@patch("backend.retrieval.zoning.community_area_bounds", return_value=(41.91, -87.66, 41.95, -87.63))
async def test_polygons_returns_empty_on_connection_error(mock_bounds):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    result = await zoning_polygons_for_map(7, client=client)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 0


@pytest.mark.asyncio
@patch("backend.retrieval.zoning.community_area_bounds", return_value=None)
async def test_polygons_returns_empty_for_unknown_ca(mock_bounds):
    result = await zoning_polygons_for_map(999)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 0


@pytest.mark.asyncio
@patch("backend.retrieval.zoning.community_area_bounds", return_value=(41.91, -87.66, 41.95, -87.63))
async def test_polygons_passes_correct_envelope(mock_bounds):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(SAMPLE_GEOJSON))

    await zoning_polygons_for_map(7, client=client)

    params = client.get.call_args.kwargs.get("params", {})
    assert params["geometry"] == "-87.66,41.91,-87.63,41.95"
    assert params["outSR"] == "4326"
