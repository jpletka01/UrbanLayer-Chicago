"""V5: chat sources the model does not write.

The kit's 7 baseline answers carried 18 URLs, including American Legal links whose
ids the model composed (one id cited for two different sections) and Legistar links
nobody supplied. A reader clicking one lands somewhere that doesn't say what the
answer claims. Contract: a URL survives only if WE supplied it; a sources block is
appended from the provenance map and the chunks actually cited."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.chat_sources import UrlGuard, allowed_urls, build_sources_footer, cited_chunks
from backend.citations import citation_problems
from backend.main import app
from backend.models import (
    CodeChunk, ContextObject, Location, NeighborhoodSummary, OverlayDistrict, PropertySummary,
    RegulatorySummary, RetrievalPlan, WardInfo, ZoningSummary,
)
from backend.provenance import build_provenance
from backend.retrieval.zoning_definitions import get_zone_definition

OK = "https://www.chicago.gov/ok"


def _run(text: str, size: int, allowed=frozenset({OK})) -> tuple[str, list[str]]:
    g = UrlGuard(set(allowed))
    out = "".join(g.filter(iter([text[i : i + size] for i in range(0, len(text), size)])))
    return out, g.dropped


# --- the guard: identical output however the stream is chunked -------------------------------------

CASES = [
    ("See [the code](https://codelibrary.amlegal.com/x/0-0-0-563405) and [letter](https://www.chicago.gov/ok) or https://bad.example/a. Done [1] [data:crime].",
     "See the code and [letter](https://www.chicago.gov/ok) or . Done [1] [data:crime]."),
    ("A (https://bad.example/p) b and (see https://www.chicago.gov/ok) c.", "A () b and (see https://www.chicago.gov/ok) c."),
    ("Cite [1], [2] and [data:permits]; ranges [see below] stay.", "Cite [1], [2] and [data:permits]; ranges [see below] stay."),
    ("Link [**bold** label](https://x.test/z) end", "Link **bold** label end"),
    ("Anchor [top](#top) and mail [me](mailto:a@b.co) stay.", "Anchor [top](#top) and mail [me](mailto:a@b.co) stay."),
    ("Verify at [§17-2-0304](https://codelibrary.amlegal.com/codes/chicago/latest/chicago_il/0-0-0-563405).", "Verify at §17-2-0304."),
    ("Trailing bracket that never closes [ and text", "Trailing bracket that never closes [ and text"),
    ("Titled [x](https://bad.test/y \"a title\") ok", "Titled x ok"),
]


@pytest.mark.parametrize("text,want", CASES)
def test_the_output_is_the_same_for_every_way_the_stream_is_chunked(text, want):
    for size in list(range(1, 45)) + [len(text), len(text) + 5]:
        out, _ = _run(text, size)
        assert out == want, (size, out)


def test_invented_urls_are_recorded_and_allowed_ones_are_not():
    _, dropped = _run("[a](https://bad.test/1) https://bad.test/2. [b](https://www.chicago.gov/ok)", 3)
    assert dropped == ["https://bad.test/1", "https://bad.test/2"]


def test_an_allowed_url_matches_despite_a_trailing_slash_fragment_or_punctuation():
    out, dropped = _run("Go to https://www.chicago.gov/ok/, or https://www.chicago.gov/ok#frag.", 5)
    assert out == "Go to https://www.chicago.gov/ok/, or https://www.chicago.gov/ok#frag." and dropped == []


def test_an_endless_unclosed_bracket_cannot_stall_the_stream():
    g = UrlGuard(set())
    emitted = g.feed("[" + "x" * 1000)
    assert len(emitted) > 0  # released once the hold limit is passed
    assert (emitted + g.flush()).startswith("[xxx")


def test_nothing_is_lost_at_the_end_of_the_stream():
    g = UrlGuard(set())
    assert g.feed("ends mid link [label](https://bad.test/ab") == "ends mid link "
    assert g.flush() == "label"  # an unterminated link keeps its words, not the target


# --- what we allow ----------------------------------------------------------------------------------------

def _ctx() -> ContextObject:
    ctx = ContextObject(
        parcel_zoning=ZoningSummary(zone_class="RM-4.5", ordinance_num="A7210", ordinance_date="2007-09-05", map_updated="2021-10-27",
                                    clerk_url="https://chicityclerkelms.chicago.gov/Matter/?matterId=abc"),
        regulatory=RegulatorySummary(overlays=[
            OverlayDistrict(layer_type="special_district", name="Predominance of the Block (606) District",
                            link="https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-53035"),
            OverlayDistrict(layer_type="planned_development", name="Planned Development 835", link="https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf"),
            OverlayDistrict(layer_type="aro_zone", name="Affordable Requirements Ordinance Zones"),
        ]),
        property=PropertySummary(pin14="16012280180000", land_sqft=3191, land_sqft_source="geometry"),
        neighborhood=NeighborhoodSummary(ward=WardInfo(ward=26, alderman="Jessica Fuentes", website="https://ward26.org")),
        parcel_pin="16012280180000", parcel_resolution="authoritative",
    )
    ctx.zone_definition = get_zone_definition("RM-4.5").__dict__
    return ctx


def test_allowed_urls_are_exactly_the_ones_we_supplied():
    allowed = allowed_urls(_ctx())
    assert allowed >= {
        "https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf",
        "https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-53035",  # the layer's own 606 link
        "https://chicityclerkelms.chicago.gov/Matter/?matterId=abc",
        "https://www.cookcountyassessor.com/pin/16012280180000",
        "https://ward26.org",
    }
    assert any(u.startswith("https://www.chicago.gov/city/en/depts/dcd/supp_info/office_of_the_zoningadministrator") for u in allowed)
    # a model-composed American Legal id is not among them
    assert not allowed & {"https://codelibrary.amlegal.com/codes/chicago/latest/chicago_il/0-0-0-563405"}


# --- the footer -----------------------------------------------------------------------------------------------

def _chunks():
    def mk(sec: str, title: str) -> CodeChunk:
        return CodeChunk(text="t", source_document="d", section=sec, section_title=title, subsection=None, score=1.0, cross_references=[])

    return [mk("17-2-0300", "Bulk and density standards"), mk("17-10-0100", "Parking")]


def test_footer_lists_dated_sources_for_the_parcel_data_and_the_chunks_cited():
    ctx = _ctx()
    prov = build_provenance(context=ctx, zone_definition=ctx.zone_definition, resolved_pin=ctx.parcel_pin, resolved_confidence="authoritative", query_date="2026-10-02")
    answer = "RM-4.5 allows FAR 1.7 [1]. Parking relief [2] and again [1]."
    footer = build_sources_footer(prov, cited_chunks(answer, _chunks()), "2026-03-18")
    assert footer.startswith("\n\n---\n**Sources for the parcel data used**")
    assert "Zoning district RM-4.5" in footer and "ordinance A7210" in footer
    assert "effective 2007-09-05" in footer and "record updated 2021-10-27" in footer and "queried 2026-10-02" in footer
    assert "§17-2-0304-A / §17-2-0311-A / §17-2-0303-A, code current through 2026-03-18" in footer
    assert "[source](https://codelibrary.amlegal.com/codes/chicago/latest/chicagozoning_il/0-0-0-53035)" in footer  # the layer's link, not invented
    assert "[assessor record](https://www.cookcountyassessor.com/pin/16012280180000)" in footer
    assert "- [1] Municipal Code §17-2-0300 — Bulk and density standards (code current through 2026-03-18)" in footer
    assert "- [2] Municipal Code §17-10-0100 — Parking" in footer
    assert footer.index("[1] Municipal Code") < footer.index("[2] Municipal Code")


def test_only_chunks_the_answer_cited_and_that_exist_are_listed():
    assert [n for n, _ in cited_chunks("see [2] and [9] and [0] and [data:crime]", _chunks())] == [2]
    assert cited_chunks("no citations", _chunks()) == []


def test_no_footer_when_there_is_nothing_to_list():
    assert build_sources_footer({}, [], "2026-03-18") == ""


def test_the_guard_never_strips_the_links_the_footer_itself_adds():
    ctx = _ctx()
    prov = build_provenance(context=ctx, zone_definition=ctx.zone_definition, resolved_pin=ctx.parcel_pin, resolved_confidence="authoritative", query_date="2026-10-02")
    footer = build_sources_footer(prov, [], "2026-03-18")
    out, dropped = _run(footer, 7, allowed=allowed_urls(ctx))
    assert out == footer and dropped == []


# --- citation markers backed by provenance ------------------------------------------------------------------------

def test_a_parcel_fact_marker_is_valid_only_when_the_turn_has_that_provenance():
    keys = frozenset({"zoning.far"})
    assert citation_problems("FAR is 1.7 [data:zoning.far].", 0, set(), provenance_keys=keys) == []
    assert citation_problems("FAR is 1.7 [data:zoning.far].", 0, set()) == ["[data:zoning.far] is not a known data source"]
    assert citation_problems("[data:zoning.height]", 0, set(), provenance_keys=keys) == ["[data:zoning.height] is not a known data source"]
    assert citation_problems("[data:crime]", 0, {"crime"}, provenance_keys=keys) == []


# --- through the chat endpoint -------------------------------------------------------------------------------------------

@pytest.fixture
def client():
    with patch("backend.main.get_settings") as s, patch("backend.main.db") as db:
        s.return_value = MagicMock(anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
                                   router_model="m", synthesizer_model="m", message_limit=10)
        db.init_db = AsyncMock()
        db.close_db = AsyncMock()
        db.count_user_messages = AsyncMock(return_value=0)
        yield TestClient(app)


def _chat(client, tokens, context, *, stop_reason="end_turn"):
    plan = RetrievalPlan(sources=["regulatory_domain"], location=Location(raw="Wicker Park", type="neighborhood", resolved_community_area=24,
                         resolved_community_area_name="West Town"), intent="neighborhood_overview")

    def fake_stream_answer(**kwargs):
        async def gen():
            for t in tokens:
                yield t
            kwargs["outcome"]["stop_reason"] = stop_reason
        return gen()

    with patch("backend.main.route", new_callable=AsyncMock, return_value=plan), \
         patch("backend.main._retrieve", new_callable=AsyncMock, return_value=context), \
         patch("backend.main._fetch_map_rows", new_callable=AsyncMock, return_value={}), \
         patch("backend.main.stream_answer", side_effect=fake_stream_answer):
        resp = client.post("/chat", json={"message": "q", "history": []})
    events = [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]
    return "".join(e["text"] for e in events if e["type"] == "token"), next(e for e in events if e["type"] == "done")


def test_a_model_composed_link_never_reaches_the_reader_and_the_sources_are_appended(client):
    ctx = _ctx()
    ctx.code_chunks = _chunks()
    model = "RM-4.5 allows 4 units [1]. See [the code](https://codelibrary.amlegal.com/codes/chicago/latest/chicago_il/0-0-0-563405) or https://chicago.legistar.com/x."
    tokens = [model[i : i + 4] for i in range(0, len(model), 4)]
    text, done = _chat(client, tokens, ctx)
    assert "563405" not in text and "legistar" not in text
    assert "See the code or ." in text  # the words survive, the invented targets don't
    assert text.index("**Sources for the parcel data used**") > text.index("RM-4.5 allows 4 units [1]")
    assert "Municipal Code §17-2-0300" in text and "Zoning district RM-4.5" in text
    assert "citation_warnings" not in done or not done["citation_warnings"]


def test_the_footer_comes_before_a_truncation_notice(client):
    ctx = _ctx()
    ctx.code_chunks = _chunks()
    text, done = _chat(client, ["Part one [1]. Part two cut off"], ctx, stop_reason="max_tokens")
    assert text.index("Sources for the parcel data used") < text.index("cut off before it finished")
    assert done["truncated"] is True


def test_no_footer_for_a_turn_with_no_parcel_and_no_citations(client):
    text, _ = _chat(client, ["The area is quiet."], ContextObject(community_area=24))
    assert text == "The area is quiet." and "Sources" not in text


def test_prompt_rule_37_forbids_writing_urls_or_a_sources_section():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("37. DO NOT WRITE SOURCES OR URLS")
    rule = SYNTHESIZER_SYSTEM[i : i + 1600]
    assert "removed if you do" in rule and "American Legal" in rule and "automatically" in rule
