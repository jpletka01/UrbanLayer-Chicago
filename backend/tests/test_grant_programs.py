from unittest.mock import AsyncMock, patch

import pytest

from backend.assembler import _grant_program_summary
from backend.retrieval.incentives.grant_programs import grant_programs_by_community_area


SAMPLE_SBIF = [
    {
        "project_name": "Test Pizza Place",
        "incentive_amount": "50000.00",
        "total_project_cost": "120000.00",
        "property_type": "Commercial",
        "project_description": "Roof, HVAC renovation.",
        "completion_date": "2022-03-15T00:00:00.000",
        "tif_district": "Some TIF",
    },
    {
        "project_name": "Corner Store Rehab",
        "incentive_amount": "25000.00",
        "total_project_cost": "60000.00",
        "property_type": "Commercial",
        "project_description": "Signage and storefront.",
        "completion_date": "2021-06-01T00:00:00.000",
        "tif_district": "Another TIF",
    },
]

SAMPLE_NOF = [
    {
        "project_name": "Community Arts Center",
        "incentive_amount": "200000.00",
        "total_project_cost": "500000.00",
        "property_type": "Mixed-use",
        "project_description": "Rehab vacant building into arts space.",
        "completion_date": "2023-01-20T00:00:00.000",
    },
]


class TestGrantProgramSummary:
    def test_basic(self):
        data = {"sbif": SAMPLE_SBIF, "nof_large": SAMPLE_NOF, "nof_small": []}
        for row in data["sbif"]:
            row["_program"] = "SBIF"
        for row in data["nof_large"]:
            row["_program"] = "NOF"
        result = _grant_program_summary(data)
        assert result is not None
        assert result.total_projects == 3
        assert result.total_funding == 275000.0
        assert result.by_program["SBIF"] == 2
        assert result.by_program["NOF"] == 1
        assert len(result.recent_projects) == 3
        assert result.recent_projects[0].name == "Community Arts Center"
        assert result.recent_projects[0].date == "2023-01-20"

    def test_empty_data(self):
        result = _grant_program_summary({"sbif": [], "nof_large": [], "nof_small": []})
        assert result is None

    def test_missing_keys(self):
        result = _grant_program_summary({})
        assert result is None

    def test_invalid_amounts_handled(self):
        data = {
            "sbif": [{"project_name": "X", "incentive_amount": "not_a_number",
                       "_program": "SBIF", "completion_date": "2023-01-01T00:00:00.000"}],
            "nof_large": [],
            "nof_small": [],
        }
        result = _grant_program_summary(data)
        assert result is not None
        assert result.total_projects == 1
        assert result.total_funding == 0.0


class TestGrantProgramsRetrieval:
    @pytest.mark.asyncio
    async def test_returns_data(self):
        with patch(
            "backend.retrieval.incentives.grant_programs.socrata_get",
            new_callable=AsyncMock,
            side_effect=[SAMPLE_SBIF, SAMPLE_NOF, []],
        ):
            result = await grant_programs_by_community_area("West Town")
            assert "sbif" in result
            assert "nof_large" in result
            assert "nof_small" in result
            assert len(result["sbif"]) == 2
            assert result["sbif"][0]["_program"] == "SBIF"

    @pytest.mark.asyncio
    async def test_handles_api_failure(self):
        with patch(
            "backend.retrieval.incentives.grant_programs.socrata_get",
            new_callable=AsyncMock,
            side_effect=[Exception("API error"), [], []],
        ):
            result = await grant_programs_by_community_area("West Town")
            assert result["sbif"] == []
            assert result["nof_large"] == []
