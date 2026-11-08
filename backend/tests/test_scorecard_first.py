"""The Profile's first-content request, /api/scorecard/first (decision Item 82).

Its figures must equal the full Profile's when that one arrives, so the page never shows a number that then
changes: the lot area and outline come from the same rule (`property.lot_area`) on the same inputs, the
district from the same zoning lookup and Title 17 row. A failed part is "unchecked", never empty.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from backend import main
from backend.retrieval import property as prop_mod

pytestmark = pytest.mark.asyncio

PIN = "14331030110000"
OUTLINE = {"type": "Polygon", "coordinates": [[[-87.6, 41.9], [-87.6, 41.91], [-87.59, 41.91], [-87.6, 41.9]]]}


def _geom(area=3125, shared=0):
    return {"land_sqft_geom": area, "parcel_geometry": OUTLINE, "geom_year": 2024, "shared_outline_with": shared}


def _sources(*, chars, assessments, geometry, bldg_class="211"):
    """Patch every source property_domain and first_lot_facts read, with the same answers for both."""
    stack = ExitStack()
    p = stack.enter_context
    p(patch.object(prop_mod, "lookup_parcel_by_pin", new=AsyncMock(
        return_value={"pin14": PIN, "address": "642 W BELDEN AVE", "bldg_class": bldg_class, "land_sqft": None})))
    p(patch.object(prop_mod, "get_characteristics", new=AsyncMock(return_value=chars)))
    p(patch.object(prop_mod, "get_assessments", new=AsyncMock(return_value=assessments)))
    p(patch.object(prop_mod, "get_sales", new=AsyncMock(return_value=[])))
    p(patch.object(prop_mod, "_fetch_building_fallbacks", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.appeals.get_appeals", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.tax_estimate.estimate_tax", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.parcel_geometry.get_parcel_geometry_facts", new=AsyncMock(return_value=geometry)))
    p(patch("backend.retrieval.property.parcel_flags.get_parcel_flags", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.assessor_permits.get_assessor_permits", new=AsyncMock(return_value=None)))
    return stack


CASES = {
    "assessor area wins": dict(chars={"char_land_sf": "3100", "char_bldg_sf": "2400"},
                               assessments=[{"class": "211", "year": "2024"}], geometry=_geom(3125)),
    "outline fills a gap": dict(chars={"char_bldg_sf": "9000"}, assessments=[{"class": "318", "year": "2024"}],
                                geometry=_geom(6250), bldg_class="318"),
    "shared outline is no lot's": dict(chars=None, assessments=[{"class": "299", "year": "2024"}],
                                       geometry=_geom(40000, shared=12), bldg_class="299"),
    "stale vacant-lot row dropped": dict(chars={"char_land_sf": "9999", "char_bldg_sf": "800", "class": "207"},
                                         assessments=[{"class": "100", "year": "2024"}], geometry=_geom(3000),
                                         bldg_class="100"),
    "no outline, no area": dict(chars=None, assessments=[{"class": "590", "year": "2024"}], geometry=None,
                                bldg_class="590"),
}


@pytest.mark.parametrize("case", list(CASES))
async def test_first_lot_equals_the_full_profile(case):
    kw = CASES[case]
    with _sources(**kw):
        full = await prop_mod.property_domain(41.92, -87.64, pin=PIN, workflow="property_intelligence")
        first = await prop_mod.first_lot_facts(PIN)
    assert first["land_sqft"] == full.land_sqft
    assert first["land_sqft_source"] == full.land_sqft_source
    assert first["parcel_geometry"] == full.parcel_geometry
    assert first["shared_outline_with"] == int(full.shared_outline_with or 0)


async def test_first_lot_raises_when_a_county_call_fails():
    """No guessed area: a failed characteristics call fails the lot part (the page waits for the full one)."""
    with _sources(chars=None, assessments=[], geometry=_geom()):
        with patch.object(prop_mod, "get_characteristics", new=AsyncMock(side_effect=RuntimeError("down"))):
            with pytest.raises(RuntimeError):
                await prop_mod.first_lot_facts(PIN)


ZONE = {"zone_class": "RS-3", "zone_type": 1, "ordinance_num": None, "application_num": None,
        "ordinance_date": None, "map_updated": None, "clerk_url": None}


def _endpoint(rl, *, zoning=ZONE, lot=None, lot_exc=None, zoning_exc=None):
    stack = ExitStack()
    p = stack.enter_context
    p(patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)))
    p(patch.object(main, "lookup_zoning", new=AsyncMock(return_value=zoning, side_effect=zoning_exc)))
    lot_mock = p(patch("backend.retrieval.property.first_lot_facts", new=AsyncMock(return_value=lot, side_effect=lot_exc)))
    return stack, lot_mock


async def test_first_payload_for_an_exact_parcel():
    rl = main.ResolvedLocation(41.9239, -87.6456, "642 W Belden Ave", PIN, "authoritative", "address_points")
    lot = {"pin14": PIN, "land_sqft": 3100, "land_sqft_source": "assessor", "parcel_geometry": OUTLINE,
           "shared_outline_with": 0}
    stack, _ = _endpoint(rl, lot=lot)
    with stack:
        out = await main.scorecard_first(address="642 W Belden Ave")
    assert out["resolved_pin"] == PIN and out["resolved_confidence"] == "authoritative"
    assert out["zoning"]["zone_class"] == "RS-3" and out["zoning_unchecked"] is False
    # The same Title 17 row the full response serializes as zone_definition.
    from dataclasses import asdict
    from backend.retrieval.zoning_definitions import get_zone_definition
    assert out["zone_definition"] == asdict(get_zone_definition("RS-3"))
    assert out["lot"] == lot and out["lot_unchecked"] is False


async def test_first_payload_for_an_approximate_match_has_no_lot():
    rl = main.ResolvedLocation(41.9177, -87.7105, "3300 W Armitage Ave", None, "approximate", "geocode_nearest")
    stack, lot_mock = _endpoint(rl)
    with stack:
        out = await main.scorecard_first(address="3300 W Armitage Ave")
    assert out["resolved_pin"] is None and out["lot"] is None and out["lot_unchecked"] is False
    lot_mock.assert_not_awaited()


async def test_failed_parts_are_unchecked_not_empty():
    rl = main.ResolvedLocation(41.9239, -87.6456, "642 W Belden Ave", PIN, "authoritative", "address_points")
    stack, _ = _endpoint(rl, zoning_exc=RuntimeError("arcgis"), lot_exc=RuntimeError("socrata"))
    with stack:
        out = await main.scorecard_first(address="642 W Belden Ave")
    assert out["zoning"] is None and out["zoning_unchecked"] is True and out["zone_definition"] is None
    assert out["lot"] is None and out["lot_unchecked"] is True


async def test_outside_chicago_is_refused_like_the_full_profile():
    from fastapi import HTTPException
    rl = main.ResolvedLocation(38.9, -77.03, "1600 Pennsylvania Ave", None, "approximate", "geocode_nearest")
    stack, _ = _endpoint(rl)
    with stack:
        with pytest.raises(HTTPException) as exc:
            await main.scorecard_first(address="1600 Pennsylvania Ave")
    assert exc.value.status_code == 422
