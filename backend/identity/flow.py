"""One sign-in and linking flow for Google, Apple and Microsoft (Phase 9, decision Item 121).

    GET  /api/auth/{provider}?next=/path       sign in: redirect to the provider
    POST /api/auth/link/{provider}             signed in + CSRF: {url} to add this provider to the account
    GET  /api/auth/{provider}/callback         Google, Microsoft, the local stand-in
    POST /api/auth/apple/callback              Apple (form_post, a cross-site POST)

The state is random, single use, and bound to the browser by an httpOnly cookie holding a signed record of
{state, nonce, PKCE verifier, intent, user id for a link, return path, expiry}. Apple's POST doesn't carry Lax
cookies, so Apple's state cookie alone is ``__Host-`` + Secure + SameSite=None. Errors land on the return path with
``?signin_error=<code>``; tokens, codes and emails are never logged, only provider and outcome.

Rules (owner-approved plan): an account is reached only by (provider, subject); never linked by email; linking is
explicit from a signed-in session and refused when the identity belongs to another account; the last way in can't be
removed; the "you may already have an account" hint only when both sides' emails are provider-verified.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend import db
from backend.auth import _jwt_secret, decode_access_token, issue_session
from backend.config import get_settings
from backend.identity import providers as P
from backend.identity.tokens import TokenError, verify_id_token
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

FLOW_COOKIE = "ul_oauth"
APPLE_FLOW_COOKIE = "__Host-ul_oauth_apple"
FLOW_TTL_S = 600
# States already used in this process: a replayed cookie + code pair is refused even inside its ten minutes.
_used_states = TTLCache(ttl_seconds=FLOW_TTL_S + 60, maxsize=5_000, name="oauth_used_states")


# ---------------------------------------------------------------------------
# Signed flow record
# ---------------------------------------------------------------------------

def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    mac = hmac.new(_jwt_secret().encode(), f"oauth-flow.{body}".encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _unsign(value: str | None) -> dict | None:
    if not value or "." not in value:
        return None
    body, mac = value.rsplit(".", 1)
    good = hmac.new(_jwt_secret().encode(), f"oauth-flow.{body}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, good):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None


def safe_next(path: str | None) -> str:
    """Only a path on this site: starts with one "/", no scheme, host, backslash or control characters."""
    if not path or not isinstance(path, str) or len(path) > 500:
        return "/"
    if not path.startswith("/") or path.startswith("//") or "\\" in path or any(ord(ch) < 32 for ch in path):
        return "/"
    lowered = path.lower()
    if lowered.startswith("/%2f") or lowered.startswith("/%5c"):
        return "/"
    return path


def _with_params(path: str, **params: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{get_settings().frontend_url.rstrip('/')}{path}{sep}{urlencode(params)}"


def _cookie_name(provider: str) -> str:
    return APPLE_FLOW_COOKIE if provider == "apple" and not P.stand_in("apple") else FLOW_COOKIE


def _set_flow_cookie(response, provider: str, value: str) -> None:
    if _cookie_name(provider) == APPLE_FLOW_COOKIE:
        # Apple's answer is a cross-site POST: only SameSite=None rides it, which needs Secure; __Host- pins it to
        # this host and path "/".
        response.set_cookie(APPLE_FLOW_COOKIE, value, max_age=FLOW_TTL_S, httponly=True, secure=True,
                            samesite="none", path="/")
    else:
        response.set_cookie(FLOW_COOKIE, value, max_age=FLOW_TTL_S, httponly=True,
                            secure=get_settings().auth_cookie_secure, samesite="lax", path="/")


def _clear_flow_cookies(response) -> None:
    response.delete_cookie(FLOW_COOKIE, path="/")
    response.delete_cookie(APPLE_FLOW_COOKIE, path="/", secure=True, samesite="none")


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def _require_offered(provider: str) -> None:
    if not P.offered(provider):
        raise HTTPException(status_code=404, detail="Sign-in method not available")


def _authorization(provider: str, intent: str, user_id: str | None, next_path: str) -> tuple[str, str]:
    """(provider URL, signed cookie value) for a new flow."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64) if _pkce(provider) else ""
    record = {"s": state, "n": nonce, "v": verifier, "p": provider, "i": intent, "u": user_id,
              "r": safe_next(next_path), "e": int(time.time()) + FLOW_TTL_S}
    if P.stand_in(provider):
        url = f"/api/auth/dev/authorize?{urlencode({'provider': provider, 'state': state})}"
        return url, _sign(record)
    spec = P.PROVIDERS[provider]
    params = {
        "client_id": P.client_id(provider),
        "redirect_uri": P.callback_url(provider),
        "response_type": "code",
        "scope": spec.scopes,
        "state": state,
        "nonce": nonce,
    }
    if spec.pkce:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params.update(code_challenge=challenge, code_challenge_method="S256")
    if spec.form_post:
        params["response_mode"] = "form_post"
    if provider == "google":
        params["prompt"] = "select_account"
    if provider == "microsoft":
        params["prompt"] = "select_account"
    return f"{spec.authorize_url}?{urlencode(params)}", _sign(record)


def _pkce(provider: str) -> bool:
    return P.PROVIDERS[provider].pkce and not P.stand_in(provider)


async def start_sign_in(request: Request, provider: str) -> RedirectResponse:
    _require_offered(provider)
    url, cookie = _authorization(provider, "signin", None, request.query_params.get("next") or "/")
    if url.startswith("/"):
        url = f"{str(request.base_url).rstrip('/')}{url}"
    response = RedirectResponse(url=url, status_code=302)
    _set_flow_cookie(response, provider, cookie)
    log.info("sign-in started provider=%s", provider)
    return response


async def start_link(request: Request, provider: str, user: dict) -> JSONResponse:
    _require_offered(provider)
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - an empty body is fine
        body = {}
    next_path = body.get("next") if isinstance(body, dict) else None
    url, cookie = _authorization(provider, "link", user["id"], next_path or "/settings")
    if url.startswith("/"):
        url = f"{str(request.base_url).rstrip('/')}{url}"
    response = JSONResponse({"url": url})
    _set_flow_cookie(response, provider, cookie)
    log.info("link started provider=%s", provider)
    return response


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

async def _exchange(provider: str, code: str, verifier: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": P.callback_url(provider),
        "client_id": P.client_id(provider),
        "client_secret": P.client_secret(provider),
    }
    if verifier:
        data["code_verifier"] = verifier
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(P.PROVIDERS[provider].token_url, data=data, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise TokenError(f"token endpoint {resp.status_code}")
    token = resp.json().get("id_token")
    if not token:
        raise TokenError("no id_token")
    return token


def _fail(next_path: str, code: str) -> RedirectResponse:
    response = RedirectResponse(url=_with_params(next_path, signin_error=code), status_code=303)
    _clear_flow_cookies(response)
    return response


async def callback(request: Request, provider: str) -> RedirectResponse:
    if provider not in P.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown sign-in method")
    if request.method == "POST":
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
    else:
        params = dict(request.query_params)

    record = _unsign(request.cookies.get(_cookie_name(provider))) or _unsign(request.cookies.get(FLOW_COOKIE))
    next_path = safe_next(record.get("r")) if record else "/"
    if params.get("error"):
        log.info("sign-in declined provider=%s", provider)
        return _fail(next_path, "declined")
    state = params.get("state") or ""
    if (
        not record
        or record.get("p") != provider
        or not state
        or not hmac.compare_digest(str(record.get("s")), state)
        or int(record.get("e") or 0) < int(time.time())
        or _used_states.get(state) is not None
    ):
        log.warning("sign-in refused provider=%s reason=state", provider)
        return _fail(next_path, "expired")
    _used_states.set(state, True)

    code = params.get("code") or ""
    try:
        if P.stand_in(provider):
            claims = P.dev_claims(provider, code.removeprefix("dev:"))
            if claims is None:
                raise TokenError("unknown test person")
        else:
            if not P.configured(provider) or not code:
                raise TokenError("not configured")
            id_token = await _exchange(provider, code, record.get("v") or "")
            apple_user = None
            if provider == "apple" and params.get("user"):
                try:
                    apple_user = json.loads(params["user"])
                except json.JSONDecodeError:
                    apple_user = None
            claims = await verify_id_token(provider, id_token, record["n"], apple_user=apple_user)
    except TokenError as exc:
        log.warning("sign-in refused provider=%s reason=%s", provider, exc)
        return _fail(next_path, "failed")
    except httpx.HTTPError:
        log.warning("sign-in refused provider=%s reason=provider unreachable", provider)
        return _fail(next_path, "unavailable")

    if record.get("i") == "link":
        return await _finish_link(request, provider, record, claims, next_path)
    return await _finish_sign_in(provider, claims, next_path)


async def _finish_sign_in(provider: str, claims: dict, next_path: str) -> RedirectResponse:
    from backend import quotas

    user, created = await db.sign_in_identity(claims, str(uuid.uuid4()))
    params: dict[str, str] = {}
    if created:
        await quotas.seed_from_identity(user["id"], claims["provider"], claims["subject"])
        if claims.get("email_verified") and not claims.get("private_email") and provider != "microsoft":
            other = await db.verified_email_elsewhere(user["id"], claims.get("email"))
            if other:
                params["signin_hint"] = other
    log.info("signed in provider=%s new_account=%s", provider, created)
    url = _with_params(next_path, **params) if params else f"{get_settings().frontend_url.rstrip('/')}{next_path}"
    response = RedirectResponse(url=url, status_code=303)
    await issue_session(response, user)
    _clear_flow_cookies(response)
    return response


async def _finish_link(request: Request, provider: str, record: dict, claims: dict, next_path: str) -> RedirectResponse:
    user_id = record.get("u")
    # The session that started the link must still be this one. Apple's cross-site POST carries no Lax cookie, and
    # an access token may have lapsed in ten minutes: then the signed record (set by a signed-in, CSRF-checked POST
    # in this browser) is the binding. A different signed-in user is always refused.
    session = decode_access_token(request.cookies.get("access_token") or "")
    if not user_id or (session and session.get("sub") != user_id) or await db.get_user_by_id(user_id) is None:
        log.warning("link refused provider=%s reason=session", provider)
        return _fail(next_path, "session")
    result = await db.link_identity(user_id, claims)
    if result == "linked":
        from backend import entitlements
        await entitlements.carry_on_link(user_id, claims["provider"], claims["subject"])
    log.info("link provider=%s result=%s", provider, result)
    response = RedirectResponse(url=_with_params(next_path, link=result, provider=provider), status_code=303)
    _clear_flow_cookies(response)
    return response


# ---------------------------------------------------------------------------
# Listing and removing
# ---------------------------------------------------------------------------

def _mask(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    if domain.lower() == "privaterelay.appleid.com":
        return None
    return f"{local[:1]}{'•' * max(1, min(len(local) - 1, 6))}@{domain}"


async def identities_for(user: dict) -> dict:
    rows = await db.list_identities(user["id"])
    return {
        "identities": [
            {
                "provider": r["provider"],
                "email": _mask(r.get("email")),
                "private_email": bool(r.get("private_email")),
                "added_at": r["created_at"],
                "last_used_at": r["last_used_at"],
            }
            for r in rows
        ],
        "available": P.available(),
    }


async def remove(user: dict, provider: str) -> dict:
    result = await db.remove_identity(user["id"], provider)
    log.info("sign-in method removal provider=%s result=%s", provider, result)
    if result == "last":
        raise HTTPException(status_code=409, detail={"error": "last_method"})
    if result == "missing":
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Local test stand-in's "provider" page
# ---------------------------------------------------------------------------

def dev_authorize_page(request: Request) -> HTMLResponse:
    provider = request.query_params.get("provider") or ""
    state = request.query_params.get("state") or ""
    if not P.stand_in(provider):
        raise HTTPException(status_code=404, detail="Not found")
    base = str(request.base_url).rstrip("/")
    links = []
    for key, person in P.DEV_PEOPLE.items():
        if P.dev_claims(provider, key) is None:
            continue
        href = f"{base}/api/auth/{provider}/callback?{urlencode({'code': f'dev:{key}', 'state': state})}"
        links.append(f'<li><a href="{html.escape(href)}">{html.escape(person["label"])}</a> '
                     f'<small>{html.escape(person["email"])}</small></li>')
    cancel = f"{base}/api/auth/{provider}/callback?{urlencode({'error': 'access_denied', 'state': state})}"
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Local test sign-in</title>
<style>body{{font:16px system-ui;margin:40px auto;max-width:480px;padding:0 16px}}li{{margin:12px 0}}
small{{color:#666;display:block}}</style></head><body><h1>Local test sign-in</h1>
<p>Stand-in for <b>{html.escape(provider.title())}</b> on this review stack. No real account is used.</p>
<ul>{''.join(links)}</ul><p><a href="{html.escape(cancel)}">Cancel</a></p></body></html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})
