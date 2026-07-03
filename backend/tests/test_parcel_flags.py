"""Tests for parcel distress/opportunity flags (backend/retrieval/property/parcel_flags.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.parcel_flags import get_parcel_flags


def _responses(tax_sale=(), scavenger=(), city_owned=(), str_prohibited=(), scofflaw=()):
    """side_effect list in the coros-dict insertion order (scofflaw last, only
    present when coords were passed)."""
    return [list(tax_sale), list(scavenger), list(city_owned), list(str_prohibited), list(scofflaw)]


@pytest.mark.asyncio
async def test_all_clear_returns_none_and_caches():
    with patch("backend.retrieval.property.parcel_flags.socrata_get",
               new=AsyncMock(side_effect=_responses())) as mock:
        assert await get_parcel_flags("20331000020000", 41.75, -87.64) is None
        # second call served from the known-clear cache — no new queries
        assert await get_parcel_flags("20331000020000", 41.75, -87.64) is None
        assert mock.await_count == 5


@pytest.mark.asyncio
async def test_flags_populated():
    with patch("backend.retrieval.property.parcel_flags.socrata_get",
               new=AsyncMock(side_effect=_responses(
                   tax_sale=[{"tax_sale_year": "2013", "sold_at_sale": "N"},
                             {"tax_sale_year": "2012", "sold_at_sale": "N"}],
                   city_owned=[{"property_status": "Owned by City",
                                "sales_status": "Available",
                                "application_url": {"url": "https://chiblockbuilder.com/x"}}],
                   str_prohibited=[{"pin": "20-33-100-002-0000-1001"}],
                   scofflaw=[{"address": "741 W 79TH ST",
                              "circuit_court_case_number": "18M1400123",
                              "defendant_owner": "X LLC"}],
               ))):
        flags = await get_parcel_flags("20331000020000", 41.75, -87.64)

    assert flags is not None
    assert flags.tax_sale_years == [2012, 2013]
    assert flags.city_owned and flags.city_owned_sales_status == "Available"
    assert flags.city_owned_application_url == "https://chiblockbuilder.com/x"
    assert flags.str_prohibited
    assert flags.scofflaw and flags.scofflaw_case == "18M1400123"


@pytest.mark.asyncio
async def test_partial_failure_still_reports_other_flags():
    with patch("backend.retrieval.property.parcel_flags.socrata_get",
               new=AsyncMock(side_effect=[
                   Exception("boom"), [], [{"property_status": "Owned by City"}], [], [],
               ])):
        flags = await get_parcel_flags("16121000010000", 41.9, -87.7)
    assert flags is not None
    assert flags.city_owned
    assert flags.tax_sale_years == []


@pytest.mark.asyncio
async def test_no_coords_skips_scofflaw():
    with patch("backend.retrieval.property.parcel_flags.socrata_get",
               new=AsyncMock(side_effect=[[], [], [], []])) as mock:
        assert await get_parcel_flags("16121000010000") is None
    assert mock.await_count == 4