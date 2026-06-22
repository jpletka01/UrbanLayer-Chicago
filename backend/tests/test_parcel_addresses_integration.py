"""Real-API verification of the assessor address→PIN fallback (3723-97qp).

Pre-deploy gate for the coverage-gap fix: hits the live Cook County Assessor
Parcel Addresses dataset. Proves (1) a real address ABSENT from Address Points
(481 W Deming Pl) now recovers its authoritative PIN, (2) a genuine non-address
(2400 N Milwaukee Ave) still returns None, and (3) an INDEPENDENT spatial
cross-check: the recovered parcel's centroid sits within a block of the Census
geocoder's own location for the same address text — corroborating the mapping
via a source independent of the assessor dataset.

Run with:  python -m pytest backend/tests/ -m integration -k assessor -v
"""

import math

import pytest
from unittest.mock import patch

from backend.retrieval import socrata
from backend.retrieval.property.parcel_addresses import assessor_address_to_pin
from backend import main as main_mod

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _fresh_shared_client():
    """Reset the module-level shared httpx client between tests (each runs on its
    own event loop). Harness-only; production runs on a single loop."""
    socrata._shared_client = None
    yield
    socrata._shared_client = None


# Verified live against 3723-97qp: 481 W Deming Pl → 14283190070000 (this parcel
# is absent from Address Points 78yw-iddh — the gap this fix closes).
GAP_ADDRESS = "481 W Deming Pl"
GAP_PIN = "14283190070000"


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def test_assessor_recovers_gap_address():
    pin = await assessor_address_to_pin(GAP_ADDRESS)
    assert pin == GAP_PIN


async def test_assessor_returns_none_for_genuine_non_address():
    assert await assessor_address_to_pin("2400 N Milwaukee Ave") is None


async def test_assessor_returns_none_for_multi_parcel_building():
    # 333 W Wacker Dr spans multiple PINs → not a confident unique match.
    assert await assessor_address_to_pin("333 W Wacker Dr") is None


async def test_resolve_location_threads_authoritative_pin_via_step_3_5():
    """Flag on: the gap address threads through _resolve_location as authoritative."""
    with patch.object(
        main_mod.get_settings(), "assessor_address_resolution_enabled", True
    ):
        rl = await main_mod._resolve_location(address=GAP_ADDRESS)
    assert rl.pin == GAP_PIN
    assert rl.confidence == "authoritative"
    assert rl.lat and rl.lon


async def test_recovered_pin_agrees_with_independent_geocode():
    """INDEPENDENT cross-check: recovered parcel centroid is within a block of the
    Census geocoder's location for the same address (different source → corroboration)."""
    with patch.object(
        main_mod.get_settings(), "assessor_address_resolution_enabled", True
    ):
        rl = await main_mod._resolve_location(address=GAP_ADDRESS)
    geo = await main_mod.geocode_address(GAP_ADDRESS)
    assert geo is not None, "Census geocoder returned nothing"
    dist = _haversine_m(rl.lat, rl.lon, geo[0], geo[1])
    assert dist < 80, f"recovered centroid {dist:.0f} m from independent geocode (suspicious)"
