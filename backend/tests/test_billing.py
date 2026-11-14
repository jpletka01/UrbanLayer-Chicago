"""Billing (Phase 9 epic 4, decision Item 123): every row of the threat model.

Stripe is never called: the module's ``stripe`` calls are patched, and webhook payloads are signed here with the
test's own secret exactly as Stripe signs them (``t=<ts>,v1=<HMAC-SHA256(secret, "<ts>.<body>")>``).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
import stripe
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import auth, config, db, payments
from backend.main import app

SECRET = "whsec_test_secret"
CSRF = {"x-csrf-token": "csrf-test"}


@pytest_asyncio.fixture
async def test_db(tmp_path):
    s = MagicMock()
    s.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()
        yield
        await db.close_db()


def _settings(**over):
    s = MagicMock()
    s.stripe_secret_key = "sk_test_x"
    s.stripe_webhook_secret = SECRET
    s.stripe_price_id_pro_monthly = "price_month"
    s.stripe_price_id_pro_yearly = "price_year"
    s.stripe_price_id_report = ""
    s.frontend_url = "http://localhost:5173"
    s.environment = "development"
    for k, v in over.items():
        setattr(s, k, v)
    return s


@pytest.fixture
def pay_settings():
    s = _settings()
    with patch("backend.payments.get_settings", return_value=s):
        yield s


@pytest.fixture(autouse=True)
def _no_real_stripe():
    """Any Stripe call a test didn't patch fails loudly instead of reaching the network."""
    def boom(*_a, **_k):
        raise AssertionError("unpatched Stripe call")
    with patch.object(stripe.Subscription, "retrieve", side_effect=boom), \
         patch.object(stripe.Subscription, "cancel", side_effect=boom), \
         patch.object(stripe.Customer, "create", side_effect=boom), \
         patch.object(stripe.checkout.Session, "create", side_effect=boom), \
         patch.object(stripe.checkout.Session, "retrieve", side_effect=boom), \
         patch.object(stripe.Refund, "create", side_effect=boom):
        payments._user_locks.clear()
        yield


async def _user(uid: str, tier: str = "free", email: str | None = None) -> dict:
    claims = {"provider": "google", "subject": f"g-{uid}", "email": email, "name": uid.upper()}
    user, _ = await db.sign_in_identity(claims, uid)
    if tier != "free":
        await db.update_user_tier(uid, tier)
    return user


async def _current(uid: str) -> dict:
    """The user as every request sees it (auth's choke point)."""
    raw = await db.get_user_by_id(uid)
    return auth._apply_comp_premium(await auth._with_subscription(raw))


def _sub(sub_id="sub_1", customer="cus_1", status="active", interval="month", end=1_900_000_000,
         cancel=False, created=100):
    return {
        "id": sub_id, "customer": customer, "status": status, "created": created,
        "cancel_at_period_end": cancel, "cancel_at": None,
        "items": {"data": [{"current_period_end": end, "price": {"recurring": {"interval": interval}}}]},
    }


def _signed(event: dict, *, secret: str = SECRET, ts: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    ts = ts or int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def _event(event_type: str, obj: dict, event_id: str = "evt_1", livemode: bool = False) -> dict:
    return {"id": event_id, "object": "event", "type": event_type, "livemode": livemode,
            "data": {"object": obj}, "api_version": "2025-03-31"}


class _Req:
    """What handle_webhook reads from a request."""
    def __init__(self, body: bytes, headers: dict):
        self._body, self.headers = body, headers

    async def body(self) -> bytes:
        return self._body


async def _post(event: dict, **kw) -> dict:
    body, headers = _signed(event, **kw)
    return await payments.handle_webhook(_Req(body, headers))


async def _subscribed(uid="u1", customer="cus_1", **sub_kw):
    await db.set_subscription_customer(uid, customer)
    with patch.object(stripe.Subscription, "retrieve", return_value=_sub(customer=customer, **sub_kw)):
        await payments.sync_subscription(sub_kw.get("sub_id", "sub_1"))


# ── Webhook: signature, mode, replay ──────────────────────────────────────────────────────────────────────────

class TestWebhookTrust:
    @pytest.mark.asyncio
    async def test_unsigned_event_is_refused_and_changes_nothing(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        body = json.dumps(_event("customer.subscription.updated", _sub())).encode()
        with pytest.raises(HTTPException) as e:
            await payments.handle_webhook(_Req(body, {}))
        assert e.value.status_code == 400
        assert (await _current("u1"))["tier"] == "free"

    @pytest.mark.asyncio
    async def test_wrong_secret_and_stale_timestamp_refused(self, test_db, pay_settings):
        ev = _event("customer.subscription.updated", _sub())
        for kw in ({"secret": "whsec_other"}, {"ts": int(time.time()) - 3600}):
            with pytest.raises(HTTPException) as e:
                await _post(ev, **kw)
            assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_webhook_secret_refuses_even_in_development(self, test_db):
        with patch("backend.payments.get_settings", return_value=_settings(stripe_webhook_secret="")):
            body, headers = _signed(_event("customer.subscription.updated", _sub()))
            with pytest.raises(HTTPException) as e:
                await payments.handle_webhook(_Req(body, headers))
        assert e.value.status_code == 503

    @pytest.mark.asyncio
    async def test_live_event_on_a_test_server_refused(self, test_db, pay_settings):
        with pytest.raises(HTTPException) as e:
            await _post(_event("customer.subscription.updated", _sub(), livemode=True))
        assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_replay_is_processed_once(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        ev = _event("customer.subscription.updated", _sub())
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub()) as retrieve:
            first = await _post(ev)
            second = await _post(ev)
        assert first == {"received": True}
        assert second == {"received": True, "duplicate": True}
        assert retrieve.call_count == 1

    @pytest.mark.asyncio
    async def test_ten_copies_at_once_are_processed_once(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        ev = _event("customer.subscription.updated", _sub())
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub()) as retrieve:
            results = await asyncio.gather(*[_post(ev) for _ in range(10)])
        assert retrieve.call_count == 1
        assert sum(1 for r in results if r.get("duplicate")) == 9

    @pytest.mark.asyncio
    async def test_a_failure_lets_stripes_retry_run_it(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        ev = _event("customer.subscription.updated", _sub())
        with patch.object(stripe.Subscription, "retrieve", side_effect=stripe.APIConnectionError("down")):
            with pytest.raises(HTTPException) as e:
                await _post(ev)
        assert e.value.status_code == 500
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub()):
            assert await _post(ev) == {"received": True}
        assert (await _current("u1"))["tier"] == "premium"


# ── Webhook: state comes from Stripe ─────────────────────────────────────────────────────────────────────────

class TestStateFromStripe:
    @pytest.mark.asyncio
    async def test_late_active_event_after_cancel_stays_free(self, test_db, pay_settings):
        """Events out of order: Stripe's current state (canceled) wins over a stale body saying active."""
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        canceled = _sub(status="canceled")
        with patch.object(stripe.Subscription, "retrieve", return_value=canceled):
            await _post(_event("customer.subscription.deleted", canceled, "evt_del"))
            await _post(_event("customer.subscription.updated", _sub(status="active"), "evt_late"))
        assert (await _current("u1"))["tier"] == "free"

    @pytest.mark.asyncio
    async def test_checkout_completed_credits_the_account_that_owns_the_customer(self, test_db, pay_settings):
        await _user("u1")
        await _user("u2")
        await db.set_subscription_customer("u1", "cus_1")
        session = {"id": "cs_1", "mode": "subscription", "client_reference_id": "u1",
                   "customer": "cus_1", "subscription": "sub_1", "metadata": {"user_id": "u2"}}
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub()):
            await _post(_event("checkout.session.completed", session))
        assert (await _current("u1"))["tier"] == "premium"
        assert (await _current("u2"))["tier"] == "free"  # metadata naming another account is ignored

    @pytest.mark.asyncio
    async def test_checkout_naming_another_accounts_customer_credits_nobody(self, test_db, pay_settings):
        await _user("u1")
        await _user("u2")
        await db.set_subscription_customer("u1", "cus_1")
        await db.set_subscription_customer("u2", "cus_2")
        session = {"id": "cs_1", "mode": "subscription", "client_reference_id": "u2",
                   "customer": "cus_1", "subscription": "sub_1"}
        await _post(_event("checkout.session.completed", session))  # no Stripe call is made
        assert (await _current("u1"))["tier"] == "free"
        assert (await _current("u2"))["tier"] == "free"

    @pytest.mark.asyncio
    async def test_subscription_for_an_unknown_customer_changes_nothing(self, test_db, pay_settings):
        await _user("u1")
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub(customer="cus_x")):
            await _post(_event("customer.subscription.created", _sub(customer="cus_x")))
        assert (await _current("u1"))["tier"] == "free"

    @pytest.mark.asyncio
    async def test_invoice_events_resync_both_api_shapes(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")
        old_shape = {"id": "in_1", "subscription": "sub_1"}
        new_shape = {"id": "in_2", "parent": {"subscription_details": {"subscription": "sub_1"}}}
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub(status="past_due")) as r:
            await _post(_event("invoice.payment_failed", old_shape, "evt_a"))
            await _post(_event("invoice.payment_failed", new_shape, "evt_b"))
        assert r.call_count == 2
        assert (await db.get_subscription("u1"))["status"] == "past_due"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status,pro", [
        ("active", True), ("trialing", True), ("past_due", True),
        ("unpaid", False), ("canceled", False), ("incomplete", False), ("incomplete_expired", False),
        ("paused", False),
    ])
    async def test_plan_by_status(self, test_db, pay_settings, status, pro):
        await _user("u1")
        await _subscribed(status=status)
        assert ((await _current("u1"))["tier"] == "premium") is pro

    @pytest.mark.asyncio
    async def test_webhooks_never_write_the_tier_column_and_admin_stays_admin(self, test_db, pay_settings):
        await _user("a1", tier="admin")
        await _subscribed("a1", status="active")
        assert (await _current("a1"))["tier"] == "admin"
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub(status="canceled")):
            await payments.sync_subscription("sub_1")
        assert (await _current("a1"))["tier"] == "admin"
        assert (await db.get_user_by_id("a1"))["tier"] == "admin"

    @pytest.mark.asyncio
    async def test_success_url_alone_grants_nothing(self, test_db, pay_settings):
        await _user("u1")
        await db.set_subscription_customer("u1", "cus_1")  # checkout started, no webhook yet
        status = await payments.get_subscription_status(await _current("u1"))
        assert status["plan"] == "free" and status["subscription_active"] is False


# ── Checkout ──────────────────────────────────────────────────────────────────────────────────────────────────

def _session(sid="cs_1", url="https://checkout.stripe.test/cs_1"):
    return {"id": sid, "url": url, "status": "open"}


class TestCheckout:
    @pytest.mark.asyncio
    async def test_interval_maps_to_the_servers_price(self, test_db, pay_settings):
        user = await _user("u1")
        with patch.object(stripe.Customer, "create", return_value={"id": "cus_1"}), \
             patch.object(stripe.checkout.Session, "create", return_value=_session()) as create:
            url = await payments.create_checkout_session(user, "year", "pricing")
        assert url.endswith("cs_1")
        kw = create.call_args.kwargs
        assert kw["line_items"] == [{"price": "price_year", "quantity": 1}]
        assert kw["client_reference_id"] == "u1" and kw["customer"] == "cus_1"
        assert kw["success_url"] == "http://localhost:5173/settings/plan?checkout=done"
        assert kw["cancel_url"] == "http://localhost:5173/pricing"
        assert kw["mode"] == "subscription"
        assert kw["locale"] == "en"

    @pytest.mark.asyncio
    async def test_bad_interval_400(self, test_db, pay_settings):
        user = await _user("u1")
        for bad in ("free", "price_month", "week", ""):
            with pytest.raises(HTTPException) as e:
                await payments.create_checkout_session(user, bad)
            assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_purchases_off_503(self, test_db):
        user = await _user("u1")
        for missing in ("stripe_secret_key", "stripe_webhook_secret", "stripe_price_id_pro_yearly"):
            with patch("backend.payments.get_settings", return_value=_settings(**{missing: ""})):
                with pytest.raises(HTTPException) as e:
                    await payments.create_checkout_session(user, "month")
            assert e.value.status_code == 503

    @pytest.mark.asyncio
    async def test_customer_made_once_with_idempotency_key_and_no_email_needed(self, test_db, pay_settings):
        user = await _user("u1", email=None)  # Apple/Microsoft may give no email
        with patch.object(stripe.Customer, "create", return_value={"id": "cus_1"}) as cc, \
             patch.object(stripe.checkout.Session, "create", side_effect=[_session("cs_1"), _session("cs_2")]):
            await payments.create_checkout_session(user, "month")
            await payments.create_checkout_session(user, "year")
        assert cc.call_count == 1
        assert cc.call_args.kwargs["idempotency_key"] == "ul-customer-u1"
        assert cc.call_args.kwargs["metadata"] == {"user_id": "u1"}
        assert "email" not in cc.call_args.kwargs

    @pytest.mark.asyncio
    async def test_already_subscribed_409(self, test_db, pay_settings):
        await _user("u1")
        await _subscribed(status="active")
        with pytest.raises(HTTPException) as e:
            await payments.create_checkout_session(await _current("u1"), "month")
        assert e.value.status_code == 409 and e.value.detail == {"error": "already_subscribed"}

    @pytest.mark.asyncio
    async def test_open_session_is_reused(self, test_db, pay_settings):
        user = await _user("u1")
        with patch.object(stripe.Customer, "create", return_value={"id": "cus_1"}), \
             patch.object(stripe.checkout.Session, "create", return_value=_session()) as create, \
             patch.object(stripe.checkout.Session, "retrieve", return_value=_session()):
            a = await payments.create_checkout_session(user, "month")
            b = await payments.create_checkout_session(user, "month")
        assert a == b and create.call_count == 1

    @pytest.mark.asyncio
    async def test_two_checkouts_at_once_make_one_session(self, test_db, pay_settings):
        user = await _user("u1")
        with patch.object(stripe.Customer, "create", return_value={"id": "cus_1"}) as cc, \
             patch.object(stripe.checkout.Session, "create", return_value=_session()) as create, \
             patch.object(stripe.checkout.Session, "retrieve", return_value=_session()):
            urls = await asyncio.gather(*[payments.create_checkout_session(user, "month") for _ in range(5)])
        assert len(set(urls)) == 1 and create.call_count == 1 and cc.call_count == 1

    @pytest.mark.asyncio
    async def test_expired_session_is_replaced(self, test_db, pay_settings):
        user = await _user("u1")
        with patch.object(stripe.Customer, "create", return_value={"id": "cus_1"}), \
             patch.object(stripe.checkout.Session, "create", side_effect=[_session("cs_1"), _session("cs_2", "u2")]), \
             patch.object(stripe.checkout.Session, "retrieve", return_value={**_session(), "status": "expired"}):
            await payments.create_checkout_session(user, "month")
            assert await payments.create_checkout_session(user, "month") == "u2"

    @pytest.mark.asyncio
    async def test_second_subscription_is_canceled_and_refunded(self, test_db, pay_settings):
        await _user("u1")
        await _subscribed(status="active", created=100)
        newer = _sub(sub_id="sub_2", created=200)
        newer_expanded = {**newer, "latest_invoice": {"id": "in_2", "payment_intent": "pi_2"}}

        def retrieve(sid, **kw):
            if sid == "sub_1":
                return _sub(created=100)
            return newer_expanded if kw.get("expand") else newer

        with patch.object(stripe.Subscription, "retrieve", side_effect=retrieve), \
             patch.object(stripe.Subscription, "cancel") as cancel, \
             patch.object(stripe.Refund, "create") as refund:
            await payments.sync_subscription("sub_2")
        cancel.assert_called_once_with("sub_2")
        refund.assert_called_once_with(payment_intent="pi_2")
        assert (await db.get_subscription("u1"))["stripe_subscription_id"] == "sub_1"
        assert (await _current("u1"))["tier"] == "premium"

    @pytest.mark.asyncio
    async def test_admin_cannot_start_checkout(self, test_db, pay_settings):
        await _user("a1", tier="admin")
        with pytest.raises(HTTPException) as e:
            await payments.create_checkout_session(await _current("a1"), "month")
        assert e.value.status_code == 409


class TestCheckoutRoute:
    @pytest.fixture
    def client(self):
        user = {"id": "u1", "tier": "free", "email": None, "name": "U"}
        app.dependency_overrides[auth.require_auth] = lambda: user
        c = TestClient(app)
        c.cookies.set("csrf_token", "csrf-test")
        yield c
        app.dependency_overrides.clear()

    def test_only_month_or_year_accepted(self, client):
        with patch("backend.payments.create_checkout_session") as create:
            for bad in ({"interval": "free"}, {"interval": "price_month"}, {"interval": "month", "origin": "evil"}):
                assert client.post("/api/billing/checkout", json=bad, headers=CSRF).status_code == 422
        create.assert_not_called()

    def test_price_id_from_the_browser_is_ignored(self, client):
        async def fake(user, interval, origin, language):
            return f"https://x/{interval}/{origin}/{language}"
        with patch("backend.payments.create_checkout_session", side_effect=fake):
            r = client.post("/api/billing/checkout", json={"interval": "year", "price": "price_free", "language": "es"},
                            headers=CSRF)
        assert r.status_code == 200 and r.json() == {"url": "https://x/year/settings/es"}

    def test_report_checkout_is_retired(self, client):
        r = client.post("/api/checkout/report", json={"pin": "14331030110000"}, headers=CSRF)
        assert r.status_code == 410 and r.json()["detail"] == {"error": "report_purchase_retired"}


# ── Status, portal, deletion, keys, logs ──────────────────────────────────────────────────────────────────────

class TestStatusAndPortal:
    @pytest.mark.asyncio
    async def test_renewing_and_ending_dates(self, test_db, pay_settings):
        await _user("u1")
        end = 1_900_000_000  # 2030-03-17 Chicago
        await _subscribed(status="active", interval="year", end=end)
        s = await payments.get_subscription_status(await _current("u1"))
        assert s["plan"] == "pro" and s["source"] == "stripe" and s["interval"] == "year"
        assert s["renews_on"] == "2030-03-17" and s["ends_on"] is None and s["can_manage"] is True
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub(interval="year", end=end, cancel=True)):
            await payments.sync_subscription("sub_1")
        s = await payments.get_subscription_status(await _current("u1"))
        assert s["renews_on"] is None and s["ends_on"] == "2030-03-17"

    @pytest.mark.asyncio
    async def test_free_and_admin_status(self, test_db, pay_settings):
        await _user("u1")
        await _user("a1", tier="admin")
        free = await payments.get_subscription_status(await _current("u1"))
        admin = await payments.get_subscription_status(await _current("a1"))
        assert free["plan"] == "free" and free["purchases_enabled"] is True and free["can_manage"] is False
        assert admin["plan"] == "admin"

    @pytest.mark.asyncio
    async def test_portal_returns_to_settings_and_needs_a_subscription(self, test_db, pay_settings):
        await _user("u1")
        with pytest.raises(HTTPException) as e:
            await payments.create_billing_portal_session(await _current("u1"))
        assert e.value.status_code == 400
        await _subscribed(status="active")
        with patch.object(stripe.billing_portal.Session, "create",
                          return_value=SimpleNamespace(url="https://portal")) as create:
            assert await payments.create_billing_portal_session(await _current("u1")) == "https://portal"
        assert create.call_args.kwargs == {"customer": "cus_1", "return_url": "http://localhost:5173/settings/plan",
                                          "locale": "en"}

    @pytest.mark.asyncio
    async def test_deleting_an_account_cancels_its_subscription_first(self, test_db, pay_settings):
        await _user("u1")
        await _subscribed(status="active")
        with patch.object(stripe.Subscription, "cancel") as cancel:
            await payments.cancel_user_subscription(await _current("u1"))
        cancel.assert_called_once_with("sub_1")
        with patch.object(stripe.Subscription, "cancel", side_effect=stripe.APIConnectionError("down")):
            with pytest.raises(HTTPException) as e:
                await payments.cancel_user_subscription(await _current("u1"))
        assert e.value.status_code == 502
        await db.delete_user_account("u1")
        assert await db.get_subscription("u1") is None


class TestKeysAndLogs:
    def test_live_key_refused_outside_production(self):
        for env in ("development", "test"):
            s = config.Settings(environment=env, stripe_secret_key="sk_live_abc")
            with pytest.raises(RuntimeError, match="live key"):
                config.validate_production(s)
            s = config.Settings(environment=env, stripe_secret_key="rk_live_abc")
            with pytest.raises(RuntimeError):
                config.validate_production(s)
        config.validate_production(config.Settings(environment="development", stripe_secret_key="sk_test_abc"))

    @pytest.mark.asyncio
    async def test_logs_carry_ids_only(self, test_db, pay_settings, caplog):
        await _user("u1", email="person@example.com")
        await db.set_subscription_customer("u1", "cus_1")
        session = {"id": "cs_1", "mode": "subscription", "client_reference_id": "u1", "customer": "cus_1",
                   "subscription": "sub_1", "customer_details": {"email": "person@example.com", "name": "Person"}}
        caplog.set_level(logging.DEBUG, logger="backend.payments")
        with patch.object(stripe.Subscription, "retrieve", return_value=_sub()):
            await _post(_event("checkout.session.completed", session))
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert "person@example.com" not in text and "Person" not in text and SECRET not in text
        assert "evt_1" in text


class TestMigration:
    @pytest.mark.asyncio
    async def test_v19_database_gains_the_billing_tables(self, tmp_path):
        s = MagicMock()
        s.db_path = tmp_path / "old.db"
        with patch("backend.db.get_settings", return_value=s):
            await db.init_db()
            await _user("u1")
            conn = db._get_db()
            await conn.executescript(
                "DROP TABLE subscriptions; DROP TABLE stripe_events; DROP TABLE entitlement_uses; "
                "UPDATE schema_version SET version = 19;"
            )
            await db.close_db()
            await db.init_db()
            cur = await db._get_db().execute("SELECT version FROM schema_version")
            assert (await cur.fetchone())[0] == 20
            assert await db.get_user_by_id("u1") is not None
            await db.set_subscription_customer("u1", "cus_1")
            assert (await db.get_subscription("u1"))["stripe_customer_id"] == "cus_1"
            await db.close_db()
