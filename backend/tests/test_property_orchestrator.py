"""Tests for the property domain orchestrator."""

import datetime

import pytest
from unittest.mock import AsyncMock, patch

from backend.models import PropertySummary
from backend.retrieval.property import property_domain, _build_summary, _safe_int, _safe_float


SAMPLE_PARCEL = {
    "pin14": "14241020170000",
    "bldg_class": "2-11",
    "bldg_sqft": 2400,
    "land_sqft": 3200,
    "total_value": 350000,
    "address": "443 W WRIGHTWOOD AVE",
}

# Mirrors the real x54s-btds schema: `char_apts` (not char_units), `char_yrblt`
# (age derived from it), `char_air`; there is no char_age/char_class_description.
SAMPLE_CHARS = {
    "pin": "14241020170000",
    "year": "2024",
    "char_bldg_sf": "2600",
    "char_land_sf": "3200",
    "char_ncu": "3",
    "char_apts": "2",
    "char_rooms": "8",
    "char_beds": "4",
    "char_fbath": "2",
    "char_hbath": "1",
    "char_yrblt": "1929",
}

# Real uzyt-m557 schema uses `year`, not `tax_year`.
SAMPLE_ASSESSMENTS = [
    {"year": "2024", "class": "211", "mailed_land": "10000", "mailed_bldg": "35000", "mailed_tot": "45000"},
    {"year": "2023", "class": "211", "mailed_land": "9500", "mailed_bldg": "33000", "mailed_tot": "42500"},
]

SAMPLE_SALES = [
    {"sale_date": "2023-06-15T00:00:00.000", "sale_price": "450000", "deed_type": "Warranty"},
    {"sale_date": "2018-03-01T00:00:00.000", "sale_price": "320000", "deed_type": "Warranty"},
]


@pytest.mark.asyncio
async def test_assembles_full_summary():
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert isinstance(result, PropertySummary)
        assert result.pin14 == "14241020170000"
        assert result.address == "443 W WRIGHTWOOD AVE"
        assert result.bldg_sqft == 2600  # CCAO overrides GIS
        assert result.stories == 3
        assert result.units == 2
        assert result.rooms == 8
        assert result.bedrooms == 4
        assert result.full_baths == 2
        assert result.half_baths == 1
        assert result.year_built == 1929
        assert result.bldg_age == datetime.date.today().year - 1929
        assert result.tax_exempt is False
        assert result.total_assessed_value == 45000.0
        assert len(result.assessment_history) == 2
        assert result.assessment_history[0].year == 2024
        assert result.assessment_history[0].total == 45000.0
        assert len(result.sales_history) == 2
        assert result.sales_history[0].price == 450000.0


@pytest.mark.asyncio
async def test_returns_none_when_no_parcel():
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel:
        mock_parcel.return_value = None
        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)
        assert result is None


@pytest.mark.asyncio
async def test_handles_partial_ccao_failure():
    """If one CCAO query fails, the others still contribute."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.side_effect = Exception("timeout")
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2400  # falls back to GIS value
        assert result.stories is None  # no CCAO enrichment
        assert len(result.assessment_history) == 2
        assert len(result.sales_history) == 2


@pytest.mark.asyncio
async def test_handles_all_ccao_failure():
    """If all CCAO queries fail, we still get GIS parcel data."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.side_effect = Exception("timeout")
        mock_assess.side_effect = Exception("timeout")
        mock_sales.side_effect = Exception("timeout")

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2400
        assert result.assessment_history == []
        assert result.sales_history == []


@pytest.mark.asyncio
async def test_pin14_passed_to_ccao_queries():
    """Verify the PIN from parcel lookup is forwarded to all CCAO sub-queries."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = {"pin14": "99998887770000", "address": "TEST"}
        mock_chars.return_value = None
        mock_assess.return_value = []
        mock_sales.return_value = []

        client = AsyncMock()
        await property_domain(41.93, -87.64, client=client)

        mock_chars.assert_awaited_once()
        assert mock_chars.call_args[0][0] == "99998887770000"
        mock_assess.assert_awaited_once()
        assert mock_assess.call_args[0][0] == "99998887770000"
        mock_sales.assert_awaited_once()
        assert mock_sales.call_args[0][0] == "99998887770000"


def test_safe_int_handles_various_inputs():
    assert _safe_int("2400") == 2400
    assert _safe_int("2400.5") == 2400
    assert _safe_int(2400) == 2400
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("N/A") is None


def test_safe_float_handles_various_inputs():
    assert _safe_float("45000.50") == 45000.50
    assert _safe_float(45000) == 45000.0
    assert _safe_float(None) is None
    assert _safe_float("") is None
    assert _safe_float("N/A") is None


@pytest.mark.asyncio
async def test_development_feasibility_skips_assessments_and_sales():
    """workflow=development_feasibility should only fetch characteristics."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, workflow="development_feasibility", client=client)

        assert result is not None
        assert result.pin14 == "14241020170000"
        assert result.bldg_sqft == 2600
        mock_chars.assert_awaited_once()
        mock_assess.assert_not_awaited()
        mock_sales.assert_not_awaited()
        assert result.assessment_history == []
        assert result.sales_history == []


@pytest.mark.asyncio
async def test_general_workflow_fetches_everything():
    """workflow=general (default) should fetch all sub-queries."""
    with patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock) as mock_parcel, \
         patch("backend.retrieval.property.get_characteristics", new_callable=AsyncMock) as mock_chars, \
         patch("backend.retrieval.property.get_assessments", new_callable=AsyncMock) as mock_assess, \
         patch("backend.retrieval.property.get_sales", new_callable=AsyncMock) as mock_sales:

        mock_parcel.return_value = SAMPLE_PARCEL
        mock_chars.return_value = SAMPLE_CHARS
        mock_assess.return_value = SAMPLE_ASSESSMENTS
        mock_sales.return_value = SAMPLE_SALES

        client = AsyncMock()
        result = await property_domain(41.93, -87.64, workflow="general", client=client)

        assert result is not None
        mock_chars.assert_awaited_once()
        mock_assess.assert_awaited_once()
        mock_sales.assert_awaited_once()
        assert len(result.assessment_history) == 2
        assert len(result.sales_history) == 2


def test_build_summary_assessment_fallback_values():
    """Assessment should fall back from mailed to certified to board values."""
    parcel = {"pin14": "12345678901234", "address": "TEST"}
    assessments = [
        {"tax_year": "2024", "certified_tot": "40000"},
        {"tax_year": "2023", "board_tot": "38000"},
    ]
    summary = _build_summary(parcel, None, assessments, [])
    assert summary.assessment_history[0].total == 40000.0
    assert summary.assessment_history[1].total == 38000.0
    assert summary.total_assessed_value == 40000.0
