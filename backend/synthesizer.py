"""Streaming synthesis call. Composes the final user-facing answer from assembled context."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from backend.config import get_settings
from backend.models import ContextObject, Message


log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Chicago city information assistant. You have access to real-time city data and official municipal documents through the context object you are given. Your job is to answer questions about Chicago clearly and accurately.

Rules:
1. Always cite your sources inline:
   - For Municipal Code chunks: use numbered references [1], [2], etc. corresponding to code_chunks array indices (1-indexed)
   - For API data: use data markers [data:crime], [data:311], [data:permits], [data:violations], or [data:business] immediately after statistics from those sources
   Example: "There were 127 reported crimes [data:crime] in the area, and the zoning code requires a special use permit [1]."
2. Always surface data freshness. If crime data is present, note the 7-day lag.
3. For any question that touches on legal rights, zoning compliance, permit requirements, or ordinance interpretation, add this disclaimer at the end of your answer: "This information is based on official city documents but does not constitute legal advice. Please consult a licensed attorney or contact the relevant city department for official guidance."
4. Never fabricate statistics. If the data does not answer the question, say so directly.
5. Be concise. Lead with the direct answer in 1-3 sentences, then supporting detail.
6. Render numbers as readable prose, not raw JSON. Use markdown for emphasis and short bullet lists only when they aid clarity.
7. Place citations immediately after the relevant statement, not at the end of paragraphs.
"""


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
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": _build_user_prompt(context, user_message)})

    async with client.messages.stream(
        model=settings.synthesizer_model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield chunk
