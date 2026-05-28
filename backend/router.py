"""LLM router. Parses a user message into a structured RetrievalPlan."""

from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from backend.config import get_settings
from backend.models import RetrievalPlan
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


SYSTEM_PROMPT = f"""You are the routing layer of a Chicago city-information assistant.

Your job: parse a user's message and emit a strict JSON retrieval plan. You do NOT answer the user. You only describe what to fetch.

{_community_area_table()}

Output a JSON object with these fields:
- sources: array. Pick from: "crime_api", "311_api", "permits_api", "violations_api", "business_api", "vector_search".
- location.raw: the raw location phrase the user used, or "".
- location.type: one of "intersection", "address", "neighborhood", "community_area", "none".
- location.resolved_community_area: integer 1-77 or null. Pick using the table above when you can; leave null if unsure.
- location.resolved_address: the canonicalized address string the user gave, or null.
- intent: one of "neighborhood_overview", "incident_lookup", "legal_question", "event_query", "trend_analysis", "clarification_needed".
- time_range_days: integer, default 90. Use shorter (7, 30) when the user asks about "recent" or "this week".
- requires_disclaimer: true ONLY for zoning, permit, code, ordinance, or legal-rights questions.
- search_query: a 1-line semantic query to send to vector search, or null if vector_search is not in sources.
- clarification: a one-line clarification question to ask the user, or null. ONLY set when intent is "clarification_needed".

Rules:
- "What's going on in/near X" -> neighborhood_overview, include crime_api + 311_api + permits_api.
- "Can I build/open/operate X" or "is X allowed" -> legal_question, include vector_search, requires_disclaimer=true.
- If no location and the question requires one, set intent="clarification_needed" and emit a clarification.
- Always emit valid JSON. Do not wrap it in markdown or commentary.
"""


async def _llm_plan(message: str) -> dict:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.router_model,
        max_tokens=600,
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
