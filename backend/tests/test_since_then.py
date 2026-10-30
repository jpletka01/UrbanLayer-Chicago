"""WS6 M9: "since then", the comparison of what an answer or report said with today's facts.

No network and no model: today's facts come from fakes for the two lookups the Profile uses, the amendment list
from the legislation snapshot's reader, the refreshes from a patched list.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from backend import db
from backend.data_health import diff
from backend.main import app, require_auth
from backend.models import ContextObject, OverlayDistrict, RegulatorySummary, ZoningSummary

PIN = "14313320180000"
LAT, LON = 41.91, -87.68
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def old_snap(**kw) -> dict:
    base = {
        "v": 1, "answered_at": "2026-10-01T10:00:00Z", "pin": PIN, "lat": LAT, "lon": LON, "address": "1601 N Milwaukee Ave",
        "zoning": {"zone_class": "B3-2", "ordinance_num": "O2021-1", "ordinance_date": "2021-12-15", "map_updated": "2021-12-15"},
        "overlays": [["adu_area", "adu area"], ["historic_district", "wicker park historic district"]],
        "flags": {"is_landmark_building": False}, "unchecked_overlays": [],
        "standards": {"far": 2.2, "max_height": "50", "min_lot_area_per_unit": None, "unit_yield": 9},
        "code": {"current_through": "2026-03-18", "cited_sections": ["17-3-0207"], "bulk_sections": ["17-3-0400"]},
        "passed": {"rezonings": [], "landmark_designations": []}, "unchecked": [],
    }
    base.update(kw)
    return base


def cur_snap(**kw) -> dict:
    base = {
        "zoning": {"zone_class": "B3-2", "ordinance_num": "O2021-1", "ordinance_date": "2021-12-15", "map_updated": "2021-12-15", "clerk_url": None},
        "overlays": [["adu_area", "adu area"], ["historic_district", "wicker park historic district"]],
        "standards": {"far": 2.2, "max_height": "50", "min_lot_area_per_unit": None},
        "checked": {"zoning": True, "unchecked_overlays": []}, "passed_detail": {"rezonings": [], "landmark_designations": []},
    }
    base.update(kw)
    return base


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No amendments and no text refreshes unless a test adds them."""
    monkeypatch.setattr(diff, "load_refreshes", lambda: [])
    monkeypatch.setattr("backend.legislation.currency.amendments_since", lambda day, scope=(): [])


def kinds(result) -> list[str]:
    return [c["kind"] for c in result["changes"]]


# --- the comparison --------------------------------------------------------------------------------------------

def test_nothing_changed_reads_as_none():
    r = diff.compare(old_snap(), cur_snap())
    assert r == {"status": "none", "changes": [], "unchecked": []}


def test_a_district_change_carries_its_ordinance_and_link():
    z = {"zone_class": "B2-3", "ordinance_num": "O2026-7", "ordinance_date": "2026-09-23", "map_updated": "2026-10-05", "clerk_url": "https://clerk/x"}
    r = diff.compare(old_snap(), cur_snap(zoning=z))
    assert r["status"] == "changes"
    assert r["changes"][0] == {"kind": "district", "old": "B3-2", "new": "B2-3", "record": "O2026-7", "passed_on": "2026-09-23", "url": "https://clerk/x"}


def test_a_district_written_differently_is_not_a_change():
    z = {**cur_snap()["zoning"], "zone_class": " b3-2 "}
    assert diff.compare(old_snap(), cur_snap(zoning=z))["status"] == "none"


def test_an_overlay_added_or_removed_is_a_change_but_a_renamed_spacing_is_not():
    spaced = [["adu_area", "adu area"], ["historic_district", "wicker park historic district"]]
    assert diff.compare(old_snap(), cur_snap(overlays=spaced))["status"] == "none"
    r = diff.compare(old_snap(), cur_snap(overlays=[["adu_area", "adu area"], ["planned_development", "pd 1234"]]))
    got = {(c["change"], c["layer"]) for c in r["changes"] if c["kind"] == "overlay"}
    assert got == {("added", "planned_development"), ("removed", "historic_district")}
    # an added overlay carries the City's own wording of its name when today's lookup has it; a removed one has none
    labelled = diff.compare(old_snap(), cur_snap(overlays=[["adu_area", "adu area"], ["planned_development", "pd 1234"]],
                                                 overlay_labels={"planned_development|pd 1234": "PD 1,234"}))
    names = {c["change"]: c["name"] for c in labelled["changes"] if c["kind"] == "overlay"}
    assert names == {"added": "PD 1,234", "removed": None}


def test_an_overlay_the_map_could_not_answer_makes_no_claim_either_way():
    cur = cur_snap(overlays=[["adu_area", "adu area"]], checked={"zoning": True, "unchecked_overlays": ["historic_district"]})
    r = diff.compare(old_snap(), cur)
    assert r["changes"] == [] and r["status"] == "partial" and r["unchecked"] == ["overlay:historic_district"]


def test_a_layer_the_old_answer_could_not_check_is_not_reported_as_added():
    old = old_snap(overlays=[["adu_area", "adu area"]], unchecked_overlays=["historic_district"])
    assert diff.compare(old, cur_snap())["status"] == "none"


def test_an_overlay_that_carries_no_rule_is_never_flagged():
    assert diff.compare(old_snap(), cur_snap(overlays=[*cur_snap()["overlays"], ["ssa", "ssa 12"]]))["status"] == "none"


def test_a_failed_lookup_is_never_no_change():
    r = diff.compare(old_snap(), None)
    assert r["status"] == "unavailable" and r["unchecked"] == ["everything"]
    r = diff.compare(old_snap(), cur_snap(zoning=None, checked={"zoning": False, "unchecked_overlays": []}))
    assert r["status"] == "partial" and "district" in r["unchecked"]


def test_standards_are_compared_for_the_same_district_only():
    r = diff.compare(old_snap(), cur_snap(standards={"far": 3.0, "max_height": "50", "min_lot_area_per_unit": None}))
    assert r["changes"] == [{"kind": "standards", "field": "far", "old": 2.2, "new": 3.0, "zone_class": "B3-2"}]
    z = {**cur_snap()["zoning"], "zone_class": "B2-3"}
    r = diff.compare(old_snap(), cur_snap(zoning=z, standards={"far": 9.0, "max_height": "1", "min_lot_area_per_unit": 5}))
    assert kinds(r) == ["district"]


def test_a_passed_rezoning_and_designation_listing_the_parcel_are_flagged_once():
    detail = {"rezonings": [{"record": "O2026-9", "passed_on": "2026-10-14", "url": "https://clerk/9"}],
              "landmark_designations": [{"record": "O2026-3", "passed_on": "2026-09-01", "url": None, "name": "Some Landmark"}]}
    r = diff.compare(old_snap(), cur_snap(passed_detail=detail))
    assert kinds(r) == ["map_amendment", "designation"]
    already = old_snap(passed={"rezonings": ["O2026-9"], "landmark_designations": ["O2026-3"]})
    assert diff.compare(already, cur_snap(passed_detail=detail))["status"] == "none"


def amendment(record, passed_on, sections):
    return {"record": record, "passed_on": passed_on, "title": f"title {record}", "url": f"https://clerk/{record}", "sections": sections}


def test_an_amendment_touching_a_cited_section_is_split_before_and_after_the_answer(monkeypatch):
    rows = [amendment("A", "2026-09-23", ["17-3-0403"]), amendment("B", "2026-03-25", ["17-3-0207"]),
            amendment("C", "2026-09-30", ["17-9-0129"])]
    monkeypatch.setattr("backend.legislation.currency.amendments_since", lambda day, scope=(): rows)
    r = diff.compare(old_snap(answered_at="2026-09-27T10:00:00Z"), cur_snap())
    got = {c["record"]: c["phase"] for c in r["changes"] if c["kind"] == "amendment"}
    # 17-3-0403 is inside the cited bulk article 17-3-0400; 17-9-0129 touches nothing the answer cited.
    assert got == {"A": "before_answer", "B": "before_answer"}
    r = diff.compare(old_snap(answered_at="2026-09-01T10:00:00Z"), cur_snap())
    assert {c["record"]: c["phase"] for c in r["changes"]} == {"A": "after_answer", "B": "before_answer"}


def test_no_amendment_claim_without_a_vintage_to_measure_from(monkeypatch):
    monkeypatch.setattr("backend.legislation.currency.amendments_since", lambda day, scope=(): [amendment("A", "2026-09-23", ["17-3-0403"])])
    old = old_snap(code={"current_through": None, "cited_sections": ["17-3-0207"], "bulk_sections": []})
    assert diff.compare(old, cur_snap())["status"] == "none"


def test_a_refreshed_section_that_the_answer_cited_is_reported(monkeypatch):
    monkeypatch.setattr(diff, "load_refreshes", lambda: [
        {"from": "2026-03-18", "to": "2026-06-17", "modified": ["17-3-0404", "9-1-1"], "removed": [], "added": []},
        {"from": "2025-01-01", "to": "2026-03-18", "modified": ["17-3-0207"], "removed": [], "added": []},  # not newer than the answer's text
    ])
    r = diff.compare(old_snap(), cur_snap())
    assert r["changes"] == [{"kind": "text_refresh", "current_through": "2026-06-17", "sections": ["17-3-0400"]}]


def test_a_correction_applies_to_a_matching_snapshot_made_before_its_date():
    landmark = old_snap(answered_at="2026-09-20T10:00:00Z", flags={"is_landmark_building": True})
    r = diff.compare(landmark, cur_snap())
    assert [c["id"] for c in r["changes"]] == ["landmark-survey-layer"]
    assert diff.compare(old_snap(answered_at="2026-10-03T10:00:00Z", flags={"is_landmark_building": True}), cur_snap())["status"] == "none"
    assert diff.compare(old_snap(answered_at="2026-09-20T10:00:00Z"), cur_snap())["status"] == "none"
    rm = old_snap(answered_at="2026-06-01T10:00:00Z", zoning={"zone_class": "RM-6.5"})
    assert [c["id"] for c in diff.compare(rm, cur_snap(zoning={"zone_class": "RM-6.5"}))["changes"]] == ["zoning-table-heights-2026-07"]
    mfg = old_snap(answered_at="2026-06-01T10:00:00Z", zoning={"zone_class": "M1-2"})
    assert [c["id"] for c in diff.compare(mfg, cur_snap(zoning={"zone_class": "M1-2"}))["changes"]] == ["zoning-table-heights-2026-07-manufacturing"]


def test_corrections_file_is_well_formed():
    entries = diff.load_corrections()
    assert entries and len({e["id"] for e in entries}) == len(entries)
    for e in entries:
        assert {"id", "date", "source_id", "fact_keys", "summary", "applies_if", "commit"} <= set(e)
        datetime.strptime(e["date"], "%Y-%m-%d")
        assert e["applies_if"] and all(isinstance(k, str) for k in e["applies_if"])
    from backend.data_health.registry import SOURCES

    ids = {s.id for s in SOURCES}
    assert {e["source_id"] for e in entries} <= ids


# --- reconstructing an old snapshot ----------------------------------------------------------------------------

def parcel_context() -> dict:
    ctx = ContextObject(
        resolved_address="1601 N Milwaukee Ave", parcel_pin=PIN,
        parcel_zoning=ZoningSummary(zone_class="B3-2", ordinance_num="O2021-1"),
        regulatory=RegulatorySummary(overlays=[OverlayDistrict(layer_type="adu_area", name="ADU Area")]),
    )
    return json.loads(ctx.model_dump_json(exclude_none=True))


def test_an_old_answer_is_rebuilt_from_its_context_and_plan_and_says_so():
    created = int(datetime(2026, 4, 2, tzinfo=timezone.utc).timestamp() * 1000)
    snap = diff.reconstruct(parcel_context(), {"location": {"resolved_lat": LAT, "resolved_lon": LON}}, created)
    assert snap["reconstructed"] is True and snap["answered_at"] == "2026-04-02T00:00:00Z"
    assert (snap["lat"], snap["lon"]) == (LAT, LON) and snap["overlays"] == [["adu_area", "adu area"]]


def test_the_code_text_an_old_answer_used_is_the_one_before_the_first_refresh(monkeypatch):
    monkeypatch.setattr(diff, "load_refreshes", lambda: [{"from": "2026-03-18", "to": "2026-06-17", "applied_at": "2026-10-21T05:00:00+00:00"}])
    created = int(datetime(2026, 4, 2, tzinfo=timezone.utc).timestamp() * 1000)
    assert diff.reconstruct(parcel_context(), None, created)["code"]["current_through"] == "2026-03-18"
    later = int(datetime(2026, 10, 22, tzinfo=timezone.utc).timestamp() * 1000)
    assert diff.reconstruct(parcel_context(), None, later)["code"]["current_through"] == "2026-06-17"  # after the refresh: today's text
    assert diff.reconstruct(parcel_context(), None, None) is None  # no date to place it by: never guess


def test_a_context_that_is_not_of_a_parcel_gives_nothing():
    assert diff.reconstruct({"community_area": 24}, None, 1) is None and diff.reconstruct(None, None, 1) is None


def test_a_stored_snapshot_without_a_point_takes_the_plans_point():
    s = diff.with_point(old_snap(lat=None, lon=None), {"location": {"resolved_lat": 1.5, "resolved_lon": 2.5}})
    assert (s["lat"], s["lon"]) == (1.5, 2.5)
    assert diff.with_point(old_snap(lat=None, lon=None), None, fallback=(3.0, 4.0))["lat"] == 3.0


# --- today's facts ---------------------------------------------------------------------------------------------

ZONING = {"zone_class": "B2-3", "zone_type": 1, "ordinance_num": "O2026-7", "application_num": None,
          "ordinance_date": "2026-09-23", "map_updated": "2026-10-05", "clerk_url": "https://clerk/x"}


@pytest.mark.asyncio
async def test_todays_facts_are_built_from_the_profiles_own_lookups():
    reg = RegulatorySummary(overlays=[OverlayDistrict(layer_type="adu_area", name="ADU  Area")], unchecked_overlays=["aro_zone"])
    with patch("backend.retrieval.zoning.lookup_zoning", new=AsyncMock(return_value=ZONING)), \
         patch("backend.retrieval.regulatory.regulatory_domain", new=AsyncMock(return_value=reg)):
        cur = await diff.current_facts(old_snap())
    assert cur["zoning"]["zone_class"] == "B2-3" and cur["zoning"]["clerk_url"] == "https://clerk/x"
    assert cur["overlays"] == [["adu_area", "adu area"]] and cur["standards"]["far"] is not None
    assert cur["overlay_labels"] == {"adu_area|adu area": "ADU  Area"}
    assert cur["checked"] == {"zoning": True, "unchecked_overlays": ["aro_zone"]}


@pytest.mark.asyncio
async def test_a_failed_lookup_is_reported_as_unchecked_not_empty():
    with patch("backend.retrieval.zoning.lookup_zoning", new=AsyncMock(side_effect=RuntimeError("down"))), \
         patch("backend.retrieval.regulatory.regulatory_domain", new=AsyncMock(side_effect=RuntimeError("down"))):
        cur = await diff.current_facts(old_snap())
    assert cur["checked"]["zoning"] is False and "historic_district" in cur["checked"]["unchecked_overlays"]
    assert diff.compare(old_snap(), cur)["status"] == "partial"


@pytest.mark.asyncio
async def test_no_point_means_nothing_to_look_up():
    assert await diff.current_facts(old_snap(lat=None, lon=None)) is None


# --- the cached check ------------------------------------------------------------------------------------------

@pytest_asyncio.fixture
async def world(tmp_path):
    settings = MagicMock()
    settings.db_path = tmp_path / "t.db"
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        await db.upsert_user("owner", "o@x.com", "Owner", None, "g1")
        await db.upsert_user("other", "x@x.com", "Other", None, "g2")
        yield
        await db.close_db()


@pytest.mark.asyncio
async def test_an_answer_under_a_day_old_is_skipped_without_a_lookup(world):
    fake = AsyncMock(return_value=cur_snap())
    with patch.object(diff, "current_facts", new=fake):
        r = await diff.changes_for(old_snap(answered_at="2026-10-25T03:00:00Z"), now=NOW)
    assert r["status"] == "too_soon" and r["answered_on"] == "2026-10-25"
    fake.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_complete_check_is_kept_for_the_day_and_a_partial_one_is_not(world):
    fake = AsyncMock(return_value=cur_snap())
    with patch.object(diff, "current_facts", new=fake):
        await diff.changes_for(old_snap(), now=NOW)
        await diff.changes_for(old_snap(), now=NOW)
        assert fake.await_count == 1
        await diff.changes_for(old_snap(), now=datetime(2026, 10, 26, 12, tzinfo=timezone.utc))
        assert fake.await_count == 2  # a new day looks again
    partial = AsyncMock(return_value=cur_snap(checked={"zoning": True, "unchecked_overlays": ["aro_zone"]}))
    other = old_snap(pin="99999999999999", lat=41.0)
    with patch.object(diff, "current_facts", new=partial):
        await diff.changes_for(other, now=NOW)
        await diff.changes_for(other, now=NOW)
    assert partial.await_count == 2


@pytest.mark.asyncio
async def test_a_lookup_that_raises_reads_as_unavailable(world):
    with patch.object(diff, "current_facts", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await diff.changes_for(old_snap(), now=NOW)
    assert r["status"] == "unavailable"


@pytest.mark.asyncio
async def test_no_snapshot_means_no_parcel(world):
    assert (await diff.changes_for(None))["status"] == "no_parcel"


# --- conversations ---------------------------------------------------------------------------------------------

def stored(pin: str, lat: float, answered="2026-10-01T10:00:00Z") -> dict:
    return old_snap(pin=pin, lat=lat, answered_at=answered)


async def add_message(conv_id, role, snap=None, created_at=None):
    conn = db._get_db()
    cur = await conn.execute("SELECT COALESCE(MAX(position), -1) FROM messages WHERE conversation_id = ?", (conv_id,))
    pos = (await cur.fetchone())[0] + 1
    await conn.execute(
        "INSERT INTO messages (conversation_id, role, content, position, created_at, facts_json) VALUES (?, ?, 'x', ?, ?, ?)",
        (conv_id, role, pos, created_at or 1, json.dumps(snap) if snap else None),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_a_conversation_gets_a_note_per_parcel_answer_and_none_for_the_rest(world):
    await db.create_conversation("c1", "t", user_id="owner")
    await add_message("c1", "user")
    await add_message("c1", "assistant", stored(PIN, LAT))
    await add_message("c1", "assistant")  # an answer about the area: no snapshot, no context
    z = {**cur_snap()["zoning"], "zone_class": "B2-3"}
    with patch.object(diff, "current_facts", new=AsyncMock(return_value=cur_snap(zoning=z))):
        out = await diff.conversation_changes("c1", now=NOW)
    assert list(out["notes"]) == ["1"] and out["notes"]["1"]["status"] == "changes"


@pytest.mark.asyncio
async def test_only_three_distinct_parcels_are_rechecked_newest_first(world):
    await db.create_conversation("c2", "t", user_id="owner")
    for i in range(5):
        await add_message("c2", "assistant", stored(f"1431332018000{i}", 41.0 + i))
    fake = AsyncMock(return_value=cur_snap())
    with patch.object(diff, "current_facts", new=fake):
        out = await diff.conversation_changes("c2", now=NOW)
    assert fake.await_count == 3
    assert [out["notes"][str(i)]["status"] for i in range(5)] == ["skipped", "skipped", "none", "none", "none"]


@pytest.mark.asyncio
async def test_an_old_message_is_rebuilt_when_it_has_no_stored_snapshot(world):
    await db.create_conversation("c3", "t", user_id="owner")
    conn = db._get_db()
    created = int(datetime(2026, 4, 2, tzinfo=timezone.utc).timestamp() * 1000)
    await conn.execute(
        "INSERT INTO messages (conversation_id, role, content, context_json, plan_json, position, created_at) VALUES ('c3', 'assistant', 'x', ?, ?, 0, ?)",
        (json.dumps(parcel_context()), json.dumps({"location": {"resolved_lat": LAT, "resolved_lon": LON}}), created),
    )
    await conn.commit()
    with patch.object(diff, "current_facts", new=AsyncMock(return_value=cur_snap())):
        out = await diff.conversation_changes("c3", now=NOW)
    assert out["notes"]["0"]["reconstructed"] is True and out["notes"]["0"]["answered_on"] == "2026-04-02"


@pytest.mark.asyncio
async def test_a_message_remembers_the_point_it_was_made_at(world):
    await db.create_conversation("c4", "t", user_id="owner")
    await db.save_messages("c4", [{"role": "assistant", "content": "x", "context": parcel_context(),
                                   "plan": {"location": {"resolved_lat": LAT, "resolved_lon": LON}}}])
    (m,) = await db.get_message_facts("c4")
    assert (m["facts"]["lat"], m["facts"]["lon"]) == (LAT, LON)
    got = await db.get_conversation("c4", "owner")
    assert got["messages"][0]["created_at"] > 0


# --- endpoints -------------------------------------------------------------------------------------------------

async def api(user, method, url):
    app.dependency_overrides[require_auth] = lambda: user
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
            return await getattr(ac, method)(url)
    finally:
        app.dependency_overrides.pop(require_auth, None)


OWNER = {"id": "owner", "tier": "free", "email": "o@x.com"}
OTHER = {"id": "other", "tier": "free", "email": "x@x.com"}


@pytest.mark.asyncio
async def test_the_owner_endpoint_is_owner_only(world):
    await db.create_conversation("c5", "t", user_id="owner")
    await add_message("c5", "assistant", stored(PIN, LAT))
    with patch.object(diff, "current_facts", new=AsyncMock(return_value=cur_snap())):
        assert (await api(OWNER, "get", "/api/conversations/c5/changes")).status_code == 200
        assert (await api(OTHER, "get", "/api/conversations/c5/changes")).status_code == 404


@pytest.mark.asyncio
async def test_a_shared_link_gets_the_same_notes_without_signing_in_and_is_cached_and_limited(world):
    from backend import main as main_mod
    from backend.rate_limit import clear_rate_limits

    clear_rate_limits()
    main_mod._share_changes_cache._store.clear()
    await db.create_conversation("c6", "t", user_id="owner")
    await add_message("c6", "assistant", stored(PIN, LAT))
    token = (await db.create_share_token("c6", "owner"))["token"]
    fake = AsyncMock(return_value=cur_snap())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
        with patch.object(diff, "conversation_changes", new=AsyncMock(wraps=diff.conversation_changes)) as spy, \
             patch.object(diff, "current_facts", new=fake):
            first = await ac.get(f"/api/share/{token}/changes")
            second = await ac.get(f"/api/share/{token}/changes")
            assert first.status_code == 200 and first.json() == second.json() and first.json()["notes"]["0"]["status"] == "none"
            assert spy.await_count == 1  # the second hit came from the cache
        assert (await ac.get("/api/share/nope/changes")).status_code == 404
        codes = [(await ac.get(f"/api/share/{token}/changes")).status_code for _ in range(25)]
    assert 429 in codes
    clear_rate_limits()


@pytest.mark.asyncio
async def test_a_revoked_share_stops_answering(world):
    from backend.rate_limit import clear_rate_limits

    clear_rate_limits()
    await db.create_conversation("c7", "t", user_id="owner")
    token = (await db.create_share_token("c7", "owner"))["token"]
    await db.revoke_share("c7", "owner")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
        assert (await ac.get(f"/api/share/{token}/changes")).status_code == 404


@pytest.mark.asyncio
async def test_a_purchase_is_flagged_from_its_originals_snapshot(world):
    await db.save_report_purchase("owner", "cs_1", "1601 N Milwaukee Ave", LAT, LON, pin=PIN)
    await db.complete_report_purchase("cs_1", "pi_1")
    await db.save_report_purchase("owner", "cs_2", "2 Other St", 41.5, -87.5, pin="22222222222222")
    await db.complete_report_purchase("cs_2", "pi_2")
    pid = (await db.get_user_report_purchases("owner"))[-1]["id"]
    await db.record_render(user_id="owner", purchase_id=pid, pin=PIN, lat=LAT, lon=LON, kind="original",
                           facts=old_snap(lat=None, lon=None), vintages=[], language="en", pdf=b"%PDF")
    z = {**cur_snap()["zoning"], "zone_class": "B2-3"}
    with patch.object(diff, "current_facts", new=AsyncMock(return_value=cur_snap(zoning=z))):
        body = (await api(OWNER, "get", "/api/me/purchases")).json()["purchases"]
    by_id = {p["id"]: p for p in body}
    assert by_id[pid]["changes"]["status"] == "changes" and by_id[pid]["changes"]["changes"][0]["kind"] == "district"
    assert [p["changes"] for p in body if p["id"] != pid] == [None]  # no original, nothing to compare


@pytest.mark.asyncio
async def test_a_failing_check_never_costs_the_purchase_list(world):
    await db.save_report_purchase("owner", "cs_1", "1601 N Milwaukee Ave", LAT, LON, pin=PIN)
    await db.complete_report_purchase("cs_1", "pi_1")
    with patch.object(diff, "purchase_changes", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = await api(OWNER, "get", "/api/me/purchases")
    assert r.status_code == 200 and r.json()["purchases"][0]["changes"] is None
