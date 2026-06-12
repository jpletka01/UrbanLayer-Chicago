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
    rows = [{"pin": "14283180570000", "lat": "41.93060", "long": "-87.64083"}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result == {
        "pin14": "14283180570000",
        "lat": 41.93060,
        "lon": -87.64083,
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
        {"pin": "14283180570000", "lat": "41.9", "long": "-87.6"},
        {"pin": "14283180580000", "lat": "41.9", "long": "-87.6"},
    ]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_duplicate_same_pin_treated_as_single_match():
    """Two rows, same PIN (duplicate point) → still a confident single match."""
    rows = [
        {"pin": "14283180570000", "lat": "41.93060", "long": "-87.64083"},
        {"pin": "14-28-318-057-0000", "lat": "41.93060", "long": "-87.64083"},
    ]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is not None
    assert result["pin14"] == "14283180570000"


async def test_pin_is_normalized_to_14_digits():
    rows = [{"pin": "14-28-318-057-0000", "lat": "41.9", "long": "-87.6"}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result["pin14"] == "14283180570000"


async def test_socrata_error_returns_none():
    with _patch_socrata(raises=RuntimeError("portal down")):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_match_with_null_coords_returns_none():
    """Authoritative PIN but unusable point → None (caller will geocode)."""
    rows = [{"pin": "14283180570000", "lat": None, "long": None}]
    with _patch_socrata(rows):
        result = await address_points.address_to_pin("443 W Wrightwood Ave")
    assert result is None


async def test_query_uses_address_point_columns_and_limit():
    """Lock the query shape: parsed components + the `long` select + $limit guard."""
    rows = [{"pin": "14283180570000", "lat": "41.9", "long": "-87.6"}]
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


# --------------------------------------------------------------------------- #
# pin_to_address — display-only PIN → address reverse lookup
# --------------------------------------------------------------------------- #

async def test_pin_to_address_formats_display_address():
    """cmpaddabrv is ALL-CAPS; the result is display-cased."""
    rows = [{"cmpaddabrv": "642 W BELDEN AVE"}]
    with _patch_socrata(rows):
        result = await address_points.pin_to_address("14331030110000")
    assert result == "642 W Belden Ave"


async def test_pin_to_address_no_rows_returns_none():
    with _patch_socrata([]):
        result = await address_points.pin_to_address("14283190070000")
    assert result is None


async def test_pin_to_address_error_returns_none():
    with _patch_socrata(raises=RuntimeError("portal down")):
        result = await address_points.pin_to_address("14331030110000")
    assert result is None


async def test_pin_to_address_query_shape():
    """Lock the query: pin filter, display column, deterministic order, limit 1."""
    mock = AsyncMock(return_value=[{"cmpaddabrv": "642 W BELDEN AVE"}])
    with patch.object(address_points, "socrata_get", new=mock):
        await address_points.pin_to_address("14331030110000")
    params = mock.call_args.args[1]
    assert params["$where"] == "pin='14331030110000'"
    assert params["$select"] == "cmpaddabrv"
    assert params["$order"] == "addrnocom"
    assert params["$limit"] == 1


async def test_format_display_address_cases():
    f = address_points._format_display_address
    assert f("642 W BELDEN AVE") == "642 W Belden Ave"
    assert f("2400 N MILWAUKEE AVE") == "2400 N Milwaukee Ave"
    assert f("123 E 63RD ST") == "123 E 63rd St"
    assert f("1 S STATE ST") == "1 S State St"
