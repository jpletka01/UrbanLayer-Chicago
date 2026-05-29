"""Shared Anthropic client.

A single process-lifetime client is reused across the router, synthesizer, and
conversation layers so a chat request doesn't pay connection-pool setup three
times. Mirrors the `get_settings()` lru_cache pattern.
"""

from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from backend.config import get_settings


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key)
