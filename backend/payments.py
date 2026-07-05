"""Stripe payment integration — checkout, webhooks, billing portal."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import stripe
from fastapi import HTTPException, Request

from backend import db
from backend.config import get_settings

log = logging.getLogger(__name__)


def _configure_stripe() -> None:
    s = get_settings()
    stripe.api_key = s.stripe_secret_key


async def create_checkout_session(user: dict, visitor_id: str | None = None) -> str:
    """Create a Stripe Checkout session and return the URL.

    ``visitor_id`` (analytics) rides the session metadata so the webhook can
    attribute the completed purchase to the originating visitor's funnel.
    """
    _configure_stripe()
    s = get_settings()

    if not s.stripe_price_id_pro_monthly:
        raise HTTPException(status_code=503, detail="Payment not configured")

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": s.stripe_price_id_pro_monthly, "quantity": 1}],
        "success_url": f"{s.frontend_url}/?checkout=success",
        "cancel_url": f"{s.frontend_url}/pricing",
        "metadata": {
            "user_id": user["id"],
            **({"visitor_id": visitor_id} if visitor_id else {}),
        },
    }

    if user.get("stripe_customer_id"):
        params["customer"] = user["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
        params["customer_creation"] = "always"

    session = stripe.checkout.Session.create(**params)
    return session.url


async def create_billing_portal_session(user: dict) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    _configure_stripe()
    s = get_settings()

    if not user.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No active subscription")

    session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{s.frontend_url}/pricing",
    )
    return session.url


async def create_report_checkout_session(
    user: dict, address: str | None, lat: float, lon: float,
    pin: str | None = None, visitor_id: str | None = None,
) -> str:
    """Create a one-time Stripe Checkout session for a single report ($25).

    ``pin`` keys the purchase to the parcel when known; the address/coord
    fields remain for display and for legacy coordinate-matched entitlement.
    """
    _configure_stripe()
    s = get_settings()

    if not s.stripe_price_id_report:
        raise HTTPException(status_code=503, detail="Report purchase not configured")

    if pin:
        return_query = f"pin={quote_plus(pin)}"
    else:
        return_query = f"address={quote_plus(address or '')}"
    params: dict = {
        "mode": "payment",
        "line_items": [{"price": s.stripe_price_id_report, "quantity": 1}],
        "success_url": f"{s.frontend_url}/scorecard?{return_query}&report_purchased=1",
        "cancel_url": f"{s.frontend_url}/scorecard?{return_query}",
        "metadata": {
            "user_id": user["id"],
            "purchase_type": "report",
            "address": address or "",
            "lat": str(round(lat, 4)),
            "lon": str(round(lon, 4)),
            **({"pin": pin} if pin else {}),
            **({"visitor_id": visitor_id} if visitor_id else {}),
        },
    }

    if user.get("stripe_customer_id"):
        params["customer"] = user["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
        params["customer_creation"] = "always"

    session = stripe.checkout.Session.create(**params)

    await db.save_report_purchase(
        user_id=user["id"],
        stripe_session_id=session.id,
        address=address,
        lat=lat,
        lon=lon,
        pin=pin,
    )

    return session.url


async def handle_webhook(request: Request) -> dict:
    """Process a Stripe webhook event."""
    _configure_stripe()
    s = get_settings()

    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not s.stripe_webhook_secret:
        log.warning("Stripe webhook secret not configured, skipping verification")
        import json
        event = stripe.Event.construct_from(json.loads(body), stripe.api_key)
    else:
        try:
            event = stripe.Webhook.construct_event(body, sig, s.stripe_webhook_secret)
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    else:
        log.debug("Unhandled Stripe event: %s", event_type)

    return {"received": True}


async def _handle_checkout_completed(session: dict) -> None:
    mode = session.get("mode")
    if mode == "payment":
        await _handle_report_purchase_completed(session)
    else:
        await _handle_subscription_checkout_completed(session)


async def _handle_subscription_checkout_completed(session: dict) -> None:
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        log.error("Checkout session missing user_id metadata")
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    await db.update_user_stripe(user_id, customer_id, subscription_id)
    await db.update_user_tier(user_id, "premium")
    log.info("User %s upgraded to premium (customer=%s)", user_id, customer_id)
    await _save_money_event("subscription_started", session)


async def _handle_report_purchase_completed(session: dict) -> None:
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        log.error("Report purchase session missing user_id metadata")
        return

    session_id = session.get("id")
    payment_intent = session.get("payment_intent")
    customer_id = session.get("customer")

    purchase = await db.complete_report_purchase(session_id, payment_intent)

    if customer_id and user_id:
        user = await db.get_user_by_id(user_id)
        if user and not user.get("stripe_customer_id"):
            await db.update_user_stripe(user_id, customer_id, None)

    address = metadata.get("address", "unknown")
    log.info(
        "Report purchased: user=%s address=%s session=%s",
        user_id, address, session_id,
    )
    await _save_money_event("purchase_completed", session)


async def _save_money_event(event_name: str, session: dict) -> None:
    """Write a server-side analytics event for a completed Stripe purchase.

    Money events are never accepted from the browser (main.py allowlist
    excludes them) — the webhook is the only writer, so the funnel's
    purchase step can't be spoofed. save_events never raises.
    """
    metadata = session.get("metadata", {})
    await db.save_events([{
        "session_id": session.get("id") or "stripe",
        "visitor_id": metadata.get("visitor_id"),
        "user_id": metadata.get("user_id"),
        "event_name": event_name,
        "event_data": {
            "purchase_type": metadata.get("purchase_type", "subscription"),
            "amount_total": session.get("amount_total"),
            **({"pin": metadata["pin"]} if metadata.get("pin") else {}),
        },
        "page": None,
        "address": metadata.get("address") or None,
    }])


async def _handle_subscription_updated(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    user = await db.get_user_by_stripe_customer(customer_id)
    if not user:
        log.warning("Subscription update for unknown customer: %s", customer_id)
        return

    status = subscription.get("status")
    if status in ("active", "trialing"):
        await db.update_user_tier(user["id"], "premium")
    elif status in ("past_due", "unpaid", "canceled", "incomplete_expired"):
        await db.update_user_tier(user["id"], "free")
        await db.update_user_stripe(user["id"], customer_id, None)


async def _handle_subscription_deleted(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    user = await db.get_user_by_stripe_customer(customer_id)
    if not user:
        log.warning("Subscription deleted for unknown customer: %s", customer_id)
        return

    await db.update_user_tier(user["id"], "free")
    await db.update_user_stripe(user["id"], customer_id, None)
    log.info("User %s downgraded to free (subscription canceled)", user["id"])


async def cancel_user_subscription(user: dict) -> None:
    """Cancel the user's active Stripe subscription immediately.

    Raises HTTPException(502) when Stripe rejects the cancellation — the
    caller (account deletion) must abort rather than orphan a live
    subscription behind a deleted account. An already-canceled/missing
    subscription counts as success.
    """
    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
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


async def get_subscription_status(user: dict) -> dict:
    """Return current subscription status for the user."""
    result = {
        "tier": user["tier"],
        "stripe_customer_id": user.get("stripe_customer_id"),
        "subscription_active": user["tier"] in ("premium", "admin"),
    }
    return result
