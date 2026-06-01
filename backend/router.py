"""LLM router. Parses a user message into a structured RetrievalPlan."""

from __future__ import annotations

import json
import logging

from backend.config import get_settings
from backend.llm import tracked_create
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


async def _llm_plan(
    message: str,
    request_group: str = "",
    conversation_id: str | None = None,
) -> dict:
    settings = get_settings()
    resp = await tracked_create(
        request_group=request_group,
        conversation_id=conversation_id,
        phase="router",
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


async def route(
    message: str,
    request_group: str = "",
    conversation_id: str | None = None,
) -> RetrievalPlan:
    raw = await _llm_plan(message, request_group, conversation_id)

    location = raw.get("location") or {}
    raw_loc = (location.get("raw") or "").strip()
    loc_type = location.get("type") or "none"
    ca = location.get("resolved_community_area")
    ca_name: str | None = None

    resolved_lat: float | None = None
    resolved_lon: float | None = None

    if ca is None and raw_loc:
        ca = community_area_by_name(raw_loc)
    # Always geocode addresses to get lat/lon for the map pin and zoning lookup,
    # even when the community area is already known from the LLM or alias table.
    if (location.get("resolved_address") or loc_type == "address") and raw_loc:
        geocode_input = location.get("resolved_address") or raw_loc
        resolved_ca, coords = await resolve_address_to_community_area(geocode_input)
        if ca is None:
            ca = resolved_ca
        if coords:
            resolved_lat, resolved_lon = coords
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
                "resolved_lat": resolved_lat,
                "resolved_lon": resolved_lon,
            },
            "intent": raw.get("intent", "neighborhood_overview"),
            "time_range_days": int(raw.get("time_range_days") or 90),
            "requires_disclaimer": bool(raw.get("requires_disclaimer", False)),
            "search_query": raw.get("search_query"),
            "clarification": raw.get("clarification"),
            "workflow_hint": raw.get("workflow_hint", "general"),
        }
    )
    return plan
