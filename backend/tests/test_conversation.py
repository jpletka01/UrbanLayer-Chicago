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
        assert needs_synthesis("lincoln park", history) is True

    def test_short_answer_after_generic_question(self):
        """Synthesis needed when short answer follows any question."""
        history = [
            Message(role="user", content="what's the crime rate?"),
            Message(role="assistant", content="Which neighborhood are you interested in?"),
        ]
        assert needs_synthesis("wicker park", history) is True

    def test_long_standalone_question_no_synthesis(self):
        """No synthesis for long, self-contained follow-up questions."""
        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics for Wicker Park..."),
        ]
        # Long, self-contained question
        long_question = "What about the building permits that have been issued in Logan Square over the past year?"
        assert needs_synthesis(long_question, history) is False

    def test_short_answer_after_non_question(self):
        """No synthesis when last assistant message isn't a question."""
        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics for Wicker Park. Theft is the most common crime type."),
        ]
        assert needs_synthesis("thanks", history) is False

    def test_address_clarification(self):
        """Synthesis needed for address clarifications."""
        history = [
            Message(role="user", content="can I open a bar here?"),
            Message(role="assistant", content="What address are you asking about?"),
        ]
        assert needs_synthesis("2400 N Milwaukee Ave", history) is True

    def test_district_clarification(self):
        """Synthesis needed for zoning district clarifications."""
        history = [
            Message(role="user", content="what uses are allowed in this zone?"),
            Message(role="assistant", content="Which district are you asking about?"),
        ]
        assert needs_synthesis("RS-3", history) is True

    def test_multiple_turns_clarification(self):
        """Synthesis works with longer history."""
        history = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="Hi! What can I help you with?"),
            Message(role="user", content="can I add a deck to my house?"),
            Message(role="assistant", content="What neighborhood is your house in?"),
        ]
        assert needs_synthesis("logan square", history) is True

    def test_where_clarification(self):
        """Synthesis for 'where' questions."""
        history = [
            Message(role="user", content="what's the zoning here?"),
            Message(role="assistant", content="Where are you located?"),
        ]
        assert needs_synthesis("near wrigley field", history) is True


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
    async def test_passthrough_long_standalone(self):
        """Long self-contained question passes through unchanged."""
        from backend.conversation import synthesize_query

        history = [
            Message(role="user", content="what's the crime rate in wicker park?"),
            Message(role="assistant", content="Here are the crime statistics..."),
        ]
        question = "What about the building permits that have been issued in the Logan Square neighborhood over the past year or so?"
        result = await synthesize_query(question, history)

        assert result == question
