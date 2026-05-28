import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from backend.retrieval.crime import crime_by_community_area, crime_recent_by_block
from backend.retrieval.three11 import (
    open_311_by_community_area,
    open_311_oldest,
    response_times_by_community_area,
)
from backend.retrieval.buildings import permits_by_community_area, violations_by_community_area
from backend.retrieval.business import businesses_by_community_area


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.dataset_crime = "ijzp-q8t2"
    settings.dataset_311 = "v6vf-nfxy"
    settings.dataset_permits = "ydr8-5enu"
    settings.dataset_violations = "22u3-xenr"
    settings.dataset_business = "uupf-x98q"
    settings.crime_lag_days = 7
    return settings


class TestCrimeRetrieval:
    @pytest.mark.asyncio
    async def test_crime_by_community_area_query_structure(self, mock_settings):
        with patch("backend.retrieval.crime.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.crime.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await crime_by_community_area(24, days=90)

        assert mock_get.call_count == 2
        crimes_call, arrests_call = mock_get.call_args_list
        assert crimes_call[0][0] == "ijzp-q8t2"
        crimes_params = crimes_call[0][1]
        assert "community_area='24'" in crimes_params["$where"]
        assert "$group" in crimes_params
        assert "primary_type" in crimes_params["$group"]
        assert "$limit" in crimes_params

        arrests_params = arrests_call[0][1]
        assert "arrest=true" in arrests_params["$where"]

    @pytest.mark.asyncio
    async def test_crime_by_community_area_returns_results_with_arrests(self, mock_settings):
        crimes_data = [
            {"primary_type": "THEFT", "count": "50"},
            {"primary_type": "BATTERY", "count": "30"},
        ]
        arrests_data = [
            {"primary_type": "THEFT", "arrests": "5"},
            {"primary_type": "BATTERY", "arrests": "10"},
        ]
        with patch("backend.retrieval.crime.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.crime.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.side_effect = [crimes_data, arrests_data]
                result = await crime_by_community_area(24, days=90)

        assert len(result) == 2
        assert result[0]["arrests"] == "5"
        assert result[1]["arrests"] == "10"

    @pytest.mark.asyncio
    async def test_crime_recent_by_block_query_structure(self, mock_settings):
        with patch("backend.retrieval.crime.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.crime.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await crime_recent_by_block("016XX W DIVISION ST", days=30, limit=20)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        params = call_args[0][1]
        assert "block='016XX W DIVISION ST'" in params["$where"]
        assert params["$limit"] == 20
        assert "date DESC" in params["$order"]


class TestThree11Retrieval:
    @pytest.mark.asyncio
    async def test_open_311_by_community_area_filters_duplicates(self, mock_settings):
        with patch("backend.retrieval.three11.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.three11.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await open_311_by_community_area(24)

        call_args = mock_get.call_args
        params = call_args[0][1]
        assert "sr_type!='Open - Dup'" in params["$where"]
        assert "status='Open'" in params["$where"]

    @pytest.mark.asyncio
    async def test_open_311_oldest_returns_single_record(self, mock_settings):
        mock_data = [{"sr_number": "SR123", "sr_type": "Pothole", "created_date": "2024-01-01"}]
        with patch("backend.retrieval.three11.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.three11.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_data
                result = await open_311_oldest(24)

        assert len(result) == 1
        call_args = mock_get.call_args
        params = call_args[0][1]
        assert params["$limit"] == 1
        assert "created_date ASC" in params["$order"]

    @pytest.mark.asyncio
    async def test_response_times_groups_by_sr_type(self, mock_settings):
        with patch("backend.retrieval.three11.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.three11.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await response_times_by_community_area(24, days=90)

        call_args = mock_get.call_args
        params = call_args[0][1]
        assert params["$group"] == "sr_type"
        assert "avg_days" in params["$select"]
        assert "status='Closed'" in params["$where"]


class TestBuildingsRetrieval:
    @pytest.mark.asyncio
    async def test_permits_by_community_area_query(self, mock_settings):
        with patch("backend.retrieval.buildings.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.buildings.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await permits_by_community_area(24, days=365)

        call_args = mock_get.call_args
        assert call_args[0][0] == "ydr8-5enu"
        params = call_args[0][1]
        assert "community_area='24'" in params["$where"]
        assert "issue_date" in params["$where"]
        assert "reported_cost" in params["$select"]

    @pytest.mark.asyncio
    async def test_violations_by_community_area_query(self, mock_settings):
        with patch("backend.retrieval.buildings.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.buildings.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await violations_by_community_area(24, days=365)

        call_args = mock_get.call_args
        assert call_args[0][0] == "22u3-xenr"
        params = call_args[0][1]
        assert "violation_status" in params["$select"]
        assert "violation_description" in params["$select"]


class TestBusinessRetrieval:
    @pytest.mark.asyncio
    async def test_businesses_by_community_area_query(self, mock_settings):
        with patch("backend.retrieval.business.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.business.socrata_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                await businesses_by_community_area(24)

        call_args = mock_get.call_args
        assert call_args[0][0] == "uupf-x98q"
        params = call_args[0][1]
        assert "community_area='24'" in params["$where"]
        assert "business_activity" in params["$select"]
        assert params["$limit"] == 100
