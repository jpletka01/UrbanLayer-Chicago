"""Tests for vacant buildings retrieval and assembly."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.assembler import _vacant_building_summary
from backend.retrieval.vacant import vacant_buildings_by_community_area


SAMPLE_GROUPED = [
    {"issuing_department": "BUILDINGS", "count": "15"},
    {"issuing_department": "POLICE", "count": "8"},
    {"issuing_department": "STREETS & SANITATION", "count": "3"},
]

SAMPLE_DETAIL = [
    {
        "property_address": "1234 W EXAMPLE ST",
        "issued_date": "2025-11-15T00:00:00.000",
        "violation_type": "13-12-125 Duty to secure vacant building",
        "entity_or_person_s_": "ACME LLC",
        "current_amount_due": "5000",
        "latitude": "41.88",
        "longitude": "-87.65",
    },
    {
        "property_address": "5678 S TEST AVE",
        "issued_date": "2025-10-01T00:00:00.000",
        "violation_type": "13-12-140 Watchman required",
        "entity_or_person_s_": "",
        "current_amount_due": "0",
        "latitude": "41.77",
        "longitude": "-87.63",
    },
]


class TestVacantBuildingSummary:
    def test_basic(self):
        result = _vacant_building_summary({"grouped": SAMPLE_GROUPED, "detail": SAMPLE_DETAIL})
        assert result is not None
        assert result.total == 26
        assert result.by_department["BUILDINGS"] == 15
        assert result.by_department["POLICE"] == 8
        assert len(result.recent_reports) == 2
        assert result.recent_reports[0].address == "1234 W EXAMPLE ST"
        assert result.recent_reports[0].date == "2025-11-15"
        assert result.recent_reports[0].amount_due == 5000.0
        assert result.recent_reports[1].amount_due is None

    def test_empty_data(self):
        result = _vacant_building_summary({"grouped": [], "detail": []})
        assert result is None

    def test_responsible_entity(self):
        result = _vacant_building_summary({"grouped": SAMPLE_GROUPED, "detail": SAMPLE_DETAIL})
        assert result is not None
        assert result.recent_reports[0].responsible_entity == "ACME LLC"
        assert result.recent_reports[1].responsible_entity is None


class TestVacantBuildingsRetrieval:
    @pytest.mark.asyncio
    async def test_returns_grouped_and_detail(self):
        with patch("backend.retrieval.vacant.community_area_bounds", return_value=(41.7, -87.7, 41.9, -87.6)):
            with patch("backend.retrieval.vacant.socrata_aggregate", new_callable=AsyncMock, return_value=SAMPLE_GROUPED):
                with patch("backend.retrieval.vacant.socrata_get", new_callable=AsyncMock, return_value=SAMPLE_DETAIL):
                    result = await vacant_buildings_by_community_area(25)
                    assert "grouped" in result
                    assert "detail" in result
                    assert len(result["grouped"]) == 3
                    assert len(result["detail"]) == 2

    @pytest.mark.asyncio
    async def test_no_bounds_returns_empty(self):
        with patch("backend.retrieval.vacant.community_area_bounds", return_value=None):
            result = await vacant_buildings_by_community_area(99)
            assert result == {"grouped": [], "detail": []}
