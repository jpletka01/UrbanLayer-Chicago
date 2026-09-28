import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.prompts import SYNTHESIZER_SYSTEM as SYSTEM_PROMPT
from backend.synthesizer import _build_user_text
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
        prompt = _build_user_text(ctx, "What's happening?")

        assert "```json" in prompt
        assert '"community_area": 24' in prompt
        assert '"community_area_name": "West Town"' in prompt
        assert "THEFT" in prompt

    def test_includes_user_message(self):
        ctx = ContextObject()
        prompt = _build_user_text(ctx, "Tell me about Wicker Park")

        assert "User question: Tell me about Wicker Park" in prompt

    def test_includes_citation_instruction(self):
        ctx = ContextObject()
        prompt = _build_user_text(ctx, "What's the crime like?")

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
        prompt = _build_user_text(ctx, "Can I build a coach house?")

        assert "17-2-0303" in prompt
        assert "Coach houses" in prompt


class TestSystemPrompt:
    def test_includes_citation_rules(self):
        assert "cite your sources" in SYSTEM_PROMPT.lower()
        assert "[1]" in SYSTEM_PROMPT and "[2]" in SYSTEM_PROMPT

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
        prompt = _build_user_text(ctx, "Test")
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
        prompt = _build_user_text(ctx, "Overview please")

        assert "West Town" in prompt
        assert "Crime data may lag" in prompt
        assert "THEFT" in prompt
        assert "Pothole" in prompt
        assert "17-2-0100" in prompt
        assert "requires_disclaimer" in prompt


class TestFormatAnalytics:
    """Regression: a category with no prior-month rows has change_pct=None, and
    formatting it crashed the whole answer ("'>' not supported between
    'NoneType' and 'int'") for any parcel with a new trend category."""

    def test_new_category_formats_instead_of_crashing(self):
        from backend.models import AnalyticsSummary, TrendItem
        from backend.synthesizer import _format_analytics

        item = TrendItem(category="Graffiti Removal", current_count=4, prior_count=0, change_pct=None)
        text = _format_analytics(AnalyticsSummary(
            crime_trends=[item], three11_trends=[item], permit_trends=[item],
        ))
        assert text.count("Graffiti Removal: 4 (new this month") == 3

    def test_percentages_still_render(self):
        from backend.models import AnalyticsSummary, TrendItem
        from backend.synthesizer import _format_analytics

        items = [
            TrendItem(category="Theft", current_count=12, prior_count=10, change_pct=20),
            TrendItem(category="Battery", current_count=8, prior_count=10, change_pct=-20),
            TrendItem(category="Assault", current_count=5, prior_count=5, change_pct=0),
        ]
        text = _format_analytics(AnalyticsSummary(crime_trends=items))
        assert "Theft: 12 (up 20%)" in text
        assert "Battery: 8 (down 20%)" in text
        assert "Assault: 5 (flat 0%)" in text
