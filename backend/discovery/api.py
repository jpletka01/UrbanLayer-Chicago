"""Discovery wire endpoints (07) — `GET /discovery/registry`, `POST /discovery/search`.

`api` calls the fixed pipeline `parse → merge → evaluate → build` and assembles the
`SearchResponse`, echoing back the canonical post-merge CQS (INV-4). It is the only
place the compilers and the evaluator are wired together; the evaluator stays a leaf
that knows nothing about the wire (09).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.discovery import parcel_source
from backend.discovery.compile_merge import merge
from backend.discovery.compile_text import parse
from backend.discovery.cqs import CQS, CqsFragment, FilterAssignment, Predicate, SortSpec, SpatialScope
from backend.discovery.diagnostics import Diagnostics, build
from backend.discovery.evaluator import evaluate
from backend.discovery.registry import Registry
from backend.discovery.registry import load as load_registry

log = logging.getLogger(__name__)

# Mounted under /api so the production nginx (which proxies only /api/, /chat, /health,
# /autocomplete, /section/ to the backend) routes it — and so it never collides with the
# frontend's /discovery page route.
router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class SearchRequest(BaseModel):
    # current chip state (topic-expand + user edits, FE-applied) — raw predicates
    userFilters: dict[str, Predicate] = Field(default_factory=dict)
    topicId: str | None = None  # telemetry only; backend does NOT re-expand (04.4)
    text: str | None = None  # parsed by the backend text compiler
    sort: SortSpec | None = None  # user override; else registry default
    scope: SpatialScope | None = None  # default {mode:"all"}
    registryVersion: str | None = None  # FE staleness check (advisory; FE refetches)


class SearchResult(BaseModel):
    pins: list[str]
    total: int


class SearchResponse(BaseModel):
    dataVersion: str
    cqs: CQS  # canonical, post-merge — FE renders chips/summary from THIS (INV-4)
    result: SearchResult
    diagnostics: Diagnostics


@router.get("/registry", response_model=Registry)
def get_registry() -> Registry:
    return load_registry()


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    # Defined sync so FastAPI runs the (CPU-bound) evaluation in a worker thread
    # rather than blocking the event loop.
    user_frag = CqsFragment(
        filters={
            fid: FilterAssignment(predicate=pred, source="user")
            for fid, pred in req.userFilters.items()
        }
    )
    text_frag = parse(req.text or "")

    cqs, dropped = merge(
        user_frag, text_frag, sort=req.sort, scope=req.scope, topic_id=req.topicId
    )

    data_version = parcel_source.current_version()
    result = evaluate(cqs, data_version)
    diagnostics = build(cqs, data_version, evaluate, result=result, dropped=dropped)

    return SearchResponse(
        dataVersion=data_version,
        cqs=cqs,
        result=SearchResult(pins=result.pins, total=result.total),
        diagnostics=diagnostics,
    )
