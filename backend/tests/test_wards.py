"""Tests for ward boundary + alderman lookup (backend/retrieval/neighborhood/wards.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.neighborhood import wards


def _square(lon0, lat0, d=0.1):
    return {
        "type": "MultiPolygon",
        "coordinates": [[[
            [lon0, lat0], [lon0 + d, lat0], [lon0 + d, lat0 + d], [lon0, lat0 + d], [lon0, lat0],
        ]]],
    }


BOUNDARY_ROWS = [
    {"ward": "27", "the_geom": _square(-87.7, 41.85)},
    {"ward": "42", "the_geom": _square(-87.7, 42.00)},
]

OFFICE_ROWS = [
    # website mirrors the real wire shape: Socrata URL columns are objects,
    # not strings ({"url": ...}) — this sank the whole NeighborhoodSummary
    # via WardInfo validation until normalized (found live 2026-07-02).
    {"ward": "27", "alderman": "Walter Burnett, Jr.", "ward_phone": "(312) 432-1995",
     "email": "ward27@cityofchicago.org", "website": {"url": "https://www.ward27chicago.com"}},
]


@pytest.fixture
async def loaded_wards():
    with patch("backend.retrieval.neighborhood.wards.socrata_get",
               new=AsyncMock(side_effect=[BOUNDARY_ROWS, OFFICE_ROWS])):
        await wards.preload()
    yield
    wards._wards = None
    wards._offices = None


@pytest.mark.asyncio
async def test_ward_by_point_with_office(loaded_wards):
    info = wards.ward_by_point(41.90, -87.65)
    assert info is not None
    assert info["ward"] == 27
    assert info["alderman"] == "Walter Burnett, Jr."
    assert info["phone"] == "(312) 432-1995"
    assert info["website"] == "https://www.ward27chicago.com"


@pytest.mark.asyncio
async def test_ward_by_point_without_office_row(loaded_wards):
    info = wards.ward_by_point(42.05, -87.65)
    assert info is not None
    assert info["ward"] == 42
    assert info["alderman"] is None


@pytest.mark.asyncio
async def test_ward_by_point_outside_all(loaded_wards):
    assert wards.ward_by_point(40.0, -90.0) is None


def test_ward_by_point_before_preload():
    wards._wards = None
    wards._offices = None
    assert wards.ward_by_point(41.90, -87.65) is None
