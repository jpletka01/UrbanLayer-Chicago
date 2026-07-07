"""Unit tests for the assessor address→PIN fallback resolver (3723-97qp).

Contract mirrors address_points.address_to_pin: a PIN only on a *unique
confident* match. The dataset stores the full address string, so a coarse `like`
prefix is re-parsed per row and kept only on an exact number+direction+name
match; no-match / unparseable / multi-PIN / error all return None.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property import parcel_addresses

pytestmark = pytest.mark.asyncio


def _patch_socrata(rows=None, *, raises=None):
    if raises is not None:
        return patch.object(
            parcel_addresses, "socrata_get", new=AsyncMock(side_effect=raises)
        )
    return patch.object(
        parcel_addresses, "socrata_get", new=AsyncMock(return_value=rows or [])
    )


async def test_unique_match_returns_pin():
    """481 W Deming Pl → unique 14283190070000 (the parcel 78yw-iddh misses)."""
    rows = [{"pin": "14283190070000", "prop_address_full": "481 W DEMING PL"}]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "14283190070000"


async def test_unparseable_address_returns_none_without_querying():
    mock = AsyncMock(return_value=[])
    with patch.object(parcel_addresses, "socrata_get", new=mock):
        result = await parcel_addresses.assessor_address_to_pin("not an address")
    assert result is None
    mock.assert_not_called()


async def test_zero_rows_returns_none():
    with _patch_socrata([]):
        result = await parcel_addresses.assessor_address_to_pin("2400 N Milwaukee Ave")
    assert result is None


async def test_reparse_guard_filters_prefix_collision_street():
    """A like-matched but different street ("DEMINGWOOD") is dropped by the
    exact-component re-parse → the real match stays unique."""
    rows = [
        {"pin": "14283190070000", "prop_address_full": "481 W DEMING PL"},
        {"pin": "99999999999999", "prop_address_full": "481 W DEMINGWOOD AVE"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "14283190070000"


async def test_reparse_guard_filters_different_number():
    """Defensive: a stray different-number row (e.g. 4810) is dropped."""
    rows = [
        {"pin": "14283190070000", "prop_address_full": "481 W DEMING PL"},
        {"pin": "88888888888888", "prop_address_full": "4810 W DEMING PL"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "14283190070000"


async def test_multi_distinct_pins_returns_none():
    """Two distinct PINs for the same exact components (multi-parcel/condo) → None."""
    rows = [
        {"pin": "17094120130000", "prop_address_full": "333 W WACKER DR"},
        {"pin": "17094120140000", "prop_address_full": "333 W WACKER DR"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("333 W Wacker Dr")
    assert result is None


async def test_same_pin_multiple_units_treated_as_single_match():
    """Several rows, one PIN (unit suffixes on one parcel) → confident single match."""
    rows = [
        {"pin": "14283190070000", "prop_address_full": "481 W DEMING PL"},
        {"pin": "14-28-319-007-0000", "prop_address_full": "481 W DEMING PL UNIT 2"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "14283190070000"


async def test_pin_normalized_to_14_digits():
    rows = [{"pin": "14-28-319-007-0000", "prop_address_full": "481 W DEMING PL"}]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "14283190070000"


async def test_socrata_error_returns_none():
    with _patch_socrata(raises=RuntimeError("portal down")):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result is None


async def test_query_shape_uses_abbrev_direction_city_and_like():
    """Lock the query: like on number+abbrev-direction+name, Chicago scope,
    newest-first order, NO hard year filter (a `year=<current>` equality missed
    addresses whose rows stop earlier — 1425 N Wells St ends at 2001)."""
    rows = [{"pin": "14283190070000", "prop_address_full": "481 W DEMING PL"}]
    mock = AsyncMock(return_value=rows)
    with patch.object(parcel_addresses, "socrata_get", new=mock):
        await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    args = mock.call_args.args
    params = args[1]
    where = params["$where"]
    assert "year=" not in where
    # abbreviated single-letter directional (the dataset stores "481 W DEMING PL")
    assert "like '481 W DEMING%'" in where
    # county-wide dataset scoped to Chicago (suburb street-name collisions)
    assert "upper(prop_address_city_name)='CHICAGO'" in where
    assert params["$select"] == "pin,prop_address_full,year"
    assert params["$order"] == "year DESC"
    assert "$limit" in params


async def test_newest_year_wins_over_historical_mapping():
    """A re-addressed parcel resolves to the CURRENT mapping — older-year rows
    pointing at a different PIN must not force a false multi-match."""
    rows = [
        {"pin": "11111111111111", "prop_address_full": "481 W DEMING PL", "year": "2026.0"},
        {"pin": "22222222222222", "prop_address_full": "481 W DEMING PL", "year": "2001"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result == "11111111111111"


async def test_historical_only_address_resolves_its_last_mapping():
    """An address whose rows stop in the past (1425 N Wells St → retired parcel)
    still returns that last PIN — the caller's Parcel Universe centroid
    requirement is what rejects a PIN that no longer exists."""
    rows = [
        {"pin": "17042050520000", "prop_address_full": "1425 N WELLS ST", "year": "2001"},
        {"pin": "17042050520000", "prop_address_full": "1425 N WELLS ST", "year": "2000"},
    ]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("1425 N Wells St")
    assert result == "17042050520000"


async def test_malformed_pin_rejected_not_padded():
    """Non-14-digit PINs are never repaired by padding (corrupt-PIN hazard)."""
    rows = [{"pin": "1428319007000", "prop_address_full": "481 W DEMING PL", "year": "2026"}]
    with _patch_socrata(rows):
        result = await parcel_addresses.assessor_address_to_pin("481 W Deming Pl")
    assert result is None
