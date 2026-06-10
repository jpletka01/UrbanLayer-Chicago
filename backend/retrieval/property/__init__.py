"""Property domain orchestrator.

Looks up the Cook County parcel at a lat/lon to get the PIN14,
then fetches CCAO characteristics, assessments, and sales in parallel.
"""

import asyncio
import logging

import httpx

import datetime

from backend.config import get_settings
from backend.models import AssessmentRecord, PropertySummary, SaleRecord, TaxLineItem
from backend.retrieval.property.assessments import get_assessments
from backend.retrieval.property.characteristics import get_characteristics
from backend.retrieval.property.parcels import lookup_parcel
from backend.retrieval.property.sales import get_sales

log = logging.getLogger(__name__)


async def property_domain(
    lat: float,
    lon: float,
    *,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> PropertySummary | None:
    """Fetch all property data for a point.

    Step 1: Cook County GIS parcel lookup (lat/lon -> PIN14)
    Step 2: CCAO characteristics, assessments, sales in parallel (by PIN)
    """
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        parcel = await lookup_parcel(lat, lon, client=client)
        if parcel is None:
            log.info("No parcel found at (%s, %s)", lat, lon)
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
        else:
            data_gaps.append("property tax estimate")

        return _build_summary(parcel, chars, assessments, sales, tax_result,
                              data_gaps=data_gaps)
    finally:
        if owns:
            await client.aclose()


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


def _build_summary(
    parcel: dict,
    chars: dict | None,
    assessments: list[dict],
    sales: list[dict],
    tax_result: dict | None = None,
    *,
    data_gaps: list[str] | None = None,
) -> PropertySummary:
    pin14 = parcel["pin14"]
    address = parcel.get("address")
    bldg_class = parcel.get("bldg_class")
    bldg_sqft = _safe_int(parcel.get("bldg_sqft"))
    land_sqft = _safe_int(parcel.get("land_sqft"))

    bldg_class_description = None
    stories = None
    units = None
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
        bldg_sqft = _safe_int(chars.get("char_bldg_sf")) or bldg_sqft
        land_sqft = _safe_int(chars.get("char_land_sf")) or land_sqft
        stories = _safe_int(chars.get("char_ncu"))
        units = _safe_int(chars.get("char_apts"))
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
    if tax_result:
        estimated_annual_tax = tax_result.get("tax_bill_total")
        tax_code = tax_result.get("tax_code")
        for item in tax_result.get("line_items", []):
            tax_breakdown.append(TaxLineItem(
                agency=item["agency"],
                rate=item["rate"],
                amount=item["amount"],
            ))

    return PropertySummary(
        pin14=pin14,
        address=address,
        bldg_class=bldg_class,
        bldg_class_description=bldg_class_description,
        bldg_sqft=bldg_sqft,
        land_sqft=land_sqft,
        stories=stories,
        units=units,
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
        assessment_history=assessment_history,
        sales_history=sales_history,
        parcel_geometry=parcel.get("geometry"),
        data_gaps=data_gaps or [],
    )
