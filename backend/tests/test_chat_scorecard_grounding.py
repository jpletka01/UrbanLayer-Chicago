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
    AddressViolations,
    ComparablesSummary,
    IncentivesSummary,
    Location,
    NeighborhoodSummary,
    PropertySummary,
    RegulatorySummary,
    RetrievalPlan,
    ScorecardContext,
    TrafficSummary,
    ViolationSummary,
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


def _sc(pin=PIN, *, verdict=None, address_violations=None, traffic=None) -> ScorecardContext:
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
        verdict=verdict,
        address_violations=address_violations,
        traffic=traffic,
    )


# A distilled verdict as lib/scorecardContext.ts ships it — flagged caveated so
# the test proves the hedge survives all the way into chat context.
CAVEATED_VERDICT = {
    "category": "constrained",
    "headline": "Constrained upside",
    "binding_constraint": "In a planned development — uses are entitlement-defined",
    "reasons": [{"text": "In a planned development", "polarity": "negative"}],
    "confidence": "caveated",
    "caveats": [
        "Parcel identity unconfirmed — verify the PIN before relying on parcel facts.",
        "Development capacity not computed (building area unavailable).",
    ],
    "signals": {"capacityBand": "unknown"},
}


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
async def test_retrieve_grafts_verdict_with_caveats_intact():
    """The Scorecard's computed verdict (incl. its caveats) must ride into chat
    context so the synthesizer can speak to the verdict and stay hedged. This is
    the seam where a caveated verdict could silently lose its hedge."""
    sc = _sc(verdict=CAVEATED_VERDICT)
    plan = _plan(["property_domain", "regulatory_domain", "incentives_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
            patch.object(main_mod, "regulatory_domain", new=AsyncMock()), \
            patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
            patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()):
        ctx = await _retrieve(plan, scorecard_context=sc)

    assert ctx.verdict is sc.verdict
    assert ctx.verdict["confidence"] == "caveated"
    # The hedge must survive the handoff — both caveats present, untruncated.
    assert ctx.verdict["caveats"] == CAVEATED_VERDICT["caveats"]
    assert ctx.verdict["binding_constraint"]


@pytest.mark.asyncio
async def test_retrieve_no_verdict_grafted_on_pin_mismatch():
    """A verdict belongs to its parcel — a mismatched grounding must not leak it."""
    sc = _sc(pin="99999999999999", verdict=CAVEATED_VERDICT)
    plan = _plan(["property_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock(return_value=None)), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock(return_value=None)):
        ctx = await _retrieve(plan, scorecard_context=sc)

    assert ctx.verdict is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["present", "confirmed_zero", "unconfirmed"])
async def test_retrieve_grafts_address_violations_tristate(status):
    """The parcel's address-scoped violation tri-state must reach chat context in
    its OWN field (distinct from the area-level ctx.violations) so the chat can
    agree with the page — present / confirmed_zero / unconfirmed all ride through,
    and confirmed_zero must never collapse into unconfirmed (or vice versa)."""
    summary = ViolationSummary(total=3, open_count=1, top_descriptions=[]) if status == "present" else None
    av = AddressViolations(status=status, summary=summary)
    sc = _sc(address_violations=av)
    plan = _plan(["property_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
            patch.object(main_mod, "regulatory_domain", new=AsyncMock()), \
            patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
            patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()):
        ctx = await _retrieve(plan, scorecard_context=sc)

    assert ctx.address_violations is av
    assert ctx.address_violations.status == status
    # Distinct field — never grafted onto the area-level ctx.violations.
    assert ctx.violations is None


@pytest.mark.asyncio
async def test_retrieve_grafts_traffic_into_neighborhood_shell():
    """Nearest-street traffic (Scorecard Tier-2) rides into chat context inside
    neighborhood — when the turn didn't run the neighborhood orchestrator, a
    shell is created so the fact still serializes to the synthesizer."""
    traffic = TrafficSummary(road="MILWAUKEE AVE", daily_vehicles=21200, directions=2)
    sc = _sc(traffic=traffic)
    plan = _plan(["property_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
            patch.object(main_mod, "regulatory_domain", new=AsyncMock()), \
            patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
            patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()):
        ctx = await _retrieve(plan, scorecard_context=sc)

    assert ctx.neighborhood is not None
    assert ctx.neighborhood.traffic is traffic
    # And it survives serialization to the synthesizer's context JSON.
    assert '"MILWAUKEE AVE"' in ctx.model_dump_json()


@pytest.mark.asyncio
async def test_retrieve_traffic_never_overwrites_fresher_fetch():
    """When the turn DID fetch neighborhood data, the grounded (older) traffic
    row must not clobber the live one."""
    fresh = TrafficSummary(road="MILWAUKEE AVE", daily_vehicles=19000, directions=2)
    stale = TrafficSummary(road="MILWAUKEE AVE", daily_vehicles=21200, directions=2)
    sc = _sc(traffic=stale)
    plan = _plan(["property_domain", "neighborhood_domain"])

    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
            patch.object(main_mod, "regulatory_domain", new=AsyncMock()), \
            patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
            patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()), \
            patch.object(main_mod, "neighborhood_domain",
                         new=AsyncMock(return_value=NeighborhoodSummary(traffic=fresh))):
        ctx = await _retrieve(plan, scorecard_context=sc)

    assert ctx.neighborhood is not None
    assert ctx.neighborhood.traffic is fresh


@pytest.mark.asyncio
async def test_retrieve_no_address_violations_on_pin_mismatch():
    """A parcel's at-address record belongs to that parcel — a mismatched grounding
    must not leak its confirmed_zero (which would read as 'this parcel is clean')."""
    sc = _sc(pin="99999999999999", address_violations=AddressViolations(status="confirmed_zero"))
    plan = _plan(["property_domain"])
    with patch.object(main_mod, "property_domain", new=AsyncMock(return_value=None)), \
            patch.object(main_mod, "lookup_zoning", new=AsyncMock(return_value=None)):
        ctx = await _retrieve(plan, scorecard_context=sc)
    assert ctx.address_violations is None


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
