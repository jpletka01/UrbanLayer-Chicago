"""Streaming synthesis call. Composes the final user-facing answer from assembled context."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.config import get_settings
from backend.llm import tracked_stream
from backend.models import AnalyticsSummary, ContextObject, Message
from backend.prompts import SYNTHESIZER_SYSTEM


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


def _build_user_prompt(
    context: ContextObject,
    user_message: str,
    upload_filenames: list[str] | None = None,
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

    if upload_filenames:
        parts.append(
            f"The user attached {len(upload_filenames)} file(s): {', '.join(upload_filenames)}\n"
            "Note: File contents are not analyzed in this version. "
            "The user may be referencing these files in their question.\n\n"
        )

    parts.append(
        f"User question: {user_message}\n\n"
        "Answer the question using only the context data above. Cite sources inline."
    )
    return "".join(parts)


async def stream_answer(
    *,
    context: ContextObject,
    user_message: str,
    history: list[Message],
    upload_filenames: list[str] | None = None,
    request_group: str = "",
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    settings = get_settings()

    messages: list[dict] = [{"role": m.role, "content": m.content} for m in history]
    messages.append({
        "role": "user",
        "content": _build_user_prompt(context, user_message, upload_filenames),
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
