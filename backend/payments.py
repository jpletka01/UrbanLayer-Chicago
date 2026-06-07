"""Stripe payment integration — checkout, webhooks, billing portal."""

from __future__ import annotations

import logging

import stripe
from fastapi import HTTPException, Request

from backend import db
from backend.config import get_settings

log = logging.getLogger(__name__)


def _configure_stripe() -> None:
    s = get_settings()
    stripe.api_key = s.stripe_secret_key


async def create_checkout_session(user: dict) -> str:
    """Create a Stripe Checkout session and return the URL."""
    _configure_stripe()
    s = get_settings()

    if not s.stripe_price_id_pro_monthly:
        raise HTTPException(status_code=503, detail="Payment not configured")

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": s.stripe_price_id_pro_monthly, "quantity": 1}],
        "success_url": f"{s.frontend_url}/?checkout=success",
        "cancel_url": f"{s.frontend_url}/pricing",
        "metadata": {"user_id": user["id"]},
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
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        log.error("Checkout session missing user_id metadata")
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    await db.update_user_stripe(user_id, customer_id, subscription_id)
    await db.update_user_tier(user_id, "premium")
    log.info("User %s upgraded to premium (customer=%s)", user_id, customer_id)


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


async def get_subscription_status(user: dict) -> dict:
    """Return current subscription status for the user."""
    result = {
        "tier": user["tier"],
        "stripe_customer_id": user.get("stripe_customer_id"),
        "subscription_active": user["tier"] in ("premium", "admin"),
    }
    return result
