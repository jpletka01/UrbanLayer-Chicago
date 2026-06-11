"""R7: property_domain resolves by PIN when one is supplied (INV-2).

When an authoritative PIN is threaded in, the orchestrator must resolve the
parcel via `lookup_parcel_by_pin` (pure Socrata, GIS-independent) and must NOT
re-derive identity from coordinates. With no PIN, the coordinate path is
unchanged (regression guard). A supplied PIN whose row is missing degrades to
the coordinate lookup.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property import property_domain

pytestmark = pytest.mark.asyncio

PIN_PARCEL = {
    "pin14": "14331030110000",
    "bldg_class": "205",
    "bldg_sqft": None,
    "land_sqft": None,
    "total_value": None,
    "address": None,
    "geometry": None,
    "zip_code": "60614",
    "township_name": "Lake View",
    "nbhd_code": None,
    "tax_code": None,
}
COORD_PARCEL = {**PIN_PARCEL, "pin14": "14331030120000", "bldg_class": "391"}


def _patches():
    return (
        patch("backend.retrieval.property.lookup_parcel_by_pin", new_callable=AsyncMock),
        patch("backend.retrieval.property.lookup_parcel", new_callable=AsyncMock),
        patch("backend.retrieval.property.get_characteristics", new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.get_assessments", new=AsyncMock(return_value=[])),
        patch("backend.retrieval.property.get_sales", new=AsyncMock(return_value=[])),
        # The tax path queries an 8.8GB PTAXSIM SQLite DB — irrelevant to PIN
        # routing and unavailable/slow in unit context. Stub it out.
        patch("backend.retrieval.property.tax_estimate.estimate_tax", new=AsyncMock(return_value=None)),
    )


async def test_pin_resolves_by_pin_and_skips_coord_lookup():
    p_bypin, p_coord, p_ch, p_as, p_sa, p_tax = _patches()
    with p_bypin as by_pin, p_coord as by_coord, p_ch, p_as, p_sa, p_tax:
        by_pin.return_value = PIN_PARCEL
        result = await property_domain(41.93, -87.64, pin="14331030110000", client=AsyncMock())
    assert result is not None
    assert result.pin14 == "14331030110000"
    by_pin.assert_awaited_once()
    by_coord.assert_not_awaited()


async def test_missing_pin_row_degrades_to_coord_lookup():
    p_bypin, p_coord, p_ch, p_as, p_sa, p_tax = _patches()
    with p_bypin as by_pin, p_coord as by_coord, p_ch, p_as, p_sa, p_tax:
        by_pin.return_value = None
        by_coord.return_value = COORD_PARCEL
        result = await property_domain(41.93, -87.64, pin="00000000000000", client=AsyncMock())
    assert result is not None
    assert result.pin14 == "14331030120000"
    by_pin.assert_awaited_once()
    by_coord.assert_awaited_once()


async def test_no_pin_uses_coord_path_only():
    p_bypin, p_coord, p_ch, p_as, p_sa, p_tax = _patches()
    with p_bypin as by_pin, p_coord as by_coord, p_ch, p_as, p_sa, p_tax:
        by_coord.return_value = COORD_PARCEL
        result = await property_domain(41.93, -87.64, client=AsyncMock())
    assert result is not None
    assert result.pin14 == "14331030120000"
    by_coord.assert_awaited_once()
    by_pin.assert_not_awaited()
