"""FastAPI app exposing /chat as a Server-Sent Events stream.

Event types streamed to the client (one JSON object per `data:` line):
  {"type": "plan",    "plan":    RetrievalPlan}
  {"type": "context", "context": ContextObject}
  {"type": "token",   "text":    "..."}
  {"type": "error",   "error":   "..."}
  {"type": "done"}
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.analytics import compute_analytics
from backend.assembler import assemble_context
from backend.config import get_settings
from backend.conversation import synthesize_query
from backend import db
from backend.models import (
    ChatChunk,
    ChatRequest,
    ContextObject,
    ImportRequest,
    MapDataRequest,
    MapDataResponse,
    RetrievalPlan,
    SaveMessagesRequest,
)
from backend.retrieval import buildings, business, crime, three11
from backend.retrieval.geo import geocode_address_suggestions
from backend.retrieval.map_data import crimes_for_map, permits_for_map, requests_311_for_map, zoning_for_map
from backend.retrieval.vector_search import (
    expand_cross_references,
    get_full_section,
    semantic_search,
)
from backend.router import route
from backend.synthesizer import stream_answer


log = logging.getLogger(__name__)

app = FastAPI(title="Chicago City Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    get_settings()
    await db.init_db()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await db.close_db()


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/autocomplete")
async def autocomplete(q: str = "") -> list[dict]:
    """Return address suggestions for autocomplete."""
    if len(q.strip()) < 3:
        return []
    return await geocode_address_suggestions(q)


@app.get("/section/{section_id}")
async def section(section_id: str) -> dict:
    """Return the full reassembled municipal-code section by ID.

    Backs the clickable cross-references in the sources panel: a chunk may cite
    a section that wasn't itself retrieved, so we look it up on demand.
    """
    loop = asyncio.get_running_loop()
    chunk = await loop.run_in_executor(None, lambda: get_full_section(section_id))
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found")
    return chunk.model_dump()


@app.post("/api/map-data")
async def map_data(req: MapDataRequest) -> MapDataResponse:
    settings = get_settings()
    tasks: dict[str, asyncio.Task] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        if "crime_api" in req.sources:
            tasks["crimes"] = asyncio.create_task(
                crimes_for_map(req.community_area, days=req.time_range_days, client=client)
            )
        if "311_api" in req.sources:
            tasks["requests_311"] = asyncio.create_task(
                requests_311_for_map(req.community_area, client=client)
            )
        if "permits_api" in req.sources:
            tasks["building_permits"] = asyncio.create_task(
                permits_for_map(req.community_area, days=req.time_range_days, client=client)
            )
        if settings.enable_zoning_layer:
            tasks["zoning"] = asyncio.create_task(
                zoning_for_map(req.community_area, client=client)
            )

        results: dict[str, Any] = {}
        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, value in zip(tasks.keys(), done):
            if isinstance(value, Exception):
                log.warning("Map data %s failed: %s", key, value)
                results[key] = [] if key != "zoning" else {"type": "FeatureCollection", "features": []}
            else:
                results[key] = value

    queried_address = None
    if req.address_lat is not None and req.address_lon is not None:
        queried_address = {
            "latitude": req.address_lat,
            "longitude": req.address_lon,
            "label": req.address_label or "",
        }

    crimes = results.get("crimes", [])
    requests_311 = results.get("requests_311", [])
    building_permits = results.get("building_permits", [])

    capped: dict[str, bool] = {}
    if "crimes" in results:
        capped["crimes"] = len(crimes) >= settings.limit_map_crime
    if "requests_311" in results:
        capped["requests_311"] = len(requests_311) >= settings.limit_map_311
    if "building_permits" in results:
        capped["building_permits"] = len(building_permits) >= settings.limit_map_permits

    return MapDataResponse(
        crimes=crimes,
        requests_311=requests_311,
        building_permits=building_permits,
        zoning=results.get("zoning") if settings.enable_zoning_layer else None,
        queried_address=queried_address,
        capped=capped,
    )


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

@app.get("/api/conversations")
async def list_conversations() -> list[dict]:
    return await db.list_conversations()


@app.post("/api/conversations", status_code=201)
async def create_conversation(body: dict) -> dict:
    conv_id = body.get("id", f"conv_{int(time.time() * 1000)}")
    title = body.get("title", "New conversation")
    return await db.create_conversation(conv_id, title)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str) -> dict:
    conv = await db.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str) -> dict:
    deleted = await db.delete_conversation(conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.put("/api/conversations/{conv_id}/messages")
async def append_messages(conv_id: str, req: SaveMessagesRequest) -> dict:
    conv = await db.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = [m.model_dump(exclude_none=True) for m in req.messages]
    await db.save_messages(conv_id, messages)
    return {"ok": True}


@app.patch("/api/conversations/{conv_id}/messages/{position}")
async def update_message(conv_id: str, position: int, body: dict) -> dict:
    if "map_data" in body:
        await db.update_message_map_data(
            conv_id, position, body["map_data"], body.get("map_fetched_at"),
        )
    return {"ok": True}


@app.post("/api/conversations/import")
async def import_conversations(req: ImportRequest) -> dict:
    count = await db.import_conversations(
        [c.model_dump() for c in req.conversations]
    )
    return {"imported": count}


@app.delete("/api/conversations")
async def clear_conversations() -> dict:
    await db.clear_all_conversations()
    return {"ok": True}


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(chunk: ChatChunk) -> str:
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


async def _retrieve(plan: RetrievalPlan) -> ContextObject:
    ca = plan.location.resolved_community_area
    tasks: dict[str, asyncio.Task] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        if ca is not None:
            if "crime_api" in plan.sources:
                tasks["crime"] = asyncio.create_task(
                    crime.crime_by_community_area(ca, days=plan.time_range_days, client=client)
                )
            if "311_api" in plan.sources:
                tasks["311"] = asyncio.create_task(
                    three11.open_311_by_community_area(ca, client=client)
                )
                tasks["311_oldest"] = asyncio.create_task(
                    three11.open_311_oldest(ca, client=client)
                )
            if "permits_api" in plan.sources:
                tasks["permits"] = asyncio.create_task(
                    buildings.permits_by_community_area(ca, client=client)
                )
            if "violations_api" in plan.sources:
                tasks["violations"] = asyncio.create_task(
                    buildings.violations_by_community_area(ca, client=client)
                )
            if "business_api" in plan.sources:
                tasks["business"] = asyncio.create_task(
                    business.businesses_by_community_area(ca, client=client)
                )

        results: dict[str, list] = {}
        if tasks:
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for key, value in zip(tasks.keys(), done):
                if isinstance(value, Exception):
                    log.warning("Retrieval %s failed: %s", key, value)
                    results[key] = []
                else:
                    results[key] = value

    code_chunks = []
    if "vector_search" in plan.sources and plan.search_query:
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(
            None, lambda: semantic_search(plan.search_query, top_k=5)
        )
        code_chunks = await loop.run_in_executor(None, lambda: expand_cross_references(chunks))

    return assemble_context(
        plan=plan,
        crime_rows=results.get("crime") if "crime" in results else None,
        three11_rows=results.get("311") if "311" in results else None,
        three11_oldest=results.get("311_oldest"),
        permit_rows=results.get("permits") if "permits" in results else None,
        violation_rows=results.get("violations") if "violations" in results else None,
        business_rows=results.get("business") if "business" in results else None,
        code_chunks=code_chunks,
    )


async def _fetch_map_rows(plan: RetrievalPlan) -> dict[str, list]:
    """Fetch raw geo-located rows for analytics computation."""
    ca = plan.location.resolved_community_area
    if ca is None:
        return {}

    tasks: dict[str, asyncio.Task] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        if "crime_api" in plan.sources:
            tasks["crimes"] = asyncio.create_task(
                crimes_for_map(ca, days=plan.time_range_days, client=client)
            )
        if "311_api" in plan.sources:
            tasks["requests_311"] = asyncio.create_task(
                requests_311_for_map(ca, client=client)
            )
        if "permits_api" in plan.sources:
            tasks["building_permits"] = asyncio.create_task(
                permits_for_map(ca, days=plan.time_range_days, client=client)
            )

        results: dict[str, list] = {}
        if tasks:
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for key, value in zip(tasks.keys(), done):
                if isinstance(value, Exception):
                    log.warning("Map-row fetch %s failed: %s", key, value)
                    results[key] = []
                else:
                    results[key] = value

    return results


def _build_map_response(
    map_rows: dict[str, list], plan: RetrievalPlan,
) -> MapDataResponse | None:
    """Build a MapDataResponse from fetched map rows."""
    if not map_rows:
        return None
    settings = get_settings()
    crimes = map_rows.get("crimes", [])
    requests_311 = map_rows.get("requests_311", [])
    building_permits = map_rows.get("building_permits", [])

    capped: dict[str, bool] = {}
    if "crimes" in map_rows:
        capped["crimes"] = len(crimes) >= settings.limit_map_crime
    if "requests_311" in map_rows:
        capped["requests_311"] = len(requests_311) >= settings.limit_map_311
    if "building_permits" in map_rows:
        capped["building_permits"] = len(building_permits) >= settings.limit_map_permits

    queried_address = None
    loc = plan.location
    if loc.resolved_lat is not None and loc.resolved_lon is not None:
        queried_address = {
            "latitude": loc.resolved_lat,
            "longitude": loc.resolved_lon,
            "label": loc.resolved_address or "",
        }

    return MapDataResponse(
        crimes=crimes,
        requests_311=requests_311,
        building_permits=building_permits,
        queried_address=queried_address,
        capped=capped,
    )


async def _event_stream(req: ChatRequest) -> AsyncIterator[str]:
    start = time.monotonic()
    elapsed_ms = lambda: int((time.monotonic() - start) * 1000)

    # Message limit enforcement
    if req.conversation_id:
        settings = get_settings()
        count = await db.count_user_messages(req.conversation_id)
        if count >= settings.message_limit:
            yield _sse(ChatChunk(
                type="error",
                error="MESSAGE_LIMIT_REACHED",
                t_ms=elapsed_ms(),
            ))
            yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
            return

    query = await synthesize_query(req.message, req.history)

    try:
        plan = await route(query)
    except Exception as exc:
        log.exception("Router failed")
        yield _sse(ChatChunk(type="error", error=f"Router failed: {exc}", t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        return

    yield _sse(ChatChunk(type="plan", plan=plan, t_ms=elapsed_ms()))

    if plan.intent == "clarification_needed" and plan.clarification:
        yield _sse(ChatChunk(type="token", text=plan.clarification, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        return

    # Run retrieval and map-data fetch concurrently
    try:
        context, map_rows = await asyncio.gather(
            _retrieve(plan),
            _fetch_map_rows(plan),
        )
    except Exception as exc:
        log.exception("Retrieval failed")
        yield _sse(ChatChunk(type="error", error=f"Retrieval failed: {exc}", t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        return

    # Compute analytics from map rows and attach to context
    analytics = compute_analytics(
        crime_rows=map_rows.get("crimes"),
        three11_rows=map_rows.get("requests_311"),
        permit_rows=map_rows.get("building_permits"),
    )
    context.analytics = analytics

    yield _sse(ChatChunk(type="context", context=context, t_ms=elapsed_ms()))

    # Emit map data so the frontend doesn't need a separate fetch
    map_response = _build_map_response(map_rows, plan)
    if map_response:
        yield _sse(ChatChunk(type="map_data", map_data=map_response, t_ms=elapsed_ms()))

    first_token = True
    try:
        async for token in stream_answer(
            context=context, user_message=req.message, history=req.history
        ):
            chunk_t = elapsed_ms() if first_token else None
            yield _sse(ChatChunk(type="token", text=token, t_ms=chunk_t))
            first_token = False
    except Exception as exc:
        log.exception("Synthesizer failed")
        yield _sse(ChatChunk(type="error", error=f"Synthesizer failed: {exc}", t_ms=elapsed_ms()))

    yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
