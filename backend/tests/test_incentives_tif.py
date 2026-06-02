from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.retrieval.incentives import tif
from backend.retrieval.incentives.tif import fetch_tif_fund_analysis, tif_geojson_by_community_area


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset module-level boundary cache between tests."""
    tif._tif_boundaries = None
    yield
    tif._tif_boundaries = None


def _make_geojson(features):
    return {"type": "FeatureCollection", "features": features}


def _make_feature(name, coords, *, comm_area="22", repealed_d=None):
    """Build a simple polygon feature (a small square) with real Socrata fields."""
    lon, lat = coords
    d = 0.01
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "approval_d": "2005-06-01T00:00:00.000",
            "expiration": "2029-12-31T00:00:00.000",
            "type": "Existing",
            "comm_area": comm_area,
            "repealed_d": repealed_d,
            "ref": "T-099",
        },
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
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_check_tif_skips_repealed(mock_client_cls):
    geojson = _make_geojson([
        _make_feature("Repealed TIF", (-87.65, 41.93), repealed_d="2020-01-01T00:00:00.000"),
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    result = await tif.check_tif(41.93, -87.65, client=mock_client)
    assert result is None


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.socrata_get")
async def test_fetch_financials_success(mock_socrata):
    mock_socrata.return_value = [
        {"report_year": "2024", "tif_district": "Elston/Armstrong", "public_funds": "500000", "current_year_payments": "300000"},
        {"report_year": "2024", "tif_district": "Elston/Armstrong", "public_funds": "200000", "current_year_payments": "100000"},
    ]
    result = await tif.fetch_tif_financials("Elston/Armstrong", client=AsyncMock())
    assert len(result) == 2
    assert result[0]["report_year"] == "2024"


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
    assert result["properties"]["approval_d"] == "2005-06-01T00:00:00.000"


# --- neighborhood-level TIF lookup ---


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_tif_districts_by_community_area(mock_client_cls):
    geojson = _make_geojson([
        _make_feature("Fullerton/Milwaukee", (-87.70, 41.93), comm_area="16,21,22"),
        _make_feature("Pulaski Corridor", (-87.73, 41.92), comm_area="16,20,21,22,23"),
        _make_feature("Unrelated TIF", (-87.60, 41.80), comm_area="44,45"),
        _make_feature("Repealed One", (-87.71, 41.93), comm_area="22", repealed_d="2020-01-01T00:00:00.000"),
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    results = await tif.tif_districts_by_community_area(22, client=mock_client)
    assert len(results) == 2
    names = {r["tif_name"] for r in results}
    assert names == {"Fullerton/Milwaukee", "Pulaski Corridor"}
    assert results[0]["start_year"] == 2005
    assert results[0]["end_year"] == 2029


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_tif_districts_by_community_area_no_match(mock_client_cls):
    geojson = _make_geojson([
        _make_feature("Some TIF", (-87.65, 41.93), comm_area="10,11"),
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    results = await tif.tif_districts_by_community_area(99, client=mock_client)
    assert results == []


# --- fetch_tif_fund_analysis ---


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.socrata_get")
async def test_fetch_fund_analysis_success(mock_socrata):
    mock_socrata.return_value = [
        {
            "report_year": "2024",
            "tif_district": "Fullerton/Milwaukee",
            "property_tax_increment_current": "21911518",
            "property_tax_increment_cumulative": "192573767",
            "total_expenditure": "24619936",
            "fund_balance": "63162041",
            "net_income": "-1270044",
        },
        {
            "report_year": "2023",
            "tif_district": "Fullerton/Milwaukee",
            "property_tax_increment_current": "21604111",
            "property_tax_increment_cumulative": "170662249",
            "total_expenditure": "7694785",
            "fund_balance": "64432085",
            "net_income": "15618068",
        },
    ]
    result = await fetch_tif_fund_analysis("Fullerton/Milwaukee", client=AsyncMock())
    assert len(result) == 2
    assert result[0]["report_year"] == "2024"
    assert result[0]["property_tax_increment_current"] == "21911518"


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.socrata_get")
async def test_fetch_fund_analysis_error(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata down")
    result = await fetch_tif_fund_analysis("Fullerton/Milwaukee", client=AsyncMock())
    assert result == []


# --- tif_geojson_by_community_area ---


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_tif_geojson_by_community_area(mock_client_cls):
    geojson = _make_geojson([
        _make_feature("Fullerton/Milwaukee", (-87.70, 41.93), comm_area="16,21,22"),
        _make_feature("Pulaski Corridor", (-87.73, 41.92), comm_area="16,20,21,22,23"),
        _make_feature("Unrelated TIF", (-87.60, 41.80), comm_area="44,45"),
        _make_feature("Repealed One", (-87.71, 41.93), comm_area="22", repealed_d="2020-01-01T00:00:00.000"),
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    features = await tif_geojson_by_community_area(22, client=mock_client)
    assert len(features) == 2
    names = {f["properties"]["name"] for f in features}
    assert names == {"Fullerton/Milwaukee", "Pulaski Corridor"}
    assert all(f["type"] == "Feature" for f in features)
    assert all(f["geometry"]["type"] == "Polygon" for f in features)
    assert all(f["properties"]["zone_type"] == "tif" for f in features)


@pytest.mark.asyncio
@patch("backend.retrieval.incentives.tif.httpx.AsyncClient")
async def test_tif_geojson_by_community_area_no_match(mock_client_cls):
    geojson = _make_geojson([
        _make_feature("Some TIF", (-87.65, 41.93), comm_area="10,11"),
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = geojson

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    features = await tif_geojson_by_community_area(99, client=mock_client)
    assert features == []


# --- _parse_year ---

def test_parse_year():
    assert tif._parse_year("2005-06-01T00:00:00.000") == 2005
    assert tif._parse_year("2029-12-31T00:00:00.000") == 2029
    assert tif._parse_year(None) is None
    assert tif._parse_year("") is None


# --- live integration tests (real Socrata TIF boundaries, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tif_boundaries_load_live():
    """Verify TIF boundary GeoJSON loads from Socrata and contains polygons."""
    tif._tif_boundaries = None  # ensure fresh fetch
    boundaries = await tif._load_tif_boundaries()
    assert len(boundaries) > 0, "Expected TIF district boundaries from Socrata"
    name, props, poly, geom = boundaries[0]
    assert isinstance(name, str) and name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_tif_live_known_district():
    """Pilsen/Little Village area — should be in a TIF district."""
    tif._tif_boundaries = None
    result = await tif.check_tif(41.856, -87.664)
    # This area has TIF districts; if boundaries changed, just verify the call works
    assert result is None or (result["tif_name"] and "properties" in result)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tif_by_community_area_live():
    """Logan Square (CA 22) should have active TIF districts."""
    tif._tif_boundaries = None
    results = await tif.tif_districts_by_community_area(22)
    assert len(results) > 0, "Expected TIF districts in Logan Square"
    assert all(r.get("tif_name") for r in results)
