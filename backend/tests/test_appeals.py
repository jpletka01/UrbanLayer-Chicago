"""Tests for assessment appeal history (backend/retrieval/property/appeals.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.appeals import get_appeals


ASSESSOR_ROWS = [
    {"year": "2024", "mailed_tot": "50000", "certified_tot": "45000",
     "change": "change", "appeal_type": "RESIDENTIAL"},
]

BOR_ROWS = [
    {"tax_year": "2018", "assessor_totalvalue": "41850.0", "bor_totalvalue": "32500.0",
     "result": "Decrease", "appealtypedescription": "Overvaluation"},
    {"tax_year": "2015", "assessor_totalvalue": "41801.0", "bor_totalvalue": "41801.0",
     "result": "No Change", "appealtypedescription": "Overvaluation"},
]

# Includes the subject parcel (must be excluded from neighbor stats).
NEARBY_ROWS = [
    {"pin": "20331000020000", "tax_year": "2025", "assessor_totalvalue": "100", "bor_totalvalue": "50", "result": "Decrease"},
    {"pin": "20331000040000", "tax_year": "2025", "assessor_totalvalue": "10000", "bor_totalvalue": "9000", "result": "Decrease"},
    {"pin": "20331000050000", "tax_year": "2025", "assessor_totalvalue": "20000", "bor_totalvalue": "16000", "result": "Decrease"},
    {"pin": "20331000060000", "tax_year": "2024", "assessor_totalvalue": "5000", "bor_totalvalue": "5000", "result": "No Change"},
]


@pytest.mark.asyncio
async def test_appeals_merges_stages_and_neighbor_stats():
    with patch("backend.retrieval.property.appeals.socrata_get",
               new=AsyncMock(side_effect=[ASSESSOR_ROWS, BOR_ROWS, NEARBY_ROWS])):
        s = await get_appeals("20331000020000", 41.75, -87.64)

    assert s is not None
    assert [r.stage for r in s.records] == ["assessor", "board_of_review", "board_of_review"]
    assert s.records[0].year == 2024 and s.records[0].reduction_pct == 10.0
    bor_2018 = next(r for r in s.records if r.year == 2018)
    assert bor_2018.reduction_pct == pytest.approx(22.3, abs=0.1)
    # Subject pin excluded; 3 neighbors, 2 reductions (10% and 20% -> median 15)
    assert s.nearby_appeal_count == 3
    assert s.nearby_reduced_count == 2
    assert s.nearby_median_reduction_pct == 15.0
    assert s.nearby_window_years == [2024, 2025]
    assert s.nearby_capped is False


@pytest.mark.asyncio
async def test_appeals_nearby_capped_when_row_cap_saturated():
    """A full page of nearby rows means the true count is a floor, not exact."""
    from backend.retrieval.property.appeals import NEARBY_ROW_CAP
    capped_rows = [
        {"pin": f"2033100{i:04d}0000", "tax_year": "2025",
         "assessor_totalvalue": "10000", "bor_totalvalue": "9000", "result": "Decrease"}
        for i in range(NEARBY_ROW_CAP)
    ]
    with patch("backend.retrieval.property.appeals.socrata_get",
               new=AsyncMock(side_effect=[[], [], capped_rows])):
        s = await get_appeals("99999999990000", 41.75, -87.64)
    assert s is not None
    assert s.nearby_capped is True
    assert s.nearby_appeal_count == NEARBY_ROW_CAP


@pytest.mark.asyncio
async def test_appeals_none_when_empty_everywhere():
    with patch("backend.retrieval.property.appeals.socrata_get",
               new=AsyncMock(side_effect=[[], [], []])):
        assert await get_appeals("99999999990000", 41.75, -87.64) is None


@pytest.mark.asyncio
async def test_appeals_survives_partial_failures():
    with patch("backend.retrieval.property.appeals.socrata_get",
               new=AsyncMock(side_effect=[Exception("boom"), BOR_ROWS, Exception("boom")])):
        s = await get_appeals("20331000020000", 41.75, -87.64)
    assert s is not None
    assert len(s.records) == 2
    assert s.nearby_appeal_count == 0


@pytest.mark.asyncio
async def test_appeals_skips_nearby_without_coords():
    with patch("backend.retrieval.property.appeals.socrata_get",
               new=AsyncMock(side_effect=[ASSESSOR_ROWS, BOR_ROWS])) as mock:
        s = await get_appeals("20331000020000")
    assert s is not None
    assert mock.await_count == 2
    assert s.nearby_appeal_count == 0