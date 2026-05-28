import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    ChatChunk,
    CodeChunk,
    ContextObject,
    CrimeSummary,
    Location,
    RetrievalPlan,
)


@pytest.fixture
def client():
    with patch("backend.main.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            anthropic_api_key="test-key",
            socrata_app_token="test-token",
            qdrant_url="http://localhost:6333",
            router_model="claude-sonnet-4-6",
            synthesizer_model="claude-sonnet-4-6",
        )
        yield TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


class TestAutocompleteEndpoint:
    def test_autocomplete_returns_empty_for_short_query(self, client):
        response = client.get("/autocomplete?q=ab")
        assert response.status_code == 200
        assert response.json() == []

    def test_autocomplete_calls_geocode_suggestions(self, client):
        with patch("backend.main.geocode_address_suggestions", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = [
                {"address": "2400 N MILWAUKEE AVE, CHICAGO, IL", "lat": 41.92, "lon": -87.70}
            ]
            response = client.get("/autocomplete?q=2400+N+Milwaukee")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "MILWAUKEE" in data[0]["address"]

    def test_autocomplete_returns_empty_on_no_results(self, client):
        with patch("backend.main.geocode_address_suggestions", new_callable=AsyncMock) as mock_geo:
            mock_geo.return_value = []
            response = client.get("/autocomplete?q=xyznonexistent")

        assert response.status_code == 200
        assert response.json() == []


class TestChatEndpoint:
    @pytest.fixture
    def mock_plan(self):
        return RetrievalPlan(
            sources=["crime_api"],
            location=Location(
                raw="Wicker Park",
                type="neighborhood",
                resolved_community_area=24,
                resolved_community_area_name="West Town",
            ),
            intent="neighborhood_overview",
            time_range_days=90,
            requires_disclaimer=False,
        )

    @pytest.fixture
    def mock_context(self):
        return ContextObject(
            community_area=24,
            community_area_name="West Town",
            crime_last_90d=CrimeSummary(
                total=100,
                arrest_rate=0.15,
                by_type={"THEFT": 40, "BATTERY": 30, "BURGLARY": 30},
            ),
            data_lag_note="Crime data may lag by up to 7 days.",
        )

    def test_chat_returns_sse_content_type(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Test response."

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_chat_streams_plan_event(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Response."

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        events = _parse_sse_events(response.text)
        plan_events = [e for e in events if e.get("type") == "plan"]
        assert len(plan_events) == 1
        assert plan_events[0]["plan"]["location"]["raw"] == "Wicker Park"

    def test_chat_streams_context_event(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Response."

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        events = _parse_sse_events(response.text)
        context_events = [e for e in events if e.get("type") == "context"]
        assert len(context_events) == 1
        assert context_events[0]["context"]["community_area"] == 24

    def test_chat_streams_token_events(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Hello "
                        yield "World"

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        events = _parse_sse_events(response.text)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) == 2
        assert token_events[0]["text"] == "Hello "
        assert token_events[1]["text"] == "World"

    def test_chat_streams_done_event(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Response."

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

    def test_chat_clarification_needed_skips_retrieval(self, client):
        clarification_plan = RetrievalPlan(
            sources=[],
            location=Location(raw="", type="none"),
            intent="clarification_needed",
            clarification="Which neighborhood are you asking about?",
        )

        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                mock_route.return_value = clarification_plan

                response = client.post(
                    "/chat",
                    json={"message": "What's the crime like?", "history": []},
                )

        mock_retrieve.assert_not_called()
        events = _parse_sse_events(response.text)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) == 1
        assert "neighborhood" in token_events[0]["text"].lower()

    def test_chat_router_error_returns_error_event(self, client):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            mock_route.side_effect = Exception("Router exploded")

            response = client.post(
                "/chat",
                json={"message": "Test message", "history": []},
            )

        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "Router failed" in error_events[0]["error"]

    def test_chat_includes_timing(self, client, mock_plan, mock_context):
        with patch("backend.main.route", new_callable=AsyncMock) as mock_route:
            with patch("backend.main._retrieve", new_callable=AsyncMock) as mock_retrieve:
                with patch("backend.main.stream_answer") as mock_stream:
                    mock_route.return_value = mock_plan
                    mock_retrieve.return_value = mock_context

                    async def fake_stream(**kwargs):
                        yield "Response."

                    mock_stream.return_value = fake_stream()

                    response = client.post(
                        "/chat",
                        json={"message": "What's happening in Wicker Park?", "history": []},
                    )

        events = _parse_sse_events(response.text)
        plan_event = next(e for e in events if e.get("type") == "plan")
        assert "t_ms" in plan_event
        assert isinstance(plan_event["t_ms"], int)


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events
