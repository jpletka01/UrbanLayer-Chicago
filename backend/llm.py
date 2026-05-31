"""Shared Anthropic client and tracked LLM call helpers.

A single process-lifetime client is reused across the router, synthesizer, and
conversation layers so a chat request doesn't pay connection-pool setup three
times. The tracked_create / tracked_stream wrappers capture token usage and
timing, persisting them to SQLite for the admin dashboard.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from backend.config import get_settings

log = logging.getLogger(__name__)

COST_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_MTOK.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key)


async def tracked_create(
    *,
    request_group: str,
    conversation_id: str | None,
    phase: str,
    model: str,
    **kwargs: Any,
) -> Any:
    """Wrapper around client.messages.create() that logs usage to SQLite."""
    from backend import db

    client = get_anthropic_client()
    start = time.monotonic()
    try:
        resp = await client.messages.create(model=model, **kwargs)
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            await db.save_llm_call(
                request_group=request_group,
                conversation_id=conversation_id,
                phase=phase,
                model=model,
                input_tokens=0,
                output_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_message=str(exc)[:500],
            )
        except Exception:
            log.warning("Failed to log LLM error call")
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    usage = resp.usage
    try:
        await db.save_llm_call(
            request_group=request_group,
            conversation_id=conversation_id,
            phase=phase,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_create_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            duration_ms=duration_ms,
        )
    except Exception:
        log.warning("Failed to log LLM call")
    return resp


@asynccontextmanager
async def tracked_stream(
    *,
    request_group: str,
    conversation_id: str | None,
    phase: str,
    model: str,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Async context manager wrapping client.messages.stream() that logs usage."""
    from backend import db

    client = get_anthropic_client()
    start = time.monotonic()
    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    cache_create = 0
    status = "ok"
    error_msg = None

    try:
        async with client.messages.stream(model=model, **kwargs) as stream:
            yield stream
            try:
                final = await stream.get_final_message()
                usage = final.usage
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
            except Exception as e:
                log.warning("Could not get final message from stream: %s", e)
    except Exception as exc:
        status = "error"
        error_msg = str(exc)[:500]
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            await db.save_llm_call(
                request_group=request_group,
                conversation_id=conversation_id,
                phase=phase,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_create_tokens=cache_create,
                duration_ms=duration_ms,
                status=status,
                error_message=error_msg,
            )
        except Exception:
            log.warning("Failed to log LLM stream call")
