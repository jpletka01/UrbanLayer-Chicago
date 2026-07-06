"""Voucher system: time-boxed complimentary premium for early adopters.

The contract: premium_until is a SEPARATE column from tier — Stripe webhooks
write tier and must never clobber a comp grant; expiry is implicit (the
effective-tier choke point in auth.get_current_user compares against now), so
there is no revocation job to forget. Redemption is attributable: one row per
(code, user), surfaced in the admin voucher list.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import auth, db
from backend import main as main_mod
from backend.main import app
from backend.payments import (
    _handle_subscription_deleted,
    get_subscription_status,
)

CSRF_TOKEN = "csrf-test"
CSRF_HEADERS = {"x-csrf-token": CSRF_TOKEN}

DAY_MS = 86_400_000


@pytest_asyncio.fixture
async def test_db(tmp_path):
    mock_settings = MagicMock()
    mock_settings.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield
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


@pytest.fixture(autouse=True)
def _clear_attempt_cap():
    main_mod._VOUCHER_ATTEMPTS.clear()
    yield
    main_mod._VOUCHER_ATTEMPTS.clear()


def _make_client(user_id: str | None = None, email: str = "", tier: str = "free") -> TestClient:
    client = TestClient(app)
    client.cookies.set("csrf_token", CSRF_TOKEN)
    if user_id is not None:
        client.cookies.set("access_token", auth.create_access_token(user_id, email, tier))
    return client


async def _user(user_id: str, email: str, tier: str = "free") -> dict:
    user = await db.upsert_user(user_id, email, "Test User", None, f"g-{user_id}")
    if tier != "free":
        await db.update_user_tier(user_id, tier)
    return user


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

class TestVoucherDb:
    @pytest.mark.asyncio
    async def test_create_and_get(self, test_db):
        await db.create_voucher("UL-TEST1234", "jane", 30, max_redemptions=2)
        v = await db.get_voucher("UL-TEST1234")
        assert v["label"] == "jane"
        assert v["duration_days"] == 30
        assert v["max_redemptions"] == 2
        assert v["disabled"] == 0

    @pytest.mark.asyncio
    async def test_redeem_sets_premium_until(self, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-CODE", None, 30)
        until = await db.redeem_voucher("UL-CODE", "u1")
        assert abs(until - (_now_ms() + 30 * DAY_MS)) < 5_000
        user = await db.get_user_by_id("u1")
        assert user["premium_until"] == until

    @pytest.mark.asyncio
    async def test_stacking_extends_from_existing_grant(self, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-ONE", None, 30)
        await db.create_voucher("UL-TWO", None, 10)
        first = await db.redeem_voucher("UL-ONE", "u1")
        second = await db.redeem_voucher("UL-TWO", "u1")
        assert abs(second - (first + 10 * DAY_MS)) < 5_000

    @pytest.mark.asyncio
    async def test_unknown_code(self, test_db):
        await _user("u1", "a@b.com")
        with pytest.raises(db.VoucherError) as exc:
            await db.redeem_voucher("UL-NOPE", "u1")
        assert exc.value.reason == "not_found"

    @pytest.mark.asyncio
    async def test_disabled_code_reads_as_not_found(self, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-OFF", None, 30)
        await db._get_db().execute("UPDATE vouchers SET disabled = 1 WHERE code = 'UL-OFF'")
        with pytest.raises(db.VoucherError) as exc:
            await db.redeem_voucher("UL-OFF", "u1")
        assert exc.value.reason == "not_found"

    @pytest.mark.asyncio
    async def test_double_redeem_same_user(self, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-CODE", None, 30, max_redemptions=5)
        await db.redeem_voucher("UL-CODE", "u1")
        with pytest.raises(db.VoucherError) as exc:
            await db.redeem_voucher("UL-CODE", "u1")
        assert exc.value.reason == "already_redeemed"

    @pytest.mark.asyncio
    async def test_exhausted(self, test_db):
        await _user("u1", "a@b.com")
        await _user("u2", "c@d.com")
        await db.create_voucher("UL-CODE", None, 30, max_redemptions=1)
        await db.redeem_voucher("UL-CODE", "u1")
        with pytest.raises(db.VoucherError) as exc:
            await db.redeem_voucher("UL-CODE", "u2")
        assert exc.value.reason == "exhausted"

    @pytest.mark.asyncio
    async def test_list_includes_redemptions_with_emails(self, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-CODE", "jane", 30)
        await db.redeem_voucher("UL-CODE", "u1")
        vouchers = await db.list_vouchers()
        assert len(vouchers) == 1
        assert vouchers[0]["redemptions"][0]["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_get_user_by_email_case_insensitive(self, test_db):
        await _user("u1", "Jane@Example.com")
        assert (await db.get_user_by_email("jane@example.com"))["id"] == "u1"
        assert await db.get_user_by_email("nobody@example.com") is None


# ---------------------------------------------------------------------------
# Effective tier (auth choke point)
# ---------------------------------------------------------------------------

async def _current_user(user_id: str, email: str, tier: str = "free") -> dict:
    token = auth.create_access_token(user_id, email, tier)
    request = MagicMock()
    request.cookies = {"access_token": token}
    return await auth.get_current_user(request)


class TestEffectiveTier:
    @pytest.mark.asyncio
    async def test_active_comp_grants_premium(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await db.set_premium_until("u1", _now_ms() + DAY_MS)
        user = await _current_user("u1", "a@b.com")
        assert user["tier"] == "premium"
        assert user["comp_premium"] is True

    @pytest.mark.asyncio
    async def test_expired_comp_stays_free(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await db.set_premium_until("u1", _now_ms() - 1_000)
        user = await _current_user("u1", "a@b.com")
        assert user["tier"] == "free"
        assert "comp_premium" not in user

    @pytest.mark.asyncio
    async def test_real_premium_and_admin_untouched(self, _auth_enabled, test_db):
        await _user("p1", "p@b.com", tier="premium")
        await _user("a1", "a@b.com", tier="admin")
        premium = await _current_user("p1", "p@b.com", "premium")
        admin = await _current_user("a1", "a@b.com", "admin")
        assert premium["tier"] == "premium" and "comp_premium" not in premium
        assert admin["tier"] == "admin" and "comp_premium" not in admin

    @pytest.mark.asyncio
    async def test_comp_passes_require_tier_premium(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await db.set_premium_until("u1", _now_ms() + DAY_MS)
        token = auth.create_access_token("u1", "a@b.com", "free")
        request = MagicMock()
        request.cookies = {"access_token": token}
        user = await auth.require_tier("premium")(request)
        assert user["tier"] == "premium"


# ---------------------------------------------------------------------------
# Stripe interplay
# ---------------------------------------------------------------------------

class TestStripeInterplay:
    @pytest.mark.asyncio
    async def test_subscription_deleted_does_not_clobber_comp(self, test_db):
        """A canceled Stripe sub downgrades tier but must leave the comp grant."""
        await _user("u1", "a@b.com", tier="premium")
        await db.update_user_stripe("u1", "cus_1", "sub_1")
        until = _now_ms() + 20 * DAY_MS
        await db.set_premium_until("u1", until)

        await _handle_subscription_deleted({"customer": "cus_1"})

        user = await db.get_user_by_id("u1")
        assert user["tier"] == "free"
        assert user["premium_until"] == until  # comp survives; user stays premium via it

    @pytest.mark.asyncio
    async def test_subscription_status_distinguishes_comp(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        until = _now_ms() + DAY_MS
        await db.set_premium_until("u1", until)
        user = await _current_user("u1", "a@b.com")

        status = await get_subscription_status(user)
        assert status["tier"] == "premium"
        assert status["subscription_active"] is False
        assert status["comp_until"] == until

    @pytest.mark.asyncio
    async def test_subscription_status_real_premium(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com", tier="premium")
        user = await _current_user("u1", "a@b.com", "premium")
        status = await get_subscription_status(user)
        assert status["subscription_active"] is True
        assert status["comp_until"] is None


# ---------------------------------------------------------------------------
# POST /api/voucher/redeem
# ---------------------------------------------------------------------------

class TestRedeemEndpoint:
    def test_requires_auth(self, _auth_enabled, test_db):
        resp = _make_client().post(
            "/api/voucher/redeem", json={"code": "UL-X"}, headers=CSRF_HEADERS
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_success_and_me_reflects_premium(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-EARLY", "jane", 30)
        client = _make_client("u1", "a@b.com")

        resp = client.post(
            "/api/voucher/redeem", json={"code": " ul-early "}, headers=CSRF_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["premium_until"] > _now_ms()

        me = client.get("/api/auth/me")
        assert me.json()["user"]["tier"] == "premium"

    @pytest.mark.asyncio
    async def test_error_mapping(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await _user("u2", "c@d.com")
        await db.create_voucher("UL-ONCE", None, 30, max_redemptions=1)
        c1 = _make_client("u1", "a@b.com")
        c2 = _make_client("u2", "c@d.com")

        assert c1.post("/api/voucher/redeem", json={"code": ""}, headers=CSRF_HEADERS).status_code == 400
        assert c1.post("/api/voucher/redeem", json={"code": "UL-NOPE"}, headers=CSRF_HEADERS).status_code == 404
        assert c1.post("/api/voucher/redeem", json={"code": "UL-ONCE"}, headers=CSRF_HEADERS).status_code == 200
        assert c1.post("/api/voucher/redeem", json={"code": "UL-ONCE"}, headers=CSRF_HEADERS).status_code == 409
        assert c2.post("/api/voucher/redeem", json={"code": "UL-ONCE"}, headers=CSRF_HEADERS).status_code == 410

    @pytest.mark.asyncio
    async def test_attempt_cap(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        client = _make_client("u1", "a@b.com")
        for _ in range(main_mod._VOUCHER_ATTEMPT_LIMIT):
            client.post("/api/voucher/redeem", json={"code": "UL-GUESS"}, headers=CSRF_HEADERS)
        resp = client.post("/api/voucher/redeem", json={"code": "UL-GUESS"}, headers=CSRF_HEADERS)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET /api/report/access with comp premium
# ---------------------------------------------------------------------------

class TestReportAccessGate:
    @pytest.mark.asyncio
    async def test_comp_user_has_subscription_access(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        await db.set_premium_until("u1", _now_ms() + DAY_MS)
        client = _make_client("u1", "a@b.com")
        resp = client.get("/api/report/access", params={"lat": 41.91, "lon": -87.67})
        assert resp.status_code == 200
        assert resp.json() == {"has_access": True, "reason": "subscription"}

    @pytest.mark.asyncio
    async def test_free_user_without_purchase_has_none(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        rl = SimpleNamespace(
            lat=41.91, lon=-87.67, address="1601 N Milwaukee Ave",
            pin=None, confidence="approximate",
        )
        with patch.object(main_mod, "_resolve_location", AsyncMock(return_value=rl)):
            resp = _make_client("u1", "a@b.com").get(
                "/api/report/access", params={"lat": 41.91, "lon": -87.67}
            )
        assert resp.status_code == 200
        assert resp.json()["has_access"] is False


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_non_admin_forbidden(self, _auth_enabled, test_db):
        await _user("u1", "a@b.com")
        client = _make_client("u1", "a@b.com")
        assert client.get("/api/admin/vouchers").status_code == 403
        assert client.post("/api/admin/vouchers", json={}, headers=CSRF_HEADERS).status_code == 403
        assert client.post("/api/admin/grant", json={}, headers=CSRF_HEADERS).status_code == 403

    @pytest.mark.asyncio
    async def test_mint_autogenerated_code(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        client = _make_client("adm", "j@b.com", "admin")
        resp = client.post(
            "/api/admin/vouchers",
            json={"label": "jane", "duration_days": 14, "max_redemptions": 3},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 200
        v = resp.json()
        assert v["code"].startswith("UL-") and len(v["code"]) == 11
        assert all(ch in main_mod._VOUCHER_ALPHABET for ch in v["code"][3:])
        assert v["duration_days"] == 14 and v["max_redemptions"] == 3

    @pytest.mark.asyncio
    async def test_mint_custom_code_uppercased_and_duplicate_409(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        client = _make_client("adm", "j@b.com", "admin")
        resp = client.post(
            "/api/admin/vouchers",
            json={"code": "urbanlayer-jane", "duration_days": 30},
            headers=CSRF_HEADERS,
        )
        assert resp.json()["code"] == "URBANLAYER-JANE"
        dup = client.post(
            "/api/admin/vouchers",
            json={"code": "URBANLAYER-JANE", "duration_days": 30},
            headers=CSRF_HEADERS,
        )
        assert dup.status_code == 409

    @pytest.mark.asyncio
    async def test_mint_validation(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        client = _make_client("adm", "j@b.com", "admin")
        resp = client.post(
            "/api/admin/vouchers", json={"duration_days": 0}, headers=CSRF_HEADERS
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_shows_redemptions(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        await _user("u1", "a@b.com")
        await db.create_voucher("UL-CODE", "jane", 30)
        await db.redeem_voucher("UL-CODE", "u1")
        resp = _make_client("adm", "j@b.com", "admin").get("/api/admin/vouchers")
        vouchers = resp.json()["vouchers"]
        assert vouchers[0]["code"] == "UL-CODE"
        assert vouchers[0]["redemptions"][0]["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_grant_by_email(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        await _user("u1", "Tester@Example.com")
        client = _make_client("adm", "j@b.com", "admin")
        resp = client.post(
            "/api/admin/grant",
            json={"email": "tester@example.com", "days": 21},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 200
        until = resp.json()["premium_until"]
        assert abs(until - (_now_ms() + 21 * DAY_MS)) < 5_000
        assert (await db.get_user_by_id("u1"))["premium_until"] == until

    @pytest.mark.asyncio
    async def test_grant_unknown_email_404(self, _auth_enabled, test_db):
        await _user("adm", "j@b.com", tier="admin")
        resp = _make_client("adm", "j@b.com", "admin").post(
            "/api/admin/grant",
            json={"email": "ghost@example.com", "days": 21},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 404
