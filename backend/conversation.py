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

    Returns True when there is conversation history and the current message
    might benefit from context (short messages, follow-up questions, pronouns
    referring to prior context, etc.)
    """
    if not history:
        return False

    if len(history) < 2:
        return False

    msg_lower = message.lower().strip()
    msg_len = len(msg_lower)

    # Very short messages (< 50 chars) almost always need context
    # These are typically answers to clarification questions
    is_very_short = msg_len < 50

    # Short messages (< 100 chars) need context if they have indicators
    is_short_message = msg_len < 100

    # Check if last assistant message was a question (likely clarification)
    last_assistant = None
    for msg in reversed(history):
        if msg.role == "assistant":
            last_assistant = msg.content
            break

    last_was_question = last_assistant and last_assistant.strip().endswith("?")

    # Messages with pronouns/references to prior context
    context_references = [
        "their ", "they ", "them ", "it ", "its ",
        "that ", "this ", "these ", "those ",
        "the same", "there ", "here ",
        "what about", "how about", "and ",
        "also ", "too?", "as well",
    ]
    has_context_reference = any(ref in msg_lower for ref in context_references)

    # Follow-up question patterns
    followup_patterns = [
        "do you have", "can you", "could you",
        "what is", "what are", "what's",
        "where is", "where are", "where's",
        "how do", "how can", "how much", "how many",
        "is there", "are there",
        "tell me more", "more about", "explain",
    ]
    looks_like_followup = any(msg_lower.startswith(p) for p in followup_patterns)

    # Questions that lack obvious subject/location
    ends_with_question = msg_lower.endswith("?")
    lacks_location = not any(word in msg_lower for word in [
        "chicago", "street", "ave", "avenue", "blvd", "boulevard",
        "park", "square", "heights", "village", "town"
    ])

    # Very short answer after a question = almost certainly needs context
    if is_very_short and last_was_question:
        return True

    # Short message with context references or follow-up patterns
    if is_short_message and (has_context_reference or looks_like_followup):
        return True

    # Short question lacking location context
    if is_short_message and ends_with_question and lacks_location:
        return True

    return False


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
