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
import re
import time
from typing import Any, AsyncIterator, NamedTuple

import httpx
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.analytics import compute_analytics
from backend.retrieval.cache import TTLCache
from backend.assembler import assemble_context
from backend.config import get_settings
from backend.context_manager import summarize_turn
from backend.conversation import synthesize_query
from backend.llm import tracked_create
from backend import db
from backend.report_builder import (
    _apply_mock_overrides,
    _comp_class_prefix,
    _fetch_report_data,
    _generate_comps_map,
    _generate_construction_map,
)
from backend.models import (
    ChatChunk,
    ChatRequest,
    ContextObject,
    EventBatch,
    ImportRequest,
    MapDataRequest,
    MapDataResponse,
    NeighborhoodSummary,
    RetrievalPlan,
    SaveMessagesRequest,
    ScorecardContext,
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
from backend.retrieval.zoning import lookup_zoning
from backend.retrieval.vector_search import (
    expand_cross_references,
    get_full_section,
    semantic_search,
)
from backend.router import route
from backend.synthesizer import LANGUAGE_NAMES, stream_answer


log = logging.getLogger(__name__)

_RETRIEVAL_SEM = asyncio.Semaphore(8)

# Bounds concurrent PDF report renders (report_concurrency=1). The heavy WeasyPrint
# render now runs in an isolated child (~118 MB, backend/report_render.py); serializing
# keeps the parent's per-request matplotlib/HTML allocations predictable. See the
# Tier-0 investigation in claude-context/guides/report-v6-execution-plan.md.
_REPORT_SEM = asyncio.Semaphore(get_settings().report_concurrency)

# Best-effort: return top-of-heap free space to the OS after each report via
# malloc_trim(0). glibc-only — a caught no-op elsewhere (e.g. macOS dev).
# NOTE (measured 2026-06-16): this did NOT visibly flatten the parent's ~20 MB/
# render RSS creep — that growth is evidently live caches (matplotlib/fonts) or
# fragmentation malloc_trim can't reach, not reclaimable top-of-heap space. Kept as
# a cheap, harmless mitigation; the creep is benign (ample headroom + 8 GB swap,
# decelerates, worker restarts each deploy).
try:
    import ctypes as _ctypes
    import ctypes.util as _ctypes_util

    _LIBC = _ctypes.CDLL(_ctypes_util.find_library("c"))
except Exception:  # pragma: no cover - exotic platforms
    _LIBC = None


def _trim_malloc() -> None:
    if _LIBC is not None and hasattr(_LIBC, "malloc_trim"):
        try:
            _LIBC.malloc_trim(0)
        except Exception:  # pragma: no cover
            pass


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
    "/api/newsletter",  # anonymous email capture; single INSERT OR IGNORE
}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.url.path not in _CSRF_EXEMPT_PATHS:
                from backend.auth import csrf_check
                if not csrf_check(request):
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

# Property Discovery (filter/search) wire endpoints — see backend/discovery/.
from backend.discovery.api import router as discovery_router  # noqa: E402

app.include_router(discovery_router)


@app.on_event("startup")
async def _startup() -> None:
    settings = get_settings()
    await db.init_db()
    from backend.discovery import parcel_source
    parcel_source.ensure_loaded()
    # ptaxsim.db is optional-by-design (estimate_tax degrades to None), which let
    # prod run for weeks serving NO tax data with nothing in the logs. Missing DB
    # must be loud: every scorecard/report tax figure depends on it.
    if not settings.ptaxsim_enabled:
        log.warning("PTAXSIM disabled by config — tax estimates will be absent")
    elif not settings.ptaxsim_db_path.exists():
        log.warning(
            "PTAXSIM database missing at %s — ALL tax estimates (bill, rate, "
            "breakdown) will be absent. Seed it with scripts/download_ptaxsim.py",
            settings.ptaxsim_db_path,
        )
    await _preload_datasets()


async def _preload_datasets() -> None:
    """Pre-warm lazy-loaded datasets in the background."""
    from backend.retrieval.incentives import tif, enterprise_zones
    from backend.retrieval.neighborhood import transit, demographics, wards

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        labels = ["TIF boundaries", "EZ boundaries", "transit stations", "demographics",
                  "ward boundaries"]
        results = await asyncio.gather(
            tif.preload(client=client),
            enterprise_zones.preload(client=client),
            transit.preload(),
            demographics.preload(client=client),
            wards.preload(client=client),
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

    # Informational, not gating: the app is degraded-but-up without ptaxsim
    # (tax figures absent). Surfaced here so a deploy check / uptime probe can
    # catch a missing DB — prod ran without one for weeks, silently.
    ptaxsim_ok = bool(settings.ptaxsim_enabled and settings.ptaxsim_db_path.exists())

    ok = qdrant_ok and db_ok
    result = {"ok": ok, "qdrant": qdrant_ok, "db": db_ok, "ptaxsim": ptaxsim_ok}
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
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"user": result["user"]})
    set_auth_cookies(
        resp, result["access_token"], result["refresh_token"], result["csrf_token"],
    )
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request, response: Response):
    # Anonymous visitors need the (JS-readable, double-submit) CSRF cookie
    # too: anon chat is open, and CSRFMiddleware checks POST /chat. The
    # cookie is otherwise only issued at OAuth callback/refresh.
    if not request.cookies.get("csrf_token"):
        import secrets
        from backend.auth import get_settings as _auth_settings
        response.set_cookie(
            "csrf_token", secrets.token_urlsafe(16),
            httponly=False, secure=_auth_settings().auth_cookie_secure,
            samesite="lax", path="/",
        )
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
    user: dict = Depends(require_auth),
) -> list[dict]:
    return await db.list_conversations(_user_id(user))


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    body: dict, user: dict = Depends(require_auth),
) -> dict:
    conv_id = body.get("id", f"conv_{int(time.time() * 1000)}")
    title = body.get("title", "New conversation")
    language = body.get("language", "en")
    return await db.create_conversation(conv_id, title, _user_id(user), language=language)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(
    conv_id: str, user: dict = Depends(require_auth),
) -> dict:
    conv = await db.get_conversation(conv_id, _user_id(user))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str, user: dict = Depends(require_auth),
) -> dict:
    deleted = await db.delete_conversation(conv_id, _user_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.put("/api/conversations/{conv_id}/messages")
async def append_messages(
    conv_id: str, req: SaveMessagesRequest,
    user: dict = Depends(require_auth),
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
    user: dict = Depends(require_auth),
) -> dict:
    conv = await db.get_conversation(conv_id, _user_id(user))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if "map_data" in body:
        await db.update_message_map_data(
            conv_id, position, body["map_data"], body.get("map_fetched_at"),
        )
    return {"ok": True}


@app.post("/api/conversations/import")
async def import_conversations(
    req: ImportRequest, user: dict = Depends(require_auth),
) -> dict:
    count = await db.import_conversations(
        [c.model_dump() for c in req.conversations], _user_id(user),
    )
    return {"imported": count}


@app.delete("/api/conversations")
async def clear_conversations(
    user: dict = Depends(require_auth),
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
    conv_id: str, user: dict = Depends(require_auth),
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
    user: dict = Depends(require_auth),
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


_PROPERTY_DOMAINS = {"property_domain", "regulatory_domain", "incentives_domain"}


def _scorecard_grounding_applies(
    plan: RetrievalPlan, sc: ScorecardContext | None,
) -> bool:
    """True when pre-resolved Scorecard grounding should replace live retrieval.

    Three conditions (all required): grounding is present, its pin matches the
    parcel the plan resolved to (so we never graft one parcel's facts onto a
    question the router read as being about another), and the plan is
    property-scoped — it asked for at least one property/regulatory/incentives
    domain or ran the site-due-diligence workflow. A pure neighborhood or
    code-research turn fails the last check and retrieves normally (augment).
    """
    if sc is None or not sc.pin:
        return False
    if plan.location.pin != sc.pin:
        return False
    return bool(_PROPERTY_DOMAINS & set(plan.sources)) or plan.workflow_hint == "site_due_diligence"


async def _retrieve(
    plan: RetrievalPlan, scorecard_context: ScorecardContext | None = None,
) -> ContextObject:
    ca = plan.location.resolved_community_area
    tasks: dict[str, asyncio.Task] = {}

    # When the Scorecard handed us pre-resolved grounding for this exact parcel,
    # skip the property/regulatory/incentives/zoning fetches it already covers
    # (bypass) and merge those sub-objects into the assembled context below.
    # vector_search + neighborhood + the activity feeds still run (augment).
    use_sc = _scorecard_grounding_applies(plan, scorecard_context)

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
    if plan.requires_disclaimer and loc.resolved_lat and loc.resolved_lon and not use_sc:
        tasks["zoning_lookup"] = asyncio.create_task(_limited(
            lookup_zoning(loc.resolved_lat, loc.resolved_lon)
        ))

    wf = plan.workflow_hint or "general"

    if "regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon and not use_sc:
        tasks["regulatory"] = asyncio.create_task(_limited(
            regulatory_domain(loc.resolved_lat, loc.resolved_lon, workflow=wf)
        ))

    # ARO is folded into the regulatory summary; the Scorecard grounding already
    # carries it, so skip the fetch when we're substituting that summary.
    _aro_triggers = {"regulatory_domain", "property_domain", "neighborhood_domain", "incentives_domain"}
    if _aro_triggers & set(plan.sources) and ca is not None and not use_sc:
        tasks["aro_housing"] = asyncio.create_task(_limited(
            aro_housing_by_community_area(ca)
        ))

    if "property_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon and not use_sc:
        tasks["property"] = asyncio.create_task(_limited(
            # pin keys the property domain authoritatively when the turn came
            # from a Scorecard handoff (INV-2 parity with /api/scorecard)
            property_domain(loc.resolved_lat, loc.resolved_lon, pin=loc.pin, workflow=wf)
        ))

    if "incentives_domain" in plan.sources and not use_sc:
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

    ctx = assemble_context(
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

    if use_sc:
        # Graft the Scorecard's already-assembled sub-objects in place of the
        # fetches we skipped. They're post-assembly (same shapes ctx uses) and
        # already carry the assembler's tax-class enrichment. comparables and
        # zone_definition have no assembler input — set them straight on ctx
        # (new optional fields; the synthesizer serializes them automatically).
        sc = scorecard_context
        if sc.parcel_zoning is not None:
            ctx.parcel_zoning = sc.parcel_zoning
        if sc.regulatory is not None:
            ctx.regulatory = sc.regulatory
        if sc.property is not None:
            ctx.property = sc.property
        if sc.incentives is not None:
            ctx.incentives = sc.incentives
        ctx.comparables = sc.comparables
        ctx.zone_definition = sc.zone_definition
        ctx.verdict = sc.verdict
        # Address-scoped violation tri-state rides in its own field — it never
        # touches ctx.violations (the area feed, which still augments if the
        # router asked for it). The prompt rule prioritizes this for parcel-level
        # questions; the two scopes stay separate.
        ctx.address_violations = sc.address_violations
        # Nearest-street traffic rides inside neighborhood (its natural home in
        # the serialized context); create the shell when this turn didn't run
        # the neighborhood orchestrator. Never overwrite a fresher fetch.
        if sc.traffic is not None:
            if ctx.neighborhood is None:
                ctx.neighborhood = NeighborhoodSummary(traffic=sc.traffic)
            elif ctx.neighborhood.traffic is None:
                ctx.neighborhood.traffic = sc.traffic

    return ctx


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


# Land-use vocabulary that makes the zoning/overlay polygon layers a relevant
# visualization for a chat turn. requires_disclaimer alone is NOT a signal —
# every legal question carries it, and a violations question shouldn't paint
# the whole community area's zoning quilt (map-relevance review, 2026-06-12).
_LANDUSE_QUERY_RE = re.compile(
    r"zon|land.?use|setback|\bfar\b|floor.?area|height|bulk|density|\badu\b"
    r"|variance|overlay|landmark|historic|lakefront|planned.?development",
    re.IGNORECASE,
)


def _landuse_map_relevant(plan: RetrievalPlan) -> bool:
    """True when the turn is actually about land use, so the zoning/overlay
    polygon layers illustrate the answer instead of diluting it."""
    if plan.workflow_hint == "site_due_diligence":
        return True
    text = f"{plan.search_query or ''} {plan.location.raw or ''}"
    return bool(_LANDUSE_QUERY_RE.search(text))


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
    landuse_relevant = _landuse_map_relevant(plan)
    if plan.requires_disclaimer and landuse_relevant and not skip_polygons:
        tasks["zoning"] = asyncio.create_task(_limited(
            zoning_for_map(ca)
        ))

    loc = plan.location
    if not skip_polygons:
        if ("regulatory_domain" in plan.sources and landuse_relevant
                and loc.resolved_lat and loc.resolved_lon):
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


def _map_capped_flags(map_rows: dict[str, Any]) -> dict[str, bool]:
    """Per-layer row-cap flags for fetched map rows — shared by the map
    response (badging) and compute_analytics (trend truncation guard)."""
    settings = get_settings()
    capped: dict[str, bool] = {}
    if "crimes" in map_rows:
        capped["crimes"] = len(map_rows.get("crimes", [])) >= settings.limit_map_crime
    if "requests_311" in map_rows:
        capped["requests_311"] = len(map_rows.get("requests_311", [])) >= settings.limit_map_311
    if "building_permits" in map_rows:
        capped["building_permits"] = len(map_rows.get("building_permits", [])) >= settings.limit_map_permits
    return capped


def _build_map_response(
    map_rows: dict[str, Any], plan: RetrievalPlan,
) -> MapDataResponse | None:
    """Build a MapDataResponse from fetched map rows."""
    if not map_rows:
        return None
    crimes = map_rows.get("crimes", [])
    requests_311 = map_rows.get("requests_311", [])
    building_permits = map_rows.get("building_permits", [])

    capped = _map_capped_flags(map_rows)

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


# Distance beyond which a turn's own geocode is treated as a pivot away from the
# sticky parcel (vs. geocoder jitter on the same parcel). ~0.1 mi ≈ 160 m.
_PARCEL_HINT_PIVOT_MI = 0.1


async def _apply_parcel_hint(plan, pin: str):
    """Replace the router's text-geocoded location with the authoritative parcel.

    Scorecard→chat handoffs carry the held parcel's PIN; without it the chat
    re-geocodes the address embedded in the question text and can land on a
    neighboring parcel. Only address-typed plans are overridden — a question
    the router read as a neighborhood/area query keeps its own location.
    Read-only direction (truth-model §3): chat never writes the selection.
    Any resolution failure leaves the plan untouched.
    """
    if plan.location.type != "address":
        return plan
    try:
        rl = await _resolve_location(pin=pin)
    except Exception:
        log.warning("Parcel hint resolution failed for pin %s — keeping router location", pin)
        return plan
    if rl.pin != pin:
        return plan
    loc = plan.location
    # Pivot guard (conversation-sticky grounding): the sticky parcel pin now rides
    # on EVERY turn, so a turn that pivoted to a different explicit address ("what
    # about 500 N State?") must NOT be dragged back to the held parcel. If the
    # router already geocoded this turn to a point far from the sticky parcel, the
    # user moved on — keep the router's location and let the grounding gate drop
    # the stale context via its pin mismatch. Follow-ups about the same parcel
    # (synthesize_query re-embeds its address) resolve near it and still anchor.
    if loc.resolved_lat is not None and loc.resolved_lon is not None:
        from backend.retrieval.property.sales import _haversine_mi
        if _haversine_mi(loc.resolved_lat, loc.resolved_lon, rl.lat, rl.lon) > _PARCEL_HINT_PIVOT_MI:
            return plan
    ca = community_area_by_point(rl.lat, rl.lon)
    loc.resolved_lat = rl.lat
    loc.resolved_lon = rl.lon
    loc.pin = rl.pin
    if rl.address:
        loc.resolved_address = rl.address
    if ca is not None:
        loc.resolved_community_area = ca
        loc.resolved_community_area_name = community_area_name(ca)
    return plan


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
        if req.parcel_pin:
            plan = await _apply_parcel_hint(plan, req.parcel_pin)
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
            _retrieve(plan, scorecard_context=req.scorecard_context),
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
            capped=_map_capped_flags(map_rows),
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


class ResolvedLocation(NamedTuple):
    """Outcome of parcel resolution. ``pin`` is the system-of-record identity
    (None on the degraded path); ``confidence`` is "authoritative" or
    "approximate" (truth-model §5, drives the INV-5 disclosure)."""
    lat: float
    lon: float
    address: str | None
    pin: str | None
    confidence: str


async def _resolve_location(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
) -> ResolvedLocation:
    """Resolve input to a parcel identity + point. Raises HTTPException on failure.

    Strict precedence (truth-model §5) — first confident match wins:
      1. explicit lat/lon — a deliberate point (map/Explorer click).
      2. supplied PIN — the authoritative parcel key (never overridden by a
         co-supplied address; INV-6 / R6).
      3. address → authoritative PIN via Cook County Address Points (78yw-iddh).
         GIS-independent; this is the step that closes R7 for typed addresses.
      4. degraded fallback — geocode + downstream nearest-centroid, flagged
         "approximate" so the artifact discloses it (INV-5).
      5. nothing resolvable → 422.
    """
    settings = get_settings()
    resolved_address: str | None = address

    # 1. Explicit coordinates are a deliberate point override — highest precedence.
    if lat is not None and lon is not None:
        return ResolvedLocation(lat, lon, resolved_address, pin, "authoritative")

    # 2. A supplied PIN is the authoritative unique parcel key — resolve its
    #    centroid directly, never overridden by a co-supplied address.
    if pin:
        from backend.retrieval.socrata import socrata_get
        from backend.retrieval.property.address_points import pin_to_address
        coord_coro = socrata_get(
            settings.dataset_ccao_parcels,
            # Parcel Universe (pabr-t5kh) exposes coordinates as lat/lon, not
            # latitude/longitude — the latter 400s and breaks PIN-only resolution.
            {"$where": f"pin='{pin}'", "$select": "lat,lon", "$limit": 1},
            base_url=settings.cook_county_socrata_base,
        )
        display_address = resolved_address
        if resolved_address:
            rows = await coord_coro
        else:
            # Pin-keyed entry (Explorer/chat handoff, canonical URLs) carries no
            # address — backfill a display address so the artifact isn't headed
            # "Unknown Address". Display-only: coordinates stay Parcel Universe,
            # and `resolved_address` is left untouched so the fallback steps
            # below behave exactly as before when the PIN has no coordinates.
            rows, display_address = await asyncio.gather(
                coord_coro, pin_to_address(pin)
            )
        if rows and rows[0].get("lat") and rows[0].get("lon"):
            return ResolvedLocation(
                float(rows[0]["lat"]), float(rows[0]["lon"]),
                display_address, pin, "authoritative",
            )

    # 3. Address → authoritative PIN via Address Points. Resolving the parcel by
    #    PIN (not by the geocoded point's nearest centroid) is what eliminates the
    #    ~77% wrong-parcel rate while GIS is down. The returned lat/lon is the
    #    parcel's own point, improving every coordinate-driven downstream domain.
    if address and settings.address_point_resolution_enabled:
        from backend.retrieval.property.address_points import address_to_pin
        hit = await address_to_pin(address)
        if hit:
            return ResolvedLocation(
                hit["lat"], hit["lon"], resolved_address, hit["pin14"], "authoritative",
            )

    # 3.5 Address → authoritative PIN via the Assessor's Parcel Addresses
    #     (3723-97qp) — a SECOND authoritative source consulted only after an
    #     Address Points miss. Covers parcels absent from 78yw-iddh (e.g. 481 W
    #     Deming Pl). It has no coordinates, so backfill the parcel centroid from
    #     Parcel Universe (same query as step 2). A PIN whose centroid doesn't
    #     resolve falls through to the degraded path rather than guessing a point.
    if address and settings.assessor_address_resolution_enabled:
        from backend.retrieval.property.parcel_addresses import assessor_address_to_pin
        from backend.retrieval.socrata import socrata_get
        assessor_pin = await assessor_address_to_pin(address)
        if assessor_pin:
            rows = await socrata_get(
                settings.dataset_ccao_parcels,
                {"$where": f"pin='{assessor_pin}'", "$select": "lat,lon", "$limit": 1},
                base_url=settings.cook_county_socrata_base,
            )
            if rows and rows[0].get("lat") and rows[0].get("lon"):
                return ResolvedLocation(
                    float(rows[0]["lat"]), float(rows[0]["lon"]),
                    resolved_address, assessor_pin, "authoritative",
                )

    # 4. Degraded fallback: geocode → street-interpolated point → downstream
    #    nearest-centroid. No confident PIN, so flag approximate (INV-5) and log.
    if address:
        coords = await geocode_address(address)
        if coords:
            log.warning(
                "R7 degraded resolution (approximate parcel) for address=%r", address
            )
            return ResolvedLocation(
                coords[0], coords[1], resolved_address, None, "approximate",
            )

    # 5. Nothing resolvable.
    raise HTTPException(
        status_code=422,
        detail="Could not geocode address. Try a different format or provide lat/lon coordinates.",
    )


async def _address_violations_data(resolved_address: str | None) -> dict | None:
    """Parcel-scoped building violations for the Scorecard, shaped for
    ``assembler._violation_summary`` ({status_counts, detail}).

    Switched off the community-area count (which rendered a whole neighborhood's
    violations as if they were this parcel's — a trust bug) to the address-exact
    dataset query. Returns None when the address can't be parsed to street fields
    (lat/lon- or PIN-only entry) so the card is omitted rather than falling back
    to area-as-parcel data. An empty {} (parsed, but no violations on record) is
    an honest "clean parcel" — _violation_summary maps it to None (no card).
    """
    if not resolved_address:
        return None
    parsed = buildings.parse_chicago_address(resolved_address)
    if not parsed:
        return None
    rows = await buildings.address_specific_violations(
        parsed["number"], parsed["direction"], parsed["name"]
    )
    status_counts: dict[str, int] = {}
    for r in rows:
        st = (r.get("violation_status") or "UNKNOWN").upper()
        status_counts[st] = status_counts.get(st, 0) + 1
    # "checked" distinguishes a confirmed-zero lookup (parsed + queried, no rows)
    # from a parse failure — so the UI can show "no violations on record" instead
    # of silently omitting, which would otherwise read identically to "couldn't
    # check." Silence must not mean two different things.
    return {
        "checked": True,
        "status_counts": [{"violation_status": s, "count": n} for s, n in status_counts.items()],
        "detail": rows,
    }


async def _fetch_scorecard_data(
    resolved_lat: float,
    resolved_lon: float,
    resolved_address: str | None,
    *,
    pin: str | None = None,
) -> dict:
    """Fetch all domain data for a location. Returns dict with context, metadata, and failures.

    ``pin`` (the authoritative parcel key from _resolve_location, when available)
    keys the property domain by PIN instead of re-deriving identity from the
    coordinate — INV-2. All other domains stay coordinate-driven on the resolved
    point.
    """
    ca = community_area_by_point(resolved_lat, resolved_lon)
    ca_name = community_area_name(ca) if ca else None

    tasks: dict[str, asyncio.Task] = {}
    wf = "property_intelligence"

    tasks["property"] = asyncio.create_task(_limited(
        property_domain(resolved_lat, resolved_lon, pin=pin, workflow=wf)
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

    # Violations + 311 are PARCEL-scoped (address-exact), not area-level — they
    # live outside the community-area block and key off the resolved address.
    tasks["violations"] = asyncio.create_task(_limited(
        _address_violations_data(resolved_address)
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

    # Phase 2: comparable sales (needs property class from phase 1). Class
    # derivation is shared with the report (_comp_class_prefix): exempt /
    # non-numeric classes resolve through zoning instead of querying a raw
    # first character (an "EX" subject used to search class LIKE 'E%').
    prop = results.get("property")
    if prop and getattr(prop, "bldg_class", None):
        zone_class_for_comps = (
            ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
        )
        class_prefix = _comp_class_prefix(prop.bldg_class, zone_class_for_comps)
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

    # Tri-state for the violations card: a present summary (ctx.violations), a
    # confirmed-zero ("no violations on record"), or an unconfirmed lookup
    # (address didn't parse / fetch failed → card omitted). Without this the
    # confirmed-zero and the parse-failure both render as "no card" and the
    # reader can't tell a clean building from an unchecked one.
    _viol_raw = results.get("violations")
    violations_checked = bool(_viol_raw) and bool(_viol_raw.get("checked"))

    return {
        "address": resolved_address,
        "lat": resolved_lat,
        "lon": resolved_lon,
        "community_area": ca,
        "community_area_name": ca_name,
        "context": ctx,
        "comparables": comparables_summary,
        "partial_failures": partial_failures,
        "violations_checked": violations_checked,
    }


@app.get("/api/area-stats")
async def area_stats(ca: int) -> dict:
    """Community-area benchmark aggregates for the Property Profile KPI band.
    Served from a daily in-process scan of the Discovery index; every stat is
    None/empty when the index is absent — the UI then renders no benchmark."""
    from backend.retrieval.area_stats import get_area_stats

    stats = await get_area_stats(ca)
    return stats or {
        "community_area": ca,
        "n_parcels": 0,
        "median_assessed": None,
        "n_assessed": 0,
        "median_mv_per_land_sqft": None,
        "n_mv_psf": 0,
        "by_land_use": {},
    }


_parcel_map_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="parcel_map")


@app.get("/api/parcel-map")
async def parcel_map(lat: float, lon: float) -> dict:
    """Geometry layers for the Property Profile's module maps: the zoning quilt
    around the parcel (Build module) and the overlay/TIF/EZ boundaries that hit
    the point (Regulatory/Incentives module). Every layer degrades to None —
    the maps render only the layers that arrive."""
    key = f"{lat:.4f},{lon:.4f}"
    cached = _parcel_map_cache.get(key)
    if cached is not None:
        return cached

    from backend.retrieval.zoning import zoning_polygons_near
    from backend.retrieval.incentives.tif import tif_geojson_feature
    from backend.retrieval.incentives.enterprise_zones import ez_geojson_feature

    results = await asyncio.gather(
        _limited(zoning_polygons_near(lat, lon)),
        _limited(_fetch_overlay_geojson(lat, lon)),
        _limited(tif_geojson_feature(lat, lon)),
        _limited(ez_geojson_feature(lat, lon)),
        return_exceptions=True,
    )
    zoning_fc, overlays_fc, tif_feat, ez_feat = (
        None if isinstance(r, Exception) else r for r in results
    )
    payload = {
        "zoning": _simplify_geojson(zoning_fc),
        "overlays": _simplify_geojson(overlays_fc),
        "tif": tif_feat,
        "ez": ez_feat,
    }
    # Cache only payloads with content: an all-empty result is a transient
    # upstream failure more often than a real empty area (the zoning quilt has
    # features anywhere in the city), and caching it blanked the maps for an
    # hour after one ArcGIS hiccup (2026-07-07 audit D4).
    def _feats(fc: Any) -> bool:
        return bool(isinstance(fc, dict) and fc.get("features"))

    if _feats(payload["zoning"]) or _feats(payload["overlays"]) \
            or payload["tif"] or payload["ez"]:
        _parcel_map_cache.set(key, payload)
    return payload


@app.get("/api/scorecard")
async def scorecard(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
) -> dict:
    """Non-AI instant-load property dashboard. Zero LLM cost."""
    rl = await _resolve_location(address, lat, lon, pin)
    data = await _fetch_scorecard_data(rl.lat, rl.lon, rl.address, pin=rl.pin)

    # Reconcile identity. When the authoritative address→PIN path degraded
    # ("approximate"), the property orchestrator still resolved a parcel from the
    # point via the nearest-centroid fallback — which is frequently a *neighbour*
    # (470 vs 481 W Deming; 2401/2403 vs 2400 N Milwaukee). Trust that PIN as the
    # parcel's identity only if its own address round-trips to the input; else
    # withhold it (never surface a neighbour as "exact") and flag the property/
    # comps data as based on a nearest, unverified parcel so the UI can caveat it.
    # See claude-context/audits/2026-06-21_resolver-investigation.md.
    resolved_pin = rl.pin
    resolved_confidence = rl.confidence
    nearest_parcel_unverified = False
    if address and resolved_confidence == "approximate":
        prop = data["context"].property
        candidate_pin = prop.pin14 if prop else None
        if candidate_pin:
            from backend.retrieval.property.address_points import parcel_address_matches
            if await parcel_address_matches(candidate_pin, address):
                resolved_pin = candidate_pin
                resolved_confidence = "authoritative"
            else:
                nearest_parcel_unverified = True
    # INV-1 guard: one artifact, one parcel. An authoritative resolved PIN whose
    # property record came back for a DIFFERENT pin14 means the PIN-keyed lookup
    # missed (PIN absent from Parcel Universe) and the orchestrator's coordinate
    # fallback resolved a nearby parcel instead — the identity is still the
    # resolved PIN, but the property/tax/comps figures describe the neighbor, so
    # they must carry the same caveat the approximate path uses.
    elif resolved_pin and resolved_confidence == "authoritative":
        prop = data["context"].property
        if prop and prop.pin14 and prop.pin14 != resolved_pin:
            log.warning(
                "INV-1 mismatch: resolved_pin=%s but property record is %s",
                resolved_pin, prop.pin14,
            )
            nearest_parcel_unverified = True

    data["resolved_pin"] = resolved_pin
    data["resolved_confidence"] = resolved_confidence
    data["nearest_parcel_unverified"] = nearest_parcel_unverified
    data["resolved_lat"] = rl.lat
    data["resolved_lon"] = rl.lon
    # Deterministic Title-17 bulk standards for the parcel's zone (same table
    # the PDF report uses) — powers the free "Zoning at a glance" card.
    zoning_summary = data["context"].parcel_zoning
    if zoning_summary:
        from dataclasses import asdict
        from backend.retrieval.zoning_definitions import get_zone_definition
        data["zone_definition"] = asdict(get_zone_definition(zoning_summary.zone_class))
    else:
        data["zone_definition"] = None
    data["context"] = data["context"].model_dump(exclude_none=True)
    if data.get("comparables"):
        data["comparables"] = data["comparables"].model_dump(exclude_none=True)
    else:
        data["comparables"] = None
    return data


@app.get("/api/report")
async def report(
    request: Request,
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    pin: str | None = None,
    mock: bool = False,
    language: str = "en",
    user: dict = Depends(require_auth),
) -> Response:
    """Generate a PDF development feasibility & site intelligence report."""
    import re
    from datetime import date

    from backend.auth import _TIER_ORDER
    from jinja2 import Environment, FileSystemLoader

    settings = get_settings()
    rl = await _resolve_location(address, lat, lon, pin)
    resolved_lat, resolved_lon, resolved_address = rl.lat, rl.lon, rl.address

    if _TIER_ORDER.get(user["tier"], 0) < _TIER_ORDER["premium"]:
        if not await db.has_purchased_report(
            user["id"], resolved_lat, resolved_lon, pin=rl.pin
        ):
            raise HTTPException(
                status_code=403,
                detail={"error": "report_purchase_required"},
            )

    # Bound concurrent report renders: _fetch_report_data through write_pdf is the
    # memory-heavy span (map rasters + WeasyPrint buffers). Holding _REPORT_SEM here
    # — not around the cheap auth/_resolve_location work above — caps peak render
    # memory so concurrent reports can't OOM the single worker. See the Tier-0
    # investigation in report-v6-execution-plan.md.
    async with _REPORT_SEM:
        report_data, basemap_bytes, basemap_wide_bytes = await _fetch_report_data(
            resolved_lat, resolved_lon, resolved_address, pin=rl.pin, confidence=rl.confidence,
            language=language,
        )

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

        # The basemap PNGs are only needed for the (optional) mock-mode map
        # regeneration above; the report's maps are already embedded as base64 in
        # report_data. Drop these buffers promptly so they aren't held resident
        # across the render span.
        del basemap_bytes, basemap_wide_bytes

        # Render HTML template
        from backend import report_i18n
        _t = report_i18n.make_translator(language)
        _tn = report_i18n.make_plural(language)
        _na = _t("common.na")
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        env.filters["fnum"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else _na
        env.filters["fpct"] = lambda v: f"{v * 100:.1f}%" if v is not None else _na
        env.filters["fcur"] = lambda v: f"${v:,.0f}" if v is not None else _na
        from backend.retrieval.zoning_definitions import get_zone_name
        env.filters["zone_desc"] = get_zone_name
        # Translator globals for the template (deterministic catalog, no LLM).
        env.globals["t"] = _t
        env.globals["tn"] = _tn
        template = env.get_template("zoning_report.html")

        html_content = template.render(
            report=report_data,
            report_date=report_i18n.format_report_date(date.today(), language),
        )

        # Generate the PDF in an ISOLATED CHILD PROCESS. write_pdf() (cairo/pango
        # laying out 16–19 image-embedded pages) is the heaviest single step of a
        # report; running it in a short-lived child gives a fresh address space
        # fully reclaimed on exit, so its memory (measured ~118 MB peak, 2026-06-16
        # prod) can never accumulate in or OOM the long-lived worker, and a runaway
        # render can be killed (timeout / oom_score_adj) without taking the worker
        # down. See backend/report_render.py. Still inside _REPORT_SEM, so at most
        # report_concurrency (=1) child renders run at once.
        from backend.report_render import PdfRenderError, render_pdf
        try:
            pdf_bytes = await render_pdf(
                html_content,
                timeout_s=settings.report_render_timeout_s,
                rlimit_as_bytes=settings.report_render_rlimit_as_bytes,
            )
        except PdfRenderError as exc:
            log.warning("Isolated PDF render failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail={"error": "report_render_failed"},
            ) from exc

    # Build filename
    slug = re.sub(r"[^a-z0-9]+", "_", (resolved_address or "property").lower()).strip("_")
    filename = f"{slug}_{date.today().isoformat()}_feasibility_report.pdf"

    # Trim glibc free lists back to the OS *after* the response is sent, so the
    # request's matplotlib/HTML allocations don't ratchet the worker's RSS up.
    from starlette.background import BackgroundTask

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=BackgroundTask(_trim_malloc),
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
    try:
        body = await request.json()
    except Exception:
        body = {}
    url = await create_checkout_session(user, visitor_id=body.get("visitor_id"))
    return {"url": url}


@app.post("/api/checkout/report")
async def checkout_report(request: Request, user: dict = Depends(require_auth)) -> dict:
    from backend.payments import create_report_checkout_session
    body = await request.json()
    address = body.get("address")
    lat = body.get("lat")
    lon = body.get("lon")
    pin = body.get("pin")
    if not pin and (not address or lat is None or lon is None):
        raise HTTPException(
            status_code=400, detail="pin or (address, lat, lon) is required"
        )
    if pin and (lat is None or lon is None):
        # Pin-only checkout: resolve the parcel centroid so the purchase row's
        # NOT NULL lat/lon (legacy coordinate entitlement) stays populated.
        rl = await _resolve_location(pin=pin)
        lat, lon = rl.lat, rl.lon
        address = address or rl.address
    url = await create_report_checkout_session(
        user, address, float(lat), float(lon), pin=pin,
        visitor_id=body.get("visitor_id"),
    )
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
    rl = await _resolve_location(address, lat, lon, pin)
    purchased = await db.has_purchased_report(user["id"], rl.lat, rl.lon, pin=rl.pin)
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


# Voucher redemption — early-adopter comp premium (see db.redeem_voucher).
# In-memory attempt cap: codes are unguessable, this just makes enumeration
# by a signed-in user pointless. Resets on restart, which is fine.
_VOUCHER_ATTEMPTS: dict[str, list[float]] = {}
_VOUCHER_ATTEMPT_LIMIT = 10  # per user per hour


@app.post("/api/voucher/redeem")
async def voucher_redeem(request: Request, user: dict = Depends(require_auth)) -> dict:
    body = await request.json()
    code = str(body.get("code", "")).strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    now = time.time()
    attempts = [t for t in _VOUCHER_ATTEMPTS.get(user["id"], []) if now - t < 3600]
    if len(attempts) >= _VOUCHER_ATTEMPT_LIMIT:
        raise HTTPException(
            status_code=429, detail="Too many attempts — try again in an hour"
        )
    attempts.append(now)
    _VOUCHER_ATTEMPTS[user["id"]] = attempts

    try:
        premium_until = await db.redeem_voucher(code, user["id"])
    except db.VoucherError as exc:
        status = {"not_found": 404, "already_redeemed": 409, "exhausted": 410}[
            exc.reason
        ]
        raise HTTPException(status_code=status, detail={"error": exc.reason})
    return {"premium_until": premium_until}


@app.get("/api/me/purchases")
async def my_purchases(request: Request, user: dict = Depends(require_auth)) -> dict:
    """Completed report purchases for the current user (settings billing list)."""
    purchases = await db.get_user_report_purchases(user["id"])
    return {"purchases": purchases}


@app.delete("/api/me")
async def delete_account(request: Request, user: dict = Depends(require_auth)):
    """Permanently delete the authenticated user's account.

    Stripe cancellation runs FIRST and aborts the deletion on failure — a
    live subscription must never be orphaned behind a deleted account.
    """
    from backend.auth import _auth_enabled
    if not _auth_enabled():
        raise HTTPException(
            status_code=400,
            detail="Account deletion is not available in dev mode",
        )
    from backend.payments import cancel_user_subscription
    await cancel_user_subscription(user)
    await db.delete_user_account(user["id"])
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"ok": True})
    clear_auth_cookies(resp)
    return resp


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

# Unambiguous code alphabet: no 0/O, 1/I/L — codes get read aloud and retyped.
_VOUCHER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


@app.get("/api/admin/vouchers")
async def admin_vouchers(
    request: Request, _admin: dict = Depends(require_admin)
) -> dict:
    return {"vouchers": await db.list_vouchers()}


@app.post("/api/admin/vouchers")
async def admin_create_voucher(
    request: Request, _admin: dict = Depends(require_admin)
) -> dict:
    import secrets

    body = await request.json()
    duration_days = int(body.get("duration_days", 30))
    max_redemptions = int(body.get("max_redemptions", 1))
    if duration_days < 1 or max_redemptions < 1:
        raise HTTPException(
            status_code=400, detail="duration_days and max_redemptions must be >= 1"
        )
    code = str(body.get("code") or "").strip().upper()
    if not code:
        code = "UL-" + "".join(
            secrets.choice(_VOUCHER_ALPHABET) for _ in range(8)
        )
    if await db.get_voucher(code):
        raise HTTPException(status_code=409, detail="Code already exists")
    return await db.create_voucher(
        code, body.get("label"), duration_days, max_redemptions
    )


@app.post("/api/admin/grant")
async def admin_grant_premium(
    request: Request, _admin: dict = Depends(require_admin)
) -> dict:
    """Grant comp premium by email — only works after the user's first sign-in."""
    body = await request.json()
    email = str(body.get("email", "")).strip()
    days = int(body.get("days", 30))
    if not email or days < 1:
        raise HTTPException(status_code=400, detail="email and days >= 1 are required")
    target = await db.get_user_by_email(email)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No account with that email — have them sign in once, "
                "or send a voucher code instead."
            ),
        )
    now_ms = int(time.time() * 1000)
    until = max(now_ms, target.get("premium_until") or 0) + days * 86_400_000
    await db.set_premium_until(target["id"], until)
    return {"user_id": target["id"], "email": target["email"], "premium_until": until}


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
    from backend.llm import estimate_cost
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


_VALID_EVENT_NAMES = {
    "page_view",
    "investigate_click",
    "report_cta_click",
    "chat_message_sent",
    "scorecard_bridge_click",
    "hero_address_submit",
    "hero_librarian_click",
    "sample_report_click",
    "visit_start",
    "scorecard_view",
    "checkout_started",
    "discovery_search",
    "signup_completed",
    "segment_selected",
    "scorecard_feedback",
    "newsletter_signup",
    # NOTE: purchase_completed / subscription_started are deliberately NOT
    # accepted here — money events are written server-side by the Stripe
    # webhook (payments.py) so a browser can't spoof them into the funnel.
}


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/newsletter")
async def newsletter_signup(request: Request) -> dict:
    """Anonymous newsletter capture — the owned email channel."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid body")
    email = (body.get("email") or "").strip()
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    source = str(body.get("source") or "")[:64] or None
    added = await db.add_subscriber(email, source)
    return {"ok": True, "added": added}


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
