"""Streaming synthesis call. Composes the final user-facing answer from assembled context."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.config import get_settings
from backend.llm import get_anthropic_client
from backend.models import ContextObject, Message
from backend.prompts import SYNTHESIZER_SYSTEM


log = logging.getLogger(__name__)


def _build_user_prompt(context: ContextObject, user_message: str) -> str:
    return (
        "Context data (retrieved from Chicago city databases):\n"
        f"```json\n{context.model_dump_json(indent=2)}\n```\n\n"
        f"User question: {user_message}\n\n"
        "Answer the question using only the context data above. Cite sources inline."
    )


async def stream_answer(
    *,
    context: ContextObject,
    user_message: str,
    history: list[Message],
) -> AsyncIterator[str]:
    settings = get_settings()
    client = get_anthropic_client()

    messages: list[dict] = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": _build_user_prompt(context, user_message)})

    async with client.messages.stream(
        model=settings.synthesizer_model,
        max_tokens=settings.synthesizer_max_tokens,
        system=SYNTHESIZER_SYSTEM,
        messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield chunk
