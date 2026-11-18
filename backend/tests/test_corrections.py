"""Suggest a correction (decision Item 129, PR 1): the body, who sent it, the limits, one open report per lot,
account deletion, and what is (and isn't) stored or logged.

Nothing here touches the network or a model: the Discovery index is an in-memory snapshot and the database a
temporary file.
"""

from __future__ import annotations

import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import corrections, db, quotas
from backend.auth import get_current_user
from backend.discovery import parcel_source
from backend.discovery.parcel import DictParcel, default_source
from backend.main import app
from backend.rate_limit import clear_rate_limits

A = {"id": "user_a", "email": "a@example.com", "name": "A", "tier": "free"}
B = {"id": "user_b", "email": "b@example.com", "name": "B", "tier": "free"}

VERSION = "test-corrections-v1"
PIN = "14331030110000"
PIN10 = PIN[:10]
# Enough lots for every limit (60 > the 50 open per account).
LOTS = [f"{1400000000 + i:010d}" for i in range(60)]
REPORT = {"pin": PIN, "kinds": ["stories"], "stories": 3}


@pytest.fixture(autouse=True)
def snapshot():
    parcels = [DictParcel(PIN, {"bldg_sqft": 2400.0, "bldg_sqft_source": "footprint", "room_sqft": 1350.0})]
    parcels += [DictParcel(p + "0000", {"bldg_sqft": 1000.0, "bldg_sqft_source": "footprint"}) for p in LOTS]
    parcel_source.set_snapshot(VERSION, parcels)
    yield
    parcel_source._current_version = None
    default_source.clear()


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
    """A TestClient for a signed-in user, or for a signed-out visitor (None). Sign-in is off (no providers), so
    CSRF passes and the stand-in user gets a users row, as in local development."""
    auth_settings = MagicMock()
    auth_settings.google_client_id = ""
    auth_settings.microsoft_client_id = ""
    auth_settings.apple_client_id = ""
    auth_settings.auth_dev_login = False
    auth_settings.jwt_secret = "test-secret"

    def _set(user: dict | None) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    with patch("backend.auth.get_settings", return_value=auth_settings):
        yield _set
    app.dependency_overrides.clear()


async def _rows(sql: str = "SELECT * FROM lot_corrections ORDER BY id", args: tuple = ()) -> list[dict]:
    cur = await db._get_db().execute(sql, args)
    return [dict(r) for r in await cur.fetchall()]


def _send(c: TestClient, body: dict | None = None, **over) -> object:
    return c.post("/api/discovery/corrections", json={**(body or REPORT), **over})


class TestBody:
    @pytest.mark.parametrize("extra", [{"user_id": "user_b"}, {"status": "accepted"}, {"shown": {}}, {"ip": "1.2.3.4"}])
    async def test_forbids_extra_fields(self, store, as_user, extra):
        assert _send(as_user(A), **extra).status_code == 422
        assert await _rows() == []

    @pytest.mark.parametrize("body", [
        {"pin": PIN, "kinds": []},
        {"pin": PIN, "kinds": ["owner"]},
        {"pin": PIN, "kinds": ["stories"]},  # a story count is needed
        {"pin": PIN, "kinds": ["stories"], "stories": 0},
        {"pin": PIN, "kinds": ["stories"], "stories": 151},
        {"pin": PIN, "kinds": ["area"]},  # a direction is needed
        {"pin": PIN, "kinds": ["area"], "area_dir": "sideways"},
        {"pin": PIN, "kinds": ["gone", "stories"], "stories": 2},  # no building now clears stories and area
        {"pin": PIN, "kinds": ["other"], "stories": 2},  # a count without the kind
        {"pin": "1433", "kinds": ["other"]},
        {"pin": "abcdefghij", "kinds": ["other"]},
    ])
    async def test_rejects_bad_bodies(self, store, as_user, body):
        assert _send(as_user(A), body).status_code == 422

    async def test_stores_the_report_and_the_server_snapshot(self, store, as_user):
        r = _send(as_user(A), {"pin": "14-33-103-011-0000", "kinds": ["stories", "area", "stories"], "stories": 20,
                               "area_dir": "low", "note": "   Twenty floors, not two.   "})
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "new" and r.json()["replaced"] is False
        [row] = await _rows()
        assert row["pin10"] == PIN10 and json.loads(row["kinds"]) == ["stories", "area"]
        assert row["stories"] == 20 and row["area_dir"] == "low" and row["note"] == "Twenty floors, not two."
        assert row["user_id"] == "user_a" and row["anon_id"] is None and row["ip_hash"] is None
        assert row["status"] == "new" and row["reviewed_by"] is None and row["created_at"] > 0
        assert json.loads(row["shown"]) == {"bldg_sqft": 2400.0, "bldg_sqft_source": "footprint", "stories": None,
                                            "room_sqft": 1350.0, "structure": None, "condo": None,
                                            "data_version": VERSION}

    async def test_note_is_trimmed_and_capped(self, store, as_user):
        assert _send(as_user(A), {"pin": PIN, "kinds": ["other"], "note": "  " + "x" * 600}).status_code == 201
        [row] = await _rows()
        assert row["note"] == "x" * 280
        assert _send(as_user(A), {"pin": PIN, "kinds": ["other"], "note": "x" * 2001}).status_code == 422

    async def test_blank_note_is_null(self, store, as_user):
        assert _send(as_user(A), {"pin": PIN, "kinds": ["condo"], "note": "    "}).status_code == 201
        assert (await _rows())[0]["note"] is None

    async def test_unknown_lot_is_404(self, store, as_user):
        r = _send(as_user(A), {"pin": "9999999999", "kinds": ["gone"]})
        assert r.status_code == 404
        assert await _rows() == []

    async def test_no_index_is_404(self, store, as_user):
        parcel_source._current_version = None
        assert _send(as_user(None)).status_code == 404


class TestSignedOut:
    async def test_row_carries_anon_id_and_ip_hash_and_no_raw_ip(self, store, as_user):
        c = as_user(None)
        with patch("backend.corrections.client_ip", return_value="203.0.113.7"):
            r = _send(c)
        assert r.status_code == 201
        cookie = r.cookies.get(quotas.ANON_COOKIE)
        anon_id = quotas.read_anon(cookie)
        assert anon_id  # a signed cookie was set, as the question allowance does
        [row] = await _rows()
        assert row["user_id"] is None and row["anon_id"] == anon_id
        assert row["ip_hash"] and len(row["ip_hash"]) == 32
        dump = json.dumps(row)
        assert "203.0.113.7" not in dump and "203.0.113" not in dump

    async def test_keeps_an_existing_cookie(self, store, as_user):
        c = as_user(None)
        c.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor1"))
        r = _send(c)
        assert r.status_code == 201 and quotas.ANON_COOKIE not in r.cookies
        assert (await _rows())[0]["anon_id"] == "visitor1"

    async def test_forged_cookie_gets_a_new_id(self, store, as_user):
        c = as_user(None)
        c.cookies.set(quotas.ANON_COOKIE, "visitor1.forged")
        r = _send(c)
        assert (await _rows())[0]["anon_id"] != "visitor1" and r.cookies.get(quotas.ANON_COOKIE)

    async def test_ip_hash_is_keyed_and_ipv6_is_per_64(self, store, as_user):
        req = MagicMock()
        with patch("backend.corrections.client_ip", return_value="2001:db8::1"):
            a = corrections.ip_hash(req)
        with patch("backend.corrections.client_ip", return_value="2001:db8::ffff"):
            b = corrections.ip_hash(req)
        with patch("backend.corrections.client_ip", return_value="198.51.100.1"):
            c = corrections.ip_hash(req)
        assert a == b != c

    async def test_three_a_day_per_cookie(self, store, as_user):
        c = as_user(None)
        c.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor1"))
        for pin in LOTS[:3]:
            assert _send(c, pin=pin).status_code == 201
        r = _send(c, pin=LOTS[3])
        assert r.status_code == 429 and r.json()["detail"] == corrections.TOO_MANY
        assert len(await _rows()) == 3

    async def test_ten_a_day_per_network(self, store, as_user):
        c = as_user(None)
        for i, pin in enumerate(LOTS[:10]):
            c.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon(f"visitor{i // 3}"))  # new cookies, same network
            assert _send(c, pin=pin).status_code == 201, i
        c.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("fresh"))
        assert _send(c, pin=LOTS[10]).status_code == 429
        # The refused report didn't use up the fresh cookie's allowance on another network.
        with patch("backend.corrections.client_ip", return_value="198.51.100.9"):
            assert _send(c, pin=LOTS[11]).status_code == 201

    async def test_a_second_report_on_the_lot_replaces_the_first(self, store, as_user):
        c = as_user(None)
        c.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor1"))
        assert _send(c).status_code == 201
        r = _send(c, kinds=["stories"], stories=4)
        assert r.status_code == 201 and r.json()["replaced"] is True
        [row] = await _rows()
        assert row["stories"] == 4
        # Another visitor's report on the same lot stands beside it.
        c2 = as_user(None)
        c2.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor2"))
        assert _send(c2).json()["replaced"] is False
        assert len(await _rows()) == 2


class TestSignedIn:
    async def test_ten_an_hour(self, store, as_user):
        c = as_user(A)
        for pin in LOTS[:10]:
            assert _send(c, pin=pin).status_code == 201
        r = _send(c, pin=LOTS[10])
        assert r.status_code == 429 and r.json()["detail"] == corrections.TOO_MANY
        assert _send(as_user(B), pin=LOTS[10]).status_code == 201  # per account

    async def test_fifty_open(self, store, as_user):
        c = as_user(A)
        for i, pin in enumerate(LOTS[:50]):
            if i % 10 == 0:
                clear_rate_limits()  # step past the hourly limit
            assert _send(c, pin=pin).status_code == 201
        clear_rate_limits()
        assert _send(c, pin=LOTS[50]).status_code == 429
        # Replacing an open report doesn't add one, so it still goes through.
        assert _send(c, pin=LOTS[0]).json()["replaced"] is True
        # A reviewed report is no longer open.
        await db._get_db().execute("UPDATE lot_corrections SET status = 'rejected' WHERE pin10 = ?", (LOTS[1],))
        await db._get_db().commit()
        assert _send(c, pin=LOTS[50]).status_code == 201

    async def test_one_open_per_lot_and_reviewed_ones_stay(self, store, as_user):
        c = as_user(A)
        assert _send(c).json()["replaced"] is False
        assert _send(c, kinds=["gone"], stories=None).json()["replaced"] is True
        [row] = await _rows()
        assert json.loads(row["kinds"]) == ["gone"] and row["stories"] is None
        await db._get_db().execute("UPDATE lot_corrections SET status = 'accepted'")
        await db._get_db().commit()
        assert _send(c).json()["replaced"] is False
        assert [r["status"] for r in await _rows()] == ["accepted", "new"]


class TestDeletion:
    async def test_account_deletion_removes_its_reports(self, store, as_user):
        assert _send(as_user(A)).status_code == 201
        assert _send(as_user(B)).status_code == 201
        anon = as_user(None)
        assert _send(anon).status_code == 201
        await db.delete_user_account("user_a")
        rows = await _rows()
        assert {r["user_id"] for r in rows} == {"user_b", None}

    async def test_foreign_key_cascades(self, store, as_user):
        assert _send(as_user(A)).status_code == 201
        await db._get_db().execute("DELETE FROM users WHERE id = 'user_a'")
        await db._get_db().commit()
        assert await _rows() == []


class TestLogging:
    async def test_logs_only_the_event(self, store, as_user, caplog):
        c = as_user(None)
        with caplog.at_level(logging.INFO, logger="backend.corrections"), \
                patch("backend.corrections.client_ip", return_value="203.0.113.7"):
            _send(c, {"pin": PIN, "kinds": ["stories", "other"], "stories": 5, "note": "secret note"})
            _send(as_user(A), {"pin": PIN, "kinds": ["condo"]})
        lines = [r.getMessage() for r in caplog.records if r.name == "backend.corrections"]
        assert lines == ["correction_sent kinds=stories,other signed_in=False",
                         "correction_sent kinds=condo signed_in=True"]
        text = " ".join(lines)
        for secret in ("secret note", "203.0.113.7", PIN10, "user_a"):
            assert secret not in text


class TestMigration:
    async def test_v21_database_gains_lot_corrections(self, tmp_path):
        settings = MagicMock()
        settings.db_path = str(tmp_path / "old.db")
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            await db._get_db().execute("DROP TABLE lot_corrections")
            await db._get_db().execute("UPDATE schema_version SET version = 21")
            await db._get_db().commit()
            await db.close_db()
            await db.init_db()
            cur = await db._get_db().execute("SELECT version FROM schema_version")
            assert (await cur.fetchone())[0] == db._SCHEMA_VERSION  # later migrations run on top
            idx = await _rows("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'lot_corrections'")
            assert {r["name"] for r in idx} >= {"idx_lot_corrections_status", "idx_lot_corrections_pin",
                                                "idx_lot_corrections_anon", "idx_lot_corrections_ip"}
            await db.close_db()

    async def test_prune_drops_old_correction_counters(self, store):
        conn = db._get_db()
        await conn.execute("INSERT INTO usage_counters (subject, period, used, updated_at) VALUES "
                           "('corr-anon:x', '2026-01-01', 1, 0), ('corr-ip:y', '2026-01-01', 1, 0)")
        await conn.commit()
        assert await quotas.prune() == 2


# ── Review (PR 4): the admin queue, verdicts, the export and retention ────────────────────────────────────────────

from backend.auth import require_admin  # noqa: E402

ADMIN = {"id": "admin_1", "email": "admin@example.com", "name": "Admin", "tier": "admin"}


@pytest.fixture
def as_admin(as_user):
    def _set(admin: dict | None = ADMIN) -> TestClient:
        c = as_user(None)
        if admin is None:
            def _deny():
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Admin access required")
            app.dependency_overrides[require_admin] = _deny
        else:
            app.dependency_overrides[require_admin] = lambda: admin
        return c
    return _set


async def _seed(as_user) -> dict[str, int]:
    """Three reports: A signed in on PIN, a visitor on PIN, A again on another lot."""
    ids = {}
    ids["a_pin"] = _send(as_user(A)).json()["id"]
    anon = as_user(None)
    anon.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor1"))
    with patch("backend.corrections.client_ip", return_value="203.0.113.7"):
        ids["anon_pin"] = _send(anon, {"pin": PIN, "kinds": ["area"], "area_dir": "high", "note": "Much bigger."}).json()["id"]
    ids["a_other"] = _send(as_user(A), pin=LOTS[0]).json()["id"]
    return ids


class TestQueue:
    async def test_admin_only(self, store, as_admin):
        c = as_admin(None)
        assert c.get("/api/admin/corrections").status_code == 403
        assert c.post("/api/admin/corrections/1/review", json={"action": "reject"}).status_code == 403
        assert c.get("/api/admin/corrections/export").status_code == 403

    async def test_lists_open_reports_signed_in_first_with_no_ids(self, store, as_user, as_admin):
        ids = await _seed(as_user)
        body = as_admin().get("/api/admin/corrections").json()
        assert body["total"] == 3
        order = [r["id"] for r in body["reports"]]
        assert order == [ids["a_pin"], ids["a_other"], ids["anon_pin"]]  # signed out sorts below signed in
        r = next(x for x in body["reports"] if x["id"] == ids["anon_pin"])
        assert r["signed_in"] is False and r["kinds"] == ["area"] and r["area_dir"] == "high" and r["note"] == "Much bigger."
        assert r["others_open"] == [ids["a_pin"]]
        assert r["shown"]["bldg_sqft"] == 2400.0 and r["now"]["bldg_sqft"] == 2400.0 and r["changed"] is False
        assert r["past"] == {"accepted": 0, "rejected": 0} and r["muted"] is False
        for x in body["reports"]:
            assert not {"user_id", "anon_id", "ip_hash", "reviewed_by"} & set(x)
        assert "203.0.113.7" not in json.dumps(body)

    async def test_changed_when_the_card_now_shows_another_figure(self, store, as_user, as_admin):
        _send(as_user(A))
        parcel_source.set_snapshot("v2", [DictParcel(PIN, {"bldg_sqft": 3600.0, "bldg_sqft_source": "footprint"})])
        [r] = as_admin().get("/api/admin/corrections").json()["reports"]
        assert r["changed"] is True and r["now"]["data_version"] == "v2" and r["shown"]["data_version"] == VERSION

    async def test_muted_reporter_sorts_last_and_past_counts_exclude_the_report_itself(self, store, as_user, as_admin):
        c = as_user(A)
        rejected = [_send(c, pin=p).json()["id"] for p in LOTS[:3]]
        admin = as_admin()
        for i in rejected:
            assert admin.post(f"/api/admin/corrections/{i}/review", json={"action": "reject", "reason": "Street View shows 2"}).status_code == 200
        muted = _send(as_user(A), pin=LOTS[3]).json()["id"]
        anon = as_user(None)
        anon.cookies.set(quotas.ANON_COOKIE, quotas.sign_anon("visitor1"))
        first = _send(anon, pin=LOTS[4]).json()["id"]
        reports = as_admin().get("/api/admin/corrections").json()["reports"]
        assert [r["id"] for r in reports] == [first, muted]
        assert reports[1]["muted"] is True and reports[1]["past"] == {"accepted": 0, "rejected": 3}
        done = as_admin().get("/api/admin/corrections?status=rejected").json()["reports"]
        assert len(done) == 3 and all(r["past"]["rejected"] == 2 for r in done)
        assert done[0]["review_note"] == "Street View shows 2"

    async def test_unknown_status_is_422(self, store, as_admin):
        assert as_admin().get("/api/admin/corrections?status=open").status_code == 422


class TestReview:
    async def test_accept_records_what_applies_and_clears_the_ip_hash(self, store, as_user, as_admin):
        ids = await _seed(as_user)
        r = as_admin().post(f"/api/admin/corrections/{ids['anon_pin']}/review",
                            json={"action": "accept", "apply": "stories", "stories": 4, "reason": "4 stories on Street View"})
        assert r.status_code == 200 and r.json() == {"id": ids["anon_pin"], "status": "accepted", "applied": {"stories": 4}}
        [row] = await _rows("SELECT * FROM lot_corrections WHERE id = ?", (ids["anon_pin"],))
        assert row["status"] == "accepted" and row["reviewed_by"] == "admin_1" and row["reviewed_at"] > 0
        assert row["ip_hash"] is None and row["anon_id"] == "visitor1" and json.loads(row["applied"]) == {"stories": 4}
        assert row["review_note"] == "4 stories on Street View"

    async def test_accept_empty_or_nothing_and_reject_and_duplicate(self, store, as_user, as_admin):
        ids = await _seed(as_user)
        admin = as_admin()
        assert admin.post(f"/api/admin/corrections/{ids['a_pin']}/review", json={"action": "accept", "apply": "none"}).json()["applied"] == {}
        assert admin.post(f"/api/admin/corrections/{ids['a_other']}/review", json={"action": "accept", "apply": "empty"}).json()["applied"] == {"empty": True}
        assert admin.post(f"/api/admin/corrections/{ids['anon_pin']}/review", json={"action": "duplicate", "reason": "  "}).json()["status"] == "duplicate"
        statuses = {r["id"]: (r["status"], r["review_note"]) for r in await _rows()}
        assert statuses[ids["anon_pin"]] == ("duplicate", None)

    async def test_only_an_open_report_and_404(self, store, as_user, as_admin):
        ids = await _seed(as_user)
        admin = as_admin()
        assert admin.post(f"/api/admin/corrections/{ids['a_pin']}/review", json={"action": "reject"}).status_code == 200
        r = admin.post(f"/api/admin/corrections/{ids['a_pin']}/review", json={"action": "accept", "apply": "none"})
        assert r.status_code == 409 and r.json()["detail"] == "already rejected"
        assert admin.post("/api/admin/corrections/9999/review", json={"action": "reject"}).status_code == 404

    @pytest.mark.parametrize("body", [
        {"action": "accept"},
        {"action": "accept", "apply": "stories"},
        {"action": "accept", "apply": "stories", "stories": 0},
        {"action": "accept", "apply": "empty", "stories": 3},
        {"action": "reject", "apply": "none"},
        {"action": "reject", "stories": 3},
        {"action": "approve"},
        {"action": "reject", "reason": "x" * 201},
        {"action": "reject", "status": "accepted"},
    ])
    async def test_review_body_rules(self, store, as_user, as_admin, body):
        ids = await _seed(as_user)
        assert as_admin().post(f"/api/admin/corrections/{ids['a_pin']}/review", json=body).status_code == 422

    async def test_review_logs_only_the_action(self, store, as_user, as_admin, caplog):
        ids = await _seed(as_user)
        with caplog.at_level(logging.INFO, logger="backend.corrections"):
            as_admin().post(f"/api/admin/corrections/{ids['a_pin']}/review", json={"action": "reject", "reason": "secret reason"})
        lines = [r.getMessage() for r in caplog.records if r.name == "backend.corrections"]
        assert lines == ["correction_reviewed action=reject"]


class TestExport:
    async def test_merges_accepted_reports_into_the_committed_file(self, store, as_user, as_admin, tmp_path):
        committed = tmp_path / "user_corrections.json"
        committed.write_text(json.dumps({"1700000000": {"stories": 2, "empty": False, "reviewed": "2026-11-01", "report_ids": [1], "what": "kept"}}))
        ids = await _seed(as_user)
        admin = as_admin()
        admin.post(f"/api/admin/corrections/{ids['a_pin']}/review", json={"action": "accept", "apply": "stories", "stories": 3})
        admin.post(f"/api/admin/corrections/{ids['anon_pin']}/review", json={"action": "accept", "apply": "stories", "stories": 4, "reason": "Four floors"})
        admin.post(f"/api/admin/corrections/{ids['a_other']}/review", json={"action": "accept", "apply": "none"})
        with patch("backend.corrections.COMMITTED_FILE", committed):
            body = admin.get("/api/admin/corrections/export").json()
        content = json.loads(body["content"])
        assert content["1700000000"]["what"] == "kept"  # never dropped by the export
        assert content[PIN10] == {"stories": 4, "empty": False, "reviewed": content[PIN10]["reviewed"],
                                  "report_ids": sorted([ids["a_pin"], ids["anon_pin"]]), "what": "Four floors"}
        assert LOTS[0] not in content  # accepted as a case for the Assessor: nothing applied
        assert body["entries"] == 2 and body["new_reports"] == 2
        assert body["diff"].startswith("--- a/backend/discovery/user_corrections.json")
        assert f'+  "{PIN10}": {{' in body["diff"]
        assert json.loads(committed.read_text()) == {"1700000000": {"stories": 2, "empty": False, "reviewed": "2026-11-01", "report_ids": [1], "what": "kept"}}

    async def test_no_committed_file_yet(self, store, as_user, as_admin, tmp_path):
        ids = await _seed(as_user)
        as_admin().post(f"/api/admin/corrections/{ids['a_other']}/review", json={"action": "accept", "apply": "empty"})
        with patch("backend.corrections.COMMITTED_FILE", tmp_path / "missing.json"):
            body = as_admin().get("/api/admin/corrections/export").json()
        assert json.loads(body["content"]) == {LOTS[0]: {"stories": None, "empty": True, "reviewed": json.loads(body["content"])[LOTS[0]]["reviewed"],
                                                         "report_ids": [ids["a_other"]], "what": "no building"}}
        assert not (tmp_path / "missing.json").exists()


class TestRetention:
    async def test_signed_out_reports_go_180_days_after_review(self, store, as_user, as_admin):
        ids = await _seed(as_user)
        admin = as_admin()
        for i in ids.values():
            admin.post(f"/api/admin/corrections/{i}/review", json={"action": "reject"})
        old = int(time.time() * 1000) - 181 * 86_400_000
        await db._get_db().execute("UPDATE lot_corrections SET reviewed_at = ?", (old,))
        await db._get_db().commit()
        body = admin.get("/api/admin/corrections?status=all").json()
        assert body["pruned"] == 1
        assert {r["signed_in"] for r in body["reports"]} == {True}

    async def test_open_and_recent_reports_stay(self, store, as_user):
        await _seed(as_user)
        assert await corrections.prune_reviewed() == 0
        assert len(await _rows()) == 3


class TestMigrationV23:
    async def test_v22_database_gains_applied(self, tmp_path):
        settings = MagicMock()
        settings.db_path = str(tmp_path / "old.db")
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            await db._get_db().execute("ALTER TABLE lot_corrections DROP COLUMN applied")
            await db._get_db().execute("UPDATE schema_version SET version = 22")
            await db._get_db().commit()
            await db.close_db()
            await db.init_db()
            cols = {r["name"] for r in await _rows("PRAGMA table_info(lot_corrections)")}
            assert "applied" in cols
            await db.close_db()
