import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import get_settings
from backend.models import (
    BusinessSummary,
    CodeChunk,
    ContextObject,
    CrimeSummary,
    IncentivesSummary,
    NeighborhoodSummary,
    PermitSummary,
    PropertySummary,
    RegulatorySummary,
    RetrievalPlan,
    ThreeOneOneSummary,
    ViolationSummary,
    ZoningSummary,
)


def _crime_summary(rows: list[dict[str, Any]]) -> CrimeSummary | None:
    if not rows:
        return None
    settings = get_settings()
    by_type: dict[str, int] = {}
    arrests = 0
    total = 0
    for row in rows:
        count = int(row.get("count", 0))
        total += count
        arrests += int(row.get("arrests", 0))
        by_type[row.get("primary_type", "UNKNOWN")] = count
    top = dict(sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)[:settings.top_crime_types])
    return CrimeSummary(
        total=total,
        arrest_rate=round(arrests / total, 3) if total else 0.0,
        by_type=top,
        capped=len(rows) >= settings.limit_crime,
    )


def _three11_summary(
    rows: list[dict[str, Any]],
    oldest_row: list[dict[str, Any]] | None = None,
) -> ThreeOneOneSummary | None:
    if not rows:
        return None
    settings = get_settings()
    deps: Counter[str] = Counter()
    types: Counter[str] = Counter()
    total = 0
    for row in rows:
        sr_type = row.get("sr_type", "")
        if sr_type == "Open - Dup":
            continue
        count = int(row.get("count", 0))
        total += count
        deps[row.get("owner_department", "Unknown")] += count
        types[sr_type] += count

    oldest_days: int | None = None
    if oldest_row:
        created = oldest_row[0].get("created_date")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                oldest_days = (datetime.now(timezone.utc) - dt).days
            except ValueError:
                oldest_days = None

    return ThreeOneOneSummary(
        total=total,
        oldest_open_days=oldest_days,
        by_department=dict(deps.most_common(settings.top_311_depts)),
        top_types=[t for t, _ in types.most_common(settings.top_311_types)],
        capped=len(rows) >= settings.limit_311,
    )


def _normalize_permit_type(raw: str) -> str:
    upper = (raw or "").upper()
    for keyword, label in [
        ("EXPRESS", "EXPRESS PERMIT"),
        ("RENOVATION", "RENOVATION/ALTERATION"),
        ("ALTERATION", "RENOVATION/ALTERATION"),
        ("SIGN", "SIGNS"),
        ("NEW CONSTRUCTION", "NEW CONSTRUCTION"),
        ("WRECK", "WRECKING/DEMOLITION"),
        ("DEMOLITION", "WRECKING/DEMOLITION"),
        ("ELEVATOR", "ELEVATOR EQUIPMENT"),
        ("REINSTATE", "REINSTATE REVOKED PMT"),
        ("EASY PERMIT", "EASY PERMIT PROCESS"),
    ]:
        if keyword in upper:
            return label
    return re.sub(r"^PERMIT\s*[-–—]\s*", "", upper).strip() or "OTHER"


def _permit_summary(rows: list[dict[str, Any]]) -> PermitSummary | None:
    if not rows:
        return None
    settings = get_settings()
    descs: Counter[str] = Counter()
    types: Counter[str] = Counter()
    cost_total = 0.0
    for row in rows:
        desc = (row.get("work_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
        ptype = _normalize_permit_type(row.get("permit_type", ""))
        types[ptype] += 1
        try:
            cost_total += float(row.get("reported_cost") or row.get("estimated_cost") or 0)
        except (TypeError, ValueError):
            pass
    return PermitSummary(
        total=len(rows),
        total_estimated_cost=round(cost_total, 2),
        by_type=dict(types.most_common()),
        top_work_descriptions=[d for d, _ in descs.most_common(settings.top_permits)],
        capped=len(rows) >= settings.limit_permits,
    )


_VIOLATION_CATEGORIES = [
    (["ELEVA"], "Elevator/Escalator"),
    (["EXTERIOR WALL", "EAVES", "LINTELS", "WINDOW SILLS", "PARAPET", "CHIMNEY", "EXTERIOR DOOR", "EXTERIOR STAIR"], "Exterior Structure"),
    (["INTERIOR WALL", "CEILING", "INTERIOR STAIR", "FLOOR"], "Interior Structure"),
    (["PORCH"], "Porch/Deck"),
    (["ROOF"], "Roof"),
    (["FENCE"], "Fencing"),
    (["GARAGE", "SHED"], "Garage/Shed"),
    (["WINDOW", "SCREEN", "PLEXGLAS"], "Windows/Screens"),
    (["SMOKE DETECT", "CARB MONOX", "FIRE EXT"], "Fire Safety"),
    (["OBSTRUCTION", "EXIT WAY"], "Egress/Safety"),
    (["NUISANCE", "WEED", "DEBRIS", "EXCESSIVE"], "Nuisance/Cleanup"),
    (["MICE", "RODENT"], "Pest Control"),
    (["PERMIT", "PLANS", "CONTRACTOR", "LICENSED"], "Permits/Contractor"),
    (["INSPECT", "REINSPECT", "ARRANGE"], "Inspection Required"),
    (["PLUMB"], "Plumbing"),
    (["HEAT"], "Heating"),
]


def _categorize_violation(desc: str) -> str:
    upper = (desc or "").upper()
    for keywords, category in _VIOLATION_CATEGORIES:
        for kw in keywords:
            if kw in upper:
                return category
    return "Other"


def _violation_summary(rows: list[dict[str, Any]]) -> ViolationSummary | None:
    if not rows:
        return None
    settings = get_settings()
    descs: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    open_count = 0
    for row in rows:
        desc = (row.get("violation_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
            categories[_categorize_violation(desc)] += 1
        if (row.get("violation_status") or "").upper() == "OPEN":
            open_count += 1
    return ViolationSummary(
        total=len(rows),
        open_count=open_count,
        by_category=dict(categories.most_common()),
        top_descriptions=[d for d, _ in descs.most_common(settings.top_violations)],
        capped=len(rows) >= settings.limit_violations,
    )


def _business_summary(rows: list[dict[str, Any]]) -> BusinessSummary | None:
    if not rows:
        return None
    settings = get_settings()
    activities: Counter[str] = Counter()
    license_types: Counter[str] = Counter()
    for row in rows:
        activity = (row.get("business_activity") or "").strip()
        if activity:
            primary = activity.split("|")[0].strip()
            activities[primary] += 1
        license_desc = (row.get("license_description") or "").strip()
        if license_desc:
            license_types[license_desc] += 1
    return BusinessSummary(
        total=len(rows),
        by_license_type=dict(license_types.most_common(settings.top_businesses * 2)),
        top_activities=[a for a, _ in activities.most_common(settings.top_businesses)],
        capped=len(rows) >= settings.limit_business,
    )


def assemble_context(
    *,
    plan: RetrievalPlan,
    crime_rows: list[dict[str, Any]] | None = None,
    three11_rows: list[dict[str, Any]] | None = None,
    three11_oldest: list[dict[str, Any]] | None = None,
    permit_rows: list[dict[str, Any]] | None = None,
    violation_rows: list[dict[str, Any]] | None = None,
    business_rows: list[dict[str, Any]] | None = None,
    code_chunks: list[CodeChunk] | None = None,
    zoning_info: dict[str, Any] | None = None,
    regulatory_summary: RegulatorySummary | None = None,
    property_summary: PropertySummary | None = None,
    incentives_summary: IncentivesSummary | None = None,
    neighborhood_summary: NeighborhoodSummary | None = None,
) -> ContextObject:
    settings = get_settings()

    crime = _crime_summary(crime_rows or []) if crime_rows is not None else None
    three11 = _three11_summary(three11_rows or [], three11_oldest) if three11_rows is not None else None
    permits = _permit_summary(permit_rows or []) if permit_rows is not None else None
    violations = _violation_summary(violation_rows or []) if violation_rows is not None else None
    businesses = _business_summary(business_rows or []) if business_rows is not None else None
    chunks = sorted(code_chunks or [], key=lambda c: c.score, reverse=True)[:settings.top_chunks]

    data_as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lag_note = None
    if crime is not None:
        lag = settings.crime_lag_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lag)).strftime("%Y-%m-%d")
        lag_note = f"Crime data excludes the most recent {lag} days (as of {cutoff})."

    parcel_zoning = None
    if zoning_info and zoning_info.get("zone_class"):
        parcel_zoning = ZoningSummary(
            zone_class=zoning_info["zone_class"],
            zone_type=zoning_info.get("zone_type"),
            ordinance_num=zoning_info.get("ordinance_num"),
        )

    return ContextObject(
        community_area=plan.location.resolved_community_area,
        community_area_name=plan.location.resolved_community_area_name,
        resolved_address=plan.location.resolved_address,
        data_as_of=data_as_of,
        data_lag_note=lag_note,
        crime_last_90d=crime,
        open_311_requests=three11,
        permits=permits,
        violations=violations,
        businesses=businesses,
        code_chunks=chunks,
        parcel_zoning=parcel_zoning,
        regulatory=regulatory_summary,
        property=property_summary,
        incentives=incentives_summary,
        neighborhood=neighborhood_summary,
        requires_disclaimer=plan.requires_disclaimer,
    )
