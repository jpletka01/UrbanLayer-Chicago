"""Tests for Chicago Energy Benchmarking retrieval (backend/retrieval/property/energy.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.energy import get_energy_benchmark


def _row(**over) -> dict:
    base = {
        "id": "251245",
        "data_year": "2022",
        "reporting_status": "Submitted Data",
        "chicago_energy_rating": "3.5",
        "energy_star_score": "74",
        "gross_floor_area_buildings_sq_ft": "249095",
        "year_built": "1927",
        "primary_property_type": "Multifamily Housing",
        "site_eui_kbtu_sq_ft": "88.5",
        "ghg_intensity_kg_co2e_sq_ft": "5.8",
        "latitude": "41.7689",
        "longitude": "-87.5858",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_latest_submitted_row_wins():
    rows = [
        _row(data_year="2023", reporting_status="Not Submitted",
             chicago_energy_rating="0", energy_star_score=None),
        _row(data_year="2022", reporting_status="Submitted"),  # bare variant is real
        _row(data_year="2021", chicago_energy_rating="2.0"),
    ]
    with patch("backend.retrieval.property.energy.socrata_get",
               new=AsyncMock(return_value=rows)):
        r = await get_energy_benchmark(41.7689, -87.5858)
    assert r is not None
    assert r["chicago_energy_rating"] == 3.5
    assert r["energy_star_score"] == 74
    assert r["gross_floor_area"] == 249095
    assert r["year_built"] == 1927
    assert r["data_year"] == 2022
    assert r["not_submitted"] is False


@pytest.mark.asyncio
async def test_nearest_property_id_wins_over_adjacent_tower():
    rows = [
        _row(id="999", latitude="41.7695", longitude="-87.5865",
             gross_floor_area_buildings_sq_ft="500000"),  # ~70m away
        _row(id="251245", latitude="41.76891", longitude="-87.58581"),
    ]
    with patch("backend.retrieval.property.energy.socrata_get",
               new=AsyncMock(return_value=rows)):
        r = await get_energy_benchmark(41.7689, -87.5858)
    assert r is not None
    assert r["gross_floor_area"] == 249095


@pytest.mark.asyncio
async def test_non_submitter_zero_rating_is_compliance_not_score():
    rows = [_row(reporting_status="Not Submitted", chicago_energy_rating="0",
                 energy_star_score=None, site_eui_kbtu_sq_ft=None)]
    with patch("backend.retrieval.property.energy.socrata_get",
               new=AsyncMock(return_value=rows)):
        r = await get_energy_benchmark(41.7689, -87.5858)
    assert r is not None
    assert r["chicago_energy_rating"] is None
    assert r["not_submitted"] is True
    assert r["gross_floor_area"] == 249095  # GFA still usable as a fill


@pytest.mark.asyncio
async def test_none_when_not_covered():
    """<50k-sqft buildings aren't in the dataset — expected absence."""
    with patch("backend.retrieval.property.energy.socrata_get",
               new=AsyncMock(return_value=[])) as mock:
        assert await get_energy_benchmark(41.9, -87.7) is None
        assert await get_energy_benchmark(41.9, -87.7) is None  # negative-cached
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_none_on_transport_failure():
    with patch("backend.retrieval.property.energy.socrata_get",
               new=AsyncMock(side_effect=Exception("boom"))):
        assert await get_energy_benchmark(41.9, -87.7) is None
