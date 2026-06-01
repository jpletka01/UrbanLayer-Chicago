"""Property domain orchestrator.

Looks up the Cook County parcel at a lat/lon to get the PIN14,
then fetches CCAO characteristics, assessments, and sales in parallel.
"""

import asyncio
import logging

import httpx

from backend.models import AssessmentRecord, PropertySummary, SaleRecord
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

        results = await asyncio.gather(
            get_characteristics(pin14, client=client),
            get_assessments(pin14, client=client),
            get_sales(pin14, client=client),
            return_exceptions=True,
        )

        chars = results[0] if not isinstance(results[0], Exception) else None
        assessments = results[1] if not isinstance(results[1], Exception) else []
        sales = results[2] if not isinstance(results[2], Exception) else []

        if isinstance(results[0], Exception):
            log.warning("CCAO characteristics failed: %s", results[0])
        if isinstance(results[1], Exception):
            log.warning("CCAO assessments failed: %s", results[1])
        if isinstance(results[2], Exception):
            log.warning("CCAO sales failed: %s", results[2])

        return _build_summary(parcel, chars, assessments, sales)
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

    if chars:
        bldg_sqft = _safe_int(chars.get("char_bldg_sf")) or bldg_sqft
        land_sqft = _safe_int(chars.get("char_land_sf")) or land_sqft
        stories = _safe_int(chars.get("char_ncu"))
        units = _safe_int(chars.get("char_units"))
        rooms = _safe_int(chars.get("char_rooms"))
        bedrooms = _safe_int(chars.get("char_beds"))
        full_baths = _safe_int(chars.get("char_fbath"))
        half_baths = _safe_int(chars.get("char_hbath"))
        bldg_age = _safe_int(chars.get("char_age"))
        bldg_class_description = chars.get("char_class_description")

    assessment_history = []
    total_assessed_value = None
    for row in assessments:
        rec = AssessmentRecord(
            year=_safe_int(row.get("tax_year")),
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
        total_assessed_value=total_assessed_value,
        assessment_history=assessment_history,
        sales_history=sales_history,
    )
