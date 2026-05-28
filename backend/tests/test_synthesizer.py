import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.synthesizer import _build_user_prompt, SYSTEM_PROMPT
from backend.models import (
    CodeChunk,
    ContextObject,
    CrimeSummary,
    Message,
    ThreeOneOneSummary,
)


class TestBuildUserPrompt:
    def test_includes_context_as_json(self):
        ctx = ContextObject(
            community_area=24,
            community_area_name="West Town",
            crime_last_90d=CrimeSummary(
                total=150,
                arrest_rate=0.12,
                by_type={"THEFT": 80, "BATTERY": 70},
            ),
        )
        prompt = _build_user_prompt(ctx, "What's happening?")

        assert "```json" in prompt
        assert '"community_area": 24' in prompt
        assert '"community_area_name": "West Town"' in prompt
        assert "THEFT" in prompt

    def test_includes_user_message(self):
        ctx = ContextObject()
        prompt = _build_user_prompt(ctx, "Tell me about Wicker Park")

        assert "User question: Tell me about Wicker Park" in prompt

    def test_includes_citation_instruction(self):
        ctx = ContextObject()
        prompt = _build_user_prompt(ctx, "What's the crime like?")

        assert "Cite sources" in prompt

    def test_includes_code_chunks(self):
        ctx = ContextObject(
            code_chunks=[
                CodeChunk(
                    text="Coach houses permitted in RS-3",
                    source_document="CMC",
                    section="17-2-0303",
                    section_title="Detached Houses",
                    score=0.9,
                )
            ]
        )
        prompt = _build_user_prompt(ctx, "Can I build a coach house?")

        assert "17-2-0303" in prompt
        assert "Coach houses" in prompt


class TestSystemPrompt:
    def test_includes_citation_rules(self):
        assert "cite your sources" in SYSTEM_PROMPT.lower()
        assert "CPD crime data" in SYSTEM_PROMPT

    def test_includes_disclaimer_instruction(self):
        assert "legal advice" in SYSTEM_PROMPT.lower()
        assert "zoning compliance" in SYSTEM_PROMPT.lower()

    def test_includes_data_freshness_rule(self):
        assert "7-day lag" in SYSTEM_PROMPT

    def test_includes_no_fabrication_rule(self):
        assert "Never fabricate" in SYSTEM_PROMPT

    def test_includes_conciseness_rule(self):
        assert "concise" in SYSTEM_PROMPT.lower()


class TestContextSerialization:
    def test_empty_context_serializes(self):
        ctx = ContextObject()
        prompt = _build_user_prompt(ctx, "Test")
        assert "community_area" in prompt
        assert "null" in prompt or "None" not in prompt

    def test_full_context_serializes(self):
        ctx = ContextObject(
            community_area=24,
            community_area_name="West Town",
            data_lag_note="Crime data may lag by up to 7 days.",
            crime_last_90d=CrimeSummary(
                total=100,
                arrest_rate=0.15,
                by_type={"THEFT": 50, "BATTERY": 50},
            ),
            open_311_requests=ThreeOneOneSummary(
                total=75,
                oldest_open_days=30,
                by_department={"S&S": 50, "CDOT": 25},
                top_types=["Pothole", "Graffiti"],
            ),
            code_chunks=[
                CodeChunk(
                    text="Zoning text",
                    source_document="CMC",
                    section="17-2-0100",
                    section_title="Title",
                    score=0.8,
                )
            ],
            requires_disclaimer=True,
        )
        prompt = _build_user_prompt(ctx, "Overview please")

        assert "West Town" in prompt
        assert "Crime data may lag" in prompt
        assert "THEFT" in prompt
        assert "Pothole" in prompt
        assert "17-2-0100" in prompt
        assert "requires_disclaimer" in prompt
