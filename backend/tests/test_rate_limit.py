"""Tests for rate limiting — the only cap on anonymous chat.

Coherence audit step 3 opened anonymous chat (no auth gate in the
frontend), so the anon sliding-window limit and its "Sign in for higher
limits" 429 detail became the product's upgrade nudge. These tests pin
that contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import rate_limit
from backend.main import app


def _anon_request(ip: str = "203.0.113.7") -> MagicMock:
    request = MagicMock()
    request.headers = {}
    request.client.host = ip
    request.cookies = {}
    return request


@pytest.fixture
def _auth_disabled():
    settings = MagicMock()
    settings.google_client_id = ""
    settings.jwt_secret = ""
    with patch("backend.auth.get_settings", return_value=settings):
        yield settings


class TestCheckRateLimit:
    async def test_under_limit_records_and_passes(self, _auth_disabled, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANON_DAY", "3")
        monkeypatch.setenv("RATE_LIMIT_ANON_HOUR", "3")
        await rate_limit.check_rate_limit(_anon_request())
        assert rate_limit._windows["ip:203.0.113.7"].timestamps

    async def test_anon_daily_429_suggests_sign_in(self, _auth_disabled, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANON_DAY", "1")
        monkeypatch.setenv("RATE_LIMIT_ANON_HOUR", "5")
        request = _anon_request()
        await rate_limit.check_rate_limit(request)
        with pytest.raises(HTTPException) as exc_info:
            await rate_limit.check_rate_limit(request)
        assert exc_info.value.status_code == 429
        assert "Sign in for higher limits" in exc_info.value.detail
        assert "Retry-After" in exc_info.value.headers

    async def test_separate_ips_have_separate_windows(self, _auth_disabled, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANON_DAY", "1")
        monkeypatch.setenv("RATE_LIMIT_ANON_HOUR", "5")
        await rate_limit.check_rate_limit(_anon_request("203.0.113.7"))
        # A different IP is not affected by the first IP's window.
        await rate_limit.check_rate_limit(_anon_request("203.0.113.8"))


class TestChatRateLimitHTTP:
    def test_chat_429_carries_detail(self, _auth_disabled, monkeypatch):
        """A rate-limited /chat returns a JSON 429 (not an SSE stream)."""
        monkeypatch.setenv("RATE_LIMIT_ANON_DAY", "1")
        monkeypatch.setenv("RATE_LIMIT_ANON_HOUR", "1")
        # TestClient requests arrive from host "testclient"; pre-fill its window.
        rate_limit._windows["ip:testclient"].record()
        client = TestClient(app)
        resp = client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 429
        assert "Sign in for higher limits" in resp.json()["detail"]
