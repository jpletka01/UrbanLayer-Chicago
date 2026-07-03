"""Tests for building-fact fallbacks (backend/retrieval/property/building_facts.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.building_facts import (
    get_commercial_building_sqft,
    get_condo_characteristics,
    get_footprint_facts,
)


@pytest.mark.asyncio
async def test_commercial_sqft_sums_latest_year_only():
    """An economic unit has one row PER BUILDING per year — sum the most
    recent year, never mix vintages."""
    rows = [
        {"bldgsf": "252829.0", "year": "2024"},
        {"bldgsf": "492800.0", "year": "2024"},
        {"bldgsf": "999999.0", "year": "2021"},
    ]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        sqft = await get_commercial_building_sqft("17161020270000")
    assert sqft == 252829 + 492800


@pytest.mark.asyncio
async def test_commercial_sqft_none_when_no_rows():
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=[])):
        assert await get_commercial_building_sqft("17161020270000") is None


@pytest.mark.asyncio
async def test_footprint_prefers_populated_row_and_filters_demolished():
    rows = [
        {"stories": "0", "year_built": "0", "bldg_sq_fo": "0.0", "bldg_statu": "ACTIVE"},
        {"stories": "2", "year_built": "1924", "bldg_sq_fo": "0.0", "bldg_statu": "ACTIVE"},
        {"stories": "9", "year_built": "1900", "bldg_sq_fo": "9999", "bldg_statu": "DEMOLISHED"},
    ]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_footprint_facts(41.75, -87.64)
    assert facts == {"stories": 2, "year_built": 1924, "bldg_sqft": None}


@pytest.mark.asyncio
async def test_footprint_rejects_implausible_year():
    rows = [{"stories": "1", "year_built": "3", "bldg_sq_fo": "0", "bldg_statu": "ACTIVE"}]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_footprint_facts(41.76, -87.65)
    assert facts is not None
    assert facts["year_built"] is None
    assert facts["stories"] == 1


@pytest.mark.asyncio
async def test_condo_chars_maps_unit_fields():
    rows = [{"char_unit_sf": "1150", "char_yrblt": "2007", "char_bedrooms": "2", "year": "2024"}]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_condo_characteristics("17102140281234")
    assert facts == {"unit_sqft": 1150, "year_built": 2007, "bedrooms": 2}
