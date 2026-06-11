"""Regression tests for `_resolve_location` precedence.

Locks in the PIN-precedence fix (follow-up to R5, the parcel bbox-fallback bug
in `claude-context/guides/report-status.md`): when a request supplies both a
`pin` and an `address`, the **PIN** is the authoritative parcel key and must win.
Previously the resolver checked `address` before `pin` (an `elif` chain), so a
co-supplied address geocoded to a point that the downstream bbox parcel lookup
could resolve to a *neighbor* — rendering a report for the wrong parcel.

Precedence contract (highest → lowest):
    explicit lat/lon  →  pin  →  address (fallback + display metadata)
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend import main as main_mod

pytestmark = pytest.mark.asyncio

# Distinct sentinel coordinates so each branch is unambiguous.
PIN_COORDS = (41.9300, -87.6400)
GEOCODE_COORDS = (41.8800, -87.6300)
EXPLICIT_COORDS = (41.8500, -87.6500)


def _patch_pin_lookup(lat_lon):
    """Patch the lazily-imported socrata_get used by the PIN branch.

    `lat_lon` is a (lat, lon) tuple for a hit, or None for "PIN not found".
    """
    if lat_lon is None:
        rows = []
    else:
        rows = [{"lat": str(lat_lon[0]), "lon": str(lat_lon[1])}]
    return patch(
        "backend.retrieval.socrata.socrata_get",
        new=AsyncMock(return_value=rows),
    )


def _patch_geocode(lat_lon):
    return patch.object(
        main_mod, "geocode_address", new=AsyncMock(return_value=lat_lon)
    )


async def test_pin_wins_over_address():
    """pin + address supplied → PIN coordinates are used, not the geocoded address."""
    with _patch_pin_lookup(PIN_COORDS), _patch_geocode(GEOCODE_COORDS):
        lat, lon, addr = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="14283190070000"
        )
    assert (lat, lon) == PIN_COORDS
    # Address is retained as display metadata even though it did not drive coords.
    assert addr == "443 W Wrightwood Ave"


async def test_address_used_as_fallback_when_pin_lookup_empty():
    """pin + address, but the PIN returns no rows → fall back to the geocoded address."""
    with _patch_pin_lookup(None), _patch_geocode(GEOCODE_COORDS):
        lat, lon, addr = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="00000000000000"
        )
    assert (lat, lon) == GEOCODE_COORDS
    assert addr == "443 W Wrightwood Ave"


async def test_address_used_as_fallback_when_pin_has_null_coords():
    """PIN row exists but lat/lon are null → fall back to the geocoded address."""
    rows = [{"lat": None, "lon": None}]
    with patch("backend.retrieval.socrata.socrata_get", new=AsyncMock(return_value=rows)), \
            _patch_geocode(GEOCODE_COORDS):
        lat, lon, _ = await main_mod._resolve_location(
            address="443 W Wrightwood Ave", pin="14283190070000"
        )
    assert (lat, lon) == GEOCODE_COORDS


async def test_pin_only_still_resolves():
    """pin alone (no address) → PIN coordinates (behavior preserved)."""
    with _patch_pin_lookup(PIN_COORDS), _patch_geocode(GEOCODE_COORDS):
        lat, lon, addr = await main_mod._resolve_location(pin="14283190070000")
    assert (lat, lon) == PIN_COORDS
    assert addr is None


async def test_address_only_unaffected():
    """address alone (no pin) → geocoded address (behavior preserved)."""
    with _patch_geocode(GEOCODE_COORDS):
        lat, lon, addr = await main_mod._resolve_location(address="2400 N Milwaukee Ave")
    assert (lat, lon) == GEOCODE_COORDS
    assert addr == "2400 N Milwaukee Ave"


async def test_explicit_latlon_wins_over_pin_and_address():
    """Explicit lat/lon is a deliberate point override → highest precedence."""
    # If either the pin or geocode path were consulted the test would fail, so
    # patch them to *other* coords and assert the explicit ones win.
    with _patch_pin_lookup(PIN_COORDS), _patch_geocode(GEOCODE_COORDS):
        lat, lon, _ = await main_mod._resolve_location(
            address="443 W Wrightwood Ave",
            lat=EXPLICIT_COORDS[0],
            lon=EXPLICIT_COORDS[1],
            pin="14283190070000",
        )
    assert (lat, lon) == EXPLICIT_COORDS


async def test_no_inputs_raises_422():
    """Nothing resolvable → HTTPException 422 (behavior preserved)."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await main_mod._resolve_location()
    assert exc.value.status_code == 422
