"""Discovery wire endpoints (07) — `GET /discovery/registry`, `POST /discovery/search`.

`api` calls the fixed pipeline `parse → merge → evaluate → build` and assembles the
`SearchResponse`, echoing back the canonical post-merge CQS (INV-4). It is the only
place the compilers and the evaluator are wired together; the evaluator stays a leaf
that knows nothing about the wire (09).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend.discovery import parcel as parcel_mod
from backend.discovery import parcel_source
from backend.discovery.compile_merge import merge
from backend.discovery.compile_text import parse
from backend.discovery.cqs import (
    CQS,
    CqsFragment,
    DroppedInvalid,
    FilterAssignment,
    Predicate,
    SortSpec,
    SpatialScope,
)
from backend.discovery.diagnostics import Diagnostics, build
from backend.discovery.evaluator import OrderedResult, evaluate
from backend.discovery.registry import Registry
from backend.discovery.registry import load as load_registry

log = logging.getLogger(__name__)

# Default page window for the result list (infinite scroll fetches subsequent windows).
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200

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
    # Result-list pagination window over the (fully ordered) evaluator output. The
    # evaluator still returns the complete ordered PIN list; the API slices the window.
    limit: int | None = None  # rows per page (clamped to MAX_PAGE_LIMIT)
    offset: int = 0  # window start into the ordered result


class ResultRow(BaseModel):
    """One hydrated result parcel — the scannable unit of the result list + map.

    Fields beyond the frozen `pin` are hydrated from the same dataVersion snapshot the
    evaluator ordered; the derived ones (`value_percentile`, `upside_score`,
    `is_teardown_candidate`) stay null until the index computes them (PR-INDEX).
    """

    model_config = ConfigDict(populate_by_name=True)

    pin: str
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    community_area: int | None = None
    land_use: str | None = None
    parcel_class: str | None = Field(default=None, alias="class")
    lot_sqft: float | None = None
    bldg_sqft: float | None = None
    year_built: int | None = None
    units: int | None = None
    assessed_value: float | None = None
    price_per_sf: float | None = None
    last_sale_price: float | None = None
    last_sale_date: str | None = None
    improvement_ratio: float | None = None
    value_percentile: float | None = None
    upside_score: float | None = None
    is_teardown_candidate: bool = False
    # The value of the ACTIVE sort key for this row — so the list can always surface
    # "what you sorted by" even when that field is not one of the displayed columns.
    sortValue: float | str | None = None


class SearchResult(BaseModel):
    rows: list[ResultRow]  # the requested page window, in evaluated order
    total: int  # full match count (drives count + teaser; independent of the window)
    nextOffset: int | None = None  # cursor for the next window; None when exhausted


class SearchResponse(BaseModel):
    dataVersion: str
    cqs: CQS  # canonical, post-merge — FE renders chips/summary from THIS (INV-4)
    result: SearchResult
    diagnostics: Diagnostics


@router.get("/registry", response_model=Registry)
def get_registry() -> Registry:
    return load_registry()


def _resolve(req: SearchRequest) -> tuple[CQS, OrderedResult, list[DroppedInvalid], str]:
    """The single parse→merge→evaluate path.

    `/search`, and later `/search/pins` and `/search/export`, ALL go through this so the
    canonical CQS and the fully ordered result can never drift between endpoints by
    construction (sort/scope/topicId are applied in exactly one place). Each endpoint
    differs only in how it projects the shared `OrderedResult`.
    """
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
    return cqs, result, dropped, data_version


def _display_sort_value(parcel: parcel_mod.Parcel, sort_field: str) -> float | str | None:
    """The active sort key's value for this row (PIN key → the raw PIN, never missing)."""
    if sort_field == "pin":
        return parcel.pin
    return parcel.get(sort_field)


def _row_from_parcel(parcel: parcel_mod.Parcel, sort_field: str) -> ResultRow:
    g = parcel.get
    return ResultRow(
        pin=parcel.pin,
        lat=parcel.lat,
        lon=parcel.lon,
        address=g("address"),
        community_area=g("community_area"),
        land_use=g("land_use_class"),
        # exempt/$0 assessments are already absent at the snapshot seam
        # (parcel_index.normalize_value_fields), so this reads None for them.
        assessed_value=g("total_assessed_value"),
        **{"class": g("class")},
        lot_sqft=g("land_sqft"),
        bldg_sqft=g("bldg_sqft"),
        year_built=g("year_built"),
        units=g("units"),
        price_per_sf=g("price_per_sf"),
        last_sale_price=g("last_sale_price"),
        last_sale_date=g("last_sale_date"),
        improvement_ratio=g("improvement_ratio"),
        value_percentile=g("value_percentile"),
        upside_score=g("upside_score"),
        is_teardown_candidate=bool(g("is_teardown_candidate")),
        sortValue=_display_sort_value(parcel, sort_field),
    )


def _hydrate_window(pins: list[str], data_version: str, sort_key: str) -> list[ResultRow]:
    """Hydrate the windowed PINs into ResultRows from the dataVersion snapshot."""
    by_pin = {p.pin: p for p in parcel_mod.default_source.get(data_version)}
    sort_field = load_registry().sort_field(sort_key)
    rows: list[ResultRow] = []
    for pin in pins:
        parcel = by_pin.get(pin)
        if parcel is not None:  # snapshot is authoritative; skip any stale pin
            rows.append(_row_from_parcel(parcel, sort_field))
    return rows


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    # Defined sync so FastAPI runs the (CPU-bound) evaluation in a worker thread
    # rather than blocking the event loop.
    cqs, result, dropped, data_version = _resolve(req)
    diagnostics = build(cqs, data_version, evaluate, result=result, dropped=dropped)

    limit = min(req.limit or DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT)
    offset = max(req.offset, 0)
    window = result.pins[offset : offset + limit]
    rows = _hydrate_window(window, data_version, cqs.sort.key)
    next_offset = offset + limit if offset + limit < result.total else None

    return SearchResponse(
        dataVersion=data_version,
        cqs=cqs,
        result=SearchResult(rows=rows, total=result.total, nextOffset=next_offset),
        diagnostics=diagnostics,
    )
