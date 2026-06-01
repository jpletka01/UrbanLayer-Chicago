"""Tests for CCAO property characteristics lookup."""

import pytest
from unittest.mock import patch, AsyncMock

from backend.retrieval.property.characteristics import get_characteristics


@pytest.fixture
def mock_socrata(mock_settings):
    with patch("backend.retrieval.property.characteristics.get_settings", return_value=mock_settings), \
         patch("backend.retrieval.property.characteristics.socrata_get", new_callable=AsyncMock) as mock_get:
        yield mock_get


@pytest.mark.asyncio
async def test_returns_characteristics_for_valid_pin(mock_socrata):
    mock_socrata.return_value = [{
        "pin": "14241020170000",
        "year": "2024",
        "char_bldg_sf": "2400",
        "char_land_sf": "3200",
        "char_rooms": "8",
    }]
    result = await get_characteristics("14241020170000")
    assert result is not None
    assert result["char_bldg_sf"] == "2400"
    mock_socrata.assert_awaited_once()
    call_kwargs = mock_socrata.call_args
    assert call_kwargs.kwargs["base_url"] == "https://datacatalog.cookcountyil.gov/resource"


@pytest.mark.asyncio
async def test_returns_none_for_empty_result(mock_socrata):
    mock_socrata.return_value = []
    result = await get_characteristics("14241020170000")
    assert result is None


@pytest.mark.asyncio
async def test_handles_socrata_error(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata error")
    result = await get_characteristics("14241020170000")
    assert result is None
