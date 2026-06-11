"""Unit tests for the R7 authoritative address→PIN resolver (78yw-iddh).

Contract (truth-model §5, INV-3): return a PIN only on a *unique confident*
match; no-match / unparseable / multi-match / error all return None so the
caller falls through to the degraded path — never an arbitrary pick.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property import address_points

pytestmark = pytest.mark.asyncio


def _patch_socrata(rows=None, *, raises=None):
    if raises is not None:
        return patch.object(
            address_points, "socrata_get", new=AsyncMock(side_effect=raises)
        )
    return patch.object(
        address_points, "socrata_get", new=AsyncMock(return_value=rows or [])
    )


async def test_unique_match_returns_pin_and_coords():
    """One row → {pin14, lat, lon}; the dataset's `long` column maps to `lon`."""
    rows = [{"pin": "14283190070000", "lat": "41.92874", "long": "-87.64145"}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result == {
        "pin14": "14283190070000",
        "lat": 41.92874,
        "lon": -87.64145,
        "address": "443 W Wrightwood Ave",
    }


async def test_unparseable_address_returns_none_without_querying():
    """An unparseable string short-circuits before any Socrata call."""
    mock = AsyncMock(return_value=[])
    with patch.object(address_points, "socrata_get", new=mock):
        result = await address_points.address_to_pin("not an address")
    assert result is None
    mock.assert_not_called()


async def test_zero_rows_returns_none():
    with _patch_socrata([]):
        result = await address_points.address_to_pin("2400 N Milwaukee Ave")
    assert result is None


async def test_multi_match_distinct_pins_returns_none():
    """Two distinct PINs for the same address components is NOT confident."""
    rows = [
        {"pin": "14283190070000", "lat": "41.9", "long": "-87.6"},
        {"pin": "14283190080000", "lat": "41.9", "long": "-87.6"},
    ]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_duplicate_same_pin_treated_as_single_match():
    """Two rows, same PIN (duplicate point) → still a confident single match."""
    rows = [
        {"pin": "14283190070000", "lat": "41.92874", "long": "-87.64145"},
        {"pin": "14-28-319-007-0000", "lat": "41.92874", "long": "-87.64145"},
    ]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is not None
    assert result["pin14"] == "14283190070000"


async def test_pin_is_normalized_to_14_digits():
    rows = [{"pin": "14-28-319-007-0000", "lat": "41.9", "long": "-87.6"}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result["pin14"] == "14283190070000"


async def test_socrata_error_returns_none():
    with _patch_socrata(raises=RuntimeError("portal down")):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_match_with_null_coords_returns_none():
    """Authoritative PIN but unusable point → None (caller will geocode)."""
    rows = [{"pin": "14283190070000", "lat": None, "long": None}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_query_uses_address_point_columns_and_limit():
    """Lock the query shape: parsed components + the `long` select + $limit guard."""
    rows = [{"pin": "14283190070000", "lat": "41.9", "long": "-87.6"}]
    mock = AsyncMock(return_value=rows)
    with patch.object(address_points, "socrata_get", new=mock):
        await address_points.address_to_pin("443 W Wrightwood Ave")
    _, kwargs = mock.call_args
    args = mock.call_args.args
    params = args[1]
    where = params["$where"]
    assert "add_number='443'" in where
    # Direction matched in either single-letter or spelled-out form (78yw-iddh
    # stores the word, e.g. "WEST").
    assert "upper(st_predir) in ('W','WEST')" in where
    assert "upper(st_name)='WRIGHTWOOD'" in where
    assert params["$select"] == "pin,lat,long"
    assert "$limit" in params
