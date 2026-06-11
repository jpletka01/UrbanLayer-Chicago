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
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.analytics import compute_analytics
from backend.assembler import assemble_context
from backend.config import get_settings
from backend.context_manager import summarize_turn
from backend.conversation import synthesize_query
from backend.llm import tracked_create
from backend import db
from backend.models import (
    ChatChunk,
    ChatRequest,
    ContextObject,
    EventBatch,
    ImportRequest,
    MapDataRequest,
    MapDataResponse,
    RetrievalPlan,
    SaveMessagesRequest,
    TurnSummary,
)
from backend.retrieval import buildings, business, crime, food_inspections, three11, vacant
from backend.retrieval.geo import (
    COMMUNITY_AREAS,
    community_area_by_point,
    community_area_name,
    geocode_address,
    geocode_address_suggestions,
)
from backend.retrieval.map_data import crimes_for_map, permits_for_map, requests_311_for_map, zoning_for_map
from backend.retrieval.incentives import incentives_domain
from backend.retrieval.neighborhood import neighborhood_domain
from backend.retrieval.property import property_domain
from backend.retrieval.regulatory import regulatory_domain
from backend.retrieval.regulatory.aro_housing import aro_housing_by_community_area
from backend.retrieval.zoning import adjacent_parcel_zoning, lookup_zoning
from backend.retrieval.vector_search import (
    expand_cross_references,
    get_full_section,
    semantic_search,
)
from backend.router import route
from backend.synthesizer import LANGUAGE_NAMES, stream_answer


log = logging.getLogger(__name__)

_RETRIEVAL_SEM = asyncio.Semaphore(8)


async def _limited(coro):
    async with _RETRIEVAL_SEM:
        return await coro


_settings_init = get_settings()
if _settings_init.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_settings_init.sentry_dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

app = FastAPI(title="Chicago City Intelligence")

_CSRF_EXEMPT_PATHS = {
    "/api/webhook/stripe",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/events",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.url.path not in _CSRF_EXEMPT_PATHS:
                from backend.auth import _auth_enabled
                if _auth_enabled():
                    cookie_token = request.cookies.get("csrf_token", "")
                    header_token = request.headers.get("x-csrf-token", "")
                    if not cookie_token or cookie_token != header_token:
                        from starlette.responses import JSONResponse
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "CSRF token mismatch"},
                        )
        return await call_next(request)


_settings = get_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(CSRFMiddleware)


@app.on_event("startup")
async def _startup() -> None:
    get_settings()
    await db.init_db()
    await _preload_datasets()


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

    # Pre-load ML models so the first query doesn't cause a memory spike
    try:
        from backend.retrieval.vector_search import _model, _reranker
        settings = get_settings()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _model)
        log.info("Preloaded embedding model")
        if settings.reranker_enabled:
            await loop.run_in_executor(None, _reranker)
            log.info("Preloaded reranker model")
        else:
            log.info("Reranker disabled, skipping preload")
    except Exception as exc:
        log.warning("ML model preload failed: %s", exc)


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
    require_auth,
    require_tier,
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

def _user_id(user: dict | None) -> str | None:
    return user["id"] if user else None


@app.get("/api/conversations")
async def list_conversations_endpoint(
    user: dict | None = Depends(get_current_user),
) -> list[dict]:
    return await db.list_conversations(_user_id(user))


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    body: dict, user: dict | None = Depends(get_current_user),
) -> dict:
    conv_id = body.get("id", f"conv_{int(time.time() * 1000)}")
    title = body.get("title", "New conversation")
    language = body.get("language", "en")
    return await db.create_conversation(conv_id, title, _user_id(user), language=language)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(
    conv_id: str, user: dict | None = Depends(get_current_user),
) -> dict:
    conv = await db.get_conversation(conv_id, _user_id(user))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str, user: dict | None = Depends(get_current_user),
) -> dict:
    deleted = await db.delete_conversation(conv_id, _user_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.put("/api/conversations/{conv_id}/messages")
async def append_messages(
    conv_id: str, req: SaveMessagesRequest,
    user: dict | None = Depends(get_current_user),
) -> dict:
    conv = await db.get_conversation(conv_id, _user_id(user))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = [m.model_dump(exclude_none=True) for m in req.messages]
    await db.save_messages(conv_id, messages)
    return {"ok": True}


@app.patch("/api/conversations/{conv_id}/messages/{position}")
async def update_message(
    conv_id: str, position: int, body: dict,
    user: dict | None = Depends(get_current_user),
) -> dict:
    if "map_data" in body:
        await db.update_message_map_data(
            conv_id, position, body["map_data"], body.get("map_fetched_at"),
        )
    return {"ok": True}


@app.post("/api/conversations/import")
async def import_conversations(
    req: ImportRequest, user: dict | None = Depends(get_current_user),
) -> dict:
    count = await db.import_conversations(
        [c.model_dump() for c in req.conversations], _user_id(user),
    )
    return {"imported": count}


@app.delete("/api/conversations")
async def clear_conversations(
    user: dict | None = Depends(get_current_user),
) -> dict:
    await db.clear_all_conversations(_user_id(user))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Conversation sharing
# ---------------------------------------------------------------------------

@app.post("/api/conversations/{conv_id}/share", status_code=201)
async def create_share(
    conv_id: str, user: dict = Depends(require_auth),
) -> dict:
    result = await db.create_share_token(conv_id, user["id"])
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    settings = get_settings()
    base_url = settings.frontend_url or ""
    return {"token": result["token"], "url": f"{base_url}/s/{result['token']}"}


@app.get("/api/conversations/{conv_id}/share")
async def get_share_status(
    conv_id: str, user: dict | None = Depends(get_current_user),
) -> dict:
    share = await db.get_conversation_share(conv_id)
    if not share:
        return {"shared": False}
    settings = get_settings()
    base_url = settings.frontend_url or ""
    return {
        "shared": True,
        "token": share["token"],
        "url": f"{base_url}/s/{share['token']}",
        "created_at": share["created_at"],
    }


@app.delete("/api/conversations/{conv_id}/share")
async def revoke_share(
    conv_id: str, user: dict = Depends(require_auth),
) -> dict:
    revoked = await db.revoke_share(conv_id, user["id"])
    if not revoked:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"ok": True}


@app.get("/api/share/{token}")
async def get_shared_conversation(token: str) -> dict:
    conv = await db.get_shared_conversation(token)
    if conv is None:
        raise HTTPException(status_code=404, detail="Shared conversation not found")
    return conv


# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------

@app.post("/api/conversations/{conv_id}/uploads", status_code=201)
async def upload_files(
    conv_id: str, files: list[UploadFile] = File(...),
    user: dict | None = Depends(get_current_user),
) -> dict:
    settings = get_settings()

    conv = await db.get_conversation(conv_id, _user_id(user))
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
async def list_uploads(
    conv_id: str, user: dict | None = Depends(get_current_user),
) -> list[dict]:
    conv = await db.get_conversation(conv_id, _user_id(user))
    if not conv:
        raise HTTPException(404, "Conversation not found")
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
            tasks["crime"] = asyncio.create_task(_limited(
                crime.crime_by_community_area(ca, days=plan.time_range_days)
            ))
            tasks["crime_yoy"] = asyncio.create_task(_limited(
                crime.crime_yoy_by_community_area(ca, days=plan.time_range_days)
            ))
        if "311_api" in plan.sources:
            tasks["311"] = asyncio.create_task(_limited(
                three11.open_311_by_community_area(ca)
            ))
            tasks["311_oldest"] = asyncio.create_task(_limited(
                three11.open_311_oldest(ca)
            ))
        if "permits_api" in plan.sources:
            tasks["permits"] = asyncio.create_task(_limited(
                buildings.permits_by_community_area(ca)
            ))
        if "violations_api" in plan.sources:
            tasks["violations"] = asyncio.create_task(_limited(
                buildings.violations_by_community_area(ca)
            ))
        if "business_api" in plan.sources:
            tasks["business"] = asyncio.create_task(_limited(
                business.businesses_by_community_area(ca)
            ))
        if "vacant_buildings_api" in plan.sources:
            tasks["vacant"] = asyncio.create_task(_limited(
                vacant.vacant_buildings_by_community_area(ca)
            ))
        if "food_inspections_api" in plan.sources:
            tasks["food_inspections"] = asyncio.create_task(_limited(
                food_inspections.food_inspections_by_community_area(ca)
            ))

    loc = plan.location
    if plan.requires_disclaimer and loc.resolved_lat and loc.resolved_lon:
        tasks["zoning_lookup"] = asyncio.create_task(_limited(
            lookup_zoning(loc.resolved_lat, loc.resolved_lon)
        ))

    wf = plan.workflow_hint or "general"

    if "regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
        tasks["regulatory"] = asyncio.create_task(_limited(
            regulatory_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
        ))

    _aro_triggers = {"regulatory_domain", "property_domain", "neighborhood_domain", "incentives_domain"}
    if _aro_triggers & set(plan.sources) and ca is not None:
        tasks["aro_housing"] = asyncio.create_task(_limited(
            aro_housing_by_community_area(ca)
        ))

    if "property_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
        tasks["property"] = asyncio.create_task(_limited(
            property_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
        ))

    if "incentives_domain" in plan.sources:
        ca_name = loc.resolved_community_area_name
        if loc.resolved_lat and loc.resolved_lon:
            tasks["incentives"] = asyncio.create_task(_limited(
                incentives_domain(
                    loc.resolved_lat, loc.resolved_lon,
                    ca_name=ca_name, workflow=wf,
                )
            ))
        elif ca is not None:
            tasks["incentives"] = asyncio.create_task(_limited(
                incentives_domain(ca=ca, ca_name=ca_name, workflow=wf)
            ))

    if "neighborhood_domain" in plan.sources:
        tasks["neighborhood"] = asyncio.create_task(_limited(
            neighborhood_domain(
                loc.resolved_lat or 0.0,
                loc.resolved_lon or 0.0,
                community_area=ca,
                address=loc.resolved_address,
                workflow=wf,
            )
        ))

    _FAILURE_LABELS = {
        "crime": "crime statistics",
        "crime_yoy": "crime year-over-year comparison",
        "311": "311 service requests",
        "permits": "building permits",
        "violations": "building violations",
        "business": "business licenses",
        "vacant": "vacant buildings",
        "food_inspections": "food inspections",
        "aro_housing": "affordable housing data",
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
                elif key in ("zoning_lookup", "regulatory", "property", "incentives", "neighborhood", "crime_yoy"):
                    results[key] = None
                else:
                    results[key] = []
                if key in _FAILURE_LABELS:
                    partial_failures.append(_FAILURE_LABELS[key])
            else:
                results[key] = value

    prop_summary = results.get("property")
    if prop_summary is not None and hasattr(prop_summary, "data_gaps"):
        partial_failures.extend(prop_summary.data_gaps)

    code_chunks = []
    if "vector_search" in plan.sources and plan.search_query:
        chunks = await semantic_search(plan.search_query, top_k=5)
        code_chunks = await expand_cross_references(chunks)

    return assemble_context(
        plan=plan,
        crime_rows=results.get("crime") if "crime" in results else None,
        crime_yoy_data=results.get("crime_yoy"),
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
        aro_housing_rows=results.get("aro_housing") if "aro_housing" in results else None,
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


async def _fetch_map_rows(
    plan: RetrievalPlan,
    *,
    cached_community_area: int | None = None,
) -> dict[str, Any]:
    """Fetch raw geo-located rows for analytics computation."""
    ca = plan.location.resolved_community_area
    if ca is None:
        return {}

    skip_polygons = cached_community_area is not None and cached_community_area == ca

    tasks: dict[str, asyncio.Task] = {}

    if "crime_api" in plan.sources:
        tasks["crimes"] = asyncio.create_task(_limited(
            crimes_for_map(ca, days=plan.time_range_days)
        ))
    if "311_api" in plan.sources:
        tasks["requests_311"] = asyncio.create_task(_limited(
            requests_311_for_map(ca)
        ))
    if "permits_api" in plan.sources:
        tasks["building_permits"] = asyncio.create_task(_limited(
            permits_for_map(ca, days=plan.time_range_days)
        ))
    if plan.requires_disclaimer and not skip_polygons:
        tasks["zoning"] = asyncio.create_task(_limited(
            zoning_for_map(ca)
        ))

    loc = plan.location
    if not skip_polygons:
        if "regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon:
            tasks["overlay_geojson"] = asyncio.create_task(_limited(
                _fetch_overlay_geojson(loc.resolved_lat, loc.resolved_lon)
            ))

        if "incentives_domain" in plan.sources:
            if loc.resolved_lat and loc.resolved_lon:
                from backend.retrieval.incentives.tif import tif_geojson_feature
                from backend.retrieval.incentives.enterprise_zones import ez_geojson_feature
                tasks["tif_geojson"] = asyncio.create_task(_limited(
                    tif_geojson_feature(loc.resolved_lat, loc.resolved_lon)
                ))
                tasks["ez_geojson"] = asyncio.create_task(_limited(
                    ez_geojson_feature(loc.resolved_lat, loc.resolved_lon)
                ))
            elif ca is not None:
                from backend.retrieval.incentives.tif import tif_geojson_by_community_area
                tasks["tif_geojson_list"] = asyncio.create_task(_limited(
                    tif_geojson_by_community_area(ca)
                ))

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


def _simplify_geojson(fc: dict | None, tolerance: float = 0.0001) -> dict | None:
    """Simplify polygon geometries in a GeoJSON FeatureCollection."""
    if fc is None or "features" not in fc:
        return fc
    from shapely.geometry import shape, mapping
    simplified_features = []
    for feature in fc["features"]:
        geom = feature.get("geometry")
        if geom and geom.get("type") in ("Polygon", "MultiPolygon"):
            try:
                s = shape(geom).simplify(tolerance, preserve_topology=True)
                feature = {**feature, "geometry": mapping(s)}
            except Exception:
                pass
        simplified_features.append(feature)
    return {**fc, "features": simplified_features}


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
        zoning=_simplify_geojson(map_rows.get("zoning")),
        overlay_districts=_simplify_geojson(map_rows.get("overlay_geojson")),
        incentive_zones=_simplify_geojson(incentive_zones),
        queried_address=queried_address,
        capped=capped,
    )


async def _event_stream(req: ChatRequest) -> AsyncIterator[str]:
    start = time.monotonic()
    elapsed_ms = lambda: int((time.monotonic() - start) * 1000)
    request_group = str(uuid.uuid4())
    plan: RetrievalPlan | None = None
    error_msg: str | None = None
    timings: dict[str, int] = {}

    # Load turn summaries for context management
    turn_summaries: list[TurnSummary] | None = None
    if req.conversation_id:
        try:
            summary_dicts = await db.get_turn_summaries(req.conversation_id)
            if summary_dicts:
                turn_summaries = [TurnSummary(**d) for d in summary_dicts]
        except Exception:
            pass

    # Message limit enforcement + query synthesis
    try:
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

        t0 = time.monotonic()
        query = await synthesize_query(
            req.message, req.history,
            request_group=request_group,
            conversation_id=req.conversation_id,
            language=req.language,
        )
        timings["conv_synth"] = int((time.monotonic() - t0) * 1000)
    except Exception as exc:
        log.exception("Pre-routing failed")
        error_msg = f"Failed to process query: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms()))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "error", error_msg,
        ))
        return

    try:
        t0 = time.monotonic()
        plan = await route(
            query,
            request_group=request_group,
            conversation_id=req.conversation_id,
        )
        timings["router"] = int((time.monotonic() - t0) * 1000)
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
        clarification_text = plan.clarification
        if req.language != "en":
            try:
                lang_name = LANGUAGE_NAMES.get(req.language, req.language)
                resp = await tracked_create(
                    request_group=request_group,
                    conversation_id=req.conversation_id,
                    phase="translation",
                    model=settings.conversation_model,
                    max_tokens=200,
                    system=f"Translate the following text to {lang_name}. Output ONLY the translation.",
                    messages=[{"role": "user", "content": clarification_text}],
                )
                translated = "".join(
                    b.text for b in resp.content if getattr(b, "type", "") == "text"
                ).strip()
                if translated:
                    clarification_text = translated
            except Exception:
                log.warning("Clarification translation failed, using English", exc_info=True)
        yield _sse(ChatChunk(type="token", text=clarification_text, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms(), timings=timings))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "ok", None,
        ))
        return

    # Run retrieval and map-data fetch concurrently
    try:
        t0 = time.monotonic()
        context, map_rows = await asyncio.gather(
            _retrieve(plan),
            _fetch_map_rows(plan, cached_community_area=req.cached_community_area),
        )
        timings["retrieval"] = int((time.monotonic() - t0) * 1000)
    except Exception as exc:
        log.exception("Retrieval failed")
        error_msg = f"Retrieval failed: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))
        yield _sse(ChatChunk(type="done", t_ms=elapsed_ms(), timings=timings))
        asyncio.create_task(_save_request_log(
            request_group, req, plan, elapsed_ms(), "error", error_msg,
        ))
        return

    # Compute analytics from map rows and attach to context
    try:
        analytics = compute_analytics(
            crime_rows=map_rows.get("crimes"),
            three11_rows=map_rows.get("requests_311"),
            permit_rows=map_rows.get("building_permits"),
        )
        context.analytics = analytics
    except Exception:
        log.warning("Analytics computation failed", exc_info=True)

    yield _sse(ChatChunk(type="context", context=context, t_ms=elapsed_ms()))

    # Emit map data so the frontend doesn't need a separate fetch
    try:
        map_response = _build_map_response(map_rows, plan)
        if map_response:
            yield _sse(ChatChunk(type="map_data", map_data=map_response, t_ms=elapsed_ms()))
    except Exception:
        log.warning("Map response build failed", exc_info=True)

    first_token = True
    t_first_token: int | None = None
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
            language=req.language,
        ):
            chunk_t = elapsed_ms() if first_token else None
            if first_token:
                t_first_token = chunk_t
            yield _sse(ChatChunk(type="token", text=token, t_ms=chunk_t))
            first_token = False
    except Exception as exc:
        log.exception("Synthesizer failed")
        error_msg = f"Synthesizer failed: {exc}"
        yield _sse(ChatChunk(type="error", error=error_msg, t_ms=elapsed_ms()))

    if t_first_token is not None:
        timings["first_token"] = t_first_token

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

    timings["total"] = elapsed_ms()
    yield _sse(ChatChunk(type="done", t_ms=elapsed_ms(), timings=timings))

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
            language=req.language,
        )
    except Exception:
        log.warning("Failed to save request log")


# ---------------------------------------------------------------------------
# Scorecard API
# ---------------------------------------------------------------------------


async def _resolve_location(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
) -> tuple[float, float, str | None]:
    """Resolve input to (lat, lon, address). Raises HTTPException on failure."""
    resolved_lat: float | None = None
    resolved_lon: float | None = None
    resolved_address: str | None = address

    if lat is not None and lon is not None:
        resolved_lat, resolved_lon = lat, lon
    elif address:
        coords = await geocode_address(address)
        if coords:
            resolved_lat, resolved_lon = coords
    elif pin:
        from backend.retrieval.socrata import socrata_get
        settings = get_settings()
        rows = await socrata_get(
            settings.dataset_ccao_parcels,
            # Parcel Universe (pabr-t5kh) exposes coordinates as lat/lon, not
            # latitude/longitude — the latter 400s and breaks PIN-only resolution.
            {"$where": f"pin='{pin}'", "$select": "lat,lon", "$limit": 1},
            base_url=settings.cook_county_socrata_base,
        )
        if rows and rows[0].get("lat") and rows[0].get("lon"):
            resolved_lat = float(rows[0]["lat"])
            resolved_lon = float(rows[0]["lon"])

    if resolved_lat is None or resolved_lon is None:
        raise HTTPException(
            status_code=422,
            detail="Could not geocode address. Try a different format or provide lat/lon coordinates.",
        )
    return resolved_lat, resolved_lon, resolved_address


async def _fetch_scorecard_data(
    resolved_lat: float,
    resolved_lon: float,
    resolved_address: str | None,
) -> dict:
    """Fetch all domain data for a location. Returns dict with context, metadata, and failures."""
    ca = community_area_by_point(resolved_lat, resolved_lon)
    ca_name = community_area_name(ca) if ca else None

    tasks: dict[str, asyncio.Task] = {}
    wf = "property_intelligence"

    tasks["property"] = asyncio.create_task(_limited(
        property_domain(resolved_lat, resolved_lon, workflow=wf)
    ))
    tasks["regulatory"] = asyncio.create_task(_limited(
        regulatory_domain(resolved_lat, resolved_lon, workflow="site_due_diligence")
    ))
    tasks["zoning"] = asyncio.create_task(_limited(
        lookup_zoning(resolved_lat, resolved_lon)
    ))

    if ca is not None:
        tasks["incentives"] = asyncio.create_task(_limited(
            incentives_domain(
                resolved_lat, resolved_lon,
                ca_name=ca_name, workflow="site_due_diligence",
            )
        ))
        tasks["neighborhood"] = asyncio.create_task(_limited(
            neighborhood_domain(
                resolved_lat, resolved_lon,
                community_area=ca,
                address=resolved_address,
                workflow=wf,
            )
        ))
        tasks["aro_housing"] = asyncio.create_task(_limited(
            aro_housing_by_community_area(ca)
        ))
        tasks["crime"] = asyncio.create_task(_limited(
            crime.crime_by_community_area(ca)
        ))
        tasks["crime_yoy"] = asyncio.create_task(_limited(
            crime.crime_yoy_by_community_area(ca)
        ))
        tasks["violations"] = asyncio.create_task(_limited(
            buildings.violations_by_community_area(ca)
        ))

    tasks["address_311"] = asyncio.create_task(_limited(
        three11.address_311_complaints(resolved_lat, resolved_lon)
    ))

    results: dict[str, Any] = {}
    partial_failures: list[str] = []
    comparables_summary = None
    _FAILURE_MAP = {
        "property": "property records",
        "regulatory": "regulatory overlays",
        "zoning": "parcel zoning",
        "incentives": "incentive zones",
        "neighborhood": "demographics and transit",
        "aro_housing": "affordable housing data",
        "crime": "crime statistics",
        "crime_yoy": "crime year-over-year comparison",
        "violations": "building violations",
        "address_311": "address 311 complaints",
    }

    done = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for key, value in zip(tasks.keys(), done):
        if isinstance(value, Exception):
            log.warning("Scorecard retrieval %s failed: %s", key, value)
            results[key] = None
            if key in _FAILURE_MAP:
                partial_failures.append(_FAILURE_MAP[key])
        else:
            results[key] = value

    from backend.models import RetrievalPlan, Location
    _source_tags = [
        "crime_api", "violations_api", "regulatory_domain",
        "property_domain", "incentives_domain", "neighborhood_domain",
    ]
    dummy_plan = RetrievalPlan(
        sources=_source_tags,
        location=Location(
            raw=resolved_address or "",
            resolved_lat=resolved_lat,
            resolved_lon=resolved_lon,
            resolved_community_area=ca,
            resolved_community_area_name=ca_name,
            resolved_address=resolved_address,
        ),
        intent="neighborhood_overview",
        requires_disclaimer=True,
    )

    from backend.assembler import assemble_context as _assemble
    ctx = _assemble(
        plan=dummy_plan,
        crime_rows=results.get("crime"),
        crime_yoy_data=results.get("crime_yoy"),
        address_311_data=results.get("address_311"),
        violation_data=results.get("violations") if results.get("violations") else None,
        zoning_info=results.get("zoning"),
        regulatory_summary=results.get("regulatory"),
        property_summary=results.get("property"),
        incentives_summary=results.get("incentives"),
        neighborhood_summary=results.get("neighborhood"),
        aro_housing_rows=results.get("aro_housing"),
        partial_failures=partial_failures,
    )

    # Phase 2: comparable sales (needs property class from phase 1)
    prop = results.get("property")
    if prop and getattr(prop, "bldg_class", None) and len(prop.bldg_class) > 0:
        class_prefix = prop.bldg_class[0]
        try:
            from backend.retrieval.property.sales import nearby_comparable_sales
            from backend.models import ComparableSale, ComparablesSummary
            comps_data = await _limited(
                nearby_comparable_sales(resolved_lat, resolved_lon, class_prefix)
            )
            if comps_data.get("sales"):
                s = comps_data["summary"]
                comparables_summary = ComparablesSummary(
                    median_sale_price=s.get("median_sale_price"),
                    median_price_per_land_sqft=s.get("median_price_per_land_sqft"),
                    median_price_per_bldg_sqft=s.get("median_price_per_bldg_sqft"),
                    price_range_min=s.get("price_range_min"),
                    price_range_max=s.get("price_range_max"),
                    sales_volume=s.get("sales_volume", 0),
                    sales=[ComparableSale(**sale) for sale in comps_data["sales"]],
                )
        except Exception as exc:
            log.warning("Scorecard comparable sales failed: %s", exc)
            partial_failures.append("comparable sales")

    return {
        "address": resolved_address,
        "lat": resolved_lat,
        "lon": resolved_lon,
        "community_area": ca,
        "community_area_name": ca_name,
        "context": ctx,
        "comparables": comparables_summary,
        "partial_failures": partial_failures,
    }


@app.get("/api/scorecard")
async def scorecard(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
) -> dict:
    """Non-AI instant-load property dashboard. Zero LLM cost."""
    resolved_lat, resolved_lon, resolved_address = await _resolve_location(
        address, lat, lon, pin
    )
    data = await _fetch_scorecard_data(resolved_lat, resolved_lon, resolved_address)
    data["context"] = data["context"].model_dump(exclude_none=True)
    if data.get("comparables"):
        data["comparables"] = data["comparables"].model_dump(exclude_none=True)
    else:
        data["comparables"] = None
    return data


@app.get("/api/explore")
async def explore(
    community_area: int,
    class_prefix: str | None = None,
    limit: int = 200,
    offset: int = 0,
    _user: dict = Depends(require_tier("premium")),
) -> dict:
    """Bulk parcel exploration by community area and property class."""
    from backend.retrieval.explore import explore_parcels
    from backend.retrieval.geo import community_area_bounds as _ca_bounds

    settings = get_settings()
    limit = min(limit, settings.limit_explore_max)

    parcels, total, ca_name = await explore_parcels(
        community_area, class_prefix=class_prefix, limit=limit, offset=offset
    )

    bounds = _ca_bounds(community_area)

    return {
        "community_area": community_area,
        "community_area_name": ca_name,
        "bounds": list(bounds) if bounds else None,
        "parcels": parcels,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/explore/map")
async def explore_map(
    community_area: int,
    class_prefix: str | None = None,
    _user: dict = Depends(require_tier("premium")),
) -> dict:
    """All parcels for the map layer (up to 5000). Separate from paginated table."""
    from backend.retrieval.explore import explore_parcels

    settings = get_settings()
    parcels, total, _ = await explore_parcels(
        community_area, class_prefix=class_prefix,
        limit=settings.limit_explore_map, offset=0,
    )

    return {
        "parcels": parcels,
        "total": total,
    }


_ZONE_PREFIX_COLORS: dict[str, tuple[int, int, int]] = {
    "RS": (255, 235, 59),
    "RT": (255, 224, 130),
    "RM": (255, 213, 79),
    "B": (66, 133, 244),
    "C": (156, 39, 176),
    "M": (233, 30, 99),
    "PD": (158, 158, 158),
    "PMD": (176, 176, 176),
    "D": (0, 150, 136),
    "DC": (0, 150, 136),
    "DX": (38, 166, 154),
    "DR": (77, 182, 172),
    "DS": (0, 137, 123),
    "T": (141, 110, 99),
    "P": (76, 175, 80),
    "POS": (102, 187, 106),
}
_ZONE_FALLBACK = (120, 120, 120)

_ZONE_LABELS: dict[str, str] = {
    "RS": "Residential Single",
    "RT": "Residential Two-Flat",
    "RM": "Residential Multi",
    "B": "Business",
    "C": "Commercial",
    "M": "Manufacturing",
    "PD": "Planned Dev",
    "PMD": "Planned Mfg",
    "D": "Downtown",
    "DC": "Downtown Core",
    "DX": "Downtown Mixed",
    "DR": "Downtown Res",
    "DS": "Downtown Svc",
    "T": "Transportation",
    "P": "Parks",
    "POS": "Open Space",
}


def _zone_prefix(zone_class: str) -> str:
    import re
    m = re.match(r"^([A-Z]+)", (zone_class or "").strip().upper())
    return m.group(1) if m else ""


def _latlon_to_px(
    lat: float, lon: float,
    lat0: float, lon0: float,
    zoom: int, w: int, h: int,
) -> tuple[float, float]:
    from math import log, tan, radians, cos, pi
    scale = 256 * (2 ** zoom)
    x = (lon + 180) / 360 * scale
    y = (1 - log(tan(radians(lat)) + 1 / cos(radians(lat))) / pi) / 2 * scale
    cx = (lon0 + 180) / 360 * scale
    cy = (1 - log(tan(radians(lat0)) + 1 / cos(radians(lat0))) / pi) / 2 * scale
    return (x - cx + w / 2) * 2, (y - cy + h / 2) * 2


def _generate_zoning_map(
    lat: float,
    lon: float,
    zoning_geojson: dict,
    basemap_bytes: bytes,
    overlay_geojson: dict | None = None,
) -> str | None:
    """Generate a base64-encoded PNG map with zoning polygon overlays and regulatory boundaries."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
        from PIL import Image
    except ImportError:
        log.warning("matplotlib/Pillow not available, skipping zoning map")
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 15

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(
            figsize=(img_w / dpi, img_h / dpi), dpi=dpi,
        )
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        seen_prefixes: dict[str, tuple[float, float, float]] = {}

        features = zoning_geojson.get("features") or []
        for feat in features:
            props = feat.get("properties") or {}
            zone_class = props.get("ZONE_CLASS", "")
            prefix = _zone_prefix(zone_class)
            rgb = _ZONE_PREFIX_COLORS.get(prefix, _ZONE_FALLBACK)
            fc = (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

            if prefix and prefix not in seen_prefixes:
                seen_prefixes[prefix] = fc

            geom = feat.get("geometry") or {}
            geom_type = geom.get("type", "")
            coord_rings: list[list] = []

            if geom_type == "Polygon":
                coord_rings = geom.get("coordinates") or []
            elif geom_type == "MultiPolygon":
                for poly in geom.get("coordinates") or []:
                    coord_rings.extend(poly)

            for ring in coord_rings:
                pixels = []
                in_view = False
                for coord in ring:
                    px, py = _latlon_to_px(
                        coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H,
                    )
                    pixels.append((px, py))
                    if 0 <= px <= img_w and 0 <= py <= img_h:
                        in_view = True

                if not in_view or len(pixels) < 3:
                    continue

                patch = MplPolygon(
                    pixels, closed=True,
                    facecolor=(*fc, 0.35),
                    edgecolor=(*fc, 0.7),
                    linewidth=0.5,
                )
                ax.add_patch(patch)

        # Draw regulatory overlay boundaries (dashed outlines)
        _OVERLAY_COLORS = {
            "landmark_district": ("#f59e0b", "Landmark"),
            "historic_district": ("#f59e0b", "Historic"),
            "national_register": ("#fbbf24", "Nat'l Register"),
            "planned_development": ("#8b5cf6", "Planned Dev"),
            "ssa": ("#06b6d4", "SSA"),
            "pedestrian_street": ("#ec4899", "Ped. Street"),
        }
        overlay_legend: list[tuple[str, str, str]] = []
        if overlay_geojson:
            for feat in (overlay_geojson.get("features") or []):
                props = feat.get("properties") or {}
                otype = props.get("overlay_type", "")
                if otype not in _OVERLAY_COLORS:
                    continue
                color_hex, label = _OVERLAY_COLORS[otype]
                oname = props.get("NAME") or props.get("DIST_NAME") or label
                if (color_hex, oname) not in [(c, n) for c, _, n in overlay_legend]:
                    overlay_legend.append((color_hex, label, oname))

                geom = feat.get("geometry") or {}
                geom_type = geom.get("type", "")
                coord_rings: list[list] = []
                if geom_type == "Polygon":
                    coord_rings = geom.get("coordinates") or []
                elif geom_type == "MultiPolygon":
                    for poly in geom.get("coordinates") or []:
                        coord_rings.extend(poly)

                for ring in coord_rings:
                    pixels = []
                    for coord in ring:
                        px, py = _latlon_to_px(coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H)
                        pixels.append((px, py))
                    if len(pixels) < 3:
                        continue
                    patch = MplPolygon(
                        pixels, closed=True,
                        facecolor="none",
                        edgecolor=color_hex,
                        linewidth=1.5,
                        linestyle="--",
                        zorder=8,
                    )
                    ax.add_patch(patch)

        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(
            pin_px, pin_py, "o",
            markersize=10, color="#c96442",
            markeredgecolor="white", markeredgewidth=2,
            zorder=10,
        )

        if seen_prefixes:
            sorted_prefixes = sorted(
                seen_prefixes.items(),
                key=lambda kv: list(_ZONE_PREFIX_COLORS.keys()).index(kv[0])
                if kv[0] in _ZONE_PREFIX_COLORS else 99,
            )
            legend_handles = []
            for prefix, color in sorted_prefixes:
                label = _ZONE_LABELS.get(prefix, prefix)
                handle = plt.Line2D(
                    [0], [0], marker="s", color="none",
                    markerfacecolor=(*color, 0.6),
                    markeredgecolor=(*color, 0.9),
                    markersize=6, label=label,
                )
                legend_handles.append(handle)

            for color_hex, label, oname in overlay_legend:
                handle = plt.Line2D(
                    [0], [0], color=color_hex,
                    linewidth=1.5, linestyle="--",
                    label=oname[:20],
                )
                legend_handles.append(handle)

            legend = ax.legend(
                handles=legend_handles,
                loc="upper right",
                fontsize=5.5,
                frameon=True,
                framealpha=0.8,
                facecolor="#1a1a1a",
                edgecolor="#333333",
                labelcolor="white",
                handletextpad=0.4,
                borderpad=0.4,
                borderaxespad=0.6,
            )
            legend.set_zorder(20)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: City of Chicago Zoning Map (ArcGIS) · Mapbox · OpenStreetMap",
            ha="center", va="bottom",
            fontsize=4.5, color="#999999",
            bbox=dict(
                facecolor="#0d0d0d", alpha=0.7,
                edgecolor="none", pad=3,
            ),
            zorder=15,
        )

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", bbox_inches="tight",
            pad_inches=0, facecolor="#0d0d0d",
        )
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate zoning map", exc_info=True)
        return None


def _generate_construction_map(
    lat: float,
    lon: float,
    projects: list[dict],
    basemap_bytes: bytes,
) -> str | None:
    """Generate a base64-encoded PNG map with construction/demolition markers."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 14

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        has_construction = False
        has_demolition = False

        for idx, proj in enumerate(projects[:10], start=1):
            try:
                plat = float(proj.get("latitude", 0))
                plon = float(proj.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if plat == 0 or plon == 0:
                continue

            px, py = _latlon_to_px(plat, plon, lat, lon, ZOOM, MAP_W, MAP_H)
            if not (0 <= px <= img_w and 0 <= py <= img_h):
                continue

            ptype = proj.get("permit_type", "")
            is_demo = "WRECKING" in ptype or "DEMOLITION" in ptype
            if is_demo:
                color = "#ef4444"
                marker = "s"
                has_demolition = True
            else:
                color = "#10b981"
                marker = "o"
                has_construction = True
            ax.plot(px, py, marker, markersize=10, color=color,
                    markeredgecolor="white", markeredgewidth=1.2, zorder=5)
            ax.text(px, py, str(idx), ha="center", va="center",
                    fontsize=5.5, fontweight="bold", color="white", zorder=6)

        # Subject property pin
        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(pin_px, pin_py, "D", markersize=9, color="#2563eb",
                markeredgecolor="white", markeredgewidth=2, zorder=10)

        legend_handles = []
        if has_construction:
            legend_handles.append(plt.Line2D(
                [0], [0], marker="o", color="none", markerfacecolor="#10b981",
                markeredgecolor="white", markersize=6, label="New Construction",
            ))
        if has_demolition:
            legend_handles.append(plt.Line2D(
                [0], [0], marker="s", color="none", markerfacecolor="#ef4444",
                markeredgecolor="white", markersize=6, label="Demolition",
            ))
        legend_handles.append(plt.Line2D(
            [0], [0], marker="D", color="none", markerfacecolor="#2563eb",
            markeredgecolor="white", markersize=6, label="Subject Property",
        ))

        legend = ax.legend(
            handles=legend_handles, loc="upper right", fontsize=5.5,
            frameon=True, framealpha=0.8, facecolor="#1a1a1a",
            edgecolor="#333333", labelcolor="white",
            handletextpad=0.4, borderpad=0.4, borderaxespad=0.6,
        )
        legend.set_zorder(20)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: City of Chicago Building Permits · Mapbox · OpenStreetMap",
            ha="center", va="bottom", fontsize=4.5, color="#999999",
            bbox=dict(facecolor="#0d0d0d", alpha=0.7, edgecolor="none", pad=3),
            zorder=15,
        )

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate construction map", exc_info=True)
        return None


def _generate_comps_map(
    lat: float,
    lon: float,
    sales: list["ComparableSale"],
    basemap_bytes: bytes,
) -> str | None:
    """Generate a base64-encoded PNG map with comparable sale locations."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 15

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        for i, sale in enumerate(sales[:15]):
            slat = getattr(sale, "lat", None) or (sale.get("lat") if isinstance(sale, dict) else None)
            slon = getattr(sale, "lon", None) or (sale.get("lon") if isinstance(sale, dict) else None)
            if not slat or not slon:
                continue
            px, py = _latlon_to_px(slat, slon, lat, lon, ZOOM, MAP_W, MAP_H)
            if not (0 <= px <= img_w and 0 <= py <= img_h):
                continue
            ax.plot(
                px, py, "D",
                markersize=7, color="#22d3ee",
                markeredgecolor="white", markeredgewidth=0.8,
                zorder=5,
            )
            ax.annotate(
                str(i + 1),
                (px, py), color="white", fontsize=4.5,
                fontweight="bold", ha="center", va="center",
                zorder=6,
            )

        # Subject property
        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(
            pin_px, pin_py, "o",
            markersize=10, color="#c96442",
            markeredgecolor="white", markeredgewidth=2,
            zorder=10,
        )

        legend_handles = [
            plt.Line2D([0], [0], marker="D", color="none", markerfacecolor="#22d3ee",
                       markeredgecolor="white", markersize=6, label="Comparable Sale"),
            plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="#c96442",
                       markeredgecolor="white", markersize=6, label="Subject Property"),
        ]
        legend = ax.legend(
            handles=legend_handles, loc="upper right",
            fontsize=5.5, frameon=True, framealpha=0.8,
            facecolor="#1a1a1a", edgecolor="#333333", labelcolor="white",
            handletextpad=0.4, borderpad=0.4, borderaxespad=0.6,
        )
        legend.set_zorder(20)

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate comps map", exc_info=True)
        return None


def _generate_comps_chart(comps: "ComparablesSummary") -> str | None:
    """Generate a base64-encoded PNG scatter chart of comparable sales."""
    import base64
    import io
    from datetime import datetime

    if not comps or not comps.sales or len(comps.sales) < 2:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        log.warning("matplotlib not available, skipping comps chart")
        return None

    dates = []
    prices = []
    for s in comps.sales:
        if s.sale_date and s.sale_price:
            try:
                dt = datetime.strptime(s.sale_date[:10], "%Y-%m-%d")
                dates.append(dt)
                prices.append(s.sale_price)
            except ValueError:
                continue

    if len(dates) < 2:
        return None

    fig, ax = plt.subplots(figsize=(5.5, 2.5), dpi=150)
    ax.scatter(
        dates, [p / 1000 for p in prices],
        c="#2563eb", s=50, zorder=3, edgecolors="white", linewidth=0.5,
    )

    if comps.median_sale_price:
        ax.axhline(
            y=comps.median_sale_price / 1000,
            color="#9ca3af", linestyle="--", linewidth=0.8,
            label=f"Median ${comps.median_sale_price:,.0f}",
        )
        ax.legend(fontsize=7, loc="upper left", frameon=False)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.set_ylabel("Sale Price ($K)", fontsize=8, color="#374151")
    ax.set_xlabel("", fontsize=8)
    ax.tick_params(axis="both", labelsize=7, colors="#6b7280")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.grid(axis="y", color="#f3f4f6", linewidth=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _comp_class_prefix(bldg_class: str | None, zone_class: str | None) -> str:
    """Choose the Cook County class prefix for comparable-sales search.

    Marketable subjects use their own class family (first digit). Non-marketable
    subjects (exempt class "EX", or non-numeric/unknown classes that never trade)
    fall back to a class implied by zoning, so a redevelopment reader still gets
    comps. Cook County: 2xx residential, 5xx commercial/industrial.
    """
    bc = (bldg_class or "").strip().upper()
    if bc and bc[0].isdigit() and not bc.startswith("EX"):
        return bc[0]

    z = (zone_class or "").strip().upper()
    if z.startswith(("RS", "RT", "RM", "DR")):
        return "2"
    if z.startswith(("B", "C", "M", "DX", "DC", "DS", "PMD")):
        return "5"
    return "2"  # default to residential comps


async def _fetch_report_data(
    resolved_lat: float,
    resolved_lon: float,
    resolved_address: str | None,
) -> "ReportData":
    """Fetch all data for a v2 development feasibility report."""
    from backend.models import (
        ComparablesSummary, ComparableSale, NearbyDevelopment, ReportData,
    )
    from backend.retrieval.buildings import (
        address_specific_permits, address_specific_violations,
        nearby_new_construction, parse_chicago_address,
    )
    from backend.retrieval.property.sales import nearby_comparable_sales
    from backend.zoning_extract import calculate_development_potential, extract_zoning_standards

    settings = get_settings()

    # Step 1: Base scorecard data
    base = await _fetch_scorecard_data(resolved_lat, resolved_lon, resolved_address)
    ctx = base["context"]
    partial_failures: list[str] = list(base.get("partial_failures", []))

    # Step 2: v2 data retrievals in parallel
    zone_class = ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
    v2_tasks: dict[str, asyncio.Task] = {}

    if zone_class:
        v2_tasks["zoning_standards"] = asyncio.create_task(
            _limited(extract_zoning_standards(zone_class, request_group="report"))
        )

    v2_tasks["adjacent_zoning"] = asyncio.create_task(
        _limited(adjacent_parcel_zoning(resolved_lat, resolved_lon))
    )

    if resolved_address:
        parsed = parse_chicago_address(resolved_address)
        if parsed:
            v2_tasks["address_permits"] = asyncio.create_task(
                _limited(address_specific_permits(
                    parsed["number"], parsed["direction"], parsed["name"]
                ))
            )
            v2_tasks["address_violations"] = asyncio.create_task(
                _limited(address_specific_violations(
                    parsed["number"], parsed["direction"], parsed["name"]
                ))
            )

    # Comparable sales. For marketable parcels use the subject's own class family;
    # for non-marketable subjects (exempt / unknown class) derive the comp class
    # from zoning so a redevelopment reader still gets a valuation basis.
    class_prefix = _comp_class_prefix(
        ctx.property.bldg_class if ctx.property else None, zone_class
    )
    if class_prefix:
        v2_tasks["comparable_sales"] = asyncio.create_task(
            _limited(nearby_comparable_sales(resolved_lat, resolved_lon, class_prefix))
        )

    v2_tasks["nearby_construction"] = asyncio.create_task(
        _limited(nearby_new_construction(resolved_lat, resolved_lon, radius_deg=settings.nearby_construction_radius_deg))
    )

    # Gather v2 results
    v2_done = await asyncio.gather(*v2_tasks.values(), return_exceptions=True)
    v2_results: dict[str, Any] = {}
    _V2_FAILURE_MAP = {
        "zoning_standards": "zoning code extraction",
        "adjacent_zoning": "adjacent zoning",
        "address_permits": "address-specific permits",
        "address_violations": "address-specific violations",
        "comparable_sales": "comparable sales",
        "nearby_construction": "nearby construction activity",
    }
    for key, value in zip(v2_tasks.keys(), v2_done):
        if isinstance(value, Exception):
            log.warning("Report v2 retrieval %s failed: %s", key, value)
            v2_results[key] = None
            if key in _V2_FAILURE_MAP:
                partial_failures.append(_V2_FAILURE_MAP[key])
        else:
            v2_results[key] = value

    # Step 3: Calculate development potential
    standards = v2_results.get("zoning_standards")
    # R1: when AI extraction is unavailable or low-confidence, fall back to the
    # deterministic Title 17 zone-class table so we never dump wrong-chapter raw
    # code and development potential can still be computed for known zones.
    if zone_class and (standards is None or standards.extraction_confidence == "low"):
        from backend.zoning_extract import standards_from_definitions
        fallback_standards = standards_from_definitions(zone_class)
        if fallback_standards is not None:
            standards = fallback_standards
    dev_potential = None
    if standards and ctx.property:
        land_sqft = ctx.property.land_sqft or 0
        bldg_sqft = ctx.property.bldg_sqft or 0
        if land_sqft > 0:
            dev_potential = calculate_development_potential(standards, land_sqft, bldg_sqft)

    # Step 4: Effective tax rate
    effective_tax_rate = None
    if ctx.property:
        assessed = ctx.property.total_assessed_value
        annual_tax = ctx.property.estimated_annual_tax
        # Fallback: use most recent assessment total if direct value is missing
        if not assessed and ctx.property.assessment_history:
            for ah in ctx.property.assessment_history:
                if ah.total and ah.total > 0:
                    assessed = ah.total
                    break
        if assessed and assessed > 0 and annual_tax and annual_tax > 0:
            # Cook County: market value ≈ assessed / 0.10 (residential)
            market_value = assessed / 0.10
            effective_tax_rate = round(annual_tax / market_value, 4)

    # Step 5: Static map URL
    mapbox_token = settings.mapbox_token or settings.vite_mapbox_token
    static_map_url = None
    if mapbox_token:
        static_map_url = (
            f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
            f"pin-l+2563eb({resolved_lon},{resolved_lat})/"
            f"{resolved_lon},{resolved_lat},15/600x400@2x"
            f"?access_token={mapbox_token}"
        )

    # Step 6: Build bulk standards text fallback (for low-confidence extraction)
    bulk_standards_text = ""
    if zone_class:
        try:
            chunks = await _limited(
                semantic_search(
                    f"{zone_class} bulk standards floor area ratio height setback lot coverage",
                    top_k=5,
                )
            )
            if chunks:
                bulk_standards_text = "\n\n".join(
                    f"[{c.section_title}]\n{c.text}" for c in chunks[:3]
                )
        except Exception:
            pass

    # Build comparable sales summary
    comps_data = v2_results.get("comparable_sales") or {"summary": {}, "sales": []}
    comps_summary = None
    if comps_data.get("sales"):
        s = comps_data["summary"]
        comps_summary = ComparablesSummary(
            median_sale_price=s.get("median_sale_price"),
            median_price_per_land_sqft=s.get("median_price_per_land_sqft"),
            median_price_per_bldg_sqft=s.get("median_price_per_bldg_sqft"),
            price_range_min=s.get("price_range_min"),
            price_range_max=s.get("price_range_max"),
            sales_volume=s.get("sales_volume", 0),
            comp_basis=s.get("comp_basis"),
            sales=[ComparableSale(**sale) for sale in comps_data["sales"]],
        )

    # Build nearby development
    nc_data = v2_results.get("nearby_construction")
    nearby_dev = None
    if nc_data:
        projects = nc_data.get("recent_projects", [])
        projects = _enrich_nearby_projects(resolved_lat, resolved_lon, projects)
        nearby_dev = NearbyDevelopment(
            new_construction_count=nc_data.get("new_construction_count", 0),
            demolition_count=nc_data.get("demolition_count", 0),
            recent_projects=projects,
        )

    # Generate comparable sales chart + map
    comps_chart_b64 = None
    comps_map_b64 = None
    if comps_summary and comps_summary.sales and len(comps_summary.sales) >= 2:
        loop = asyncio.get_running_loop()
        try:
            comps_chart_b64 = await loop.run_in_executor(
                None, _generate_comps_chart, comps_summary
            )
        except Exception:
            log.warning("Failed to generate comps chart", exc_info=True)

    # Fetch basemaps for maps (zoom 15 for zoning, zoom 14 for construction)
    basemap_bytes = None
    basemap_wide_bytes = None
    if mapbox_token:
        try:
            async with httpx.AsyncClient(timeout=15) as map_client:
                basemap_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},15/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                basemap_wide_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},14/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                resp, resp_wide = await asyncio.gather(
                    map_client.get(basemap_url),
                    map_client.get(basemap_wide_url),
                )
                if resp.status_code == 200:
                    basemap_bytes = resp.content
                if resp_wide.status_code == 200:
                    basemap_wide_bytes = resp_wide.content
        except Exception:
            log.warning("Failed to fetch basemap for report maps", exc_info=True)

    # Fetch overlay GeoJSON for zoning map boundaries
    overlay_geojson = None
    _OVERLAY_MAP_LAYERS = [2, 5, 6, 7, 8, 9, 23]  # PD, landmark, historic, landmark bldg, nat'l register, special, SSA
    try:
        from backend.retrieval.regulatory.overlays import overlay_geojson_features
        overlay_geojson = await _limited(overlay_geojson_features(resolved_lat, resolved_lon, _OVERLAY_MAP_LAYERS))
    except Exception:
        log.warning("Failed to fetch overlay GeoJSON for zoning map", exc_info=True)

    # Generate zoning map
    zoning_map_b64 = None
    ca = base.get("community_area")
    if ca and basemap_bytes:
        try:
            from backend.retrieval.zoning import zoning_polygons_for_map
            zoning_geojson = await _limited(zoning_polygons_for_map(ca))
            if zoning_geojson.get("features"):
                loop = asyncio.get_running_loop()
                zoning_map_b64 = await loop.run_in_executor(
                    None,
                    _generate_zoning_map,
                    resolved_lat, resolved_lon,
                    zoning_geojson, basemap_bytes,
                    overlay_geojson,
                )
        except Exception:
            log.warning("Failed to generate zoning map", exc_info=True)

    # Generate construction/demolition map (wider zoom for 0.5mi radius)
    construction_map_b64 = None
    construction_basemap = basemap_wide_bytes or basemap_bytes
    if construction_basemap and nearby_dev and nearby_dev.recent_projects:
        try:
            loop = asyncio.get_running_loop()
            construction_map_b64 = await loop.run_in_executor(
                None,
                _generate_construction_map,
                resolved_lat, resolved_lon,
                nearby_dev.recent_projects, construction_basemap,
            )
        except Exception:
            log.warning("Failed to generate construction map", exc_info=True)

    # Generate comparable sales map
    if basemap_bytes and comps_summary and comps_summary.sales and len(comps_summary.sales) >= 2:
        try:
            loop = asyncio.get_running_loop()
            comps_map_b64 = await loop.run_in_executor(
                None, _generate_comps_map,
                resolved_lat, resolved_lon,
                comps_summary.sales, basemap_bytes,
            )
        except Exception:
            log.warning("Failed to generate comps map", exc_info=True)

    # Assessment trend analysis
    assessment_trend = None
    if ctx.property and ctx.property.assessment_history:
        assessment_trend = _compute_assessment_trend(ctx.property.assessment_history)

    # Ownership signals
    ownership_signals: list[dict] = []
    if ctx.property:
        ownership_signals = _derive_ownership_signals(ctx.property)

    # Parcel map + dimensions
    parcel_map_b64 = None
    parcel_dimensions = None
    if ctx.property and ctx.property.parcel_geometry:
        parcel_dimensions = _compute_parcel_dimensions(ctx.property.parcel_geometry)
        if basemap_bytes:
            # Fetch a higher-zoom basemap for the parcel map
            parcel_basemap_bytes = None
            if mapbox_token:
                parcel_basemap_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},19/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                try:
                    parcel_resp = await httpx.AsyncClient(timeout=15).get(parcel_basemap_url)
                    if parcel_resp.status_code == 200:
                        parcel_basemap_bytes = parcel_resp.content
                except Exception:
                    log.warning("Failed to fetch parcel basemap", exc_info=True)
            if parcel_basemap_bytes:
                try:
                    loop = asyncio.get_running_loop()
                    parcel_map_b64 = await loop.run_in_executor(
                        None, _generate_parcel_map,
                        resolved_lat, resolved_lon,
                        ctx.property.parcel_geometry, parcel_basemap_bytes,
                        parcel_dimensions,
                    )
                except Exception:
                    log.warning("Failed to generate parcel map", exc_info=True)

    # Zone class definitions (deterministic lookup, no API call)
    from backend.retrieval.zoning_definitions import collect_report_zone_definitions
    adj_zoning = v2_results.get("adjacent_zoning") or {}
    zone_defs = collect_report_zone_definitions(zone_class, adj_zoning)
    zone_definitions_data = [
        {
            "zone_class": zd.zone_class,
            "name": zd.name,
            "code_section": zd.code_section,
            "far": zd.far,
            "max_height": zd.max_height,
            "lot_coverage": zd.lot_coverage,
            "uses": zd.uses,
            "notes": zd.notes,
            "is_fallback": zd.is_fallback,
        }
        for zd in zone_defs
    ]

    report = ReportData(
        address=resolved_address,
        lat=resolved_lat,
        lon=resolved_lon,
        community_area=base.get("community_area"),
        community_area_name=base.get("community_area_name"),
        context=ctx,
        zoning_standards=standards,
        development_potential=dev_potential,
        comparables=comps_summary,
        address_permits=v2_results.get("address_permits") or [],
        address_violations=v2_results.get("address_violations") or [],
        adjacent_zoning=adj_zoning,
        nearby_development=nearby_dev,
        effective_tax_rate=effective_tax_rate,
        assessment_trend=assessment_trend,
        ownership_signals=ownership_signals,
        parcel_map_b64=parcel_map_b64,
        parcel_dimensions=parcel_dimensions,
        static_map_url=static_map_url,
        comps_chart_b64=comps_chart_b64,
        comps_map_b64=comps_map_b64,
        zoning_map_b64=zoning_map_b64,
        construction_map_b64=construction_map_b64,
        bulk_standards_text=bulk_standards_text,
        zone_definitions=zone_definitions_data,
        partial_failures=partial_failures,
    )

    # V5 synthesis (all deterministic, no API calls)
    report.opportunities, report.constraints = _synthesize_opportunities_constraints(report)
    report.estimated_land_value = _compute_land_value_range(report)
    report.approval_pathway = _compute_approval_pathway(report)
    report.development_trend = _compute_development_trend(report)
    report.incentive_stacking_narrative = _build_incentive_stacking_narrative(report)
    report.envelope_summary = _build_envelope_summary(report)

    # Phase 3 decision-quality synthesis (depends on the V5 fields above)
    report.far_utilization = _compute_far_utilization(report)
    report.unit_yield = _compute_unit_yield(report)
    report.comp_valuation = _compute_comp_valuation(report)
    report.ownership_interpretation = _ownership_interpretation(report)
    report.decision_box = _build_decision_box(report)

    # Envelope map (CPU-bound matplotlib render)
    if ctx.property and ctx.property.parcel_geometry and standards:
        try:
            loop = asyncio.get_running_loop()
            env_b64, env_sqft = await loop.run_in_executor(
                None, _generate_envelope_map,
                resolved_lat, resolved_lon,
                ctx.property.parcel_geometry, standards,
                parcel_dimensions,
            )
            report.envelope_map_b64 = env_b64
            report.buildable_footprint_sqft = env_sqft
        except Exception:
            log.warning("Failed to generate envelope map", exc_info=True)

    return report, basemap_bytes, basemap_wide_bytes


def _enrich_nearby_projects(
    lat: float, lon: float, projects: list[dict],
) -> list[dict]:
    """Add distance_mi and formatted_address to each nearby project."""
    from backend.retrieval.property.sales import _haversine_mi
    enriched = []
    for proj in projects:
        p = dict(proj)
        try:
            plat = float(p.get("latitude", 0))
            plon = float(p.get("longitude", 0))
            if plat and plon:
                p["distance_mi"] = round(_haversine_mi(lat, lon, plat, plon), 2)
        except (ValueError, TypeError):
            pass
        parts = []
        if p.get("street_number"):
            parts.append(str(p["street_number"]))
        if p.get("street_direction"):
            parts.append(str(p["street_direction"]))
        if p.get("street_name"):
            parts.append(str(p["street_name"]))
        if parts:
            p["formatted_address"] = " ".join(parts)
        enriched.append(p)
    enriched.sort(key=lambda x: x.get("distance_mi", 999))
    return enriched


def _compute_assessment_trend(
    assessment_history: list,
) -> dict | None:
    """Compute assessment trend from assessment history records."""
    valid = [a for a in assessment_history if a.total and a.total > 0 and a.year]
    if len(valid) < 2:
        return None
    valid.sort(key=lambda a: a.year)
    oldest, newest = valid[0], valid[-1]
    years = newest.year - oldest.year
    if years <= 0:
        return None
    total_change_pct = round((newest.total - oldest.total) / oldest.total * 100, 1)
    cagr_pct = round(((newest.total / oldest.total) ** (1.0 / years) - 1) * 100, 1)
    direction = "increasing" if total_change_pct > 5 else "decreasing" if total_change_pct < -5 else "stable"
    return {
        "total_change_pct": total_change_pct,
        "cagr_pct": cagr_pct,
        "years": years,
        "oldest_year": oldest.year,
        "newest_year": newest.year,
        "oldest_total": oldest.total,
        "newest_total": newest.total,
        "direction": direction,
    }


def _derive_ownership_signals(prop) -> list[dict]:
    """Derive factual ownership signals from property data. No LLM."""
    if not prop:
        return []
    signals: list[dict] = []

    if prop.sales_history:
        sorted_sales = sorted(
            [s for s in prop.sales_history if s.date],
            key=lambda s: s.date, reverse=True,
        )
        if sorted_sales:
            last_sale = sorted_sales[0]
            from datetime import date
            try:
                sale_date = date.fromisoformat(last_sale.date[:10])
                years_held = round((date.today() - sale_date).days / 365.25, 1)
                if years_held > 10:
                    signals.append({
                        "signal": "Long-Term Hold",
                        "detail": f"Last sale {years_held:.0f} years ago ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
                elif years_held < 2:
                    signals.append({
                        "signal": "Recent Acquisition",
                        "detail": f"Acquired {years_held:.1f} years ago ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
                else:
                    signals.append({
                        "signal": "Ownership Duration",
                        "detail": f"{years_held:.0f} years since last sale ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
            except (ValueError, TypeError):
                pass

            if last_sale.price is not None and last_sale.price <= 500:
                signals.append({
                    "signal": "Non-Arm's-Length Transfer",
                    "detail": f"Last sale price ${last_sale.price:,.0f} suggests related-party transfer",
                    "category": "transfer_type",
                })
            elif last_sale.deed_type and "QUIT" in last_sale.deed_type.upper():
                signals.append({
                    "signal": "Quit Claim Deed",
                    "detail": "Last transfer via quit claim deed (non-arm's-length)",
                    "category": "transfer_type",
                })

        if len(sorted_sales) >= 2:
            for i in range(len(sorted_sales) - 1):
                try:
                    d1 = date.fromisoformat(sorted_sales[i].date[:10])
                    d2 = date.fromisoformat(sorted_sales[i + 1].date[:10])
                    gap_years = (d1 - d2).days / 365.25
                    if gap_years < 2:
                        signals.append({
                            "signal": "Rapid Turnover",
                            "detail": f"Consecutive sales {gap_years:.1f} years apart ({sorted_sales[i+1].date[:10]} → {sorted_sales[i].date[:10]})",
                            "category": "turnover",
                        })
                        break
                except (ValueError, TypeError):
                    continue

    if prop.tax_breakdown:
        for item in prop.tax_breakdown:
            agency_upper = item.agency.upper()
            if "HOMEOWNER" in agency_upper or "HOME OWNER" in agency_upper:
                signals.append({
                    "signal": "Owner-Occupied (Homeowner Exemption)",
                    "detail": f"Homeowner exemption found in tax breakdown",
                    "category": "occupancy",
                })
                break

    return signals


def _compute_parcel_dimensions(geojson_polygon: dict) -> dict | None:
    """Compute parcel dimensions from GeoJSON polygon."""
    import math
    coords = None
    geom_type = geojson_polygon.get("type", "")
    if geom_type == "Polygon":
        rings = geojson_polygon.get("coordinates", [])
        if rings:
            coords = rings[0]
    elif geom_type == "MultiPolygon":
        polys = geojson_polygon.get("coordinates", [])
        if polys and polys[0]:
            coords = polys[0][0]

    if not coords or len(coords) < 4:
        return None

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))

    edges = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dx = (lon2 - lon1) * cos_lat * 364567.2
        dy = (lat2 - lat1) * 364567.2
        length_ft = math.sqrt(dx * dx + dy * dy)
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        edges.append({"length_ft": round(length_ft, 1), "bearing": round(bearing, 1)})

    if not edges:
        return None

    # Area via shoelace formula in local feet
    xs = [(c[0] - coords[0][0]) * cos_lat * 364567.2 for c in coords]
    ys = [(c[1] - coords[0][1]) * 364567.2 for c in coords]
    n = len(xs)
    area = 0.0
    for i in range(n - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    area_sqft = abs(area) / 2.0

    perimeter_ft = sum(e["length_ft"] for e in edges)

    sorted_edges = sorted(edges, key=lambda e: e["length_ft"], reverse=True)
    frontage_ft = None
    depth_ft = None
    if len(sorted_edges) >= 2:
        # Group edges by similar bearing (within 15 degrees)
        long_edge = sorted_edges[0]
        perpendicular = []
        parallel = []
        for e in sorted_edges[1:]:
            angle_diff = abs(long_edge["bearing"] - e["bearing"]) % 180
            if angle_diff < 30 or angle_diff > 150:
                parallel.append(e)
            else:
                perpendicular.append(e)
        depth_ft = round(long_edge["length_ft"], 1)
        if perpendicular:
            frontage_ft = round(perpendicular[0]["length_ft"], 1)
        elif parallel:
            frontage_ft = round(parallel[0]["length_ft"], 1)

    return {
        "area_sqft": round(area_sqft, 0),
        "perimeter_ft": round(perimeter_ft, 1),
        "frontage_ft": frontage_ft,
        "depth_ft": depth_ft,
        "edge_count": len(edges),
        "edges": edges[:8],
    }


def _generate_parcel_map(
    lat: float,
    lon: float,
    parcel_geojson: dict,
    basemap_bytes: bytes,
    dimensions: dict | None = None,
) -> str | None:
    """Generate a base64-encoded PNG map with parcel polygon overlay.

    Uses zoom 19 so the lot boundary fills the frame. Draws the parcel
    boundary, labels each edge with its length, and adds a scale bar.
    """
    import base64
    import io
    from math import atan2, degrees

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, Polygon as MplPolygon
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 19

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        geom_type = parcel_geojson.get("type", "")
        coord_rings: list[list] = []
        if geom_type == "Polygon":
            coord_rings = parcel_geojson.get("coordinates", [])
        elif geom_type == "MultiPolygon":
            for poly in parcel_geojson.get("coordinates", []):
                coord_rings.extend(poly)

        for ring in coord_rings:
            pixels = []
            for coord in ring:
                px, py = _latlon_to_px(coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H)
                pixels.append((px, py))
            if len(pixels) < 3:
                continue

            # Fill + thick boundary
            patch = MplPolygon(
                pixels, closed=True,
                facecolor=(0.15, 0.39, 0.92, 0.15),
                edgecolor=(0.15, 0.39, 0.92, 1.0),
                linewidth=3,
            )
            ax.add_patch(patch)

            # Corner markers
            for px_pt, py_pt in pixels[:-1]:
                ax.plot(px_pt, py_pt, "s", markersize=4,
                        color="#2563eb", markeredgecolor="white",
                        markeredgewidth=0.8, zorder=12)

            # Edge dimension labels — offset outward from centroid
            if dimensions and len(pixels) >= 4:
                cx = sum(p[0] for p in pixels[:-1]) / max(len(pixels) - 1, 1)
                cy = sum(p[1] for p in pixels[:-1]) / max(len(pixels) - 1, 1)
                edges = dimensions.get("edges", [])
                for i in range(min(len(pixels) - 1, len(edges))):
                    x1, y1 = pixels[i]
                    x2, y2 = pixels[i + 1]
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    length = edges[i]["length_ft"]
                    if length < 5:
                        continue
                    # Push label outward from polygon centroid
                    dx, dy = mx - cx, my - cy
                    norm = (dx**2 + dy**2) ** 0.5 or 1
                    offset = 28
                    lx = mx + dx / norm * offset
                    ly = my + dy / norm * offset

                    # Rotate text to match edge angle
                    angle = degrees(atan2(-(y2 - y1), x2 - x1))
                    if angle > 90:
                        angle -= 180
                    elif angle < -90:
                        angle += 180

                    ax.text(
                        lx, ly, f"{length:.0f} ft",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold",
                        rotation=angle,
                        bbox=dict(facecolor="#2563eb", alpha=0.9,
                                  edgecolor="white", linewidth=0.5,
                                  pad=2.5, boxstyle="round,pad=0.3"),
                        zorder=15,
                    )

        # Info box: frontage x depth = area
        if dimensions:
            info_parts = []
            if dimensions.get("frontage_ft"):
                info_parts.append(f"Frontage: {dimensions['frontage_ft']:.0f} ft")
            if dimensions.get("depth_ft"):
                info_parts.append(f"Depth: {dimensions['depth_ft']:.0f} ft")
            if dimensions.get("area_sqft"):
                info_parts.append(f"Area: {dimensions['area_sqft']:,.0f} sq ft")
            if info_parts:
                ax.text(
                    8, 12, "  |  ".join(info_parts),
                    ha="left", va="top", fontsize=6, color="white",
                    bbox=dict(facecolor="#1a1a1a", alpha=0.85,
                              edgecolor="#444", linewidth=0.5,
                              pad=4, boxstyle="round,pad=0.3"),
                    zorder=20,
                )

        # Scale bar (bottom-left)
        from math import cos, radians
        meters_per_px = 156543.03 * cos(radians(lat)) / (2 ** ZOOM) / 2  # @2x
        ft_per_px = meters_per_px * 3.28084
        bar_ft = 50
        bar_px = bar_ft / ft_per_px
        bar_x, bar_y = 30, img_h - 40
        ax.plot([bar_x, bar_x + bar_px], [bar_y, bar_y],
                color="white", linewidth=2.5, solid_capstyle="butt", zorder=18)
        ax.plot([bar_x, bar_x], [bar_y - 4, bar_y + 4],
                color="white", linewidth=1.5, zorder=18)
        ax.plot([bar_x + bar_px, bar_x + bar_px], [bar_y - 4, bar_y + 4],
                color="white", linewidth=1.5, zorder=18)
        ax.text(bar_x + bar_px / 2, bar_y - 8, f"{bar_ft} ft",
                ha="center", va="bottom", fontsize=5.5, color="white",
                fontweight="bold", zorder=18)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: Cook County GIS · Mapbox · OpenStreetMap",
            ha="center", va="bottom", fontsize=4.5, color="#999999",
            bbox=dict(facecolor="#0d0d0d", alpha=0.7, edgecolor="none", pad=3),
            zorder=15,
        )

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate parcel map", exc_info=True)
        return None


def _classify_edges(
    coords: list[list[float]],
    front_ft: int, side_ft: int, rear_ft: int,
) -> list[dict]:
    """Classify polygon edges as front/side/rear for setback drawing.

    Heuristic for Chicago's grid: the shortest pair of roughly-parallel edges
    are front/rear (lot width), the longest pair are sides (lot depth).
    Front = shorter of the width pair (street-facing).
    """
    import math

    if len(coords) < 4:
        return []

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))

    edges = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dx = (lon2 - lon1) * cos_lat * 364567.2
        dy = (lat2 - lat1) * 364567.2
        length_ft = math.sqrt(dx * dx + dy * dy)
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        # Inward normal (perpendicular, pointing into polygon center)
        cx = sum(c[0] for c in coords[:-1]) / (len(coords) - 1)
        cy = sum(c[1] for c in coords[:-1]) / (len(coords) - 1)
        mx = (lon1 + lon2) / 2
        my = (lat1 + lat2) / 2
        # Two candidate normals
        nx1, ny1 = -dy, dx
        nx2, ny2 = dy, -dx
        # Pick the one pointing toward centroid
        to_cx = (cx - mx) * cos_lat * 364567.2
        to_cy = (cy - my) * 364567.2
        if nx1 * to_cx + ny1 * to_cy > nx2 * to_cx + ny2 * to_cy:
            nx, ny = nx1, ny1
        else:
            nx, ny = nx2, ny2
        norm = math.sqrt(nx * nx + ny * ny)
        if norm > 0:
            nx /= norm
            ny /= norm

        edges.append({
            "idx": i,
            "p1": coords[i], "p2": coords[i + 1],
            "length_ft": length_ft,
            "bearing": bearing,
            "nx_ft": nx, "ny_ft": ny,
        })

    if len(edges) < 3:
        # Fallback: uniform minimum setback
        min_sb = min(front_ft, side_ft, rear_ft)
        for e in edges:
            e["role"] = "uniform"
            e["setback_ft"] = min_sb
        return edges

    # Normalize bearing to 0-180 (undirected)
    for e in edges:
        e["norm_bearing"] = e["bearing"] % 180

    # Sort by length to find the two principal directions
    by_length = sorted(edges, key=lambda e: e["length_ft"], reverse=True)

    # Group into two bearing clusters using the longest edge as anchor
    anchor_bearing = by_length[0]["norm_bearing"]
    group_a = []  # Parallel to anchor (sides / depth)
    group_b = []  # Perpendicular to anchor (front / rear width)

    for e in edges:
        diff = abs(e["norm_bearing"] - anchor_bearing) % 180
        if diff > 90:
            diff = 180 - diff
        if diff < 30:
            group_a.append(e)
        else:
            group_b.append(e)

    # If grouping failed (irregular lot), use uniform setback
    if not group_a or not group_b:
        min_sb = min(front_ft, side_ft, rear_ft)
        for e in edges:
            e["role"] = "uniform"
            e["setback_ft"] = min_sb
        return edges

    # group_a = longer edges = sides, group_b = shorter edges = front/rear
    # But if group_b is actually longer, swap
    avg_a = sum(e["length_ft"] for e in group_a) / len(group_a)
    avg_b = sum(e["length_ft"] for e in group_b) / len(group_b)
    if avg_b > avg_a:
        group_a, group_b = group_b, group_a

    for e in group_a:
        e["role"] = "side"
        e["setback_ft"] = side_ft

    # In group_b, shortest = front, rest = rear
    group_b.sort(key=lambda e: e["length_ft"])
    for i, e in enumerate(group_b):
        if i == 0:
            e["role"] = "front"
            e["setback_ft"] = front_ft
        else:
            e["role"] = "rear"
            e["setback_ft"] = rear_ft

    return edges


def _compute_inset_polygon(
    coords: list[list[float]],
    edges: list[dict],
) -> tuple[list[tuple[float, float]], float] | None:
    """Compute the buildable footprint polygon by insetting each edge."""
    import math

    if not edges or len(coords) < 4:
        return None

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))
    ft_to_lon = 1.0 / (cos_lat * 364567.2)
    ft_to_lat = 1.0 / 364567.2

    # For each edge, compute the offset line (shifted inward by setback)
    offset_lines = []
    for e in edges:
        sb = e.get("setback_ft", 0)
        if sb <= 0:
            # No setback — keep original edge
            offset_lines.append((e["p1"], e["p2"]))
            continue
        # Offset in lon/lat space
        dx_lon = e["nx_ft"] * sb * ft_to_lon
        dy_lat = e["ny_ft"] * sb * ft_to_lat
        p1_off = [e["p1"][0] + dx_lon, e["p1"][1] + dy_lat]
        p2_off = [e["p2"][0] + dx_lon, e["p2"][1] + dy_lat]
        offset_lines.append((p1_off, p2_off))

    if len(offset_lines) < 3:
        return None

    # Intersect adjacent offset lines to find inner polygon vertices
    def line_intersect(p1, p2, p3, p4):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-15:
            return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return (ix, iy)

    inner_pts = []
    n = len(offset_lines)
    for i in range(n):
        j = (i + 1) % n
        pt = line_intersect(
            offset_lines[i][0], offset_lines[i][1],
            offset_lines[j][0], offset_lines[j][1],
        )
        if pt is None:
            return None
        inner_pts.append(pt)

    # Close the polygon
    if inner_pts and inner_pts[0] != inner_pts[-1]:
        inner_pts.append(inner_pts[0])

    # Compute area via shoelace in feet
    xs = [(p[0] - inner_pts[0][0]) * cos_lat * 364567.2 for p in inner_pts]
    ys = [(p[1] - inner_pts[0][1]) * 364567.2 for p in inner_pts]
    area = 0.0
    for i in range(len(xs) - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    area_sqft = abs(area) / 2.0

    if area_sqft < 10:
        return None

    return inner_pts, area_sqft


def _generate_envelope_map(
    lat: float, lon: float,
    parcel_geojson: dict,
    standards: "ZoningStandards",
    dimensions: dict | None = None,
) -> tuple[str | None, float | None]:
    """Render parcel with setback zones and buildable footprint.

    Returns (base64_png, buildable_footprint_sqft) or (None, None).
    """
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
    except ImportError:
        return None, None

    front_ft = standards.front_setback_ft or 0
    side_ft = standards.side_setback_ft or 0
    rear_ft = standards.rear_setback_ft or 0

    if front_ft == 0 and side_ft == 0 and rear_ft == 0:
        return None, None

    # Extract coordinates
    geom_type = parcel_geojson.get("type", "")
    coords = None
    if geom_type == "Polygon":
        rings = parcel_geojson.get("coordinates", [])
        if rings:
            coords = rings[0]
    elif geom_type == "MultiPolygon":
        polys = parcel_geojson.get("coordinates", [])
        if polys and polys[0]:
            coords = polys[0][0]

    if not coords or len(coords) < 4:
        return None, None

    edges = _classify_edges(coords, front_ft, side_ft, rear_ft)
    if not edges:
        return None, None

    inset_result = _compute_inset_polygon(coords, edges)
    if inset_result is None:
        return None, None

    inner_pts, buildable_sqft = inset_result

    try:
        import math

        lat_mid = sum(c[1] for c in coords) / len(coords)
        cos_lat = math.cos(math.radians(lat_mid))

        # Convert to local feet for rendering
        def to_ft(lon_v, lat_v):
            return (
                (lon_v - coords[0][0]) * cos_lat * 364567.2,
                (lat_v - coords[0][1]) * 364567.2,
            )

        parcel_ft = [to_ft(c[0], c[1]) for c in coords]
        inner_ft = [to_ft(p[0], p[1]) for p in inner_pts]

        # Figure size based on parcel extents
        all_x = [p[0] for p in parcel_ft]
        all_y = [p[1] for p in parcel_ft]
        w = max(all_x) - min(all_x)
        h = max(all_y) - min(all_y)
        pad = max(w, h) * 0.15

        dpi = 150
        fig_w = max(3, min(5, (w + 2 * pad) / 40))
        fig_h = max(3, min(5, (h + 2 * pad) / 40))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        ax.set_facecolor("#f8fafc")
        fig.set_facecolor("#f8fafc")

        # Parcel outline
        parcel_patch = MplPolygon(
            parcel_ft, closed=True,
            facecolor="#f3f4f6", edgecolor="#374151",
            linewidth=2, zorder=2,
        )
        ax.add_patch(parcel_patch)

        # Setback zone hatching — draw parcel minus inner as a visual
        # Simpler approach: draw hatched strips for each edge
        for e in edges:
            sb = e.get("setback_ft", 0)
            if sb <= 0:
                continue
            p1_ft = to_ft(e["p1"][0], e["p1"][1])
            p2_ft = to_ft(e["p2"][0], e["p2"][1])
            # Offset points
            ft_to_lon = 1.0 / (cos_lat * 364567.2)
            ft_to_lat = 1.0 / 364567.2
            dx_lon = e["nx_ft"] * sb * ft_to_lon
            dy_lat = e["ny_ft"] * sb * ft_to_lat
            p1_off_ft = to_ft(e["p1"][0] + dx_lon, e["p1"][1] + dy_lat)
            p2_off_ft = to_ft(e["p2"][0] + dx_lon, e["p2"][1] + dy_lat)

            strip = [p1_ft, p2_ft, p2_off_ft, p1_off_ft]
            strip_patch = MplPolygon(
                strip, closed=True,
                facecolor="#e5e7eb", edgecolor="none",
                alpha=0.6, hatch="///", zorder=3,
            )
            ax.add_patch(strip_patch)

            # Label the setback
            mx = (p1_ft[0] + p2_ft[0] + p1_off_ft[0] + p2_off_ft[0]) / 4
            my = (p1_ft[1] + p2_ft[1] + p1_off_ft[1] + p2_off_ft[1]) / 4
            role = e.get("role", "")
            label = f"{sb}' {role}" if role and role != "uniform" else f"{sb}'"
            ax.text(
                mx, my, label,
                ha="center", va="center", fontsize=6,
                color="#6b7280", fontstyle="italic",
                zorder=8,
            )

        # Buildable footprint
        inner_patch = MplPolygon(
            inner_ft, closed=True,
            facecolor=(0.15, 0.39, 0.92, 0.15),
            edgecolor="#2563eb",
            linewidth=1.5, linestyle="--",
            zorder=5,
        )
        ax.add_patch(inner_patch)

        # Buildable area annotation centered
        cx = sum(p[0] for p in inner_ft) / len(inner_ft)
        cy = sum(p[1] for p in inner_ft) / len(inner_ft)
        ax.text(
            cx, cy, f"~{buildable_sqft:,.0f} sq ft\nbuildable",
            ha="center", va="center", fontsize=7,
            color="#1e40af", fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="#93c5fd",
                      pad=3, boxstyle="round,pad=0.3"),
            zorder=10,
        )

        # Edge dimension labels on parcel outline (outside edge)
        for e in edges:
            if e["length_ft"] < 5:
                continue
            p1_ft = to_ft(e["p1"][0], e["p1"][1])
            p2_ft = to_ft(e["p2"][0], e["p2"][1])
            mx = (p1_ft[0] + p2_ft[0]) / 2
            my = (p1_ft[1] + p2_ft[1]) / 2
            # Push dimension label outward past the edge
            ox = -e["nx_ft"] * 10
            oy = -e["ny_ft"] * 10
            ax.text(
                mx + ox, my + oy, f"{e['length_ft']:.0f}'",
                ha="center", va="center", fontsize=5.5,
                color="#374151", fontweight="bold",
                bbox=dict(facecolor="white", alpha=0.9, edgecolor="#d1d5db",
                          pad=1.5, boxstyle="round,pad=0.2"),
                zorder=9,
            )

        ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax.set_ylim(min(all_y) - pad, max(all_y) + pad)
        ax.set_aspect("equal")
        ax.axis("off")

        # Legend
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        legend_elements = [
            Patch(facecolor="#f3f4f6", edgecolor="#374151", linewidth=1.5, label="Parcel"),
            Patch(facecolor="#e5e7eb", edgecolor="none", hatch="///", alpha=0.6, label="Setback zone"),
            Patch(facecolor=(0.15, 0.39, 0.92, 0.15), edgecolor="#2563eb",
                  linestyle="--", linewidth=1, label="Buildable footprint"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=5,
                  framealpha=0.9, edgecolor="#d1d5db")

        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0.1, facecolor="#f8fafc")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return b64, round(buildable_sqft, 0)

    except Exception:
        log.warning("Failed to generate envelope map", exc_info=True)
        return None, None


def _synthesize_opportunities_constraints(
    report: "ReportData",
) -> tuple[list[dict], list[dict]]:
    """Deterministic cross-reference of all report data into actionable insights."""
    from datetime import date

    opportunities: list[dict] = []
    constraints: list[dict] = []

    ctx = report.context
    prop = ctx.property
    reg = ctx.regulatory
    inc = ctx.incentives
    nbr = ctx.neighborhood
    dev = report.development_potential
    comps = report.comparables
    standards = report.zoning_standards
    current_year = date.today().year

    # --- Incentive stacking ---
    if inc:
        has_tif = inc.in_tif_district
        has_oz = inc.in_opportunity_zone
        has_ez = inc.in_enterprise_zone
        has_qct = inc.in_qct
        has_nmtc = inc.in_nmtc

        if has_tif and has_oz and has_qct:
            opportunities.append({
                "signal": "Triple incentive stack: TIF + OZ + QCT",
                "detail": "TIF funds site improvements, OZ defers investor capital gains, QCT provides 130% LIHTC basis boost for affordable housing.",
                "category": "incentive",
            })
        elif has_tif and has_oz:
            opportunities.append({
                "signal": "TIF + Opportunity Zone",
                "detail": "TIF can subsidize infrastructure and remediation; OZ structuring provides investors with tax-advantaged entry.",
                "category": "incentive",
            })
        elif has_oz and has_qct:
            opportunities.append({
                "signal": "OZ + Qualified Census Tract",
                "detail": "OZ investors receive capital gains deferral; QCT provides 130% basis boost for LIHTC projects.",
                "category": "incentive",
            })

        if has_tif and has_ez:
            opportunities.append({
                "signal": "TIF + Enterprise Zone",
                "detail": "TIF provides direct project funding; EZ provides sales tax exemption on building materials and investment tax credits.",
                "category": "incentive",
            })

        if has_nmtc and inc.nmtc_severe_distress:
            opportunities.append({
                "signal": "NMTC with Severe Distress designation",
                "detail": "Severely Distressed tracts receive priority in CDFI allocation rounds for the 39% NMTC credit.",
                "category": "incentive",
            })

        if has_oz and prop and (prop.bldg_sqft or 0) == 0:
            opportunities.append({
                "signal": "Vacant lot in Opportunity Zone",
                "detail": "Ground-up construction on vacant land is the cleanest Qualified Opportunity Fund investment — no substantial improvement test needed.",
                "category": "incentive",
            })

        if inc.grant_programs and inc.grant_programs.total_funding and inc.grant_programs.total_funding > 500_000:
            opportunities.append({
                "signal": "Active grant funding in area",
                "detail": f"${inc.grant_programs.total_funding:,.0f} in SBIF/NOF grants awarded in this community area — established pipeline for applications.",
                "category": "incentive",
            })

        if has_tif and inc.tif_end_year:
            years_left = inc.tif_end_year - current_year
            if 0 < years_left <= 3:
                constraints.append({
                    "signal": f"TIF district expires in {years_left} year{'s' if years_left > 1 else ''}",
                    "detail": f"{inc.tif_name} expires {inc.tif_end_year}. Apply for TIF funding before expiration.",
                    "category": "incentive",
                })

    # --- TOD & Transit ---
    if nbr and nbr.transit and nbr.transit.tod_eligible and standards and standards.parking_residential:
        opportunities.append({
            "signal": "TOD parking reduction eligible",
            "detail": "Chicago TOD ordinance allows reduced parking near transit — could free buildable area otherwise consumed by parking.",
            "category": "zoning",
        })

    if nbr and nbr.walkscore and nbr.walkscore.walk_score and nbr.walkscore.walk_score >= 80 and nbr and nbr.transit and nbr.transit.tod_eligible:
        opportunities.append({
            "signal": f"Walkable transit corridor (Walk Score {nbr.walkscore.walk_score})",
            "detail": "High walkability + transit access supports reduced-parking or car-free residential development.",
            "category": "market",
        })

    if reg and any(o.layer_type == "adu" for o in (reg.overlays or [])):
        opportunities.append({
            "signal": "ADU-eligible area",
            "detail": "Accessory dwelling unit (coach house, basement apartment, rear cottage) is permitted — adds rental income potential without rezoning.",
            "category": "zoning",
        })

    # --- Development potential ---
    if prop and (prop.bldg_sqft or 0) == 0 and prop.land_sqft and dev and dev.max_buildable_sqft and dev.development_surplus_sqft and dev.development_surplus_sqft > 0:
        opportunities.append({
            "signal": "Vacant lot with full development capacity",
            "detail": f"{prop.land_sqft:,} sq ft lot allows up to {dev.max_buildable_sqft:,} sq ft with no existing structure.",
            "category": "zoning",
        })

    if prop and prop.bldg_sqft and dev and dev.development_surplus_sqft and dev.max_buildable_sqft:
        utilization = prop.bldg_sqft / dev.max_buildable_sqft
        if utilization < 0.3:
            opportunities.append({
                "signal": f"Under-improved property ({utilization:.0%} of allowed density)",
                "detail": f"Existing {prop.bldg_sqft:,} sq ft uses {utilization:.0%} of the {dev.max_buildable_sqft:,} sq ft allowed. Significant expansion or teardown-rebuild potential.",
                "category": "zoning",
            })

    if prop and prop.bldg_sqft and dev and dev.development_surplus_sqft is not None and dev.development_surplus_sqft <= 0:
        constraints.append({
            "signal": "At FAR limit — no development surplus",
            "detail": f"Existing {prop.bldg_sqft:,} sq ft structure is at or near the maximum allowed. Additional floor area requires a variance or rezoning.",
            "category": "zoning",
        })

    if prop and prop.bldg_age and prop.bldg_age >= 50 and prop.bldg_sqft and prop.bldg_sqft > 0:
        opportunities.append({
            "signal": f"Building age ({prop.bldg_age} years) may qualify for historic tax credits",
            "detail": "Federal 20% and Illinois 25% historic tax credits available for certified historic structures. Verify individual listing eligibility with Illinois SHPO.",
            "category": "financial",
        })

    # --- Zoning conformity / nonconformity ---
    if prop and prop.year_built and prop.year_built < 1957 and prop.bldg_sqft and prop.bldg_sqft > 0:
        nonconformities: list[str] = []
        if standards and standards.far and prop.bldg_sqft and prop.land_sqft:
            allowed_sqft = standards.far * prop.land_sqft
            if prop.bldg_sqft > allowed_sqft * 1.05:
                nonconformities.append(f"floor area ({prop.bldg_sqft:,} sq ft vs {allowed_sqft:,.0f} sq ft allowed by FAR {standards.far})")
        if standards and standards.max_height_ft and prop.stories:
            est_height = prop.stories * 10
            if est_height > standards.max_height_ft:
                nonconformities.append(f"height ({prop.stories} stories, est. {est_height}' vs {standards.max_height_ft:.0f}' limit)")
        if nonconformities:
            opportunities.append({
                "signal": f"Likely legally nonconforming — predates {prop.year_built} zoning",
                "detail": f"Built in {prop.year_built}, before current zoning code (1957/2004). Existing structure likely exceeds current standards for {' and '.join(nonconformities)}. Legally nonconforming buildings can continue current use but may face restrictions on expansion or reconstruction.",
                "category": "zoning",
            })
        elif prop.year_built < 1957:
            opportunities.append({
                "signal": f"Pre-zoning building (built {prop.year_built})",
                "detail": "Structure predates Chicago's 1957 comprehensive zoning code. Existing use and dimensions may be legally nonconforming ('grandfathered'). Verify conformity status before planning modifications.",
                "category": "zoning",
            })

    # --- Regulatory ---
    if reg and reg.in_planned_development:
        constraints.append({
            "signal": "Planned Development — discretionary approval required",
            "detail": "Any modification to the approved PD plan requires City Council approval, public hearing, and aldermanic support (typically 6-18 months).",
            "category": "regulatory",
        })

    if reg and reg.in_landmark_district:
        constraints.append({
            "signal": "Landmark district — design review required",
            "detail": "Commission on Chicago Landmarks must review exterior modifications. Demolition is unlikely to be approved.",
            "category": "regulatory",
        })

    if reg and reg.on_national_register and not reg.in_landmark_district:
        constraints.append({
            "signal": "National Register district — federal review for funded projects",
            "detail": "Property is in a National Register historic district. Federal tax credit projects require Section 106 review. Local demolition or major alteration may trigger Landmarks Commission review.",
            "category": "regulatory",
        })

    if reg and reg.in_aro_zone and dev and dev.max_buildable_sqft:
        # ARO only bites residential projects of 10+ units. Estimate the as-of-right
        # unit capacity (min lot area per unit, else a ~1,000 sf/unit rule of thumb)
        # and skip the flag when the lot plainly can't reach 10 units — otherwise a
        # tiny lot wrongly surfaces ARO as a binding constraint.
        from backend.retrieval.zoning_definitions import min_lot_area_per_unit
        zone_class = ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
        mla = min_lot_area_per_unit(zone_class)
        if prop and prop.land_sqft and mla:
            est_units = prop.land_sqft / mla
        else:
            est_units = dev.max_buildable_sqft / 1000.0
        if est_units >= 9:  # within rounding of the 10-unit threshold
            constraints.append({
                "signal": "ARO zone — affordable housing requirement at 10+ units",
                "detail": "Projects of 10+ units must set aside units as affordable or pay in-lieu fee (~$175K/required unit). Factor into project economics.",
                "category": "regulatory",
            })

    if reg and any(o.layer_type == "pedestrian_street" for o in (reg.overlays or [])):
        opportunities.append({
            "signal": "Pedestrian street overlay",
            "detail": "Requires 60% ground-floor transparency and active uses — constrains design but signals walkable commercial corridor with higher foot traffic.",
            "category": "regulatory",
        })

    if reg and reg.in_ssa:
        constraints.append({
            "signal": "Special Service Area levy",
            "detail": f"SSA {reg.ssa_name or ''} imposes additional property tax (typically 0.5-2.0% of EAV) beyond base property tax.",
            "category": "financial",
        })

    # --- Financial ---
    if report.effective_tax_rate and report.effective_tax_rate > 0.035:
        constraints.append({
            "signal": f"High effective tax rate ({report.effective_tax_rate:.1%})",
            "detail": "Above Cook County median (~2.1%). Reduces NOI and may impair debt service coverage. Investigate Class 6b/7a/7b/8 incentive eligibility.",
            "category": "financial",
        })

    if report.assessment_trend and report.assessment_trend.get("cagr_pct", 0) > 5:
        # Rising assessed value is a reassessment-cycle signal, not realized market
        # appreciation, and it raises the tax burden — frame it as a trend/cost to
        # verify, not an "appreciation opportunity" (see P7).
        opportunities.append({
            "signal": f"Assessed value rising ({report.assessment_trend['cagr_pct']:.1f}% CAGR, reassessment trend)",
            "detail": f"Assessed value rose {report.assessment_trend['total_change_pct']:.0f}% over {report.assessment_trend['years']} years ({report.assessment_trend.get('oldest_year')}–{report.assessment_trend.get('newest_year')}). This reflects Cook County reassessment cycles, not necessarily market appreciation, and increases the property-tax burden — model the higher assessment in underwriting.",
            "category": "market",
        })

    if comps and comps.sales_volume and comps.sales_volume < 3:
        constraints.append({
            "signal": f"Thin comparable sales market ({comps.sales_volume} transactions)",
            "detail": "Land valuation carries higher uncertainty with limited arm's-length sales nearby. Consider wider search radius or independent appraisal.",
            "category": "market",
        })

    # --- Site condition ---
    if report.address_violations:
        open_v = [v for v in report.address_violations if v.get("violation_status") == "OPEN"]
        if len(open_v) > 10:
            constraints.append({
                "signal": f"{len(open_v)} open building code violations",
                "detail": "Outstanding violations can block new permit issuance. Budget for remediation and factor violation clearance into closing timeline.",
                "category": "site_condition",
            })
        elif len(open_v) > 0:
            opportunities.append({
                "signal": f"Open violations ({len(open_v)}) as acquisition leverage",
                "detail": "Owner faces compliance costs. Open violations may create negotiating leverage on purchase price.",
                "category": "site_condition",
            })

    if ctx.address_311 and ctx.address_311.high_risk_flags:
        constraints.append({
            "signal": "High-risk 311 complaints on file",
            "detail": f"Flags: {', '.join(ctx.address_311.high_risk_flags)}. May indicate structural, mechanical, or habitability issues requiring immediate assessment.",
            "category": "site_condition",
        })

    if report.nearby_development:
        nc = report.nearby_development.new_construction_count or 0
        if nc >= 5:
            opportunities.append({
                "signal": f"Active development corridor ({nc} new construction permits nearby)",
                "detail": "High nearby construction activity indicates market confidence, established contractor availability, and favorable zoning precedent.",
                "category": "market",
            })
        elif nc == 0 and (report.nearby_development.demolition_count or 0) == 0:
            constraints.append({
                "signal": "No nearby development activity (12 months)",
                "detail": "Limited nearby construction may indicate weak demand, regulatory barriers, or infrastructure constraints.",
                "category": "market",
            })

    if report.ownership_signals:
        long_hold = any(s.get("signal") == "Long-Term Hold" for s in report.ownership_signals)
        if long_hold and report.address_violations:
            open_count = len([v for v in report.address_violations if v.get("violation_status") == "OPEN"])
            if open_count > 5:
                opportunities.append({
                    "signal": "Long-held property with deferred maintenance",
                    "detail": f"{open_count} open violations on a long-held property — owner faces mounting compliance costs and may be motivated to sell.",
                    "category": "site_condition",
                })

    # --- Environmental ---
    if reg and reg.in_special_flood_hazard:
        constraints.append({
            "signal": f"FEMA Special Flood Hazard Area (Zone {reg.flood_zone})",
            "detail": "Flood insurance mandatory for federally-backed mortgages. Construction costs typically increase 10-20% for SFHA compliance.",
            "category": "environmental",
        })

    if reg and reg.brownfield_sites and inc and inc.in_tif_district:
        opportunities.append({
            "signal": "TIF funding available for brownfield remediation",
            "detail": f"{len(reg.brownfield_sites)} brownfield site(s) nearby. TIF districts routinely fund environmental remediation as an eligible expense.",
            "category": "environmental",
        })

    # Cap at 4+4, prioritizing by category order
    _CAT_PRIORITY = ["incentive", "zoning", "regulatory", "market", "financial", "site_condition", "environmental"]
    opportunities.sort(key=lambda x: _CAT_PRIORITY.index(x["category"]) if x["category"] in _CAT_PRIORITY else 99)
    constraints.sort(key=lambda x: _CAT_PRIORITY.index(x["category"]) if x["category"] in _CAT_PRIORITY else 99)

    return opportunities[:4], constraints[:4]


def _compute_land_value_range(report: "ReportData") -> dict | None:
    """Compute estimated land value range from comparable sales."""
    comps = report.comparables
    prop = report.context.property
    if not comps or not comps.sales or comps.sales_volume < 3:
        return None
    if not prop or not prop.land_sqft or prop.land_sqft <= 0:
        return None

    prices_per_sqft = [s.price_per_land_sqft for s in comps.sales if s.price_per_land_sqft and s.price_per_land_sqft > 0]
    if len(prices_per_sqft) < 3:
        return None

    prices_per_sqft.sort()
    n = len(prices_per_sqft)
    p25_idx = max(0, int(n * 0.25))
    p75_idx = min(n - 1, int(n * 0.75))
    low_per_sqft = round(prices_per_sqft[p25_idx], 0)
    high_per_sqft = round(prices_per_sqft[p75_idx], 0)
    low = round(low_per_sqft * prop.land_sqft)
    high = round(high_per_sqft * prop.land_sqft)

    return {
        "low": low,
        "high": high,
        "low_per_sqft": low_per_sqft,
        "high_per_sqft": high_per_sqft,
        "sample_size": len(prices_per_sqft),
    }


def _compute_comp_valuation(report: "ReportData") -> dict | None:
    """Synthesize the comparable-sales set into a subject-lot valuation read (P2).

    The reliable anchor is the median comparable *sale price* (always available
    when comps exist). When ≥3 comps carry a land area we also surface a
    lot-normalized land-value range and a $/buildable-sf figure tied to the
    subject's max buildable. In dense, condo-dominated markets the assessor
    characteristics file rarely reports land area, so the land-normalized layer
    is frequently unavailable — we flag that honestly rather than fabricate it.
    """
    comps = report.comparables
    if not comps or not comps.sales or not comps.sales_volume:
        return None

    dev = report.development_potential
    out: dict[str, Any] = {
        "median_sale_price": comps.median_sale_price,
        "price_range_min": comps.price_range_min,
        "price_range_max": comps.price_range_max,
        "sample_size": comps.sales_volume,
        "comp_basis": comps.comp_basis,
        "data_limited": True,
    }

    land = report.estimated_land_value
    if land:
        out["data_limited"] = False
        out["land_value_low"] = land["low"]
        out["land_value_high"] = land["high"]
        out["land_per_sqft_low"] = land["low_per_sqft"]
        out["land_per_sqft_high"] = land["high_per_sqft"]
        out["land_sample_size"] = land["sample_size"]
        # P2: spread the implied land value across the max buildable envelope to
        # express a land cost per buildable sq ft — the figure a developer uses
        # to test a deal against construction cost + target return.
        if dev and dev.max_buildable_sqft:
            out["per_buildable_low"] = round(land["low"] / dev.max_buildable_sqft, 2)
            out["per_buildable_high"] = round(land["high"] / dev.max_buildable_sqft, 2)

    return out


def _compute_far_utilization(report: "ReportData") -> dict | None:
    """How much of the FAR-allowed floor area the existing structure uses (P1)."""
    prop = report.context.property
    standards = report.zoning_standards
    if not prop or not prop.land_sqft or not standards or standards.far is None:
        return None
    allowed = int(standards.far * prop.land_sqft)
    if allowed <= 0:
        return None
    existing = prop.bldg_sqft or 0
    return {
        "existing_sqft": existing,
        "allowed_sqft": allowed,
        "far": standards.far,
        "utilization_pct": round(existing / allowed * 100),
        "unused_sqft": max(0, allowed - existing),
        "vacant": existing == 0,
    }


def _compute_unit_yield(report: "ReportData") -> dict | None:
    """As-of-right dwelling-unit yield from minimum lot area per unit (P8).

    Uses the binding R-district density control (Title 17 Table 17-2-0303-A),
    not FAR, which is the actual as-of-right cap on unit count. Returns ``None``
    for non-R districts / unknown classes so we never fabricate a yield.
    """
    from backend.retrieval.zoning_definitions import min_lot_area_per_unit
    prop = report.context.property
    zoning = report.context.parcel_zoning
    if not prop or not prop.land_sqft or not zoning or not zoning.zone_class:
        return None
    mla = min_lot_area_per_unit(zoning.zone_class)
    if not mla:
        return None
    units = int(prop.land_sqft // mla)
    if units < 1:
        return None
    return {
        "units": units,
        "mla_per_unit": mla,
        "land_sqft": prop.land_sqft,
        "zone_class": zoning.zone_class.strip().upper(),
    }


def _ownership_interpretation(report: "ReportData") -> str | None:
    """Turn raw ownership signals into a deal read — the 'so what' (P5)."""
    sigs = report.ownership_signals
    if not sigs:
        return None
    names = {s.get("signal") for s in sigs}
    clauses: list[str] = []
    if "Long-Term Hold" in names:
        clauses.append(
            "The owner has held for over a decade, so the parcel is likely off-market — "
            "expect to initiate direct outreach with limited competitive tension, but note "
            "the owner faces no acquisition-cost pressure to sell"
        )
    elif "Recent Acquisition" in names:
        clauses.append(
            "The owner acquired recently, so their cost basis is near current market — this "
            "limits room for a price discount and suggests the site may not be actively for sale"
        )
    elif "Ownership Duration" in names:
        clauses.append(
            "The owner has held for several years, so the parcel is likely off-market — expect "
            "direct outreach rather than a listed sale, with the owner's basis set a few years back"
        )
    if "Owner-Occupied (Homeowner Exemption)" in names:
        clauses.append(
            "A homeowner exemption indicates owner occupancy, so any sale hinges on the owner's "
            "own relocation timeline"
        )
    if "Non-Arm's-Length Transfer" in names or "Quit Claim Deed" in names:
        clauses.append(
            "The most recent transfer was non-arm's-length, so the recorded price does not reflect "
            "market value and true ownership may sit behind a trust or LLC — verify the decision-maker "
            "before making an offer"
        )
    if "Rapid Turnover" in names:
        clauses.append(
            "The property has changed hands rapidly, which can signal investor flipping or unresolved "
            "issues — diligence the reason for the quick resale"
        )
    if not clauses:
        return None
    return ". ".join(clauses) + "."


def _build_decision_box(report: "ReportData") -> dict:
    """Page-1 go/no-go box: lot · zone · buildable · value · constraint · timeline (Miss#1)."""
    prop = report.context.property
    zoning = report.context.parcel_zoning
    dev = report.development_potential

    lot = f"{prop.land_sqft:,} sq ft" if prop and prop.land_sqft else "n/a"
    zone = zoning.zone_class if zoning and zoning.zone_class else "n/a"
    buildable = f"{dev.max_buildable_sqft:,} sq ft" if dev and dev.max_buildable_sqft else "n/a"

    # Value field. Credibility rule: never imply a subject valuation we can't
    # support. Tax-exempt/institutional parcels get a status read (more decision-
    # relevant than nearby residential sales); a real land-value range wins when
    # available; otherwise we surface *observed nearby sales* — labeled as market
    # context, not a valuation — and drop the word "median" below n=3 where it is
    # statistically meaningless.
    prop_exempt = bool(prop and (prop.tax_exempt or (prop.bldg_class or "").upper().startswith("EX")))
    value = "n/a"
    value_label = "Market Context"
    elv = report.estimated_land_value
    cv = report.comp_valuation
    if prop_exempt:
        value_label = "Tax Status"
        value = "Exempt (institutional) — verify availability"
    elif elv:
        value_label = "Est. Land Value"
        value = f"{_fmt_money(elv['low'])}–{_fmt_money(elv['high'])}"
    elif cv and cv.get("sample_size", 0) >= 3 and cv.get("median_sale_price"):
        value_label = "Nearby Sales (median)"
        value = f"{_fmt_money(cv['median_sale_price'])} · n={cv['sample_size']}"
    elif cv and cv.get("sample_size", 0) >= 1 and cv.get("price_range_min"):
        n = cv["sample_size"]
        value_label = "Nearby Sales"
        value = f"{_fmt_money(cv['price_range_min'])}–{_fmt_money(cv['price_range_max'])} · {n} sale{'s' if n != 1 else ''}"

    # Surface the most *deal-shaping* constraint, not merely the first synthesized
    # one — regulatory / environmental / site issues bind a project harder than a
    # thin-comp-market caveat, so order by how much each gates a go/no-go decision.
    # "No major constraints flagged" (not "None identified") so the absence reads
    # as "our rule set found nothing," not a guarantee the site is unencumbered.
    key_constraint = "No major constraints flagged"
    if report.constraints:
        _binding_order = [
            "regulatory", "environmental", "site_condition",
            "zoning", "financial", "incentive", "market",
        ]
        top = min(
            report.constraints,
            key=lambda c: _binding_order.index(c["category"])
            if c.get("category") in _binding_order else 99,
        )
        key_constraint = top["signal"]

    timeline = "n/a"
    if report.approval_pathway:
        ap = report.approval_pathway
        timeline = f"{ap['complexity'].title()} · {ap['timeline']}"

    return {
        "lot": lot,
        "zone": zone,
        "buildable": buildable,
        "value": value,
        "value_label": value_label,
        "key_constraint": key_constraint,
        "timeline": timeline,
    }


def _compute_approval_pathway(report: "ReportData") -> dict | None:
    """Determine regulatory approval complexity from report data."""
    reg = report.context.regulatory
    if not reg:
        return None

    standards = report.zoning_standards
    has_special = standards and standards.special_uses
    has_permitted = standards and standards.permitted_uses

    if reg.in_planned_development:
        complexity = "COMPLEX"
        detail = "Planned Development amendment required: City Council approval, public hearing, aldermanic support"
        timeline = "6-18 months"
    elif reg.in_landmark_district or reg.in_historic_district:
        complexity = "COMPLEX"
        detail = "Commission on Chicago Landmarks review required for exterior modifications"
        timeline = "3-6 months for permit review"
    elif reg.on_national_register:
        complexity = "MODERATE"
        detail = "National Register district — Section 106 review for federal tax credit projects; local review may apply for demolition or major alteration"
        timeline = "2-4 months for review"
    elif has_special and not has_permitted:
        complexity = "MODERATE"
        detail = "Zoning Board of Appeals hearing required for special use approval"
        timeline = "3-6 months"
    elif has_special and has_permitted:
        complexity = "MODERATE"
        detail = "Permitted uses available; special use approval needed for some use types"
        timeline = "4-8 weeks (permitted) / 3-6 months (special use)"
    else:
        complexity = "SIMPLE"
        detail = "Standard building permit application under base zoning"
        timeline = "4-8 weeks"

    modifiers: list[str] = []
    if report.address_violations:
        open_count = len([v for v in report.address_violations if v.get("violation_status") == "OPEN"])
        if open_count > 5:
            modifiers.append("Violation clearance required before new permits")
    if reg.in_special_flood_hazard:
        modifiers.append("FEMA floodplain compliance review")
    if reg.in_aro_zone:
        modifiers.append("ARO affordable housing compliance (if 10+ units)")
    if any(o.layer_type == "pedestrian_street" for o in (reg.overlays or [])):
        modifiers.append("Ground-floor design must meet pedestrian street standards")

    return {
        "complexity": complexity,
        "detail": detail,
        "timeline": timeline,
        "modifiers": modifiers,
    }


def _fmt_money(amount: float) -> str:
    """Format a dollar amount with a consistent magnitude suffix ($K below $1M, $M above)."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    return f"${amount / 1_000:.0f}K"


def _compute_development_trend(report: "ReportData") -> dict | None:
    """Synthesize nearby development data into a narrative summary."""
    nd = report.nearby_development
    if not nd:
        return None

    # Radius label derived from the actual construction-search config (0.5mi),
    # not a stale hardcoded "0.25mi" that contradicts the section header.
    radius_mi = round(get_settings().nearby_construction_radius_deg * 69.0, 2)
    radius_label = f"{radius_mi:g}mi"

    nc = nd.new_construction_count or 0
    demo = nd.demolition_count or 0
    projects = nd.recent_projects or []

    if nc == 0 and demo == 0:
        return {
            "narrative": f"Limited development activity within {radius_label} — {len(projects)} permit(s) in 12 months.",
            "intensity": "quiet",
        }

    total_investment = 0
    for p in projects:
        try:
            cost = float(p.get("reported_cost", 0) or 0)
            total_investment += cost
        except (ValueError, TypeError):
            pass

    if nc > 0 and total_investment > 0:
        avg_cost = total_investment / max(nc, 1)
        narrative = (
            f"{nc} new construction permit{'s' if nc > 1 else ''} totaling "
            f"{_fmt_money(total_investment)} within {radius_label} in the last 12 months. "
            f"Average project investment: {_fmt_money(avg_cost)}."
        )
        if demo > 0:
            narrative += f" {demo} demolition permit{'s' if demo > 1 else ''} suggest{'s' if demo == 1 else ''} active site clearance."
        intensity = "active" if nc >= 3 else "moderate"
    elif demo > nc:
        narrative = (
            f"{demo} demolition permit{'s' if demo > 1 else ''} vs {nc} new construction "
            f"permit{'s' if nc != 1 else ''} suggest a teardown-rebuild cycle in early stages."
        )
        intensity = "transitional"
    else:
        narrative = f"{nc + demo} development permit{'s' if (nc + demo) > 1 else ''} within {radius_label} in 12 months."
        intensity = "moderate"

    return {
        "narrative": narrative,
        "intensity": intensity,
        "total_investment": total_investment,
        "new_construction_count": nc,
        "demolition_count": demo,
    }


def _build_incentive_stacking_narrative(report: "ReportData") -> str | None:
    """Generate a paragraph explaining how multiple incentive programs combine."""
    inc = report.context.incentives
    if not inc:
        return None

    flags = []
    if inc.in_tif_district:
        flags.append("TIF")
    if inc.in_opportunity_zone:
        flags.append("OZ")
    if inc.in_enterprise_zone:
        flags.append("EZ")
    if inc.in_qct:
        flags.append("QCT")
    if inc.in_nmtc:
        flags.append("NMTC")

    if len(flags) < 2:
        return None

    key = "+".join(sorted(flags))
    templates = {
        "OZ+TIF": (
            "This parcel sits in both a TIF district and an Opportunity Zone. "
            "TIF funding can subsidize infrastructure, remediation, and public improvements, "
            "while OZ structuring allows investors to defer and reduce capital gains taxes through a Qualified Opportunity Fund. "
            "These programs operate independently and can be combined in the same project."
        ),
        "EZ+TIF": (
            "This parcel benefits from both TIF and Enterprise Zone designations. "
            "TIF provides direct project funding for eligible expenses, "
            "while the Enterprise Zone offers sales tax exemptions on building materials and state investment tax credits. "
            "Together, these can meaningfully reduce both hard and soft development costs."
        ),
        "OZ+QCT": (
            "This parcel is in both an Opportunity Zone and a Qualified Census Tract. "
            "OZ investors receive capital gains deferral and potential exclusion on appreciation. "
            "The QCT designation provides LIHTC projects with a 130% basis boost, "
            "making affordable housing development significantly more feasible."
        ),
        "OZ+QCT+TIF": (
            "This parcel qualifies for a triple incentive stack: TIF + Opportunity Zone + Qualified Census Tract. "
            "TIF can fund site improvements and infrastructure. OZ provides investor-level capital gains benefits. "
            "QCT delivers a 130% LIHTC basis boost for affordable housing. "
            "This combination represents one of the strongest incentive positions available in Chicago."
        ),
        "NMTC+TIF": (
            "This parcel sits in both a TIF district and an NMTC-eligible census tract. "
            "TIF provides direct project funding, while NMTC offers a 39% federal tax credit over 7 years for qualifying investments. "
            "NMTC is typically applied to commercial, mixed-use, or community facility projects."
        ),
        "EZ+OZ": (
            "This parcel benefits from both Enterprise Zone and Opportunity Zone designations. "
            "EZ provides immediate benefits through sales tax exemptions on building materials, "
            "while OZ offers long-term investor capital gains advantages through Qualified Opportunity Fund structuring."
        ),
    }

    narrative = templates.get(key)
    if narrative:
        return narrative

    return (
        f"This parcel is eligible for {len(flags)} incentive programs: {', '.join(flags)}. "
        "Multiple incentive programs can often be combined in the same project, though each has specific eligibility "
        "requirements and application processes. Consult with a tax advisor or economic development specialist "
        "to evaluate the optimal incentive strategy."
    )


def _build_envelope_summary(report: "ReportData") -> str | None:
    """Assemble development parameters into one readable block."""
    standards = report.zoning_standards
    dev = report.development_potential
    prop = report.context.property
    zoning = report.context.parcel_zoning

    if not standards or not prop or not prop.land_sqft:
        return None

    zone = zoning.zone_class if zoning else "this district"
    parts = [f"On this {prop.land_sqft:,} sq ft lot, {zone}"]

    if dev and dev.max_buildable_sqft:
        parts.append(f" allows up to {dev.max_buildable_sqft:,} sq ft of floor area")
    elif standards.far is not None:
        parts.append(f" permits a FAR of {standards.far}")

    if standards.max_stories and standards.max_height_ft:
        parts.append(f" across {standards.max_stories} stories / {standards.max_height_ft} ft")
    elif standards.max_stories:
        parts.append(f" across {standards.max_stories} stories")
    elif standards.max_height_ft:
        parts.append(f" up to {standards.max_height_ft} ft")

    parts.append(".")

    if standards.lot_coverage_pct and prop.land_sqft:
        footprint = int(standards.lot_coverage_pct * prop.land_sqft)
        parts.append(f" Maximum building footprint: approximately {footprint:,} sq ft ({int(standards.lot_coverage_pct * 100)}% lot coverage).")

    if standards.permitted_uses:
        top_uses = standards.permitted_uses[:3]
        parts.append(f" Permitted uses include: {', '.join(top_uses)}.")

    if standards.parking_residential:
        parts.append(f" Parking: {standards.parking_residential} per residential unit.")

    return "".join(parts)


def _apply_mock_overrides(report_data: "ReportData") -> "ReportData":
    """Inject realistic test data for visual QA of all v2 sections."""
    from backend.models import (
        AssessmentRecord, ComparableSale, ComparablesSummary,
        DevelopmentPotential, NearbyDevelopment, SaleRecord,
        TaxLineItem, ZoningStandards,
    )

    # Force zoning extraction with high confidence
    report_data.zoning_standards = ZoningStandards(
        far=2.2,
        max_height_ft=50,
        max_stories=4,
        lot_coverage_pct=0.75,
        min_lot_area_sqft=2500,
        front_setback_ft=10,
        side_setback_ft=5,
        rear_setback_ft=30,
        parking_residential="1 per unit",
        parking_commercial="1 per 500 sq ft GFA",
        permitted_uses=["Retail Sales", "Restaurant", "Office", "Personal Service", "Residential above ground floor"],
        special_uses=["Tavern", "Drive-Through Facility", "Gas Station"],
        notes=["Ground floor transparency minimum 60%", "TOD area may reduce parking requirement"],
        extraction_confidence="high",
    )

    # Force development potential with surplus
    land_sqft = report_data.context.property.land_sqft if report_data.context.property else 5000
    bldg_sqft = report_data.context.property.bldg_sqft if report_data.context.property else 3200
    if not land_sqft:
        land_sqft = 5000
    if not bldg_sqft:
        bldg_sqft = 3200
    report_data.development_potential = DevelopmentPotential(
        max_buildable_sqft=int(2.2 * land_sqft),
        max_lot_coverage_sqft=int(0.75 * land_sqft),
        development_surplus_sqft=int(2.2 * land_sqft) - bldg_sqft,
    )

    # Force effective tax rate + ensure property has tax/assessment for display
    report_data.effective_tax_rate = 0.0218
    if report_data.context.property:
        if not report_data.context.property.estimated_annual_tax:
            report_data.context.property.estimated_annual_tax = 8720
        if not report_data.context.property.total_assessed_value:
            report_data.context.property.total_assessed_value = 40000

    # Force comparable sales
    report_data.comparables = ComparablesSummary(
        median_sale_price=425000.0,
        median_price_per_land_sqft=142.0,
        median_price_per_bldg_sqft=195.0,
        price_range_min=275000.0,
        price_range_max=680000.0,
        sales_volume=7,
        sales=[
            ComparableSale(pin="14-30-316-001", sale_date="2025-11-14", sale_price=520000, class_code="212", land_sqft=3125, bldg_sqft=2400, price_per_land_sqft=166.4, price_per_bldg_sqft=216.7, deed_type="WARRANTY", distance_mi=0.08, lat=41.9280, lon=-87.6430),
            ComparableSale(pin="14-30-314-022", sale_date="2025-08-22", sale_price=450000, class_code="211", land_sqft=2750, bldg_sqft=1850, price_per_land_sqft=163.6, price_per_bldg_sqft=243.2, deed_type="WARRANTY", distance_mi=0.12, lat=41.9295, lon=-87.6455),
            ComparableSale(pin="14-30-318-015", sale_date="2025-06-03", sale_price=425000, class_code="212", land_sqft=3000, bldg_sqft=2200, price_per_land_sqft=141.7, price_per_bldg_sqft=193.2, deed_type="TRUSTEE", distance_mi=0.15, lat=41.9260, lon=-87.6420),
            ComparableSale(pin="14-30-320-009", sale_date="2025-03-18", sale_price=385000, class_code="211", land_sqft=2800, bldg_sqft=2100, price_per_land_sqft=137.5, price_per_bldg_sqft=183.3, deed_type="WARRANTY", distance_mi=0.18, lat=41.9310, lon=-87.6400),
            ComparableSale(pin="14-30-312-041", sale_date="2024-12-05", sale_price=680000, class_code="212", land_sqft=4500, bldg_sqft=3600, price_per_land_sqft=151.1, price_per_bldg_sqft=188.9, deed_type="WARRANTY", distance_mi=0.21, lat=41.9245, lon=-87.6445),
            ComparableSale(pin="14-30-322-007", sale_date="2024-09-11", sale_price=310000, class_code="211", land_sqft=2500, bldg_sqft=1600, price_per_land_sqft=124.0, price_per_bldg_sqft=193.8, deed_type="WARRANTY", distance_mi=0.22, lat=41.9320, lon=-87.6430),
            ComparableSale(pin="14-30-310-033", sale_date="2024-06-27", sale_price=275000, class_code="211", land_sqft=2400, bldg_sqft=1500, price_per_land_sqft=114.6, price_per_bldg_sqft=183.3, deed_type="TRUSTEE", distance_mi=0.24, lat=41.9250, lon=-87.6460),
        ],
    )

    # Force address-specific permits
    report_data.address_permits = [
        {"permit_": "100654321", "permit_type": "PERMIT - RENOVATION/ALTERATION", "work_description": "INTERIOR RENOVATION - COMMERCIAL SPACE BUILDOUT FOR RESTAURANT", "issue_date": "2025-09-14", "reported_cost": "185000", "contact_1_name": "ABC CONSTRUCTION LLC"},
        {"permit_": "100654322", "permit_type": "PERMIT - SIGNS", "work_description": "INSTALL ILLUMINATED WALL SIGN 4x8", "issue_date": "2025-06-02", "reported_cost": "8500", "contact_1_name": "CHICAGO SIGN CO"},
        {"permit_": "100654323", "permit_type": "PERMIT - EASY PERMIT PROCESS", "work_description": "ELECTRICAL - UPGRADE SERVICE TO 400A", "issue_date": "2025-01-18", "reported_cost": "12000", "contact_1_name": "METRO ELECTRIC INC"},
        {"permit_": "100654324", "permit_type": "PERMIT - RENOVATION/ALTERATION", "work_description": "TUCKPOINTING AND MASONRY REPAIR - REAR WALL", "issue_date": "2024-08-22", "reported_cost": "45000", "contact_1_name": "LAKESIDE MASONRY"},
        {"permit_": "100654325", "permit_type": "PERMIT - EASY PERMIT PROCESS", "work_description": "PLUMBING - REPLACE WATER HEATER", "issue_date": "2024-03-11", "reported_cost": "3200", "contact_1_name": "AAA PLUMBING SERVICES"},
    ]

    # Force address-specific violations
    report_data.address_violations = [
        {"violation_date": "2025-04-15", "violation_status": "OPEN", "inspection_number": "14823456", "violation_description": "FAILURE TO MAINTAIN EXTERIOR WALLS - DETERIORATED MASONRY MORTAR JOINTS ON NORTH ELEVATION"},
        {"violation_date": "2024-11-03", "violation_status": "COMPLIED", "inspection_number": "14712345", "violation_description": "FAILED TO MAINTAIN REQUIRED EXIT SIGN ILLUMINATION IN REAR STAIRWELL"},
        {"violation_date": "2024-06-20", "violation_status": "COMPLIED", "inspection_number": "14601234", "violation_description": "FAILURE TO MAINTAIN ALLEY AND REAR YARD FREE OF DEBRIS AND REFUSE"},
    ]

    # Force nearby development (with lat/lon for map generation)
    mock_lat = report_data.lat or 41.9270
    mock_lon = report_data.lon or -87.6980
    report_data.nearby_development = NearbyDevelopment(
        new_construction_count=4,
        demolition_count=2,
        recent_projects=[
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat + 0.001), "longitude": str(mock_lon + 0.001), "work_description": "Erect new 3-story mixed-use building", "issue_date": "2025-11-15", "reported_cost": "450000", "street_number": "2410", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.07, "formatted_address": "2410 N MILWAUKEE AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat - 0.001), "longitude": str(mock_lon + 0.002), "work_description": "Erect new single-family residence", "issue_date": "2025-09-22", "reported_cost": "280000", "street_number": "2356", "street_direction": "N", "street_name": "KEDZIE AVE", "distance_mi": 0.12, "formatted_address": "2356 N KEDZIE AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat + 0.002), "longitude": str(mock_lon - 0.001), "work_description": "Erect new 6-unit residential building", "issue_date": "2025-08-10", "reported_cost": "720000", "street_number": "2430", "street_direction": "N", "street_name": "CALIFORNIA AVE", "distance_mi": 0.15, "formatted_address": "2430 N CALIFORNIA AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat - 0.002), "longitude": str(mock_lon - 0.002), "work_description": "Erect new commercial building", "issue_date": "2025-06-05", "reported_cost": "950000", "street_number": "2501", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.20, "formatted_address": "2501 N MILWAUKEE AVE"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "latitude": str(mock_lat + 0.0015), "longitude": str(mock_lon - 0.0015), "work_description": "Wreck existing 2-story frame building", "issue_date": "2025-10-01", "reported_cost": "35000", "street_number": "2418", "street_direction": "N", "street_name": "SACRAMENTO AVE", "distance_mi": 0.11, "formatted_address": "2418 N SACRAMENTO AVE"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "latitude": str(mock_lat - 0.0015), "longitude": str(mock_lon + 0.0005), "work_description": "Wreck existing garage structure", "issue_date": "2025-07-18", "reported_cost": "15000", "street_number": "2380", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.13, "formatted_address": "2380 N MILWAUKEE AVE"},
        ],
    )

    # Force building characteristics + history (development_feasibility workflow skips history)
    if report_data.context.property:
        report_data.context.property.exterior_wall = report_data.context.property.exterior_wall or "Masonry"
        report_data.context.property.roof_type = report_data.context.property.roof_type or "Shingle/Asphalt"
        report_data.context.property.basement = report_data.context.property.basement or "Full"
        report_data.context.property.garage_size = report_data.context.property.garage_size or "1 Car"
        report_data.context.property.air_conditioning = report_data.context.property.air_conditioning or "Central"
        if not report_data.context.property.year_built and report_data.context.property.bldg_age:
            from datetime import date
            report_data.context.property.year_built = date.today().year - report_data.context.property.bldg_age

        if not report_data.context.property.assessment_history:
            report_data.context.property.assessment_history = [
                AssessmentRecord(year=2025, land=12000, building=27900, total=39900),
                AssessmentRecord(year=2024, land=11500, building=26000, total=37500),
                AssessmentRecord(year=2023, land=10800, building=24200, total=35000),
                AssessmentRecord(year=2022, land=10000, building=22000, total=32000),
                AssessmentRecord(year=2021, land=9500, building=18500, total=28000),
            ]
            report_data.context.property.total_assessed_value = 39900

        if not report_data.context.property.sales_history:
            report_data.context.property.sales_history = [
                SaleRecord(date="2014-03-22", price=285000, deed_type="WARRANTY"),
                SaleRecord(date="2005-09-15", price=192000, deed_type="WARRANTY"),
                SaleRecord(date="1998-06-01", price=125000, deed_type="TRUSTEE"),
            ]

        if not report_data.context.property.tax_breakdown:
            report_data.context.property.tax_breakdown = [
                TaxLineItem(agency="CITY OF CHICAGO", rate=0.01245, amount=4215.60),
                TaxLineItem(agency="BOARD OF EDUCATION", rate=0.00980, amount=3316.20),
                TaxLineItem(agency="COOK COUNTY FOREST PRESERVE", rate=0.00162, amount=548.44),
                TaxLineItem(agency="METRO WATER RECLAMATION", rate=0.00410, amount=1387.86),
                TaxLineItem(agency="CHICAGO PARK DISTRICT", rate=0.00315, amount=1066.14),
                TaxLineItem(agency="CITY COLLEGES", rate=0.00205, amount=693.90),
                TaxLineItem(agency="COOK COUNTY", rate=0.00175, amount=592.34),
                TaxLineItem(agency="COOK COUNTY HEALTH FACILITIES", rate=0.00098, amount=331.63),
            ]

    # Force assessment trend
    report_data.assessment_trend = {
        "total_change_pct": 42.5,
        "cagr_pct": 7.3,
        "years": 5,
        "oldest_year": 2020,
        "newest_year": 2025,
        "oldest_total": 28000,
        "newest_total": 39900,
        "direction": "increasing",
    }

    # Force ownership signals
    report_data.ownership_signals = [
        {"signal": "Long-Term Hold", "detail": "Last sale 12 years ago (2014-03-22)", "category": "ownership_duration"},
        {"signal": "Owner-Occupied (Homeowner Exemption)", "detail": "Homeowner exemption found in tax breakdown", "category": "occupancy"},
    ]

    # Force parcel dimensions (mock rectangular lot)
    report_data.parcel_dimensions = {
        "area_sqft": 3125,
        "perimeter_ft": 250.0,
        "frontage_ft": 25.0,
        "depth_ft": 125.0,
        "edge_count": 4,
        "edges": [
            {"length_ft": 125.0, "bearing": 0.0},
            {"length_ft": 25.0, "bearing": 90.0},
            {"length_ft": 125.0, "bearing": 180.0},
            {"length_ft": 25.0, "bearing": 270.0},
        ],
    }

    # Force adjacent zoning
    report_data.adjacent_zoning = {"N": "B3-2", "S": "RS-3", "E": "B3-2", "W": "RT-4"}

    # NOTE: parcel_geometry is NOT mocked — fabricated coordinates produce a
    # misleading lot map. The parcel map only renders with real GIS geometry.
    # Mock parcel_dimensions (below) still populate the dimensions grid.

    # Generate comps chart for mock data
    try:
        report_data.comps_chart_b64 = _generate_comps_chart(report_data.comparables)
    except Exception:
        pass

    # Envelope map for mock data
    if report_data.context.property and report_data.context.property.parcel_geometry and report_data.zoning_standards:
        try:
            report_data.envelope_map_b64, report_data.buildable_footprint_sqft = _generate_envelope_map(
                report_data.lat, report_data.lon,
                report_data.context.property.parcel_geometry,
                report_data.zoning_standards,
                report_data.parcel_dimensions,
            )
        except Exception:
            log.warning("Failed to generate mock envelope map", exc_info=True)

    # V5 synthesis on mock data
    report_data.opportunities, report_data.constraints = _synthesize_opportunities_constraints(report_data)
    report_data.estimated_land_value = _compute_land_value_range(report_data)
    report_data.approval_pathway = _compute_approval_pathway(report_data)
    report_data.development_trend = _compute_development_trend(report_data)
    report_data.incentive_stacking_narrative = _build_incentive_stacking_narrative(report_data)
    report_data.envelope_summary = _build_envelope_summary(report_data)

    # Phase 3 decision-quality synthesis on mock data
    report_data.far_utilization = _compute_far_utilization(report_data)
    report_data.unit_yield = _compute_unit_yield(report_data)
    report_data.comp_valuation = _compute_comp_valuation(report_data)
    report_data.ownership_interpretation = _ownership_interpretation(report_data)
    report_data.decision_box = _build_decision_box(report_data)

    # Clear partial failures since mock data is complete
    report_data.partial_failures = []

    return report_data


@app.get("/api/report")
async def report(
    request: Request,
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
    mock: bool = False,
    user: dict = Depends(require_auth),
) -> Response:
    """Generate a PDF development feasibility & site intelligence report."""
    import re
    from datetime import date

    from backend.auth import _TIER_ORDER
    from jinja2 import Environment, FileSystemLoader
    from weasyprint import HTML

    resolved_lat, resolved_lon, resolved_address = await _resolve_location(
        address, lat, lon, pin
    )

    if _TIER_ORDER.get(user["tier"], 0) < _TIER_ORDER["premium"]:
        if not await db.has_purchased_report(user["id"], resolved_lat, resolved_lon):
            raise HTTPException(
                status_code=403,
                detail={"error": "report_purchase_required"},
            )

    report_data, basemap_bytes, basemap_wide_bytes = await _fetch_report_data(resolved_lat, resolved_lon, resolved_address)

    if mock:
        report_data = _apply_mock_overrides(report_data)
        # Regenerate construction map with mock development data (always, since mock replaces projects)
        construction_basemap = basemap_wide_bytes or basemap_bytes
        if construction_basemap and report_data.nearby_development and report_data.nearby_development.recent_projects:
            try:
                loop = asyncio.get_running_loop()
                report_data.construction_map_b64 = await loop.run_in_executor(
                    None, _generate_construction_map,
                    report_data.lat, report_data.lon,
                    report_data.nearby_development.recent_projects, construction_basemap,
                )
            except Exception:
                log.warning("Failed to generate mock construction map", exc_info=True)
        # NOTE: parcel map is NOT regenerated for mock mode — mock geometry is
        # fabricated and would produce a misleading lot boundary. The parcel map
        # only renders when real GIS geometry is available from _fetch_report_data().
        # Regenerate comps map with mock data
        if not report_data.comps_map_b64 and basemap_bytes and report_data.comparables and report_data.comparables.sales:
            sales_with_coords = [s for s in report_data.comparables.sales if s.lat and s.lon]
            if len(sales_with_coords) >= 2:
                try:
                    loop = asyncio.get_running_loop()
                    report_data.comps_map_b64 = await loop.run_in_executor(
                        None, _generate_comps_map,
                        report_data.lat, report_data.lon,
                        report_data.comparables.sales, basemap_bytes,
                    )
                except Exception:
                    log.warning("Failed to generate mock comps map", exc_info=True)
        # Regenerate zone definitions from mock-overridden zone data
        from backend.retrieval.zoning_definitions import collect_report_zone_definitions as _collect_zdefs
        zone_class = report_data.context.parcel_zoning.zone_class if report_data.context.parcel_zoning else None
        mock_zdefs = _collect_zdefs(zone_class, report_data.adjacent_zoning)
        report_data.zone_definitions = [
            {"zone_class": zd.zone_class, "name": zd.name, "code_section": zd.code_section,
             "far": zd.far, "max_height": zd.max_height, "lot_coverage": zd.lot_coverage,
             "uses": zd.uses, "notes": zd.notes, "is_fallback": zd.is_fallback}
            for zd in mock_zdefs
        ]

    # Render HTML template
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    env.filters["fnum"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else "N/A"
    env.filters["fpct"] = lambda v: f"{v * 100:.1f}%" if v is not None else "N/A"
    env.filters["fcur"] = lambda v: f"${v:,.0f}" if v is not None else "N/A"
    from backend.retrieval.zoning_definitions import get_zone_name
    env.filters["zone_desc"] = get_zone_name
    template = env.get_template("zoning_report.html")

    html_content = template.render(
        report=report_data,
        report_date=date.today().strftime("%B %d, %Y"),
    )

    # Generate PDF
    pdf_bytes = HTML(string=html_content).write_pdf()

    # Build filename
    slug = re.sub(r"[^a-z0-9]+", "_", (resolved_address or "property").lower()).strip("_")
    filename = f"{slug}_{date.today().isoformat()}_feasibility_report.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
# Payments API
# ---------------------------------------------------------------------------


@app.post("/api/checkout")
async def checkout(request: Request, user: dict = Depends(require_auth)) -> dict:
    from backend.payments import create_checkout_session
    url = await create_checkout_session(user)
    return {"url": url}


@app.post("/api/checkout/report")
async def checkout_report(request: Request, user: dict = Depends(require_auth)) -> dict:
    from backend.payments import create_report_checkout_session
    body = await request.json()
    address = body.get("address")
    lat = body.get("lat")
    lon = body.get("lon")
    if not address or lat is None or lon is None:
        raise HTTPException(status_code=400, detail="address, lat, and lon are required")
    url = await create_report_checkout_session(user, address, float(lat), float(lon))
    return {"url": url}


@app.get("/api/report/access")
async def check_report_access(
    request: Request,
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
    user: dict = Depends(require_auth),
) -> dict:
    """Check if the current user can download a report for this location."""
    from backend.auth import _TIER_ORDER
    if _TIER_ORDER.get(user["tier"], 0) >= _TIER_ORDER["premium"]:
        return {"has_access": True, "reason": "subscription"}
    resolved_lat, resolved_lon, _ = await _resolve_location(address, lat, lon, pin)
    purchased = await db.has_purchased_report(user["id"], resolved_lat, resolved_lon)
    return {"has_access": purchased, "reason": "purchased" if purchased else "none"}


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request) -> dict:
    from backend.payments import handle_webhook
    return await handle_webhook(request)


@app.get("/api/subscription")
async def subscription_status(
    request: Request, user: dict = Depends(require_auth),
) -> dict:
    from backend.payments import get_subscription_status
    return await get_subscription_status(user)


@app.post("/api/billing/portal")
async def billing_portal(request: Request, user: dict = Depends(require_auth)) -> dict:
    from backend.payments import create_billing_portal_session
    url = await create_billing_portal_session(user)
    return {"url": url}


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


@app.get("/api/admin/engagement")
async def admin_engagement(request: Request, period: str = "30d", _admin: dict = Depends(require_admin)) -> dict:
    return await db.get_engagement_stats(period)


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


_VALID_EVENT_NAMES = {"page_view", "investigate_click", "report_cta_click", "chat_message_sent"}


@app.post("/api/events")
async def ingest_events(request: Request, batch: EventBatch) -> dict:
    user_id = None
    try:
        from backend.auth import get_current_user
        user = await get_current_user(request)
        user_id = user.get("id") if user else None
    except Exception:
        pass

    valid = [
        {**e.model_dump(), "user_id": user_id}
        for e in batch.events
        if e.event_name in _VALID_EVENT_NAMES
    ]
    if valid:
        asyncio.create_task(db.save_events(valid))
    return {"ok": True}


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
