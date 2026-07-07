"""Tests for building-fact fallbacks (backend/retrieval/property/building_facts.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.building_facts import (
    get_commercial_facts,
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
        facts = await get_commercial_facts("17161020270000")
    assert facts["bldg_sqft"] == 252829 + 492800


@pytest.mark.asyncio
async def test_commercial_none_when_no_rows():
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=[])):
        assert await get_commercial_facts("17161020270000") is None


@pytest.mark.asyncio
async def test_commercial_fields_use_per_field_newest_year():
    """A newer vintage carrying yearbuilt/tot_units but NULL bldgsf must not
    erase the sqft an older vintage holds (six class-318 panel parcels lost
    bldg_sqft when every field was pinned to one latest year, 2026-07-07)."""
    rows = [
        {"yearbuilt": "1920", "tot_units": "48", "year": "2024",
         "keypin": "14-17-404-024-0000", "pins": "14-17-404-024-0000"},
        {"bldgsf": "39000", "yearbuilt": "1921", "tot_units": "48", "year": "2021",
         "keypin": "14-17-404-024-0000", "pins": "14-17-404-024-0000"},
    ]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_commercial_facts("14174040240000")
    assert facts == {"bldg_sqft": 39000, "year_built": 1920, "units": 48}


@pytest.mark.asyncio
async def test_commercial_year_built_from_principal_building():
    """On a multi-building unit the LARGEST structure's vintage is what
    "built in ..." should describe; latest year only."""
    rows = [
        {"bldgsf": "1000", "yearbuilt": "1999", "year": "2024"},
        {"bldgsf": "90000", "yearbuilt": "1987", "year": "2024"},
        {"bldgsf": "90000", "yearbuilt": "1902", "year": "2021"},
    ]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_commercial_facts("17161020270000")
    assert facts["year_built"] == 1987


@pytest.mark.asyncio
async def test_commercial_units_only_for_single_pin_economic_unit():
    """tot_units describes the WHOLE economic unit — a member parcel of a
    multi-PIN complex must not be asserted to hold the complex's units
    (Presidential Towers: 2,346 on every member PIN)."""
    multi = [{
        "bldgsf": "492800", "tot_units": "2346", "year": "2024",
        "keypin": "17-16-102-027-0000",
        "pins": "17-16-101-023-0000, 17-16-102-027-0000",
    }]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=multi)):
        facts = await get_commercial_facts("17161010230000")
    assert facts["units"] is None

    single = [{
        "bldgsf": "57301", "tot_units": "80", "yearbuilt": "1928", "year": "2024",
        "keypin": "16-17-200-001-0000", "pins": "16-17-200-001-0000",
    }]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=single)):
        facts = await get_commercial_facts("16172000010000")
    assert facts == {"bldg_sqft": 57301, "year_built": 1928, "units": 80}


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
async def test_footprint_point_in_parcel_filters_neighbor():
    """With the parcel polygon, only footprints whose own center is INSIDE the
    parcel count — the neighbor's abutting building (center outside) is
    excluded even though it falls in the query circle."""
    parcel = {
        "type": "Polygon",
        "coordinates": [[[-87.641, 41.930], [-87.640, 41.930],
                         [-87.640, 41.931], [-87.641, 41.931],
                         [-87.641, 41.930]]],
    }
    inside = {
        "type": "Polygon",
        "coordinates": [[[-87.6407, 41.9303], [-87.6403, 41.9303],
                         [-87.6403, 41.9307], [-87.6407, 41.9307],
                         [-87.6407, 41.9303]]],
    }
    neighbor = {  # centered well east of the parcel's edge
        "type": "Polygon",
        "coordinates": [[[-87.6399, 41.9303], [-87.6395, 41.9303],
                         [-87.6395, 41.9307], [-87.6399, 41.9307],
                         [-87.6399, 41.9303]]],
    }
    rows = [
        {"stories": "9", "year_built": "1980", "bldg_sq_fo": "0",
         "bldg_statu": "ACTIVE", "the_geom": neighbor},
        {"stories": "3", "year_built": "1928", "bldg_sq_fo": "0",
         "bldg_statu": "ACTIVE", "the_geom": inside},
    ]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_footprint_facts(
            41.9305, -87.6405, parcel_geojson=parcel)
    assert facts == {"stories": 3, "year_built": 1928, "bldg_sqft": None}


@pytest.mark.asyncio
async def test_footprint_point_in_parcel_no_contained_returns_none():
    """A polygon-matched query with no contained footprint must NOT fall back
    to nearest-circle ranking (that reintroduces the neighbor grab)."""
    parcel = {
        "type": "Polygon",
        "coordinates": [[[-87.641, 41.930], [-87.640, 41.930],
                         [-87.640, 41.931], [-87.641, 41.931],
                         [-87.641, 41.930]]],
    }
    neighbor = {
        "type": "Polygon",
        "coordinates": [[[-87.6399, 41.9303], [-87.6395, 41.9303],
                         [-87.6395, 41.9307], [-87.6399, 41.9307],
                         [-87.6399, 41.9303]]],
    }
    rows = [{"stories": "9", "year_built": "1980", "bldg_sq_fo": "0",
             "bldg_statu": "ACTIVE", "the_geom": neighbor}]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_footprint_facts(
            41.9305, -87.6405, parcel_geojson=parcel)
    assert facts is None


@pytest.mark.asyncio
async def test_condo_chars_maps_unit_fields():
    rows = [{"char_unit_sf": "1150", "char_yrblt": "2007", "char_bedrooms": "2", "year": "2024"}]
    with patch("backend.retrieval.property.building_facts.socrata_get",
               new=AsyncMock(return_value=rows)):
        facts = await get_condo_characteristics("17102140281234")
    assert facts == {"unit_sqft": 1150, "year_built": 2007, "bedrooms": 2}
