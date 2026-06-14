"""Discovery wire endpoints (07) — `GET /discovery/registry`, `POST /discovery/search`.

`api` calls the fixed pipeline `parse → merge → evaluate → build` and assembles the
`SearchResponse`, echoing back the canonical post-merge CQS (INV-4). It is the only
place the compilers and the evaluator are wired together; the evaluator stays a leaf
that knows nothing about the wire (09).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import get_current_user, require_tier
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
from backend.discovery.registry import Coverage, Registry
from backend.discovery.registry import load as load_registry

log = logging.getLogger(__name__)

# Default page window for the result list (infinite scroll fetches subsequent windows).
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200
# Free-tier teaser: non-premium users get the top N ranked rows (with full fields incl.
# upside) + the TRUE total + a gated flag — then the upgrade wall. Enforced server-side so
# devtools can't page past it. The full ranked list / map intelligence / export are Pro.
FREE_ROW_CAP = 10


def _is_pro(user: dict | None) -> bool:
    return bool(user) and user.get("tier") in ("premium", "admin")

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
    gated: bool = False  # True for free tier — rows are the capped teaser, total is the real count


class SearchResponse(BaseModel):
    dataVersion: str
    cqs: CQS  # canonical, post-merge — FE renders chips/summary from THIS (INV-4)
    result: SearchResult
    diagnostics: Diagnostics


# Map = the FULL ordered match set (not the list window), capped so the browser stays sane.
MAX_MAP_POINTS = 5000


class PinPoint(BaseModel):
    pin: str
    lat: float | None
    lon: float | None
    upside: float | None  # upside_score → Pro map color (null = "no data" swatch)
    landUse: str | None  # land_use_class → free-tier map color (view-only, use-colored)


class PinsResponse(BaseModel):
    dataVersion: str
    total: int  # full match count
    points: list[PinPoint]  # full ordered coord set, capped at MAX_MAP_POINTS
    truncated: bool  # True when total > cap → some matches are off the map ("refine to see all")


ALL_COMMUNITY_AREAS = 77  # Chicago has 77 community areas → coverage "all"


def _iso_date(epoch: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).date().isoformat()


@router.get("/registry", response_model=Registry)
def get_registry() -> Registry:
    # The static artifact + the current index's coverage/populatedFields. With no index
    # (current_meta None) we return the artifact's defaults: coverage "none" + empty
    # populatedFields — i.e. fully dormant. NEVER infer "all available" from missing meta.
    base = load_registry()
    meta = parcel_source.current_meta()
    if meta is None:
        return base
    areas = sorted(set(meta.community_areas))
    mode = "all" if len(areas) >= ALL_COMMUNITY_AREAS else ("partial" if areas else "none")
    coverage = Coverage(mode=mode, liveAreas=areas, asOf=_iso_date(meta.built_at))
    return base.model_copy(update={"coverage": coverage, "populatedFields": sorted(meta.populated_fields)})


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
        # Display reads the REAL assessed value (exempt/$0 included); only the sort key
        # is nulled for exempt/$0, via parcel_index.derive_sort_fields.
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


def _pin_lookup(data_version: str) -> dict[str, parcel_mod.Parcel]:
    """A pin→parcel map over the dataVersion snapshot (shared by /search + /search/pins)."""
    return {p.pin: p for p in parcel_mod.default_source.get(data_version)}


def _hydrate_window(pins: list[str], data_version: str, sort_key: str) -> list[ResultRow]:
    """Hydrate the windowed PINs into ResultRows from the dataVersion snapshot."""
    by_pin = _pin_lookup(data_version)
    sort_field = load_registry().sort_field(sort_key)
    rows: list[ResultRow] = []
    for pin in pins:
        parcel = by_pin.get(pin)
        if parcel is not None:  # snapshot is authoritative; skip any stale pin
            rows.append(_row_from_parcel(parcel, sort_field))
    return rows


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, user: dict | None = Depends(get_current_user)) -> SearchResponse:
    # Defined sync so FastAPI runs the (CPU-bound) evaluation in a worker thread
    # rather than blocking the event loop.
    cqs, result, dropped, data_version = _resolve(req)
    diagnostics = build(cqs, data_version, evaluate, result=result, dropped=dropped)

    if _is_pro(user):
        limit = min(req.limit or DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT)
        offset = max(req.offset, 0)
        next_offset = offset + limit if offset + limit < result.total else None
        gated = False
    else:
        # Free teaser (server-enforced): top FREE_ROW_CAP, no paging past it, real total.
        limit, offset, next_offset, gated = FREE_ROW_CAP, 0, None, True

    window = result.pins[offset : offset + limit]
    rows = _hydrate_window(window, data_version, cqs.sort.key)

    return SearchResponse(
        dataVersion=data_version,
        cqs=cqs,
        result=SearchResult(rows=rows, total=result.total, nextOffset=next_offset, gated=gated),
        diagnostics=diagnostics,
    )


@router.post("/search/pins", response_model=PinsResponse)
def search_pins(req: SearchRequest) -> PinsResponse:
    # Same _resolve path as /search → identical ordered PIN sequence by construction (the
    # map prefix matches the list prefix; sort/scope/topicId can't drift between them).
    # Returns the FULL ordered coord set (capped), NOT the list's paginated window — the
    # map is never sourced from the infinite-scroll rows. NOT tier-capped: free users see
    # ALL match dots (the FE colors free by land use + makes it view-only — a presentational
    # gate; upside rides along since it isn't secret).
    _cqs, result, _dropped, data_version = _resolve(req)
    by_pin = _pin_lookup(data_version)
    points: list[PinPoint] = []
    for pin in result.pins[:MAX_MAP_POINTS]:
        parcel = by_pin.get(pin)
        if parcel is not None:
            points.append(
                PinPoint(
                    pin=parcel.pin,
                    lat=parcel.lat,
                    lon=parcel.lon,
                    upside=parcel.get("upside_score"),
                    landUse=parcel.get("land_use_class"),
                )
            )
    return PinsResponse(
        dataVersion=data_version,
        total=result.total,
        points=points,
        truncated=result.total > MAX_MAP_POINTS,
    )


# CSV export columns: (ResultRow attr, header). A header given as ("filter", id) is sourced
# from that filter's hand-authored registry label — never a snake_case field id. The CSV is
# the deliverable a prospector takes to a spreadsheet, so every header reads in English.
_EXPORT_COLUMNS: list[tuple[str, str | tuple[str, str]]] = [
    ("pin", "PIN"),
    ("address", "Address"),
    ("community_area", "Community area"),
    ("land_use", ("filter", "land_use")),
    ("parcel_class", "Class"),
    ("lot_sqft", ("filter", "lot_size")),
    ("bldg_sqft", ("filter", "building_size")),
    ("year_built", ("filter", "year_built")),
    ("units", ("filter", "units")),
    ("assessed_value", ("filter", "assessed_value")),
    ("price_per_sf", ("filter", "price_per_sf")),
    ("last_sale_price", ("filter", "last_sale_price")),
    ("last_sale_date", "Last sale date"),
    ("improvement_ratio", ("filter", "improvement_ratio")),
    ("value_percentile", ("filter", "value_percentile")),
    ("upside_score", ("filter", "upside_score")),
    ("is_teardown_candidate", ("filter", "is_teardown_candidate")),
    ("lat", "Latitude"),
    ("lon", "Longitude"),
]


def _export_headers(registry: Registry) -> list[str]:
    out: list[str] = []
    for _attr, header in _EXPORT_COLUMNS:
        if isinstance(header, tuple):
            out.append(registry.filter_def(header[1]).label or header[1])
        else:
            out.append(header)
    return out


def _csv_cell(row: ResultRow, attr: str) -> object:
    value = getattr(row, attr)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return int(value)  # 9000000 not 9000000.0 — clean for a spreadsheet
    return "" if value is None else value


def _export_filename(cqs: CQS, data_version: str) -> str:
    # Slug from the canonical CQS filter ids — the same source the FE summarize() reads, so
    # the filename reflects exactly what was filtered. Plus dataVersion + date.
    ids = sorted(cqs.filters.keys())
    raw = "-".join(ids) if ids else "all"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "all"
    date = datetime.now(timezone.utc).date().isoformat()
    name = f"discovery_{slug[:60]}_{data_version}_{date}.csv"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)


def _export_stream(cqs: CQS, result: OrderedResult, data_version: str) -> Iterator[str]:
    """Yield the FULL match set as CSV, in evaluated order — never the list window."""
    registry = load_registry()
    sort_field = registry.sort_field(cqs.sort.key)
    by_pin = _pin_lookup(data_version)
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        out = buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        return out

    writer.writerow(_export_headers(registry))
    yield flush()
    for pin in result.pins:  # ALL rows, no limit/offset
        parcel = by_pin.get(pin)
        if parcel is None:
            continue
        row = _row_from_parcel(parcel, sort_field)
        writer.writerow([_csv_cell(row, attr) for attr, _h in _EXPORT_COLUMNS])
        yield flush()


@router.post("/search/export")
def search_export(req: SearchRequest, _user: dict = Depends(require_tier("premium"))) -> StreamingResponse:
    # Premium-gated (free tier → 403). Exports the FULL match set, server-side, via the same
    # _resolve path as /search and /search/pins — so the CSV is exactly what the user
    # filtered, in the same order, independent of any list pagination.
    cqs, result, _dropped, data_version = _resolve(req)
    filename = _export_filename(cqs, data_version)
    return StreamingResponse(
        _export_stream(cqs, result, data_version),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
