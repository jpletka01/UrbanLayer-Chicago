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

from backend.assembler import assemble_context
from backend.config import get_settings
from backend.conversation import synthesize_query
from backend.models import ChatChunk, ChatRequest, ContextObject, MapDataRequest, MapDataResponse, RetrievalPlan
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
    # Force settings load so a misconfigured env crashes early.
    get_settings()


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


async def _event_stream(req: ChatRequest) -> AsyncIterator[str]:
    start = time.monotonic()
    elapsed_ms = lambda: int((time.monotonic() - start) * 1000)

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

    try:
        context = await _retrieve(plan)
    except Exception as exc:
        log.exception("Retrieval failed")
        yield _sse(ChatChunk(type="error", error=f"Retrieval failed: {exc}", t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        return

    yield _sse(ChatChunk(type="context", context=context, t_ms=elapsed_ms()))

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
