"""The WS8 Phase 0 census: capacity states, polygon roll-up, outside-city exclusion, and the coverage verdict."""

import json

import pytest

from backend import provenance
from eval import capacity_coverage as cc


def _p(**kw):
    base = {"zoning_group": "residential", "class": "2-03", "land_sqft": 3000.0, "bldg_sqft": 1500.0, "density_band": 1.2}
    base.update(kw)
    return base


def test_thresholds_agree_with_the_confidence_standard():
    assert cc.HIDE_COVERAGE_BELOW == provenance.HIDE_COVERAGE_BELOW
    assert cc.FADE_COVERAGE_BELOW == provenance.FADE_COVERAGE_BELOW


@pytest.mark.parametrize(
    "attrs, state",
    [
        (_p(), "computable"),
        (_p(zoning_group=None), "no_zoning"),
        (_p(zoning_group="planned_development", density_band=None), "planned_development"),
        (_p(**{"class": "2-99", "land_sqft": None, "bldg_sqft": None}), "condo_unit"),
        (_p(**{"class": "EX"}), "exempt"),
        (_p(zoning_group="manufacturing", density_band=None), "no_allowed_far"),
        (_p(land_sqft=None), "unknown_land"),
        (_p(land_sqft=120.0), "suspect_land"),
        (_p(land_sqft=5_000_000.0), "suspect_land"),
        (_p(bldg_sqft=None), "unknown_gfa"),
        (_p(bldg_sqft=0), "unknown_gfa"),
        (_p(is_vacant=True, bldg_sqft=None), "vacant_land"),
        (_p(is_vacant=True, bldg_sqft=900.0), "class_conflict"),
        (_p(density_band=2.0, bldg_sqft=3000.0 * 2.0 * 3 + 1), "apparently_overbuilt"),
        (_p(density_band=2.0, bldg_sqft=3000.0 * 2.0 * 3), "computable"),  # exactly 3x the cap is the guard's edge, not over it
    ],
)
def test_classify(attrs, state):
    assert cc.classify(attrs) == state


def test_unknown_building_area_is_never_read_as_underbuilt():
    # Every non-computable state, including a missing building area, must stay out of "computable".
    assert cc.classify(_p(bldg_sqft=None)) != "computable"
    assert cc.classify(_p(is_vacant=True, bldg_sqft=800.0)) != "vacant_land"  # a vacant class with a building is flagged


def test_planned_development_wins_over_condo_and_missing_far():
    assert cc.classify(_p(zoning_group="planned_development", density_band=None, **{"class": "2-99"})) == "planned_development"


def test_polygon_state_collapses_unit_pins_to_one_condo_polygon():
    rows = [("20-02-105-029-0000", _p()), ("20-02-105-029-1001", _p(**{"class": "2-99"}))]
    assert cc.polygon_state(rows) == "condo_unit"


def test_polygon_state_uses_the_base_row_otherwise():
    assert cc.polygon_state([("17-01-001-001-0000", _p(bldg_sqft=None))]) == "unknown_gfa"
    assert cc.polygon_state([("17-01-001-001-8001", _p())]) == "no_base_row"


@pytest.mark.parametrize("share, verdict", [(0.0, "withheld"), (0.0999, "withheld"), (0.10, "low"), (0.2499, "low"), (0.25, "standard")])
def test_coverage_verdict(share, verdict):
    assert cc.coverage_verdict(share) == verdict


def _row(pin, lat, ca, attrs):
    return (pin, lat, -87.7, json.dumps(attrs), json.dumps([f"neighborhood:{ca}"]))


def test_outside_city_rows_are_counted_apart_and_excluded_from_every_share():
    rows = [
        _row("14-01-001-001-0000", 41.9, 3, _p()),
        _row("14-01-001-002-0000", 41.9, 3, _p(bldg_sqft=None)),
        _row("15-12-413-008-0000", 41.5, 25, _p(zoning_group=None)),  # a suburb tagged to Austin
    ]
    result = cc.census(rows, lambda lat, lon: 3 if lat > 41.8 else None)
    assert result["index_rows"] == 3
    assert result["outside_city"]["n"] == 1
    assert result["outside_city"]["tagged_to_ca"] == {"25": 1}
    assert result["rows"]["citywide"]["n"] == 2
    assert "25" not in result["rows"]["by_community_area"]  # the suburb never creates or lowers an area
    assert result["rows"]["by_community_area"]["3"]["states"]["computable"] == 1
    assert result["rows"]["by_community_area"]["3"]["states"]["unknown_gfa"] == 1


def test_census_reports_row_and_polygon_levels():
    rows = [
        _row("20-02-105-029-0000", 41.9, 3, _p()),
        _row("20-02-105-029-1001", 41.9, 3, _p(**{"class": "2-99", "land_sqft": None, "bldg_sqft": None})),
        _row("20-02-105-029-1002", 41.9, 3, _p(**{"class": "2-99", "land_sqft": None, "bldg_sqft": None})),
    ]
    result = cc.census(rows, lambda lat, lon: 3)
    assert result["rows"]["citywide"]["n"] == 3
    assert result["polygons"]["citywide"]["n"] == 1
    assert result["polygons"]["citywide"]["states"]["condo_unit"] == 1
