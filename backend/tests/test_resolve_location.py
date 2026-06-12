"""Regression + R7 tests for `_resolve_location` precedence.

Strict precedence (truth-model §5, highest → lowest):
    explicit lat/lon  →  pin  →  address→PIN (78yw-iddh)  →  geocode (approximate)

Locks in:
  * R6 — a supplied PIN is never overridden by a co-supplied address (INV-6).
  * R7 — a typed address resolves to its authoritative PIN via Address Points
    before the degraded geocode + nearest-centroid path ever runs.

`_resolve_location` returns a `ResolvedLocation(lat, lon, address, pin, confidence)`
NamedTuple; `confidence` is "authoritative" or "approximate".
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend import main as main_mod

pytestmark = pytest.mark.asyncio

# Distinct sentinel coordinates so each branch is unambiguous.
PIN_COORDS = (41.9300, -87.6400)
ADDR_POINT_COORDS = (41.9306, -87.6408)
GEOCODE_COORDS = (41.8800, -87.6300)
EXPLICIT_COORDS = (41.8500, -87.6500)

# Fixture identities mirror reality (verified live in test_address_points_integration):
# 443 W Wrightwood Ave ↔ 14283180570000, 642 W Belden Ave ↔ 14331030110000.
# 14283190070000 (481 W Deming Pl, class EX) has no address point.


def _patch_pin_lookup(lat_lon):
    """Patch the lazily-imported socrata_get used by the PIN branch (step 2)."""
    rows = [] if lat_lon is None else [{"lat": str(lat_lon[0]), "lon": str(lat_lon[1])}]
    return patch(
        "backend.retrieval.socrata.socrata_get",
        new=AsyncMock(return_value=rows),
    )


def _patch_address_to_pin(result):
    """Patch the lazily-imported address→PIN resolver (step 3).

    `result` is a hit dict, or None for "no confident match".
    """
    return patch(
        "backend.retrieval.property.address_points.address_to_pin",
        new=AsyncMock(return_value=result),
    )


def _addr_point_hit(lat_lon, pin="14283180570000"):
    return {"pin14": pin, "lat": lat_lon[0], "lon": lat_lon[1], "address": "x"}


def _patch_pin_to_address(result):
    """Patch the lazily-imported PIN→display-address reverse lookup (step 2)."""
    return patch(
        "backend.retrieval.property.address_points.pin_to_address",
        new=AsyncMock(return_value=result),
    )


def _patch_geocode(lat_lon):
    return patch.object(
        main_mod, "geocode_address", new=AsyncMock(return_value=lat_lon)
    )


# --------------------------------------------------------------------------- #
# R6 — PIN precedence
# --------------------------------------------------------------------------- #

async def test_pin_wins_over_address():
    """pin + address → PIN coords win; address→PIN is never consulted.

    The supplied pin and address deliberately belong to different parcels —
    proving the address can never override the pin.
    """
    addr_mock = AsyncMock(return_value=_addr_point_hit(ADDR_POINT_COORDS))
    with _patch_pin_lookup(PIN_COORDS), _patch_geocode(GEOCODE_COORDS), \
            patch("backend.retrieval.property.address_points.address_to_pin", new=addr_mock):
        rl = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="14283190070000"
        )
    assert (rl.lat, rl.lon) == PIN_COORDS
    assert rl.pin == "14283190070000"
    assert rl.confidence == "authoritative"
    assert rl.address == "443 W Wrightwood Ave"
    addr_mock.assert_not_called()


async def test_pin_only_still_resolves():
    """pin alone → PIN coords, authoritative, display address backfilled."""
    with _patch_pin_lookup(PIN_COORDS), _patch_pin_to_address("481 W Deming Pl"):
        rl = await main_mod._resolve_location(pin="14283190070000")
    assert (rl.lat, rl.lon) == PIN_COORDS
    assert rl.pin == "14283190070000"
    assert rl.confidence == "authoritative"
    assert rl.address == "481 W Deming Pl"


async def test_pin_only_backfill_miss_keeps_address_none():
    """pin alone, no address point for the parcel → resolves with address=None."""
    with _patch_pin_lookup(PIN_COORDS), _patch_pin_to_address(None):
        rl = await main_mod._resolve_location(pin="14283190070000")
    assert (rl.lat, rl.lon) == PIN_COORDS
    assert rl.address is None
    assert rl.confidence == "authoritative"


async def test_pin_with_address_skips_backfill():
    """A supplied address is never overridden by the reverse lookup."""
    backfill = AsyncMock(return_value="999 Wrong St")
    with _patch_pin_lookup(PIN_COORDS), \
            patch("backend.retrieval.property.address_points.pin_to_address", new=backfill):
        rl = await main_mod._resolve_location(
            address="642 W Belden Ave", pin="14331030110000"
        )
    assert rl.address == "642 W Belden Ave"
    backfill.assert_not_called()


# --------------------------------------------------------------------------- #
# R7 — address → authoritative PIN (the new dominant path)
# --------------------------------------------------------------------------- #

async def test_address_point_hit_resolves_by_pin():
    """address only, Address Points hit → parcel point + PIN, geocode not called."""
    geo = AsyncMock(return_value=GEOCODE_COORDS)
    with _patch_address_to_pin(_addr_point_hit(ADDR_POINT_COORDS, pin="14331030110000")), \
            patch.object(main_mod, "geocode_address", new=geo):
        rl = await main_mod._resolve_location(address="642 W Belden Ave")
    assert (rl.lat, rl.lon) == ADDR_POINT_COORDS
    assert rl.pin == "14331030110000"
    assert rl.confidence == "authoritative"
    geo.assert_not_called()


async def test_address_point_miss_falls_to_geocode_approximate():
    """address only, no confident Address Points match → geocode, approximate, no PIN."""
    with _patch_address_to_pin(None), _patch_geocode(GEOCODE_COORDS):
        rl = await main_mod._resolve_location(address="2400 N Milwaukee Ave")
    assert (rl.lat, rl.lon) == GEOCODE_COORDS
    assert rl.pin is None
    assert rl.confidence == "approximate"
    assert rl.address == "2400 N Milwaukee Ave"


async def test_kill_switch_skips_address_point_step():
    """address_point_resolution_enabled=False → straight to geocode (no PIN)."""
    addr_mock = AsyncMock(return_value=_addr_point_hit(ADDR_POINT_COORDS))
    settings = main_mod.get_settings()
    with patch.object(settings, "address_point_resolution_enabled", False), \
            patch("backend.retrieval.property.address_points.address_to_pin", new=addr_mock), \
            _patch_geocode(GEOCODE_COORDS):
        rl = await main_mod._resolve_location(address="443 W Wrightwood Ave")
    assert (rl.lat, rl.lon) == GEOCODE_COORDS
    assert rl.confidence == "approximate"
    addr_mock.assert_not_called()


# --------------------------------------------------------------------------- #
# Fallback chains when a supplied PIN does not resolve
# --------------------------------------------------------------------------- #

async def test_empty_pin_falls_through_to_address_point():
    """pin returns no rows → address→PIN is tried next (more authoritative than geocode)."""
    with _patch_pin_lookup(None), \
            _patch_address_to_pin(_addr_point_hit(ADDR_POINT_COORDS)), \
            _patch_geocode(GEOCODE_COORDS):
        rl = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="00000000000000"
        )
    assert (rl.lat, rl.lon) == ADDR_POINT_COORDS
    assert rl.pin == "14283180570000"
    assert rl.confidence == "authoritative"


async def test_empty_pin_and_address_miss_falls_to_geocode():
    """pin empty + Address Points miss → geocoded address, approximate."""
    with _patch_pin_lookup(None), _patch_address_to_pin(None), _patch_geocode(GEOCODE_COORDS):
        rl = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="00000000000000"
        )
    assert (rl.lat, rl.lon) == GEOCODE_COORDS
    assert rl.pin is None
    assert rl.confidence == "approximate"


async def test_pin_null_coords_falls_through():
    """PIN row exists but lat/lon null → fall through to address→PIN then geocode."""
    rows = [{"lat": None, "lon": None}]
    with patch("backend.retrieval.socrata.socrata_get", new=AsyncMock(return_value=rows)), \
            _patch_address_to_pin(None), _patch_geocode(GEOCODE_COORDS):
        rl = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="14283180570000"
        )
    assert (rl.lat, rl.lon) == GEOCODE_COORDS
    assert rl.confidence == "approximate"


# --------------------------------------------------------------------------- #
# Explicit lat/lon + error path
# --------------------------------------------------------------------------- #

async def test_explicit_latlon_wins_over_pin_and_address():
    """Explicit lat/lon is a deliberate point override → highest precedence."""
    addr_mock = AsyncMock(return_value=_addr_point_hit(ADDR_POINT_COORDS))
    with _patch_pin_lookup(PIN_COORDS), _patch_geocode(GEOCODE_COORDS), \
            patch("backend.retrieval.property.address_points.address_to_pin", new=addr_mock):
        rl = await main_mod._resolve_location(
            address="443 W Wrightwood Ave",
            lat=EXPLICIT_COORDS[0],
            lon=EXPLICIT_COORDS[1],
            pin="14283180570000",
        )
    assert (rl.lat, rl.lon) == EXPLICIT_COORDS
    assert rl.confidence == "authoritative"
    # The explicit-point branch carries the supplied pin forward, never geocodes.
    addr_mock.assert_not_called()


async def test_no_inputs_raises_422():
    """Nothing resolvable → HTTPException 422 (behavior preserved)."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await main_mod._resolve_location()
    assert exc.value.status_code == 422
