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
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from backend.analytics import compute_analytics
from backend.assembler import assemble_context
from backend.config import get_settings
from backend.context_manager import summarize_turn
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
    TurnSummary,
)
from backend.retrieval import buildings, business, crime, food_inspections, three11, vacant
from backend.retrieval.geo import COMMUNITY_AREAS, community_area_by_point, geocode_address_suggestions
from backend.retrieval.map_data import crimes_for_map, permits_for_map, requests_311_for_map, zoning_for_map
from backend.retrieval.incentives import incentives_domain
from backend.retrieval.neighborhood import neighborhood_domain
from backend.retrieval.property import property_domain
from backend.retrieval.regulatory import regulatory_domain
from backend.retrieval.zoning import lookup_zoning
from backend.retrieval.vector_search import (
    expand_cross_references,
    get_full_section,
    semantic_search,
)
from backend.router import route
from backend.synthesizer import stream_answer


log = logging.getLogger(__name__)

_settings_init = get_settings()
if _settings_init.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_settings_init.sentry_dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

app = FastAPI(title="Chicago City Intelligence")

_settings = get_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def _startup() -> None:
    get_settings()
    await db.init_db()
    asyncio.create_task(_preload_datasets())


async def _preload_datasets() -> None:
    """Pre-warm lazy-loaded datasets in the background."""
    from backend.retrieval.incentives import tif, enterprise_zones
    from backend.retrieval.neighborhood import transit, demographics

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        labels = ["TIF boundaries", "EZ boundaries", "transit stations", "demographics"]
        results = await asyncio.gather(
            tif.preload(client=client),
            enterprise_zones.preload(client=client),
            transit.preload(),
            demographics.preload(client=client),
            return_exceptions=True,
        )
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                log.warning("Startup preload %s failed: %s", label, result)
            else:
                log.info("Preloaded %s", label)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await db.close_db()
    from backend.retrieval.property.tax_estimate import close as close_ptaxsim
    await close_ptaxsim()
    from backend.retrieval.socrata import close_shared_client
    await close_shared_client()


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    qdrant_ok = False
    db_ok = False

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{settings.qdrant_url}/healthz")
            qdrant_ok = r.status_code == 200
    except Exception:
        pass

    try:
        db_conn = db._get_db()
        await db_conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    ok = qdrant_ok and db_ok
    result = {"ok": ok, "qdrant": qdrant_ok, "db": db_ok}
    if not ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(content=result, status_code=503)
    return result


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

from backend.auth import (
    get_current_user,
    handle_google_callback,
    handle_google_login,
    handle_logout,
    handle_me,
    handle_refresh,
    require_admin,
    set_auth_cookies,
    clear_auth_cookies,
)


@app.get("/api/auth/google")
async def google_login(request: Request):
    return await handle_google_login(request)


@app.get("/api/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    return await handle_google_callback(request)


@app.post("/api/auth/refresh")
async def refresh_token(request: Request):
    result = await handle_refresh(request)
    response = StreamingResponse(content=iter([]), media_type="application/json")
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"user": result["user"]})
    set_auth_cookies(
        resp, result["access_token"], result["refresh_token"], result["csrf_token"],
    )
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request):
    return await handle_me(request)


@app.post("/api/auth/logout")
async def logout(request: Request):
    result = await handle_logout(request)
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content=result)
    clear_auth_cookies(resp)
    return resp


@app.get("/autocomplete")
async def autocomplete(q: str = "") -> list[dict]:
    """Return address suggestions for autocomplete."""
    if len(q.strip()) < 3:
        return []
    return await geocode_address_suggestions(q)


@app.get("/api/community-area")
async def community_area_lookup(lat: float, lon: float) -> dict:
    ca = community_area_by_point(lat, lon)
    if ca is None:
        raise HTTPException(status_code=404, detail="Location not within Chicago")
    return {"community_area": ca, "name": COMMUNITY_AREAS.get(ca, "")}


@app.get("/section/{section_id}")
async def section(section_id: str) -> dict:
    """Return the full reassembled municipal-code section by ID.

    Backs the clickable cross-references in the sources panel: a chunk may cite
    a section that wasn't itself retrieved, so we look it up on demand.
    """
    chunk = await get_full_section(section_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found")
    return chunk.model_dump()


@app.post("/api/map-data")
async def map_data(req: MapDataRequest) -> MapDataResponse:
    settings = get_settings()
    tasks: dict[str, asyncio.Task] = {}

    if "crime_api" in req.sources:
        tasks["crimes"] = asyncio.create_task(
            crimes_for_map(req.community_area, days=req.time_range_days)
        )
    if "311_api" in req.sources:
        tasks["requests_311"] = asyncio.create_task(
            requests_311_for_map(req.community_area)
        )
    if "permits_api" in req.sources:
        tasks["building_permits"] = asyncio.create_task(
            permits_for_map(req.community_area, days=req.time_range_days)
        )
    if settings.enable_zoning_layer:
        tasks["zoning"] = asyncio.create_task(
            zoning_for_map(req.community_area)
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
# File uploads
# ---------------------------------------------------------------------------

@app.post("/api/conversations/{conv_id}/uploads", status_code=201)
async def upload_files(conv_id: str, files: list[UploadFile] = File(...)) -> dict:
    settings = get_settings()

    conv = await db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    if len(files) > settings.upload_max_per_message:
        raise HTTPException(400, f"Max {settings.upload_max_per_message} files per upload")

    results = []
    for f in files:
        if f.content_type not in settings.upload_allowed_types:
            raise HTTPException(400, f"File type {f.content_type} not allowed")

        content = await f.read()
        if len(content) > settings.upload_max_size_bytes:
            raise HTTPException(
                400,
                f"File exceeds {settings.upload_max_size_bytes // (1024 * 1024)}MB limit",
            )

        upload_id = str(uuid.uuid4())
        ext = Path(f.filename).suffix if f.filename else ""
        upload_dir = settings.upload_dir / conv_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path = upload_dir / f"{upload_id}{ext}"
        storage_path.write_bytes(content)

        meta = await db.save_upload(
            upload_id=upload_id,
            conversation_id=conv_id,
            filename=f.filename or "unnamed",
            mime_type=f.content_type,
            size_bytes=len(content),
            storage_path=str(storage_path),
        )
        results.append(meta)

    return {"uploads": results}


@app.get("/api/uploads/{upload_id}/file")
async def download_file(upload_id: str) -> FileResponse:
    upload = await db.get_upload(upload_id)
    if not upload:
        raise HTTPException(404, "Upload not found")
    return FileResponse(
        upload["storage_path"],
        media_type=upload["mime_type"],
        filename=upload["filename"],
    )


@app.delete("/api/uploads/{upload_id}")
async def delete_upload_endpoint(upload_id: str) -> dict:
    upload = await db.get_upload(upload_id)
    if not upload:
        raise HTTPException(404, "Upload not found")
    path = Path(upload["storage_path"])
    if path.exists():
        path.unlink()
    await db.delete_upload(upload_id)
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/uploads")
async def list_uploads(conv_id: str) -> list[dict]:
    return await db.get_uploads_for_conversation(conv_id)


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(chunk: ChatChunk) -> str:
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


async def _retrieve(plan: RetrievalPlan) -> ContextObject:
    ca = plan.location.resolved_community_area
    tasks: dict[str, asyncio.Task] = {}

    if ca is not None:
        if "crime_api" in plan.sources:
            tasks["crime"] = asyncio.create_task(
                crime.crime_by_community_area(ca, days=plan.time_range_days)
            )
        if "311_api" in plan.sources:
            tasks["311"] = asyncio.create_task(
                three11.open_311_by_community_area(ca)
            )
            tasks["311_oldest"] = asyncio.create_task(
                three11.open_311_oldest(ca)
            )
        if "permits_api" in plan.sources:
            tasks["permits"] = asyncio.create_task(
                buildings.permits_by_community_area(ca)
            )
        if "violations_api" in plan.sources:
            tasks["violations"] = asyncio.create_task(
                buildings.violations_by_community_area(ca)
            )
        if "business_api" in plan.sources:
            tasks["business"] = asyncio.create_task(
                business.businesses_by_community_area(ca)
            )
        if "vacant_buildings_api" in plan.sources:
            tasks["vacant"] = asyncio.create_task(
                vacant.vacant_buildings_by_community_area(ca)
            )
        if "food_inspections_api" in plan.sources:
            tasks["food_inspections"] = asyncio.create_task(
                food_inspections.food_inspections_by_community_area(ca)
            )

    loc = plan.location
    if plan.requires_disclaimer and loc.resolved_lat and loc.resolved_lon:
        tasks["zoning_lookup"] = asyncio.create_task(
            lookup_zoning(loc.resolved_lat, loc.resolved_lon)
        )

    wf = plan.workflow_hint or "general"

    if "regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
        tasks["regulatory"] = asyncio.create_task(
            regulatory_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
        )

    if "property_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
        tasks["property"] = asyncio.create_task(
            property_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
        )

    if "incentives_domain" in plan.sources:
        if loc.resolved_lat and loc.resolved_lon:
            tasks["incentives"] = asyncio.create_task(
                incentives_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
            )
        elif ca is not None:
            tasks["incentives"] = asyncio.create_task(
                incentives_domain(ca=ca, workflow=wf)
            )

    if "neighborhood_domain" in plan.sources:
        tasks["neighborhood"] = asyncio.create_task(
            neighborhood_domain(
                loc.resolved_lat or 0.0,
                loc.resolved_lon or 0.0,
                community_area=ca,
                address=loc.resolved_address,
                workflow=wf,
            )
        )

    _FAILURE_LABELS = {
        "crime": "crime statistics",
        "311": "311 service requests",
        "permits": "building permits",
        "violations": "building violations",
        "business": "business licenses",
        "vacant": "vacant buildings",
        "food_inspections": "food inspections",
        "zoning_lookup": "parcel zoning",
        "regulatory": "regulatory overlays",
        "property": "property records",
        "incentives": "incentive zones",
        "neighborhood": "demographics and transit",
    }

    results: dict[str, Any] = {}
    partial_failures: list[str] = []
    if tasks:
        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, value in zip(tasks.keys(), done):
            if isinstance(value, Exception):
                log.warning("Retrieval %s failed: %s", key, value)
                if key in ("permits", "violations", "business", "vacant", "food_inspections"):
                    results[key] = {}
                elif key in ("zoning_lookup", "regulatory", "property", "incentives", "neighborhood"):
                    results[key] = None
                else:
                    results[key] = []
                if key in _FAILURE_LABELS:
                    partial_failures.append(_FAILURE_LABELS[key])
            else:
                results[key] = value

    code_chunks = []
    if "vector_search" in plan.sources and plan.search_query:
        chunks = await semantic_search(plan.search_query, top_k=5)
        code_chunks = await expand_cross_references(chunks)

    return assemble_context(
        plan=plan,
        crime_rows=results.get("crime") if "crime" in results else None,
        three11_rows=results.get("311") if "311" in results else None,
        three11_oldest=results.get("311_oldest"),
        permit_data=results.get("permits") if "permits" in results else None,
        violation_data=results.get("violations") if "violations" in results else None,
        business_data=results.get("business") if "business" in results else None,
        vacant_data=results.get("vacant") if "vacant" in results else None,
        food_inspection_data=results.get("food_inspections") if "food_inspections" in results else None,
        code_chunks=code_chunks,
        zoning_info=results.get("zoning_lookup"),
        regulatory_summary=results.get("regulatory"),
        property_summary=results.get("property"),
        incentives_summary=results.get("incentives"),
        neighborhood_summary=results.get("neighborhood"),
        partial_failures=partial_failures,
    )


async def _fetch_overlay_geojson(
    lat: float, lon: float,
) -> dict | None:
    """Get GeoJSON features for overlays that hit at this point."""
    from backend.retrieval.regulatory.overlays import query_all_overlays, overlay_geojson_features
    hits = await query_all_overlays(lat, lon)
    if not hits:
        return None
    layer_ids = [lid for lid, _ in hits]
    return await overlay_geojson_features(lat, lon, layer_ids)


async def _fetch_map_rows(plan: RetrievalPlan) -> dict[str, Any]:
    """Fetch raw geo-located rows for analytics computation."""
    ca = plan.location.resolved_community_area
    if ca is None:
        return {}

    tasks: dict[str, asyncio.Task] = {}

    if "crime_api" in plan.sources:
        tasks["crimes"] = asyncio.create_task(
            crimes_for_map(ca, days=plan.time_range_days)
        )
    if "311_api" in plan.sources:
        tasks["requests_311"] = asyncio.create_task(
            requests_311_for_map(ca)
        )
    if "permits_api" in plan.sources:
        tasks["building_permits"] = asyncio.create_task(
            permits_for_map(ca, days=plan.time_range_days)
        )
    if plan.requires_disclaimer:
        tasks["zoning"] = asyncio.create_task(
            zoning_for_map(ca)
        )

    loc = plan.location
    if "regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
        tasks["overlay_geojson"] = asyncio.create_task(
            _fetch_overlay_geojson(loc.resolved_lat, loc.resolved_lon)
        )

    if "incentives_domain" in plan.sources:
        if loc.resolved_lat and loc.resolved_lon:
            from backend.retrieval.incentives.tif import tif_geojson_feature
            from backend.retrieval.incentives.enterprise_zones import ez_geojson_feature
            tasks["tif_geojson"] = asyncio.create_task(
                tif_geojson_feature(loc.resolved_lat, loc.resolved_lon)
            )
            tasks["ez_geojson"] = asyncio.create_task(
                ez_geojson_feature(loc.resolved_lat, loc.resolved_lon)
            )
        elif ca is not None:
            from backend.retrieval.incentives.tif import tif_geojson_by_community_area
            tasks["tif_geojson_list"] = asyncio.create_task(
                tif_geojson_by_community_area(ca)
            )

    results: dict[str, Any] = {}
    if tasks:
        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, value in zip(tasks.keys(), done):
            if isinstance(value, Exception):
                log.warning("Map-row fetch %s failed: %s", key, value)
                _NONE_ON_FAIL = {"zoning", "tif_geojson", "ez_geojson", "overlay_geojson"}
                results[key] = None if key in _NONE_ON_FAIL else []
            else:
                results[key] = value

    return results


def _build_map_response(
    map_rows: dict[str, Any], plan: RetrievalPlan,
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

    incentive_features = []
    if map_rows.get("tif_geojson"):
        incentive_features.append(map_rows["tif_geojson"])
    if map_rows.get("tif_geojson_list"):
        incentive_features.extend(map_rows["tif_geojson_list"])
    if map_rows.get("ez_geojson"):
        incentive_features.append(map_rows["ez_geojson"])
    incentive_zones = (
        {"type": "FeatureCollection", "features": incentive_features}
        if incentive_features else None
    )

    return MapDataResponse(
        crimes=crimes,
        requests_311=requests_311,
        building_permits=building_permits,
        zoning=map_rows.get("zoning"),
        overlay_districts=map_rows.get("overlay_geojson"),
        incentive_zones=incentive_zones,
        queried_address=queried_address,
        capped=capped,
    )


async def _event_stream(req: ChatRequest) -> AsyncIterator[str]:
    start = time.monotonic()
    elapsed_ms = lambda: int((time.monotonic() - start) * 1000)
    request_group = str(uuid.uuid4())
    plan: RetrievalPlan | None = None
    error_msg: str | None = None

    # Load turn summaries for context management
    turn_summaries: list[TurnSummary] | None = None
    if req.conversation_id:
        try:
            summary_dicts = await db.get_turn_summaries(req.conversation_id)
            if summary_dicts:
                turn_summaries = [TurnSummary(**d) for d in summary_dicts]
        except Exception:
            pass

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

    query = await synthesize_query(
        req.message, req.history,
        request_group=request_group,
        conversation_id=req.conversation_id,
    )

    try:
        plan = await route(
            query,
            request_group=request_group,
            conversation_id=req.conversation_id,
        )
    except Exception as exc:
        log.exception("Router failed")
        error_msg = f"Router failed: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "error", error_msg,
        ))
        return

    yield _sse(ChatChunk(type="plan", plan=plan, t_ms=elapsed_ms()))

    if plan.intent == "clarification_needed" and plan.clarification:
        yield _sse(ChatChunk(type="token", text=plan.clarification, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "ok", None,
        ))
        return

    # Run retrieval and map-data fetch concurrently
    try:
        context, map_rows = await asyncio.gather(
            _retrieve(plan),
            _fetch_map_rows(plan),
        )
    except Exception as exc:
        log.exception("Retrieval failed")
        error_msg = f"Retrieval failed: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "error", error_msg,
        ))
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
            context=context,
            user_message=req.message,
            history=req.history,
            turn_summaries=turn_summaries,
            plan=plan,
            upload_ids=req.upload_ids or None,
            request_group=request_group,
            conversation_id=req.conversation_id,
        ):
            chunk_t = elapsed_ms() if first_token else None
            yield _sse(ChatChunk(type="token", text=token, t_ms=chunk_t))
            first_token = False
    except Exception as exc:
        log.exception("Synthesizer failed")
        error_msg = f"Synthesizer failed: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))

    # Generate turn summary for context management (fire-and-forget)
    if plan and not error_msg:
        try:
            turn_idx = len(turn_summaries) if turn_summaries else 0
            _turn_summary = summarize_turn(turn_idx, req.message, plan, context)
            yield _sse(ChatChunk(
                type="turn_summary",
                turn_summary=_turn_summary.model_dump(),
                t_ms=elapsed_ms(),
            ))
        except Exception:
            log.warning("Failed to generate turn summary", exc_info=True)

    yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))

    asyncio.create_task(_save_request_log(
        request_group, req, plan, elapsed_ms(),
        "error" if error_msg else "ok", error_msg,
    ))


async def _save_request_log(
    request_group: str,
    req: ChatRequest,
    plan: RetrievalPlan | None,
    total_duration_ms: int,
    status: str,
    error_message: str | None,
) -> None:
    try:
        await db.save_request_log(
            request_group=request_group,
            conversation_id=req.conversation_id,
            user_message=req.message[:500],
            intent=plan.intent if plan else None,
            community_area=(
                plan.location.resolved_community_area if plan else None
            ),
            community_area_name=(
                plan.location.resolved_community_area_name if plan else None
            ),
            sources=list(plan.sources) if plan else None,
            total_duration_ms=total_duration_ms,
            status=status,
            error_message=error_message[:500] if error_message else None,
        )
    except Exception:
        log.warning("Failed to save request log")


@app.post("/chat")
async def chat(request: Request, req: ChatRequest) -> StreamingResponse:
    from backend.rate_limit import check_rate_limit, check_daily_budget
    await check_rate_limit(request)
    await check_daily_budget()
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

@app.get("/api/admin/cache")
async def admin_cache(request: Request, _admin: dict = Depends(require_admin)) -> dict:
    from backend.retrieval.cache import TTLCache
    caches = [c.stats() for c in TTLCache._instances]
    total_hits = sum(c["hits"] for c in caches)
    total_misses = sum(c["misses"] for c in caches)
    total = total_hits + total_misses
    return {
        "caches": caches,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "overall_hit_rate": round(total_hits / total, 4) if total > 0 else 0.0,
    }


@app.get("/api/admin/overview")
async def admin_overview(request: Request, period: str = "30d", _admin: dict = Depends(require_admin)) -> dict:
    from backend.llm import estimate_cost
    overview = await db.get_admin_overview(period)
    # Compute estimated costs
    for model, usage in overview["by_model"].items():
        usage["estimated_cost_usd"] = round(
            estimate_cost(model, usage["input_tokens"], usage["output_tokens"]), 4,
        )
    for phase_data in overview["by_phase"].values():
        phase_data["estimated_cost_usd"] = 0.0
    overview["estimated_cost_usd"] = round(
        sum(u["estimated_cost_usd"] for u in overview["by_model"].values()), 4,
    )
    return overview


@app.get("/api/admin/timeseries")
async def admin_timeseries(request: Request, period: str = "30d", bucket: str = "day", _admin: dict = Depends(require_admin)) -> list[dict]:
    from backend.llm import estimate_cost, COST_PER_MTOK
    rows = await db.get_admin_timeseries(period, bucket)
    for row in rows:
        row["estimated_cost_usd"] = round(
            estimate_cost("claude-sonnet-4-6", row["input_tokens"], row["output_tokens"]),
            4,
        )
        row["avg_duration_ms"] = round(row["avg_duration_ms"])
    return rows


@app.get("/api/admin/latency")
async def admin_latency(request: Request, period: str = "30d", _admin: dict = Depends(require_admin)) -> list[dict]:
    return await db.get_admin_latency(period)


@app.get("/api/admin/conversations")
async def admin_conversations(request: Request, _admin: dict = Depends(require_admin)) -> dict:
    return await db.get_admin_conversation_stats()


@app.get("/api/admin/requests")
async def admin_requests(request: Request, limit: int = 50, offset: int = 0, _admin: dict = Depends(require_admin)) -> list[dict]:
    return await db.get_admin_request_logs(limit, offset)


@app.get("/api/admin/benchmark")
async def admin_benchmark(request: Request, _admin: dict = Depends(require_admin)) -> dict:
    import json as json_mod
    benchmark_path = Path(__file__).resolve().parent.parent / "eval" / "benchmark_results.json"
    if not benchmark_path.exists():
        return {
            "grade_distribution": {},
            "total_queries": 0,
            "avg_score": 0,
            "last_run": None,
            "per_query": [],
        }
    try:
        data = json_mod.loads(benchmark_path.read_text())
        return data
    except Exception:
        return {
            "grade_distribution": {},
            "total_queries": 0,
            "avg_score": 0,
            "last_run": None,
            "per_query": [],
        }


_transit_stations_cache: list | None = None


@app.get("/api/transit-stations")
async def transit_stations() -> list:
    import json as json_mod
    global _transit_stations_cache
    if _transit_stations_cache is not None:
        return _transit_stations_cache
    stations_path = get_settings().data_dir / "transit_stations.json"
    if not stations_path.exists():
        return []
    try:
        _transit_stations_cache = json_mod.loads(stations_path.read_text())
        return _transit_stations_cache
    except Exception:
        return []


_EMPTY_JUDGE = {
    "overall_grade_distribution": {},
    "dimension_summaries": {},
    "total_queries": 0,
    "skipped_queries": 0,
    "avg_score": 0,
    "last_run": None,
    "per_query": [],
}


@app.get("/api/admin/judge")
async def admin_judge(request: Request, _admin: dict = Depends(require_admin)) -> dict:
    import json as json_mod
    judge_path = Path(__file__).resolve().parent.parent / "eval" / "judge_results.json"
    if not judge_path.exists():
        return dict(_EMPTY_JUDGE)
    try:
        return json_mod.loads(judge_path.read_text())
    except Exception:
        return dict(_EMPTY_JUDGE)
