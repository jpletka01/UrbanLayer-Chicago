"""Multi-turn conversation synthesis.

When a user's message is a short answer to a clarification (e.g., providing a
location after being asked), this module synthesizes the full context into a
single self-contained query for the router.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from backend.config import get_settings
from backend.models import Message


log = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are a query rewriter for a Chicago city information assistant.

Given a conversation history and the user's latest message, produce a single self-contained query that captures the user's full intent.

Rules:
- If the latest message is already a complete question with all needed context, return it unchanged.
- If the latest message answers a clarification (like providing a location or confirming a detail), merge the original question with the new information into one clear query.
- If the latest message is a follow-up question on the same topic, incorporate relevant context from prior turns.
- Output ONLY the rewritten query. No explanation, no quotes, no prefixes like "Query:".

Examples:

History:
User: is it legal to add a balcony to my townhouse?
Assistant: What is the address or neighborhood of your townhouse?
Latest: it's on wrightwood in lincoln park

Output: Is it legal to add a balcony to a townhouse on Wrightwood in Lincoln Park?

History:
User: what's the crime rate in wicker park?
Assistant: [crime statistics response]
Latest: what about logan square?

Output: What's the crime rate in Logan Square?

History:
User: can I open a restaurant in a residential zone?
Assistant: Which specific zoning district are you asking about?
Latest: RS-3

Output: Can I open a restaurant in an RS-3 residential zoning district?
"""


def needs_synthesis(message: str, history: list[Message]) -> bool:
    """Determine if we need to synthesize conversation context.

    Returns True when:
    1. There is conversation history, AND
    2. The current message is short (likely an answer to clarification) OR
       the last assistant message looks like a clarification question
    """
    if not history:
        return False

    if len(history) < 2:
        return False

    last_assistant = None
    for msg in reversed(history):
        if msg.role == "assistant":
            last_assistant = msg.content
            break

    if not last_assistant:
        return False

    is_short_message = len(message.strip()) < 100

    clarification_indicators = [
        "what is the address",
        "what address",
        "which neighborhood",
        "what neighborhood",
        "which district",
        "what district",
        "which location",
        "what location",
        "where is",
        "where are",
        "can you specify",
        "could you specify",
        "please provide",
        "what area",
        "which area",
        "what zone",
        "which zone",
    ]
    last_lower = last_assistant.lower()
    looks_like_clarification = any(ind in last_lower for ind in clarification_indicators)

    ends_with_question = last_assistant.strip().endswith("?")

    return is_short_message and (looks_like_clarification or ends_with_question)


async def synthesize_query(message: str, history: list[Message]) -> str:
    """Synthesize conversation history into a single self-contained query.

    If synthesis is not needed or fails, returns the original message unchanged.
    """
    if not needs_synthesis(message, history):
        return message

    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    history_text = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
        for m in history
    )

    user_prompt = f"History:\n{history_text}\nLatest: {message}"

    try:
        resp = await client.messages.create(
            model=settings.conversation_model,
            max_tokens=300,
            system=SYNTHESIS_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", "") == "text"
        ).strip()

        if text:
            log.info("Synthesized query: %r -> %r", message, text)
            return text
        return message
    except Exception as exc:
        log.warning("Conversation synthesis failed, using original message: %s", exc)
        return message
