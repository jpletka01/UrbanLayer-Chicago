import json
from pathlib import Path
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
async def test_check_ez_load_failure_raises():
    """A failed load is "not checked", never "not in a zone": it must not come back as None."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection refused")

    with pytest.raises(Exception, match="Connection refused"):
        await ez.check_enterprise_zone(41.93, -87.65, client=mock_client)


# Recorded 2026-11-03 from the map view 64xf-pyvh: 6 features, every geometry null, no properties.
_NULL_GEOMETRY_FIXTURE = Path(__file__).parent / "fixtures" / "enterprise_zones_64xf_null_geometry_2026-11-03.geojson"


def _client_returning(body):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = body
    client = AsyncMock()
    client.get.return_value = resp
    return client


@pytest.mark.asyncio
async def test_null_geometry_response_raises_and_is_not_cached():
    body = json.loads(_NULL_GEOMETRY_FIXTURE.read_text())
    assert len(body["features"]) == 6 and all(f["geometry"] is None for f in body["features"])
    client = _client_returning(body)

    with pytest.raises(RuntimeError, match="no usable geometry"):
        await ez.check_enterprise_zone(41.93, -87.65, client=client)
    with pytest.raises(RuntimeError, match="no usable geometry"):
        await ez.ez_geojson_feature(41.93, -87.65, client=client)
    assert ez._ez_boundaries is None
    assert client.get.await_count == 2  # retried, not served from a cached empty list


@pytest.mark.asyncio
async def test_empty_feature_collection_raises():
    with pytest.raises(RuntimeError, match="no usable geometry"):
        await ez.check_enterprise_zone(41.93, -87.65, client=_client_returning(_make_geojson([])))


@pytest.mark.asyncio
async def test_numbered_zone_gets_a_readable_name():
    """bwpt-y235 names Chicago's zones by number ("5"); the Profile shows "Chicago Enterprise Zone 5"."""
    feat = _make_feature("ignored", (-87.65, 41.93))
    feat["properties"] = {"name": "5", "enterprise": "5.0", "objectid": "2"}
    result = await ez.check_enterprise_zone(41.93, -87.65, client=_client_returning(_make_geojson([feat])))
    assert result == {"zone_name": "Chicago Enterprise Zone 5"}


def test_zone_name_keeps_a_text_name():
    assert ez._zone_name({"zone_name": "Calumet"}) == "Calumet"
    assert ez._zone_name({}) == "Unknown Enterprise Zone"


@pytest.mark.asyncio
async def test_ez_geometry_load_failure_raises():
    mock_client = AsyncMock()
    success = MagicMock()
    success.raise_for_status = MagicMock()
    success.json.return_value = _make_geojson([
        _make_feature("Recovered EZ", (-87.65, 41.93)),
    ])
    mock_client.get.side_effect = [Exception("Connection refused"), success]

    with pytest.raises(Exception, match="Connection refused"):
        await ez.ez_geojson_feature(41.93, -87.65, client=mock_client)
    recovered = await ez.ez_geojson_feature(41.93, -87.65, client=mock_client)

    assert recovered is not None
    assert recovered["properties"]["name"] == "Recovered EZ"
    assert mock_client.get.await_count == 2


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
    """Chicago's six Enterprise Zones load with geometry (an empty layer raises; decision Item 64)."""
    ez._ez_boundaries = None  # ensure fresh fetch
    boundaries = await ez._load_ez_boundaries()
    assert len(boundaries) == 6
    names = sorted(b[0] for b in boundaries)
    assert names == [f"Chicago Enterprise Zone {n}" for n in range(1, 7)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_ez_live_not_in_zone():
    """Lincoln Park (affluent area) is unlikely to be in an Enterprise Zone."""
    ez._ez_boundaries = None
    result = await ez.check_enterprise_zone(41.9307, -87.6411)
    assert result is None
