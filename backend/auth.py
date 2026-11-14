"""Sessions (our own JWT + rotating refresh token) and the auth dependencies.

Sign-in itself (Google, Apple, Microsoft; never email) lives in ``backend/identity/`` (Phase 9, Item 121).
When no provider is set up and the local test sign-in is off, auth is disabled and every request is treated as an
admin user, so local dev works without any OAuth setup.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time

import jwt
from fastapi import Request, Response

from backend import db
from backend.config import _DEV_JWT_SECRET, get_settings

log = logging.getLogger(__name__)


def _auth_enabled() -> bool:
    s = get_settings()
    if s.google_client_id or s.microsoft_client_id or s.apple_client_id:
        return True
    from backend.identity.providers import dev_login_allowed
    return dev_login_allowed()


def _jwt_secret() -> str:
    s = get_settings()
    if s.jwt_secret:
        return s.jwt_secret
    # Development only: production refuses to start without a real secret
    # (config.validate_production).
    return _DEV_JWT_SECRET


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str, tier: str) -> str:
    s = get_settings()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "iat": now,
        "exp": now + s.jwt_access_token_ttl,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Cookie management
# ---------------------------------------------------------------------------

def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    s = get_settings()
    secure = s.auth_cookie_secure
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=secure, samesite="lax",
        path="/", max_age=s.jwt_access_token_ttl,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=secure, samesite="lax",
        path="/api/auth", max_age=s.jwt_refresh_token_ttl,
    )
    response.set_cookie(
        "csrf_token", csrf_token,
        httponly=False, secure=secure, samesite="lax",
        path="/", max_age=s.jwt_access_token_ttl,
    )


def clear_auth_cookies(response: Response) -> None:
    for name, path in [
        ("access_token", "/"),
        ("refresh_token", "/api/auth"),
        ("csrf_token", "/"),
    ]:
        response.delete_cookie(name, path=path)


async def issue_session(response: Response, user: dict) -> None:
    """Start a session for ``user`` on ``response``: access JWT, a stored refresh token, a CSRF cookie."""
    s = get_settings()
    access_token = create_access_token(user["id"], user.get("email") or "", user["tier"])
    refresh_token = create_refresh_token()
    await db.save_refresh_token(
        user_id=user["id"],
        token_hash=hash_token(refresh_token),
        expires_at=int(time.time() * 1000) + s.jwt_refresh_token_ttl * 1000,
    )
    set_auth_cookies(response, access_token, refresh_token, secrets.token_urlsafe(16))


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_DEV_USER = {
    "id": "dev",
    # example.com, not localhost — Stripe rejects "dev@localhost" as an invalid
    # email, which 500s every dev-mode checkout before the session is created.
    "email": "dev@example.com",
    "name": "Developer",
    "picture_url": None,
    "google_id": "dev",
    "tier": "admin",
}


async def get_current_user(request: Request) -> dict | None:
    if not _auth_enabled():
        return _DEV_USER

    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user = await db.get_user_by_id(payload["sub"])
    if user is None:
        return None
    return _apply_comp_premium(await _with_subscription(user))


# A subscription in these states is Pro. past_due = Stripe is still retrying the card (owner, Item 123: keep Pro
# until Stripe gives up, which moves it to unpaid or canceled).
PRO_STATUSES = frozenset({"active", "trialing", "past_due"})


async def _with_subscription(user: dict) -> dict:
    """Attach the account's Stripe subscription state (``subscription``) and derive Pro from it. Webhooks never
    write ``users.tier`` (Item 123), so ``admin`` stays admin whatever happens at Stripe."""
    try:
        sub = await db.get_subscription(user["id"])
    except Exception:  # noqa: BLE001 — a missing table (old test databases) is "no subscription"
        sub = None
    user = {**user, "subscription": sub}
    if sub and sub.get("status") in PRO_STATUSES and user.get("tier") == "free":
        user["tier"] = "premium"
        user["paid_premium"] = True
    return user


def _apply_comp_premium(user: dict | None) -> dict | None:
    """Effective tier: an unexpired premium_until grants premium to a free user.

    This is the single choke point — every gate (report, discovery, rate
    limits, require_tier) reads the dict returned here. The tier COLUMN stays
    'free', so Stripe webhooks and the CHECK constraint are untouched;
    comp_premium marks the grant so /api/subscription can distinguish it
    from a real subscription.
    """
    if (
        user
        and user.get("tier") == "free"
        and (user.get("premium_until") or 0) > int(time.time() * 1000)
    ):
        return {**user, "tier": "premium", "comp_premium": True}
    return user


async def require_auth(request: Request) -> dict:
    user = await get_current_user(request)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(request: Request) -> dict:
    user = await require_auth(request)
    if user["tier"] != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


_TIER_ORDER = {"free": 0, "premium": 1, "admin": 2}


def require_tier(minimum: str):
    async def _check(request: Request) -> dict:
        from fastapi import HTTPException
        user = await require_auth(request)
        if _TIER_ORDER.get(user["tier"], 0) < _TIER_ORDER[minimum]:
            raise HTTPException(
                status_code=403,
                detail={"error": "upgrade_required", "required_tier": minimum},
            )
        return user
    return _check


def csrf_check(request: Request) -> bool:
    """Double-submit CSRF check: True when the request may proceed.

    The single source of truth for CSRF validation — CSRFMiddleware in main.py
    consumes this. Skipped (True) in dev mode and for safe methods.
    """
    if not _auth_enabled():
        return True
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    cookie_token = request.cookies.get("csrf_token", "")
    header_token = request.headers.get("x-csrf-token", "")
    return bool(cookie_token) and cookie_token == header_token


# ---------------------------------------------------------------------------
# Auth endpoint handlers
# ---------------------------------------------------------------------------

async def handle_refresh(request: Request) -> dict:
    from fastapi import HTTPException

    old_token = request.cookies.get("refresh_token")
    if not old_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_data = await db.get_refresh_token(hash_token(old_token))
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    await db.revoke_refresh_token(hash_token(old_token))

    user = await db.get_user_by_id(token_data["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # The plan the page shows right after a refresh: a subscription or a voucher, like every other request.
    user = _apply_comp_premium(await _with_subscription(user))

    s = get_settings()
    new_access = create_access_token(user["id"], user.get("email") or "", user["tier"])
    new_refresh = create_refresh_token()
    csrf = secrets.token_urlsafe(16)

    await db.save_refresh_token(
        user_id=user["id"],
        token_hash=hash_token(new_refresh),
        expires_at=int(time.time() * 1000) + s.jwt_refresh_token_ttl * 1000,
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "csrf_token": csrf,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "picture_url": user.get("picture_url"),
            "tier": user["tier"],
        },
    }


async def handle_me(request: Request) -> dict:
    if not _auth_enabled():
        return {
            "authenticated": True,
            "auth_required": False,
            "user": {
                "id": _DEV_USER["id"],
                "email": _DEV_USER["email"],
                "name": _DEV_USER["name"],
                "picture_url": _DEV_USER["picture_url"],
                "tier": _DEV_USER["tier"],
            },
        }

    user = await get_current_user(request)
    if user:
        return {
            "authenticated": True,
            "auth_required": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "picture_url": user.get("picture_url"),
                "tier": user["tier"],
            },
        }
    # The refresh cookie is httponly, so the client can't see it. Saying whether
    # one exists lets an anonymous visitor skip a refresh call that can only 401.
    return {
        "authenticated": False,
        "auth_required": True,
        "user": None,
        "can_refresh": bool(request.cookies.get("refresh_token")),
    }


async def handle_logout(request: Request) -> dict:
    token = request.cookies.get("refresh_token")
    if token:
        await db.revoke_refresh_token(hash_token(token))
    return {"ok": True}
