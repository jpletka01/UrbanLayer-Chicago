"""Regression tests for Phase 2 report-credibility fixes.

Guards the credibility findings from the V6 real-data audit so they cannot
silently regress. See claude-context/guides/report-v6-execution-plan.md (Phase 2).

Covers:
- P4    — 311 severity taxonomy (rodent baiting is routine service, not site risk)
- Q12/P9 — class EX labeled "exempt", not "standard"
- Q9    — Lakefront Protection District flag is correct; only the lead label changes
- Q11   — National Register district name preserved verbatim (not a bug)
- D6    — overlay bracket dedup precondition (name == description for nameless layers)
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.assembler import assemble_context
from backend.models import Location, PropertySummary, RetrievalPlan
from backend.retrieval.regulatory import regulatory_domain
from backend.retrieval.three11 import address_311_complaints


def _plan(**kwargs) -> RetrievalPlan:
    loc = Location(raw="Lincoln Park", type="address", resolved_community_area=7)
    defaults = dict(
        sources=["property_domain", "incentives_domain"],
        location=loc,
        intent="incident_lookup",
        time_range_days=90,
        requires_disclaimer=False,
    )
    defaults.update(kwargs)
    return RetrievalPlan(**defaults)


# --- P4: 311 severity taxonomy ---------------------------------------------


@pytest.mark.asyncio
async def test_p4_rodent_baiting_is_routine_not_high_risk():
    """Rodent/rat complaints are routine City abatement — not structural high-risk."""
    rows = [
        {"sr_type": "Rodent Baiting/Rat Complaint", "status": "Open", "created_date": "2026-01-01"},
        {"sr_type": "No Heat", "status": "Open", "created_date": "2026-01-02"},
    ]
    with patch("backend.retrieval.three11.socrata_get", AsyncMock(return_value=rows)):
        result = await address_311_complaints(41.9307, -87.6411)

    # Structural complaint stays high-risk; rodent moves to routine service.
    assert result["high_risk_flags"] == ["No Heat"]
    assert "Rodent Baiting/Rat Complaint" not in result["high_risk_flags"]
    assert result["routine_service_flags"] == ["Rodent Baiting/Rat Complaint"]


@pytest.mark.asyncio
async def test_p4_no_structural_risk_when_only_routine():
    """A parcel with only a rat complaint has no high-risk site-condition flag."""
    rows = [
        {"sr_type": "Rodent Baiting/Rat Complaint", "status": "Completed", "created_date": "2026-01-01"},
    ]
    with patch("backend.retrieval.three11.socrata_get", AsyncMock(return_value=rows)):
        result = await address_311_complaints(41.9307, -87.6411)

    assert result["high_risk_flags"] == []
    assert result["routine_service_flags"] == ["Rodent Baiting/Rat Complaint"]


# --- Q12/P9: class EX is exempt, not "standard" ----------------------------


def test_q12_ex_class_labeled_exempt_not_standard():
    prop = PropertySummary(pin="14283190070000", bldg_class="EX", tax_exempt=True)
    ctx = assemble_context(plan=_plan(), property_summary=prop)
    assert ctx.incentives is not None
    assert ctx.incentives.property_tax_class == "exempt"
    assert "standard classification" not in (ctx.incentives.tax_incentive_description or "")
    assert "tax-exempt" in (ctx.incentives.tax_incentive_description or "").lower()


def test_q12_standard_class_still_standard():
    """A genuine non-incentive, non-exempt class is still labeled 'standard'."""
    prop = PropertySummary(pin="1", bldg_class="2-11")
    ctx = assemble_context(plan=_plan(), property_summary=prop)
    assert ctx.incentives is not None
    assert ctx.incentives.property_tax_class == "standard"


def test_q12_incentive_class_unchanged():
    """Class 6b stays an incentive class, not exempt/standard."""
    prop = PropertySummary(pin="1", bldg_class="6b")
    ctx = assemble_context(plan=_plan(), property_summary=prop)
    assert ctx.incentives is not None
    assert ctx.incentives.property_tax_class == "6B"


# --- Q9: Lakefront flag correct; lead label is the district, not the subtype ---


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(return_value=[]))
@patch("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None))
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_q9_lakefront_leads_with_district_name(mock_overlays):
    # Layer 3 = Lakefront Protection District; feature NAME is the subtype.
    mock_overlays.return_value = [(3, {"NAME": "Private Lakefront"})]
    result = await regulatory_domain(41.9307, -87.6411, client=AsyncMock())

    assert result.in_lakefront_protection is True  # flag stays — it is correct
    ov = result.overlays[0]
    assert ov.name == "Lakefront Protection District"   # leads with the district
    assert ov.description == "Private Lakefront"          # subtype demoted to qualifier


# --- Q11: National Register district name preserved (this was NOT a bug) -----


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(return_value=[]))
@patch("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None))
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_q11_national_register_name_preserved(mock_overlays):
    # The Lakeview Historic District is a real NR district that spans into Lincoln Park.
    mock_overlays.return_value = [(8, {"NAME": "Lakeview Historic District"})]
    result = await regulatory_domain(41.9307, -87.6411, client=AsyncMock())

    ov = result.overlays[0]
    assert ov.name == "Lakeview Historic District"
    assert ov.description == "National Register Districts"
    assert result.on_national_register is True


# --- D6: nameless overlay layers get name == description so template dedups ---


@pytest.mark.asyncio
@patch("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(return_value=[]))
@patch("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None))
@patch("backend.retrieval.regulatory.query_all_overlays")
async def test_d6_nameless_overlay_name_equals_description(mock_overlays):
    # Layer 17 (ADU) returns no NAME field → name falls back to layer name == description.
    mock_overlays.return_value = [(17, {"ADU_AREA": "No Limitations"})]
    result = await regulatory_domain(41.9307, -87.6411, client=AsyncMock())

    ov = result.overlays[0]
    # Template suppresses the [bracket] when these are equal (case-insensitive).
    assert ov.name.strip().lower() == ov.description.strip().lower()
