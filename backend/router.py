"""LLM router. Parses a user message into a structured RetrievalPlan."""

from __future__ import annotations

import json
import logging

from backend.config import get_settings
from backend.llm import get_anthropic_client
from backend.models import RetrievalPlan
from backend.prompts import ROUTER_SYSTEM_TEMPLATE
from backend.retrieval.geo import (
    COMMUNITY_AREAS,
    NEIGHBORHOOD_ALIASES,
    community_area_by_name,
    resolve_address_to_community_area,
)


log = logging.getLogger(__name__)


def _community_area_table() -> str:
    rows = [f"  {ca}: {name}" for ca, name in COMMUNITY_AREAS.items()]
    aliases = [f"  {alias} -> CA {ca}" for alias, ca in NEIGHBORHOOD_ALIASES.items()]
    return (
        "Official community areas (integer id : name):\n"
        + "\n".join(rows)
        + "\n\nCommon neighborhood aliases:\n"
        + "\n".join(aliases)
    )


SYSTEM_PROMPT = ROUTER_SYSTEM_TEMPLATE.format(community_area_table=_community_area_table())


async def _llm_plan(message: str) -> dict:
    settings = get_settings()
    client = get_anthropic_client()
    resp = await client.messages.create(
        model=settings.router_model,
        max_tokens=settings.router_max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


async def route(message: str) -> RetrievalPlan:
    raw = await _llm_plan(message)

    location = raw.get("location") or {}
    raw_loc = (location.get("raw") or "").strip()
    loc_type = location.get("type") or "none"
    ca = location.get("resolved_community_area")
    ca_name: str | None = None

    if ca is None and raw_loc:
        ca = community_area_by_name(raw_loc)
    if ca is None and (location.get("resolved_address") or loc_type == "address") and raw_loc:
        resolved_ca, _coords = await resolve_address_to_community_area(raw_loc)
        ca = resolved_ca
    if ca is not None:
        ca_name = COMMUNITY_AREAS.get(int(ca))

    plan = RetrievalPlan.model_validate(
        {
            "sources": raw.get("sources", []),
            "location": {
                "raw": raw_loc,
                "type": loc_type,
                "resolved_community_area": int(ca) if ca is not None else None,
                "resolved_community_area_name": ca_name,
                "resolved_address": location.get("resolved_address"),
            },
            "intent": raw.get("intent", "neighborhood_overview"),
            "time_range_days": int(raw.get("time_range_days") or 90),
            "requires_disclaimer": bool(raw.get("requires_disclaimer", False)),
            "search_query": raw.get("search_query"),
            "clarification": raw.get("clarification"),
        }
    )
    return plan
