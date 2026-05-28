"""Tests for multi-turn conversation synthesis."""

import pytest

from backend.conversation import needs_synthesis
from backend.models import Message


class TestNeedsSynthesis:
    """Test the heuristic that determines when synthesis is needed."""

    def test_empty_history_no_synthesis(self):
        """No synthesis needed when there's no history."""
        assert needs_synthesis("hello", []) is False

    def test_single_message_history_no_synthesis(self):
        """No synthesis needed with only one message in history."""
        history = [Message(role="user", content="hello")]
        assert needs_synthesis("how are you", history) is False

    def test_short_answer_after_clarification(self):
        """Synthesis needed when short answer follows clarification question."""
        history = [
            Message(role="user", content="is it legal to add a balcony to my townhouse?"),
            Message(role="assistant", content="What is the address or neighborhood of your townhouse?"),
        ]
        # Short answer lacking context needs synthesis
        assert needs_synthesis("lincoln park", history) is True

    def test_short_followup_question(self):
        """Synthesis needed for short follow-up questions."""
        history = [
            Message(role="user", content="what's the crime rate?"),
            Message(role="assistant", content="Which neighborhood are you interested in?"),
        ]
        assert needs_synthesis("wicker park", history) is True

    def test_context_reference_needs_synthesis(self):
        """Synthesis needed when message references prior context."""
        history = [
            Message(role="user", content="Do I need a permit for window replacement at 525 W Arlington?"),
            Message(role="assistant", content="Yes, window replacement generally requires a permit..."),
        ]
        # "their" refers to prior context
        assert needs_synthesis("do you have their website?", history) is True

    def test_what_about_followup(self):
        """Synthesis needed for 'what about' follow-ups."""
        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics for Wicker Park..."),
        ]
        assert needs_synthesis("what about logan square?", history) is True

    def test_long_standalone_with_location_no_synthesis(self):
        """No synthesis for long questions that include location context."""
        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics for Wicker Park..."),
        ]
        # Long question with explicit location - self-contained
        long_question = "I'm also curious about what's happening with building permits in the Logan Square neighborhood these days"
        assert needs_synthesis(long_question, history) is False

    def test_short_thanks_no_synthesis(self):
        """No synthesis for short non-question responses like thanks."""
        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics for Wicker Park. Theft is the most common crime type."),
        ]
        # "thanks" doesn't have context references or question patterns
        assert needs_synthesis("thanks!", history) is False

    def test_address_answer(self):
        """Synthesis needed for address answers."""
        history = [
            Message(role="user", content="can I open a bar here?"),
            Message(role="assistant", content="What address are you asking about?"),
        ]
        # Short answer with street name
        assert needs_synthesis("2400 N Milwaukee", history) is True

    def test_district_answer(self):
        """Synthesis needed for zoning district answers."""
        history = [
            Message(role="user", content="what uses are allowed in this zone?"),
            Message(role="assistant", content="Which district are you asking about?"),
        ]
        # Very short answer
        assert needs_synthesis("RS-3", history) is True

    def test_multiple_turns(self):
        """Synthesis works with longer history."""
        history = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="Hi! What can I help you with?"),
            Message(role="user", content="can I add a deck to my house?"),
            Message(role="assistant", content="What neighborhood is your house in?"),
        ]
        assert needs_synthesis("logan square", history) is True

    def test_how_question_followup(self):
        """Synthesis for follow-up 'how' questions."""
        history = [
            Message(role="user", content="what's the zoning at 123 Main St?"),
            Message(role="assistant", content="The zoning is RS-3 residential."),
        ]
        assert needs_synthesis("how do I apply for a variance?", history) is True


class TestSynthesizeQuery:
    """Integration tests for the actual synthesis call.

    These tests require the Anthropic API and are marked as integration tests.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_balcony_clarification(self):
        """Test the example from the issue: balcony question + location answer."""
        from backend.conversation import synthesize_query

        history = [
            Message(role="user", content="is it legal to add a balcony to my townhouse?"),
            Message(role="assistant", content="What is the address or neighborhood of your townhouse?"),
        ]
        result = await synthesize_query("it's on wrightwood in lincoln park", history)

        assert "balcony" in result.lower()
        assert "lincoln park" in result.lower() or "wrightwood" in result.lower()
        assert "?" in result

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_passthrough_no_history(self):
        """Original message returned when no history."""
        from backend.conversation import synthesize_query

        result = await synthesize_query("what's happening in wicker park?", [])
        assert result == "what's happening in wicker park?"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_website_followup(self):
        """Follow-up asking for website uses context."""
        from backend.conversation import synthesize_query

        history = [
            Message(role="user", content="Do I need a permit for window replacement?"),
            Message(role="assistant", content="Yes, contact the Department of Buildings."),
        ]
        result = await synthesize_query("do you have their website?", history)

        # Should synthesize to include what "their" refers to
        assert "website" in result.lower()
        assert ("building" in result.lower() or "department" in result.lower())
