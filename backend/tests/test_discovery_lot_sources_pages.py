"""The lot-source pager retries a dropped connection and a 5xx (the server run of 2026-11-11 died on one)."""

from __future__ import annotations

import httpx
import pytest

from backend.discovery import lot_sources


def _client(answers):
    calls = iter(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        a = next(calls)
        if isinstance(a, Exception):
            raise a
        return httpx.Response(a, json=[{"id": 1}] if a == 200 else {})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(lot_sources.time, "sleep", lambda s: None)


def test_a_dropped_connection_and_a_503_are_retried():
    drop = httpx.RemoteProtocolError("Server disconnected without sending a response.")
    assert lot_sources._pages(_client([drop, 503, 200]), "x", {}, "http://p") == [{"id": 1}]


def test_five_dropped_connections_raise():
    drop = httpx.RemoteProtocolError("gone")
    with pytest.raises(httpx.RemoteProtocolError):
        lot_sources._pages(_client([drop] * 5), "x", {}, "http://p")


def test_five_503s_raise():
    with pytest.raises(httpx.HTTPStatusError):
        lot_sources._pages(_client([503] * 5), "x", {}, "http://p")
