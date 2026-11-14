"""Stripe billing: Pro checkout, the webhook, the billing portal (Phase 9 epic 4, decision Item 123).

Rules:
- Pro is $19 a month or $199 a year. The browser sends only ``interval`` ("month" | "year"); the price ids live in
  the server's settings.
- The subscription's state is Stripe's, never the browser's. Every webhook is signature-checked (in every
  environment), recorded once by event id (a replay does nothing), and answered by **re-reading the subscription
  from Stripe** and storing that, so the order events arrive in doesn't matter. Pro is derived from the stored
  state in ``auth`` (``PRO_STATUSES``); nothing here writes ``users.tier``.
- One customer per account, created by this server with the account id in its metadata; a checkout carries
  ``client_reference_id``. Nothing the browser sends back names an account.
- At most one subscription: checkout is refused while one is live, an open checkout session is reused, and a
  second subscription that still gets through is canceled and refunded.
- Purchases are on only when the secret key, the webhook secret and both prices are set (``purchases_enabled``).
- The $25 report purchase is retired: no new checkout; a late webhook for an old session is still recorded.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import stripe
from fastapi import HTTPException, Request

from backend import db
from backend.config import get_settings, stripe_key_is_live

log = logging.getLogger(__name__)

CHICAGO = ZoneInfo("America/Chicago")
INTERVALS = ("month", "year")
CHECKOUT_TTL_S = 30 * 60  # Stripe's shortest allowed expiry
_RETURN_PATHS = {"settings": "/settings/plan", "pricing": "/pricing"}
# Stripe's pages in the reader's language: Spanish is Latin American (es-419), the closest to the app's es-MX.
_STRIPE_LOCALES = {"en": "en", "es": "es-419"}
_user_locks: dict[str, asyncio.Lock] = {}


def _configure_stripe() -> None:
    stripe.api_key = get_settings().stripe_secret_key


def purchases_enabled() -> bool:
    s = get_settings()
    return bool(
        s.stripe_secret_key and s.stripe_webhook_secret
        and s.stripe_price_id_pro_monthly and s.stripe_price_id_pro_yearly
    )


def _price_for(interval: str) -> str:
    s = get_settings()
    return {"month": s.stripe_price_id_pro_monthly, "year": s.stripe_price_id_pro_yearly}[interval]


def _lock(user_id: str) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock


def _get(obj, key, default=None):
    """Read a field from a Stripe object or a plain dict."""
    try:
        value = obj.get(key, default) if hasattr(obj, "get") else getattr(obj, key, default)
    except Exception:  # noqa: BLE001
        return default
    return default if value is None else value


def _id(value) -> str | None:
    """A Stripe reference is an id string, or the expanded object."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return _get(value, "id")


def is_pro_status(status: str | None) -> bool:
    from backend.auth import PRO_STATUSES
    return status in PRO_STATUSES


# ── Checkout ──────────────────────────────────────────────────────────────────────────────────────────────────

async def _ensure_customer(user: dict) -> dict:
    """The account's one Stripe customer, created once (an idempotency key per account covers two requests racing
    across processes; the per-account lock covers this one). Email is optional (Apple and Microsoft may give none):
    Checkout asks for a receipt address."""
    sub = await db.get_subscription(user["id"])
    if sub:
        return sub
    params: dict = {"metadata": {"user_id": user["id"]}}
    if user.get("email"):
        params["email"] = user["email"]
    if user.get("name"):
        params["name"] = user["name"]
    customer = stripe.Customer.create(**params, idempotency_key=f"ul-customer-{user['id']}")
    return await db.set_subscription_customer(user["id"], customer["id"])


async def create_checkout_session(user: dict, interval: str, origin: str = "settings", language: str = "en") -> str:
    """Start (or reuse) a Pro checkout and return its URL."""
    if interval not in INTERVALS:
        raise HTTPException(status_code=400, detail={"error": "bad_interval"})
    if not purchases_enabled():
        raise HTTPException(status_code=503, detail={"error": "purchases_off"})
    if user.get("tier") == "admin":
        raise HTTPException(status_code=409, detail={"error": "admin_account"})
    _configure_stripe()
    s = get_settings()
    return_path = _RETURN_PATHS.get(origin, _RETURN_PATHS["settings"])
    base = s.frontend_url.rstrip("/")

    async with _lock(user["id"]):
        sub = await _ensure_customer(user)
        if is_pro_status(sub.get("status")):
            raise HTTPException(status_code=409, detail={"error": "already_subscribed"})

        now = int(time.time())
        if (
            sub.get("checkout_session_id")
            and sub.get("checkout_interval") == interval
            and (sub.get("checkout_expires_at") or 0) > now + 60
        ):
            try:
                existing = stripe.checkout.Session.retrieve(sub["checkout_session_id"])
                if _get(existing, "status") == "open" and _get(existing, "url"):
                    return existing["url"]
            except stripe.StripeError:
                pass  # make a new one

        expires_at = now + CHECKOUT_TTL_S
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=sub["stripe_customer_id"],
            client_reference_id=user["id"],
            line_items=[{"price": _price_for(interval), "quantity": 1}],
            success_url=f"{base}/settings/plan?checkout=done",
            cancel_url=f"{base}{return_path}",
            expires_at=expires_at,
            locale=_STRIPE_LOCALES.get(language, "auto"),
            metadata={"user_id": user["id"], "interval": interval},
            subscription_data={"metadata": {"user_id": user["id"]}},
        )
        await db.set_checkout_session(user["id"], session["id"], interval, expires_at)
        log.info("checkout created user=%s interval=%s", user["id"], interval)
        return session["url"]


async def create_billing_portal_session(user: dict, language: str = "en") -> str:
    """Stripe's Portal: cancel, card, invoices, month <-> year. Back to Settings → Plan."""
    sub = await db.get_subscription(user["id"])
    if not sub or not sub.get("stripe_subscription_id"):
        raise HTTPException(status_code=400, detail={"error": "no_subscription"})
    _configure_stripe()
    s = get_settings()
    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{s.frontend_url.rstrip('/')}/settings/plan",
        locale=_STRIPE_LOCALES.get(language, "auto"),
    )
    return session.url


async def create_report_checkout_session(*_args, **_kwargs) -> str:
    """Retired with the $25 report (Item 123): Pro and the free Deep analysis replace it."""
    raise HTTPException(status_code=410, detail={"error": "report_purchase_retired"})


# ── Webhook ───────────────────────────────────────────────────────────────────────────────────────────────────

_SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
}
_INVOICE_EVENTS = {"invoice.paid", "invoice.payment_failed", "invoice.payment_succeeded"}


async def handle_webhook(request: Request) -> dict:
    """Verify, record once, and sync from Stripe. Never trusts the event body for state."""
    s = get_settings()
    if not s.stripe_webhook_secret:
        # Item 123: no unsigned events anywhere (locally, `stripe listen` gives a secret).
        log.error("Stripe webhook secret not configured; rejecting webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")
    _configure_stripe()

    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(body, sig, s.stripe_webhook_secret)
    except (stripe.SignatureVerificationError, ValueError):
        log.warning("stripe webhook refused reason=signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if bool(_get(event, "livemode", False)) != stripe_key_is_live(s.stripe_secret_key):
        log.warning("stripe webhook refused reason=mode event=%s", _get(event, "id"))
        raise HTTPException(status_code=400, detail="Event mode does not match this server")

    event_id = _get(event, "id")
    event_type = _get(event, "type")
    if not await db.record_stripe_event(event_id, event_type):
        log.info("stripe webhook duplicate event=%s type=%s", event_id, event_type)
        return {"received": True, "duplicate": True}

    try:
        await _dispatch(event_type, event["data"]["object"])
    except Exception:
        await db.forget_stripe_event(event_id)  # Stripe retries; the retry runs it again
        log.exception("stripe webhook failed event=%s type=%s", event_id, event_type)
        raise HTTPException(status_code=500, detail="Webhook processing failed")
    log.info("stripe webhook processed event=%s type=%s", event_id, event_type)
    return {"received": True}


async def _dispatch(event_type: str, obj) -> None:
    if event_type == "checkout.session.completed":
        if _get(obj, "mode") == "payment":
            await _handle_report_purchase_completed(obj)
            return
        await _handle_subscription_checkout(obj)
    elif event_type in _SUBSCRIPTION_EVENTS:
        await sync_subscription(_get(obj, "id"))
    elif event_type in _INVOICE_EVENTS:
        sub_id = _invoice_subscription(obj)
        if sub_id:
            await sync_subscription(sub_id)
    else:
        log.debug("Unhandled Stripe event: %s", event_type)


def _invoice_subscription(invoice) -> str | None:
    """An invoice's subscription: ``subscription`` on older API versions, ``parent.subscription_details`` on newer."""
    sub = _id(_get(invoice, "subscription"))
    if sub:
        return sub
    details = _get(_get(invoice, "parent") or {}, "subscription_details") or {}
    return _id(_get(details, "subscription"))


async def _handle_subscription_checkout(session) -> None:
    user_id = _get(session, "client_reference_id")
    customer_id = _id(_get(session, "customer"))
    sub_id = _id(_get(session, "subscription"))
    if not (user_id and customer_id and sub_id):
        log.error("subscription checkout missing reference session=%s", _get(session, "id"))
        return
    ours = await db.get_subscription(user_id)
    if not ours or ours["stripe_customer_id"] != customer_id:
        # The customer is created by this server for this account; anything else is not ours to credit.
        log.error("subscription checkout customer mismatch session=%s user=%s", _get(session, "id"), user_id)
        return
    await sync_subscription(sub_id)
    await _save_money_event("subscription_started", session, user_id)


def _period_end(sub) -> int | None:
    end = _get(sub, "current_period_end")
    if end:
        return int(end)
    items = _get(_get(sub, "items") or {}, "data") or []
    ends = [int(_get(i, "current_period_end")) for i in items if _get(i, "current_period_end")]
    return max(ends) if ends else None


def _interval(sub) -> str | None:
    items = _get(_get(sub, "items") or {}, "data") or []
    for item in items:
        recurring = _get(_get(item, "price") or {}, "recurring") or {}
        if _get(recurring, "interval"):
            return _get(recurring, "interval")
    return None


async def sync_subscription(sub_id: str | None) -> None:
    """Re-read a subscription from Stripe and store it on its customer's account."""
    if not sub_id:
        return
    sub = stripe.Subscription.retrieve(sub_id)
    customer_id = _id(_get(sub, "customer"))
    ours = await db.get_subscription_by_customer(customer_id) if customer_id else None
    if not ours:
        log.warning("subscription for a customer that isn't ours sub=%s", sub_id)
        return

    status = _get(sub, "status")
    current = ours.get("stripe_subscription_id")
    if current and current != sub_id and is_pro_status(ours.get("status")) and is_pro_status(status):
        # A second live subscription on one account (two checkouts from before the guard): keep the first,
        # cancel and refund the newer one.
        older_created = 0
        try:
            older_created = int(_get(stripe.Subscription.retrieve(current), "created", 0))
        except stripe.StripeError:
            pass
        newer = sub_id if int(_get(sub, "created", 0)) >= older_created else current
        await _cancel_and_refund(newer)
        if newer == sub_id:
            log.error("second subscription canceled and refunded user=%s sub=%s", ours["user_id"], sub_id)
            return
        sub = stripe.Subscription.retrieve(sub_id)
        status = _get(sub, "status")

    if current and current != sub_id and is_pro_status(ours.get("status")) and not is_pro_status(status):
        # An old or abandoned subscription changed while the live one stays: nothing to store.
        return

    cancel_at_end = bool(_get(sub, "cancel_at_period_end", False)) or bool(_get(sub, "cancel_at"))
    await db.write_subscription_state(
        customer_id,
        subscription_id=sub_id,
        status=status,
        interval=_interval(sub),
        current_period_end=_period_end(sub),
        cancel_at_period_end=cancel_at_end,
    )
    log.info("subscription synced user=%s status=%s", ours["user_id"], status)


async def _cancel_and_refund(sub_id: str) -> None:
    sub = stripe.Subscription.retrieve(sub_id, expand=["latest_invoice"])
    stripe.Subscription.cancel(sub_id)
    invoice = _get(sub, "latest_invoice")
    invoice_id = _id(invoice)
    intent = _id(_get(invoice, "payment_intent")) if not isinstance(invoice, str) else None
    if not intent and invoice_id:
        try:
            payments = stripe.InvoicePayment.list(invoice=invoice_id)
            for p in _get(payments, "data") or []:
                intent = _id(_get(_get(p, "payment") or {}, "payment_intent"))
                if intent:
                    break
        except (stripe.StripeError, AttributeError):
            intent = None
    if intent:
        stripe.Refund.create(payment_intent=intent)
    else:
        log.error("second subscription canceled but no payment found to refund sub=%s", sub_id)


async def _handle_report_purchase_completed(session) -> None:
    """A report checkout started before the retirement may still complete; record it as before."""
    metadata = _get(session, "metadata") or {}
    user_id = _get(metadata, "user_id")
    if not user_id:
        log.error("Report purchase session missing user_id metadata")
        return
    purchase = await db.complete_report_purchase(_get(session, "id"), _get(session, "payment_intent"))
    if purchase is None:
        log.error("Report purchase webhook for unknown session %s", _get(session, "id"))
        return
    if not purchase["newly_completed"]:
        return
    await _save_money_event("purchase_completed", session, user_id)


async def _save_money_event(event_name: str, session, user_id: str) -> None:
    """The funnel's money step is written only here (main.py's allowlist excludes it from the browser)."""
    metadata = _get(session, "metadata") or {}
    await db.save_events([{
        "session_id": _get(session, "id") or "stripe",
        "visitor_id": _get(metadata, "visitor_id"),
        "user_id": user_id,
        "event_name": event_name,
        "event_data": {
            "purchase_type": _get(metadata, "purchase_type", "subscription"),
            "interval": _get(metadata, "interval"),
            "amount_total": _get(session, "amount_total"),
        },
        "page": None,
        "address": None,
    }])


# ── Account deletion and status ───────────────────────────────────────────────────────────────────────────────

async def cancel_user_subscription(user: dict) -> None:
    """Cancel the account's live subscription now, before the account is deleted.

    Raises HTTPException(502) when Stripe refuses: a live subscription must never be orphaned behind a deleted
    account. An already-canceled or missing one counts as success."""
    sub = await db.get_subscription(user["id"])
    sub_id = (sub or {}).get("stripe_subscription_id") or user.get("stripe_subscription_id")
    if not sub_id:
        return
    if sub and sub.get("status") in ("canceled", "incomplete_expired"):
        return
    _configure_stripe()
    try:
        stripe.Subscription.cancel(sub_id)
    except stripe.InvalidRequestError as exc:
        log.info("Subscription %s already inactive at Stripe: %s", sub_id, exc)
    except stripe.StripeError as exc:
        log.error("Failed to cancel subscription %s: %s", sub_id, exc)
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not cancel your subscription — your account was NOT "
                "deleted. Try again or contact support."
            ),
        )
    else:
        log.info("Canceled subscription %s for user %s", sub_id, user["id"])


def _chicago_date(epoch_s: int | None) -> str | None:
    if not epoch_s:
        return None
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).astimezone(CHICAGO).date().isoformat()


async def get_subscription_status(user: dict) -> dict:
    """What Settings → Plan shows. ``plan`` is the effective one (admin / pro / free); ``source`` says why."""
    sub = user.get("subscription")
    if sub is None and user.get("id"):
        try:
            sub = await db.get_subscription(user["id"])
        except Exception:  # noqa: BLE001
            sub = None
    paid = bool(sub and is_pro_status(sub.get("status")))
    comp = bool(user.get("comp_premium"))
    tier = user.get("tier")
    plan = "admin" if tier == "admin" else ("pro" if tier == "premium" else "free")
    source = "stripe" if paid else ("voucher" if comp else None)
    period_end = _chicago_date(sub.get("current_period_end")) if paid else None
    ending = bool(paid and sub.get("cancel_at_period_end"))
    return {
        "tier": tier,
        "plan": plan,
        "source": source,
        "status": sub.get("status") if sub else None,
        "interval": sub.get("price_interval") if paid else None,
        "renews_on": None if ending else period_end,
        "ends_on": period_end if ending else None,
        "past_due": bool(paid and sub.get("status") == "past_due"),
        # Manage billing (Stripe's Portal) only for a Stripe subscription: a voucher has nothing to manage there.
        "subscription_active": paid,
        "can_manage": bool(sub and sub.get("stripe_subscription_id")),
        "comp_until": user.get("premium_until") if comp else None,
        "purchases_enabled": purchases_enabled(),
    }
