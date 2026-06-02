from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.retrieval.incentives import enterprise_zones as ez


@pytest.fixture(autouse=True)
def _reset_cache():
    ez._ez_boundaries = None
    yield
    ez._ez_boundaries = None


def _make_geojson(features):
    return {"type": "FeatureCollection", "features": features}


def _make_feature(name, coords):
    lon, lat = coords
    d = 0.01
    return {
        "type": "Feature",
        "properties": {"zone_name": name},
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
@patch("backend.retrieval.incentives.enterprise_zones.httpx.AsyncClient")
async def test_check_ez_hit(mock_client_cls):
    geojson = _make_geojson([_make_feature("Chicago Enterprise Zone", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)
    assert result is not None
    assert result["zone_name"] == "Chicago Enterprise Zone"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.enterprise_zones.httpx.AsyncClient")
async def test_check_ez_miss(mock_client_cls):
    geojson = _make_geojson([_make_feature("Chicago Enterprise Zone", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await ez.check_enterprise_zone(42.10, -87.80, client=mock_client)
    assert result is None


@pytest.mark.asyncio
async def test_check_ez_load_failure():
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection refused")

    result = await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.enterprise_zones.httpx.AsyncClient")
async def test_ez_boundaries_cached(mock_client_cls):
    geojson = _make_geojson([_make_feature("Test EZ", (-87.65, 41.93))])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)
    await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.enterprise_zones.httpx.AsyncClient")
async def test_ez_name_fallback(mock_client_cls):
    feat = {
        "type": "Feature",
        "properties": {"name": "Fallback Name"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-87.66, 41.92], [-87.64, 41.92],
                [-87.64, 41.94], [-87.66, 41.94],
                [-87.66, 41.92],
            ]],
        },
    }
    geojson = _make_geojson([feat])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)
    assert result is not None
    assert result["zone_name"] == "Fallback Name"


# --- live integration tests (real Socrata Enterprise Zone boundaries, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ez_boundaries_load_live():
    """Verify Enterprise Zone GeoJSON loads from Socrata.

    Note: The Socrata dataset may return features with null geometry,
    in which case zero boundaries are loaded. This is a data-quality
    issue on the Socrata side, not a code bug.
    """
    ez._ez_boundaries = None  # ensure fresh fetch
    boundaries = await ez._load_ez_boundaries()
    assert isinstance(boundaries, list)
    if len(boundaries) == 0:
        pytest.skip("EZ dataset returned no valid geometries (Socrata data-quality issue)")
    name, props, poly, geom = boundaries[0]
    assert isinstance(name, str) and name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_ez_live_not_in_zone():
    """Lincoln Park (affluent area) is unlikely to be in an Enterprise Zone."""
    ez._ez_boundaries = None
    result = await ez.check_enterprise_zone(41.9307, -87.6411)
    assert result is None
