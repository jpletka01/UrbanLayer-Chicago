"""WS0 M6: the confidence standard in chat.

- a withheld figure's value is removed from the context before the model sees it, and listed with its reason;
- the provenance map is stored on the context, reaches the sidebar and the stored message, and never the model;
- an area-only turn gets dated entries, and its sources footer says period and margin;
- the prompt rule asks for period, margin and the withheld reason.

No model is called: the synthesizer's input is built and inspected, never sent.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import db
from backend.chat_sources import build_sources_footer
from backend.main import _provenance_for, app
from backend.models import (
    CensusTractDemographics, ComparableSale, ComparablesSummary, ContextObject, CrimeSummary, DemographicsSummary,
    Location, NeighborhoodSummary, PropertySummary, RetrievalPlan, StoredMessage, WalkScoreSummary, ZoningSummary,
)
from backend.provenance import withhold_low_evidence
from backend.synthesizer import _build_user_text


def tract(**kw) -> CensusTractDemographics:
    base = dict(
        tract_fips="17031831000", tract_name="Census Tract 8310, Cook, IL", census_reporter_url="https://censusreporter.org/x",
        median_gross_rent=2435, poverty_rate=1.0, population=2431, median_household_income=91234,
        acs_period="2020–2024", acs_release="acs2024_5yr",
        moe={"median_gross_rent": 220.0, "poverty_rate": 2.5, "median_household_income": 8000.0},
        cv={"median_gross_rent": 0.055, "poverty_rate": 0.61, "median_household_income": 0.05},
    )
    return CensusTractDemographics(**{**base, **kw})


def area_ctx(**kw) -> ContextObject:
    kw.setdefault("community_area", 24)
    kw.setdefault("community_area_name", "West Town")
    kw.setdefault("neighborhood", NeighborhoodSummary(census_tract=tract()))
    return ContextObject(**kw)


def comps(n: int) -> ComparablesSummary:
    sales = [ComparableSale(pin=f"1431332018{i:04d}", sale_price=1_000_000 + i, sale_date="2025-05-01", price_per_land_sqft=300.0 + i) for i in range(n)]
    return ComparablesSummary(
        median_sale_price=1_234_567.0, median_price_per_land_sqft=301.0, sales_volume=n, sales=sales,
        comp_radius_mi=0.25, comp_window_years=3,
    )


def model_text(ctx: ContextObject) -> str:
    """What the synthesizer would send the model, as text."""
    return _build_user_text(ctx, "question")


def run(ctx: ContextObject) -> dict:
    return withhold_low_evidence(ctx, _provenance_for(ctx))


# --- withholding -------------------------------------------------------------------------------------------

def test_a_withheld_tract_figure_never_reaches_the_model_and_says_why():
    ctx = area_ctx()
    assert "poverty_rate" in model_text(ctx)
    run(ctx)
    text = model_text(ctx)
    assert ctx.neighborhood.census_tract.poverty_rate is None
    assert "poverty_rate\": null" in text and "\"poverty_rate\": 1.0" not in text
    assert "poverty_rate" not in ctx.neighborhood.census_tract.moe and "poverty_rate" not in ctx.neighborhood.census_tract.cv
    (w,) = ctx.withheld_figures
    assert w.fact_id == "area.tract.poverty_rate"
    assert w.reason == "the margin of error is 61% of the estimate"
    assert "withheld_figures" in text and w.reason in text
    # the rest of the tract is untouched
    assert ctx.neighborhood.census_tract.median_gross_rent == 2435 and ctx.neighborhood.census_tract.moe["median_gross_rent"] == 220.0


def test_the_withheld_entry_stays_in_the_map_without_its_value():
    ctx = area_ctx()
    prov = run(ctx)
    e = prov["area.tract.poverty_rate"]
    assert e["confidence"] == "withheld" and "value" not in e
    assert prov["area.tract.median_gross_rent"]["value"] == 2435
    assert ctx.provenance is prov


def test_clearing_a_figure_never_edits_the_shared_cached_object():
    shared = tract()
    ctx = area_ctx(neighborhood=NeighborhoodSummary(census_tract=shared))
    run(ctx)
    assert ctx.neighborhood.census_tract.poverty_rate is None
    assert shared.poverty_rate == 1.0 and "poverty_rate" in shared.cv  # the next request still sees it (and withholds it itself)


def test_thin_comps_lose_their_medians_but_keep_the_sales():
    ctx = ContextObject(parcel_zoning=ZoningSummary(zone_class="B3-2"), comparables=comps(2))
    run(ctx)
    c = ctx.comparables
    assert c.median_sale_price is None and c.median_price_per_land_sqft is None and len(c.sales) == 2
    reasons = {w.fact_id: w.reason for w in ctx.withheld_figures}
    assert reasons["property.comps.median_price"] == "only 2 sales (needs 3)"
    assert "1234567" not in model_text(ctx) and "1000001" in model_text(ctx)  # the median goes, the sales stay


def test_four_comps_are_faded_not_withheld_and_a_trimmed_handoff_does_not_change_the_state():
    ctx = ContextObject(parcel_zoning=ZoningSummary(zone_class="B3-2"), comparables=comps(4))
    prov = run(ctx)
    assert ctx.withheld_figures is None and ctx.comparables.median_sale_price == 1_234_567.0
    assert prov["property.comps.median_price"]["confidence"] == "low"
    # the Profile trims the handoff to 8 sales: 8 of 20 and 20 of 20 are both standard
    ctx8 = ContextObject(parcel_zoning=ZoningSummary(zone_class="B3-2"), comparables=comps(8))
    assert run(ctx8)["property.comps.median_price"]["confidence"] == "standard"


def test_every_figure_that_can_be_withheld_has_a_place_to_be_cleared():
    """The state is decided per fact id; the value lives in a field. A figure the rules can withhold but this
    module cannot clear would keep reaching the model, so each is pinned here."""
    from backend.provenance import _COMMUNITY_AREA_FIELDS, _COMPS_FIELDS, _clear_figure
    from backend.provenance_figures import _TRACT_ORDER

    dm = DemographicsSummary(community_area=24, community_area_name="West Town", population=87781, median_household_income=98000)
    ctx = ContextObject(neighborhood=NeighborhoodSummary(census_tract=tract(), demographics=dm), comparables=comps(5))
    for field in _TRACT_ORDER:
        assert _clear_figure(ctx, f"area.tract.{field}"), field
    for fact in (*_COMPS_FIELDS, *_COMMUNITY_AREA_FIELDS):
        assert _clear_figure(ctx, fact), fact
    assert not _clear_figure(ctx, "area.crime")  # nothing else is clearable: it is told to the model as withheld instead


def test_a_turn_with_nothing_to_withhold_has_no_withheld_key_in_the_model_text():
    ctx = area_ctx(neighborhood=NeighborhoodSummary(census_tract=tract(poverty_rate=4.6, cv={"poverty_rate": 0.1})))
    run(ctx)
    assert ctx.withheld_figures is None
    assert "withheld_figures" not in model_text(ctx)


# --- naming what survives ----------------------------------------------------------------------------------

def test_estimates_and_calculations_are_noted_and_official_records_are_not():
    dm = DemographicsSummary(community_area=24, community_area_name="West Town", population=87000,
                             median_household_income=98000, acs_period="2019–2023")
    ctx = area_ctx(
        neighborhood=NeighborhoodSummary(
            census_tract=tract(poverty_rate=4.6, cv={"poverty_rate": 0.1}), demographics=dm,
            walkscore=WalkScoreSummary(walk_score=91, ws_link="https://walkscore.com/x")),
        crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}),
    )
    run(ctx)
    notes = {n.fact_id: n.note for n in ctx.figure_notes}
    assert "Low confidence" in notes["area.community_area.median_household_income"] and "no margin of error" in notes["area.community_area.median_household_income"]
    assert "private company" in notes["neighborhood.walkscore"].lower()
    assert "area.crime" not in notes and "area.tract.median_gross_rent" not in notes  # official records and standard ACS: no note
    text = model_text(ctx)
    assert "figure_notes" in text and "private company" in text.lower()


def test_figure_notes_are_capped():
    ctx = ContextObject(parcel_zoning=ZoningSummary(zone_class="B3-2"), property=PropertySummary(pin14="14313320180000"))
    prov = {f"x.{i}": {"label": f"Figure {i}", "tier": "our_calculation", "method_key": "calculation", "confidence": "standard",
                       "confidence_reasons": [], "query_date": "2026-10-22", "period": "2025"} for i in range(40)}
    withhold_low_evidence(ctx, prov)
    assert len(ctx.figure_notes) == 16


# --- the map stays off the model --------------------------------------------------------------------------

def test_the_provenance_map_is_stored_but_never_sent_to_the_model():
    ctx = area_ctx(crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}))
    run(ctx)
    assert ctx.provenance and "area.tract.median_gross_rent" in ctx.provenance
    text = model_text(ctx)
    assert "confidence_reasons" not in text and "\"provenance\"" not in text and "query_date" not in text
    assert "provenance" in ctx.model_dump(mode="json")


def test_the_profile_context_payload_is_unchanged():
    d = ContextObject(parcel_zoning=ZoningSummary(zone_class="B3-2")).model_dump(exclude_none=True)
    assert not {"provenance", "withheld_figures", "figure_notes"} & d.keys()


# --- area-only turns ------------------------------------------------------------------------------------------

def test_a_parcel_less_turn_gets_dated_area_entries_and_a_footer_that_says_period_and_margin():
    ctx = area_ctx(crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}), data_lag_cutoff="2026-10-14")
    prov = run(ctx)
    assert {"area.crime", "area.tract.median_gross_rent", "geo.community_area"} <= prov.keys()
    footer = build_sources_footer(prov, [], "2026-03-18")
    assert footer.startswith("\n\n---\n**Sources for the data used**")
    lines = footer.splitlines()
    tract_line = next(line for line in lines if "Census Tract 8310" in line)
    assert "margins of error at the 90% level" in tract_line
    assert "last 90 days" in next(line for line in lines if "West Town" in line and "Crime" in line)
    dates = next(line for line in lines if line.startswith("- **Data dates:**"))
    assert "ACS (tract) 2020–2024" in dates and "Crime through Oct 14, 2026" in dates
    assert "poverty" not in footer.lower()  # nothing about a withheld figure


def test_a_feed_with_no_publisher_date_says_when_we_asked():
    ctx = ContextObject(community_area=24, community_area_name="West Town", crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}))
    dates = next(x for x in build_sources_footer(run(ctx), [], None).splitlines() if x.startswith("- **Data dates:**"))
    assert dates.startswith("- **Data dates:** Crime checked ") and "through" not in dates


def test_a_parcel_answer_keeps_its_heading_and_gains_the_area_lines():
    ctx = area_ctx(parcel_zoning=ZoningSummary(zone_class="B3-2"))
    prov = run(ctx)
    footer = build_sources_footer(prov, [], "2026-03-18")
    assert "Sources for the parcel data used" in footer and "2020–2024" in footer


def test_no_footer_for_a_turn_without_sources():
    assert build_sources_footer(run(ContextObject(community_area=24)), [], None) == ""


# --- through the chat endpoint ---------------------------------------------------------------------------------

@pytest.fixture
def client():
    with patch("backend.main.get_settings") as s, patch("backend.main.db") as mdb:
        s.return_value = MagicMock(anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
                                   router_model="m", synthesizer_model="m", message_limit=10)
        mdb.init_db = AsyncMock()
        mdb.close_db = AsyncMock()
        mdb.count_user_messages = AsyncMock(return_value=0)
        yield TestClient(app)


def test_the_chat_stream_carries_the_map_and_the_model_gets_no_withheld_value(client):
    plan = RetrievalPlan(sources=["neighborhood_domain"], location=Location(raw="Wicker Park", type="neighborhood", resolved_community_area=24,
                         resolved_community_area_name="West Town"), intent="neighborhood_overview")
    seen: dict = {}

    def fake_stream_answer(**kwargs):
        seen["model_text"] = _build_user_text(kwargs["context"], "q")

        async def gen():
            yield "The tract's rent is about $2,435."
        return gen()

    with patch("backend.main.route", new_callable=AsyncMock, return_value=plan), \
         patch("backend.main._retrieve", new_callable=AsyncMock, return_value=area_ctx()), \
         patch("backend.main._fetch_map_rows", new_callable=AsyncMock, return_value={}), \
         patch("backend.main.stream_answer", side_effect=fake_stream_answer):
        resp = client.post("/chat", json={"message": "q", "history": []})
    events = [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]
    context = next(e for e in events if e["type"] == "context")["context"]
    assert context["provenance"]["area.tract.poverty_rate"]["confidence"] == "withheld"
    assert context["withheld_figures"][0]["fact_id"] == "area.tract.poverty_rate"
    assert "poverty_rate" not in context["neighborhood"]["census_tract"]  # the chunk drops nulls: the sidebar cannot show it
    assert "confidence_reasons" not in seen["model_text"] and "\"poverty_rate\": 1.0" not in seen["model_text"]
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "Sources for the data used" in text and "2020–2024" in text
    done = next(e for e in events if e["type"] == "done")
    assert not done.get("citation_warnings")


# --- stored with the answer -----------------------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    settings = MagicMock()
    settings.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        yield
        await db.close_db()


async def test_provenance_survives_a_save_and_load_and_an_old_message_still_loads(test_db):
    ctx = area_ctx()
    run(ctx)
    sent = json.loads(json.dumps(ctx.model_dump(mode="json", exclude_none=True)))  # the SSE chunk the browser holds
    old = {"community_area": 24, "community_area_name": "West Town", "requires_disclaimer": False, "code_chunks": []}
    stored = [StoredMessage(role="assistant", content="answer", context=sent), StoredMessage(role="assistant", content="old", context=old)]

    await db.create_conversation("c1", "t", None)
    await db.save_messages("c1", [m.model_dump(exclude_none=True) for m in stored])
    got = (await db.get_conversation("c1", None))["messages"]

    new = ContextObject.model_validate(got[0]["context"])
    assert new.provenance == ctx.provenance  # the dates it was given, not recomputed
    assert new.withheld_figures[0].fact_id == "area.tract.poverty_rate"
    old_ctx = ContextObject.model_validate(got[1]["context"])
    assert old_ctx.provenance is None and old_ctx.withheld_figures is None and old_ctx.figure_notes is None


def test_a_saved_message_cannot_carry_an_unbounded_map():
    with pytest.raises(ValueError):
        ContextObject(provenance={str(i): {} for i in range(401)})


# --- the prompt rule ------------------------------------------------------------------------------------------------------

def test_prompt_rule_38_asks_for_period_margin_and_the_withheld_reason():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("38. HOW SURE EACH FIGURE IS")
    rule = SYNTHESIZER_SYSTEM[i : i + 2600]
    for needle in ("period", "acs_period", "margin of error", "`moe`", "five income brackets", "`withheld_figures`", "NEVER state",
                   "`reason`", "`figure_notes`", "never the date the data describes"):
        assert needle in rule, needle
