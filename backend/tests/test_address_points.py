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


# --- Reverse round-trip gate (parcel_address_matches) -----------------------
#
# Guards promotion of a fallback/nearest-centroid PIN to confirmed identity:
# accept only when the candidate parcel's own address points round-trip to the
# input on number + direction + street + side-of-street parity.


async def test_round_trip_accepts_exact_match():
    """642 W Belden's parcel carries a 642 W Belden address point → accept."""
    rows = [{"add_number": "642", "st_predir": "WEST", "st_name": "BELDEN"}]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("14331030110000", "642 W Belden Ave")
    assert ok is True


async def test_round_trip_rejects_wrong_side_neighbor_deming():
    """Orchestrator grabbed 470 W Deming for input 481 (even vs odd) → reject."""
    rows = [{"add_number": "470", "st_predir": "WEST", "st_name": "DEMING"}]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("14283180160000", "481 W Deming Pl")
    assert ok is False


async def test_round_trip_rejects_across_street_neighbor_milwaukee():
    """Orchestrator grabbed 2401/2403 N Milwaukee for input 2400 → reject."""
    rows = [
        {"add_number": "2401", "st_predir": "NORTH", "st_name": "MILWAUKEE"},
        {"add_number": "2403", "st_predir": "NORTH", "st_name": "MILWAUKEE"},
    ]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("13253220380000", "2400 N Milwaukee Ave")
    assert ok is False


async def test_round_trip_accepts_one_of_multi_address_parcel():
    """A multi-address parcel (2401-2403) matches when the input is one of them."""
    rows = [
        {"add_number": "2401", "st_predir": "NORTH", "st_name": "MILWAUKEE"},
        {"add_number": "2403", "st_predir": "NORTH", "st_name": "MILWAUKEE"},
    ]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("13253220380000", "2403 N Milwaukee Ave")
    assert ok is True


async def test_round_trip_rejects_direction_mismatch():
    """Same number + street but wrong directional → reject."""
    rows = [{"add_number": "642", "st_predir": "EAST", "st_name": "BELDEN"}]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("14331030110000", "642 W Belden Ave")
    assert ok is False


async def test_round_trip_handles_letter_direction_encoding():
    """78yw-iddh sometimes stores the directional as a single letter, not the word."""
    rows = [{"add_number": "642", "st_predir": "W", "st_name": "BELDEN"}]
    with _patch_socrata(rows):
        ok = await address_points.parcel_address_matches("14331030110000", "642 W Belden Ave")
    assert ok is True


async def test_round_trip_unparseable_input_returns_false_without_query():
    sg = AsyncMock(return_value=[])
    with patch.object(address_points, "socrata_get", new=sg):
        ok = await address_points.parcel_address_matches("14331030110000", "???")
    assert ok is False
    sg.assert_not_called()


async def test_round_trip_query_error_returns_false():
    """Any lookup error withholds (False) — never a default-accept."""
    with _patch_socrata(raises=Exception("timeout")):
        ok = await address_points.parcel_address_matches("14331030110000", "642 W Belden Ave")
    assert ok is False
