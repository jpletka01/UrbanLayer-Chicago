"""Property domain orchestrator.

Looks up the Cook County parcel at a lat/lon to get the PIN14,
then fetches CCAO characteristics, assessments, and sales in parallel.
"""

import asyncio
import logging
from typing import Any

import httpx

import datetime

from backend.config import get_settings
from backend.models import (
    AssessmentRecord,
    PropertySummary,
    SaleRecord,
    TaxExemption,
    TaxLineItem,
)
from backend.retrieval.property.assessments import get_assessments
from backend.retrieval.property.characteristics import get_characteristics
from backend.retrieval.property.parcels import lookup_parcel, lookup_parcel_by_pin
from backend.retrieval.property.sales import get_sales

log = logging.getLogger(__name__)


async def property_domain(
    lat: float,
    lon: float,
    *,
    pin: str | None = None,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> PropertySummary | None:
    """Fetch all property data for a point.

    Step 1: Resolve the parcel. When an authoritative PIN is supplied, resolve
            by PIN directly (pure Socrata, GIS-independent). Otherwise fall back
            to the coordinate parcel lookup (GIS PIP → Socrata nearest-centroid).
    Step 2: CCAO characteristics, assessments, sales in parallel (by PIN)
    """
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        if pin:
            parcel = await lookup_parcel_by_pin(pin, client=client)
            if parcel is None:
                # PIN row missing/unavailable — degrade to the coordinate path.
                parcel = await lookup_parcel(lat, lon, client=client)
        else:
            parcel = await lookup_parcel(lat, lon, client=client)
        if parcel is None:
            log.info("No parcel found at (%s, %s) pin=%s", lat, lon, pin)
            return None

        pin14 = parcel["pin14"]

        skip_history = workflow in ("development_feasibility",)

        coros = [get_characteristics(pin14, client=client)]
        if not skip_history:
            coros.append(get_assessments(pin14, client=client))
            coros.append(get_sales(pin14, client=client))

        settings = get_settings()
        if settings.ptaxsim_enabled:
            from backend.retrieval.property.tax_estimate import estimate_tax
            tax_year = datetime.date.today().year - 1
            coros.append(estimate_tax(tax_year, pin14))

        # Geometry-derived land area + parcel outline from the local PTAXSIM
        # polygon table — the only all-class land source (CCAO chars is
        # residential-only; GIS is flaky and absent on the PIN-keyed path).
        from backend.retrieval.property.parcel_geometry import get_parcel_geometry_facts
        coros.append(get_parcel_geometry_facts(pin14))

        results = await asyncio.gather(*coros, return_exceptions=True)

        data_gaps: list[str] = []

        idx = 0
        chars = results[idx] if not isinstance(results[idx], Exception) else None
        if isinstance(results[idx], Exception):
            log.warning("CCAO characteristics failed: %s", results[idx])
            data_gaps.append("property characteristics")
        idx += 1

        assessments: list[dict] = []
        sales: list[dict] = []
        if not skip_history:
            assessments = results[idx] if not isinstance(results[idx], Exception) else []
            if isinstance(results[idx], Exception):
                log.warning("CCAO assessments failed: %s", results[idx])
                data_gaps.append("property assessments")
            elif not assessments:
                data_gaps.append("property assessments")
            idx += 1
            sales = results[idx] if not isinstance(results[idx], Exception) else []
            if isinstance(results[idx], Exception):
                log.warning("CCAO sales failed: %s", results[idx])
            idx += 1

        tax_result = None
        if settings.ptaxsim_enabled:
            tax_result = results[idx] if not isinstance(results[idx], Exception) else None
            if isinstance(results[idx], Exception):
                log.warning("PTAXSIM tax estimate failed: %s", results[idx])
                data_gaps.append("property tax estimate")
            elif tax_result is None:
                data_gaps.append("property tax estimate")
            idx += 1
        else:
            data_gaps.append("property tax estimate")

        geometry_facts = results[idx] if not isinstance(results[idx], Exception) else None
        if isinstance(results[idx], Exception):
            log.warning("Parcel geometry facts failed: %s", results[idx])

        building_fallbacks = await _fetch_building_fallbacks(
            parcel, chars, assessments, lat, lon, client=client,
        )

        return _build_summary(parcel, chars, assessments, sales, tax_result,
                              geometry_facts=geometry_facts,
                              building_fallbacks=building_fallbacks,
                              data_gaps=data_gaps)
    finally:
        if owns:
            await client.aclose()


async def _fetch_building_fallbacks(
    parcel: dict,
    chars: dict | None,
    assessments: list[dict],
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Phase 2: building-fact fallbacks, fetched only when the primary CCAO
    characteristics left gaps (x54s-btds covers regression-class residential
    only — the 2026-07-02 benchmark measured 0% bldg facts everywhere else).

    Returns {"condo": ..., "commercial_sqft": ..., "footprint": ...} (each
    possibly None) or None when nothing was needed/fetched.
    """
    cls = str(
        parcel.get("bldg_class")
        or (assessments[0].get("class") if assessments else "")
        or ""
    ).strip().upper().replace("-", "")

    # Vacant land (class 1xx) has no building to find; skip entirely.
    if cls[:1] == "1":
        return None

    has_bldg = bool(chars and _safe_int(chars.get("char_bldg_sf")))
    has_year = bool(chars and _safe_int(chars.get("char_yrblt")))
    has_stories = bool(chars and _decode_stories(chars))
    if has_bldg and has_year and has_stories:
        return None

    from backend.retrieval.property.building_facts import (
        get_commercial_building_sqft,
        get_condo_characteristics,
        get_footprint_facts,
    )

    coros: dict[str, Any] = {}
    if chars is None:
        # x54s-covered parcels never appear in the condo/commercial datasets;
        # only bother when the primary lookup came back empty.
        coros["condo"] = get_condo_characteristics(parcel["pin14"], client=client)
        coros["commercial_sqft"] = get_commercial_building_sqft(parcel["pin14"], client=client)
    coros["footprint"] = get_footprint_facts(lat, lon, client=client)

    done = await asyncio.gather(*coros.values(), return_exceptions=True)
    fallbacks: dict[str, Any] = {}
    for key, value in zip(coros.keys(), done):
        if isinstance(value, Exception):
            log.warning("Building fallback %s failed: %s", key, value)
            fallbacks[key] = None
        else:
            fallbacks[key] = value
    return fallbacks


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# x54s-btds ships DECODED strings, not numbers (verified against the live
# dataset + column metadata 2026-07-02): `char_apts` is "Two".."Six" (apartment
# count, classes 211/212 only), `char_type_resd` is "1 Story"/"1.5 Story"/
# "2 Story"/"3 Story +"/"Split Level", `char_use` is "Single-Family"/
# "Multi-Family". `char_ncu` is the number of COMMERCIAL units — it was
# previously (wrongly) surfaced as stories.
_APTS_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

_TYPE_RESD_STORIES = {
    "1 story": 1.0,
    "1.5 story": 1.5,
    "2 story": 2.0,
    "3 story +": 3.0,
    # "Split Level" has no defensible story count -> None
}


def _decode_units(chars: dict) -> int | None:
    """Dwelling units: decoded apartment count when CCAO provides one (211/212),
    else 1 for a confirmed single-family parcel, else unknown."""
    apts = _APTS_WORDS.get(str(chars.get("char_apts") or "").strip().lower())
    if apts:
        return apts
    if str(chars.get("char_use") or "").strip().lower() == "single-family":
        return 1
    return None


def _decode_stories(chars: dict) -> float | None:
    return _TYPE_RESD_STORIES.get(str(chars.get("char_type_resd") or "").strip().lower())


def _build_summary(
    parcel: dict,
    chars: dict | None,
    assessments: list[dict],
    sales: list[dict],
    tax_result: dict | None = None,
    *,
    geometry_facts: dict | None = None,
    building_fallbacks: dict | None = None,
    data_gaps: list[str] | None = None,
) -> PropertySummary:
    pin14 = parcel["pin14"]
    address = parcel.get("address")
    bldg_class = parcel.get("bldg_class")
    bldg_sqft = _safe_int(parcel.get("bldg_sqft"))
    land_sqft = _safe_int(parcel.get("land_sqft"))
    land_sqft_source = "gis" if land_sqft else None
    bldg_sqft_source = "gis" if bldg_sqft else None

    bldg_class_description = None
    stories = None
    units = None
    commercial_units = None
    rooms = None
    bedrooms = None
    full_baths = None
    half_baths = None
    bldg_age = None
    year_built = None

    exterior_wall = None
    roof_type = None
    basement = None
    garage_size = None
    air_conditioning = None

    if chars:
        # NOTE: dataset x54s-btds column names — `char_apts` (not char_units),
        # `char_air` (not char_ac); there is no char_age or char_class_description.
        ccao_bldg = _safe_int(chars.get("char_bldg_sf"))
        if ccao_bldg:
            bldg_sqft = ccao_bldg
            bldg_sqft_source = "assessor"
        ccao_land = _safe_int(chars.get("char_land_sf"))
        if ccao_land:
            land_sqft = ccao_land
            land_sqft_source = "assessor"
        stories = _decode_stories(chars)
        units = _decode_units(chars)
        ncu = _safe_int(chars.get("char_ncu"))
        commercial_units = ncu if ncu is not None and ncu > 0 else None
        rooms = _safe_int(chars.get("char_rooms"))
        bedrooms = _safe_int(chars.get("char_beds"))
        full_baths = _safe_int(chars.get("char_fbath"))
        half_baths = _safe_int(chars.get("char_hbath"))
        year_built = _safe_int(chars.get("char_yrblt"))
        # Derive age from year built (dataset has no precomputed age column).
        if year_built:
            bldg_age = datetime.date.today().year - year_built
        exterior_wall = chars.get("char_ext_wall") or None
        roof_type = chars.get("char_roof_cnst") or None
        basement = chars.get("char_bsmt") or None
        garage_size = chars.get("char_gar1_size") or None
        air_conditioning = chars.get("char_air") or None

    assessment_history = []
    total_assessed_value = None
    for row in assessments:
        rec = AssessmentRecord(
            year=_safe_int(row.get("year")),
            land=_safe_float(row.get("mailed_land") or row.get("certified_land")),
            building=_safe_float(
                row.get("mailed_bldg") or row.get("certified_bldg")
            ),
            total=_safe_float(
                row.get("mailed_tot")
                or row.get("certified_tot")
                or row.get("board_tot")
            ),
        )
        # The CCAO's in-progress year (e.g. 2026) carries NULL value columns until
        # values are mailed, and Socrata omits NULL fields — so the latest row comes
        # back valueless (land/building/total all None). Skip it: every consumer
        # already filters null totals, but a phantom valueless record would still
        # pollute assessment_history (and the synthesizer context). See known-issues
        # "CCAO latest assessment year is VALUELESS until mailed".
        if rec.total is None and rec.land is None and rec.building is None:
            continue
        assessment_history.append(rec)
        if total_assessed_value is None and rec.total is not None:
            total_assessed_value = rec.total

    sales_history = []
    for row in sales:
        rec = SaleRecord(
            date=row.get("sale_date"),
            price=_safe_float(row.get("sale_price")),
            deed_type=row.get("deed_type"),
        )
        sales_history.append(rec)

    # Geometry-derived fill: assessor-stated area wins when present; the
    # polygon-computed area covers every class the assessor datasets don't
    # (commercial/multifamily/exempt/industrial — 0% before 2026-07-02).
    parcel_geometry = parcel.get("geometry")
    if geometry_facts:
        if not land_sqft and geometry_facts.get("land_sqft_geom"):
            land_sqft = geometry_facts["land_sqft_geom"]
            land_sqft_source = "geometry"
        if parcel_geometry is None:
            parcel_geometry = geometry_facts.get("parcel_geometry")

    # Building-fact fallbacks (condo unit chars → commercial valuation →
    # city footprints), applied ONLY into holes the assessor data left, with
    # per-field provenance so the UI/report can label non-assessor numbers.
    year_built_source = "assessor" if year_built else None
    stories_source = "assessor" if stories else None
    if building_fallbacks:
        condo = building_fallbacks.get("condo")
        if condo:
            if not bldg_sqft and condo.get("unit_sqft"):
                bldg_sqft = condo["unit_sqft"]
                bldg_sqft_source = "condo_unit"
            if not year_built and condo.get("year_built"):
                year_built = condo["year_built"]
                year_built_source = "assessor"  # CCAO condo dataset — same authority
                bldg_age = datetime.date.today().year - year_built
            if not bedrooms and condo.get("bedrooms"):
                bedrooms = condo["bedrooms"]
        if not bldg_sqft and building_fallbacks.get("commercial_sqft"):
            bldg_sqft = building_fallbacks["commercial_sqft"]
            bldg_sqft_source = "commercial_valuation"
        footprint = building_fallbacks.get("footprint")
        if footprint:
            if not bldg_sqft and footprint.get("bldg_sqft"):
                bldg_sqft = footprint["bldg_sqft"]
                bldg_sqft_source = "footprint"
            if not year_built and footprint.get("year_built"):
                year_built = footprint["year_built"]
                year_built_source = "footprint"
                bldg_age = datetime.date.today().year - year_built
            if not stories and footprint.get("stories"):
                stories = float(footprint["stories"])
                stories_source = "footprint"

    # Exempt parcels (class "EX") carry zero assessed value / tax — a real,
    # decision-relevant fact (institutional ownership), not a data gap.
    assessment_class = assessments[0].get("class") if assessments else None
    tax_exempt = any(
        (c or "").strip().upper().startswith("EX")
        for c in (bldg_class, assessment_class)
    )

    estimated_annual_tax = None
    tax_code = None
    tax_breakdown: list[TaxLineItem] = []
    tax_exemptions: list[TaxExemption] = []
    if tax_result:
        estimated_annual_tax = tax_result.get("tax_bill_total")
        tax_code = tax_result.get("tax_code")
        for item in tax_result.get("line_items", []):
            tax_breakdown.append(TaxLineItem(
                agency=item["agency"],
                rate=item["rate"],
                amount=item["amount"],
            ))
        for exe in tax_result.get("exemptions", []):
            tax_exemptions.append(TaxExemption(
                kind=exe["kind"],
                eav_reduction=exe["eav_reduction"],
            ))

    return PropertySummary(
        pin14=pin14,
        address=address,
        bldg_class=bldg_class,
        bldg_class_description=bldg_class_description,
        bldg_sqft=bldg_sqft,
        land_sqft=land_sqft,
        land_sqft_source=land_sqft_source,
        bldg_sqft_source=bldg_sqft_source,
        year_built_source=year_built_source,
        stories_source=stories_source,
        stories=stories,
        units=units,
        commercial_units=commercial_units,
        rooms=rooms,
        bedrooms=bedrooms,
        full_baths=full_baths,
        half_baths=half_baths,
        bldg_age=bldg_age,
        year_built=year_built,
        exterior_wall=exterior_wall,
        roof_type=roof_type,
        basement=basement,
        garage_size=garage_size,
        air_conditioning=air_conditioning,
        tax_exempt=tax_exempt,
        total_assessed_value=total_assessed_value,
        estimated_annual_tax=estimated_annual_tax,
        tax_code=tax_code,
        tax_breakdown=tax_breakdown,
        tax_exemptions=tax_exemptions,
        assessment_history=assessment_history,
        sales_history=sales_history,
        parcel_geometry=parcel_geometry,
        data_gaps=data_gaps or [],
    )
