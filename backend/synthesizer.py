"""Streaming synthesis call. Composes the final user-facing answer from assembled context."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.config import get_settings
from backend.context_manager import detect_location_switch, format_summaries_for_prompt
from backend.llm import tracked_stream
from backend.models import AnalyticsSummary, ContextObject, Message, RetrievalPlan, TurnSummary
from backend.prompts import LANGUAGE_INSTRUCTION, SYNTHESIZER_SYSTEM
from backend.vision import prepare_upload_content_blocks


log = logging.getLogger(__name__)

LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "pl": "Polish",
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
}

SLIDING_WINDOW_PAIRS = 2


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


def _build_history_with_summaries(
    turn_summaries: list[TurnSummary],
    recent_messages: list[Message],
    current_plan: RetrievalPlan,
) -> list[dict]:
    """Build message history using summaries + sliding window instead of full history."""
    messages: list[dict] = []

    if turn_summaries:
        current_ca = current_plan.location.resolved_community_area
        summary_text = format_summaries_for_prompt(turn_summaries, current_ca)

        switched, prior_location = detect_location_switch(current_plan, turn_summaries)
        if switched and prior_location:
            summary_text += (
                f"\n\nNote: The user has switched locations. Prior turn data is for {prior_location} "
                "and should only be referenced if the user explicitly requests a comparison."
            )

        messages.append({"role": "user", "content": summary_text})
        messages.append({"role": "assistant", "content": "Understood. I have the conversation context."})

    window = recent_messages[-(SLIDING_WINDOW_PAIRS * 2):]
    for m in window:
        messages.append({"role": m.role, "content": m.content})

    return messages


async def stream_answer(
    *,
    context: ContextObject,
    user_message: str,
    history: list[Message],
    turn_summaries: list[TurnSummary] | None = None,
    plan: RetrievalPlan | None = None,
    upload_ids: list[str] | None = None,
    request_group: str = "",
    conversation_id: str | None = None,
    language: str = "en",
) -> AsyncIterator[str]:
    settings = get_settings()

    upload_blocks: list[dict] | None = None
    if upload_ids:
        upload_blocks = await prepare_upload_content_blocks(upload_ids) or None

    if turn_summaries and plan:
        messages = _build_history_with_summaries(turn_summaries, history, plan)
    else:
        messages = [{"role": m.role, "content": m.content} for m in history]

    messages.append({
        "role": "user",
        "content": _build_user_content(context, user_message, upload_blocks),
    })

    if language != "en":
        lang_name = LANGUAGE_NAMES.get(language, language)
        system = SYNTHESIZER_SYSTEM + "\n\n" + LANGUAGE_INSTRUCTION.format(language_name=lang_name)
    else:
        system = SYNTHESIZER_SYSTEM

    async with tracked_stream(
        request_group=request_group,
        conversation_id=conversation_id,
        phase="synthesizer",
        model=settings.synthesizer_model,
        max_tokens=settings.synthesizer_max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield chunk
