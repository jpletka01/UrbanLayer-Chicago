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
from functools import lru_cache
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
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
from backend.discovery.evaluator import EvalResult
from backend.discovery.result_cache import cached_evaluate
from backend.discovery.registry import Coverage, ParcelTiles, Registry
from backend.discovery.registry import load as load_registry
from backend.discovery.lot_facts import WARNING_ORDER
from backend.retrieval.property.assessment_level import is_nominal_assessment

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
    # Also return the map's coordinate set from this same evaluation (see SearchResponse.pins).
    includePins: bool = False
    # Opt in to the parcels the default `hide_unusual` filter keeps out (decision Item 60).
    includeUnusual: bool = False
    # Also return how many matches fall in each community area, from the same evaluation (the new map's city view
    # labels each area with its count: matches are drawn as lot outlines only, Item 104).
    includeAreaCounts: bool = False


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
    # The district's family and table FAR, already in the index (the exact class awaits the index
    # enrichment wave); the dot preview shows them (decision Item 57).
    zoning_group: str | None = None
    zone_class: str | None = None  # the exact district, once the index carries it (Item 59)
    allowed_far: float | None = None
    # A nominal assessment ($1 common area; decision Item 46): the row says "Nominal", never "$1".
    nominal_assessment: bool = False
    # Room to build (allowed floor area minus the building's) and where the building area came from: assessor,
    # commercial_valuation or footprint (Item 104). None = unknown, never 0.
    room_sqft: float | None = None
    bldg_sqft_source: str | None = None
    # "complex" = the room of the multi-parcel site this lot belongs to (complex_lots lots), not of the lot alone.
    room_scope: str | None = None
    complex_lots: int | None = None
    # How wide the lot really is (the widest circle inside it), and whether that makes it a strip (< 16 ft, Item 104).
    lot_width_ft: float | None = None
    narrow_strip: bool = False
    # What a card shows beyond the figures (owner's review, Item 104): the City's neighborhood (slug), the walk to the
    # nearest L station in miles, and the incentive areas the lot is in.
    hood: str | None = None
    transit_mi: float | None = None
    in_tif: bool | None = None
    in_enterprise_zone: bool | None = None
    # At most one serious warning for the card (Item 104): {"kind": demolition | vacant_case | pending_rezoning |
    # landmark | nominal, "detail": a date or a name, when there is one}.
    warning: dict[str, str | None] | None = None
    # The value of the ACTIVE sort key for this row — so the list can always surface
    # "what you sorted by" even when that field is not one of the displayed columns.
    sortValue: float | str | None = None


class SearchResult(BaseModel):
    rows: list[ResultRow]  # the requested page window, in evaluated order
    total: int  # full match count (drives count + teaser; independent of the window)
    nextOffset: int | None = None  # cursor for the next window; None when exhausted
    gated: bool = False  # True for free tier — rows are the capped teaser, total is the real count


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


class SearchResponse(BaseModel):
    dataVersion: str
    cqs: CQS  # canonical, post-merge — FE renders chips/summary from THIS (INV-4)
    result: SearchResult
    diagnostics: Diagnostics
    # Only when the request set `includePins`: exactly what POST /search/pins returns for the
    # same request, computed from the SAME evaluation as `result` (one dataVersion, one
    # total, one ordering), so list and map cannot disagree. Not tier-capped, like /pins.
    pins: PinsResponse | None = None
    # Only with `includeAreaCounts`: community area number (as a string) -> matches in it.
    areaCounts: dict[str, int] | None = None


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
    return base.model_copy(update={
        "coverage": coverage,
        "populatedFields": sorted(meta.populated_fields),
        "recipeCounts": meta.recipe_counts,
        "parcelTiles": _parcel_tiles(meta.data_version),
    })


def _parcel_tiles(index_version: str) -> ParcelTiles | None:
    """The tile file's registry block (decision Item 68), or None when no usable file is installed."""
    from backend.config import get_settings
    from backend.discovery.parcel_tiles import tiles_info

    info = tiles_info(get_settings().discovery_tiles_path)
    if not info:
        return None
    try:
        return ParcelTiles(
            builtAt=info.get("built_at") or "", minZoom=int(info["minzoom"]), maxZoom=int(info["maxzoom"]),
            parcels=int(info.get("parcels") or 0), current=info.get("index_version") == index_version,
        )
    except (KeyError, ValueError):
        return None


def _resolve(req: SearchRequest) -> tuple[CQS, EvalResult, list[DroppedInvalid], str]:
    """The single parse→merge→evaluate path.

    `/search`, and later `/search/pins` and `/search/export`, ALL go through this so the
    canonical CQS and the fully ordered result can never drift between endpoints by
    construction (sort/scope/topicId are applied in exactly one place). Each endpoint
    differs only in how it projects the shared ordered result.
    """
    user_frag = CqsFragment(
        filters={
            fid: FilterAssignment(predicate=pred, source="user")
            for fid, pred in req.userFilters.items()
        }
    )
    text_frag = parse(req.text or "")
    cqs, dropped = merge(
        user_frag, text_frag, sort=req.sort, scope=req.scope, topic_id=req.topicId,
        include_unusual=req.includeUnusual,
    )
    data_version = parcel_source.current_version()
    result = cached_evaluate(cqs, data_version)  # the single evaluator, memoised (INV-2)
    return cqs, result, dropped, data_version


def _display_sort_value(parcel: parcel_mod.Parcel, sort_field: str) -> float | str | None:
    """The active sort key's value for this row (PIN key → the raw PIN, never missing)."""
    if sort_field == "pin":
        return parcel.pin
    return parcel.get(sort_field)


def _nominal(av: float | None, cls: str | None, land_use: str | None) -> bool:
    """A $1-$99 token assessment on a taxable parcel (decision Item 46). $0 and exempt rows keep their own
    display: $0 is a value the County carries, not a placeholder to explain (the list's $0-vs-missing rule)."""
    return bool(av) and av > 0 and land_use != "exempt" and is_nominal_assessment(av, cls)


def _warning(g, nominal: bool) -> dict[str, str | None] | None:
    """The one serious warning a card shows, in the owner's order (Item 104)."""
    for key in WARNING_ORDER:
        v = g(key)
        if v:
            return {"kind": key.removeprefix("warn_"), "detail": v if isinstance(v, str) else None}
    return {"kind": "nominal", "detail": None} if nominal else None


def _row_from_parcel(parcel: parcel_mod.Parcel, sort_field: str) -> ResultRow:
    g = parcel.get
    nominal = _nominal(g("total_assessed_value"), g("class"), g("land_use_class"))
    return ResultRow(
        pin=parcel.pin,
        lat=parcel.lat,
        lon=parcel.lon,
        address=g("address"),
        community_area=g("community_area") or _community_area_of(parcel),
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
        zoning_group=g("zoning_group"),
        zone_class=g("zone_class"),
        allowed_far=g("density_band"),
        nominal_assessment=nominal,
        room_sqft=g("room_sqft"),
        bldg_sqft_source=g("bldg_sqft_source"),
        room_scope=g("room_scope"),
        complex_lots=g("complex_lots"),
        lot_width_ft=g("lot_width_ft"),
        narrow_strip=bool(g("narrow_strip")),
        hood=g("hood"),
        transit_mi=g("cta_rail_distance_mi"),
        in_tif=g("in_tif_district"),
        in_enterprise_zone=g("in_enterprise_zone"),
        warning=_warning(g, nominal),
        sortValue=_display_sort_value(parcel, sort_field),
    )


def _pin_lookup(data_version: str) -> dict[str, parcel_mod.Parcel]:
    """A pin→parcel map over the dataVersion snapshot (shared by /search + /search/pins).

    Memoized in parcel_source (built once per dataVersion) — not rebuilt O(N) per request.
    """
    return parcel_source.pin_lookup(data_version)


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


def _pins_payload(result: EvalResult, data_version: str) -> PinsResponse:
    """The map's coordinate set: the ordered prefix of the result, capped at MAX_MAP_POINTS."""
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


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, user: dict | None = Depends(get_current_user)) -> SearchResponse:
    # Defined sync so FastAPI runs the (CPU-bound) evaluation in a worker thread
    # rather than blocking the event loop.
    cqs, result, dropped, data_version = _resolve(req)
    diagnostics = build(cqs, data_version, cached_evaluate, result=result, dropped=dropped)

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
        pins=_pins_payload(result, data_version) if req.includePins else None,
        areaCounts=_area_counts(result, data_version) if req.includeAreaCounts else None,
    )


def _community_area_of(parcel) -> int | None:
    """The community area from the parcel's own region handle (the index keeps it there, not in attrs)."""
    for region in getattr(parcel, "_regions", ()):
        if region.startswith("neighborhood:"):
            try:
                return int(region.split(":", 1)[1])
            except ValueError:
                return None
    return None


def _area_counts(result, data_version: str) -> dict[str, int]:
    """Matches per community area, read from each matched parcel's own region handles."""
    lookup = _pin_lookup(data_version)
    counts: dict[str, int] = {}
    for pin in result.pins:
        parcel = lookup.get(pin)
        ca = _community_area_of(parcel) if parcel is not None else None
        if ca is not None:
            counts[str(ca)] = counts.get(str(ca), 0) + 1
    return counts


@router.get("/distribution")
def distribution(filter: str = Query(..., alias="filter")) -> dict:
    """A filter's values across the whole index, and how many lots have no value (Item 104): the filters sheet's
    coverage line and histogram, with the unknowns as their own hatched bar. A range filter is binned over its
    registry domain; an enum or flag is counted by value. Display only: never a search."""
    try:
        fdef = load_registry().filter_def(filter)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown filter")
    if fdef.kind == "region":
        raise HTTPException(status_code=422, detail="a region filter has no distribution")
    return _distribution(parcel_source.current_version(), filter)


@lru_cache(maxsize=64)
def _distribution(version: str, filter_id: str) -> dict:
    fdef = load_registry().filter_def(filter_id)
    ranged = fdef.kind == "range" and fdef.range is not None
    lo, hi = fdef.range.domain if ranged else (0.0, 1.0)
    n_bins = 16
    width = (hi - lo) / n_bins or 1
    counts = [0] * n_bins
    values: dict[str, int] = {}
    unknown = total = 0
    for parcel in parcel_source.pin_lookup(version).values():
        total += 1
        v = parcel.get(fdef.field)
        if v is None:
            unknown += 1
        elif ranged:
            i = int((float(v) - lo) // width)
            counts[min(max(i, 0), n_bins - 1)] += 1
        else:
            key = str(v).lower() if isinstance(v, bool) else str(v)
            values[key] = values.get(key, 0) + 1
    out: dict = {"filter": filter_id, "dataVersion": version, "total": total, "unknown": unknown}
    if ranged:
        out["bins"] = [{"min": lo + i * width, "max": lo + (i + 1) * width, "n": c} for i, c in enumerate(counts)]
    else:
        out["values"] = values
    return out


@router.get("/lot-context")
def lot_context(pin10: str = Query(..., min_length=10, max_length=10)) -> dict:
    """A lot and its neighbors for a card's picture (owner's review, Item 104): outlines within about 50 m of the lot,
    each with its room-to-build band (the lot tiles' `r`), so a card draws a slice of the block colored like the map.
    Display only."""
    digits = "".join(ch for ch in pin10 if ch.isdigit())
    if len(digits) != 10:
        raise HTTPException(status_code=400, detail="pin10 must be 10 digits")
    return _lot_context(parcel_source.current_version(), digits)


_CTX_CELL = 0.0006  # degrees; neighbors come from this cell and the eight around it (~50-65 m)


@lru_cache(maxsize=2)
def _pin10_grid(version: str) -> tuple[dict[tuple[int, int], list[str]], dict[str, tuple[float, float, dict]]]:
    grid: dict[tuple[int, int], list[str]] = {}
    lots: dict[str, tuple[float, float, dict]] = {}
    for parcel in parcel_source.pin_lookup(version).values():
        if parcel.lat is None or parcel.lon is None:
            continue
        p10 = parcel.pin.replace("-", "")[:10]
        if p10 in lots and not parcel.pin.replace("-", "").endswith("0000"):
            continue  # the base parcel speaks for the lot
        lots[p10] = (parcel.lat, parcel.lon, parcel._attrs)
    for p10, (lat, lon, _a) in lots.items():
        grid.setdefault((int(lat // _CTX_CELL), int(lon // _CTX_CELL)), []).append(p10)
    return grid, lots


@lru_cache(maxsize=512)
def _lot_context(version: str, pin10: str) -> dict:
    import sqlite3

    import shapely
    from shapely import wkt as shapely_wkt
    from shapely.geometry import mapping

    from backend.config import get_settings
    from backend.discovery.lot_facts import measure_bands

    grid, lots = _pin10_grid(version)
    me = lots.get(pin10)
    if me is None:
        raise HTTPException(status_code=404, detail="lot not in the index")
    cy, cx = int(me[0] // _CTX_CELL), int(me[1] // _CTX_CELL)
    near = [p for dy in (-1, 0, 1) for dx in (-1, 0, 1) for p in grid.get((cy + dy, cx + dx), [])]
    path = get_settings().ptaxsim_db_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="no outlines")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(near))
        latest: dict[str, str] = {}
        for p, text in db.execute(
            f"SELECT pin10, geometry FROM pin_geometry_raw WHERE pin10 IN ({marks}) AND geometry IS NOT NULL ORDER BY end_year ASC",
            near,
        ):
            latest[p] = text
    finally:
        db.close()
    feats = []
    for p, text in latest.items():
        try:
            g = shapely_wkt.loads(text).simplify(0.000003, preserve_topology=True)
        except (shapely.errors.GEOSException, ValueError):
            continue
        band = measure_bands(lots[p][2]).get("r")
        feats.append({"type": "Feature", "geometry": mapping(g),
                      "properties": {"pin10": p, "r": band, "me": p == pin10}})
    return {"type": "FeatureCollection", "features": feats}


@router.get("/neighborhoods")
def neighborhood_outlines() -> Response:
    """The City's 98 named neighborhoods (Item 104): names, slugs (the `hood:<slug>` region) and outlines."""
    from backend.discovery.neighborhoods import geojson_bytes

    return Response(content=geojson_bytes(), media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/areas")
def community_area_outlines() -> Response:
    """The 77 community areas, simplified to about 15 m, with a label point each: the new map's city view."""
    return Response(content=_areas_geojson(), media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@lru_cache(maxsize=1)
def _areas_geojson() -> bytes:
    import json as _json

    import shapely
    from shapely.geometry import mapping, shape

    from backend.config import get_settings

    raw = _json.loads((get_settings().data_dir / "community_areas.geojson").read_text())
    feats = []
    for f in raw.get("features", []):
        props = f.get("properties") or {}
        num = props.get("community_area")
        if num is None or not f.get("geometry"):
            continue
        g = shape(f["geometry"]).simplify(0.00015, preserve_topology=True)
        label = shapely.point_on_surface(g)
        feats.append({"type": "Feature", "id": int(num), "geometry": mapping(g),
                      "properties": {"ca": int(num), "name": str(props.get("name") or ""),
                                     "lx": round(label.x, 5), "ly": round(label.y, 5)}})
    return _json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")).encode()


@router.get("/parcel", response_model=ResultRow)
def parcel_row(pin: str, sort: str = Query("lot_size")) -> ResultRow:
    """One result row by PIN, for the map's dot preview (decision Item 57): a dot outside the loaded list
    window still opens a preview. The same fields as a /search row, from the current snapshot; every
    tier gets it (Q1: the full preview for everyone). Pro keeps the list past the teaser, export and
    the upside coloring."""
    version = parcel_source.current_version()
    parcel = _pin_lookup(version).get(pin)
    if parcel is None:
        # A map outline carries only its PIN10 (one outline per PIN10, Item 68): open that lot's base
        # parcel, else its lowest unit PIN. An outline with no row here is "not in our data yet".
        digits = "".join(ch for ch in pin if ch.isdigit())
        if len(digits) == 10:
            parcel = parcel_source.pin10_lookup(version).get(digits)
    if parcel is None:
        raise HTTPException(status_code=404, detail="parcel not in the index")
    try:
        sort_field = load_registry().sort_field(sort)
    except KeyError:  # an unknown sort key reads the default rather than failing the preview
        sort_field = load_registry().sort_field("lot_size")
    return _row_from_parcel(parcel, sort_field)


@router.post("/search/pins", response_model=PinsResponse)
def search_pins(req: SearchRequest) -> PinsResponse:
    # Same _resolve path as /search → identical ordered PIN sequence by construction (the
    # map prefix matches the list prefix; sort/scope/topicId can't drift between them).
    # Returns the FULL ordered coord set (capped), NOT the list's paginated window — the
    # map is never sourced from the infinite-scroll rows. NOT tier-capped: free users see
    # ALL match dots (the FE colors free by land use + makes it view-only — a presentational
    # gate; upside rides along since it isn't secret).
    _cqs, result, _dropped, data_version = _resolve(req)
    return _pins_payload(result, data_version)


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
    ids = sorted(fid for fid, a in cqs.filters.items() if a.source != "default")  # the default hide is not a choice
    raw = "-".join(ids) if ids else "all"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "all"
    date = datetime.now(timezone.utc).date().isoformat()
    name = f"discovery_{slug[:60]}_{data_version}_{date}.csv"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)


def _export_stream(cqs: CQS, result: EvalResult, data_version: str) -> Iterator[str]:
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
