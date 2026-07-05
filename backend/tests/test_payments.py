"""Tests for the payments module: tier gating, DB helpers, and Stripe integration.

Integration tests hit real Stripe test-mode APIs (free, no cost).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend import auth, db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    mock_settings = MagicMock()
    mock_settings.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield
        await db.close_db()


@pytest.fixture
def _auth_settings():
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


# ---------------------------------------------------------------------------
# DB helper functions
# ---------------------------------------------------------------------------

class TestStripeDBHelpers:
    @pytest.mark.asyncio
    async def test_update_user_tier(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")
        assert user["tier"] == "free"

        await db.update_user_tier("u1", "premium")
        user = await db.get_user_by_id("u1")
        assert user["tier"] == "premium"

    @pytest.mark.asyncio
    async def test_update_user_stripe(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")

        await db.update_user_stripe("u1", "cus_test123", "sub_test456")
        user = await db.get_user_by_id("u1")
        assert user["stripe_customer_id"] == "cus_test123"
        assert user["stripe_subscription_id"] == "sub_test456"

    @pytest.mark.asyncio
    async def test_update_user_stripe_clear_subscription(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_stripe("u1", "cus_test123", "sub_test456")
        await db.update_user_stripe("u1", "cus_test123", None)

        user = await db.get_user_by_id("u1")
        assert user["stripe_customer_id"] == "cus_test123"
        assert user["stripe_subscription_id"] is None

    @pytest.mark.asyncio
    async def test_get_user_by_stripe_customer(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_stripe("u1", "cus_test123", "sub_test456")

        user = await db.get_user_by_stripe_customer("cus_test123")
        assert user is not None
        assert user["id"] == "u1"

    @pytest.mark.asyncio
    async def test_get_user_by_stripe_customer_not_found(self, test_db):
        user = await db.get_user_by_stripe_customer("cus_nonexistent")
        assert user is None

    @pytest.mark.asyncio
    async def test_schema_v7_adds_stripe_columns(self, test_db):
        user = await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        assert "stripe_customer_id" in user
        assert "stripe_subscription_id" in user


# ---------------------------------------------------------------------------
# require_tier dependency
# ---------------------------------------------------------------------------

class TestRequireTier:
    @pytest.mark.asyncio
    async def test_free_user_blocked_from_premium(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        token = auth.create_access_token("u1", "a@b.com", "free")
        request = MagicMock()
        request.cookies = {"access_token": token}

        check = auth.require_tier("premium")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await check(request)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "upgrade_required"

    @pytest.mark.asyncio
    async def test_premium_user_passes_premium_gate(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_tier("u1", "premium")
        token = auth.create_access_token("u1", "a@b.com", "premium")
        request = MagicMock()
        request.cookies = {"access_token": token}

        check = auth.require_tier("premium")
        user = await check(request)
        assert user["tier"] == "premium"

    @pytest.mark.asyncio
    async def test_admin_passes_premium_gate(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.update_user_tier("u1", "admin")
        token = auth.create_access_token("u1", "a@b.com", "admin")
        request = MagicMock()
        request.cookies = {"access_token": token}

        check = auth.require_tier("premium")
        user = await check(request)
        assert user["tier"] == "admin"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, _auth_settings):
        request = MagicMock()
        request.cookies = {}

        check = auth.require_tier("premium")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await check(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# PIN-keyed report purchases (SelectedParcel Phase 2 — money binds to PIN)
# ---------------------------------------------------------------------------

CONTROL_PIN = "14331030110000"  # 642 W Belden Ave (QA control parcel)
EX_PIN = "14283190070000"       # exempt QA subject
CONTROL_LAT, CONTROL_LON = 41.9239, -87.6443


class TestHasPurchasedReportPin:
    @pytest.mark.asyncio
    async def test_migration_v11_adds_pin_column_and_index(self, test_db):
        conn = db._get_db()
        cur = await conn.execute("PRAGMA table_info(report_purchases)")
        cols = {row[1] for row in await cur.fetchall()}
        assert "pin" in cols
        cur = await conn.execute("PRAGMA index_list(report_purchases)")
        names = {row[1] for row in await cur.fetchall()}
        assert "idx_rp_user_pin" in names

    @pytest.mark.asyncio
    async def test_pin_purchase_grants_access_despite_coordinate_drift(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.save_report_purchase(
            "u1", "cs_pin", "642 W Belden Ave",
            CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN,
        )
        await db.complete_report_purchase("cs_pin")

        # Coordinates drifted far outside the 4-decimal cell — PIN still matches.
        assert await db.has_purchased_report(
            "u1", CONTROL_LAT + 0.01, CONTROL_LON + 0.01, pin=CONTROL_PIN
        )

    @pytest.mark.asyncio
    async def test_legacy_pinless_row_matches_by_coords(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.save_report_purchase(
            "u1", "cs_legacy", "642 W Belden Ave", CONTROL_LAT, CONTROL_LON,
        )
        await db.complete_report_purchase("cs_legacy")

        # Legacy row (pin NULL) stays entitled via the coordinate clause,
        # whether or not the access check now resolves a pin.
        assert await db.has_purchased_report("u1", CONTROL_LAT, CONTROL_LON)
        assert await db.has_purchased_report(
            "u1", CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN
        )

    @pytest.mark.asyncio
    async def test_no_access_for_different_parcel(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.save_report_purchase(
            "u1", "cs_other", "642 W Belden Ave",
            CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN,
        )
        await db.complete_report_purchase("cs_other")

        assert not await db.has_purchased_report(
            "u1", CONTROL_LAT + 0.01, CONTROL_LON + 0.01, pin=EX_PIN
        )

    @pytest.mark.asyncio
    async def test_pending_purchase_grants_nothing(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await db.save_report_purchase(
            "u1", "cs_pending", "642 W Belden Ave",
            CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN,
        )
        assert not await db.has_purchased_report(
            "u1", CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN
        )


class TestCreateReportCheckoutSessionPin:
    @pytest.fixture
    def _payment_settings(self):
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_x"
        settings.stripe_price_id_report = "price_x"
        settings.frontend_url = "http://localhost:5173"
        with patch("backend.payments.get_settings", return_value=settings):
            yield settings

    @pytest.mark.asyncio
    async def test_pin_in_metadata_urls_and_purchase_row(self, test_db, _payment_settings):
        from backend.payments import create_report_checkout_session

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")

        session = MagicMock(id="cs_test_pin", url="https://checkout.stripe.com/c/x")
        with patch("stripe.checkout.Session.create", return_value=session) as mock_create:
            url = await create_report_checkout_session(
                user, "642 W Belden Ave", CONTROL_LAT, CONTROL_LON, pin=CONTROL_PIN,
            )

        assert url == session.url
        params = mock_create.call_args.kwargs
        assert params["metadata"]["pin"] == CONTROL_PIN
        assert f"?pin={CONTROL_PIN}&report_purchased=1" in params["success_url"]
        assert f"?pin={CONTROL_PIN}" in params["cancel_url"]

        row = await db.complete_report_purchase("cs_test_pin")
        assert row is not None
        assert row["pin"] == CONTROL_PIN

    @pytest.mark.asyncio
    async def test_pinless_checkout_falls_back_to_address_urls(self, test_db, _payment_settings):
        from backend.payments import create_report_checkout_session

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")

        session = MagicMock(id="cs_test_addr", url="https://checkout.stripe.com/c/y")
        with patch("stripe.checkout.Session.create", return_value=session) as mock_create:
            await create_report_checkout_session(
                user, "642 W Belden Ave", CONTROL_LAT, CONTROL_LON,
            )

        params = mock_create.call_args.kwargs
        assert "pin" not in params["metadata"]
        assert "address=642+W+Belden+Ave&report_purchased=1" in params["success_url"]

        row = await db.complete_report_purchase("cs_test_addr")
        assert row is not None
        assert row["pin"] is None


class TestCheckoutReportEndpoint:
    FREE_USER = {
        "id": "u1", "email": "a@b.com", "name": "Alice",
        "tier": "free", "stripe_customer_id": None,
    }

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        app.dependency_overrides[auth.require_auth] = lambda: self.FREE_USER
        with patch("backend.auth._auth_enabled", return_value=False):
            yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def _resolved_control(self):
        from backend.main import ResolvedLocation
        return ResolvedLocation(
            CONTROL_LAT, CONTROL_LON, "642 W BELDEN AVE",
            CONTROL_PIN, "authoritative",
        )

    def test_checkout_with_pin_only_body(self, client, _resolved_control):
        with patch("backend.main._resolve_location", new_callable=AsyncMock) as mock_rl, \
             patch("backend.payments.create_report_checkout_session",
                   new_callable=AsyncMock) as mock_create:
            mock_rl.return_value = _resolved_control
            mock_create.return_value = "https://checkout.stripe.com/c/z"
            resp = client.post("/api/checkout/report", json={"pin": CONTROL_PIN})

        assert resp.status_code == 200
        assert resp.json() == {"url": "https://checkout.stripe.com/c/z"}
        assert mock_rl.call_args.kwargs == {"pin": CONTROL_PIN}
        assert mock_create.call_args.kwargs["pin"] == CONTROL_PIN
        args = mock_create.call_args.args
        assert args[1:] == ("642 W BELDEN AVE", CONTROL_LAT, CONTROL_LON)

    def test_checkout_with_full_body_skips_resolution(self, client):
        with patch("backend.main._resolve_location", new_callable=AsyncMock) as mock_rl, \
             patch("backend.payments.create_report_checkout_session",
                   new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "https://checkout.stripe.com/c/z"
            resp = client.post("/api/checkout/report", json={
                "pin": CONTROL_PIN, "address": "642 W Belden Ave",
                "lat": CONTROL_LAT, "lon": CONTROL_LON,
            })

        assert resp.status_code == 200
        mock_rl.assert_not_called()
        assert mock_create.call_args.kwargs["pin"] == CONTROL_PIN

    def test_checkout_legacy_body_without_pin(self, client):
        with patch("backend.payments.create_report_checkout_session",
                   new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "https://checkout.stripe.com/c/z"
            resp = client.post("/api/checkout/report", json={
                "address": "642 W Belden Ave",
                "lat": CONTROL_LAT, "lon": CONTROL_LON,
            })

        assert resp.status_code == 200
        assert mock_create.call_args.kwargs["pin"] is None

    def test_checkout_rejects_empty_identity(self, client):
        resp = client.post("/api/checkout/report", json={})
        assert resp.status_code == 400

    def test_report_access_passes_resolved_pin(self, client, _resolved_control):
        with patch("backend.main._resolve_location", new_callable=AsyncMock) as mock_rl, \
             patch("backend.main.db.has_purchased_report",
                   new_callable=AsyncMock) as mock_has:
            mock_rl.return_value = _resolved_control
            mock_has.return_value = True
            resp = client.get(f"/api/report/access?pin={CONTROL_PIN}")

        assert resp.status_code == 200
        assert resp.json() == {"has_access": True, "reason": "purchased"}
        assert mock_has.call_args.args == ("u1", CONTROL_LAT, CONTROL_LON)
        assert mock_has.call_args.kwargs == {"pin": CONTROL_PIN}


# ---------------------------------------------------------------------------
# Stripe integration tests (test mode, free)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestStripeIntegration:
    @pytest.fixture
    def _stripe_settings(self):
        from backend.config import get_settings
        s = get_settings()
        if not s.stripe_secret_key:
            pytest.skip("STRIPE_SECRET_KEY not set")
        return s

    @pytest.mark.asyncio
    async def test_create_checkout_session(self, _stripe_settings, test_db):
        from backend.payments import create_checkout_session

        settings = _stripe_settings
        if not settings.stripe_price_id_pro_monthly:
            pytest.skip("STRIPE_PRICE_ID_PRO_MONTHLY not set")

        await db.upsert_user("u1", "test@example.com", "Test", None, "g1")
        user = await db.get_user_by_id("u1")

        url = await create_checkout_session(user)
        assert url is not None
        assert "checkout.stripe.com" in url

    @pytest.mark.asyncio
    async def test_get_subscription_status_free_user(self, _stripe_settings, test_db):
        from backend.payments import get_subscription_status

        await db.upsert_user("u1", "test@example.com", "Test", None, "g1")
        user = await db.get_user_by_id("u1")

        status = await get_subscription_status(user)
        assert status["tier"] == "free"
        assert status["subscription_active"] is False

    @pytest.mark.asyncio
    async def test_webhook_handler_checkout_completed(self, _stripe_settings, test_db):
        """Simulate a checkout.session.completed webhook event."""
        from backend import payments

        await db.upsert_user("u1", "test@example.com", "Test", None, "g1")

        # Simulate the internal handler directly (avoids needing real webhook signature)
        await payments._handle_checkout_completed({
            "metadata": {"user_id": "u1"},
            "customer": "cus_test_integration",
            "subscription": "sub_test_integration",
        })

        user = await db.get_user_by_id("u1")
        assert user["tier"] == "premium"
        assert user["stripe_customer_id"] == "cus_test_integration"
        assert user["stripe_subscription_id"] == "sub_test_integration"

    @pytest.mark.asyncio
    async def test_webhook_handler_subscription_deleted(self, _stripe_settings, test_db):
        """Simulate a subscription deletion event."""
        from backend import payments

        await db.upsert_user("u1", "test@example.com", "Test", None, "g1")
        await db.update_user_tier("u1", "premium")
        await db.update_user_stripe("u1", "cus_test_del", "sub_test_del")

        await payments._handle_subscription_deleted({
            "customer": "cus_test_del",
        })

        user = await db.get_user_by_id("u1")
        assert user["tier"] == "free"
        assert user["stripe_subscription_id"] is None


class TestFunnelEvents:
    """Server-side analytics events for purchases (growth instrumentation)."""

    @pytest.fixture
    def _payment_settings(self):
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_x"
        settings.stripe_price_id_report = "price_x"
        settings.stripe_price_id_pro_monthly = "price_pro"
        settings.frontend_url = "http://localhost:5173"
        with patch("backend.payments.get_settings", return_value=settings):
            yield settings

    async def _events_named(self, name: str) -> list[dict]:
        conn = db._get_db()
        cur = await conn.execute(
            "SELECT * FROM events WHERE event_name = ?", (name,)
        )
        return [dict(r) for r in await cur.fetchall()]

    @pytest.mark.asyncio
    async def test_visitor_id_rides_report_checkout_metadata(self, test_db, _payment_settings):
        from backend.payments import create_report_checkout_session

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")

        session = MagicMock(id="cs_vid", url="https://checkout.stripe.com/c/v")
        with patch("stripe.checkout.Session.create", return_value=session) as mock_create:
            await create_report_checkout_session(
                user, "642 W Belden Ave", 41.9236, -87.6439, visitor_id="vis-123",
            )
        assert mock_create.call_args.kwargs["metadata"]["visitor_id"] == "vis-123"

    @pytest.mark.asyncio
    async def test_visitor_id_rides_subscription_checkout_metadata(self, test_db, _payment_settings):
        from backend.payments import create_checkout_session

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")

        session = MagicMock(url="https://checkout.stripe.com/c/s")
        with patch("stripe.checkout.Session.create", return_value=session) as mock_create:
            await create_checkout_session(user, visitor_id="vis-456")
        assert mock_create.call_args.kwargs["metadata"]["visitor_id"] == "vis-456"

    @pytest.mark.asyncio
    async def test_report_purchase_webhook_writes_purchase_event(self, test_db, _payment_settings):
        from backend import payments
        from backend.payments import create_report_checkout_session

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")
        session = MagicMock(id="cs_evt", url="https://checkout.stripe.com/c/e")
        with patch("stripe.checkout.Session.create", return_value=session):
            await create_report_checkout_session(
                user, "642 W Belden Ave", 41.9236, -87.6439,
                pin="14331030110000", visitor_id="vis-789",
            )

        await payments._handle_report_purchase_completed({
            "id": "cs_evt",
            "payment_intent": "pi_x",
            "customer": "cus_x",
            "amount_total": 2500,
            "metadata": {
                "user_id": "u1",
                "purchase_type": "report",
                "address": "642 W Belden Ave",
                "pin": "14331030110000",
                "visitor_id": "vis-789",
            },
        })

        events = await self._events_named("purchase_completed")
        assert len(events) == 1
        ev = events[0]
        assert ev["visitor_id"] == "vis-789"
        assert ev["user_id"] == "u1"
        assert ev["address"] == "642 W Belden Ave"
        import json as json_mod
        data = json_mod.loads(ev["event_data"])
        assert data["purchase_type"] == "report"
        assert data["amount_total"] == 2500
        assert data["pin"] == "14331030110000"

    @pytest.mark.asyncio
    async def test_subscription_webhook_writes_subscription_event(self, test_db, _payment_settings):
        from backend import payments

        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        await payments._handle_checkout_completed({
            "metadata": {"user_id": "u1", "visitor_id": "vis-sub"},
            "customer": "cus_sub",
            "subscription": "sub_x",
            "amount_total": 9900,
        })

        events = await self._events_named("subscription_started")
        assert len(events) == 1
        assert events[0]["visitor_id"] == "vis-sub"
        assert events[0]["user_id"] == "u1"

    def test_money_events_not_client_ingestable(self):
        """The browser allowlist must never accept money events — the Stripe
        webhook is their only writer, so the funnel's purchase step can't be
        spoofed by a client."""
        from backend.main import _VALID_EVENT_NAMES

        assert "purchase_completed" not in _VALID_EVENT_NAMES
        assert "subscription_started" not in _VALID_EVENT_NAMES
        # ...and the new client-side funnel events ARE accepted.
        for name in (
            "visit_start", "scorecard_view", "checkout_started",
            "discovery_search", "signup_completed",
        ):
            assert name in _VALID_EVENT_NAMES
