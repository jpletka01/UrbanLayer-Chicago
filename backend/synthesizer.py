"""Streaming synthesis call. Composes the final user-facing answer from assembled context."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.config import get_settings
from backend.llm import tracked_stream
from backend.models import AnalyticsSummary, ContextObject, Message
from backend.prompts import SYNTHESIZER_SYSTEM
from backend.vision import prepare_upload_content_blocks


log = logging.getLogger(__name__)


def _format_analytics(analytics: AnalyticsSummary) -> str:
    """Format analytics as readable text for Claude (not JSON — saves tokens)."""
    lines: list[str] = []
    if analytics.trend_period:
        lines.append(f"Month-over-month trends ({analytics.trend_period}) — per-category counts for a single month, not the full-period total:")
    else:
        lines.append("Month-over-month trends — per-category counts for a single month, not the full-period total:")

    if analytics.crime_trends:
        lines.append("Crime:")
        for t in analytics.crime_trends:
            direction = "up" if t.change_pct > 0 else "down" if t.change_pct < 0 else "flat"
            lines.append(f"  - {t.category}: {t.current_count} ({direction} {abs(t.change_pct)}%)")

    if analytics.three11_trends:
        lines.append("311 Requests:")
        for t in analytics.three11_trends:
            direction = "up" if t.change_pct > 0 else "down" if t.change_pct < 0 else "flat"
            lines.append(f"  - {t.category}: {t.current_count} ({direction} {abs(t.change_pct)}%)")

    if analytics.permit_trends:
        lines.append("Permits:")
        for t in analytics.permit_trends:
            direction = "up" if t.change_pct > 0 else "down" if t.change_pct < 0 else "flat"
            lines.append(f"  - {t.category}: {t.current_count} ({direction} {abs(t.change_pct)}%)")

    return "\n".join(lines) + "\n\n"


def _build_user_text(
    context: ContextObject,
    user_message: str,
) -> str:
    ctx_json = context.model_dump_json(indent=2, exclude={"analytics"})
    parts = [
        "Context data (retrieved from Chicago city databases):\n",
        f"```json\n{ctx_json}\n```\n\n",
    ]

    if context.analytics and (
        context.analytics.crime_trends
        or context.analytics.three11_trends
        or context.analytics.permit_trends
    ):
        parts.append(_format_analytics(context.analytics))

    parts.append(
        f"User question: {user_message}\n\n"
        "Answer the question using only the context data above. Cite sources inline."
    )
    return "".join(parts)


def _build_user_content(
    context: ContextObject,
    user_message: str,
    upload_content_blocks: list[dict] | None = None,
) -> str | list[dict]:
    """Build user message content. Returns str for text-only, list for multimodal."""
    text = _build_user_text(context, user_message)
    if not upload_content_blocks:
        return text
    content: list[dict] = [{"type": "text", "text": text}]
    content.extend(upload_content_blocks)
    return content


async def stream_answer(
    *,
    context: ContextObject,
    user_message: str,
    history: list[Message],
    upload_ids: list[str] | None = None,
    request_group: str = "",
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    settings = get_settings()

    upload_blocks: list[dict] | None = None
    if upload_ids:
        upload_blocks = await prepare_upload_content_blocks(upload_ids) or None

    messages: list[dict] = [{"role": m.role, "content": m.content} for m in history]
    messages.append({
        "role": "user",
        "content": _build_user_content(context, user_message, upload_blocks),
    })

    async with tracked_stream(
        request_group=request_group,
        conversation_id=conversation_id,
        phase="synthesizer",
        model=settings.synthesizer_model,
        max_tokens=settings.synthesizer_max_tokens,
        system=SYNTHESIZER_SYSTEM,
        messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield chunk
