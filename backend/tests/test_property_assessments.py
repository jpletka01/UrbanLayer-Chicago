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
async def test_a_failed_call_raises_instead_of_reading_as_no_assessments(mock_socrata):
    """WS6 M7: a failure is not "none on file". The property domain catches it and reports the gap."""
    mock_socrata.side_effect = Exception("Socrata error")
    with pytest.raises(Exception, match="Socrata error"):
        await get_assessments("14241020170000")


@pytest.mark.asyncio
async def test_a_failure_is_not_cached_but_an_empty_answer_is(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata error")
    with pytest.raises(Exception):
        await get_assessments("99999999999999")
    mock_socrata.side_effect = None
    mock_socrata.return_value = []
    assert await get_assessments("99999999999999") == []  # the retry ran: the failure was not remembered
    assert mock_socrata.call_count == 2
    mock_socrata.reset_mock()
    assert await get_assessments("99999999999999") == []  # a genuinely empty answer stays cached
    assert mock_socrata.call_count == 0
