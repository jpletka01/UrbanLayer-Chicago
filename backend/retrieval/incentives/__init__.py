"""Incentives domain orchestrator.

Checks TIF district membership, Enterprise Zone membership, and
Opportunity Zone eligibility. If the parcel is in a TIF, fetches
the district's financial reports as a conditional follow-up.
"""

import asyncio
import logging

import httpx

from backend.timing import timed
from backend.data_health.failures import INCENTIVE_GAPS
from backend.models import IncentivesSummary
from backend.retrieval.incentives.enterprise_zones import check_enterprise_zone
from backend.retrieval.incentives.grant_programs import grant_programs_by_community_area
from backend.retrieval.geo import resolve_census_tract
from backend.retrieval.incentives.lihtc import check_qct
from backend.retrieval.incentives.nmtc import check_nmtc
from backend.retrieval.incentives.opportunity_zones import check_opportunity_zone
from backend.retrieval.incentives.tif import (
    check_tif,
    fetch_tif_financials,
    fetch_tif_fund_analysis,
    tif_districts_by_community_area,
    _parse_year,
)

log = logging.getLogger(__name__)


async def incentives_domain(
    lat: float | None = None,
    lon: float | None = None,
    *,
    ca: int | None = None,
    ca_name: str | None = None,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> IncentivesSummary:
    """Fetch all incentive zone data for a point or community area."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        has_coords = lat is not None and lon is not None

        if has_coords:
            return await _incentives_by_point(
                lat, lon, ca_name=ca_name, workflow=workflow, client=client,
            )

        if ca is not None:
            return await _incentives_by_community_area(
                ca, ca_name=ca_name, client=client,
            )

        return IncentivesSummary()
    finally:
        if owns:
            await client.aclose()


async def _incentives_by_point(
    lat: float,
    lon: float,
    *,
    ca_name: str | None = None,
    workflow: str = "general",
    client: httpx.AsyncClient,
) -> IncentivesSummary:
    """Full point-based incentive lookup (TIF + EZ + OZ + QCT + NMTC + grants).

    Every program that failed is recorded in ``unchecked`` (and as a ``data_gaps`` label), so it reads
    "not checked" instead of "not in one"; a failed tract lookup leaves QCT and NMTC unchecked
    (decision Item 65). OZ is checked by the point, not the tract (see ``opportunity_zones``).
    """
    phase_a_tasks = {
        "tif": check_tif(lat, lon, client=client),
        "ez": check_enterprise_zone(lat, lon, client=client),
        "tract": resolve_census_tract(lat, lon, client=client),
        "oz": check_opportunity_zone(lat=lat, lon=lon, client=client),
    }
    if ca_name:
        phase_a_tasks["grants"] = grant_programs_by_community_area(ca_name, client=client)

    done_a = await asyncio.gather(
        *(timed(f"incentives.{k}", c) for k, c in phase_a_tasks.items()), return_exceptions=True,
    )
    phase_a: dict[str, object] = {}
    failed: set[str] = set()
    for key, value in zip(phase_a_tasks.keys(), done_a):
        if isinstance(value, Exception):
            log.warning("Incentives %s lookup failed: %s", key, value)
            failed.add(key)
            phase_a[key] = None
        else:
            phase_a[key] = value

    tif_result = phase_a["tif"]
    tract_fips = phase_a["tract"]
    if "tract" in failed or not tract_fips:
        # No tract (failed, or the FCC placed the point in none): the tract-keyed programs went unasked.
        failed.update({"qct", "nmtc"})

    phase_b_tasks: dict[str, asyncio.Task] = {}

    skip_financials = workflow in ("business_launch",)
    if tif_result and tif_result.get("tif_name") and not skip_financials:
        phase_b_tasks["financials"] = asyncio.create_task(timed(
            "incentives.financials", fetch_tif_financials(tif_result["tif_name"], client=client),
        ))
        phase_b_tasks["fund_analysis"] = asyncio.create_task(timed(
            "incentives.fund_analysis", fetch_tif_fund_analysis(tif_result["tif_name"], client=client),
        ))

    if tract_fips:
        phase_b_tasks["qct"] = asyncio.create_task(timed(
            "incentives.qct", check_qct(tract_fips, client=client),
        ))
        phase_b_tasks["nmtc"] = asyncio.create_task(timed(
            "incentives.nmtc", check_nmtc(tract_fips, client=client),
        ))

    phase_b_results: dict[str, object] = {}
    if phase_b_tasks:
        done = await asyncio.gather(*phase_b_tasks.values(), return_exceptions=True)
        for key, value in zip(phase_b_tasks.keys(), done):
            if isinstance(value, Exception):
                log.warning("Incentives phase B %s failed: %s", key, value)
                failed.add(key)
                phase_b_results[key] = None
            else:
                phase_b_results[key] = value

    summary = _build_summary(
        tif_result, phase_a["ez"], tract_fips,
        phase_b_results.get("financials"),
        phase_a["oz"],
        fund_analysis=phase_b_results.get("fund_analysis"),
        grant_data=phase_a.get("grants"),
        qct_result=phase_b_results.get("qct"),
        nmtc_result=phase_b_results.get("nmtc"),
    )
    _mark_unchecked(summary, failed)
    return summary


def _mark_unchecked(summary: IncentivesSummary, failed: set[str]) -> None:
    """Record the programs that weren't checked, in ``INCENTIVE_GAPS`` order."""
    programs = [k for k in INCENTIVE_GAPS if k not in ("tif_finances",) and k in failed]
    summary.unchecked = programs
    summary.enterprise_zone_unchecked = "ez" in failed
    gaps = list(programs)
    if failed & {"financials", "fund_analysis"}:
        gaps.append("tif_finances")
    summary.data_gaps = [INCENTIVE_GAPS[k] for k in gaps]


async def _incentives_by_community_area(
    ca: int,
    *,
    ca_name: str | None = None,
    client: httpx.AsyncClient,
) -> IncentivesSummary:
    """Neighborhood-level lookup: list TIF districts covering the community area."""
    tif_failed = False
    try:
        tif_list = await tif_districts_by_community_area(ca, client=client)
    except Exception as exc:
        log.warning("TIF community area lookup failed: %s", exc)
        tif_list = []
        tif_failed = True

    grant_data = None
    if ca_name:
        try:
            grant_data = await grant_programs_by_community_area(ca_name, client=client)
        except Exception as exc:
            log.warning("Grant programs lookup failed: %s", exc)

    if tif_list:
        fund_results = await asyncio.gather(
            *(fetch_tif_fund_analysis(d["tif_name"], client=client) for d in tif_list),
            return_exceptions=True,
        )
        for district, fund_data in zip(tif_list, fund_results):
            if isinstance(fund_data, Exception) or not fund_data:
                continue
            latest = fund_data[0]
            district["property_tax_revenue"] = _safe_float(
                latest.get("property_tax_increment_current")
            )
            district["fund_balance"] = _safe_float(latest.get("fund_balance"))
            district["total_expenditure"] = _safe_float(
                latest.get("total_expenditure")
            )
            district["report_year"] = latest.get("report_year")

    from backend.assembler import _grant_program_summary
    grants_summary = _grant_program_summary(grant_data) if grant_data else None

    summary = IncentivesSummary(
        in_tif_district=len(tif_list) > 0,
        tif_districts_in_area=tif_list if tif_list else None,
        grant_programs=grants_summary,
    )
    if tif_failed:
        _mark_unchecked(summary, {"tif"})
    return summary


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
    *,
    fund_analysis: list[dict] | None = None,
    grant_data: dict | None = None,
    qct_result: dict | None = None,
    nmtc_result: dict | None = None,
) -> IncentivesSummary:
    in_tif = tif_result is not None
    tif_name = tif_result["tif_name"] if tif_result else None

    tif_year_start = None
    tif_end_year = None
    if tif_result:
        props = tif_result.get("properties", {})
        tif_year_start = (
            _parse_year(props.get("approval_d"))
            or _safe_int(props.get("start_year") or props.get("year"))
        )
        tif_end_year = (
            _parse_year(props.get("expiration"))
            or _safe_int(props.get("end_year"))
        )

    tif_property_tax_revenue = None
    tif_cumulative_revenue = None
    tif_fund_balance = None
    tif_annual_expenditure = None
    tif_fund_history: list[dict] = []

    if fund_analysis:
        latest = fund_analysis[0]
        tif_property_tax_revenue = _safe_float(
            latest.get("property_tax_increment_current")
        )
        tif_cumulative_revenue = _safe_float(
            latest.get("property_tax_increment_cumulative")
        )
        tif_fund_balance = _safe_float(latest.get("fund_balance"))
        tif_annual_expenditure = _safe_float(latest.get("total_expenditure"))

        for row in fund_analysis:
            tif_fund_history.append({
                "year": row.get("report_year"),
                "revenue": _safe_float(row.get("property_tax_increment_current")),
                "expenditure": _safe_float(row.get("total_expenditure")),
                "fund_balance": _safe_float(row.get("fund_balance")),
                "net_income": _safe_float(row.get("net_income")),
            })

    tif_total_revenue = tif_property_tax_revenue
    tif_total_expenditure = tif_annual_expenditure

    financials_list: list[dict] = tif_financials or []

    in_oz = oz_result is not None and oz_result.get("designated", False)
    oz_tract = oz_result.get("tract") if oz_result else None

    in_ez = ez_result is not None
    ez_name = ez_result.get("zone_name") if ez_result else None

    in_qct = qct_result is not None and qct_result.get("designated", False)
    qct_tract = qct_result.get("tract") if qct_result else None

    in_nmtc = nmtc_result is not None and nmtc_result.get("qualifying", False)
    nmtc_tract = nmtc_result.get("tract") if nmtc_result else None
    nmtc_severe = nmtc_result.get("severe_distress", False) if nmtc_result else False
    nmtc_pov = nmtc_result.get("poverty_rate") if nmtc_result else None

    return IncentivesSummary(
        in_tif_district=in_tif,
        tif_name=tif_name,
        tif_year_start=tif_year_start,
        tif_end_year=tif_end_year,
        tif_total_revenue=tif_total_revenue,
        tif_total_expenditure=tif_total_expenditure,
        tif_property_tax_revenue=tif_property_tax_revenue,
        tif_cumulative_revenue=tif_cumulative_revenue,
        tif_fund_balance=tif_fund_balance,
        tif_annual_expenditure=tif_annual_expenditure,
        tif_fund_history=tif_fund_history,
        tif_financials=financials_list,
        in_opportunity_zone=in_oz,
        oz_tract=oz_tract,
        in_enterprise_zone=in_ez,
        enterprise_zone_name=ez_name,
        in_qct=in_qct,
        qct_tract=qct_tract,
        in_nmtc=in_nmtc,
        nmtc_tract=nmtc_tract,
        nmtc_severe_distress=nmtc_severe,
        nmtc_poverty_rate=nmtc_pov,
        census_tract=tract_fips,
        grant_programs=_build_grant_summary(grant_data),
    )


def _build_grant_summary(grant_data: dict | None):
    if not grant_data:
        return None
    from backend.assembler import _grant_program_summary
    return _grant_program_summary(grant_data)
