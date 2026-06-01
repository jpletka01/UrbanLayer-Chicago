"""Multi-turn conversation synthesis.

When a user's message is a short answer to a clarification (e.g., providing a
location after being asked), this module synthesizes the full context into a
single self-contained query for the router.
"""

from __future__ import annotations

import logging
import re

from backend.config import get_settings
from backend.llm import tracked_create
from backend.models import Message
from backend.prompts import CONVERSATION_SYNTHESIS
from backend.retrieval.geo import COMMUNITY_AREAS, NEIGHBORHOOD_ALIASES


log = logging.getLogger(__name__)


def _find_neighborhood(text: str) -> tuple[int | None, str | None]:
    """Find a community area reference in text. Returns (ca_number, matched_name)."""
    t = text.lower()
    for alias, ca in NEIGHBORHOOD_ALIASES.items():
        if alias in t:
            return ca, alias
    for ca, name in COMMUNITY_AREAS.items():
        if name.lower() in t:
            return ca, name
    return None, None


def _try_neighborhood_switch(message: str, history: list[Message]) -> str | None:
    """For neighborhood switch/compare follow-ups, produce a clean single-neighborhood query.

    When the user says "what about Austin?" or "compare to Englewood", takes the
    original question from history and substitutes the new neighborhood. Returns
    None if this isn't a neighborhood-switch pattern.
    """
    msg_lower = message.lower()
    switch_signals = ["compare", "versus", " vs ", "what about", "how about",
                      "look up", "check ", "show me", "switch to", "now do"]
    if not any(s in msg_lower for s in switch_signals):
        return None

    new_ca, new_match = _find_neighborhood(message)
    if not new_ca:
        return None

    first_user_msg = next((m.content for m in history if m.role == "user"), None)
    if not first_user_msg:
        return None

    old_ca, old_match = _find_neighborhood(first_user_msg)
    if not old_ca or old_ca == new_ca:
        return None

    new_name = COMMUNITY_AREAS.get(new_ca, new_match or "")
    result = re.sub(re.escape(old_match or ""), new_name, first_user_msg, count=1, flags=re.IGNORECASE)

    if result == first_user_msg:
        return None

    log.info("Neighborhood switch: %r -> %r", message, result)
    return result


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
        "compare", "versus ", " vs ",
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


async def synthesize_query(
    message: str,
    history: list[Message],
    request_group: str = "",
    conversation_id: str | None = None,
) -> str:
    """Synthesize conversation history into a single self-contained query.

    If synthesis is not needed or fails, returns the original message unchanged.
    """
    if not needs_synthesis(message, history):
        return message

    switched = _try_neighborhood_switch(message, history)
    if switched:
        return switched

    settings = get_settings()

    def _truncate(content: str, role: str, max_chars: int = 150) -> str:
        if role == "user" or len(content) <= max_chars:
            return content
        return content[:max_chars].rsplit(" ", 1)[0] + " …"

    history_text = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {_truncate(m.content, m.role)}"
        for m in history
    )

    user_prompt = f"History:\n{history_text}\nLatest: {message}"

    try:
        resp = await tracked_create(
            request_group=request_group,
            conversation_id=conversation_id,
            phase="conversation",
            model=settings.conversation_model,
            max_tokens=settings.conversation_max_tokens,
            system=CONVERSATION_SYNTHESIS,
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
