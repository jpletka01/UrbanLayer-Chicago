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
            {"$where": f"pin='{pin}'", "$select": "latitude,longitude", "$limit": 1},
            base_url=settings.cook_county_socrata_base,
        )
        if rows and rows[0].get("latitude") and rows[0].get("longitude"):
            resolved_lat = float(rows[0]["latitude"])
            resolved_lon = float(rows[0]["longitude"])

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
) -> str | None:
    """Generate a base64-encoded PNG map with zoning polygon overlays."""
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

    # Comparable sales (use property class prefix if available)
    class_prefix = ""
    if ctx.property and ctx.property.bldg_class:
        class_prefix = ctx.property.bldg_class[0]
    if class_prefix:
        v2_tasks["comparable_sales"] = asyncio.create_task(
            _limited(nearby_comparable_sales(resolved_lat, resolved_lon, class_prefix))
        )

    v2_tasks["nearby_construction"] = asyncio.create_task(
        _limited(nearby_new_construction(resolved_lat, resolved_lon))
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
    settings = get_settings()
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

    # Generate comparable sales chart
    comps_chart_b64 = None
    if comps_summary and comps_summary.sales and len(comps_summary.sales) >= 2:
        loop = asyncio.get_running_loop()
        try:
            comps_chart_b64 = await loop.run_in_executor(
                None, _generate_comps_chart, comps_summary
            )
        except Exception:
            log.warning("Failed to generate comps chart", exc_info=True)

    # Fetch basemap once for both zoning and construction maps
    basemap_bytes = None
    if mapbox_token:
        basemap_no_pin_url = (
            f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
            f"{resolved_lon},{resolved_lat},15/600x400@2x"
            f"?access_token={mapbox_token}"
        )
        try:
            basemap_resp = await httpx.AsyncClient(timeout=15).get(basemap_no_pin_url)
            if basemap_resp.status_code == 200:
                basemap_bytes = basemap_resp.content
        except Exception:
            log.warning("Failed to fetch basemap for report maps", exc_info=True)

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
                )
        except Exception:
            log.warning("Failed to generate zoning map", exc_info=True)

    # Generate construction/demolition map
    construction_map_b64 = None
    if basemap_bytes and nearby_dev and nearby_dev.recent_projects:
        try:
            loop = asyncio.get_running_loop()
            construction_map_b64 = await loop.run_in_executor(
                None,
                _generate_construction_map,
                resolved_lat, resolved_lon,
                nearby_dev.recent_projects, basemap_bytes,
            )
        except Exception:
            log.warning("Failed to generate construction map", exc_info=True)

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
                    f"{resolved_lon},{resolved_lat},17/600x400@2x"
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
        zoning_map_b64=zoning_map_b64,
        construction_map_b64=construction_map_b64,
        bulk_standards_text=bulk_standards_text,
        zone_definitions=zone_definitions_data,
        partial_failures=partial_failures,
    )
    return report, basemap_bytes


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
    """Generate a base64-encoded PNG map with parcel polygon overlay."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 17

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
            patch = MplPolygon(
                pixels, closed=True,
                facecolor=(0.15, 0.39, 0.92, 0.3),
                edgecolor=(0.15, 0.39, 0.92, 0.9),
                linewidth=2,
            )
            ax.add_patch(patch)

            if dimensions and len(pixels) >= 4:
                for i in range(min(len(pixels) - 1, 4)):
                    mx = (pixels[i][0] + pixels[i + 1][0]) / 2
                    my = (pixels[i][1] + pixels[i + 1][1]) / 2
                    if 0 <= mx <= img_w and 0 <= my <= img_h:
                        edge_idx = i
                        if edge_idx < len(dimensions.get("edges", [])):
                            length = dimensions["edges"][edge_idx]["length_ft"]
                            if length > 10:
                                ax.text(
                                    mx, my, f"{length:.0f}'",
                                    ha="center", va="center", fontsize=5.5,
                                    color="white", fontweight="bold",
                                    bbox=dict(facecolor="#2563eb", alpha=0.85,
                                              edgecolor="none", pad=2, boxstyle="round,pad=0.2"),
                                    zorder=15,
                                )

        # Subject property pin
        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(pin_px, pin_py, "o", markersize=8, color="#c96442",
                markeredgecolor="white", markeredgewidth=2, zorder=10)

        if dimensions:
            info_parts = []
            if dimensions.get("frontage_ft"):
                info_parts.append(f"Frontage: {dimensions['frontage_ft']:.0f}'")
            if dimensions.get("depth_ft"):
                info_parts.append(f"Depth: {dimensions['depth_ft']:.0f}'")
            if dimensions.get("area_sqft"):
                info_parts.append(f"Area: {dimensions['area_sqft']:,.0f} sq ft")
            if info_parts:
                ax.text(
                    8, 12, "  |  ".join(info_parts),
                    ha="left", va="top", fontsize=5.5, color="white",
                    bbox=dict(facecolor="#1a1a1a", alpha=0.8,
                              edgecolor="#333", pad=4, boxstyle="round,pad=0.3"),
                    zorder=20,
                )

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
        front_setback_ft=0,
        side_setback_ft=0,
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
            ComparableSale(pin="14-30-316-001", sale_date="2025-11-14", sale_price=520000, class_code="212", land_sqft=3125, bldg_sqft=2400, price_per_land_sqft=166.4, price_per_bldg_sqft=216.7, deed_type="WARRANTY", distance_mi=0.08),
            ComparableSale(pin="14-30-314-022", sale_date="2025-08-22", sale_price=450000, class_code="211", land_sqft=2750, bldg_sqft=1850, price_per_land_sqft=163.6, price_per_bldg_sqft=243.2, deed_type="WARRANTY", distance_mi=0.12),
            ComparableSale(pin="14-30-318-015", sale_date="2025-06-03", sale_price=425000, class_code="212", land_sqft=3000, bldg_sqft=2200, price_per_land_sqft=141.7, price_per_bldg_sqft=193.2, deed_type="TRUSTEE", distance_mi=0.15),
            ComparableSale(pin="14-30-320-009", sale_date="2025-03-18", sale_price=385000, class_code="211", land_sqft=2800, bldg_sqft=2100, price_per_land_sqft=137.5, price_per_bldg_sqft=183.3, deed_type="WARRANTY", distance_mi=0.18),
            ComparableSale(pin="14-30-312-041", sale_date="2024-12-05", sale_price=680000, class_code="212", land_sqft=4500, bldg_sqft=3600, price_per_land_sqft=151.1, price_per_bldg_sqft=188.9, deed_type="WARRANTY", distance_mi=0.21),
            ComparableSale(pin="14-30-322-007", sale_date="2024-09-11", sale_price=310000, class_code="211", land_sqft=2500, bldg_sqft=1600, price_per_land_sqft=124.0, price_per_bldg_sqft=193.8, deed_type="WARRANTY", distance_mi=0.22),
            ComparableSale(pin="14-30-310-033", sale_date="2024-06-27", sale_price=275000, class_code="211", land_sqft=2400, bldg_sqft=1500, price_per_land_sqft=114.6, price_per_bldg_sqft=183.3, deed_type="TRUSTEE", distance_mi=0.24),
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

    # Generate comps chart for mock data
    try:
        report_data.comps_chart_b64 = _generate_comps_chart(report_data.comparables)
    except Exception:
        pass

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

    report_data, basemap_bytes = await _fetch_report_data(resolved_lat, resolved_lon, resolved_address)

    if mock:
        report_data = _apply_mock_overrides(report_data)
        # Regenerate construction map with mock development data (always, since mock replaces projects)
        if basemap_bytes and report_data.nearby_development and report_data.nearby_development.recent_projects:
            try:
                loop = asyncio.get_running_loop()
                report_data.construction_map_b64 = await loop.run_in_executor(
                    None, _generate_construction_map,
                    report_data.lat, report_data.lon,
                    report_data.nearby_development.recent_projects, basemap_bytes,
                )
            except Exception:
                log.warning("Failed to generate mock construction map", exc_info=True)
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
