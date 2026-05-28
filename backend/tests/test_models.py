import pytest
from pydantic import ValidationError

from backend.models import (
    ChatChunk,
    ChatRequest,
    CodeChunk,
    ContextObject,
    CrimeSummary,
    Location,
    Message,
    RetrievalPlan,
    ThreeOneOneSummary,
)


class TestLocation:
    def test_defaults(self):
        loc = Location()
        assert loc.raw == ""
        assert loc.type == "none"
        assert loc.resolved_community_area is None
        assert loc.resolved_community_area_name is None

    def test_full_location(self):
        loc = Location(
            raw="Wicker Park",
            type="neighborhood",
            resolved_community_area=24,
            resolved_community_area_name="West Town",
            resolved_address="1600 W Division St",
            resolved_lat=41.903,
            resolved_lon=-87.668,
        )
        assert loc.raw == "Wicker Park"
        assert loc.resolved_community_area == 24

    def test_invalid_location_type_rejected(self):
        with pytest.raises(ValidationError):
            Location(type="invalid_type")


class TestRetrievalPlan:
    def test_defaults(self):
        plan = RetrievalPlan()
        assert plan.sources == []
        assert plan.intent == "neighborhood_overview"
        assert plan.time_range_days == 90
        assert plan.requires_disclaimer is False

    def test_full_plan(self):
        plan = RetrievalPlan(
            sources=["crime_api", "vector_search"],
            location=Location(raw="Loop", type="community_area", resolved_community_area=32),
            intent="legal_question",
            time_range_days=30,
            requires_disclaimer=True,
            search_query="parking requirements",
        )
        assert "crime_api" in plan.sources
        assert plan.location.resolved_community_area == 32
        assert plan.requires_disclaimer is True

    def test_invalid_source_rejected(self):
        with pytest.raises(ValidationError):
            RetrievalPlan(sources=["invalid_source"])

    def test_invalid_intent_rejected(self):
        with pytest.raises(ValidationError):
            RetrievalPlan(intent="invalid_intent")


class TestCrimeSummary:
    def test_full_summary(self):
        summary = CrimeSummary(
            total=150,
            arrest_rate=0.15,
            by_type={"THEFT": 50, "BATTERY": 40, "BURGLARY": 30, "ASSAULT": 20, "ROBBERY": 10},
        )
        assert summary.total == 150
        assert summary.arrest_rate == 0.15
        assert len(summary.by_type) == 5


class TestThreeOneOneSummary:
    def test_full_summary(self):
        summary = ThreeOneOneSummary(
            total=200,
            oldest_open_days=45,
            by_department={"Streets & Sanitation": 100, "CDOT": 50, "Water": 50},
            top_types=["Pothole", "Graffiti", "Tree Trim"],
        )
        assert summary.total == 200
        assert summary.oldest_open_days == 45

    def test_null_oldest_days(self):
        summary = ThreeOneOneSummary(
            total=0,
            oldest_open_days=None,
            by_department={},
            top_types=[],
        )
        assert summary.oldest_open_days is None


class TestCodeChunk:
    def test_full_chunk(self):
        chunk = CodeChunk(
            text="Parking requirements for RS-3 districts...",
            source_document="Chicago Municipal Code",
            section="17-10-0207",
            section_title="Off-Street Parking",
            subsection="(a)",
            score=0.89,
            cross_references=["17-10-0200", "17-10-0208"],
        )
        assert chunk.section == "17-10-0207"
        assert chunk.score == 0.89
        assert len(chunk.cross_references) == 2

    def test_defaults(self):
        chunk = CodeChunk(
            text="Test",
            source_document="CMC",
            section="1-1-1",
            section_title="Title",
            score=0.5,
        )
        assert chunk.subsection is None
        assert chunk.cross_references == []


class TestContextObject:
    def test_defaults(self):
        ctx = ContextObject()
        assert ctx.community_area is None
        assert ctx.crime_last_90d is None
        assert ctx.code_chunks == []
        assert ctx.requires_disclaimer is False

    def test_full_context(self):
        ctx = ContextObject(
            community_area=24,
            community_area_name="West Town",
            data_lag_note="Crime data may lag by up to 7 days.",
            crime_last_90d=CrimeSummary(total=100, arrest_rate=0.1, by_type={"THEFT": 100}),
            code_chunks=[
                CodeChunk(
                    text="Test",
                    source_document="CMC",
                    section="1-1-1",
                    section_title="Title",
                    score=0.5,
                )
            ],
            requires_disclaimer=True,
        )
        assert ctx.community_area == 24
        assert ctx.crime_last_90d.total == 100
        assert len(ctx.code_chunks) == 1


class TestMessage:
    def test_user_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message(self):
        msg = Message(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="system", content="Test")


class TestChatRequest:
    def test_minimal_request(self):
        req = ChatRequest(message="What's happening?")
        assert req.message == "What's happening?"
        assert req.history == []

    def test_with_history(self):
        req = ChatRequest(
            message="Follow up",
            history=[
                Message(role="user", content="First question"),
                Message(role="assistant", content="First answer"),
            ],
        )
        assert len(req.history) == 2


class TestChatChunk:
    def test_plan_chunk(self):
        plan = RetrievalPlan(sources=["crime_api"])
        chunk = ChatChunk(type="plan", plan=plan, t_ms=150)
        assert chunk.type == "plan"
        assert chunk.plan is not None
        assert chunk.t_ms == 150

    def test_context_chunk(self):
        ctx = ContextObject(community_area=24)
        chunk = ChatChunk(type="context", context=ctx, t_ms=500)
        assert chunk.type == "context"
        assert chunk.context.community_area == 24

    def test_token_chunk(self):
        chunk = ChatChunk(type="token", text="Hello")
        assert chunk.type == "token"
        assert chunk.text == "Hello"
        assert chunk.t_ms is None

    def test_error_chunk(self):
        chunk = ChatChunk(type="error", error="Something went wrong", t_ms=100)
        assert chunk.type == "error"
        assert chunk.error == "Something went wrong"

    def test_done_chunk(self):
        chunk = ChatChunk(type="done", t_ms=2000)
        assert chunk.type == "done"
        assert chunk.t_ms == 2000

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ChatChunk(type="invalid")
