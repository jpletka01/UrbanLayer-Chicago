"""Tests for CCAO parcel sales history lookup."""

import pytest
from unittest.mock import patch, AsyncMock

from backend.retrieval.property.sales import get_sales


@pytest.fixture
def mock_socrata(mock_settings):
    with patch("backend.retrieval.property.sales.get_settings", return_value=mock_settings), \
         patch("backend.retrieval.property.sales.socrata_get", new_callable=AsyncMock) as mock_get:
        yield mock_get


@pytest.mark.asyncio
async def test_returns_sales_list(mock_socrata):
    mock_socrata.return_value = [
        {"pin": "14241020170000", "sale_date": "2023-06-15", "sale_price": "450000", "deed_type": "Warranty"},
        {"pin": "14241020170000", "sale_date": "2018-03-01", "sale_price": "320000", "deed_type": "Warranty"},
    ]
    result = await get_sales("14241020170000")
    assert len(result) == 2
    assert result[0]["sale_price"] == "450000"


@pytest.mark.asyncio
async def test_returns_empty_list_for_no_data(mock_socrata):
    mock_socrata.return_value = []
    result = await get_sales("14241020170000")
    assert result == []


@pytest.mark.asyncio
async def test_handles_socrata_error(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata error")
    result = await get_sales("14241020170000")
    assert result == []


@pytest.mark.asyncio
async def test_negative_cache_prevents_retry(mock_socrata):
    mock_socrata.side_effect = Exception("Socrata error")
    result1 = await get_sales("99999999999999")
    assert result1 == []
    assert mock_socrata.call_count == 1

    mock_socrata.reset_mock()
    result2 = await get_sales("99999999999999")
    assert result2 == []
    assert mock_socrata.call_count == 0
