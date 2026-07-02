"""Account deletion + purchase history (settings page backend).

The deletion contract: Stripe cancellation runs FIRST and aborts on failure
(never orphan a live subscription behind a deleted account); conversations
cascade messages/uploads/shares and their files on disk; refresh tokens die
with the user row; report_purchases rows survive as tombstones (user_id SET
NULL — schema v12); legacy user_id IS NULL rows are shared, not the user's,
and stay untouched.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
import stripe
from fastapi.testclient import TestClient

from backend import auth, db
from backend.main import app
from backend.payments import cancel_user_subscription

CSRF_TOKEN = "csrf-test"
CSRF_HEADERS = {"x-csrf-token": CSRF_TOKEN}


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Fresh SQLite database + upload dir for each test."""
    mock_settings = MagicMock()
    mock_settings.db_path = tmp_path / "test.db"
    mock_settings.upload_dir = tmp_path / "uploads"
    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield mock_settings
        await db.close_db()


@pytest.fixture
def _auth_enabled():
    settings = MagicMock()
    settings.google_client_id = "test-client-id"
    settings.google_client_secret = "test-secret"
    settings.jwt_secret = "test-jwt-secret-key-for-testing"
    settings.jwt_access_token_ttl = 900
    settings.jwt_refresh_token_ttl = 604800
    settings.auth_cookie_secure = False
    settings.frontend_url = "http://localhost:5173"
    with patch("backend.auth.get_settings", return_value=settings):
        yield settings


@pytest.fixture
def _auth_disabled():
    settings = MagicMock()
    settings.google_client_id = ""
    settings.jwt_secret = ""
    settings.jwt_access_token_ttl = 900
    settings.jwt_refresh_token_ttl = 604800
    settings.auth_cookie_secure = False
    settings.frontend_url = "http://localhost:5173"
    with patch("backend.auth.get_settings", return_value=settings):
        yield settings


def _make_client(user_id: str | None = None, email: str = "", tier: str = "free") -> TestClient:
    client = TestClient(app)
    client.cookies.set("csrf_token", CSRF_TOKEN)
    if user_id is not None:
        client.cookies.set("access_token", auth.create_access_token(user_id, email, tier))
    return client


async def _completed_purchase(
    user_id: str, session_id: str, pin: str | None = None,
) -> None:
    await db.save_report_purchase(
        user_id=user_id, stripe_session_id=session_id,
        address="1601 N Milwaukee Ave", lat=41.9103, lon=-87.6773, pin=pin,
    )
    await db.complete_report_purchase(session_id, "pi_test")


async def _count(sql: str, *params) -> int:
    cur = await db._get_db().execute(sql, params)
    return (await cur.fetchone())[0]


# ---------------------------------------------------------------------------
# GET /api/me/purchases
# ---------------------------------------------------------------------------

class TestPurchasesEndpoint:
    def test_requires_auth(self, _auth_enabled, test_db):
        resp = _make_client().get("/api/me/purchases")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_lists_completed_purchases_with_pin(self, _auth_enabled, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await _completed_purchase("u1", "cs_1", pin="14283190070000")
        # Pending purchases (abandoned checkouts) must not appear.
        await db.save_report_purchase(
            user_id="u1", stripe_session_id="cs_2",
            address="642 W Belden Ave", lat=41.9236, lon=-87.6453,
        )

        resp = _make_client("u1", "a@b.com").get("/api/me/purchases")
        assert resp.status_code == 200
        purchases = resp.json()["purchases"]
        assert len(purchases) == 1
        assert purchases[0]["pin"] == "14283190070000"
        assert purchases[0]["address"] == "1601 N Milwaukee Ave"
        assert purchases[0]["amount_cents"] == 2500
        assert purchases[0]["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_only_own_purchases(self, _auth_enabled, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.upsert_user("u2", "c@d.com", "Bob", None, "g2")
        await _completed_purchase("u2", "cs_other")

        resp = _make_client("u1", "a@b.com").get("/api/me/purchases")
        assert resp.json()["purchases"] == []


# ---------------------------------------------------------------------------
# db.delete_user_account cascade
# ---------------------------------------------------------------------------

class TestDeleteUserAccountDb:
    @pytest.mark.asyncio
    async def test_full_cascade(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")

        await db.create_conversation("c1", "My research", user_id="u1")
        await db.save_messages("c1", [
            {"role": "user", "content": "what can I build here?"},
            {"role": "assistant", "content": "RS-3 allows..."},
        ])
        await db.create_share_token("c1", "u1")

        upload_dir = test_db.upload_dir / "c1"
        upload_dir.mkdir(parents=True)
        upload_file = upload_dir / "up1.png"
        upload_file.write_bytes(b"fake png")
        await db.save_upload("up1", "c1", "survey.png", "image/png", 8, str(upload_file))

        await db.save_refresh_token(
            user_id="u1", token_hash="hash1", expires_at=9_999_999_999_999,
        )
        await db.save_events([{
            "session_id": "s1", "visitor_id": "v1", "user_id": "u1",
            "event_name": "page_view",
        }])
        # request_logs / llm_calls user_id is written by the chat pipeline, not
        # the save helpers — insert directly to exercise the cleanup clauses.
        conn = db._get_db()
        await conn.execute(
            "INSERT INTO request_logs (request_group, user_message, total_duration_ms,"
            " user_id, created_at) VALUES ('rg1', 'secret question', 100, 'u1', 1)"
        )
        await conn.execute(
            "INSERT INTO llm_calls (request_group, phase, model, input_tokens,"
            " output_tokens, duration_ms, user_id, created_at)"
            " VALUES ('rg1', 'router', 'm', 1, 1, 5, 'u1', 1)"
        )
        await conn.commit()
        await _completed_purchase("u1", "cs_1", pin="14283190070000")

        result = await db.delete_user_account("u1")
        assert result["conversations_deleted"] == 1

        assert await db.get_user_by_id("u1") is None
        assert await _count("SELECT COUNT(*) FROM conversations") == 0
        assert await _count("SELECT COUNT(*) FROM messages") == 0
        assert await _count("SELECT COUNT(*) FROM uploads") == 0
        assert await _count("SELECT COUNT(*) FROM conversation_shares") == 0
        assert await _count("SELECT COUNT(*) FROM refresh_tokens") == 0
        assert await _count("SELECT COUNT(*) FROM events WHERE user_id = 'u1'") == 0
        assert await _count("SELECT COUNT(*) FROM request_logs WHERE user_id = 'u1'") == 0
        assert not upload_file.exists()

        # Telemetry rows survive unlinked; purchase rows survive tombstoned.
        assert await _count("SELECT COUNT(*) FROM llm_calls") == 1
        assert await _count("SELECT COUNT(*) FROM llm_calls WHERE user_id IS NULL") == 1
        assert await _count("SELECT COUNT(*) FROM report_purchases") == 1
        assert await _count(
            "SELECT COUNT(*) FROM report_purchases WHERE user_id IS NULL"
        ) == 1

    @pytest.mark.asyncio
    async def test_other_users_and_legacy_rows_untouched(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.upsert_user("u2", "c@d.com", "Bob", None, "g2")
        await db.create_conversation("c1", "Alice's", user_id="u1")
        await db.create_conversation("c2", "Bob's", user_id="u2")
        await db.create_conversation("c3", "Legacy anon", user_id=None)
        await _completed_purchase("u2", "cs_bob")

        await db.delete_user_account("u1")

        assert await db.get_user_by_id("u2") is not None
        cur = await db._get_db().execute("SELECT id FROM conversations ORDER BY id")
        assert [r["id"] for r in await cur.fetchall()] == ["c2", "c3"]
        purchases = await db.get_user_report_purchases("u2")
        assert len(purchases) == 1


# ---------------------------------------------------------------------------
# payments.cancel_user_subscription
# ---------------------------------------------------------------------------

class TestCancelUserSubscription:
    @pytest.mark.asyncio
    async def test_no_subscription_is_noop(self):
        with patch("backend.payments.stripe.Subscription.cancel") as cancel:
            await cancel_user_subscription({"id": "u1", "stripe_subscription_id": None})
        cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancels_active_subscription(self):
        with patch("backend.payments.stripe.Subscription.cancel") as cancel:
            await cancel_user_subscription(
                {"id": "u1", "stripe_subscription_id": "sub_1"}
            )
        cancel.assert_called_once_with("sub_1")

    @pytest.mark.asyncio
    async def test_already_canceled_counts_as_success(self):
        err = stripe.InvalidRequestError("No such subscription", param=None)
        with patch("backend.payments.stripe.Subscription.cancel", side_effect=err):
            await cancel_user_subscription(
                {"id": "u1", "stripe_subscription_id": "sub_1"}
            )  # must not raise

    @pytest.mark.asyncio
    async def test_stripe_failure_raises_502(self):
        from fastapi import HTTPException
        err = stripe.APIConnectionError("stripe down")
        with patch("backend.payments.stripe.Subscription.cancel", side_effect=err):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_user_subscription(
                    {"id": "u1", "stripe_subscription_id": "sub_1"}
                )
        assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# DELETE /api/me
# ---------------------------------------------------------------------------

class TestDeleteAccountEndpoint:
    def test_requires_auth(self, _auth_enabled, test_db):
        resp = _make_client().delete("/api/me", headers=CSRF_HEADERS)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_blocked_in_dev_mode(self, _auth_disabled, test_db):
        resp = TestClient(app).delete("/api/me")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_failure_aborts_deletion(self, _auth_enabled, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_stripe("u1", "cus_1", "sub_1")
        await db.create_conversation("c1", "Keep me", user_id="u1")

        err = stripe.APIConnectionError("stripe down")
        with patch("backend.payments.stripe.Subscription.cancel", side_effect=err):
            resp = _make_client("u1", "a@b.com", "premium").delete(
                "/api/me", headers=CSRF_HEADERS
            )

        assert resp.status_code == 502
        assert await db.get_user_by_id("u1") is not None
        assert await _count("SELECT COUNT(*) FROM conversations") == 1

    @pytest.mark.asyncio
    async def test_success_cancels_then_deletes(self, _auth_enabled, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_stripe("u1", "cus_1", "sub_1")
        await db.update_user_tier("u1", "premium")
        await db.create_conversation("c1", "Gone", user_id="u1")

        with patch("backend.payments.stripe.Subscription.cancel") as cancel:
            resp = _make_client("u1", "a@b.com", "premium").delete(
                "/api/me", headers=CSRF_HEADERS
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        cancel.assert_called_once_with("sub_1")
        assert await db.get_user_by_id("u1") is None
        assert await _count("SELECT COUNT(*) FROM conversations") == 0
        # Session cookies are cleared on the way out.
        set_cookie = ",".join(resp.headers.get_list("set-cookie"))
        assert "access_token=" in set_cookie

    @pytest.mark.asyncio
    async def test_free_user_no_stripe_call(self, _auth_enabled, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")

        with patch("backend.payments.stripe.Subscription.cancel") as cancel:
            resp = _make_client("u1", "a@b.com").delete("/api/me", headers=CSRF_HEADERS)

        assert resp.status_code == 200
        cancel.assert_not_called()
        assert await db.get_user_by_id("u1") is None


# ---------------------------------------------------------------------------
# Schema v12 migration
# ---------------------------------------------------------------------------

class TestMigrationV12:
    @pytest.mark.asyncio
    async def test_purchases_survive_user_delete(self, test_db):
        """The rebuilt table's SET NULL FK is what makes deletion safe."""
        cur = await db._get_db().execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='report_purchases'"
        )
        sql = (await cur.fetchone())[0]
        assert "ON DELETE SET NULL" in sql
        assert "ON DELETE CASCADE" not in sql

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await _completed_purchase("u1", "cs_1", pin="123")
        await db._migrate_v12(db._get_db())  # re-run: guard should no-op
        purchases = await db.get_user_report_purchases("u1")
        assert len(purchases) == 1
