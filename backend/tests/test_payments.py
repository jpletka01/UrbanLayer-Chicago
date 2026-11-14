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
    settings.microsoft_client_id = ""
    settings.apple_client_id = ""
    settings.auth_dev_login = False
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


class TestFunnelEvents:
    """The money events are written only by the Stripe webhook (see test_billing.py)."""

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
            "discovery_search", "discovery_start_choice", "signup_completed",
        ):
            assert name in _VALID_EVENT_NAMES


class TestEngagementFunnel:
    """Funnel + channel rollups in get_engagement_stats (growth instrumentation)."""

    @staticmethod
    def _ev(name: str, visitor: str, data: dict | None = None) -> dict:
        return {
            "session_id": f"s-{visitor}",
            "visitor_id": visitor,
            "user_id": None,
            "event_name": name,
            "event_data": data,
            "page": "/",
            "address": None,
        }

    @pytest.mark.asyncio
    async def test_funnel_counts_distinct_visitors_per_step(self, test_db):
        ev = self._ev
        await db.save_events([
            # v1 goes all the way to purchase
            ev("visit_start", "v1"),
            ev("hero_address_submit", "v1"),
            ev("scorecard_view", "v1"),
            ev("investigate_click", "v1"),
            ev("checkout_started", "v1"),
            ev("purchase_completed", "v1"),
            # v2 views a scorecard twice (distinct count must be 1) and stops
            ev("visit_start", "v2"),
            ev("hero_address_submit", "v2"),
            ev("scorecard_view", "v2"),
            ev("scorecard_view", "v2"),
            # v3 only lands
            ev("visit_start", "v3"),
        ])

        stats = await db.get_engagement_stats("all")
        funnel = {s["step"]: s["visitors"] for s in stats["funnel"]}
        assert funnel["visited"] == 3
        assert funnel["address_entered"] == 2
        assert funnel["scorecard_viewed"] == 2
        assert funnel["engaged"] == 1
        assert funnel["checkout_started"] == 1
        assert funnel["purchased"] == 1
        # steps stay in funnel order
        assert [s["step"] for s in stats["funnel"]] == [
            "visited", "address_entered", "scorecard_viewed",
            "engaged", "checkout_started", "purchased",
        ]

    @pytest.mark.asyncio
    async def test_channels_classify_utm_referrer_direct(self, test_db):
        ev = self._ev
        await db.save_events([
            ev("visit_start", "v1", {"utm_source": "hn", "referrer": "https://news.ycombinator.com/"}),
            ev("visit_start", "v2", {"referrer": "https://www.google.com/search?q=x"}),
            ev("visit_start", "v3", {"referrer": None}),
            ev("visit_start", "v4", {}),
        ])

        stats = await db.get_engagement_stats("all")
        assert stats["channels"]["utm:hn"] == 1  # utm wins over referrer
        assert stats["channels"]["www.google.com"] == 1
        assert stats["channels"]["direct"] == 2

    @pytest.mark.asyncio
    async def test_channels_fall_back_to_first_touch(self, test_db):
        stats_before = await db.get_engagement_stats("all")
        assert stats_before["channels"] == {}

        await db.save_events([
            self._ev("visit_start", "v1", {
                "referrer": None,
                "first_touch": {"utm_source": "newsletter", "referrer": None},
            }),
        ])
        stats = await db.get_engagement_stats("all")
        assert stats["channels"] == {"utm:newsletter": 1}


class TestNewsletter:
    """Subscribers table (schema v13) + /api/newsletter endpoint."""

    @pytest.mark.asyncio
    async def test_add_subscriber_dedupes_case_insensitive(self, test_db):
        assert await db.add_subscriber("A@B.com", "footer") is True
        assert await db.add_subscriber("a@b.com", "scorecard") is False
        conn = db._get_db()
        cur = await conn.execute("SELECT email, source FROM subscribers")
        rows = [dict(r) for r in await cur.fetchall()]
        assert rows == [{"email": "a@b.com", "source": "footer"}]

    @pytest.mark.asyncio
    async def test_schema_v13_creates_subscribers(self, test_db):
        conn = db._get_db()
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='subscribers'"
        )
        assert await cur.fetchone() is not None

    def test_newsletter_endpoint_validates_email(self):
        # No context manager: entering TestClient runs the app lifespan
        # (real db init + model preload) and poisons global state for the
        # rest of the suite — match the TestCheckoutReportEndpoint pattern.
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        with patch("backend.main.db.add_subscriber", new=AsyncMock(return_value=True)) as mock_add:
            ok = client.post("/api/newsletter", json={"email": "x@y.com", "source": "footer"})
            assert ok.status_code == 200
            assert ok.json() == {"ok": True, "added": True}
            mock_add.assert_awaited_once_with("x@y.com", "footer")

            bad = client.post("/api/newsletter", json={"email": "not-an-email"})
            assert bad.status_code == 400
            empty = client.post("/api/newsletter", json={})
            assert empty.status_code == 400
