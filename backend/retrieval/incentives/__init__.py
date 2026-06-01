"""Incentives domain orchestrator.

Checks TIF district membership, Enterprise Zone membership, and
Opportunity Zone eligibility. If the parcel is in a TIF, fetches
the district's financial reports as a conditional follow-up.
"""

import asyncio
import logging

import httpx

from backend.models import IncentivesSummary
from backend.retrieval.incentives.enterprise_zones import check_enterprise_zone
from backend.retrieval.incentives.opportunity_zones import (
    check_opportunity_zone,
    resolve_census_tract,
)
from backend.retrieval.incentives.tif import check_tif, fetch_tif_financials

log = logging.getLogger(__name__)


async def incentives_domain(
    lat: float,
    lon: float,
    *,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> IncentivesSummary:
    """Fetch all incentive zone data for a point."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        # Phase A: parallel boundary checks + tract resolution
        tif_task = check_tif(lat, lon, client=client)
        ez_task = check_enterprise_zone(lat, lon, client=client)
        tract_task = resolve_census_tract(lat, lon, client=client)

        phase_a = await asyncio.gather(
            tif_task, ez_task, tract_task, return_exceptions=True,
        )

        tif_result = phase_a[0] if not isinstance(phase_a[0], Exception) else None
        ez_result = phase_a[1] if not isinstance(phase_a[1], Exception) else None
        tract_fips = phase_a[2] if not isinstance(phase_a[2], Exception) else None

        if isinstance(phase_a[0], Exception):
            log.warning("TIF boundary check failed: %s", phase_a[0])
        if isinstance(phase_a[1], Exception):
            log.warning("Enterprise Zone check failed: %s", phase_a[1])
        if isinstance(phase_a[2], Exception):
            log.warning("Census tract resolution failed: %s", phase_a[2])

        # Phase B: conditional follow-up queries
        phase_b_tasks: dict[str, asyncio.Task] = {}

        skip_financials = workflow in ("business_launch",)
        if tif_result and tif_result.get("tif_name") and not skip_financials:
            phase_b_tasks["financials"] = asyncio.create_task(
                fetch_tif_financials(tif_result["tif_name"], client=client)
            )

        if tract_fips:
            phase_b_tasks["oz"] = asyncio.create_task(
                check_opportunity_zone(tract_fips, client=client)
            )

        phase_b_results: dict[str, object] = {}
        if phase_b_tasks:
            done = await asyncio.gather(*phase_b_tasks.values(), return_exceptions=True)
            for key, value in zip(phase_b_tasks.keys(), done):
                if isinstance(value, Exception):
                    log.warning("Incentives phase B %s failed: %s", key, value)
                    phase_b_results[key] = None
                else:
                    phase_b_results[key] = value

        return _build_summary(
            tif_result, ez_result, tract_fips,
            phase_b_results.get("financials"),
            phase_b_results.get("oz"),
        )
    finally:
        if owns:
            await client.aclose()


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _build_summary(
    tif_result: dict | None,
    ez_result: dict | None,
    tract_fips: str | None,
    tif_financials: list[dict] | None,
    oz_result: dict | None,
) -> IncentivesSummary:
    in_tif = tif_result is not None
    tif_name = tif_result["tif_name"] if tif_result else None

    tif_year_start = None
    tif_end_year = None
    if tif_result:
        props = tif_result.get("properties", {})
        tif_year_start = _safe_int(
            props.get("start_year") or props.get("year")
        )
        tif_end_year = _safe_int(props.get("end_year"))

    tif_total_revenue = None
    tif_total_expenditure = None
    financials_list: list[dict] = []
    if tif_financials:
        financials_list = tif_financials
        for record in tif_financials:
            rev = _safe_float(record.get("revenue") or record.get("property_tax_extraction"))
            exp = _safe_float(record.get("expenditure") or record.get("cumulative_expenditure"))
            if rev is not None and tif_total_revenue is None:
                tif_total_revenue = rev
            if exp is not None and tif_total_expenditure is None:
                tif_total_expenditure = exp

    in_oz = oz_result is not None and oz_result.get("designated", False)
    oz_tract = oz_result.get("tract") if oz_result else None

    in_ez = ez_result is not None
    ez_name = ez_result.get("zone_name") if ez_result else None

    return IncentivesSummary(
        in_tif_district=in_tif,
        tif_name=tif_name,
        tif_year_start=tif_year_start,
        tif_end_year=tif_end_year,
        tif_total_revenue=tif_total_revenue,
        tif_total_expenditure=tif_total_expenditure,
        tif_financials=financials_list,
        in_opportunity_zone=in_oz,
        oz_tract=oz_tract,
        in_enterprise_zone=in_ez,
        enterprise_zone_name=ez_name,
        census_tract=tract_fips,
    )
