"""A failed chat turn says which step failed and keeps the question (decision Item 72).

Tester report 2026-11-06: every chat answered "Something went wrong while answering. Please try again." The prod
request_logs showed the router failing with Anthropic's "credit balance is too low" 400. Contract: each failed step
streams an `error` naming the step (`error_step`, words in the chat's language); a model-provider outage (credits,
key, overload, unreachable) says chat is temporarily unavailable (`error_kind: unavailable`) and a billing or key
failure raises a Sentry alarm, since it won't fix itself. The exception text never reaches the browser."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import _provider_outage, app
from backend.models import ContextObject, Location, RetrievalPlan

_REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, status: int, message: str):
    resp = httpx.Response(status, request=_REQ, json={"type": "error", "error": {"type": "x", "message": message}})
    return cls(message, response=resp, body=None)


CREDIT = _status_error(
    anthropic.BadRequestError, 400,
    "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.",
)


@pytest.fixture
def client():
    with patch("backend.main.get_settings") as s, patch("backend.main.db") as db:
        s.return_value = MagicMock(
            anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
            router_model="m", synthesizer_model="m", message_limit=10,
        )
        db.init_db = AsyncMock()
        db.close_db = AsyncMock()
        db.count_user_messages = AsyncMock(return_value=0)
        db.save_request_log = AsyncMock()
        yield TestClient(app)


_PLAN = RetrievalPlan(
    sources=["crime_api"],
    location=Location(raw="Wicker Park", type="neighborhood", resolved_community_area=24,
                      resolved_community_area_name="West Town"),
    intent="neighborhood_overview",
)


def _events(client, *, route=None, retrieve=None, stream=None, synth=None, language="en"):
    patches = [
        patch("backend.main.synthesize_query", new_callable=AsyncMock,
              **({"side_effect": synth} if synth else {"return_value": "q"})),
        patch("backend.main.route", new_callable=AsyncMock,
              **({"side_effect": route} if route else {"return_value": _PLAN})),
        patch("backend.main._retrieve", new_callable=AsyncMock,
              **({"side_effect": retrieve} if retrieve else {"return_value": ContextObject(community_area=24)})),
        patch("backend.main._fetch_map_rows", new_callable=AsyncMock, return_value={}),
        patch("backend.main.stream_answer", side_effect=stream or (lambda **kw: _gen(["ok"]))),
    ]
    for p in patches:
        p.start()
    try:
        resp = client.post("/chat", json={"message": "What about Wicker Park?", "history": [], "language": language})
    finally:
        for p in patches:
            p.stop()
    return [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]


def _gen(tokens, then=None):
    async def gen():
        for t in tokens:
            yield t
        if then:
            raise then
    return gen()


def _error(events):
    return next(e for e in events if e["type"] == "error")


@pytest.mark.parametrize("stage, step, words", [
    ("synth", "read", "reading your question"),
    ("route", "route", "working out what to look up"),
    ("retrieve", "gather", "gathering the data"),
    ("stream", "answer", "writing the answer"),
])
def test_each_failed_step_names_itself(client, stage, step, words):
    boom = TypeError("'>' not supported between instances of 'NoneType' and 'int'")
    kwargs = {"stream": lambda **kw: _gen(["half"], boom)} if stage == "stream" else {stage: boom}
    events = _events(client, **kwargs)
    err = _error(events)
    assert err["error_step"] == step and err["error_kind"] == "step"
    assert words in err["error"] and "question is kept" in err["error"]
    assert "NoneType" not in json.dumps(events)  # the exception stays server-side
    assert events[-1]["type"] == "done"


def test_step_error_is_in_spanish_for_a_spanish_chat(client):
    err = _error(_events(client, route=RuntimeError("x"), language="es"))
    assert err["error"] == "La respuesta falló al decidir qué consultar. Su pregunta se conservó: inténtelo de nuevo."


def test_out_of_credits_says_chat_is_unavailable_and_alarms(client):
    sentry = MagicMock()
    with patch.dict(sys.modules, {"sentry_sdk": sentry}):
        err = _error(_events(client, route=CREDIT))
    assert err["error_kind"] == "unavailable" and err["error_step"] == "route"
    assert err["error"].startswith("Chat is temporarily unavailable.")
    assert "credit" not in err["error"].lower()
    sentry.capture_message.assert_called_once()
    assert sentry.capture_message.call_args.kwargs["level"] == "fatal"
    assert "billing" in sentry.capture_message.call_args.args[0]


def test_an_overloaded_provider_is_unavailable_but_does_not_page(client):
    sentry = MagicMock()
    overloaded = _status_error(anthropic.InternalServerError, 529, "Overloaded")
    with patch.dict(sys.modules, {"sentry_sdk": sentry}):
        err = _error(_events(client, stream=lambda **kw: _gen([], overloaded)))
    assert err["error_kind"] == "unavailable" and err["error_step"] == "answer"
    sentry.capture_message.assert_not_called()


@pytest.mark.parametrize("exc, reason", [
    (CREDIT, "billing"),
    (_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"), "auth"),
    (_status_error(anthropic.PermissionDeniedError, 403, "not allowed"), "auth"),
    (_status_error(anthropic.RateLimitError, 429, "rate limited"), "overloaded"),
    (_status_error(anthropic.InternalServerError, 529, "Overloaded"), "overloaded"),
    (_status_error(anthropic.InternalServerError, 500, "boom"), "down"),
    (anthropic.APIConnectionError(request=_REQ), "down"),
    (_status_error(anthropic.BadRequestError, 400, "messages: field required"), None),
    (ValueError("x"), None),
])
def test_provider_outage_classification(exc, reason):
    assert _provider_outage(exc) == reason


def test_a_healthy_turn_has_no_error(client):
    events = _events(client)
    assert not [e for e in events if e["type"] == "error"]
