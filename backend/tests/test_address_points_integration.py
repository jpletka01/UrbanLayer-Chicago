"""Real-API verification of the R7 address→PIN path.

Pre-deploy gate (truth-model §6, r7-implementation-plan §4): hits the live Cook
County Address Points (78yw-iddh). Proves the authoritative address→PIN mapping
resolves and threads through `_resolve_location` as an authoritative match,
closing the wrong-neighbor failure for a real Chicago address.

The address→PIN pair below was verified directly against the live 78yw-iddh
dataset on 2026-06-11.

Run with:  python -m pytest backend/tests/ -m integration -k address_point -v
"""

import pytest

from backend.retrieval import socrata
from backend.retrieval.property.address_points import address_to_pin
from backend import main as main_mod

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _fresh_shared_client():
    """Each pytest-asyncio test runs on its own event loop, so the module-level
    shared httpx client from a prior test is bound to a dead loop ("Event loop is
    closed"). Reset it so every test builds a client on its own loop. Harness-only;
    production runs on a single loop."""
    socrata._shared_client = None
    yield
    socrata._shared_client = None

# Verified live against 78yw-iddh: 443 W Wrightwood Ave → PIN 14283180570000.
KNOWN_ADDRESS = "443 W Wrightwood Ave"
KNOWN_PIN = "14283180570000"


async def test_address_to_pin_resolves_known_address():
    hit = await address_to_pin(KNOWN_ADDRESS)
    assert hit is not None, "Address Points returned no confident match"
    assert hit["pin14"] == KNOWN_PIN
    assert hit["lat"] and hit["lon"]


async def test_resolve_location_threads_authoritative_pin():
    rl = await main_mod._resolve_location(address=KNOWN_ADDRESS)
    assert rl.pin == KNOWN_PIN
    assert rl.confidence == "authoritative"
