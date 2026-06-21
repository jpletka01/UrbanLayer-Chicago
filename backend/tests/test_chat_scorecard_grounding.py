"""Tests for the Scorecard chat-grounding bypass.

Contract: when a chat turn carries pre-resolved ScorecardContext for the parcel
the plan resolved to AND the plan is property-scoped, _retrieve substitutes the
Scorecard's already-assembled property/regulatory/incentives/zoning sub-objects
in place of live fetches (bypass) and grafts comparables + zone_definition onto
the context. vector_search / neighborhood / activity feeds still retrieve
(augment). A pin mismatch or a non-property-scoped plan falls back to normal
retrieval.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend import main as main_mod
from backend.main import _retrieve, _scorecard_grounding_applies
from backend.models import (
    ComparablesSummary,
    IncentivesSummary,
    Location,
    PropertySummary,
    RegulatorySummary,
    RetrievalPlan,
    ScorecardContext,
    ZoningSummary,
)

PIN = "14331030110000"
COORDS = (41.92395, -87.64558)


def _plan(sources, *, pin=PIN, workflow="general", ca=7) -> RetrievalPlan:
    return RetrievalPlan(
        sources=sources,
        location=Location(
            raw="642 W Belden Ave",
            type="address",
            resolved_address="642 W Belden Ave",
            resolved_lat=COORDS[0],
            resolved_lon=COORDS[1],
            resolved_community_area=ca,
            resolved_community_area_name="Lincoln Park",
            pin=pin,
        ),
        intent="neighborhood_overview",
        requires_disclaimer=True,
        workflow_hint=workflow,
    )


def _sc(pin=PIN) -> ScorecardContext:
    return ScorecardContext(
        pin=pin,
        address="642 W Belden Ave",
        community_area_name="Lincoln Park",
        lat=COORDS[0],
        lon=COORDS[1],
        parcel_zoning=ZoningSummary(zone_class="RM-5"),
        zone_definition={"zone_class": "RM-5", "far": 2.0},
        property=PropertySummary(bldg_class="2-11"),
        regulatory=RegulatorySummary(in_planned_development=True),
        incentives=IncentivesSummary(property_tax_class="standard"),
        comparables=ComparablesSummary(median_sale_price=950000, sales_volume=6),
    )


# --------------------------------------------------------------------------- #
# _scorecard_grounding_applies — the gate
# --------------------------------------------------------------------------- #

def test_gate_true_when_pin_matches_and_property_scoped():
    assert _scorecard_grounding_applies(_plan(["property_domain"]), _sc()) is True


def test_gate_true_for_site_due_diligence_workflow():
    plan = _plan(["vector_search"], workflow="site_due_diligence")
    assert _scorecard_grounding_applies(plan, _sc()) is True


def test_gate_false_when_no_grounding():
    assert _scorecard_grounding_applies(_plan(["property_domain"]), None) is False


def test_gate_false_on_pin_mismatch():
    plan = _plan(["property_domain"], pin="99999999999999")
    assert _scorecard_grounding_applies(plan, _sc(pin=PIN)) is False


def test_gate_false_when_not_property_scoped():
    # A pure neighborhood/code turn — retrieve normally even with grounding present.
    plan = _plan(["crime_api", "311_api"])
    assert _scorecard_grounding_applies(plan, _sc()) is False


def test_gate_false_when_grounding_has_no_pin():
    sc = _sc()
    sc.pin = None
    assert _scorecard_grounding_applies(_plan(["property_domain"]), sc) is False


# --------------------------------------------------------------------------- #
# _retrieve — skip + merge
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_retrieve_skips_property_domains_and_merges_grounding():
    sc = _sc()
    plan = _plan(["property_domain", "regulatory_domain", "incentives_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock()) as prop, \
            patch.object(main_mod, "regulatory_domain", new=AsyncMock()) as reg, \
            patch.object(main_mod, "incentives_domain", new=AsyncMock()) as inc, \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock()) as zon, \
            patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()) as aro:
        ctx = await _retrieve(plan, scorecard_context=sc)

    # Bypass: none of the substituted fetches ran.
    prop.assert_not_called()
    reg.assert_not_called()
    inc.assert_not_called()
    zon.assert_not_called()
    aro.assert_not_called()

    # Merge: grounding sub-objects + sibling fields landed on the context.
    assert ctx.property is sc.property
    assert ctx.regulatory is sc.regulatory
    assert ctx.incentives is sc.incentives
    assert ctx.parcel_zoning is sc.parcel_zoning
    assert ctx.comparables is sc.comparables
    assert ctx.zone_definition == {"zone_class": "RM-5", "far": 2.0}


@pytest.mark.asyncio
async def test_retrieve_runs_normally_on_pin_mismatch():
    sc = _sc(pin="99999999999999")
    plan = _plan(["property_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock(return_value=None)) as prop, \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock(return_value=None)):
        ctx = await _retrieve(plan, scorecard_context=sc)

    # Augment: the live fetch ran, grounding was not grafted.
    prop.assert_called_once()
    assert ctx.comparables is None
    assert ctx.zone_definition is None


@pytest.mark.asyncio
async def test_retrieve_vector_search_still_runs_under_grounding():
    sc = _sc()
    plan = _plan(["property_domain", "vector_search"], workflow="site_due_diligence")
    plan.search_query = "RM-5 setback requirements"

    with patch.object(main_mod, "property_domain", new=AsyncMock()) as prop, \
            patch.object(main_mod, "semantic_search", new=AsyncMock(return_value=[])) as ss, \
            patch.object(main_mod, "expand_cross_references", new=AsyncMock(return_value=[])):
        ctx = await _retrieve(plan, scorecard_context=sc)

    prop.assert_not_called()       # bypass for property facts
    ss.assert_called_once()        # augment: code search still runs
    assert ctx.property is sc.property


@pytest.mark.asyncio
async def test_retrieve_overwrite_preserves_still_running_fetches():
    """The narrow overwrite must not clobber neighborhood / activity-feed
    sub-objects produced by the fetches that still run under grounding."""
    from backend.models import NeighborhoodSummary

    sc = _sc()
    plan = _plan(["property_domain", "neighborhood_domain", "crime_api"])
    nbhd = NeighborhoodSummary()

    with patch.object(main_mod, "property_domain", new=AsyncMock()) as prop, \
            patch.object(main_mod, "neighborhood_domain", new=AsyncMock(return_value=nbhd)) as nb, \
            patch.object(main_mod.crime, "crime_by_community_area",
                         new=AsyncMock(return_value=[{"primary_type": "THEFT", "count": 12, "arrests": 2}])) as cr, \
            patch.object(main_mod.crime, "crime_yoy_by_community_area", new=AsyncMock(return_value=None)):
        ctx = await _retrieve(plan, scorecard_context=sc)

    prop.assert_not_called()       # bypass
    nb.assert_called_once()        # augment: neighborhood ran
    cr.assert_called_once()        # augment: crime ran
    # Survive the overwrite intact.
    assert ctx.neighborhood is nbhd
    assert ctx.crime_last_90d is not None
    # Grounding still grafted alongside them.
    assert ctx.property is sc.property
    assert ctx.comparables is sc.comparables
