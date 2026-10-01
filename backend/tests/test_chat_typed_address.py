"""Tests for _apply_typed_address — F1: an address typed into chat is resolved
to its parcel the way the Property Profile resolves it.

Contract: an address-typed plan with no parcel hint gets the parcel's own point
and PIN from Address Points / Assessor Parcel Addresses (never the Census
geocode's street-interpolated point, which can sit in a neighboring district).
When no confident parcel exists the router's geocode is kept but the location
is marked "approximate" so the answer can say so. Nothing else is touched.
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend import main as main_mod
from backend.main import ResolvedLocation, _apply_typed_address
from backend.models import Location, RetrievalPlan

pytestmark = pytest.mark.asyncio

PIN = "16012280180000"
PARCEL = (41.90470, -87.68866)
GEOCODED = (41.90484, -87.68850)  # street-interpolated point, ~176 ft off, wrong polygon


def _plan(loc_type: str = "address", pin: str | None = None) -> RetrievalPlan:
    return RetrievalPlan(
        sources=["regulatory_domain", "property_domain"],
        location=Location(
            raw="1256 N Artesian Ave, Chicago, Illinois",
            type=loc_type,  # type: ignore[arg-type]
            resolved_address="1256 N Artesian Ave, Chicago, IL",
            resolved_lat=GEOCODED[0],
            resolved_lon=GEOCODED[1],
            resolved_community_area=24,
            resolved_community_area_name="West Town",
            pin=pin,
        ),
    )


def _patch_resolve(result=None, *, raises=None):
    mock = AsyncMock(side_effect=raises) if raises else AsyncMock(return_value=result)
    return patch.object(main_mod, "_resolve_location", new=mock), mock


async def test_typed_address_gets_the_parcels_own_point_and_pin():
    rl = ResolvedLocation(*PARCEL, "1256 N Artesian Ave, Chicago, IL", PIN, "authoritative")
    patcher, mock = _patch_resolve(rl)
    with patcher, \
            patch.object(main_mod, "community_area_by_point", return_value=22), \
            patch.object(main_mod, "community_area_name", return_value="Logan Square"):
        plan = await _apply_typed_address(_plan())
    loc = plan.location
    assert (loc.resolved_lat, loc.resolved_lon) == PARCEL
    assert loc.pin == PIN and loc.resolution == "authoritative"
    assert (loc.resolved_community_area, loc.resolved_community_area_name) == (22, "Logan Square")
    # the router's own geocode is not re-run: only a confident parcel is wanted
    assert mock.await_args.kwargs == {"address": "1256 N Artesian Ave, Chicago, IL", "degraded_fallback": False}


async def test_no_confident_parcel_keeps_geocode_and_marks_approximate():
    patcher, _ = _patch_resolve(raises=HTTPException(status_code=422, detail="x"))
    with patcher:
        plan = await _apply_typed_address(_plan())
    loc = plan.location
    assert loc.resolution == "approximate" and loc.pin is None
    assert (loc.resolved_lat, loc.resolved_lon) == GEOCODED
    assert loc.resolved_community_area_name == "West Town"


async def test_lookup_error_degrades_to_approximate():
    patcher, _ = _patch_resolve(raises=RuntimeError("socrata down"))
    with patcher:
        plan = await _apply_typed_address(_plan())
    assert plan.location.resolution == "approximate" and plan.location.pin is None


async def test_non_authoritative_result_is_not_trusted():
    rl = ResolvedLocation(*PARCEL, "x", None, "approximate")
    patcher, _ = _patch_resolve(rl)
    with patcher:
        plan = await _apply_typed_address(_plan())
    assert plan.location.resolution == "approximate" and plan.location.pin is None
    assert (plan.location.resolved_lat, plan.location.resolved_lon) == GEOCODED


@pytest.mark.parametrize("loc_type", ["neighborhood", "intersection", "none"])
async def test_non_address_plans_untouched(loc_type):
    patcher, mock = _patch_resolve()
    with patcher:
        plan = await _apply_typed_address(_plan(loc_type))
    assert plan.location.resolution is None and plan.location.pin is None
    mock.assert_not_called()


async def test_already_pinned_plan_is_not_re_resolved():
    patcher, mock = _patch_resolve()
    with patcher:
        plan = await _apply_typed_address(_plan(pin=PIN))
    assert plan.location.pin == PIN
    mock.assert_not_called()


async def test_resolve_location_can_skip_the_degraded_geocode():
    """degraded_fallback=False must never call the geocoder: a miss is a 422."""
    geocode = AsyncMock(return_value=(41.9, -87.7))
    with patch("backend.retrieval.property.address_points.address_to_pin", new=AsyncMock(return_value=None)), \
            patch("backend.retrieval.property.parcel_addresses.assessor_address_to_pin", new=AsyncMock(return_value=None)), \
            patch.object(main_mod, "geocode_address", new=geocode):
        with pytest.raises(HTTPException) as exc:
            await main_mod._resolve_location(address="1 N Nowhere St", degraded_fallback=False)
        assert exc.value.status_code == 422
        geocode.assert_not_called()
        rl = await main_mod._resolve_location(address="1 N Nowhere St")  # default keeps the fallback
        assert rl.confidence == "approximate" and rl.pin is None
        geocode.assert_awaited_once()
