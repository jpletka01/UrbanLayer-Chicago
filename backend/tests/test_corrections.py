"""Suggest a correction (decision Item 129, PR 1): the body, who sent it, the limits, one open report per lot,
account deletion, and what is (and isn't) stored or logged.

Nothing here touches the network or a model: the Discovery index is an in-memory snapshot and the database a
temporary file.
"""

from __future__ import annotations

import json
import logging
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
                                            "room_sqft": 1350.0, "data_version": VERSION}

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
            assert (await cur.fetchone())[0] == 22
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
