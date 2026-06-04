"""Tests for food inspections retrieval and assembly."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.assembler import _food_inspection_summary
from backend.retrieval.food_inspections import food_inspections_by_community_area


SAMPLE_BY_RESULT = [
    {"results": "Pass", "count": "120"},
    {"results": "Fail", "count": "30"},
    {"results": "Pass w/ Conditions", "count": "50"},
    {"results": "No Entry", "count": "5"},
]

SAMPLE_BY_RISK = [
    {"risk": "Risk 1 (High)", "count": "100"},
    {"risk": "Risk 2 (Medium)", "count": "80"},
    {"risk": "Risk 3 (Low)", "count": "25"},
]

SAMPLE_DETAIL = [
    {
        "dba_name": "JOES PIZZA",
        "facility_type": "Restaurant",
        "risk": "Risk 1 (High)",
        "results": "Fail",
        "inspection_date": "2025-12-01T00:00:00.000",
        "violations": "6. IMPROPER TEMP",
        "latitude": "41.88",
        "longitude": "-87.65",
    },
    {
        "dba_name": "HAPPY BAKERY",
        "facility_type": "Bakery",
        "risk": "Risk 2 (Medium)",
        "results": "Pass",
        "inspection_date": "2025-11-20T00:00:00.000",
        "violations": "",
        "latitude": "41.89",
        "longitude": "-87.64",
    },
]


class TestFoodInspectionSummary:
    def test_basic(self):
        result = _food_inspection_summary({
            "by_result": SAMPLE_BY_RESULT,
            "by_risk": SAMPLE_BY_RISK,
            "detail": SAMPLE_DETAIL,
        })
        assert result is not None
        assert result.total == 205
        assert result.by_result["Pass"] == 120
        assert result.by_result["Fail"] == 30
        assert result.fail_rate is not None
        assert 14 < result.fail_rate < 15
        assert len(result.recent_inspections) == 2
        assert result.recent_inspections[0].name == "JOES PIZZA"
        assert result.recent_inspections[0].result == "Fail"
        assert result.recent_inspections[0].date == "2025-12-01"

    def test_risk_breakdown(self):
        result = _food_inspection_summary({
            "by_result": SAMPLE_BY_RESULT,
            "by_risk": SAMPLE_BY_RISK,
            "detail": [],
        })
        assert result is not None
        assert result.by_risk["Risk 1 (High)"] == 100

    def test_empty_data(self):
        result = _food_inspection_summary({"by_result": [], "by_risk": [], "detail": []})
        assert result is None

    def test_zero_fail_rate(self):
        result = _food_inspection_summary({
            "by_result": [{"results": "Pass", "count": "50"}],
            "by_risk": [],
            "detail": [],
        })
        assert result is not None
        assert result.fail_rate == 0.0


class TestFoodInspectionsRetrieval:
    @pytest.mark.asyncio
    async def test_returns_data(self):
        with patch("backend.retrieval.food_inspections.community_area_bounds", return_value=(41.7, -87.7, 41.9, -87.6)):
            with patch("backend.retrieval.food_inspections.socrata_aggregate", new_callable=AsyncMock, side_effect=[SAMPLE_BY_RESULT, SAMPLE_BY_RISK]):
                with patch("backend.retrieval.food_inspections.socrata_get", new_callable=AsyncMock, return_value=SAMPLE_DETAIL):
                    result = await food_inspections_by_community_area(25)
                    assert "by_result" in result
                    assert "by_risk" in result
                    assert "detail" in result

    @pytest.mark.asyncio
    async def test_no_bounds_returns_empty(self):
        with patch("backend.retrieval.food_inspections.community_area_bounds", return_value=None):
            result = await food_inspections_by_community_area(99)
            assert result == {"by_result": [], "by_risk": [], "detail": []}
