"""F4: an answer cut off at the synthesizer token cap must say so.

Kit 2026-10-01: 5 of 7 cold-chat answers ended mid-sentence at the 2,000-token
cap and two lost the final question entirely, with nothing to tell the reader.
Contract: the synthesizer reports its stop_reason; on "max_tokens" the chat
stream appends a visible notice (so saved/exported text carries it too) and the
`done` event carries truncated=true. A finished answer carries neither."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import synthesizer
from backend.main import _TRUNCATION_NOTICE, app
from backend.models import ContextObject, Location, RetrievalPlan


# --- the synthesizer reports why the stream ended -----------------------------------

def _fake_stream(chunks, stop_reason):
    async def text_stream():
        for c in chunks:
            yield c

    stream = SimpleNamespace(
        text_stream=text_stream(),
        get_final_message=AsyncMock(return_value=SimpleNamespace(stop_reason=stop_reason)),
    )

    @asynccontextmanager
    async def tracked(**kwargs):
        yield stream

    return tracked


async def _run(stop_reason, outcome):
    with patch.object(synthesizer, "tracked_stream", _fake_stream(["a", "b"], stop_reason)):
        return [
            t async for t in synthesizer.stream_answer(
                context=ContextObject(), user_message="q", history=[], outcome=outcome,
            )
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["max_tokens", "end_turn"])
async def test_stream_answer_reports_stop_reason(reason):
    outcome: dict = {}
    assert await _run(reason, outcome) == ["a", "b"]
    assert outcome["stop_reason"] == reason


@pytest.mark.asyncio
async def test_stream_answer_works_without_an_outcome_holder():
    assert await _run("max_tokens", None) == ["a", "b"]


# --- the chat stream says so -----------------------------------------------------------

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
        yield TestClient(app)


def _chat(client, stop_reason, language="en"):
    plan = RetrievalPlan(
        sources=["crime_api"],
        location=Location(raw="Wicker Park", type="neighborhood", resolved_community_area=24,
                          resolved_community_area_name="West Town"),
        intent="neighborhood_overview",
    )

    def fake_stream_answer(**kwargs):
        async def gen():
            yield "First part. "
            yield "Second part"
            kwargs["outcome"]["stop_reason"] = stop_reason
        return gen()

    with patch("backend.main.route", new_callable=AsyncMock, return_value=plan), \
         patch("backend.main._retrieve", new_callable=AsyncMock, return_value=ContextObject(community_area=24)), \
         patch("backend.main._fetch_map_rows", new_callable=AsyncMock, return_value={}), \
         patch("backend.main.stream_answer", side_effect=fake_stream_answer):
        resp = client.post("/chat", json={"message": "What about Wicker Park?", "history": [], "language": language})
    events = [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]
    text = "".join(e["text"] for e in events if e["type"] == "token")
    done = next(e for e in events if e["type"] == "done")
    return text, done


def test_cut_off_answer_gets_a_visible_notice_and_a_done_flag(client):
    text, done = _chat(client, "max_tokens")
    assert text.endswith(_TRUNCATION_NOTICE["en"]) and "cut off" in text
    assert done["truncated"] is True


def test_notice_is_localized(client):
    text, done = _chat(client, "max_tokens", language="es")
    assert text.endswith(_TRUNCATION_NOTICE["es"]) and done["truncated"] is True


def test_finished_answer_has_no_notice_and_no_flag(client):
    text, done = _chat(client, "end_turn")
    assert text == "First part. Second part"
    assert not done.get("truncated")
