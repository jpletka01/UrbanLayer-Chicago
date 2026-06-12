"""Tests for _apply_parcel_hint — the Scorecard→chat parcel handoff.

Contract: a parcel hint replaces the router's text-geocoded location with the
authoritative parcel point ONLY when the router read the question as an
address query; neighborhood/area plans and any resolution failure leave the
plan untouched. Read-only direction — the hint never invents a location the
router didn't have a slot for.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend import main as main_mod
from backend.main import ResolvedLocation, _apply_parcel_hint
from backend.models import Location, RetrievalPlan

pytestmark = pytest.mark.asyncio

PIN = "14331030110000"
PARCEL_COORDS = (41.92395, -87.64558)
GEOCODED_COORDS = (41.92390, -87.64550)


def _plan(loc_type: str = "address") -> RetrievalPlan:
    return RetrievalPlan(
        sources=["property_domain"],
        location=Location(
            raw="642 W Belden Ave",
            type=loc_type,  # type: ignore[arg-type]
            resolved_address="642 W Belden Ave",
            resolved_lat=GEOCODED_COORDS[0],
            resolved_lon=GEOCODED_COORDS[1],
        ),
        intent="neighborhood_overview",
        requires_disclaimer=False,
    )


def _patch_resolve(result=None, *, raises=None):
    mock = AsyncMock(side_effect=raises) if raises else AsyncMock(return_value=result)
    return patch.object(main_mod, "_resolve_location", new=mock)


async def test_address_plan_overridden_with_parcel_point():
    rl = ResolvedLocation(*PARCEL_COORDS, "642 W Belden Ave", PIN, "authoritative")
    with _patch_resolve(rl), \
            patch.object(main_mod, "community_area_by_point", return_value=7), \
            patch.object(main_mod, "community_area_name", return_value="Lincoln Park"):
        plan = await _apply_parcel_hint(_plan("address"), PIN)
    assert (plan.location.resolved_lat, plan.location.resolved_lon) == PARCEL_COORDS
    assert plan.location.pin == PIN
    assert plan.location.resolved_address == "642 W Belden Ave"
    assert plan.location.resolved_community_area == 7
    assert plan.location.resolved_community_area_name == "Lincoln Park"


async def test_neighborhood_plan_left_untouched():
    """The router read an area query — the hint must not hijack it."""
    mock = AsyncMock()
    with patch.object(main_mod, "_resolve_location", new=mock):
        plan = await _apply_parcel_hint(_plan("neighborhood"), PIN)
    assert plan.location.pin is None
    assert (plan.location.resolved_lat, plan.location.resolved_lon) == GEOCODED_COORDS
    mock.assert_not_called()


async def test_resolution_failure_keeps_router_location():
    from fastapi import HTTPException
    with _patch_resolve(raises=HTTPException(status_code=422, detail="x")):
        plan = await _apply_parcel_hint(_plan("address"), PIN)
    assert plan.location.pin is None
    assert (plan.location.resolved_lat, plan.location.resolved_lon) == GEOCODED_COORDS


async def test_pin_mismatch_keeps_router_location():
    """A degraded resolution that fell through to a different identity is ignored."""
    rl = ResolvedLocation(*PARCEL_COORDS, "x", None, "approximate")
    with _patch_resolve(rl):
        plan = await _apply_parcel_hint(_plan("address"), PIN)
    assert plan.location.pin is None
    assert (plan.location.resolved_lat, plan.location.resolved_lon) == GEOCODED_COORDS
