"""Tests for the auth module: JWT, refresh tokens, user DB, endpoints, dev mode."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from backend import auth, db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Initialise a fresh SQLite database for each test."""
    mock_settings = MagicMock()
    mock_settings.db_path = tmp_path / "test.db"
    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield
        await db.close_db()


@pytest.fixture
def _auth_settings():
    """Patch get_settings for auth module with test values."""
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
    """Patch get_settings so auth is disabled (empty google_client_id)."""
    settings = MagicMock()
    settings.google_client_id = ""
    settings.jwt_secret = ""
    settings.jwt_access_token_ttl = 900
    settings.jwt_refresh_token_ttl = 604800
    settings.auth_cookie_secure = False
    settings.frontend_url = "http://localhost:5173"
    with patch("backend.auth.get_settings", return_value=settings):
        yield settings


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

class TestJWT:
    def test_create_and_decode(self, _auth_settings):
        token = auth.create_access_token("user-1", "test@example.com", "free")
        payload = auth.decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"
        assert payload["email"] == "test@example.com"
        assert payload["tier"] == "free"

    def test_expired_token_returns_none(self, _auth_settings):
        _auth_settings.jwt_access_token_ttl = -1
        token = auth.create_access_token("user-1", "test@example.com", "free")
        assert auth.decode_access_token(token) is None

    def test_tampered_token_returns_none(self, _auth_settings):
        token = auth.create_access_token("user-1", "test@example.com", "free")
        assert auth.decode_access_token(token + "tampered") is None


class TestRefreshToken:
    def test_create_is_url_safe(self):
        token = auth.create_refresh_token()
        assert len(token) > 20
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_hash_is_deterministic(self):
        token = "test-token-123"
        assert auth.hash_token(token) == auth.hash_token(token)
        assert auth.hash_token(token) != auth.hash_token(token + "x")


# ---------------------------------------------------------------------------
# User DB operations
# ---------------------------------------------------------------------------

class TestUserDB:
    @pytest.mark.asyncio
    async def test_upsert_creates_user(self, test_db):
        user = await db.upsert_user(
            user_id="u1", email="a@b.com", name="Alice",
            picture_url=None, google_id="g1",
        )
        assert user["email"] == "a@b.com"
        assert user["tier"] == "free"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.upsert_user("u1", "a@new.com", "Alice B", "pic.jpg", "g1")
        assert user["email"] == "a@new.com"
        assert user["name"] == "Alice B"

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_id("u1")
        assert user is not None
        assert user["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, test_db):
        assert await db.get_user_by_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_user_by_google_id(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        user = await db.get_user_by_google_id("g1")
        assert user is not None
        assert user["id"] == "u1"


# ---------------------------------------------------------------------------
# Refresh token DB operations
# ---------------------------------------------------------------------------

class TestRefreshTokenDB:
    @pytest.mark.asyncio
    async def test_save_and_get(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        h = auth.hash_token("tok1")
        expires = int(time.time() * 1000) + 999999999
        await db.save_refresh_token("u1", h, expires)
        found = await db.get_refresh_token(h)
        assert found is not None
        assert found["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_revoked_token_not_found(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        h = auth.hash_token("tok1")
        expires = int(time.time() * 1000) + 999999999
        await db.save_refresh_token("u1", h, expires)
        await db.revoke_refresh_token(h)
        assert await db.get_refresh_token(h) is None

    @pytest.mark.asyncio
    async def test_expired_token_not_found(self, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        h = auth.hash_token("tok1")
        expired_at = int(time.time() * 1000) - 1000
        await db.save_refresh_token("u1", h, expired_at)
        assert await db.get_refresh_token(h) is None


# ---------------------------------------------------------------------------
# Dependencies (dev mode)
# ---------------------------------------------------------------------------

class TestDevMode:
    @pytest.mark.asyncio
    async def test_get_current_user_returns_dev_user(self, _auth_disabled):
        request = MagicMock()
        user = await auth.get_current_user(request)
        assert user is not None
        assert user["id"] == "dev"
        assert user["tier"] == "admin"

    @pytest.mark.asyncio
    async def test_require_auth_passes_in_dev(self, _auth_disabled):
        request = MagicMock()
        user = await auth.require_auth(request)
        assert user["tier"] == "admin"

    @pytest.mark.asyncio
    async def test_require_admin_passes_in_dev(self, _auth_disabled):
        request = MagicMock()
        user = await auth.require_admin(request)
        assert user["tier"] == "admin"

    def test_csrf_skipped_in_dev(self, _auth_disabled):
        request = MagicMock()
        request.method = "POST"
        request.cookies = {}
        request.headers = {}
        assert auth.csrf_check(request) is True

    @pytest.mark.asyncio
    async def test_me_returns_not_required(self, _auth_disabled):
        request = MagicMock()
        result = await auth.handle_me(request)
        assert result["authenticated"] is True
        assert result["auth_required"] is False


# ---------------------------------------------------------------------------
# Dependencies (auth enabled)
# ---------------------------------------------------------------------------

class TestAuthEnabled:
    @pytest.mark.asyncio
    async def test_no_token_returns_none(self, _auth_settings):
        request = MagicMock()
        request.cookies = {}
        user = await auth.get_current_user(request)
        assert user is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        token = auth.create_access_token("u1", "a@b.com", "free")
        request = MagicMock()
        request.cookies = {"access_token": token}
        user = await auth.get_current_user(request)
        assert user is not None
        assert user["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_require_auth_raises_401(self, _auth_settings):
        request = MagicMock()
        request.cookies = {}
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_admin_raises_403(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", None, "g1")
        token = auth.create_access_token("u1", "a@b.com", "free")
        request = MagicMock()
        request.cookies = {"access_token": token}
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_admin(request)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_csrf_passes_on_get(self, _auth_settings):
        request = MagicMock()
        request.method = "GET"
        assert auth.csrf_check(request) is True

    def test_csrf_blocks_missing_header(self, _auth_settings):
        request = MagicMock()
        request.method = "POST"
        request.cookies = {"csrf_token": "abc"}
        request.headers = {}
        assert auth.csrf_check(request) is False

    def test_csrf_passes_matching(self, _auth_settings):
        request = MagicMock()
        request.method = "POST"
        request.cookies = {"csrf_token": "abc123"}
        request.headers = {"x-csrf-token": "abc123"}
        assert auth.csrf_check(request) is True

    def test_csrf_blocks_mismatch(self, _auth_settings):
        request = MagicMock()
        request.method = "POST"
        request.cookies = {"csrf_token": "abc"}
        request.headers = {"x-csrf-token": "xyz"}
        assert auth.csrf_check(request) is False


# ---------------------------------------------------------------------------
# handle_me endpoint
# ---------------------------------------------------------------------------

class TestHandleMe:
    @pytest.mark.asyncio
    async def test_authenticated_user(self, _auth_settings, test_db):
        await db.upsert_user("u1", "a@b.com", "Alice", "pic.jpg", "g1")
        token = auth.create_access_token("u1", "a@b.com", "free")
        request = MagicMock()
        request.cookies = {"access_token": token}
        result = await auth.handle_me(request)
        assert result["authenticated"] is True
        assert result["auth_required"] is True
        assert result["user"]["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_unauthenticated(self, _auth_settings):
        request = MagicMock()
        request.cookies = {}
        result = await auth.handle_me(request)
        assert result["authenticated"] is False
        assert result["user"] is None
