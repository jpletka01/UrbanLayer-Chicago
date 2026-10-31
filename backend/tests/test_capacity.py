"""The capacity states (backend/capacity.py): the census rules, the map's two added states, and parity with the
Phase 0 census (decision Items 36 and 39)."""

import inspect

import pytest

from backend import capacity as cap
from backend import provenance


def _attrs(**kw):
    base = {"zoning_group": "residential", "class": "2-11", "land_sqft": 3000.0, "bldg_sqft": 3600.0, "density_band": 1.2}
    base.update(kw)
    return base


@pytest.mark.parametrize("kw, state", [
    ({"zoning_group": None}, "no_zoning"),
    ({"zoning_group": "planned_development"}, "planned_development"),
    ({"class": "2-99"}, "condo_unit"),
    ({"class": "EX"}, "exempt"),
    ({"density_band": None}, "no_allowed_far"),
    ({"land_sqft": None}, "unknown_land"),
    ({"land_sqft": 400.0}, "suspect_land"),
    ({"is_vacant": True}, "class_conflict"),
    ({"is_vacant": True, "bldg_sqft": None}, "vacant_land"),
    ({"bldg_sqft": None}, "unknown_gfa"),
    ({"bldg_sqft": 3000.0 * 1.2 * 3 + 1}, "apparently_overbuilt"),
    ({}, "computable"),
])
def test_classify_states(kw, state):
    assert cap.classify(_attrs(**kw)) == state


def test_unknown_building_area_is_never_computable():
    """Truth invariant 1: no building area is its own state, never zero."""
    assert cap.classify(_attrs(bldg_sqft=None)) == "unknown_gfa"
    assert cap.classify(_attrs(bldg_sqft=0)) == "unknown_gfa"


def test_precedence_zoning_before_class():
    assert cap.classify(_attrs(zoning_group=None, **{"class": "2-99"})) == "no_zoning"
    assert cap.classify(_attrs(zoning_group="planned_development", **{"class": "EX"})) == "planned_development"


def test_map_condo_building_from_any_unit_pin():
    """Truth invariant 3: a polygon holding unit PINs is a condo building, even if the base row looks computable."""
    assert cap.map_polygon_state(_attrs(), has_unit_pins=True, complex_total_only=False) == "condo_building"
    assert cap.map_polygon_state(_attrs(**{"class": "2-99"}), has_unit_pins=False, complex_total_only=False) == "condo_building"
    # Outside zoning or in a PD, the polygon says so first.
    assert cap.map_polygon_state(_attrs(zoning_group=None), has_unit_pins=True, complex_total_only=False) == "no_zoning"


def test_map_multi_pin_member_only_when_building_area_is_unknown():
    """Truth invariant 2: a complex total never colors a member's lot; it is an unknown area with a reason."""
    no_area = _attrs(bldg_sqft=None, **{"class": "5-17"})
    assert cap.map_polygon_state(no_area, has_unit_pins=False, complex_total_only=True) == "multi_pin_member"
    assert cap.map_polygon_state(no_area, has_unit_pins=False, complex_total_only=False) == "unknown_gfa"
    # A state ahead of unknown_gfa stays itself.
    assert cap.map_polygon_state(_attrs(bldg_sqft=None, **{"class": "EX"}), has_unit_pins=False, complex_total_only=True) == "exempt"
    # The index's own area wins: the flag only matters when there is no area.
    assert cap.map_polygon_state(_attrs(), has_unit_pins=False, complex_total_only=True) == "computable"


def test_map_states_cover_every_census_state_but_the_unit():
    assert set(cap.STATES) - {"condo_unit"} <= set(cap.MAP_STATES)
    assert {"condo_building", "multi_pin_member", "no_base_row"} <= set(cap.MAP_STATES)
    assert cap.MAP_STATES[-1] == "computable"


def test_polygon_state_unchanged():
    assert cap.polygon_state([("14-33-103-011-0000", _attrs())]) == "computable"
    assert cap.polygon_state([("14-33-103-011-0000", _attrs()), ("14-33-103-011-1001", _attrs(**{"class": "2-99"}))]) == "condo_unit"
    assert cap.polygon_state([("14-33-103-011-1001", _attrs())]) == "no_base_row"


@pytest.mark.parametrize("share, verdict", [(0.0, "withheld"), (0.0999, "withheld"), (0.10, "low"), (0.2499, "low"), (0.25, "standard")])
def test_coverage_verdict_uses_the_confidence_standard(share, verdict):
    assert cap.coverage_verdict(share) == verdict
    assert cap.HIDE_COVERAGE_BELOW is provenance.HIDE_COVERAGE_BELOW


def test_eval_census_has_no_copy_of_the_rules():
    """Parity: the Phase 0 census imports the product's rules; it may not define its own."""
    from eval import capacity_coverage as cc

    for name in ("classify", "polygon_state", "coverage_verdict", "pin10", "STATES", "CONDO_CLASSES", "EXEMPT_CLASSES",
                 "IMPLAUSIBLE_FAR_MULTIPLE", "MIN_LOT_SQFT", "MAX_LOT_SQFT", "HIDE_COVERAGE_BELOW", "FADE_COVERAGE_BELOW"):
        assert getattr(cc, name) is getattr(cap, name), name
    src = inspect.getsource(cc)
    assert "def classify" not in src and "def polygon_state" not in src and "STATES = (" not in src
