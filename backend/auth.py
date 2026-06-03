"""Google OAuth2 + JWT session management.

When GOOGLE_CLIENT_ID is not set, auth is disabled and all requests are
treated as an admin user — local dev works without any OAuth setup.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from backend import db
from backend.config import get_settings

log = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _auth_enabled() -> bool:
    return bool(get_settings().google_client_id)


def _jwt_secret() -> str:
    s = get_settings()
    if s.jwt_secret:
        return s.jwt_secret
    return "dev-insecure-key-do-not-use-in-production"


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


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

async def exchange_google_code(code: str, redirect_uri: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        return resp.json()


async def get_google_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_DEV_USER = {
    "id": "dev",
    "email": "dev@localhost",
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


def verify_csrf(request: Request) -> None:
    if not _auth_enabled():
        return
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_token = request.cookies.get("csrf_token", "")
    header_token = request.headers.get("x-csrf-token", "")
    if not cookie_token or cookie_token != header_token:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


# ---------------------------------------------------------------------------
# Auth endpoint handlers
# ---------------------------------------------------------------------------

def _callback_url(request: Request) -> str:
    s = get_settings()
    if s.frontend_url:
        return f"{s.frontend_url.rstrip('/')}/api/auth/google/callback"
    return str(request.url_for("google_callback"))


async def handle_google_login(request: Request) -> RedirectResponse:
    s = get_settings()
    if not _auth_enabled():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Auth not configured")

    state = secrets.token_urlsafe(32)
    callback_url = _callback_url(request)

    params = urlencode({
        "client_id": s.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    })

    response = RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{params}", status_code=302)
    response.set_cookie(
        "oauth_state", state,
        httponly=True, secure=s.auth_cookie_secure,
        samesite="lax", max_age=300,
    )
    return response


async def handle_google_callback(request: Request) -> RedirectResponse:
    s = get_settings()
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("oauth_state")

    from fastapi import HTTPException

    if not code or not state or state != stored_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth callback")

    callback_url = _callback_url(request)
    tokens = await exchange_google_code(code, callback_url)
    userinfo = await get_google_userinfo(tokens["access_token"])

    existing = await db.get_user_by_google_id(str(userinfo["id"]))
    user_id = existing["id"] if existing else str(uuid.uuid4())

    user = await db.upsert_user(
        user_id=user_id,
        email=userinfo["email"],
        name=userinfo.get("name", userinfo["email"]),
        picture_url=userinfo.get("picture"),
        google_id=str(userinfo["id"]),
    )

    access_token = create_access_token(user["id"], user["email"], user["tier"])
    refresh_token = create_refresh_token()
    csrf_token = secrets.token_urlsafe(16)

    await db.save_refresh_token(
        user_id=user["id"],
        token_hash=hash_token(refresh_token),
        expires_at=int(time.time() * 1000) + s.jwt_refresh_token_ttl * 1000,
    )

    response = RedirectResponse(url=s.frontend_url, status_code=302)
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    response.delete_cookie("oauth_state")
    return response


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

    s = get_settings()
    new_access = create_access_token(user["id"], user["email"], user["tier"])
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
                "id": "dev",
                "email": "dev@localhost",
                "name": "Developer",
                "picture_url": None,
                "tier": "admin",
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
    return {"authenticated": False, "auth_required": True, "user": None}


async def handle_logout(request: Request) -> dict:
    token = request.cookies.get("refresh_token")
    if token:
        await db.revoke_refresh_token(hash_token(token))
    return {"ok": True}
