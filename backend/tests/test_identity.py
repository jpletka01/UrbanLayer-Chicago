"""Identity (Phase 9, decision Item 121): Google, Apple and Microsoft sign-in, linking, and the rules around them.

Each test names the rule or threat it covers (plan: plans/2026-11-13_phase-9-identity-plan.md, threat model table).
No network: ID tokens are signed here with a throwaway RSA key and the provider's token endpoint is stubbed.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import sqlite3
import time
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

from backend import db, quotas
from backend.auth import create_access_token
from backend.config import Settings, production_config_errors
from backend.identity import flow, providers, tokens

GOOGLE_ID, MS_ID, APPLE_ID = "google-client", "ms-client", "com.example.web"
TID = "11111111-2222-3333-4444-555555555555"
FRONT = "https://app.example.com"

_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_APPLE_P8 = ec.generate_private_key(ec.SECP256R1()).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()


def _settings(**over) -> Settings:
    base = dict(
        google_client_id=GOOGLE_ID, google_client_secret="gs",
        microsoft_client_id=MS_ID, microsoft_client_secret="ms",
        apple_client_id=APPLE_ID, apple_team_id="TEAM123456", apple_key_id="KEY1234567", apple_private_key=_APPLE_P8,
        jwt_secret="x" * 40, frontend_url=FRONT, auth_callback_base="", auth_dev_login=False,
        auth_cookie_secure=True, environment="development",
    )
    base.update(over)
    return Settings(_env_file=None, **base)


@pytest.fixture
def settings_patch():
    """Patch every module that reads settings for auth; returns a setter for a different Settings."""
    stack = ExitStack()
    current = {"s": _settings()}

    def get():
        return current["s"]

    for target in ("backend.auth.get_settings", "backend.identity.providers.get_settings",
                   "backend.identity.flow.get_settings"):
        stack.enter_context(patch(target, side_effect=get))

    def set_(**over):
        current["s"] = _settings(**over)

    yield set_
    stack.close()


@pytest_asyncio.fixture
async def store(tmp_path):
    s = MagicMock()
    s.db_path = str(tmp_path / "test.db")
    s.upload_dir = tmp_path / "uploads"
    s.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()
        yield
        await db.close_db()


@pytest.fixture(autouse=True)
def signing_key():
    with patch.object(tokens, "key_resolver", lambda provider, token: _RSA.public_key()):
        yield


def _id_token(provider: str, n: str, *, key=_RSA, alg="RS256", **over) -> str:
    now = int(time.time())
    claims = {
        "google": {"iss": "https://accounts.google.com", "aud": GOOGLE_ID, "sub": "g-sub-1",
                   "email": "pat@example.com", "email_verified": True, "name": "Pat"},
        "microsoft": {"iss": f"https://login.microsoftonline.com/{TID}/v2.0", "aud": MS_ID, "sub": "ms-pairwise",
                      "tid": TID, "oid": "oid-1", "email": "pat@example.com", "name": "Pat M"},
        "apple": {"iss": "https://appleid.apple.com", "aud": APPLE_ID, "sub": "apple-sub-1",
                  "email": "pat@example.com", "email_verified": "true"},
    }[provider]
    claims.update(iat=now, exp=now + 600, nonce=n)
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg)


def _client() -> TestClient:
    from backend.main import app
    return TestClient(app, base_url="https://api.example.com", follow_redirects=False)


def _start(c: TestClient, provider: str, next_path: str = "/saved"):
    r = c.get(f"/api/auth/{provider}", params={"next": next_path})
    assert r.status_code == 302, r.text
    q = parse_qs(urlparse(r.headers["location"]).query)
    return r, {k: v[0] for k, v in q.items()}


def _record(c: TestClient, provider: str = "google") -> dict:
    name = flow.APPLE_FLOW_COOKIE if provider == "apple" else flow.FLOW_COOKIE
    return flow._unsign(c.cookies.get(name))


def _finish(c: TestClient, provider: str, q: dict, token: str | None = None, **form):
    """Complete the callback with a stubbed token endpoint answering ``token`` (default: a good one)."""
    rec = _record(c, provider)
    tok = token or _id_token(provider, rec["n"])

    async def fake_exchange(p, code, verifier):
        assert code == "the-code"
        if providers.PROVIDERS[p].pkce:
            # PKCE: the verifier we send hashes to the challenge we published.
            assert base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=") == q["code_challenge"]
        return tok

    with patch.object(flow, "_exchange", fake_exchange):
        if provider == "apple":
            # A cross-site POST: the TestClient sends cookies regardless; the attributes are asserted separately.
            return c.post("/api/auth/apple/callback", data={"code": "the-code", "state": q["state"], **form})
        return c.get(f"/api/auth/{provider}/callback", params={"code": "the-code", "state": q["state"]})


def _sign_in(c: TestClient, provider: str, token_over: dict | None = None, **form):
    _, q = _start(c, provider)
    tok = _id_token(provider, _record(c, provider)["n"], **(token_over or {})) if token_over else None
    return _finish(c, provider, q, tok, **form)


async def _count(sql: str, *args) -> int:
    cur = await db._get_db().execute(sql, args)
    return (await cur.fetchone())[0]


# ── Start: the authorization request ──────────────────────────────────────────────────────────────────────────

class TestStart:
    def test_google_request_has_state_nonce_pkce_and_no_offline_access(self, settings_patch, store):
        c = _client()
        r, q = _start(c, "google")
        assert r.headers["location"].startswith("https://accounts.google.com/")
        assert q["state"] and q["nonce"] and q["code_challenge_method"] == "S256"
        assert q["prompt"] == "select_account" and "access_type" not in q
        assert q["redirect_uri"] == f"{FRONT}/api/auth/google/callback"
        rec = _record(c)
        assert rec["s"] == q["state"] and rec["n"] == q["nonce"] and rec["r"] == "/saved" and rec["i"] == "signin"
        cookie = r.headers["set-cookie"]
        assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower() and "Secure" in cookie

    def test_microsoft_uses_common_with_pkce(self, settings_patch, store):
        _, q = _start(_client(), "microsoft")
        assert q["code_challenge_method"] == "S256" and q["scope"] == "openid email profile"

    def test_apple_form_post_and_host_cookie(self, settings_patch, store):
        c = _client()
        r, q = _start(c, "apple")
        assert q["response_mode"] == "form_post" and "code_challenge" not in q and q["nonce"]
        cookie = r.headers["set-cookie"]
        assert cookie.startswith(f"{flow.APPLE_FLOW_COOKIE}=")
        assert "Secure" in cookie and "samesite=none" in cookie.lower() and "HttpOnly" in cookie and "Path=/" in cookie
        assert "Domain" not in cookie

    def test_unconfigured_provider_is_404_and_not_offered(self, settings_patch, store):
        settings_patch(microsoft_client_id="", microsoft_client_secret="")
        c = _client()
        assert c.get("/api/auth/microsoft").status_code == 404
        assert [p["id"] for p in c.get("/api/auth/providers").json()["providers"]] == ["google", "apple"]

    def test_unknown_provider_404(self, settings_patch, store):
        assert _client().get("/api/auth/github").status_code == 404

    def test_fixed_auth_routes_not_shadowed(self, settings_patch, store):
        c = _client()
        assert c.get("/api/auth/me").json()["authenticated"] is False
        assert c.get("/api/auth/providers").status_code == 200


# ── Callback: state ───────────────────────────────────────────────────────────────────────────────────────────

class TestState:
    def _err(self, r) -> str | None:
        return parse_qs(urlparse(r.headers["location"]).query).get("signin_error", [None])[0]

    def test_happy_path_signs_in_and_returns_to_next(self, settings_patch, store):
        c = _client()
        r = _sign_in(c, "google")
        assert r.status_code == 303 and r.headers["location"] == f"{FRONT}/saved"
        set_cookies = r.headers.get_list("set-cookie")
        assert any(h.startswith("access_token=") for h in set_cookies)
        assert any(h.startswith("refresh_token=") for h in set_cookies)
        assert c.get("/api/auth/me").json()["user"]["name"] == "Pat"

    def test_no_cookie_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        c.cookies.clear()
        r = _finish_without_cookie(c, q)
        assert self._err(r) == "expired"

    def test_other_state_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        q["state"] = "attacker-state"
        with patch.object(flow, "_exchange", side_effect=AssertionError("must not exchange")):
            r = c.get("/api/auth/google/callback", params={"code": "the-code", "state": q["state"]})
        assert self._err(r) == "expired"

    def test_expired_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        with patch("backend.identity.flow.time.time", return_value=time.time() + flow.FLOW_TTL_S + 5):
            r = c.get("/api/auth/google/callback", params={"code": "the-code", "state": q["state"]})
        assert self._err(r) == "expired"

    def test_reused_state_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        cookie = c.cookies.get(flow.FLOW_COOKIE)
        assert _finish(c, "google", q).headers["location"] == f"{FRONT}/saved"
        c.cookies.set(flow.FLOW_COOKIE, cookie)  # replay the same cookie and state
        r = c.get("/api/auth/google/callback", params={"code": "the-code", "state": q["state"]})
        assert self._err(r) == "expired"

    def test_cookie_for_another_provider_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        r = c.get("/api/auth/microsoft/callback", params={"code": "the-code", "state": q["state"]})
        assert self._err(r) == "expired"

    def test_tampered_cookie_refused(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        rec = _record(c)
        rec["r"] = "//evil.example"
        forged = flow._sign(rec)[:-4] + "0000"
        c.cookies.set(flow.FLOW_COOKIE, forged)
        r = c.get("/api/auth/google/callback", params={"code": "the-code", "state": q["state"]})
        assert self._err(r) == "expired" and r.headers["location"].startswith(f"{FRONT}/?")

    def test_provider_error_is_declined(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")
        r = c.get("/api/auth/google/callback", params={"error": "access_denied", "state": q["state"]})
        assert self._err(r) == "declined" and r.headers["location"].startswith(f"{FRONT}/saved?")


def _finish_without_cookie(c, q):
    with patch.object(flow, "_exchange", side_effect=AssertionError("must not exchange")):
        return c.get("/api/auth/google/callback", params={"code": "the-code", "state": q["state"]})


# ── Callback: the ID token ────────────────────────────────────────────────────────────────────────────────────

class TestIdToken:
    def _refused(self, c, provider, token_factory):
        _, q = _start(c, provider)
        r = _finish(c, provider, q, token_factory(_record(c, provider)["n"]))
        assert parse_qs(urlparse(r.headers["location"]).query)["signin_error"] == ["failed"]
        assert "access_token=" not in r.headers.get("set-cookie", "")

    @pytest.mark.parametrize("over", [
        {"nonce": "someone-elses"},
        {"aud": "another-app"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 3600},
        {"iat": None},
    ])
    def test_google_claims_checked(self, settings_patch, store, over):
        self._refused(_client(), "google", lambda n: _id_token("google", n, **over))

    def test_other_signing_key_refused(self, settings_patch, store):
        self._refused(_client(), "google", lambda n: _id_token("google", n, key=_OTHER_RSA))

    def test_alg_none_refused(self, settings_patch, store):
        def none_token(n):
            now = int(time.time())
            return jwt.encode({"iss": "https://accounts.google.com", "aud": GOOGLE_ID, "sub": "x", "nonce": n,
                               "iat": now, "exp": now + 600}, None, algorithm="none")
        self._refused(_client(), "google", none_token)

    def test_hs256_with_public_key_refused(self, settings_patch, store):
        def confused(n):
            now = int(time.time())
            payload = {"iss": "https://accounts.google.com", "aud": GOOGLE_ID, "sub": "x", "nonce": n,
                       "iat": now, "exp": now + 600}
            header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
            body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
            return (header + b"." + body + b".c2ln").decode()
        self._refused(_client(), "google", confused)

    def test_microsoft_issuer_must_match_its_tenant(self, settings_patch, store):
        other = "99999999-2222-3333-4444-555555555555"
        self._refused(_client(), "microsoft",
                      lambda n: _id_token("microsoft", n, iss=f"https://login.microsoftonline.com/{other}/v2.0"))
        self._refused(_client(), "microsoft",
                      lambda n: _id_token("microsoft", n, tid="not-a-guid",
                                          iss="https://login.microsoftonline.com/not-a-guid/v2.0"))

    def test_token_endpoint_failure_is_failed_not_500(self, settings_patch, store):
        c = _client()
        _, q = _start(c, "google")

        async def boom(*a):
            raise tokens.TokenError("token endpoint 400")
        with patch.object(flow, "_exchange", boom):
            r = c.get("/api/auth/google/callback", params={"code": "c", "state": q["state"]})
        assert "signin_error=failed" in r.headers["location"]


# ── Accounts and email: rules 1, 2, 5 ─────────────────────────────────────────────────────────────────────────

class TestAccounts:
    @pytest.mark.asyncio
    async def test_microsoft_identity_is_tenant_and_oid_and_never_verified(self, settings_patch, store):
        _sign_in(_client(), "microsoft")
        row = await db.get_identity("microsoft", f"{TID}:oid-1")
        assert row and row["tenant"] == TID and row["email_verified"] == 0

    @pytest.mark.asyncio
    async def test_same_email_from_two_providers_is_two_accounts(self, settings_patch, store):
        _sign_in(_client(), "google")
        _sign_in(_client(), "microsoft")
        assert await _count("SELECT COUNT(*) FROM users") == 2
        assert await _count("SELECT COUNT(DISTINCT user_id) FROM identities") == 2

    @pytest.mark.asyncio
    async def test_microsoft_token_claiming_owners_email_gets_nothing_of_theirs(self, settings_patch, store):
        c1 = _client()
        _sign_in(c1, "google")
        owner = c1.get("/api/auth/me").json()["user"]["id"]
        c2 = _client()
        _sign_in(c2, "microsoft", {"oid": "attacker", "email": "pat@example.com"})
        assert c2.get("/api/auth/me").json()["user"]["id"] != owner

    def test_hint_when_both_sides_verified(self, settings_patch, store):
        _sign_in(_client(), "google")
        r = _sign_in(_client(), "apple")
        assert parse_qs(urlparse(r.headers["location"]).query)["signin_hint"] == ["google"]

    def test_no_hint_for_microsoft_relay_or_unverified(self, settings_patch, store):
        _sign_in(_client(), "google")
        assert "signin_hint" not in _sign_in(_client(), "microsoft").headers["location"]
        assert "signin_hint" not in _sign_in(
            _client(), "apple", {"sub": "a2", "email": "x@privaterelay.appleid.com", "is_private_email": "true"}
        ).headers["location"]
        assert "signin_hint" not in _sign_in(_client(), "apple", {"sub": "a3", "email_verified": "false"}).headers["location"]

    def test_no_hint_when_the_other_side_is_microsoft(self, settings_patch, store):
        _sign_in(_client(), "microsoft")
        assert "signin_hint" not in _sign_in(_client(), "google").headers["location"]

    @pytest.mark.asyncio
    async def test_apple_name_only_first_time_and_relay_flag(self, settings_patch, store):
        user_json = json.dumps({"name": {"firstName": "Pat", "lastName": "Lee"}})
        c = _client()
        _sign_in(c, "apple", {"email": "abc@privaterelay.appleid.com", "is_private_email": "true"}, user=user_json)
        assert c.get("/api/auth/me").json()["user"]["name"] == "Pat Lee"
        c2 = _client()
        _sign_in(c2, "apple", {"email": "abc@privaterelay.appleid.com", "is_private_email": "true"})
        assert c2.get("/api/auth/me").json()["user"]["name"] == "Pat Lee"  # not blanked on later sign-ins
        row = await db.get_identity("apple", "apple-sub-1")
        assert row["private_email"] == 1

    @pytest.mark.asyncio
    async def test_returning_identity_same_account(self, settings_patch, store):
        c = _client()
        _sign_in(c, "google")
        first = c.get("/api/auth/me").json()["user"]["id"]
        c2 = _client()
        _sign_in(c2, "google", {"email": "pat.new@example.com"})
        assert c2.get("/api/auth/me").json()["user"]["id"] == first
        assert (await db.get_user_by_id(first))["email"] == "pat.new@example.com"

    @pytest.mark.asyncio
    async def test_twenty_first_sign_ins_at_once_make_one_account(self, store):
        claims = {"provider": "google", "subject": "race", "email": "r@example.com", "email_verified": True}
        results = await asyncio.gather(*(db.sign_in_identity(claims, f"u{i}") for i in range(20)))
        ids = {u["id"] for u, _ in results}
        assert len(ids) == 1 and sum(created for _, created in results) == 1
        assert await _count("SELECT COUNT(*) FROM users") == 1


# ── Linking: rule 3, rule 4 ───────────────────────────────────────────────────────────────────────────────────

def _signed_in(c: TestClient, user_id: str) -> None:
    c.cookies.set("access_token", create_access_token(user_id, "", "free"))
    c.cookies.set("csrf_token", "t")


def _link(c: TestClient, provider: str, token_over: dict | None = None, *, next_path="/settings"):
    r = c.post(f"/api/auth/link/{provider}", json={"next": next_path}, headers={"x-csrf-token": "t"})
    assert r.status_code == 200, r.text
    q = {k: v[0] for k, v in parse_qs(urlparse(r.json()["url"]).query).items()}
    tok = _id_token(provider, _record(c, provider)["n"], **(token_over or {})) if token_over else None
    rec = _record(c, provider)
    assert rec["i"] == "link"
    return _finish(c, provider, q, tok)


def _result(r) -> str | None:
    return parse_qs(urlparse(r.headers["location"]).query).get("link", [None])[0]


class TestLinking:
    @pytest_asyncio.fixture
    async def pat(self, settings_patch, store):
        user, _ = await db.sign_in_identity({"provider": "google", "subject": "g-pat"}, "pat")
        return user

    @pytest.mark.asyncio
    async def test_link_adds_identity_and_both_sign_in(self, pat):
        c = _client()
        _signed_in(c, "pat")
        r = _link(c, "microsoft")
        assert _result(r) == "linked" and r.headers["location"].startswith(f"{FRONT}/settings?")
        assert "access_token=" not in r.headers.get("set-cookie", "")  # linking never starts a new session
        c2 = _client()
        _sign_in(c2, "microsoft")
        assert c2.get("/api/auth/me").json()["user"]["id"] == "pat"
        assert [i["provider"] for i in c.get("/api/auth/identities").json()["identities"]] == ["google", "microsoft"]

    @pytest.mark.asyncio
    async def test_identity_of_another_account_is_refused_and_unchanged(self, pat):
        other, _ = await db.sign_in_identity({"provider": "microsoft", "subject": f"{TID}:oid-1"}, "other")
        c = _client()
        _signed_in(c, "pat")
        assert _result(_link(c, "microsoft")) == "taken"
        row = await db.get_identity("microsoft", f"{TID}:oid-1")
        assert row["user_id"] == "other"
        assert [i["provider"] for i in await db.list_identities("pat")] == ["google"]

    @pytest.mark.asyncio
    async def test_second_identity_from_same_provider_refused(self, pat):
        c = _client()
        _signed_in(c, "pat")
        assert _result(_link(c, "google", {"sub": "another-google"})) == "provider_exists"

    @pytest.mark.asyncio
    async def test_relinking_own_identity(self, pat):
        c = _client()
        _signed_in(c, "pat")
        assert _result(_link(c, "google", {"sub": "g-pat"})) == "already_yours"

    @pytest.mark.asyncio
    async def test_link_needs_session_and_csrf(self, pat):
        c = _client()
        assert c.post("/api/auth/link/microsoft", json={}).status_code in (401, 403)
        _signed_in(c, "pat")
        assert c.post("/api/auth/link/microsoft", json={}).status_code == 403  # no CSRF header

    @pytest.mark.asyncio
    async def test_session_swapped_mid_flow_is_refused(self, pat):
        await db.sign_in_identity({"provider": "google", "subject": "g-mallory"}, "mallory")
        c = _client()
        _signed_in(c, "pat")
        r = c.post("/api/auth/link/microsoft", json={}, headers={"x-csrf-token": "t"})
        q = {k: v[0] for k, v in parse_qs(urlparse(r.json()["url"]).query).items()}
        c.cookies.set("access_token", create_access_token("mallory", "", "free"))
        r = _finish(c, "microsoft", q)
        assert "signin_error=session" in r.headers["location"]
        assert await db.get_identity("microsoft", f"{TID}:oid-1") is None

    @pytest.mark.asyncio
    async def test_apple_link_without_lax_cookie_uses_signed_record(self, pat):
        c = _client()
        _signed_in(c, "pat")
        r = c.post("/api/auth/link/apple", json={}, headers={"x-csrf-token": "t"})
        q = {k: v[0] for k, v in parse_qs(urlparse(r.json()["url"]).query).items()}
        c.cookies.delete("access_token")  # Apple's cross-site POST doesn't carry Lax cookies
        assert _result(_finish(c, "apple", q)) == "linked"

    @pytest.mark.asyncio
    async def test_link_start_for_unoffered_provider_404(self, pat, settings_patch):
        settings_patch(apple_client_id="")
        c = _client()
        _signed_in(c, "pat")
        assert c.post("/api/auth/link/apple", json={}, headers={"x-csrf-token": "t"}).status_code == 404

    @pytest.mark.asyncio
    async def test_remove_refuses_the_last_method(self, pat):
        c = _client()
        _signed_in(c, "pat")
        r = c.delete("/api/auth/identities/google", headers={"x-csrf-token": "t"})
        assert r.status_code == 409 and r.json()["detail"]["error"] == "last_method"
        assert c.delete("/api/auth/identities/apple", headers={"x-csrf-token": "t"}).status_code == 404

    @pytest.mark.asyncio
    async def test_remove_one_of_two(self, pat):
        await db.link_identity("pat", {"provider": "apple", "subject": "a-pat"})
        c = _client()
        _signed_in(c, "pat")
        assert c.delete("/api/auth/identities/google", headers={"x-csrf-token": "t"}).json() == {"ok": True}
        assert [i["provider"] for i in await db.list_identities("pat")] == ["apple"]

    @pytest.mark.asyncio
    async def test_two_removals_at_once_leave_one(self, pat):
        await db.link_identity("pat", {"provider": "apple", "subject": "a-pat"})
        results = await asyncio.gather(db.remove_identity("pat", "google"), db.remove_identity("pat", "apple"))
        assert sorted(results) == ["last", "removed"]
        assert len(await db.list_identities("pat")) == 1

    @pytest.mark.asyncio
    async def test_identities_listing_masks_email(self, pat):
        await db.link_identity("pat", {"provider": "apple", "subject": "a", "email": "z@privaterelay.appleid.com",
                                       "private_email": True})
        await db.link_identity("pat", {"provider": "microsoft", "subject": "m", "email": "patricia@example.com"})
        c = _client()
        _signed_in(c, "pat")
        rows = {i["provider"]: i for i in c.get("/api/auth/identities").json()["identities"]}
        assert rows["microsoft"]["email"] == "p••••••@example.com"
        assert rows["apple"]["email"] is None and rows["apple"]["private_email"] is True

    @pytest.mark.asyncio
    async def test_account_deletion_removes_identities(self, pat):
        await db.delete_user_account("pat")
        assert await _count("SELECT COUNT(*) FROM identities WHERE user_id = 'pat'") == 0


# ── Return path ───────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("/saved", "/saved"),
    ("/c/abc?x=1", "/c/abc?x=1"),
    ("//evil.example", "/"),
    ("/\\evil.example", "/"),
    ("https://evil.example", "/"),
    ("/%2F%2Fevil.example", "/"),
    ("/%5Cevil", "/"),
    ("javascript:alert(1)", "/"),
    ("/ok\r\nSet-Cookie: x=1", "/"),
    ("", "/"),
    (None, "/"),
    ("/" + "a" * 600, "/"),
])
def test_safe_next(raw, expected):
    assert flow.safe_next(raw) == expected


# ── Local test sign-in ────────────────────────────────────────────────────────────────────────────────────────

class TestDevLogin:
    def _local(self, settings_patch, **over):
        settings_patch(**{**dict(google_client_id="", google_client_secret="", microsoft_client_id="",
                                 microsoft_client_secret="", apple_client_id="", auth_dev_login=True,
                                 frontend_url="http://localhost:5197", auth_cookie_secure=False), **over})

    def test_refused_in_production(self):
        s = _settings(auth_dev_login=True, environment="production")
        assert any("AUTH_DEV_LOGIN" in e for e in production_config_errors(s))

    def test_off_unless_localhost(self, settings_patch, store):
        self._local(settings_patch, frontend_url="https://staging.example.com")
        assert _client().get("/api/auth/providers").json()["providers"] == []

    def test_off_in_production_environment_even_on_localhost(self, settings_patch, store):
        self._local(settings_patch, environment="production")
        assert providers.dev_login_allowed() is False

    def test_page_404_when_off(self, settings_patch, store):
        assert _client().get("/api/auth/dev/authorize", params={"provider": "google", "state": "s"}).status_code == 404

    def test_stand_in_sign_in_and_link_end_to_end(self, settings_patch, store):
        self._local(settings_patch)
        c = _client()
        assert [p for p in c.get("/api/auth/providers").json()["providers"]] == [
            {"id": "google", "test": True}, {"id": "apple", "test": True}, {"id": "microsoft", "test": True}]
        r = c.get("/api/auth/google", params={"next": "/saved"})
        page = c.get(r.headers["location"])
        assert page.status_code == 200 and "Test person A" in page.text and "relay" not in page.text.lower()
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        r = c.get("/api/auth/google/callback", params={"code": "dev:a", "state": state})
        assert r.headers["location"] == "http://localhost:5197/saved"
        me = c.get("/api/auth/me").json()["user"]
        assert me["email"] == "test-a@example.com"
        # Link Microsoft's stand-in for the same person: rule 3 through the same callback code.
        c.cookies.set("csrf_token", "t")
        url = c.post("/api/auth/link/microsoft", json={}, headers={"x-csrf-token": "t"}).json()["url"]
        state = parse_qs(urlparse(url).query)["state"][0]
        r = c.get("/api/auth/microsoft/callback", params={"code": "dev:a", "state": state})
        assert "link=linked" in r.headers["location"]

    def test_unknown_test_person_refused(self, settings_patch, store):
        self._local(settings_patch)
        c = _client()
        r = c.get("/api/auth/google")
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        r = c.get("/api/auth/google/callback", params={"code": "dev:relay", "state": state})  # Apple-only person
        assert "signin_error=failed" in r.headers["location"]

    def test_configured_provider_is_real_not_stand_in(self, settings_patch, store):
        self._local(settings_patch, google_client_id=GOOGLE_ID, google_client_secret="gs")
        r = _client().get("/api/auth/google")
        assert r.headers["location"].startswith("https://accounts.google.com/")


# ── Quotas follow the identity (rule 6) ───────────────────────────────────────────────────────────────────────

class TestQuotaCarryOver:
    @pytest.mark.asyncio
    async def test_delete_and_sign_in_again_keeps_the_month(self, settings_patch, store):
        user, _ = await db.sign_in_identity({"provider": "google", "subject": "q"}, "q1")
        for _ in range(7):
            await quotas._take(f"user:{user['id']}", quotas.month_period(), 50)
        await quotas.carry_over_on_delete(user["id"])
        await db.delete_user_account(user["id"])
        again, created = await db.sign_in_identity({"provider": "google", "subject": "q"}, "q2")
        assert created
        await quotas.seed_from_identity(again["id"], "google", "q")
        assert await quotas.used(f"user:{again['id']}", quotas.month_period()) == 7

    @pytest.mark.asyncio
    async def test_other_identity_starts_fresh_and_hash_holds_no_identity(self, settings_patch, store):
        user, _ = await db.sign_in_identity({"provider": "google", "subject": "q"}, "q1")
        await quotas._take(f"user:{user['id']}", quotas.month_period(), 50)
        await quotas.carry_over_on_delete(user["id"])
        cur = await db._get_db().execute("SELECT subject FROM usage_counters WHERE subject LIKE 'idh:%'")
        subjects = [r[0] for r in await cur.fetchall()]
        assert len(subjects) == 1
        assert "google" not in subjects[0] and "q1" not in subjects[0]
        fresh, _ = await db.sign_in_identity({"provider": "google", "subject": "other"}, "o1")
        await quotas.seed_from_identity(fresh["id"], "google", "other")
        assert await quotas.used(f"user:{fresh['id']}", quotas.month_period()) == 0

    @pytest.mark.asyncio
    async def test_sign_in_route_seeds_a_new_account(self, settings_patch, store):
        subject = quotas.identity_subject("google", "g-sub-1")
        await db._get_db().execute(
            "INSERT INTO usage_counters (subject, period, used, updated_at) VALUES (?, ?, 4, 0)",
            (subject, quotas.month_period()),
        )
        await db._get_db().commit()
        c = _client()
        _sign_in(c, "google")
        uid = c.get("/api/auth/me").json()["user"]["id"]
        assert await quotas.used(f"user:{uid}", quotas.month_period()) == 4

    @pytest.mark.asyncio
    async def test_prune_drops_past_months(self, store):
        conn = db._get_db()
        await conn.execute("INSERT INTO usage_counters VALUES ('idh:old', '2020-01', 3, 0)")
        await conn.execute("INSERT INTO usage_counters VALUES ('idh:now', ?, 3, ?)",
                           (quotas.month_period(), int(time.time() * 1000)))
        await conn.commit()
        await quotas.prune()
        cur = await conn.execute("SELECT subject FROM usage_counters WHERE subject LIKE 'idh:%'")
        assert [r[0] for r in await cur.fetchall()] == ["idh:now"]


# ── Secrets stay out of logs ──────────────────────────────────────────────────────────────────────────────────

def test_logs_hold_no_code_token_or_email(settings_patch, store, caplog):
    caplog.set_level(logging.DEBUG)
    c = _client()
    _, q = _start(c, "google")
    tok = _id_token("google", _record(c)["n"])
    _finish(c, "google", q, tok)
    _, q = _start(c, "google")
    _finish(c, "google", q, _id_token("google", "wrong"))
    text = caplog.text
    # Our own loggers only: the test client's request log (and, in production, an access log) shows the callback
    # URL; the code there is single use and already spent.
    text = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("backend"))
    for secret in ("the-code", tok, "pat@example.com", q["state"], q["nonce"]):
        assert secret not in text
    assert "provider=google" in text


# ── Apple's client secret ─────────────────────────────────────────────────────────────────────────────────────

def test_apple_client_secret_is_short_lived_es256(settings_patch):
    secret = providers.client_secret("apple")
    header = jwt.get_unverified_header(secret)
    claims = jwt.decode(secret, options={"verify_signature": False})
    assert header["alg"] == "ES256" and header["kid"] == "KEY1234567"
    assert claims["iss"] == "TEAM123456" and claims["sub"] == APPLE_ID and claims["aud"] == "https://appleid.apple.com"
    assert claims["exp"] - claims["iat"] <= 600


# ── Migration from v18 ────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_v18_database_keeps_users_and_their_rows(tmp_path):
    path = tmp_path / "old.db"
    s = MagicMock()
    s.db_path = str(path)
    s.upload_dir = tmp_path / "u"
    s.report_store_dir = tmp_path / "r"
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()
        await db.close_db()
    # Roll the file back to v18: the old users table (email and google_id NOT NULL UNIQUE), no identities.
    con = sqlite3.connect(path)
    con.executescript("""
        PRAGMA foreign_keys=OFF;
        DROP TABLE identities;
        DROP TABLE users;
        CREATE TABLE users (
            id          TEXT PRIMARY KEY,
            email       TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            picture_url TEXT,
            google_id   TEXT NOT NULL UNIQUE,
            tier        TEXT NOT NULL DEFAULT 'free'
                CHECK(tier IN ('free', 'premium', 'admin')),
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        , stripe_customer_id TEXT, stripe_subscription_id TEXT, premium_until INTEGER);
        INSERT INTO users VALUES ('u1', 'a@example.com', 'A', NULL, 'g1', 'premium', 1, 1, 'cus_1', 'sub_1', NULL);
        INSERT INTO users VALUES ('u2', 'b@example.com', 'B', NULL, 'g2', 'free', 1, 1, NULL, NULL, 99999999999999);
        INSERT INTO saved_lots (id, user_id, lot_key, address, lat, lon, saved_at, updated_at)
            VALUES ('s1', 'u1', 'pin:1', '1 Main', 41.9, -87.7, 1, 1);
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at) VALUES ('u1', 'h', 9999999999999, 1);
        UPDATE schema_version SET version = 18;
    """)
    con.commit()
    con.close()
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()
        try:
            assert await _count("SELECT version FROM schema_version") == db._SCHEMA_VERSION == 19
            u1 = await db.get_user_by_id("u1")
            assert u1["tier"] == "premium" and u1["stripe_customer_id"] == "cus_1"
            assert (await db.get_user_by_id("u2"))["premium_until"] == 99999999999999
            assert await _count("SELECT COUNT(*) FROM saved_lots WHERE user_id = 'u1'") == 1
            assert await _count("SELECT COUNT(*) FROM refresh_tokens WHERE user_id = 'u1'") == 1
            assert (await db.get_identity("google", "g1"))["user_id"] == "u1"
            assert (await db.get_identity("google", "g2"))["user_id"] == "u2"
            assert await _count("SELECT COUNT(*) FROM pragma_foreign_key_check") == 0
            assert await _count("SELECT foreign_keys FROM pragma_foreign_keys") == 1
            # Email is no longer unique: the same address can be another account's (rule 2).
            user, created = await db.sign_in_identity(
                {"provider": "microsoft", "subject": "m", "email": "a@example.com"}, "u3")
            assert created and user["id"] == "u3"
            # Deleting a user still cascades (foreign keys on, and pointing at the rebuilt table).
            await db.delete_user_account("u1")
            assert await _count("SELECT COUNT(*) FROM saved_lots WHERE user_id = 'u1'") == 0
            assert await db.get_identity("google", "g1") is None
        finally:
            await db.close_db()
    with patch("backend.db.get_settings", return_value=s):
        await db.init_db()  # a second start is a no-op
        try:
            assert await _count("SELECT COUNT(*) FROM identities") == 2
        finally:
            await db.close_db()


@pytest.mark.asyncio
async def test_admin_grant_refuses_an_ambiguous_email(store):
    await db.sign_in_identity({"provider": "google", "subject": "g", "email": "same@example.com"}, "a")
    await db.sign_in_identity({"provider": "microsoft", "subject": "m", "email": "same@example.com"}, "b")
    assert {u["id"] for u in await db.users_by_email("SAME@example.com")} == {"a", "b"}
