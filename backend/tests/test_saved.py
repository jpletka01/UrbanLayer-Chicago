"""Saved (decision Item 119): ownership, caps, merge, deletion and "what changed" on saved lots and searches.

Every external lookup is mocked; nothing here touches the network or a model.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import db, saved
from backend.auth import get_current_user, require_auth
from backend.main import app
from backend.rate_limit import clear_rate_limits

A = {"id": "user_a", "email": "a@example.com", "name": "A", "tier": "free"}
B = {"id": "user_b", "email": "b@example.com", "name": "B", "tier": "free"}

LOT = {"pin": "14331030110000", "address": "642 W Belden Ave", "lat": 41.9237, "lon": -87.6447, "zone": "RM-5",
       "area": "Lincoln Park", "outline": [[-87.6448, 41.9236], [-87.6446, 41.9236], [-87.6446, 41.9238]]}
LOT2 = {"address": "1601 N Milwaukee Ave", "lat": 41.9103, "lon": -87.6773}


@pytest_asyncio.fixture
async def store(tmp_path):
    settings = MagicMock()
    settings.db_path = str(tmp_path / "test.db")
    settings.upload_dir = tmp_path / "uploads"
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        clear_rate_limits()
        yield
        await db.close_db()


@pytest.fixture
def as_user():
    auth_settings = MagicMock()
    auth_settings.google_client_id = ""

    def _set(user: dict | None) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        if user is None:
            def _deny():
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Authentication required")
            app.dependency_overrides[require_auth] = _deny
        else:
            app.dependency_overrides[require_auth] = lambda: user
        return TestClient(app)

    with patch("backend.auth.get_settings", return_value=auth_settings):
        yield _set
    app.dependency_overrides.clear()


def _save(client: TestClient, body: dict = LOT) -> dict:
    r = client.post("/api/saved/lots", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestLots:
    async def test_save_list_note_unsave(self, store, as_user):
        c = as_user(A)
        lot = _save(c)
        assert lot["key"] == "pin:14331030110000" and lot["note"] == "" and lot["zone"] == "RM-5"
        assert c.post("/api/saved/lots", json=LOT).status_code == 200  # already saved: no duplicate
        assert len(c.get("/api/saved/lots").json()["lots"]) == 1
        r = c.patch(f"/api/saved/lots/{lot['id']}", json={"note": "  Ask the broker about the rear lot.  "})
        assert r.json()["note"] == "Ask the broker about the rear lot."
        assert c.delete(f"/api/saved/lots/{lot['id']}").status_code == 204
        assert c.get("/api/saved/lots").json()["lots"] == []

    async def test_address_key_matches_browser_rule(self, store, as_user):
        lot = _save(as_user(A), LOT2)
        assert lot["key"] == "addr:1601 n milwaukee ave" and lot["pin"] is None

    @pytest.mark.parametrize("method,path", [
        ("get", "/api/saved/lots"), ("post", "/api/saved/lots"), ("post", "/api/saved/lots/merge"),
        ("patch", "/api/saved/lots/x"), ("delete", "/api/saved/lots/x"), ("get", "/api/saved/lots/x/changes"),
        ("get", "/api/saved/searches"), ("post", "/api/saved/searches"), ("get", "/api/saved/searches/x/new"),
        ("post", "/api/saved/searches/x/seen"), ("patch", "/api/saved/searches/x"), ("delete", "/api/saved/searches/x"),
    ])
    async def test_signed_out_is_401(self, store, as_user, method, path):
        c = as_user(None)
        r = c.request(method.upper(), path, json={} if method != "get" else None)
        assert r.status_code == 401

    async def test_another_users_lot_is_404(self, store, as_user):
        lot = _save(as_user(A))
        b = as_user(B)
        assert b.get("/api/saved/lots").json()["lots"] == []
        assert b.patch(f"/api/saved/lots/{lot['id']}", json={"note": "mine now"}).status_code == 404
        assert b.delete(f"/api/saved/lots/{lot['id']}").status_code == 404
        assert b.get(f"/api/saved/lots/{lot['id']}/changes").status_code == 404
        a_lots = as_user(A).get("/api/saved/lots").json()["lots"]
        assert len(a_lots) == 1 and a_lots[0]["note"] == ""

    @pytest.mark.parametrize("extra", [{"user_id": "user_b"}, {"snapshot_json": "{}"}, {"note": "x"}, {"id": "abc"}])
    async def test_unknown_fields_rejected(self, store, as_user, extra):
        assert as_user(A).post("/api/saved/lots", json={**LOT, **extra}).status_code == 422

    @pytest.mark.parametrize("bad", [
        {"lat": 40.7}, {"lon": -73.9}, {"pin": "1433103011"}, {"address": "   "}, {"address": "x" * 201},
        {"outline": [[-87.6, 41.9]]}, {"outline": [[0, 0], [1, 1], [2, 2]]}, {"outline": [[-87.6, 41.9]] * 41},
        {"zone": "Z" * 21},
    ])
    async def test_bad_values_rejected(self, store, as_user, bad):
        assert as_user(A).post("/api/saved/lots", json={**LOT, **bad}).status_code == 422

    async def test_note_limit(self, store, as_user):
        c = as_user(A)
        lot = _save(c)
        assert c.patch(f"/api/saved/lots/{lot['id']}", json={"note": "x" * 2001}).status_code == 422
        markup = "<img src=x onerror=alert(1)>"
        assert c.patch(f"/api/saved/lots/{lot['id']}", json={"note": markup}).json()["note"] == markup  # kept as text

    async def test_lot_cap(self, store, as_user, monkeypatch):
        monkeypatch.setattr(saved, "MAX_LOTS", 3)
        c = as_user(A)
        for n in range(3):
            _save(c, {**LOT2, "address": f"{1600 + n} N Milwaukee Ave"})
        r = c.post("/api/saved/lots", json={**LOT2, "address": "1700 N Milwaukee Ave"})
        assert r.status_code == 409 and r.json()["detail"]["error"] == "saved_limit"
        assert len(c.get("/api/saved/lots").json()["lots"]) == 3

    async def test_write_rate_limit(self, store, as_user, monkeypatch):
        c = as_user(A)
        lot = _save(c)
        hits = [c.patch(f"/api/saved/lots/{lot['id']}", json={"note": str(n)}).status_code for n in range(65)]
        assert 429 in hits

    async def test_note_never_logged(self, store, as_user, caplog):
        c = as_user(A)
        caplog.set_level(logging.DEBUG)
        lot = _save(c)
        c.patch(f"/api/saved/lots/{lot['id']}", json={"note": "secret-note-text"})
        # The app's own loggers (backend.*); the database driver's DEBUG lines never reach production logs.
        assert not any("secret-note-text" in r.getMessage() for r in caplog.records if r.name.startswith("backend"))


class TestMerge:
    async def test_merge_keeps_times_and_is_idempotent(self, store, as_user):
        c = as_user(A)
        _save(c, LOT)  # already in the account
        import time
        week_ago = int(time.time() * 1000) - 7 * 86_400_000
        body = {"lots": [{**LOT, "saved_at": week_ago}, {**LOT2, "saved_at": week_ago}]}
        r = c.post("/api/saved/lots/merge", json=body).json()
        assert r["added"] == 1 and len(r["lots"]) == 2
        merged = next(x for x in r["lots"] if x["pin"] is None)
        assert abs(merged["saved_at"] - week_ago) < 1000
        again = c.post("/api/saved/lots/merge", json=body).json()
        assert again["added"] == 0 and len(again["lots"]) == 2

    async def test_merge_clamps_future_and_ancient_times(self, store, as_user):
        import time
        now = int(time.time() * 1000)
        c = as_user(A)
        r = c.post("/api/saved/lots/merge", json={"lots": [
            {**LOT, "saved_at": now + 10 * 86_400_000}, {**LOT2, "saved_at": 1}]}).json()
        for lot in r["lots"]:
            assert now - 366 * 86_400_000 <= lot["saved_at"] <= now + 5000

    async def test_merge_respects_cap_newest_first(self, store, as_user, monkeypatch):
        monkeypatch.setattr(saved, "MAX_LOTS", 2)
        c = as_user(A)
        lots = [{**LOT2, "address": f"{1600 + n} N Milwaukee Ave", "saved_at": 1_800_000_000_000 - n} for n in range(3)]
        r = c.post("/api/saved/lots/merge", json={"lots": lots}).json()
        assert r["added"] == 2 and r["skipped"] == 1
        assert {x["address"] for x in r["lots"]} == {"1600 N Milwaukee Ave", "1601 N Milwaukee Ave"}

    async def test_merge_over_200_rejected(self, store, as_user):
        assert as_user(A).post("/api/saved/lots/merge", json={"lots": [LOT2] * 201}).status_code == 422

    async def test_concurrent_merges_never_duplicate(self, store, as_user):
        await saved._owner(A)
        lots = [saved.LotIn(**{**LOT2, "address": f"{1600 + n} N Milwaukee Ave"}) for n in range(20)]
        results = await asyncio.gather(*(saved._insert_lots("user_a", lots, keep_times=False) for _ in range(5)),
                                       return_exceptions=True)
        added = sum(r[0] for r in results if not isinstance(r, BaseException))
        cur = await db._get_db().execute("SELECT COUNT(*), COUNT(DISTINCT lot_key) FROM saved_lots WHERE user_id = 'user_a'")
        total, distinct = await cur.fetchone()
        assert total == distinct == 20 and added == 20


class TestDeletion:
    async def test_account_deletion_removes_saves(self, store, as_user):
        c = as_user(A)
        _save(c)
        await db._get_db().execute(
            "INSERT INTO saved_searches (id, user_id, name, draft_json, request_json, cqs_json, data_version, match_count,"
            " saved_at, seen_at) VALUES ('s1', 'user_a', 'n', '{}', '{}', '{}', 'v', 0, 0, 0)")
        await db._get_db().commit()
        _save(as_user(B))
        await db.delete_user_account("user_a")
        cur = await db._get_db().execute("SELECT user_id FROM saved_lots UNION ALL SELECT user_id FROM saved_searches")
        assert [r[0] for r in await cur.fetchall()] == ["user_b"]


class TestRecordChanges:
    def test_only_records_after_the_save_day(self):
        records = {
            "sales": [{"sale_date": "2026-11-03T00:00:00.000", "sale_price": "450000"}, {"sale_date": "2024-01-02", "sale_price": "1"}],
            "permits": [{"issued": "2026-11-05", "permit": "P1", "permit_type": "RENOVATION/ALTERATION", "cost": 90000.0},
                        {"issued": "2026-11-01", "permit": "P0"}],
            "violations": [{"date": "2026-11-06", "code": "CN1", "inspection": "I9"},
                           {"date": "2026-11-06", "code": "CN2", "inspection": "I9"},
                           {"date": "2025-05-01", "code": "OLD", "inspection": "I1"}],
        }
        changes, unchecked = saved.record_changes(records, "2026-11-01")
        assert unchecked == []
        assert [(c["kind"], c["date"]) for c in changes] == [("sale", "2026-11-03"), ("permit", "2026-11-05"), ("violation", "2026-11-06")]
        assert changes[0]["price"] == 450000.0

    def test_a_failed_source_is_unchecked_not_none(self):
        changes, unchecked = saved.record_changes({"sales": None, "permits": [], "violations": None}, "2026-11-01")
        assert changes == [] and unchecked == ["sales", "violations"]


class TestChangesEndpoint:
    async def test_first_check_takes_baseline_then_diffs(self, store, as_user):
        c = as_user(A)
        lot = _save(c)
        today = {"zoning": {"zone_class": "RM-5"}, "overlays": [], "checked": {"zoning": True, "unchecked_overlays": []}}
        filings = SimpleNamespace(status="ready", subject_filings=[])
        with patch("backend.saved._records", AsyncMock(return_value={"sales": [], "permits": [], "violations": []})), \
             patch("backend.data_health.diff.current_facts", AsyncMock(return_value=today)) as facts, \
             patch("backend.legislation.upcoming.summary_for", return_value=filings):
            first = c.get(f"/api/saved/lots/{lot['id']}/changes").json()
            assert first["status"] == "none" and first["watching_since"] is not None
            assert facts.await_count == 1
            # A second check reads the stored baseline and today's cached facts: no new lookup.
            with patch("backend.data_health.diff._too_soon", return_value=False):
                second = c.get(f"/api/saved/lots/{lot['id']}/changes").json()
            assert second["status"] == "none" and facts.await_count == 1

    async def test_failed_lookups_are_partial(self, store, as_user):
        c = as_user(A)
        lot = _save(c)
        with patch("backend.saved._records", AsyncMock(return_value={"sales": None, "permits": [], "violations": []})), \
             patch("backend.data_health.diff.current_facts", AsyncMock(side_effect=RuntimeError("down"))), \
             patch("backend.legislation.upcoming.summary_for", return_value=SimpleNamespace(status="unavailable", subject_filings=[])):
            r = c.get(f"/api/saved/lots/{lot['id']}/changes").json()
        assert r["status"] == "partial"
        assert set(r["unchecked"]) == {"sales", "zoning", "rezoning"}
        row = await (await db._get_db().execute("SELECT snapshot_json FROM saved_lots")).fetchone()
        assert row[0] is None  # no baseline from a failed lookup

    async def test_rezoning_filed_after_save(self, store, as_user):
        c = as_user(A)
        lot = _save(c)
        filing = SimpleNamespace(introduced_at="2099-01-05", record_number="O2099-1", title="Rezoning", url="https://x")
        today = {"zoning": {"zone_class": "RM-5"}, "overlays": [], "checked": {"zoning": True, "unchecked_overlays": []}}
        with patch("backend.saved._records", AsyncMock(return_value={"sales": [], "permits": [], "violations": []})), \
             patch("backend.data_health.diff.current_facts", AsyncMock(return_value=today)), \
             patch("backend.legislation.upcoming.summary_for", return_value=SimpleNamespace(status="ready", subject_filings=[filing])):
            r = c.get(f"/api/saved/lots/{lot['id']}/changes").json()
        assert r["status"] == "changes" and r["changes"][0]["kind"] == "rezoning_filed"


class TestSearches:
    REQ = {"userFilters": {}, "text": "vacant", "limit": 50, "includePins": True}

    def _eval(self, pins):
        return patch("backend.saved._evaluate", return_value=({"filters": {}}, "v1", pins))

    async def test_save_new_seen_rename_delete(self, store, as_user):
        c = as_user(A)
        with self._eval(["1", "2", "3"]):
            s = c.post("/api/saved/searches", json={"name": "Vacant  in Logan", "draft": {"text": "vacant"}, "request": self.REQ}).json()
        assert s["name"] == "Vacant in Logan" and s["match_count"] == 3
        with self._eval(["2", "3", "4", "5"]):
            n = c.get(f"/api/saved/searches/{s['id']}/new").json()
            assert (n["new"], n["gone"], n["exact"], n["total"]) == (2, 1, True, 4)
            assert c.post(f"/api/saved/searches/{s['id']}/seen").json()["match_count"] == 4
            assert c.get(f"/api/saved/searches/{s['id']}/new").json()["new"] == 0
        assert c.patch(f"/api/saved/searches/{s['id']}", json={"name": "Logan"}).json()["name"] == "Logan"
        assert c.delete(f"/api/saved/searches/{s['id']}").status_code == 204
        assert c.get("/api/saved/searches").json()["searches"] == []

    async def test_broad_search_counts_only(self, store, as_user, monkeypatch):
        monkeypatch.setattr(saved, "MAX_STORED_PINS", 2)
        c = as_user(A)
        with self._eval(["1", "2", "3"]):
            s = c.post("/api/saved/searches", json={"name": "All", "draft": {}, "request": self.REQ}).json()
        with self._eval(["1", "2", "3", "4"]):
            n = c.get(f"/api/saved/searches/{s['id']}/new").json()
        assert n["exact"] is False and n["new"] == 1

    async def test_another_users_search_is_404(self, store, as_user):
        with self._eval(["1"]):
            s = as_user(A).post("/api/saved/searches", json={"name": "Mine", "draft": {}, "request": self.REQ}).json()
            b = as_user(B)
            assert b.get(f"/api/saved/searches/{s['id']}/new").status_code == 404
            assert b.post(f"/api/saved/searches/{s['id']}/seen").status_code == 404
            assert b.patch(f"/api/saved/searches/{s['id']}", json={"name": "x"}).status_code == 404
            assert b.delete(f"/api/saved/searches/{s['id']}").status_code == 404
            assert b.get("/api/saved/searches").json()["searches"] == []

    async def test_search_cap_and_size(self, store, as_user, monkeypatch):
        monkeypatch.setattr(saved, "MAX_SEARCHES", 1)
        c = as_user(A)
        with self._eval(["1"]):
            assert c.post("/api/saved/searches", json={"name": "a", "draft": {}, "request": self.REQ}).status_code == 201
            r = c.post("/api/saved/searches", json={"name": "b", "draft": {}, "request": self.REQ})
            assert r.status_code == 409
        big = {"name": "big", "draft": {"x": "y" * 20_000}, "request": self.REQ}
        assert as_user(B).post("/api/saved/searches", json=big).status_code == 413

    def test_evaluate_rejects_a_non_search(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            saved._evaluate({"userFilters": "nope"})
        assert e.value.status_code == 422

    def test_pins_pack_roundtrip(self):
        assert saved._unpack(saved._pack(["b", "a"])) == {"a", "b"}
        assert saved._unpack(saved._pack([])) == set()


def test_migration_v17_tables_exist(tmp_path):
    async def run():
        settings = MagicMock()
        settings.db_path = str(tmp_path / "m.db")
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            cur = await db._get_db().execute("SELECT name FROM sqlite_master WHERE name IN ('saved_lots', 'saved_searches')")
            names = sorted(r[0] for r in await cur.fetchall())
            ver = (await (await db._get_db().execute("SELECT version FROM schema_version")).fetchone())[0]
            await db.close_db()
        return names, ver
    names, ver = asyncio.run(run())
    assert names == ["saved_lots", "saved_searches"] and ver == 17
