"""WS2 PR 1: pending-source truth, lifecycle normalization and last-good storage."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from backend.config import get_settings
from backend.data_health import probes
from backend.data_health.registry import BY_ID
from backend.legislation import pending, sync, upcoming
from backend.legislation import address_titles
from backend.legislation.pending_store import Snapshot, Store, read_status
from backend.retrieval import clerk


FIX = Path(__file__).parent / "fixtures" / "clerk"
NOW = datetime(2026, 10, 27, 18, 0, tzinfo=timezone.utc)


def _row(record: str = "O2026-0000001", **over) -> dict:
    row = {
        "matterId": "id-" + record,
        "recordNumber": record,
        "originalRecordNumber": None,
        "status": "4-In Committee",
        "subStatus": "Referred",
        "matterCategory": "ZONING RECLASSIFICATIONS",
        "type": "Ordinance",
        "title": "Zoning Reclassification Map No. 1-A at 10 N State St - App No. 23001",
        "introductionDate": "2026-10-21T15:00:00+00:00",
        "finalActionDate": None,
        "recordCreateDate": "2026-10-20T18:00:00+00:00",
        "lastPublicationDate": "2026-10-21T17:00:00+00:00",
        "supersededBy": None,
        "relations": [],
        "attachments": [],
        "actions": [],
    }
    row.update(over)
    return row


def _matter(record: str = "O2026-0000001", **over) -> clerk.ClerkMatter:
    return clerk.ClerkMatter.from_api(_row(record, **over))


async def _snapshot_for(*matters: clerk.ClerkMatter) -> Snapshot:
    by_id = {m.matter_id: m for m in matters}
    by_record = {m.record_number: m for m in matters}

    async def search(*, client=None):
        return list(matters)

    async def detail_id(value, *, client=None):
        return by_id.get(value)

    async def detail_record(value, *, client=None):
        return by_record.get(value)

    return await pending.build_snapshot(
        now=NOW,
        search=search,
        detail_by_id=detail_id,
        detail_by_record=detail_record,
        pause_s=0,
    )


async def test_pending_query_validates_vocabulary_and_keeps_only_zoning_or_title17():
    rows = [
        _row("O2026-1"),
        _row(
            "O2026-2",
            matterId="id-code17",
            matterCategory="MUNICIPAL CODE AMENDMENTS",
            title="Amendment of Municipal Code Section 17-2-0304 concerning minimum lot area",
        ),
        _row(
            "O2026-3",
            matterId="id-other",
            matterCategory="MUNICIPAL CODE AMENDMENTS",
            title="Amendment of Municipal Code Section 9-64-010 concerning parking meters",
        ),
        _row(
            "O2019-320",
            matterId="id-rereferral",
            status="5-Council Consideration",
            subStatus="Recommended for Re-Referral",
            matterCategory="MUNICIPAL CODE AMENDMENTS | Title 13 - Building & Construction",
            title="Amendment of Municipal Code Title 13 concerning bird-friendly design",
        ),
    ]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": rows, "meta": {"count": len(rows)}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        got = await clerk.pending_zoning_matters(client=client)
    assert [m.record_number for m in got] == ["O2026-1", "O2026-2"]
    params = parse_qs(urlparse(str(requests[0].url)).query)
    assert "status ne '90-Final'" in params["filter"][0]
    assert "ZONING RECLASSIFICATIONS" in params["filter"][0]
    assert "MUNICIPAL CODE AMENDMENTS" in params["filter"][0]


async def test_pending_query_treats_a_new_workflow_value_as_contract_drift():
    bad = _row(status="6-New Workflow", subStatus="Mystery")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [bad], "meta": {"count": 1}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(clerk.ClerkContractError, match="unknown pending status"):
            await clerk.pending_zoning_matters(client=client)


async def test_recorded_pending_detail_is_parseable_and_contains_no_eds_metadata():
    raw = json.loads((FIX / "pending_matter_O2026-0029359.json").read_text())
    assert raw["_recorded"] == "2026-10-27"
    assert not any("EDS" in json.dumps(a).upper() for a in raw["attachments"])
    matter = clerk.ClerkMatter.from_api(raw)
    snapshot = await _snapshot_for(matter)
    assert snapshot.counts == {
        "candidates": 1,
        "details": 1,
        "pending": 1,
        "zoning": 1,
        "code": 0,
        "title17": 0,
        "placement_ready": 1,
        "placed_matters": 0,
        "unplaced_matters": 1,
        "locations": 0,
        "partial_titles": 0,
        "unparsed_titles": 0,
        "lifecycle_collapses": 0,
        "excluded_non_pending": 0,
        "excluded_attachments": 0,
    }
    assert len(snapshot.matters[0].attachments) == 3
    assert snapshot.matters[0].application_number == "23180"


def test_hand_labeled_pending_title_panel_meets_precision_floor_with_no_wrong_streets():
    panel = json.loads((FIX / "pending_title_panel.json").read_text())
    rows = panel["rows"]
    safe = 0
    placed = 0
    correct = 0
    wrong_streets: list[str] = []
    for row in rows:
        parsed = address_titles.parse_title(row["title"])
        predicted = parsed.status == "clean"
        safe += int(row["safe_to_place"])
        placed += int(predicted)
        actual = [f"{s.dir} {s.name} {s.type}".upper() for s in parsed.segments] if predicted else []
        expected = [value.upper() for value in row["streets"]]
        if predicted and actual != expected:
            wrong_streets.append(row["record"])
        if predicted and row["safe_to_place"] and actual == expected:
            correct += 1

    precision = correct / placed
    coverage = placed / len(rows)
    contract = panel["measured_contract"]
    assert len(rows) == contract["panel_size"] and safe == contract["safe_titles"]
    assert precision >= contract["precision_floor"]
    assert wrong_streets == []
    assert coverage == pytest.approx(contract["placement_coverage"], abs=0.0001)


async def test_eds_unknown_types_and_non_https_urls_are_rejected_before_the_store():
    matter = _matter(attachments=[
        {"fileName": "O2026-1 Ordinance.pdf", "path": "https://clerk.test/ordinance.pdf", "attachmentType": "Legislation"},
        {"fileName": "O2026-1 EDS.pdf", "path": "https://clerk.test/eds.pdf", "attachmentType": "EDS"},
        {"fileName": "Economic Disclosure Statement.pdf", "path": "https://clerk.test/mislabeled.pdf", "attachmentType": "Miscellaneous"},
        {"fileName": "Unknown.pdf", "path": "https://clerk.test/unknown.pdf", "attachmentType": "Other"},
        {"fileName": "Application.pdf", "path": "http://clerk.test/application.pdf", "attachmentType": "Miscellaneous"},
    ])
    snapshot = await _snapshot_for(matter)
    assert [a.file_name for a in snapshot.matters[0].attachments] == ["O2026-1 Ordinance.pdf"]
    assert snapshot.counts["excluded_attachments"] == 4


async def test_superseded_original_collapses_to_the_one_current_substitute():
    original = _matter("O2026-0000001", supersededBy="SO2026-0000001")
    substitute = _matter(
        "SO2026-0000001",
        matterId="id-substitute",
        originalRecordNumber="O2026-0000001",
        relations=["SO2026-0000001"],
    )

    async def search(*, client=None):
        return [original]

    async def detail_id(value, *, client=None):
        return original if value == original.matter_id else None

    async def detail_record(value, *, client=None):
        return substitute if value == substitute.record_number else None

    snapshot = await pending.build_snapshot(
        now=NOW, search=search, detail_by_id=detail_id, detail_by_record=detail_record, pause_s=0,
    )
    assert [m.record_number for m in snapshot.matters] == ["SO2026-0000001"]
    row = snapshot.matters[0]
    assert row.lifecycle_id == "O2026-0000001"
    assert ("O2026-0000001", "original") in {
        (r.related_record_number, r.relation_type) for r in row.relations
    }
    assert snapshot.counts["lifecycle_collapses"] == 1


async def test_a_listed_original_that_is_final_in_detail_is_not_pending():
    listed = _matter()
    final = _matter(
        "SO2026-0000001",
        matterId=listed.matter_id,
        originalRecordNumber="O2026-0000001",
        status=clerk.FINAL,
        subStatus="Passed as Substitute",
        finalActionDate="2026-10-27T15:00:00+00:00",
    )

    async def search(*, client=None):
        return [listed]

    async def detail_id(value, *, client=None):
        return final

    async def detail_record(value, *, client=None):
        return None

    snapshot = await pending.build_snapshot(
        now=NOW, search=search, detail_by_id=detail_id, detail_by_record=detail_record, pause_s=0,
    )
    assert snapshot.matters == () and snapshot.counts["excluded_non_pending"] == 1


async def test_two_current_records_in_one_lifecycle_are_suspect_not_guessed():
    original = _matter("O2026-0000001")
    substitute = _matter(
        "SO2026-0000001", matterId="id-sub", originalRecordNumber="O2026-0000001",
    )
    with pytest.raises(pending.PendingContractError, match="multiple current matters"):
        await _snapshot_for(original, substitute)


async def test_store_failure_keeps_last_good_rows_and_health_counts(tmp_path):
    path = tmp_path / "pending.db"
    snapshot = await _snapshot_for(_matter())
    with Store(path) as store:
        store.replace(snapshot)
        store.record_problem(
            NOW.replace(hour=19), status="failed", error="ClerkUnavailable: 503 after retries",
        )

    status = read_status(path)
    assert status.latest_status == "failed" and status.checked_at == NOW
    assert status.counts == snapshot.counts and "503" in status.last_error
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT record_number FROM matters").fetchall() == [("O2026-0000001",)]


async def test_store_replacement_rolls_back_entire_snapshot_on_constraint_failure(tmp_path):
    path = tmp_path / "pending.db"
    good = await _snapshot_for(_matter())
    duplicate = replace(good.matters[0], matter_id="different-id")
    bad = replace(good, matters=(good.matters[0], duplicate))
    with Store(path) as store:
        store.replace(good)
        with pytest.raises(sqlite3.IntegrityError):
            store.replace(bad)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT matter_id, record_number FROM matters").fetchall() == [
            ("id-O2026-0000001", "O2026-0000001")
        ]
        assert con.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0] == 1


def test_schema_v1_store_migrates_in_place_to_placement_schema(tmp_path):
    path = tmp_path / "pending-v1.db"
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, attempted_at TEXT NOT NULL, checked_at TEXT,
                status TEXT NOT NULL, last_error TEXT, contract_problems TEXT NOT NULL DEFAULT '[]',
                candidate_count INTEGER, detail_count INTEGER, pending_count INTEGER, zoning_count INTEGER,
                code_count INTEGER, title17_count INTEGER, placement_ready_count INTEGER,
                partial_title_count INTEGER, unparsed_title_count INTEGER, lifecycle_collapses INTEGER,
                excluded_non_pending INTEGER, excluded_attachments INTEGER
            );
            PRAGMA user_version=1;
        """)
    with Store(path):
        pass
    with sqlite3.connect(path) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(sync_runs)")}
        assert con.execute("PRAGMA user_version").fetchone()[0] == 2
        assert {"placed_matter_count", "unplaced_matter_count", "location_count"} <= columns
        assert {"segments", "locations"} <= {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_schema_v1_status_is_readable_before_the_daily_writer_migrates_it(tmp_path):
    path = tmp_path / "pending-v1-readonly.db"
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, attempted_at TEXT NOT NULL, checked_at TEXT,
                status TEXT NOT NULL, last_error TEXT, contract_problems TEXT NOT NULL DEFAULT '[]',
                candidate_count INTEGER, detail_count INTEGER, pending_count INTEGER, zoning_count INTEGER,
                code_count INTEGER, title17_count INTEGER, placement_ready_count INTEGER,
                partial_title_count INTEGER, unparsed_title_count INTEGER, lifecycle_collapses INTEGER,
                excluded_non_pending INTEGER, excluded_attachments INTEGER
            );
            INSERT INTO sync_runs (
                attempted_at, checked_at, status, candidate_count, pending_count, zoning_count
            ) VALUES ('2026-10-27T18:00:00+00:00', '2026-10-27T18:00:00+00:00', 'ok', 4, 3, 2);
            PRAGMA user_version=1;
        """)
    status = read_status(path)
    assert status is not None and status.counts["zoning"] == 2
    assert status.counts["placed_matters"] is None and status.counts["locations"] is None


async def test_data_health_probe_reports_last_failure_without_losing_last_good_date(tmp_path, monkeypatch):
    path = tmp_path / "pending.db"
    snapshot = await _snapshot_for(_matter())
    with Store(path) as store:
        store.replace(snapshot)
        store.record_problem(NOW.replace(hour=19), status="failed", error="Clerk unavailable")
    monkeypatch.setattr(get_settings(), "pending_legislation_path", path, raising=False)

    result = await probes.probe_pending_legislation(BY_ID["internal.pending_legislation"], None)
    assert result.content == NOW.date()
    assert "pending=1" in result.info and result.findings[0].level == "warn"
    assert "Clerk unavailable" in result.findings[0].text


def test_pending_summary_cli_has_the_review_counts():
    snapshot = asyncio.run(_snapshot_for(_matter()))
    text = pending.summary(snapshot)
    assert "pending=1" in text and "placement_ready=1" in text and "excluded_attachments=0" in text


async def test_daily_placement_drives_exact_then_nearby_profile_summary(tmp_path):
    exact = _matter(
        "O2026-0000010",
        title="Zoning Reclassification Map No. 1-A at 10 N State St - App No. 23010",
    )
    nearby = _matter(
        "O2026-0000100",
        title="Zoning Reclassification Map No. 1-A at 100 N State St - App No. 23100",
    )
    snapshot = await _snapshot_for(exact, nearby)

    async def resolver(*, lo, **_kwargs):
        if lo == 10:
            return [{"pin": "17000000000001", "lat": 41.8800, "lon": -87.6278, "number": 10, "name": "STATE"}]
        return [{"pin": "17000000000002", "lat": 41.8840, "lon": -87.6278, "number": 100, "name": "STATE"}]

    snapshot = await pending.resolve_placements(snapshot, resolver=resolver)
    path = tmp_path / "pending.db"
    with Store(path) as store:
        store.replace(snapshot)

    result = upcoming.summary_for(
        path,
        lat=41.8800,
        lon=-87.6278,
        pin="17000000000001",
        address="10 N State St",
        authoritative_pin=True,
        now=NOW + timedelta(hours=1),
    )
    assert result.status == "ready" and result.placement_status == "complete"
    assert [row.record_number for row in result.subject_filings] == ["O2026-0000010"]
    assert result.subject_filings[0].match_kind == "subject_pin"
    assert [row.record_number for row in result.nearby_filings] == ["O2026-0000100"]
    assert result.nearby_filings[0].distance_mi is not None


async def test_unplaced_title_makes_a_checked_zero_partial_not_healthy_empty(tmp_path):
    snapshot = await _snapshot_for(_matter(title="Applicant requests a zoning change near State Street"))
    path = tmp_path / "pending.db"
    with Store(path) as store:
        store.replace(snapshot)
    result = upcoming.summary_for(
        path, lat=41.88, lon=-87.63, pin=None, address="10 N State St",
        authoritative_pin=False, now=NOW + timedelta(hours=1),
    )
    assert result.status == "ready" and result.placement_status == "partial"
    assert result.unplaced_count == 1
    assert result.subject_filings == [] and result.nearby_filings == []


async def test_failed_refresh_preserves_last_good_rows_but_summary_is_stale(tmp_path):
    snapshot = await _snapshot_for()
    path = tmp_path / "pending.db"
    with Store(path) as store:
        store.replace(snapshot)
        store.record_problem(NOW + timedelta(hours=1), status="failed", error="Address Points unavailable")
    result = upcoming.summary_for(
        path, lat=41.88, lon=-87.63, pin=None, address=None,
        authoritative_pin=False, now=NOW + timedelta(hours=2),
    )
    assert result.status == "stale"
    assert result.checked_at == NOW.isoformat(timespec="seconds")


def test_missing_or_too_old_snapshot_is_unavailable_not_empty(tmp_path):
    missing = upcoming.summary_for(
        tmp_path / "missing.db", lat=41.88, lon=-87.63, pin=None, address=None,
        authoritative_pin=False, now=NOW,
    )
    assert missing.status == "unavailable" and missing.placement_status == "partial"

    corrupt_path = tmp_path / "corrupt.db"
    corrupt_path.write_text("not sqlite")
    corrupt = upcoming.summary_for(
        corrupt_path, lat=41.88, lon=-87.63, pin=None, address=None,
        authoritative_pin=False, now=NOW,
    )
    assert corrupt.status == "unavailable"

    path = tmp_path / "old.db"
    snapshot = asyncio.run(_snapshot_for())
    with Store(path) as store:
        store.replace(snapshot)
    old = upcoming.summary_for(
        path, lat=41.88, lon=-87.63, pin=None, address=None,
        authoritative_pin=False, now=NOW + timedelta(days=15),
    )
    assert old.status == "unavailable" and old.subject_filings == []


def test_daily_sync_keeps_the_passed_snapshot_truth_when_pending_refresh_fails(monkeypatch, tmp_path):
    passed = {"status": "ok", "checked_at": NOW.isoformat(), "counts": {"title17": 2}}
    monkeypatch.setattr(sync, "build_snapshot", AsyncMock(return_value=passed))
    monkeypatch.setattr(
        pending, "refresh", AsyncMock(side_effect=clerk.ClerkUnavailable("429 after retries")),
    )
    monkeypatch.setattr(sync, "_report", lambda exc: None)

    code, result = asyncio.run(sync.run(
        tmp_path / "passed.json", pending_path=tmp_path / "pending.db", write=False,
    ))
    assert code == 1 and result["status"] == "ok"
    assert result["pending_check"]["status"] == "failed"
    assert "429 after retries" in result["pending_check"]["last_error"]


def test_primary_clerk_failure_records_a_pending_attempt_without_a_second_source_call(monkeypatch, tmp_path):
    pending_path = tmp_path / "pending.db"
    monkeypatch.setattr(
        sync, "build_snapshot", AsyncMock(side_effect=clerk.ClerkUnavailable("source offline")),
    )
    refresh = AsyncMock()
    monkeypatch.setattr(pending, "refresh", refresh)
    monkeypatch.setattr(sync, "_report", lambda exc: None)

    code, result = asyncio.run(sync.run(tmp_path / "passed.json", pending_path=pending_path))
    status = read_status(pending_path)
    assert code == 1 and result["pending_check"]["status"] == "failed"
    assert status is not None and status.latest_status == "failed" and status.checked_at is None
    assert "source offline" in (status.last_error or "")
    refresh.assert_not_awaited()
