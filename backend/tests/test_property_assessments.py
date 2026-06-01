"""Tests for CCAO assessment history lookup."""

import pytest
from unittest.mock import patch, AsyncMock

from backend.retrieval.property.assessments import get_assessments


@pytest.fixture
def mock_socrata(mock_settings):
    with patch("backend.retrieval.property.assessments.get_settings", return_value=mock_settings), \
         patch("backend.retrieval.property.assessments.socrata_get", new_callable=AsyncMock) as mock_get:
        yield mock_get


@pytest.mark.asyncio
async def test_returns_assessment_list(mock_socrata):
    mock_socrata.return_value = [
        {"pin": "14241020170000", "tax_year": "2024", "mailed_tot": "45000"},
        {"pin": "14241020170000", "tax_year": "2023", "mailed_tot": "42000"},
    ]
    result = await get_assessments("14241020170000")
    assert len(result) == 2
    assert result[0]["tax_year"] == "2024"


@pytest.mark.asyncio
async def test_returns_empty_list_for_no_data(mock_socrata):
    mock_socrata.return_value = []
    result = await get_assessments("14241020170000")
    assert result == []


@pytest.mark.asyncio
async def test_handles_socrata_error(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata error")
    result = await get_assessments("14241020170000")
    assert result == []
