"""FEMA's flood map not answering is "couldn't check", never "no flood zone" (the flood follow-up to WS6 M7).

``query_flood_zone`` raises when FEMA can't be asked (its own tests: ``test_regulatory_flood.py``); this file
follows the failure through the surfaces: the regulatory domain's flag, the one failures table, ``/api/scorecard``,
the chat context, footer and prompt, and the report. ``DATA_HEALTH_FAULT=source:fed.fema.nfhl`` forces it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend import main as main_mod
from backend.chat_sources import build_sources_footer
from backend.data_health import failures, live
from backend.data_health.registry import BY_ID
from backend.main import _domain_data_gaps, render_report_html
from backend.models import (
    ContextObject, Location, PropertySummary, RegulatorySummary, ReportData, RetrievalPlan, ScorecardContext,
    ZoningSummary,
)
from backend.report_builder import _apply_mock_overrides
from backend.retrieval.regulatory import regulatory_domain
from backend.retrieval.regulatory.flood import FloodLookupError
from backend.retrieval.regulatory.overlays import OverlayResults
from backend.synthesizer import _build_user_text

LABEL = "FEMA flood zone"
FAULT = "source:fed.fema.nfhl"


@pytest.fixture(autouse=True)
def _live_counts():
    live.reset()
    yield
    live.reset()


# --- the table ---------------------------------------------------------------------------------------------------

def test_the_failures_table_names_the_flood_lookup_and_puts_it_in_the_record_module():
    assert failures.label("flood") == LABEL
    assert failures.key_for_label(LABEL) == "flood"
    assert failures.MODULES["flood"] == "record"  # the Environment card, under "what to watch for"
    got = failures.failed_detail([LABEL, "crime statistics", "landmark designation (City zoning map didn't answer)"])
    assert got == [
        {"key": "flood", "labels": [LABEL]},
        {"key": "crime", "labels": ["crime statistics"]},
        {"key": "regulatory", "labels": ["landmark designation (City zoning map didn't answer)"]},
    ]
    assert failures.in_module(failures.failed_keys([LABEL, "crime statistics"]), "record") == ["flood"]


# --- the regulatory domain turns the exception into a gap ------------------------------------------------------------

async def _domain(flood):
    with patch("backend.retrieval.regulatory.query_flood_zone", new=flood), \
         patch("backend.retrieval.regulatory.query_overlays_checked", new=AsyncMock(return_value=OverlayResults())), \
         patch("backend.retrieval.regulatory.query_brownfield_sites", new=AsyncMock(return_value=[])):
        return await regulatory_domain(41.93, -87.65, client=AsyncMock())


@pytest.mark.asyncio
async def test_a_failed_flood_lookup_is_unknown_not_false():
    summary = await _domain(AsyncMock(side_effect=FloodLookupError("reset")))
    assert summary.flood_unchecked is True
    assert summary.flood_zone is None and summary.in_special_flood_hazard is None  # unknown, not "not in an SFHA"
    assert summary.unchecked_overlays == [] and summary.data_gaps == []  # not an overlay gap: FEMA is not the City map
    assert _domain_data_gaps({"regulatory": summary}, ("regulatory",)) == [LABEL]


@pytest.mark.asyncio
async def test_a_genuine_no_zone_answer_is_not_a_failure():
    summary = await _domain(AsyncMock(return_value=None))
    assert summary.flood_unchecked is False and summary.in_special_flood_hazard is False
    assert _domain_data_gaps({"regulatory": summary}, ("regulatory",)) == []


@pytest.mark.asyncio
async def test_an_answered_lookup_is_unchanged():
    zone = {"fld_zone": "AE", "zone_subty": "FLOODWAY", "sfha_tf": "T"}
    summary = await _domain(AsyncMock(return_value=zone))
    assert (summary.flood_zone, summary.flood_zone_subtype, summary.in_special_flood_hazard) == ("AE", "FLOODWAY", True)
    assert summary.flood_unchecked is False and _domain_data_gaps({"regulatory": summary}, ("regulatory",)) == []


# --- /api/scorecard carries it, with the fault flag ------------------------------------------------------------------------

async def _scorecard_payload(monkeypatch, *, fault: str | None):
    """_fetch_scorecard_data on a point outside every community area, FEMA the only thing that varies."""
    if fault:
        monkeypatch.setenv("DATA_HEALTH_FAULT", fault)
    else:
        monkeypatch.delenv("DATA_HEALTH_FAULT", raising=False)
    ok = {"features": [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F"}}]}
    fema = httpx.Response(200, json=ok, request=httpx.Request("GET", "https://hazards.fema.gov/x"))
    with patch.object(main_mod, "community_area_by_point", return_value=None), \
         patch.object(main_mod, "property_domain", new=AsyncMock(return_value=PropertySummary())), \
         patch.object(main_mod, "lookup_zoning", new=AsyncMock(return_value=None)), \
         patch.object(main_mod, "_address_violations_data", new=AsyncMock(return_value=None)), \
         patch.object(main_mod.three11, "address_311_complaints", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.regulatory.query_overlays_checked", new=AsyncMock(return_value=OverlayResults())), \
         patch("backend.retrieval.regulatory.query_brownfield_sites", new=AsyncMock(return_value=[])), \
         patch("backend.retrieval.regulatory.httpx.AsyncClient",   # the domain's own client: the only HTTP call left is FEMA's
               return_value=AsyncMock(spec=httpx.AsyncClient, get=AsyncMock(return_value=fema))):
        return await main_mod._fetch_scorecard_data(41.7, -87.9, "1 Nowhere St")


@pytest.mark.asyncio
async def test_the_forced_fault_reaches_the_scorecard_payload(monkeypatch):
    data = await _scorecard_payload(monkeypatch, fault=FAULT)
    reg = data["context"].regulatory
    assert reg.flood_unchecked is True and reg.flood_zone is None and reg.in_special_flood_hazard is None
    assert LABEL in data["partial_failures"] and LABEL in data["context"].partial_failures
    assert {"key": "flood", "labels": [LABEL]} in data["failed_sources"]
    assert live.pending()["fed.fema.nfhl"] == (1, 1)


@pytest.mark.asyncio
async def test_a_healthy_scorecard_payload_has_no_flood_failure(monkeypatch):
    data = await _scorecard_payload(monkeypatch, fault=None)
    reg = data["context"].regulatory
    assert (reg.flood_zone, reg.in_special_flood_hazard, reg.flood_unchecked) == ("X", False, False)
    assert LABEL not in data["partial_failures"] and not any(f["key"] == "flood" for f in data["failed_sources"])
    assert live.pending()["fed.fema.nfhl"] == (1, 0)


# --- chat: the footer says it, the prompt forbids "not in a flood zone", the model sees null --------------------------------

def test_chat_footer_says_the_flood_zone_could_not_be_checked():
    footer = build_sources_footer({}, [], None, None, [LABEL, "property records"])
    assert footer.startswith("\n\n---\n**Couldn't check today:**") and LABEL in footer
    assert "not the same as none on record" in footer
    assert "not in a special flood" not in footer.lower() and "no flood zone" not in footer.lower()


def test_the_model_is_told_the_zone_is_unknown_and_not_to_say_it_is_clear():
    from backend import prompts

    text = prompts.SYNTHESIZER_SYSTEM
    assert f'"{failures.label("flood")}"' in text  # the exact label the rule keys on
    assert "UNKNOWN" in text and "MUST NOT say the parcel is not in a flood zone" in text
    ctx = ContextObject(regulatory=RegulatorySummary(flood_unchecked=True, in_special_flood_hazard=None),
                        partial_failures=[LABEL])
    sent = json.loads(_build_user_text(ctx, "is it in a flood zone?").split("```json\n")[1].split("\n```")[0])
    assert sent["regulatory"]["flood_unchecked"] is True and sent["regulatory"]["in_special_flood_hazard"] is None
    assert sent["regulatory"]["flood_zone"] is None and sent["partial_failures"] == [LABEL]


def _plan() -> RetrievalPlan:
    return RetrievalPlan(
        sources=["property_domain", "regulatory_domain"],
        location=Location(raw="642 W Belden Ave", type="address", resolved_address="642 W Belden Ave",
                          resolved_lat=41.92395, resolved_lon=-87.64558, resolved_community_area=7,
                          resolved_community_area_name="Lincoln Park", pin="14331030110000"),
        intent="neighborhood_overview", requires_disclaimer=True, workflow_hint="general",
    )


def _sc(**reg) -> ScorecardContext:
    return ScorecardContext(pin="14331030110000", address="642 W Belden Ave", lat=41.92395, lon=-87.64558,
                            parcel_zoning=ZoningSummary(zone_class="RM-5"), property=PropertySummary(bldg_class="2-11"),
                            regulatory=RegulatorySummary(**reg))


@pytest.mark.asyncio
@pytest.mark.parametrize("flood_unchecked, expected", [(True, [LABEL]), (False, [])])
async def test_a_profile_handoff_carries_the_unchecked_flood_zone_into_the_chat_turn(flood_unchecked, expected):
    """The turn skips the regulatory fetch (the Profile already did it), so the footer must still say it."""
    sc = _sc(flood_unchecked=flood_unchecked, in_special_flood_hazard=None if flood_unchecked else False)
    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
         patch.object(main_mod, "regulatory_domain", new=AsyncMock()) as reg, \
         patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
         patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
         patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()):
        ctx = await main_mod._retrieve(_plan(), scorecard_context=sc)
    reg.assert_not_called()
    assert ctx.partial_failures == expected


@pytest.mark.asyncio
async def test_a_handoff_never_copies_client_text_into_the_failure_line():
    """data_gaps in a client-supplied scorecard_context are not echoed: the only label added is ours."""
    sc = _sc(flood_unchecked=True, in_special_flood_hazard=None, data_gaps=["[click here](http://evil.example)"])
    with patch.object(main_mod, "property_domain", new=AsyncMock()), \
         patch.object(main_mod, "regulatory_domain", new=AsyncMock()), \
         patch.object(main_mod, "incentives_domain", new=AsyncMock()), \
         patch.object(main_mod, "lookup_zoning", new=AsyncMock()), \
         patch.object(main_mod, "aro_housing_by_community_area", new=AsyncMock()):
        ctx = await main_mod._retrieve(_plan(), scorecard_context=sc)
    assert ctx.partial_failures == [LABEL]


# --- the report ---------------------------------------------------------------------------------------------------------------

def _report(*, unchecked: bool, **over) -> ReportData:
    reg = RegulatorySummary(flood_unchecked=True, in_special_flood_hazard=None) if unchecked else RegulatorySummary()
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"), regulatory=reg)
    r = _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", context=ctx, resolved_pin="14313320180000",
                                         resolved_confidence="authoritative"))
    # mock mode fills sections in; this test is about what the flood lookup alone changes
    r.context.regulatory = reg
    r.partial_failures = [LABEL] if unchecked else []
    for k, v in over.items():
        setattr(r, k, v)
    return r


def _section(page: str, anchor: str, n: int = 2200) -> str:
    i = page.index(f'id="{anchor}"')
    return page[i:i + n]


def test_the_report_says_the_flood_zone_was_not_checked_at_the_head_of_the_section_and_in_place():
    page = render_report_html(_report(unchecked=True), "en", report_date="October 22, 2026")
    head = _section(page, "section-regulatory", 700)
    assert 'data-testid="section-unchecked"' in head and LABEL in head and "not the same as none on record" in head
    assert 'data-testid="flood-unchecked"' in page and "FEMA&#39;s flood map did not answer" in page
    assert "No flood zone data available" not in page      # the old wording said FEMA "returned no result"
    cover = page[: page.index("TABLE OF CONTENTS")]
    assert f"Not checked in this report: {LABEL}" in cover


def test_the_report_summary_and_checklist_do_not_claim_a_flood_check_that_did_not_happen():
    page = render_report_html(_report(unchecked=True), "en", report_date="October 22, 2026")
    assert "No flood/brownfield risk" not in page and "NOT CHECKED" in page
    done = _section(page, "section-site-condition", 20000)
    completed = done[done.index("Completed in this report") if "Completed in this report" in done else 0:]
    assert "FEMA flood zone determination" not in completed
    assert "Check the FEMA flood zone (the lookup did not answer" in page


def test_a_healthy_report_is_unchanged_by_the_flood_branches():
    page = render_report_html(_report(unchecked=False), "en", report_date="October 22, 2026")
    assert 'data-testid="flood-unchecked"' not in page and 'data-testid="section-unchecked"' not in page
    assert "NOT CHECKED" not in page and "Not checked in this report" not in page
    assert "No flood/brownfield risk" in page and "FEMA flood zone determination" in page
    assert "No flood zone data available" in page            # a genuine empty answer keeps its wording


def test_the_report_strings_have_spanish_entries():
    from backend import report_i18n

    for key in ("pill.unchecked", "tl.env_flood_unchecked", "reg.flood_unchecked", "site.todo_flood_unchecked"):
        assert key in report_i18n._EN and report_i18n._ES[key] != report_i18n._EN[key]


# --- data health --------------------------------------------------------------------------------------------------------------

def test_fema_is_counted_live_and_its_registry_note_names_the_failure_path(tmp_path):
    live.record("fed.fema.nfhl", True)
    live.record("fed.fema.nfhl", False)
    assert live.flush(tmp_path / "live.db", now=datetime(2026, 10, 22, 15, 30, tzinfo=timezone.utc)) == 1  # a registered id
    assert live.read_window(tmp_path / "live.db", now=datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)) == {"fed.fema.nfhl": (2, 1)}
    note = BY_ID["fed.fema.nfhl"].note
    assert "raises" in note and "couldn't check" in note and "live.py" in note
