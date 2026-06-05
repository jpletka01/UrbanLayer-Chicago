from unittest.mock import AsyncMock, patch

import pytest

from backend.assembler import _aro_housing_summary
from backend.retrieval.regulatory.aro_housing import aro_housing_by_community_area


SAMPLE_ROWS = [
    {
        "property_name": "Hairpin Lofts",
        "address": "3414 W. Diversey Ave.",
        "units": "25",
        "property_type": "Multifamily",
        "management_company": "Leasing Co.",
        "latitude": "41.93",
        "longitude": "-87.71",
    },
    {
        "property_name": "1000M",
        "address": "1000 S. Michigan Ave.",
        "units": "23",
        "property_type": "ARO",
        "management_company": "Willow Bridge",
        "latitude": "41.87",
        "longitude": "-87.62",
    },
]


class TestAROHousingSummary:
    def test_basic(self):
        result = _aro_housing_summary(SAMPLE_ROWS)
        assert result is not None
        assert result.total_projects == 2
        assert result.total_units == 48
        assert result.projects[0].name == "Hairpin Lofts"
        assert result.projects[0].units == 25

    def test_empty_rows(self):
        result = _aro_housing_summary([])
        assert result is None

    def test_missing_units(self):
        rows = [{"property_name": "Test", "address": "123 Main"}]
        result = _aro_housing_summary(rows)
        assert result is not None
        assert result.total_units == 0
        assert result.projects[0].units is None


class TestAROHousingRetrieval:
    @pytest.mark.asyncio
    async def test_returns_data(self):
        with patch(
            "backend.retrieval.regulatory.aro_housing.socrata_get",
            new_callable=AsyncMock,
            return_value=SAMPLE_ROWS,
        ):
            result = await aro_housing_by_community_area(21)
            assert len(result) == 2
            assert result[0]["property_name"] == "Hairpin Lofts"

    @pytest.mark.asyncio
    async def test_handles_api_failure(self):
        with patch(
            "backend.retrieval.regulatory.aro_housing.socrata_get",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await aro_housing_by_community_area(21)
            assert result == []
