"""Tests for the /api/map-data endpoint and map retrieval functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_map_settings(mock_settings):
    mock_settings.limit_map_crime = 200
    mock_settings.limit_map_311 = 150
    mock_settings.limit_map_permits = 100
    mock_settings.enable_zoning_layer = False
    return mock_settings


CRIME_ROWS = [
    {"latitude": "41.925", "longitude": "-87.712", "primary_type": "THEFT",
     "date": "2025-05-01T14:22:00", "description": "FROM BUILDING", "arrest": "false"},
    {"latitude": None, "longitude": "-87.710", "primary_type": "BATTERY",
     "date": "2025-05-02T10:00:00", "description": "SIMPLE", "arrest": "false"},
]

THREE11_ROWS = [
    {"latitude": "41.923", "longitude": "-87.710", "sr_type": "Pothole in Street",
     "status": "Open", "created_date": "2025-04-15T09:00:00", "owner_department": "Streets & Sanitation"},
]

PERMIT_ROWS = [
    {"latitude": "41.924", "longitude": "-87.711", "permit_type": "PERMIT - NEW CONSTRUCTION",
     "work_description": "ERECT 3-FLAT", "reported_cost": "450000", "issue_date": "2025-03-10"},
    {"latitude": "41.925", "longitude": "-87.712", "permit_type": "PERMIT - RENOVATION/ALTERATION",
     "work_description": "INTERIOR RENOVATION", "reported_cost": None, "issue_date": "2025-03-15"},
]


class TestCleanRows:
    def test_filters_null_lat(self):
        from backend.retrieval.map_data import _clean_rows
        result = _clean_rows(CRIME_ROWS.copy())
        assert len(result) == 1
        assert result[0]["primary_type"] == "THEFT"
        assert result[0]["latitude"] == 41.925

    def test_casts_to_float(self):
        from backend.retrieval.map_data import _clean_rows
        rows = [{"latitude": "41.9", "longitude": "-87.7", "extra": "keep"}]
        result = _clean_rows(rows)
        assert isinstance(result[0]["latitude"], float)
        assert isinstance(result[0]["longitude"], float)
        assert result[0]["extra"] == "keep"


class TestCrimesForMap:
    @pytest.mark.asyncio
    async def test_returns_cleaned_rows(self, mock_map_settings):
        with patch("backend.retrieval.map_data.get_settings", return_value=mock_map_settings), \
             patch("backend.retrieval.map_data.socrata_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = CRIME_ROWS.copy()
            from backend.retrieval.map_data import crimes_for_map
            result = await crimes_for_map(24, days=90)
            assert len(result) == 1
            assert result[0]["latitude"] == 41.925
            call_params = mock_get.call_args[0][1]
            assert "$limit" in call_params
            assert call_params["$limit"] == 200


class TestPermitsForMap:
    @pytest.mark.asyncio
    async def test_renames_reported_cost(self, mock_map_settings):
        with patch("backend.retrieval.map_data.get_settings", return_value=mock_map_settings), \
             patch("backend.retrieval.map_data.socrata_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = PERMIT_ROWS.copy()
            from backend.retrieval.map_data import permits_for_map
            result = await permits_for_map(24, days=365)
            assert len(result) == 2
            assert result[0]["estimated_cost"] == 450000.0
            assert "reported_cost" not in result[0]
            assert result[1]["estimated_cost"] == 0


class TestMapDataEndpoint:
    @pytest.fixture
    def client(self, mock_map_settings):
        with patch("backend.config.get_settings", return_value=mock_map_settings), \
             patch("backend.main.get_settings", return_value=mock_map_settings), \
             patch("backend.main.crimes_for_map", new_callable=AsyncMock) as mock_crime, \
             patch("backend.main.requests_311_for_map", new_callable=AsyncMock) as mock_311, \
             patch("backend.main.permits_for_map", new_callable=AsyncMock) as mock_permits:
            mock_crime.return_value = [{"latitude": 41.9, "longitude": -87.7, "primary_type": "THEFT"}]
            mock_311.return_value = [{"latitude": 41.92, "longitude": -87.71, "sr_type": "Pothole"}]
            mock_permits.return_value = [{"latitude": 41.93, "longitude": -87.72, "estimated_cost": 100000}]
            from backend.main import app
            yield TestClient(app)

    def test_returns_correct_shape(self, client):
        resp = client.post("/api/map-data", json={"community_area": 24})
        assert resp.status_code == 200
        data = resp.json()
        assert "crimes" in data
        assert "requests_311" in data
        assert "building_permits" in data
        assert len(data["crimes"]) == 1
        assert data["zoning"] is None

    def test_includes_queried_address(self, client):
        resp = client.post("/api/map-data", json={
            "community_area": 24,
            "address_lat": 41.925,
            "address_lon": -87.712,
            "address_label": "2400 N Milwaukee Ave",
        })
        data = resp.json()
        assert data["queried_address"]["latitude"] == 41.925
        assert data["queried_address"]["label"] == "2400 N Milwaukee Ave"

    def test_no_address_returns_null(self, client):
        resp = client.post("/api/map-data", json={"community_area": 24})
        assert resp.json()["queried_address"] is None


class TestZoningForMap:
    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self, mock_map_settings):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        with patch("backend.retrieval.zoning.community_area_bounds", return_value=(41.91, -87.66, 41.95, -87.63)):
            from backend.retrieval.map_data import zoning_for_map
            result = await zoning_for_map(24, client=mock_client)
            assert result["type"] == "FeatureCollection"
            assert result["features"] == []
