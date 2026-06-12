"""HTTP-level auth tests for the conversation endpoints.

Coherence audit step 3: anonymous chat is open (rate-limited), but
conversation persistence requires a signed-in user when auth is enabled.
Without this, anonymous visitors would all share the user_id=NULL pool —
seeing and deleting each other's conversations.

Dev mode (GOOGLE_CLIENT_ID unset) is unaffected: require_auth resolves to
the dev user, and the user_id IS NULL fallback keeps legacy rows visible.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import auth, db
from backend.main import app

CSRF_TOKEN = "csrf-test"
CSRF_HEADERS = {"x-csrf-token": CSRF_TOKEN}


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Fresh SQLite database for each test."""
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


@pytest.fixture
def _auth_disabled():
    settings = MagicMock()
    settings.google_client_id = ""
    settings.jwt_secret = ""
    settings.jwt_access_token_ttl = 900
    settings.jwt_refresh_token_ttl = 604800
    settings.auth_cookie_secure = False
    settings.frontend_url = "http://localhost:5173"
    with patch("backend.auth.get_settings", return_value=settings):
        yield settings


def _make_client(user_id: str | None = None, email: str = "", tier: str = "free") -> TestClient:
    """TestClient with CSRF cookie set; optionally signed in as user_id."""
    client = TestClient(app)
    client.cookies.set("csrf_token", CSRF_TOKEN)
    if user_id is not None:
        client.cookies.set("access_token", auth.create_access_token(user_id, email, tier))
    return client


# ---------------------------------------------------------------------------
# Auth enabled, no session → 401 on every conversation endpoint
# ---------------------------------------------------------------------------

class TestAnonymousRejected:
    @pytest.mark.parametrize(
        "method,path,kwargs",
        [
            ("GET", "/api/conversations", {}),
            ("POST", "/api/conversations", {"json": {"id": "c1", "title": "t"}}),
            ("GET", "/api/conversations/c1", {}),
            ("DELETE", "/api/conversations/c1", {}),
            ("PUT", "/api/conversations/c1/messages", {"json": {"messages": []}}),
            ("PATCH", "/api/conversations/c1/messages/0", {"json": {"map_data": {}}}),
            ("POST", "/api/conversations/import", {"json": {"conversations": []}}),
            ("DELETE", "/api/conversations", {}),
            ("GET", "/api/conversations/c1/share", {}),
            (
                "POST",
                "/api/conversations/c1/uploads",
                {"files": {"files": ("t.txt", b"x", "text/plain")}},
            ),
        ],
    )
    async def test_returns_401(self, _auth_enabled, test_db, method, path, kwargs):
        client = _make_client()
        resp = client.request(method, path, headers=CSRF_HEADERS, **kwargs)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Auth enabled: users cannot see or mutate each other's conversations
# ---------------------------------------------------------------------------

class TestOwnership:
    async def _two_users(self):
        await db.upsert_user("user-a", "a@example.com", "Alice", None, "ga")
        await db.upsert_user("user-b", "b@example.com", "Bob", None, "gb")
        return (
            _make_client("user-a", "a@example.com"),
            _make_client("user-b", "b@example.com"),
        )

    async def test_other_user_gets_404(self, _auth_enabled, test_db):
        client_a, client_b = await self._two_users()
        resp = client_a.post(
            "/api/conversations",
            json={"id": "conv_a", "title": "A's research"},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 201

        assert client_a.get("/api/conversations/conv_a").status_code == 200
        assert client_b.get("/api/conversations/conv_a").status_code == 404
        assert (
            client_b.delete("/api/conversations/conv_a", headers=CSRF_HEADERS).status_code
            == 404
        )
        # PATCH ownership check (previously missing entirely)
        resp = client_b.patch(
            "/api/conversations/conv_a/messages/0",
            json={"map_data": {}},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 404

    async def test_list_is_scoped(self, _auth_enabled, test_db):
        client_a, client_b = await self._two_users()
        client_a.post(
            "/api/conversations",
            json={"id": "conv_a", "title": "A's research"},
            headers=CSRF_HEADERS,
        )
        ids_b = [c["id"] for c in client_b.get("/api/conversations").json()]
        assert "conv_a" not in ids_b
        ids_a = [c["id"] for c in client_a.get("/api/conversations").json()]
        assert "conv_a" in ids_a

    async def test_owner_can_patch_own(self, _auth_enabled, test_db):
        client_a, _ = await self._two_users()
        client_a.post(
            "/api/conversations",
            json={"id": "conv_a", "title": "A"},
            headers=CSRF_HEADERS,
        )
        client_a.put(
            "/api/conversations/conv_a/messages",
            json={"messages": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ]},
            headers=CSRF_HEADERS,
        )
        resp = client_a.patch(
            "/api/conversations/conv_a/messages/1",
            json={"map_data": {"crime": []}},
            headers=CSRF_HEADERS,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CSRF bootstrap: anonymous visitors get the double-submit cookie on /me
# (without it, anon POST /chat is blocked by CSRFMiddleware in production)
# ---------------------------------------------------------------------------

class TestCsrfBootstrap:
    async def test_me_issues_csrf_cookie_to_anonymous(self, _auth_enabled, test_db):
        client = TestClient(app)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.cookies.get("csrf_token")

    async def test_me_keeps_existing_csrf_cookie(self, _auth_enabled, test_db):
        client = TestClient(app)
        client.cookies.set("csrf_token", "existing-token")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert "csrf_token" not in resp.cookies  # not re-issued

    async def test_anon_chat_passes_csrf_with_bootstrap_pair(self, _auth_enabled, test_db):
        """The cookie+header pair from the bootstrap must satisfy the middleware
        (the request then proceeds into /chat — rate limiting, not 403)."""
        client = TestClient(app)
        token = client.get("/api/auth/me").cookies["csrf_token"]
        client.cookies.set("csrf_token", token)
        # Pre-fill the anon rate-limit window so /chat 429s instead of
        # invoking the real pipeline; 429 proves CSRF passed.
        from backend import rate_limit
        for _ in range(5):
            rate_limit._windows["ip:testclient"].record()
        resp = client.post("/chat", json={"message": "hi"}, headers={"x-csrf-token": token})
        assert resp.status_code == 429  # not 403


# ---------------------------------------------------------------------------
# Dev mode (auth disabled): everything keeps working, NULL rows visible
# ---------------------------------------------------------------------------

class TestDevMode:
    async def test_round_trip(self, _auth_disabled, test_db):
        client = _make_client()
        resp = client.post("/api/conversations", json={"id": "c1", "title": "dev conv"})
        assert resp.status_code == 201
        ids = [c["id"] for c in client.get("/api/conversations").json()]
        assert "c1" in ids

    async def test_legacy_null_rows_visible_and_deletable(self, _auth_disabled, test_db):
        await db.create_conversation("legacy", "old anon row", None)
        client = _make_client()
        ids = [c["id"] for c in client.get("/api/conversations").json()]
        assert "legacy" in ids
        assert client.delete("/api/conversations/legacy").status_code == 200
