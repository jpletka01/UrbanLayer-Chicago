"""Tests for the payments module: tier gating, DB helpers, and Stripe integration.

Integration tests hit real Stripe test-mode APIs (free, no cost).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
