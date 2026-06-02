import json
from unittest.mock import AsyncMock, patch

import pytest

import backend.retrieval.neighborhood.transit as transit_mod
from backend.retrieval.neighborhood.transit import (
    _haversine_mi,
    build_transit_access,
    check_tod_eligibility,
    find_nearest_stations,
)

SAMPLE_STATIONS = [
    {"name": "Damen", "lat": 41.9661, "lon": -87.6779, "type": "cta_rail", "lines": ["Blue"]},
    {"name": "Western", "lat": 41.9662, "lon": -87.6878, "type": "cta_rail", "lines": ["Blue"]},
    {"name": "LaSalle St", "lat": 41.8768, "lon": -87.6319, "type": "metra", "line": "Rock Island"},
    {"name": "Ravenswood", "lat": 41.9667, "lon": -87.6747, "type": "metra", "line": "UP-North"},
]


@pytest.fixture(autouse=True)
def _clear_cache():
    transit_mod._stations = None
    yield
    transit_mod._stations = None


def test_haversine_known_distance():
    chi_lat, chi_lon = 41.8781, -87.6298
    ohare_lat, ohare_lon = 41.9742, -87.9073
    dist = _haversine_mi(chi_lat, chi_lon, ohare_lat, ohare_lon)
    assert 13 < dist < 16


def test_haversine_zero_distance():
    assert _haversine_mi(41.0, -87.0, 41.0, -87.0) == 0.0


@pytest.mark.asyncio
async def test_find_nearest_stations():
    transit_mod._stations = SAMPLE_STATIONS
    near_damen = 41.9661, -87.6779
    result = await find_nearest_stations(*near_damen, radius_mi=2.0)

    assert result["nearest_cta_rail"] is not None
    assert result["nearest_cta_rail"]["name"] == "Damen"
    assert result["nearest_cta_rail"]["distance_mi"] < 0.1
    assert result["nearest_metra"] is not None
    assert result["nearest_metra"]["name"] == "Ravenswood"


@pytest.mark.asyncio
async def test_no_stations_within_radius():
    transit_mod._stations = SAMPLE_STATIONS
    far_away = 42.5, -88.5
    result = await find_nearest_stations(*far_away, radius_mi=0.1)
    assert result["nearest_cta_rail"] is None
    assert result["nearest_metra"] is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.transit.query_overlay")
async def test_tod_cta_hit(mock_overlay):
    async def mock_query(lat, lon, layer_id, *, client=None):
        if layer_id == 13:
            return {"features": [{"attributes": {"NAME": "TOD CTA"}}]}
        return None
    mock_overlay.side_effect = mock_query

    result = await check_tod_eligibility(41.93, -87.65, client=AsyncMock())
    assert result["tod_eligible"] is True
    assert result["tod_type"] == "CTA rail"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.transit.query_overlay")
async def test_tod_metra_hit(mock_overlay):
    async def mock_query(lat, lon, layer_id, *, client=None):
        if layer_id == 24:
            return {"features": [{"attributes": {"NAME": "TOD Metra"}}]}
        return None
    mock_overlay.side_effect = mock_query

    result = await check_tod_eligibility(41.93, -87.65, client=AsyncMock())
    assert result["tod_eligible"] is True
    assert result["tod_type"] == "Metra"


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.transit.query_overlay")
async def test_tod_no_hit(mock_overlay):
    mock_overlay.return_value = None

    result = await check_tod_eligibility(41.93, -87.65, client=AsyncMock())
    assert result["tod_eligible"] is False
    assert result["tod_type"] is None


@pytest.mark.asyncio
@patch("backend.retrieval.neighborhood.transit.query_overlay")
async def test_tod_query_failure(mock_overlay):
    mock_overlay.side_effect = Exception("ArcGIS down")

    result = await check_tod_eligibility(41.93, -87.65, client=AsyncMock())
    assert result["tod_eligible"] is False


def test_build_transit_access_full():
    station_result = {
        "nearest_cta_rail": {"name": "Damen", "distance_mi": 0.3, "lines": ["Blue"]},
        "nearest_metra": {"name": "Ravenswood", "distance_mi": 0.8, "line": "UP-North"},
    }
    tod_result = {"tod_eligible": True, "tod_type": "CTA rail"}
    ta = build_transit_access(station_result, tod_result)

    assert ta is not None
    assert ta.nearest_cta_rail == "Damen"
    assert ta.cta_rail_distance_mi == 0.3
    assert ta.cta_lines == ["Blue"]
    assert ta.nearest_metra == "Ravenswood"
    assert ta.metra_distance_mi == 0.8
    assert ta.metra_line == "UP-North"
    assert ta.tod_eligible is True
    assert ta.tod_type == "CTA rail"


def test_build_transit_access_none():
    assert build_transit_access(None, None) is None


# --- live integration tests (local transit data + real ArcGIS TOD overlay) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_find_nearest_stations_live():
    """Find nearest stations using real cached transit data."""
    transit_mod._stations = None  # force reload from transit_stations.json
    result = await find_nearest_stations(41.9307, -87.6411, radius_mi=3.0)
    assert result["nearest_cta_rail"] is not None
    assert result["nearest_cta_rail"]["name"]
    assert result["nearest_cta_rail"]["distance_mi"] < 3.0
    assert result["nearest_metra"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tod_eligibility_live():
    """Check TOD eligibility against the real ArcGIS overlay layers."""
    result = await check_tod_eligibility(41.9307, -87.6411)
    assert isinstance(result["tod_eligible"], bool)
    assert result["tod_type"] is None or isinstance(result["tod_type"], str)
