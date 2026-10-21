"""WS1 M2: what City Council passed since the code text we serve, and how we say so.

Classification is pinned to the recorded Clerk list (fixtures/clerk, 2026-10-21): the
16 Title 17 amendments and none of the other 81. The degradation table (plan §5.6) is
pinned so the product never says "none" without a fresh check.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.chat_sources import allowed_urls, build_sources_footer
from backend.legislation import amendments as am
from backend.legislation import codification_check, currency, currency_check, sync
from backend.models import CodeChunk, ContextObject, OverlayDistrict, PropertySummary, RegulatorySummary, ZoningSummary
from backend.retrieval import clerk

FIXTURE = Path(__file__).parent / "fixtures" / "clerk" / "code_amendments_since_2026-03-18.json"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)

TITLE17 = {
    "O2025-0018447", "O2026-0024064", "SO2025-0017570", "SO2026-0024923", "O2026-0025414", "SO2026-0024930",
    "O2026-0025429", "O2026-0025463", "O2026-0025464", "O2026-0026278", "SO2026-0026276", "O2026-0026042",
    "SO2026-0024882", "SO2026-0027187", "SO2026-0025391", "SO2026-0028463",
}
CITED_OTHER = {"SO2025-0021852", "SO2026-0024086", "O2026-0024022", "O2026-0026243", "SO2025-0017573",
               "SO2026-0027237", "SO2026-0027165"}


def _matters() -> list[clerk.ClerkMatter]:
    return [clerk.ClerkMatter.from_api(r) for r in json.loads(FIXTURE.read_text())["data"]]


def _passed() -> list[clerk.ClerkMatter]:
    return [m for m in _matters() if m.passed and m.passed_on and m.passed_on > date(2026, 3, 18)]


def _write_snapshot(checked_at: datetime | None = NOW - timedelta(hours=2), status: str = "ok", rows=None) -> dict:
    snap = {
        "schema": 1, "vintage": "2026-03-18", "status": status,
        "checked_at": checked_at.strftime("%Y-%m-%dT%H:%M:%SZ") if checked_at else None,
        "code_amendments": rows if rows is not None else [r for r in map(am.live_record, _passed()) if r["relevance"] != "other"],
    }
    currency.snapshot_path().write_text(json.dumps(snap))
    return snap


# --- classification (recorded live list) -------------------------------------------------------

def test_the_classifier_finds_the_16_title17_amendments_and_none_of_the_other_81():
    passed = _passed()
    assert len(passed) == 97
    by_class: dict[str, set[str]] = {}
    for m in passed:
        by_class.setdefault(am.relevance(m.title), set()).add(m.record_number)
    assert by_class["title17"] == TITLE17  # includes the "Titles 2, 14A, ... 17 and 18" omnibus
    assert by_class["cited_other"] == CITED_OTHER
    assert len(by_class["other"]) == 74  # liquor moratoria, meters, procurement ...


def test_sections_come_from_the_title_most_specific_first():
    assert am.sections_in_title("Amendment of Municipal Code Chapter 17-3 by adding Section 17-3-0600 regarding TOD streets") == ["17-3-0600"]
    assert am.sections_in_title("Amendment of Municipal Code Chapter 17-9 regarding waste-related uses") == ["17-9"]
    assert am.sections_in_title("Section 17-9-0109A to require special use approval") == ["17-9-0109-A"]
    assert am.sections_in_title("Sections 14X-8-802.2.2 and 14X-8-802.3.2 to modify dates") == ["14X-8-802.2.2", "14X-8-802.3.2"]


@pytest.mark.parametrize("a,b,expected", [
    ("17-3-0503-D", "17-3-0503-D", True),
    ("17-3-0503", "17-3-0503-D", True),      # section contains its subsection
    ("17-9-0109", "17-9", True),             # chapter
    ("17-3-0500", "17-3-0503-D", True),      # the indexed article
    ("17-3-0503-A", "17-3-0503-D", False),   # siblings
    ("17-9-0129", "17-9-0129.1", False),     # a separate decimal section
    ("17-2-0300", "17-3-0503-D", False),
    ("2-44-170", "2-44", True),
])
def test_section_overlap_rules(a, b, expected):
    assert am.sections_overlap(a, b) is expected and am.sections_overlap(b, a) is expected


def test_the_review_file_matches_the_live_list():
    reviews = currency.load_reviews()
    live = {m.record_number: m for m in _passed()}
    assert set(reviews) == TITLE17 | CITED_OTHER
    for rec, a in reviews.items():
        m = live[rec]
        assert a["passed_on"] == m.passed_on.isoformat() and a["url"] == m.url and a["relevance"] == am.relevance(m.title)
        assert a["codified"] is False and a["product_effect"] in ("applied", "none", "pending")
        # a summary only where someone read the ordinance; never invented from the title
        assert (a["summary"] is None) == (a["summary_basis"] is None)
    assert reviews["SO2026-0025391"]["summary_basis"] == "ordinance"


# --- the amendment list and the degradation table -------------------------------------------------

def test_amendments_touching_prefix_rules():
    _write_snapshot()
    assert {a["record"] for a in currency.amendments_touching("17-3-0503-D")} == {"O2026-0025463", "O2026-0025464", "O2026-0026042"}
    assert {a["record"] for a in currency.amendments_touching("17-3-0500")} == {"O2026-0025463", "O2026-0025464", "O2026-0026042"}
    assert [a["record"] for a in currency.amendments_touching("17-3-0600")] == ["SO2026-0025391"]
    assert currency.amendments_touching("17-2-0304-A") == []


def test_amendments_since_uses_the_date_given():
    _write_snapshot()
    assert {a["record"] for a in currency.amendments_since(date(2026, 9, 23))} == {"SO2026-0025391", "SO2026-0028463"}
    assert len(currency.amendments_since(date(2026, 3, 18), currency.ALL_SCOPES)) == 23


@pytest.mark.parametrize("age,state", [
    (timedelta(hours=2), "fresh"), (timedelta(hours=71), "fresh"),
    (timedelta(days=4), "aging"), (timedelta(days=14), "aging"),
    (timedelta(days=15), "unknown"),
])
def test_check_state_by_age(age, state):
    assert currency.check_state({"status": "ok", "checked_at": (NOW - age).isoformat()}, NOW) == state


def test_never_checked_or_suspect_is_unknown():
    assert currency.check_state(None, NOW) == "unknown"
    assert currency.check_state({"status": "suspect", "checked_at": NOW.isoformat()}, NOW) == "unknown"


def test_fresh_gives_the_count():
    _write_snapshot()
    cc = currency.code_currency(now=NOW)
    assert cc["check_state"] == "fresh" and cc["since"] == {"title17": 16, "cited_other": 7}
    assert len(cc["amendments"]) == 16  # other titles only when they touch something cited
    assert "Since then City Council has passed 16 amendments to the Zoning Ordinance (Title 17)" in currency.currency_sentence(cc)
    assert "(checked Oct 21, 2026)" in currency.currency_sentence(cc)


def test_aging_gives_the_count_as_of_the_check():
    _write_snapshot(NOW - timedelta(days=5))
    s = currency.currency_sentence(currency.code_currency(now=NOW))
    assert s.endswith(" As of Oct 16, 2026, City Council had passed 16 amendments to the Zoning Ordinance (Title 17) since then that are not in this text.")


@pytest.mark.parametrize("setup", ["missing", "stale", "suspect"])
def test_unknown_withholds_the_count_but_keeps_the_committed_list(setup):
    if setup == "stale":
        _write_snapshot(NOW - timedelta(days=30))
    elif setup == "suspect":
        _write_snapshot(status="suspect")
    cc = currency.code_currency(now=NOW)
    assert cc["check_state"] == "unknown" and cc["since"] is None and cc["checked_at"] is None
    s = currency.currency_sentence(cc)
    assert "couldn't check" in s and "none" not in s.lower() and "16" not in s
    # the committed review file (codified: false) still lists them, TOD Streets included
    assert "SO2026-0025391" in {a["record"] for a in cc["amendments"]}


def test_none_is_said_only_after_a_fresh_check_that_found_none():
    _write_snapshot(rows=[])
    with patch.object(currency, "load_reviews", return_value={}):
        assert "has passed no amendments" in currency.currency_sentence(currency.code_currency(now=NOW))
        _write_snapshot(NOW - timedelta(days=30), rows=[])
        assert "no amendments" not in currency.currency_sentence(currency.code_currency(now=NOW))


def test_an_unreviewed_live_amendment_still_shows_with_its_title():
    row = {"record": "O2026-9999999", "url": "https://chicityclerkelms.chicago.gov/Matter/?matterId=X", "title": "Amendment of Section 17-2-0304",
           "passed_on": "2026-10-20", "relevance": "title17", "kind": "text", "sections": ["17-2-0304"]}
    _write_snapshot(rows=[row])
    cc = currency.code_currency(cited_sections=["17-2-0304-A"], now=NOW)
    new = next(a for a in cc["amendments"] if a["record"] == "O2026-9999999")
    assert new["review_status"] == "unreviewed" and new["summary"] is None and new["parcel_relevant"] and new["touches"] == ["17-2-0304-A"]
    assert cc["amendments"][0]["record"] == "O2026-9999999"  # parcel-relevant first


def test_the_snapshot_is_reloaded_when_it_changes():
    _write_snapshot(rows=[])
    assert currency.code_currency(now=NOW)["since"]["title17"] == 16  # from the review file
    _write_snapshot(NOW - timedelta(days=30))
    path = currency.snapshot_path()
    import os
    os.utime(path, ns=(path.stat().st_mtime_ns + 10**9,) * 2)
    assert currency.code_currency(now=NOW)["since"] is None


# --- per parcel ---------------------------------------------------------------------------------

def test_tod_street_map_effect_matches_by_address_range():
    eff = {"kind": "tod_street", "direction": "N", "street": "WESTERN", "from": 3600, "to": 4859}
    assert currency.map_effect_matches(eff, "4000 N Western Ave, Chicago, IL 60618")
    assert not currency.map_effect_matches(eff, "5000 N Western Ave")
    assert not currency.map_effect_matches(eff, "4000 S Western Ave")
    assert not currency.map_effect_matches(eff, None)


def test_a_pedestrian_street_removal_without_a_range_needs_the_overlay():
    eff = {"kind": "pedestrian_street_removed", "direction": "W", "street": "LAWRENCE", "from": None, "to": None}
    assert currency.map_effect_matches(eff, "1100 W Lawrence Ave", ["pedestrian_street"])
    assert not currency.map_effect_matches(eff, "1100 W Lawrence Ave", [])
    added = {**eff, "kind": "pedestrian_street_added"}
    assert not currency.map_effect_matches(added, "1100 W Lawrence Ave", ["pedestrian_street"])  # no guessing a segment


def test_the_parcel_context_lists_all_title17_relevant_first():
    _write_snapshot()
    ctx = ContextObject(
        resolved_address="4000 N Western Ave, Chicago, IL 60618",
        parcel_zoning=ZoningSummary(zone_class="B3-2"),
        regulatory=RegulatorySummary(overlays=[]),
        property=PropertySummary(pin14="13131000010000"),
    )
    cc = ctx.code_currency
    assert len(cc["amendments"]) == 16
    relevant = [a["record"] for a in cc["amendments"] if a["parcel_relevant"]]
    # TOD streets by address; the B3 gas-station ban by the business use table (17-3-0207)
    assert set(relevant) == {"SO2026-0025391", "SO2026-0024923"}
    assert [a["record"] for a in cc["amendments"][:2]] == ["SO2026-0025391", "SO2026-0024923"]
    note = next(n for n in ctx.coverage_notes if n["id"] == "code_amendments_parcel")
    assert note["applies"] == "parcel" and "SO2026-0025391" in note["text"] and "not reflected on this page" in note["text"]
    assert note["link"].startswith("https://chicityclerkelms.chicago.gov/Matter/?matterId=")


def test_a_residential_parcel_off_the_tod_streets_has_no_parcel_note():
    _write_snapshot()
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="RT-4"))
    assert not any(a["parcel_relevant"] for a in ctx.code_currency["amendments"])
    assert "code_amendments_parcel" not in [n["id"] for n in ctx.coverage_notes]


def test_the_milwaukee_overlay_cites_its_article():
    ov = OverlayDistrict(layer_type="special_district", name="Milwaukee Avenue Special Character Overlay District")
    assert "17-7-1500" in currency.parcel_cited_sections("B3-2", [ov])


def test_a_parcel_less_code_question_gets_only_the_touching_amendments():
    _write_snapshot()
    chunk = CodeChunk(text="x", source_document="x", section="17-3-0500", section_title="Pedestrian streets", score=1.0)
    cc = ContextObject(code_chunks=[chunk]).code_currency
    assert {a["record"] for a in cc["amendments"]} == {"O2026-0025463", "O2026-0025464", "O2026-0026042"}
    other = CodeChunk(text="x", source_document="x", section="17-2-0300", section_title="Bulk", score=1.0)
    assert ContextObject(code_chunks=[other]).code_currency is None
    assert ContextObject().code_currency is None


# --- chat ---------------------------------------------------------------------------------------

def _bulk_prov() -> dict:
    return {"zoning.far": {"label": "Floor area ratio for B3-2", "section": "17-3-0403-A", "as_of": "2026-03-18"}}


def test_footer_says_how_current_the_code_is_and_which_amendments_touch_what_was_cited():
    _write_snapshot()
    chunk = CodeChunk(text="x", source_document="x", section="17-3-0500", section_title="Pedestrian streets", score=1.0)
    ctx = ContextObject(code_chunks=[chunk])
    footer = build_sources_footer({}, [(1, chunk)], "2026-03-18", ctx.code_currency)
    line = footer.strip().splitlines()[-1]
    assert line.startswith("- **Code text current through Mar 18, 2026** · 16 later zoning amendments (3 touch sections cited above: ")
    assert "[O2026-0026042](https://chicityclerkelms.chicago.gov/Matter/?matterId=" in line and "(§17-3-0500)" in line


def test_footer_never_counts_without_a_recent_check():
    cc = currency.code_currency(now=NOW)  # no snapshot
    footer = build_sources_footer(_bulk_prov(), [], "2026-03-18", cc)
    assert "we couldn't check recently for later amendments ([City Clerk](https://chicityclerkelms.chicago.gov/))" in footer
    assert "later zoning amendment" not in footer


def test_no_currency_line_when_the_answer_cites_no_code():
    _write_snapshot()
    prov = {"parcel.identity": {"label": "Parcel", "source": "Cook County", "url": None}}
    assert "Code text current" not in build_sources_footer(prov, [], "2026-03-18", currency.code_currency(now=NOW))


def test_the_model_may_link_the_amendments_it_was_given():
    _write_snapshot()
    ctx = ContextObject(resolved_address="4000 N Western Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    urls = allowed_urls(ctx)
    assert currency.load_reviews()["SO2026-0025391"]["url"] in urls


def test_prompt_rule_says_amended_and_never_infers_from_the_title():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("34. HOW CURRENT THE ZONING IS")
    rule = SYNTHESIZER_SYSTEM[i: SYNTHESIZER_SYSTEM.index("35. OVERLAYS")]
    assert "`code_currency`" in rule and "never say there are none" in rule
    assert "amended on `passed_on` by `record`" in rule and "predates the change" in rule
    assert "Describe the change ONLY from `summary`" in rule and "do NOT infer what the change does" in rule
    assert "`codified: false`" in rule


def test_the_context_the_model_sees_carries_code_currency():
    _write_snapshot()
    ctx = ContextObject(resolved_address="4000 N Western Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    payload = json.loads(ctx.model_dump_json(exclude={"analytics"}))
    assert payload["code_currency"]["since"]["title17"] == 16
    assert payload["code_currency"]["amendments"][0]["record"] == "SO2026-0025391"


def test_the_model_gets_full_rows_only_for_what_touches_the_parcel_or_the_code():
    from backend.synthesizer import _build_user_text

    _write_snapshot()
    ctx = ContextObject(resolved_address="4000 N Western Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    text = _build_user_text(ctx, "What can I build here?")
    payload = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    rows = {a["record"]: a for a in payload["code_currency"]["amendments"]}
    assert len(rows) == 16 and payload["code_currency"]["since"]["title17"] == 16
    assert rows["SO2026-0025391"]["summary"].startswith("Adds §17-3-0600") and rows["SO2026-0025391"]["parcel_relevant"]
    assert set(rows["SO2026-0028463"]) == {"record", "passed_on", "title"}  # untouched: compact
    assert "url" not in rows["SO2026-0025391"]  # links come from the Sources footer


# --- the $25 report ----------------------------------------------------------------------------

def _report(language="en"):
    from backend.models import ReportData

    ctx = ContextObject(resolved_address="4000 N Western Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    return ReportData(address="4000 N Western Ave", language=language, context=ctx)


def _html(language="en") -> str:
    from backend.main import render_report_html

    return render_report_html(_report(language), language, report_date="October 21, 2026")


def test_report_block_states_the_vintage_the_count_and_the_parcel_items():
    _write_snapshot(datetime.now(timezone.utc) - timedelta(hours=1))
    html = _html()
    assert "How current the law in this report is" in html
    assert "current through the Council Journal of March 18, 2026" in html
    assert "Since then City Council has passed 16 amendments to the Zoning Ordinance (Title 17)" in html
    assert "These 2 may affect this parcel:" in html
    # the parcel's rows in the zoning section, all 16 under Data Sources
    assert "All 16 amendments passed since are listed under Data Sources &amp; Disclaimers." in html
    assert "Code amendments passed since the Council Journal of March 18, 2026" in html
    assert html.count("May affect this parcel") == 4 and html.count("SO2026-0028463") == 1
    assert "Not yet reviewed" in html and "October 14, 2026" in html


def test_report_block_withholds_the_count_without_a_recent_check():
    html = _html()
    assert "couldn&#39;t check recently" in html
    assert re.search(r'<a href="https://chicityclerkelms\.chicago\.gov/">', html)
    assert "amendments to the Zoning Ordinance (Title 17) that are not in this text" not in html


def test_report_block_renders_in_spanish_with_the_english_text_until_translated():
    _write_snapshot(datetime.now(timezone.utc) - timedelta(hours=1))
    html = _html("es")
    assert "How current the law in this report is" in html and "14 de octubre de 2026" in html


# --- the section endpoints and the admin endpoint ------------------------------------------------

@pytest.fixture
def client():
    from unittest.mock import MagicMock

    from backend import main

    with patch("backend.main.get_settings") as s, patch("backend.main.db") as db:
        s.return_value = MagicMock(anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
                                   router_model="m", synthesizer_model="m", message_limit=10)
        db.init_db = AsyncMock()
        db.close_db = AsyncMock()
        yield TestClient(main.app)


def _ped_chunk() -> CodeChunk:
    text = "17-3-0503-A Purpose. x\n\n17-3-0503-D Designated pedestrian streets. W Belmont Ave ...\n\n17-3-0504 Standards. y"
    return CodeChunk(text=text, source_document="x", section="17-3-0500", section_title="Pedestrian streets", score=1.0)


def test_code_section_endpoint_lists_the_amendments_since(client):
    from backend import main

    _write_snapshot()
    with patch.object(main, "get_full_section", new=AsyncMock(return_value=_ped_chunk())):
        d = client.get("/api/code/section/17-3-0503-D").json()
    assert {a["record"] for a in d["amended_since"]} == {"O2026-0025463", "O2026-0025464", "O2026-0026042"}
    with patch.object(main, "get_full_section", new=AsyncMock(return_value=_ped_chunk())):
        d = client.get("/section/17-3-0500").json()
    assert len(d["amended_since"]) == 3


def test_a_section_added_after_the_text_explains_itself_instead_of_a_bare_404(client):
    from backend import main

    with patch.object(main, "get_full_section", new=AsyncMock(return_value=None)):
        for path in ("/section/17-3-0600", "/api/code/section/17-3-0600"):
            r = client.get(path)
            assert r.status_code == 404
            detail = r.json()["detail"]
            assert detail["not_in_published_code"] and detail["added_by"][0]["record"] == "SO2026-0025391"
            assert "isn't in the published Municipal Code text" in detail["message"]
        assert client.get("/section/17-2-0300").json()["detail"] == "Section 17-2-0300 not found"


def test_admin_code_currency_is_admin_only_and_offline(client):
    from backend import main
    from backend.auth import require_admin

    route = next(r for r in main.app.routes if getattr(r, "path", "") == "/api/admin/code-currency")
    assert require_admin in [d.call for d in route.dependant.dependencies]  # dev mode makes everyone admin
    _write_snapshot(datetime.now(timezone.utc) - timedelta(hours=1))
    main.app.dependency_overrides[require_admin] = lambda: {"id": 1, "tier": "admin"}
    try:
        d = client.get("/api/admin/code-currency").json()
    finally:
        main.app.dependency_overrides.pop(require_admin, None)
    assert d["code"]["source_id"] == "code.municipal_text" and d["code"]["lag"]["title17_passed_since"] == 16
    assert d["clerk"]["source_id"] == "chi.clerk.legislation" and d["clerk"]["snapshot_state"] == "ok"
    assert len(d["amendments"]) == 23 and d["map_lag"] is None


# --- the daily sync -----------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def test_sync_writes_an_ok_snapshot_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=_matters()))
    out = tmp_path / "snap.json"
    code, snap = _run(sync.run(out))
    assert code == 0 and snap["status"] == "ok" and snap["vintage"] == "2026-03-18"
    assert snap["counts"] == {"passed_code_amendments": 97, "title17": 16, "cited_other": 7}
    assert {r["record"] for r in snap["code_amendments"]} == TITLE17 | CITED_OTHER
    assert json.loads(out.read_text()) == snap and not list(tmp_path.glob("*.tmp"))


def test_sync_cutoff_is_the_chicago_date(monkeypatch, tmp_path):
    late = json.loads(FIXTURE.read_text())["data"][0] | {
        "recordNumber": "O2026-0000001", "finalActionDate": "2026-03-19T03:00:00Z",  # 10 pm on Mar 18 in Chicago
        "subStatus": "Passed", "status": "90-Final", "title": "Amendment of Municipal Code Section 17-2-0304",
    }
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=[clerk.ClerkMatter.from_api(late)]))
    _, snap = _run(sync.run(tmp_path / "s.json"))
    assert snap["code_amendments"] == []


def test_sync_flags_contract_drift_as_suspect(monkeypatch, tmp_path):
    odd = _matters()
    odd[0] = odd[0].model_copy(update={"sub_status": "Reconsidered"})
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=odd))
    monkeypatch.setattr(sync, "_report", lambda exc: None)
    code, snap = _run(sync.run(tmp_path / "s.json"))
    assert code == 2 and snap["status"] == "suspect" and "Reconsidered" in snap["contract_problems"][0]


def test_sync_flags_a_vanished_passed_record_as_suspect(monkeypatch, tmp_path):
    out = tmp_path / "s.json"
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=_matters()))
    _run(sync.run(out))
    fewer = [m for m in _matters() if m.record_number != "SO2026-0025391"]
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=fewer))
    _, snap = _run(sync.run(out))
    assert snap["status"] == "suspect" and "SO2026-0025391" in snap["contract_problems"][0]


def test_sync_failure_keeps_the_last_good_rows_and_counts_failures(monkeypatch, tmp_path):
    out = tmp_path / "s.json"
    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=_matters()))
    _, good = _run(sync.run(out))
    reported = []
    monkeypatch.setattr(sync, "_report", reported.append)
    monkeypatch.setattr(clerk, "final_since", AsyncMock(side_effect=clerk.ClerkUnavailable("503 after retries")))
    code, snap = _run(sync.run(out))
    assert code == 1 and snap["status"] == "failed" and snap["consecutive_failures"] == 1
    assert snap["checked_at"] == good["checked_at"] and snap["code_amendments"] == good["code_amendments"]
    assert "503 after retries" in snap["last_error"] and len(reported) == 1
    _, snap = _run(sync.run(out))
    assert snap["consecutive_failures"] == 2


# --- refresh-time and CI checks (offline) ------------------------------------------------------------

def test_codification_check_matches_by_journal_date_and_section(tmp_path):
    amendments = [
        {"record": "A", "passed_on": "2026-05-20", "sections": ["17-3-0207"]},
        {"record": "B", "passed_on": "2026-06-17", "sections": ["17-12-1105-B"]},
        {"record": "OMNI", "passed_on": "2026-06-17", "sections": []},
        {"record": "LATE", "passed_on": "2026-07-15", "sections": ["17-6-0403"]},
    ]
    diff = {
        "old_vintage": "2026-03-18", "new_vintage": "2026-06-17", "added": ["17-7-0510"],
        "modified_detail": [
            {"section": "17-3-0207", "coun_j_dates": ["5-20-26"], "new_coun_j_dates": ["5-20-26"]},
            {"section": "17-14-0100", "coun_j_dates": ["6-17-26"], "new_coun_j_dates": ["6-17-26"]},
            {"section": "17-8-0100", "coun_j_dates": ["4-15-26"], "new_coun_j_dates": ["4-15-26"]},
        ],
    }
    r = codification_check.check(diff, amendments, tmp_path)
    assert [x["record"] for x in r["matched"]] == ["A", "OMNI"]
    assert [x["record"] for x in r["missing"]] == ["B"]  # its section wasn't changed: still uncodified
    assert r["unexplained"] == [{"section": "17-8-0100", "coun_j": "4-15-26"}]


def test_codification_check_writes_codified_flags(tmp_path):
    review = tmp_path / "amendments.json"
    review.write_text(json.dumps({"schema": 1, "amendments": {"A": {"codified": False}, "B": {"codified": False}}}))
    absent = codification_check.write_codified({"matched": [{"record": "A"}], "missing": [{"record": "B"}, {"record": "Z"}]}, review)
    assert absent == ["Z"]
    entries = json.loads(review.read_text())["amendments"]
    assert entries["A"]["codified"] is True and entries["B"]["codified"] is False


def test_currency_check_warns_on_an_old_vintage_and_long_pending_reviews():
    w = currency_check.warnings(date(2026, 10, 21))
    assert w[0] == "Municipal Code text current through 2026-03-18 (217 days, > 90)"
    assert any(x.startswith("SO2026-0024923 (passed 2026-05-20) has been pending review") for x in w)
    assert not any("SO2026-0025391" in x for x in currency_check.warnings(date(2026, 10, 30)))  # 16 days pending
