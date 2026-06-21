"""Identity reconciliation in /api/scorecard.

When the authoritative address→PIN path degrades to "approximate", the property
orchestrator still resolves a parcel from the point (nearest-centroid fallback).
That PIN may only become the parcel's *identity* if its address round-trips to
the input; otherwise it is withheld and the data is flagged nearest/unverified.
See claude-context/audits/2026-06-21_resolver-investigation.md.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend import main
from backend.models import ContextObject, PropertySummary

pytestmark = pytest.mark.asyncio


def _scorecard_data(pin14: str | None):
    """Minimal _fetch_scorecard_data payload with a property domain PIN."""
    prop = PropertySummary(pin14=pin14) if pin14 else None
    return {"context": ContextObject(property=prop), "comparables": None}


def _patch(rl, data, *, matches=False):
    return (
        patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)),
        patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)),
        patch(
            "backend.retrieval.property.address_points.parcel_address_matches",
            new=AsyncMock(return_value=matches),
        ),
    )


async def test_approximate_neighbor_pin_is_withheld_and_flagged():
    """Round-trip fails (neighbour) → PIN withheld, confidence stays approximate,
    nearest_parcel_unverified set. Never surface the neighbour as identity."""
    rl = main.ResolvedLocation(41.92886, -87.64159, "481 W Deming Pl", None, "approximate")
    p_resolve, p_fetch, p_match = _patch(rl, _scorecard_data("14283180160000"), matches=False)
    with p_resolve, p_fetch, p_match as match_mock:
        out = await main.scorecard(address="481 W Deming Pl")
    assert out["resolved_pin"] is None
    assert out["resolved_confidence"] == "approximate"
    assert out["nearest_parcel_unverified"] is True
    match_mock.assert_awaited_once()


async def test_approximate_pin_that_round_trips_is_promoted():
    """Round-trip passes → promote the candidate PIN to authoritative identity."""
    rl = main.ResolvedLocation(41.9239, -87.6456, "642 W Belden Ave", None, "approximate")
    p_resolve, p_fetch, p_match = _patch(rl, _scorecard_data("14331030110000"), matches=True)
    with p_resolve, p_fetch, p_match:
        out = await main.scorecard(address="642 W Belden Ave")
    assert out["resolved_pin"] == "14331030110000"
    assert out["resolved_confidence"] == "authoritative"
    assert out["nearest_parcel_unverified"] is False


async def test_authoritative_top_level_skips_the_gate():
    """When the address→PIN path already resolved authoritatively, the gate must
    not run (no extra round-trip query) and nothing is flagged."""
    rl = main.ResolvedLocation(41.9239, -87.6456, "642 W Belden Ave", "14331030110000", "authoritative")
    p_resolve, p_fetch, p_match = _patch(rl, _scorecard_data("14331030110000"), matches=True)
    with p_resolve, p_fetch, p_match as match_mock:
        out = await main.scorecard(address="642 W Belden Ave")
    assert out["resolved_pin"] == "14331030110000"
    assert out["resolved_confidence"] == "authoritative"
    assert out["nearest_parcel_unverified"] is False
    match_mock.assert_not_awaited()


async def test_approximate_without_property_pin_is_not_flagged():
    """No property-domain PIN to reconcile → approximate, but nothing to caveat."""
    rl = main.ResolvedLocation(41.9, -87.6, "123 Nowhere Ave", None, "approximate")
    p_resolve, p_fetch, p_match = _patch(rl, _scorecard_data(None), matches=False)
    with p_resolve, p_fetch, p_match as match_mock:
        out = await main.scorecard(address="123 Nowhere Ave")
    assert out["resolved_pin"] is None
    assert out["nearest_parcel_unverified"] is False
    match_mock.assert_not_awaited()
