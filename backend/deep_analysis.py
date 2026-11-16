"""Deep analysis (Phase 9, decision Item 124): the data behind the Profile's sixth tab.

``GET /api/deep-analysis?pin=&language=`` returns today's report as structured data, never a PDF: the same
``report_builder._fetch_report_data`` with ``rasters=False`` (no Mapbox images, no matplotlib, no code search), so
the tab and the PDF read the same facts and the same deterministic synthesis. **No model is called anywhere on
this path** (`test_deep_analysis.py` fails if one is reached), which is why Pro is unlimited.

Who may read it is decided here, on the server, each time: Pro and admin, or the account's free lot
(``entitlements.opens_lot``, a condo unit opens its lot). Reading never claims the free analysis; only
``POST /api/entitlements/deep-analysis`` does. A lot whose identity is approximate has no PIN and so no analysis.

``GET/PUT /api/deep-analysis/project`` keeps the builder's chosen project, their own numbers and the approval step
they marked done, per account and lot (schema v21 ``deep_projects``), behind the same gate.

Anti-scrape, not a cap: an account may open 60 different lots a day and make 10 requests a minute. A person
never meets it; a script walking the city does. The day's lots are kept in memory (one worker).
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backend import db, entitlements, inflight
from backend.auth import _auth_enabled, require_auth
from backend.rate_limit import check_saved_limit
from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deep-analysis", tags=["deep-analysis"])

_PIN = re.compile(r"^\d{14}$")
_CHICAGO = ZoneInfo("America/Chicago")

LOTS_PER_DAY = 60
REQUESTS_PER_MINUTE = 10
# One analysis per lot and language for 30 minutes, like the Profile's parts. One with a source that failed is kept
# only 5 minutes (it still names what couldn't be checked, so it is never read as "none"); without that, a lot whose
# optional source is down re-ran the 20–40 s lookup on every open.
_cache = TTLCache(ttl_seconds=1800, maxsize=256, name="deep_analysis")
_cache_partial = TTLCache(ttl_seconds=300, maxsize=128, name="deep_analysis_partial")
# account -> (Chicago day, lots opened that day)
_lots_today: dict[str, tuple[str, set[str]]] = {}


def clear_state() -> None:
    """Tests: forget the day's lots and the cache."""
    _lots_today.clear()
    _cache._store.clear()
    _cache_partial._store.clear()


def _today() -> str:
    return datetime.now(_CHICAGO).date().isoformat()


def _count_lot(user_id: str, pin: str) -> None:
    """Count a distinct lot for today; the 61st different lot in a Chicago day is a 429. A lot already opened today
    costs nothing."""
    day, lots = _lots_today.get(user_id, ("", set()))
    if day != _today():
        day, lots = _today(), set()
    lot = pin[:10]
    if lot not in lots:
        if len(lots) >= LOTS_PER_DAY:
            raise HTTPException(status_code=429, detail={"error": "deep_analysis_daily_lots"},
                                headers={"Retry-After": "3600"})
        lots.add(lot)
    _lots_today[user_id] = (day, lots)


async def _owner(user: dict) -> str:
    """With sign-in off (local development) the stand-in user gets a users row (``deep_projects`` references it)."""
    if not _auth_enabled():
        from backend.saved import _owner as saved_owner
        return await saved_owner(user)
    return user["id"]


async def _gate(user: dict, pin: str) -> None:
    if not _PIN.fullmatch(pin or ""):
        raise HTTPException(status_code=422, detail="pin must be 14 digits")
    if not await entitlements.opens_lot(user, pin):
        raise HTTPException(status_code=403, detail={"error": "deep_analysis_locked"})


# ── The analysis ─────────────────────────────────────────────────────────────────────────────────────────────

def _checklist(report: Any) -> list[dict]:
    """Before you buy: codes the page words in its own catalog (en / es-MX), each with the tab that shows it.
    ``done`` = this analysis checked it; ``todo`` = the builder's own step; ``warn`` = a todo our data flags."""
    reg = report.context.regulatory
    items: list[dict] = [
        {"key": "zoning", "state": "done", "tab": "build"},
        {"key": "overlays", "state": "done", "tab": "build"},
    ]
    if reg and reg.flood_unchecked:
        items.append({"key": "flood_unchecked", "state": "warn", "tab": None})
    elif reg and reg.in_special_flood_hazard:
        items.append({"key": "flood_sfha", "state": "warn", "tab": "build"})
    else:
        items.append({"key": "flood", "state": "done", "tab": "build"})
    if reg and reg.brownfield_unchecked:
        items.append({"key": "brownfield_unchecked", "state": "warn", "tab": None})
    elif reg and reg.brownfield_sites:
        items.append({"key": "brownfield_esa", "state": "warn", "tab": None})
    else:
        items.append({"key": "brownfield", "state": "done", "tab": None})
    open_violations = len([v for v in (report.address_violations or []) if v.get("violation_status") == "OPEN"])
    items.append({"key": "violations_open" if open_violations else "violations",
                  "state": "warn" if open_violations else "done", "tab": "history", "n": open_violations})
    items += [
        {"key": "taxes", "state": "done", "tab": "money"},
        {"key": "comps", "state": "done", "tab": "money"},
        {"key": "permits", "state": "done", "tab": "history"},
        {"key": "title", "state": "todo", "tab": None},
        {"key": "survey", "state": "todo", "tab": None},
        {"key": "utilities", "state": "todo", "tab": None},
        {"key": "soil", "state": "todo", "tab": None},
    ]
    return items


def _dump(model: Any) -> Any:
    return model.model_dump(mode="json") if model is not None and hasattr(model, "model_dump") else model


def build_payload(report: Any, *, pin: str) -> dict:
    """The tab's JSON from a ``ReportData`` built with ``rasters=False``. Pure (tests call it directly)."""
    from backend.deep_inputs import build_inputs
    from backend.report_builder import envelope_geometry

    ctx = report.context
    prop = ctx.property
    reg = ctx.regulatory
    inc = ctx.incentives
    nbr = ctx.neighborhood
    zoning = ctx.parcel_zoning
    standards = report.zoning_standards
    outline = prop.parcel_geometry if prop else None
    envelope = envelope_geometry(outline, standards, report.address) if outline and standards else None
    ward = nbr.ward if nbr else None
    open_violations = len([v for v in (report.address_violations or []) if v.get("violation_status") == "OPEN"])
    return {
        "pin": pin,
        "address": report.address,
        "lat": report.lat,
        "lon": report.lon,
        "language": report.language,
        "approximate": report.resolved_confidence == "approximate",
        "lot": {
            "land_sqft": prop.land_sqft if prop else None,
            "bldg_sqft": prop.bldg_sqft if prop else None,
            "units": prop.units if prop else None,
            "stories": prop.stories if prop else None,
            "outline": outline,
            "dimensions": (
                {k: report.parcel_dimensions.get(k) for k in ("frontage_ft", "depth_ft", "edge_count", "area_sqft")}
                if report.parcel_dimensions else None
            ),
        },
        "zoning": {
            "zone_class": zoning.zone_class if zoning else None,
            "standards": _dump(standards),
            "adjacent": report.adjacent_zoning,
        },
        "envelope": envelope,
        "development": _dump(report.development_potential),
        "unit_yield": report.unit_yield,
        "far_utilization": report.far_utilization,
        "decision": report.decision_box,
        "for": report.opportunities,
        "against": report.constraints,
        "approval": {
            "pathway": report.approval_pathway,
            "ward": _dump(ward),
            "in_planned_development": bool(reg and reg.in_planned_development),
            "landmark": bool(reg and (reg.in_landmark_district or reg.is_landmark_building or reg.in_historic_district)),
        },
        "rules": {
            "overlays": [_dump(o) for o in (reg.overlays if reg else [])],
            "flood_zone": reg.flood_zone if reg else None,
            "in_special_flood_hazard": reg.in_special_flood_hazard if reg else None,
            "flood_unchecked": bool(reg and reg.flood_unchecked),
            "in_aro_zone": bool(reg and reg.in_aro_zone),
            "in_tod_area": bool(reg and reg.in_tod_area),
            "in_adu_area": bool(reg and reg.in_adu_area),
            "on_pedestrian_street": bool(reg and reg.on_pedestrian_street),
            "brownfield_sites": len(reg.brownfield_sites) if reg else 0,
            "brownfield_unchecked": bool(reg and reg.brownfield_unchecked),
            "open_violations": open_violations,
            "unchecked": list(reg.unchecked_overlays) if reg else [],
        },
        "incentives": {
            "in_tif_district": bool(inc and inc.in_tif_district),
            "tif_name": inc.tif_name if inc else None,
            "in_opportunity_zone": bool(inc and inc.in_opportunity_zone),
            "in_enterprise_zone": bool(inc and inc.in_enterprise_zone),
        },
        "money": {
            "market_value": report.market_value,
            "effective_tax_rate": report.effective_tax_rate,
            "annual_tax": prop.estimated_annual_tax if prop else None,
            "annual_tax_estimated": bool(prop and prop.tax_estimate_is_fallback),
            "tax_exempt": bool(prop and prop.tax_exempt),
            "estimated_land_value": report.estimated_land_value,
            "comp_valuation": report.comp_valuation,
        },
        "checklist": _checklist(report),
        "inputs": build_inputs(report),
        "partial_failures": report.partial_failures,
    }


async def _analysis(pin: str, language: str) -> dict:
    from backend import report_i18n

    lang = report_i18n.normalize_lang(language)
    key = (pin, lang)
    cached = _cache.get(key) or _cache_partial.get(key)
    if cached is not None:
        return cached

    async def run() -> dict:
        from backend.main import _require_chicago, _resolve_location
        from backend.report_builder import _fetch_report_data

        rl = await _resolve_location(None, None, None, pin)
        _require_chicago(rl)
        report, _, _ = await _fetch_report_data(
            rl.lat, rl.lon, rl.address, pin=rl.pin, confidence=rl.confidence, language=lang, rasters=False,
        )
        payload = build_payload(report, pin=pin)
        # A run with a failed source is kept briefly and still says what failed (Item 65: never a definitive "none").
        (_cache_partial if payload["partial_failures"] else _cache).set(key, payload)
        return payload

    return await inflight.shared(("deep_analysis",) + key, run)


@router.get("")
async def get_analysis(
    pin: str = Query(...),
    language: str = "en",
    user: dict = Depends(require_auth),
) -> dict:
    check_saved_limit(user["id"], "deep_analysis", REQUESTS_PER_MINUTE)
    await _gate(user, pin)
    _count_lot(user["id"], pin)
    return await _analysis(pin, language)


# ── The builder's project ────────────────────────────────────────────────────────────────────────────────────

class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["largest", "three_flat", "townhouses", "own"]
    units: int = Field(ge=0, le=2000)
    stories: int = Field(ge=0, le=120)
    floor_area_sqft: int = Field(ge=0, le=5_000_000)


class NumbersIn(BaseModel):
    """The builder's own numbers (every one optional: absent = the page's starting value). Bounded so a stored row
    can't carry nonsense; the page's sliders stay well inside these."""
    model_config = ConfigDict(extra="forbid")
    land_price: float | None = Field(default=None, ge=0, le=500_000_000)
    sale_price_unit: float | None = Field(default=None, ge=0, le=50_000_000)
    rent_unit_month: float | None = Field(default=None, ge=0, le=100_000)
    build_cost_sqft: float | None = Field(default=None, ge=0, le=10_000)
    soft_cost_pct: float | None = Field(default=None, ge=0, le=1)
    loan_to_cost: float | None = Field(default=None, ge=0, le=1)
    loan_rate: float | None = Field(default=None, ge=0, le=0.5)
    build_months: float | None = Field(default=None, ge=0, le=120)
    selling_pct: float | None = Field(default=None, ge=0, le=0.5)
    profit_on_cost: float | None = Field(default=None, ge=0, le=2)
    vacancy_pct: float | None = Field(default=None, ge=0, le=1)
    opex_pct: float | None = Field(default=None, ge=0, le=1)
    cap_rate: float | None = Field(default=None, ge=0, le=0.5)
    target_yield: float | None = Field(default=None, ge=0, le=0.5)
    tax_rate: float | None = Field(default=None, ge=0, le=0.2)


class OwnIn(BaseModel):
    """One of the builder's own projects on this lot (a changed copy of a ready-made one)."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9]{1,12}$")
    units: int = Field(ge=0, le=2000)
    stories: int = Field(ge=0, le=120)
    floor_area_sqft: int = Field(ge=0, le=5_000_000)


class PriceIn(BaseModel):
    """A card's own sale price or rent: they depend on its unit size, so each project keeps its own."""
    model_config = ConfigDict(extra="forbid")
    sale_price_unit: float | None = Field(default=None, ge=0, le=50_000_000)
    rent_unit_month: float | None = Field(default=None, ge=0, le=100_000)


CARD_KEY = r"^(largest|three_flat|townhouses|own:[a-z0-9]{1,12})$"
MAX_OWN = 6


class ProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin: str = Field(pattern=r"^\d{14}$")
    project: ProjectIn | None = None
    numbers: NumbersIn | None = None
    mode: Literal["sell", "rent"] = "sell"
    step: int = Field(default=0, ge=0, le=12)
    # The builder's own projects, the card in focus, and each card's own price (Item 124, owner 2026-11-16).
    own: list[OwnIn] = Field(default_factory=list, max_length=MAX_OWN)
    focus: str | None = Field(default=None, pattern=CARD_KEY)
    prices: dict[Annotated[str, StringConstraints(pattern=CARD_KEY)], PriceIn] = Field(
        default_factory=dict, max_length=MAX_OWN + 3)


def _stored_project(raw: str | None) -> dict:
    """The stored project row's parts; a row from before the own-project list holds the project alone."""
    data = json.loads(raw) if raw else None
    if isinstance(data, dict) and "cards" in data:
        return {"project": data.get("project"), **data["cards"]}
    return {"project": data, "own": [], "focus": None, "prices": {}}


@router.get("/project")
async def get_project(pin: str = Query(...), user: dict = Depends(require_auth)) -> dict:
    check_saved_limit(user["id"], "deep_project", 60)
    await _gate(user, pin)
    uid = await _owner(user)
    cur = await db._get_db().execute(
        "SELECT project_json, numbers_json, step, updated_at FROM deep_projects WHERE user_id = ? AND pin = ?",
        (uid, pin[:10]),
    )
    row = await cur.fetchone()
    if not row:
        return {"pin": pin, "project": None, "numbers": None, "step": 0, "updated_at": None,
                "own": [], "focus": None, "prices": {}}
    return {
        "pin": pin,
        **_stored_project(row["project_json"]),
        "numbers": json.loads(row["numbers_json"]) if row["numbers_json"] else None,
        "step": row["step"],
        "updated_at": row["updated_at"],
    }


@router.put("/project")
async def put_project(body: ProjectBody, user: dict = Depends(require_auth)) -> dict:
    check_saved_limit(user["id"], "deep_project", 60)
    await _gate(user, body.pin)
    uid = await _owner(user)
    now = int(time.time() * 1000)
    conn = db._get_db()
    # Keyed by the lot (first ten digits), so every unit PIN of a condo lot reads the same project.
    await conn.execute(
        """INSERT INTO deep_projects (user_id, pin, project_json, numbers_json, step, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, pin) DO UPDATE SET
             project_json = excluded.project_json, numbers_json = excluded.numbers_json,
             step = excluded.step, updated_at = excluded.updated_at""",
        (uid, body.pin[:10],
         json.dumps({
             "project": body.project.model_dump() if body.project else None,
             "cards": {"own": [o.model_dump() for o in body.own], "focus": body.focus,
                       "prices": {k: v.model_dump(exclude_none=True) for k, v in body.prices.items()}},
         }),
         json.dumps({**body.numbers.model_dump(exclude_none=True), "mode": body.mode}) if body.numbers else json.dumps({"mode": body.mode}),
         body.step, now),
    )
    await conn.commit()
    return {"ok": True, "updated_at": now}
