from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.retrieval.incentives import tif


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset module-level boundary cache between tests."""
    tif._tif_boundaries = None
    yield
    tif._tif_boundaries = None


def _make_geojson(features):
    return {"type": "FeatureCollection", "features": features}


def _make_feature(name, coords):
    """Build a simple polygon feature (a small square)."""
    lon, lat = coords
    d = 0.01
    return {
        "type": "Feature",
        "properties": {"tif_name": name, "start_year": "2005", "end_year": "2029"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon - d, lat - d], [lon + d, lat - d],
                [lon + d, lat + d], [lon - d, lat + d],
                [lon - d, lat - d],
            ]],
        },
    }


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_check_tif_hit(mock_client_cls):
    geojson = _make_geojson([_make_feature("Elston/Armstrong", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await tif.check_tif(41.93, -87.65, client=mock_client)

    assert result is not None
    assert result["tif_name"] == "Elston/Armstrong"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_check_tif_miss(mock_client_cls):
    geojson = _make_geojson([_make_feature("Elston/Armstrong", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await tif.check_tif(42.10, -87.80, client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_tif_load_failure():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection refused")

    result = await tif.check_tif(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.socrata_get")
async def test_fetch_financials_success(mock_socrata):
    mock_socrata.return_value = [
        {"year": "2023", "revenue": "500000", "expenditure": "300000"},
        {"year": "2022", "revenue": "450000", "expenditure": "250000"},
    ]
    result = await tif.fetch_tif_financials("Elston/Armstrong", client=AsyncMock())
    assert len(result) == 2
    assert result[0]["year"] == "2023"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.socrata_get")
async def test_fetch_financials_error(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata down")
    result = await tif.fetch_tif_financials("Elston/Armstrong", client=AsyncMock())
    assert result == []


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_boundaries_cached_after_first_load(mock_client_cls):
    geojson = _make_geojson([_make_feature("Test TIF", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    await tif.check_tif(41.93, -87.65, client=mock_client)
    await tif.check_tif(41.93, -87.65, client=mock_client)

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_tif_properties_passed_through(mock_client_cls):
    geojson = _make_geojson([_make_feature("Western Ave", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await tif.check_tif(41.93, -87.65, client=mock_client)
    assert result is not None
    assert "properties" in result
    assert result["properties"]["start_year"] == "2005"
