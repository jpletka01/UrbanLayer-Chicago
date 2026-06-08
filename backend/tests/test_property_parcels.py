"""Tests for Cook County GIS parcel lookup + Socrata fallback."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from backend.retrieval.property.parcels import (
    lookup_parcel,
    _lookup_parcel_gis,
    _lookup_parcel_socrata,
    PARCEL_QUERY_URL,
)


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


# --- GIS unit tests ---


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
    result = await _lookup_parcel_gis(41.9307, -87.6411, client=client)
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
    result = await _lookup_parcel_gis(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_handles_http_error():
    client = AsyncMock()
    client.get.return_value = _mock_response([], status_code=500)
    result = await _lookup_parcel_gis(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_handles_connection_error():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("connection refused")
    result = await _lookup_parcel_gis(41.9307, -87.6411, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_parcel_sends_correct_geometry():
    """Verify lon comes before lat in the geometry param."""
    client = AsyncMock()
    client.get.return_value = _mock_response([])
    await _lookup_parcel_gis(41.93, -87.64, client=client)
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
    result = await _lookup_parcel_gis(41.93, -87.64, client=client)
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
    result = await _lookup_parcel_gis(41.93, -87.64, client=client)
    assert result is not None
    assert result["pin14"] == "14241020170000"
    assert "-" not in result["pin14"]


# --- Socrata fallback unit tests ---


@pytest.mark.asyncio
async def test_socrata_fallback_picks_closest_pin():
    """When multiple parcels returned, pick the one nearest the query point."""
    rows = [
        {"pin": "14283180220000", "class": "2-11", "lat": "41.9300", "lon": "-87.6415",
         "zip_code": "60614", "township_name": "North", "nbhd_code": "71120", "tax_code": "71164"},
        {"pin": "14241020170000", "class": "2-05", "lat": "41.9307", "lon": "-87.6411",
         "zip_code": "60614", "township_name": "North", "nbhd_code": "71121", "tax_code": "71165"},
        {"pin": "14283180360000", "class": "2-99", "lat": "41.9310", "lon": "-87.6400",
         "zip_code": "60614", "township_name": "North", "nbhd_code": "71122", "tax_code": "71166"},
    ]
    with patch("backend.retrieval.property.parcels.socrata_get", return_value=rows):
        result = await _lookup_parcel_socrata(41.9307, -87.6411)
    assert result is not None
    assert result["pin14"] == "14241020170000"
    assert result["bldg_class"] == "2-05"
    assert result["bldg_sqft"] is None
    assert result["address"] is None
    assert result["geometry"] is None
    assert result["zip_code"] == "60614"
    assert result["township_name"] == "North"
    assert result["nbhd_code"] == "71121"
    assert result["tax_code"] == "71165"


@pytest.mark.asyncio
async def test_socrata_fallback_empty_box():
    """No parcels in bounding box → returns None."""
    with patch("backend.retrieval.property.parcels.socrata_get", return_value=[]):
        result = await _lookup_parcel_socrata(41.9307, -87.6411)
    assert result is None


@pytest.mark.asyncio
async def test_socrata_fallback_handles_error():
    with patch("backend.retrieval.property.parcels.socrata_get", side_effect=Exception("timeout")):
        result = await _lookup_parcel_socrata(41.9307, -87.6411)
    assert result is None


@pytest.mark.asyncio
async def test_socrata_fallback_zero_pads_pin():
    rows = [{"pin": "1424102017", "class": "2-11", "lat": "41.9307", "lon": "-87.6411"}]
    with patch("backend.retrieval.property.parcels.socrata_get", return_value=rows):
        result = await _lookup_parcel_socrata(41.9307, -87.6411)
    assert result is not None
    assert result["pin14"] == "00001424102017"
    assert len(result["pin14"]) == 14


# --- Fallback chain tests ---


@pytest.mark.asyncio
async def test_gis_down_falls_back_to_socrata():
    """GIS returns None → Socrata fallback fires and returns PIN."""
    socrata_rows = [
        {"pin": "14241020170000", "class": "2-05", "lat": "41.9307", "lon": "-87.6411"},
    ]
    with patch("backend.retrieval.property.parcels._lookup_parcel_gis", return_value=None), \
         patch("backend.retrieval.property.parcels._lookup_parcel_socrata") as mock_socrata:
        mock_socrata.return_value = {
            "pin14": "14241020170000", "bldg_class": "2-05",
            "bldg_sqft": None, "land_sqft": None, "total_value": None,
            "address": None, "geometry": None,
            "zip_code": "60614", "township_name": "North",
            "nbhd_code": "71121", "tax_code": "71165",
        }
        result = await lookup_parcel(41.9307, -87.6411)
    assert result is not None
    assert result["pin14"] == "14241020170000"
    mock_socrata.assert_called_once()


@pytest.mark.asyncio
async def test_gis_success_skips_socrata():
    """GIS returns parcel → Socrata never called."""
    gis_result = {
        "pin14": "14241020170000", "bldg_class": "2-11",
        "bldg_sqft": 2400, "land_sqft": 3200, "total_value": 350000,
        "address": "443 W WRIGHTWOOD AVE", "geometry": None,
    }
    with patch("backend.retrieval.property.parcels._lookup_parcel_gis", return_value=gis_result), \
         patch("backend.retrieval.property.parcels._lookup_parcel_socrata") as mock_socrata:
        result = await lookup_parcel(41.9307, -87.6411)
    assert result is not None
    assert result["bldg_sqft"] == 2400
    mock_socrata.assert_not_called()


# --- Integration tests (real APIs) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parcel_gis_diagnostic():
    """Hit the real Cook County GIS endpoint and report what happens.

    Does NOT skip — fails with diagnostic info so we know the GIS status.
    """
    import time
    params = {
        "geometry": "-87.6411,41.9307",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PIN14,Address",
        "returnGeometry": "false",
        "f": "json",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        start = time.monotonic()
        try:
            resp = await client.get(PARCEL_QUERY_URL, params=params)
            elapsed = time.monotonic() - start
            data = resp.json()
            features = data.get("features", [])
            assert features, (
                f"GIS returned 0 features in {elapsed:.1f}s "
                f"(status={resp.status_code}, body={data}). "
                "Cook County GIS spatial index is likely still broken."
            )
            pin = features[0]["attributes"].get("PIN14")
            assert pin, f"Feature returned but no PIN14: {features[0]}"
        except httpx.TimeoutException:
            elapsed = time.monotonic() - start
            pytest.fail(
                f"GIS timed out after {elapsed:.1f}s. "
                "Cook County GIS is unresponsive for spatial queries."
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parcel_live_lincoln_park():
    """Hit the real Cook County GIS parcel layer (free, no key).

    This point definitely has a parcel, so a None result means the GIS service
    is down/slow (it is intermittently). Retry a few times, then skip rather
    than flap on transient upstream failures.
    """
    result = None
    for _ in range(3):
        result = await _lookup_parcel_gis(41.9307, -87.6411)  # ~451 W Wrightwood Ave
        if result is not None:
            break
    if result is None:
        pytest.skip("Cook County GIS unavailable (transient)")
    assert result["pin14"].isdigit() and len(result["pin14"]) == 14
    assert result["address"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parcel_socrata_live():
    """Hit the real Socrata Parcel Universe endpoint."""
    result = await _lookup_parcel_socrata(41.9307, -87.6411)
    assert result is not None, "Socrata Parcel Universe returned no parcels near Lincoln Park"
    assert result["pin14"].isdigit() and len(result["pin14"]) == 14
    assert result["bldg_class"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lookup_parcel_live_with_fallback():
    """Full lookup_parcel with fallback chain — should succeed even if GIS is down."""
    result = await lookup_parcel(41.9307, -87.6411)
    assert result is not None, "Neither GIS nor Socrata returned a parcel for Lincoln Park"
    assert result["pin14"].isdigit() and len(result["pin14"]) == 14
