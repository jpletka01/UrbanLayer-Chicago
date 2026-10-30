"""WS6 M8: the fact snapshot an answer or a report keeps, and the schema v15 that holds it.

The snapshot is built on the server from a validated ContextObject; a ``facts`` field in a client's payload is
never read. Only what a *material* change is measured against goes in (district, overlays, flags, standards,
code vintage and cited sections, headline records, each source's date, what could not be checked).
"""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from backend import db
from backend.data_health import facts
from backend.models import (
    AssessmentRecord, ContextObject, CrimeSummary, OverlayDistrict, PropertySummary, RegulatorySummary,
    StoredMessage, ZoningSummary,
)


def parcel_ctx(**kw) -> ContextObject:
    base = dict(
        resolved_address="1601 N Milwaukee Ave", parcel_pin="14313320180000",
        parcel_zoning=ZoningSummary(zone_class="B3-2", ordinance_num="O2021-1", ordinance_date="2021-12-15", map_updated="2021-12-15"),
        regulatory=RegulatorySummary(
            overlays=[OverlayDistrict(layer_type="historic_district", name="Wicker  Park Historic District"),
                      OverlayDistrict(layer_type="adu_area", name="ADU Area")],
            in_historic_district=True, unchecked_overlays=["national_register"],
        ),
        property=PropertySummary(pin14="14313320180000", land_sqft=11951, bldg_sqft=15647, total_assessed_value=398120.0, tax_year=2024,
                                 estimated_annual_tax=82586.0,
                                 assessment_history=[AssessmentRecord(year=2024, total=1), AssessmentRecord(year=2026, total=2)]),
        partial_failures=["comparable sales", "property tax estimate", "something nobody named"],
    )
    base.update(kw)
    return ContextObject(**base)


PROV = {
    "zoning.far": {"section": "17-3-0400", "source_id": "code.municipal_text", "as_of": "2026-06-17"},
    "zoning.max_height": {"section": "17-3-0400", "source_id": "code.municipal_text", "as_of": "2026-06-17"},
    "property.assessed_value": {"source_id": "cook.assessor.values", "period": "2026"},
    "area.crime": {"source_id": "chi.crime", "as_of": "2026-10-14"},
    "property.tax_estimate": {"source_id": "cook.ptaxsim"},  # no date: nothing to record
}


def snap(ctx=None, **kw) -> dict:
    return facts.snapshot(ctx or parcel_ctx(), provenance=PROV, zone_definition={"far": 2.2, "max_height": "50", "min_lot_area_per_unit": None},
                          answered_at="2026-10-22T10:00:00Z", **kw)


# --- the snapshot -----------------------------------------------------------------------------------------

def test_the_snapshot_holds_what_a_material_change_is_measured_against():
    s = snap()
    assert s["v"] == facts.SNAPSHOT_VERSION == 1 and s["answered_at"] == "2026-10-22T10:00:00Z"
    assert s["pin"] == "14313320180000" and s["address"] == "1601 N Milwaukee Ave"
    assert s["zoning"] == {"zone_class": "B3-2", "ordinance_num": "O2021-1", "ordinance_date": "2021-12-15", "map_updated": "2021-12-15"}
    assert s["standards"]["far"] == 2.2 and s["standards"]["max_height"] == "50"
    assert s["code"]["bulk_sections"] == ["17-3-0400"] and s["code"]["cited_sections"]
    assert s["property"] == {"land_sqft": 11951, "bldg_sqft": 15647, "assessment_year": 2026, "assessed_total": 398120.0,
                             "tax_year": 2024, "est_tax": 82586.0}


def test_overlays_are_sorted_and_names_are_normalized_so_spacing_is_never_a_change():
    s = snap()
    assert s["overlays"] == [["adu_area", "adu area"], ["historic_district", "wicker park historic district"]]
    other = snap(parcel_ctx(regulatory=RegulatorySummary(overlays=[OverlayDistrict(layer_type="adu_area", name="ADU  AREA"),
                                                                   OverlayDistrict(layer_type="historic_district", name="Wicker Park, Historic District")],
                                                         in_historic_district=True, unchecked_overlays=["national_register"])))
    assert other["overlays"] == s["overlays"] and other["flags"] == s["flags"]
    assert facts.normalize_name("  A  B.C ") == "a bc"


def test_flags_and_unchecked_are_recorded_and_failures_are_keys_not_prose():
    s = snap()
    assert s["flags"]["in_historic_district"] is True and s["flags"]["in_planned_development"] is False
    assert s["unchecked_overlays"] == ["national_register"]
    assert s["unchecked"] == ["comparables", "property"]  # labels become keys; a label nobody named is dropped


def test_sources_are_one_entry_per_source_with_only_the_dates_it_has():
    s = snap()["sources"]
    assert s["code.municipal_text"] == {"as_of": "2026-06-17"} and s["cook.assessor.values"] == {"period": "2026"}
    assert s["chi.crime"] == {"as_of": "2026-10-14"} and s["cook.ptaxsim"] == {}


def test_a_parcel_snapshot_is_small():
    assert len(json.dumps(snap(), separators=(",", ":"))) < 4000


def test_an_answer_about_the_area_has_nothing_to_compare():
    area = ContextObject(community_area=24, community_area_name="West Town", crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}))
    assert facts.resolved_parcel(facts.snapshot(area, answered_at="2026-10-22T10:00:00Z")) is False
    assert facts.resolved_parcel(snap()) is True
    assert facts.resolved_parcel(None) is False


def test_recorded_passed_ordinances_ride_along_for_the_later_diff(monkeypatch):
    from backend.legislation import currency

    hit = {"record": "SO2026-1", "passed_on": "2026-10-14", "url": "u", "segment": "x", "maps": None, "matched_by": "pin"}
    monkeypatch.setattr(currency, "load_snapshot", lambda: None)
    ctx = parcel_ctx()
    monkeypatch.setattr(type(ctx), "passed_not_on_map", property(lambda self: [hit]))
    assert snap(ctx)["passed"] == {"rezonings": ["SO2026-1"], "landmark_designations": []}


# --- saved messages: built on the server --------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    settings = MagicMock()
    settings.db_path = tmp_path / "test.db"
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        yield tmp_path
        await db.close_db()


def stored(role="assistant", ctx=None, **extra) -> dict:
    payload = {"role": role, "content": "answer", **({"context": json.loads(ctx.model_dump_json(exclude_none=True))} if ctx else {}), **extra}
    return StoredMessage.model_validate(payload).model_dump(exclude_none=True)


async def facts_of(conv_id: str) -> list[str | None]:
    cur = await db._get_db().execute("SELECT facts_json FROM messages WHERE conversation_id = ? ORDER BY position", (conv_id,))
    return [r["facts_json"] for r in await cur.fetchall()]


@pytest.mark.asyncio
async def test_an_assistant_answer_about_a_parcel_gets_its_snapshot_when_it_is_stored(test_db):
    await db.create_conversation("c1", "t", None)
    await db.save_messages("c1", [stored("user"), stored(ctx=parcel_ctx())])
    user_facts, answer_facts = await facts_of("c1")
    assert user_facts is None
    snapshot = json.loads(answer_facts)
    assert snapshot["zoning"]["zone_class"] == "B3-2" and snapshot["pin"] == "14313320180000" and snapshot["v"] == 1
    assert snapshot["answered_at"].endswith("Z")


@pytest.mark.asyncio
async def test_an_area_answer_and_an_answer_without_a_context_get_none(test_db):
    await db.create_conversation("c2", "t", None)
    area = ContextObject(community_area=24, crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}))
    await db.save_messages("c2", [stored(ctx=area), stored()])
    assert await facts_of("c2") == [None, None]


@pytest.mark.asyncio
async def test_a_snapshot_the_client_sends_is_ignored_the_server_builds_its_own(test_db):
    """The payload's own ``facts_json`` / ``facts`` never reach the table: StoredMessage drops unknown fields,
    and the column is written from the validated context."""
    forged = {"v": 1, "zoning": {"zone_class": "R1"}, "pin": "00000000000000"}
    msg = StoredMessage.model_validate({"role": "assistant", "content": "a", "facts_json": json.dumps(forged), "facts": forged,
                                        "context": json.loads(parcel_ctx().model_dump_json(exclude_none=True))}).model_dump(exclude_none=True)
    assert "facts_json" not in msg and "facts" not in msg
    await db.create_conversation("c3", "t", None)
    await db.save_messages("c3", [msg])
    (got,) = await facts_of("c3")
    assert json.loads(got)["zoning"]["zone_class"] == "B3-2" and json.loads(got)["pin"] == "14313320180000"


@pytest.mark.asyncio
async def test_a_context_the_server_cannot_read_never_fails_the_save(test_db):
    await db.create_conversation("c4", "t", None)
    await db.save_messages("c4", [{"role": "assistant", "content": "a", "context": {"parcel_zoning": {"zone_class": ["not", "a", "string"]}}}])
    assert await facts_of("c4") == [None]
    got = (await db.get_conversation("c4"))["messages"]
    assert got[0]["content"] == "a"


# --- schema v15 ---------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_v14_database_migrates_in_place_and_keeps_its_messages(tmp_path):
    path = tmp_path / "old.db"
    settings = MagicMock()
    settings.db_path = path
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        await db.create_conversation("c1", "t", None)
        await db.save_messages("c1", [stored(ctx=parcel_ctx())])
        await db.close_db()
    # roll the file back to what v14 looked like: no facts column, no render table, stamped 14
    con = sqlite3.connect(path)
    con.execute("DROP TABLE report_renders")
    con.execute("DROP TABLE fact_checks")
    con.execute("ALTER TABLE messages DROP COLUMN facts_json")
    con.execute("UPDATE schema_version SET version = 14")
    con.commit()
    con.close()
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        try:
            cur = await db._get_db().execute("SELECT version FROM schema_version")
            assert (await cur.fetchone())[0] == db._SCHEMA_VERSION == 16
            cur = await db._get_db().execute("PRAGMA table_info(messages)")
            assert "facts_json" in {r[1] for r in await cur.fetchall()}
            cur = await db._get_db().execute("SELECT name FROM sqlite_master WHERE name IN ('report_renders', 'idx_rr_one_original')")
            assert {r[0] for r in await cur.fetchall()} == {"report_renders", "idx_rr_one_original"}
            assert (await db.get_conversation("c1"))["messages"][0]["content"] == "answer"
            cur = await db._get_db().execute("SELECT name FROM sqlite_master WHERE name = 'fact_checks'")
            assert await cur.fetchone() is not None
        finally:
            await db.close_db()


@pytest.mark.asyncio
async def test_a_v15_database_gains_the_since_then_cache_and_keeps_everything_else(tmp_path):
    path = tmp_path / "v15.db"
    settings = MagicMock()
    settings.db_path = path
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        await db.create_conversation("c1", "t", None)
        await db.save_messages("c1", [stored(ctx=parcel_ctx())])
        await db.close_db()
    con = sqlite3.connect(path)
    con.execute("DROP TABLE fact_checks")
    con.execute("UPDATE schema_version SET version = 15")
    con.commit()
    con.close()
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        try:
            await db.put_fact_check("k", "2026-10-25", {"a": 1})
            assert await db.get_fact_check("k", "2026-10-25") == {"a": 1} and await db.get_fact_check("k", "2026-10-26") is None
            await db.put_fact_check("k", "2026-10-25", {"a": 2})  # the day's first complete check wins
            assert await db.get_fact_check("k", "2026-10-25") == {"a": 1}
            await db.put_fact_check("old", "2026-10-01", {"a": 3})
            await db.put_fact_check("new", "2026-10-25", {"a": 4})  # drops rows more than a week old
            assert await db.get_fact_check("old", "2026-10-01") is None
            assert (await db.get_conversation("c1"))["messages"][0]["content"] == "answer"
        finally:
            await db.close_db()
