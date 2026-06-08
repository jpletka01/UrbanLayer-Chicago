import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import get_settings
from backend.models import (
    Address311Summary,
    AROHousingProject,
    AROHousingSummary,
    BusinessSummary,
    CodeChunk,
    ContextObject,
    CrimeSummary,
    CrimeYoYItem,
    GrantProgramSummary,
    GrantProject,
    IncentivesSummary,
    NeighborhoodSummary,
    PermitSummary,
    PropertySummary,
    RegulatorySummary,
    RetrievalPlan,
    ThreeOneOneSummary,
    FoodInspectionDetail,
    FoodInspectionSummary,
    VacantBuildingReport,
    VacantBuildingSummary,
    ViolationSummary,
    ZoningSummary,
)


def _aro_housing_summary(rows: list[dict[str, Any]]) -> AROHousingSummary | None:
    """Build a summary from ARO housing project data."""
    if not rows:
        return None
    total_units = 0
    projects: list[AROHousingProject] = []
    for row in rows:
        units = None
        if row.get("units"):
            try:
                units = int(row["units"])
                total_units += units
            except (TypeError, ValueError):
                pass
        projects.append(AROHousingProject(
            name=(row.get("property_name") or "").strip() or "Unnamed",
            address=(row.get("address") or "").strip() or None,
            units=units,
            property_type=(row.get("property_type") or "").strip() or None,
        ))
    return AROHousingSummary(
        total_projects=len(projects),
        total_units=total_units,
        projects=projects,
    )


def _grant_program_summary(data: dict[str, Any]) -> GrantProgramSummary | None:
    """Build a summary from SBIF + NOF grant program data."""
    all_rows: list[dict] = []
    for key in ("sbif", "nof_large", "nof_small"):
        all_rows.extend(data.get(key, []))
    if not all_rows:
        return None

    by_program: dict[str, int] = {}
    total_funding = 0.0
    for row in all_rows:
        prog = row.get("_program", "Unknown")
        by_program[prog] = by_program.get(prog, 0) + 1
        amt = row.get("incentive_amount")
        if amt:
            try:
                total_funding += float(amt)
            except (TypeError, ValueError):
                pass

    recent: list[GrantProject] = []
    sorted_rows = sorted(
        all_rows,
        key=lambda r: r.get("completion_date") or "",
        reverse=True,
    )
    for row in sorted_rows[:10]:
        amt = None
        if row.get("incentive_amount"):
            try:
                amt = float(row["incentive_amount"])
            except (TypeError, ValueError):
                pass
        cost = None
        if row.get("total_project_cost"):
            try:
                cost = float(row["total_project_cost"])
            except (TypeError, ValueError):
                pass
        recent.append(GrantProject(
            name=(row.get("project_name") or "").strip() or "Unnamed",
            program=row.get("_program", "Unknown"),
            incentive_amount=amt,
            total_cost=cost,
            property_type=(row.get("property_type") or "").strip() or None,
            description=(row.get("project_description") or "").strip() or None,
            date=(row.get("completion_date") or "")[:10] or None,
        ))

    return GrantProgramSummary(
        total_projects=len(all_rows),
        total_funding=total_funding,
        by_program=by_program,
        recent_projects=recent,
    )


_TAX_INCENTIVE_CLASSES: dict[str, str] = {
    "6b": "Class 6b — Reduced assessment for industrial/commercial rehabilitation",
    "6c": "Class 6c — Reduced assessment for industrial brownfield redevelopment",
    "7a": "Class 7a — Reduced assessment for commercial/industrial in economically disadvantaged areas",
    "7b": "Class 7b — Reduced assessment for large-scale commercial/industrial projects",
    "7c": "Class 7c — Reduced assessment for long-term commercial/industrial investment",
    "8":  "Class 8 — Reduced assessment for industrial property and pollution control",
}


def _interpret_tax_class(bldg_class: str | None) -> tuple[str | None, str | None]:
    """Return (normalized_class, description) if the property class is a tax incentive."""
    if not bldg_class:
        return None, None
    code = bldg_class.strip().lower()
    for prefix, desc in _TAX_INCENTIVE_CLASSES.items():
        if code == prefix or code.startswith(prefix + "-") or code.startswith(prefix + " "):
            return prefix.upper(), desc
    return None, None


def _crime_summary(
    rows: list[dict[str, Any]],
    yoy_data: dict[str, Any] | None = None,
) -> CrimeSummary | None:
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

    yoy_items: list[CrimeYoYItem] | None = None
    yoy_period: str | None = None
    if yoy_data:
        current_map = {r["primary_type"]: int(r.get("count", 0)) for r in yoy_data.get("current", [])}
        prior_map = {r["primary_type"]: int(r.get("count", 0)) for r in yoy_data.get("prior", [])}
        all_types = set(current_map) | set(prior_map)
        items = []
        for cat in all_types:
            curr = current_map.get(cat, 0)
            prev = prior_map.get(cat, 0)
            if prev == 0:
                pct = 100 if curr > 0 else 0
            else:
                pct = round(((curr - prev) / prev) * 100)
            items.append(CrimeYoYItem(
                category=cat, current_count=curr,
                prior_year_count=prev, change_pct=pct,
            ))
        items.sort(key=lambda i: i.current_count, reverse=True)
        yoy_items = items[:settings.top_crime_types]
        yoy_period = f"{yoy_data.get('current_label', '')} vs {yoy_data.get('prior_label', '')}"

    return CrimeSummary(
        total=total,
        arrest_rate=round(arrests / total, 3) if total else 0.0,
        by_type=top,
        yoy=yoy_items,
        yoy_period=yoy_period,
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


def _permit_summary(data: dict[str, Any]) -> PermitSummary | None:
    grouped = data.get("grouped", [])
    detail = data.get("detail", [])
    if not grouped and not detail:
        return None
    settings = get_settings()

    types: dict[str, int] = {}
    cost_total = 0.0
    total = 0
    for row in grouped:
        ptype = _normalize_permit_type(row.get("permit_type", ""))
        count = int(row.get("count", 0))
        types[ptype] = types.get(ptype, 0) + count
        total += count
        try:
            cost_total += float(row.get("total_cost") or 0)
        except (TypeError, ValueError):
            pass

    descs: Counter[str] = Counter()
    contractors: Counter[str] = Counter()
    for row in detail:
        desc = (row.get("work_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
        for i in range(1, 4):
            ctype = (row.get(f"contact_{i}_type") or "").upper()
            cname = (row.get(f"contact_{i}_name") or "").strip()
            if cname and ctype in ("CONTRACTOR-GENERAL CONTRACTOR", "CONTRACTOR"):
                contractors[cname] += 1

    return PermitSummary(
        total=total,
        total_estimated_cost=round(cost_total, 2),
        by_type=dict(sorted(types.items(), key=lambda kv: kv[1], reverse=True)),
        top_work_descriptions=[d for d, _ in descs.most_common(settings.top_permits)],
        recent_contractors=[name for name, _ in contractors.most_common(5)],
        capped=False,
    )


_VIOLATION_CODE_PREFIXES: dict[str, str] = {
    "EV": "Elevator/Escalator",
    "BR": "Boiler/Mechanical",
}

_VIOLATION_CATEGORIES = [
    (["ELEVA", "ESCALAT"], "Elevator/Escalator"),
    (["BOILER", "BREECHING", "PRESSURE GAUGE", "SAFETY VALVE"], "Boiler/Mechanical"),
    (["ELECTRICAL", "WIRING", "VOLTAGE", "FIXTURE", "ELECT "], "Electrical"),
    (["EXTERIOR WALL", "EAVES", "LINTELS", "WINDOW SILLS", "PARAPET", "CHIMNEY", "EXTERIOR DOOR", "EXTERIOR STAIR", "FACADE", "BRICK", "TUCKPOINT", "MASONRY", "SIDING"], "Exterior Structure"),
    (["INTERIOR WALL", "CEILING", "INTERIOR STAIR", "FLOOR"], "Interior Structure"),
    (["PORCH", "DECK", "BALCON", "RAILING", "STEP"], "Porch/Deck"),
    (["ROOF"], "Roof"),
    (["FENCE"], "Fencing"),
    (["GARAGE", "SHED"], "Garage/Shed"),
    (["WINDOW", "SCREEN", "PLEXGLAS"], "Windows/Screens"),
    (["SMOKE DETECT", "CARB MONOX", "FIRE EXT", "FIRE ESCAPE", "FIRE ALARM"], "Fire Safety"),
    (["OBSTRUCTION", "EXIT WAY", "EGRESS", "HANDRAIL"], "Egress/Safety"),
    (["NUISANCE", "WEED", "DEBRIS", "EXCESSIVE", "REFUSE"], "Nuisance/Cleanup"),
    (["MICE", "RODENT", "PEST", "VERMIN"], "Pest Control"),
    (["PERMIT", "PLANS", "CONTRACTOR", "LICENSED"], "Permits/Contractor"),
    (["INSPECT", "REINSPECT", "ARRANGE"], "Inspection Required"),
    (["PLUMB", "DRAIN", "SEWER", "WATER SUPPLY"], "Plumbing"),
    (["HEAT", "FURNACE", "HVAC"], "Heating"),
]


def _categorize_violation(desc: str, code: str | None = None) -> str:
    if code:
        code_upper = code.strip().upper()
        for prefix, category in _VIOLATION_CODE_PREFIXES.items():
            if code_upper.startswith(prefix):
                return category
    upper = (desc or "").upper()
    for keywords, category in _VIOLATION_CATEGORIES:
        for kw in keywords:
            if kw in upper:
                return category
    return "Other"


def _violation_summary(data: dict[str, Any]) -> ViolationSummary | None:
    status_counts = data.get("status_counts", [])
    detail = data.get("detail", [])
    if not status_counts and not detail:
        return None
    settings = get_settings()

    true_total = 0
    open_count = 0
    for row in status_counts:
        count = int(row.get("count", 0))
        true_total += count
        if (row.get("violation_status") or "").upper() == "OPEN":
            open_count = count

    descs: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for row in detail:
        desc = (row.get("violation_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
            code = row.get("violation_code")
            categories[_categorize_violation(desc, code)] += 1
        if not status_counts and (row.get("violation_status") or "").upper() == "OPEN":
            open_count += 1

    return ViolationSummary(
        total=true_total if true_total else len(detail),
        open_count=open_count,
        by_category=dict(categories.most_common()),
        top_descriptions=[d for d, _ in descs.most_common(settings.top_violations)],
        capped=False,
    )


def _business_summary(data: dict[str, Any]) -> BusinessSummary | None:
    grouped = data.get("grouped", [])
    detail = data.get("detail", [])
    if not grouped and not detail:
        return None
    settings = get_settings()

    license_types: dict[str, int] = {}
    total = 0
    for row in grouped:
        desc = (row.get("license_description") or "").strip()
        count = int(row.get("count", 0))
        if desc:
            license_types[desc] = count
        total += count

    activities: Counter[str] = Counter()
    for row in detail:
        activity = (row.get("business_activity") or "").strip()
        if activity:
            primary = activity.split("|")[0].strip()
            activities[primary] += 1

    return BusinessSummary(
        total=total,
        by_license_type=dict(sorted(license_types.items(), key=lambda kv: kv[1], reverse=True)[:settings.top_businesses * 2]),
        top_activities=[a for a, _ in activities.most_common(settings.top_businesses)],
        capped=False,
    )


def _vacant_building_summary(data: dict[str, Any]) -> VacantBuildingSummary | None:
    grouped = data.get("grouped", [])
    detail = data.get("detail", [])
    if not grouped and not detail:
        return None

    by_dept: dict[str, int] = {}
    total = 0
    for row in grouped:
        dept = (row.get("issuing_department") or "").strip()
        count = int(row.get("count", 0))
        if dept:
            by_dept[dept] = count
        total += count

    recent: list[VacantBuildingReport] = []
    for row in detail[:10]:
        addr = (row.get("property_address") or "").strip()
        if not addr:
            continue
        due = None
        raw_due = row.get("current_amount_due")
        if raw_due:
            try:
                due = float(raw_due)
            except (TypeError, ValueError):
                pass
        recent.append(VacantBuildingReport(
            address=addr,
            date=row.get("issued_date", "")[:10] or None,
            violation_type=(row.get("violation_type") or "")[:200] or None,
            responsible_entity=(row.get("entity_or_person_s_") or "").strip() or None,
            amount_due=due if due and due > 0 else None,
        ))

    return VacantBuildingSummary(
        total=total,
        by_department=dict(sorted(by_dept.items(), key=lambda kv: kv[1], reverse=True)),
        recent_reports=recent,
    )


def _food_inspection_summary(data: dict[str, Any]) -> FoodInspectionSummary | None:
    by_result_rows = data.get("by_result", [])
    by_risk_rows = data.get("by_risk", [])
    detail = data.get("detail", [])
    if not by_result_rows and not by_risk_rows and not detail:
        return None

    by_result: dict[str, int] = {}
    total = 0
    for row in by_result_rows:
        res = (row.get("results") or "").strip()
        count = int(row.get("count", 0))
        if res:
            by_result[res] = count
        total += count

    by_risk: dict[str, int] = {}
    for row in by_risk_rows:
        risk = (row.get("risk") or "").strip()
        count = int(row.get("count", 0))
        if risk:
            by_risk[risk] = count

    fail_count = by_result.get("Fail", 0)
    fail_rate = round(fail_count / total * 100, 1) if total > 0 else None

    recent: list[FoodInspectionDetail] = []
    for row in detail[:10]:
        name = (row.get("dba_name") or "").strip()
        if not name:
            continue
        recent.append(FoodInspectionDetail(
            name=name,
            facility_type=(row.get("facility_type") or "").strip() or None,
            risk=(row.get("risk") or "").strip() or None,
            result=(row.get("results") or "").strip() or None,
            date=row.get("inspection_date", "")[:10] or None,
        ))

    return FoodInspectionSummary(
        total=total,
        by_result=dict(sorted(by_result.items(), key=lambda kv: kv[1], reverse=True)),
        by_risk=dict(sorted(by_risk.items(), key=lambda kv: kv[1], reverse=True)),
        fail_rate=fail_rate,
        recent_inspections=recent,
    )


def assemble_context(
    *,
    plan: RetrievalPlan,
    crime_rows: list[dict[str, Any]] | None = None,
    crime_yoy_data: dict[str, Any] | None = None,
    three11_rows: list[dict[str, Any]] | None = None,
    three11_oldest: list[dict[str, Any]] | None = None,
    permit_data: dict[str, Any] | None = None,
    violation_data: dict[str, Any] | None = None,
    business_data: dict[str, Any] | None = None,
    vacant_data: dict[str, Any] | None = None,
    food_inspection_data: dict[str, Any] | None = None,
    code_chunks: list[CodeChunk] | None = None,
    zoning_info: dict[str, Any] | None = None,
    regulatory_summary: RegulatorySummary | None = None,
    property_summary: PropertySummary | None = None,
    incentives_summary: IncentivesSummary | None = None,
    neighborhood_summary: NeighborhoodSummary | None = None,
    aro_housing_rows: list[dict[str, Any]] | None = None,
    address_311_data: dict[str, Any] | None = None,
    partial_failures: list[str] | None = None,
) -> ContextObject:
    settings = get_settings()

    crime = _crime_summary(crime_rows or [], crime_yoy_data) if crime_rows is not None else None
    three11 = _three11_summary(three11_rows or [], three11_oldest) if three11_rows is not None else None
    addr_311 = None
    if address_311_data and address_311_data.get("total", 0) > 0:
        addr_311 = Address311Summary(
            total=address_311_data["total"],
            open_count=address_311_data.get("open_count", 0),
            by_type=address_311_data.get("by_type", {}),
            high_risk_flags=address_311_data.get("high_risk_flags", []),
        )
    permits = _permit_summary(permit_data) if permit_data is not None else None
    violations = _violation_summary(violation_data) if violation_data is not None else None
    businesses = _business_summary(business_data) if business_data is not None else None
    vacant = _vacant_building_summary(vacant_data) if vacant_data is not None else None
    food = _food_inspection_summary(food_inspection_data) if food_inspection_data is not None else None
    chunks = sorted(code_chunks or [], key=lambda c: c.score, reverse=True)[:settings.top_chunks]

    data_as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lag_note = None
    lag_days = None
    lag_cutoff = None
    if crime is not None:
        lag = settings.crime_lag_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lag)).strftime("%Y-%m-%d")
        lag_note = f"Crime data excludes the most recent {lag} days (as of {cutoff})."
        lag_days = lag
        lag_cutoff = cutoff

    parcel_zoning = None
    if zoning_info and zoning_info.get("zone_class"):
        parcel_zoning = ZoningSummary(
            zone_class=zoning_info["zone_class"],
            zone_type=zoning_info.get("zone_type"),
            ordinance_num=zoning_info.get("ordinance_num"),
        )

    if aro_housing_rows:
        aro_summary = _aro_housing_summary(aro_housing_rows)
        if aro_summary:
            if regulatory_summary is None:
                regulatory_summary = RegulatorySummary()
            regulatory_summary = regulatory_summary.model_copy(update={
                "aro_housing": aro_summary,
            })

    if property_summary and property_summary.bldg_class:
        tax_class, tax_desc = _interpret_tax_class(property_summary.bldg_class)
        if tax_class:
            if incentives_summary is None:
                incentives_summary = IncentivesSummary()
            incentives_summary = incentives_summary.model_copy(update={
                "property_tax_class": tax_class,
                "tax_incentive_description": tax_desc,
            })
        elif "incentives_domain" in plan.sources:
            if incentives_summary is None:
                incentives_summary = IncentivesSummary()
            incentives_summary = incentives_summary.model_copy(update={
                "property_tax_class": "standard",
                "tax_incentive_description": f"Property class {property_summary.bldg_class} is a standard classification — no tax incentive reduction applies.",
            })
    elif "incentives_domain" in plan.sources and "property_domain" in plan.sources:
        if incentives_summary is None:
            incentives_summary = IncentivesSummary()
        incentives_summary = incentives_summary.model_copy(update={
            "property_tax_class": "unavailable",
            "tax_incentive_description": "Property class code not available from Cook County — tax incentive classification cannot be determined.",
        })

    return ContextObject(
        community_area=plan.location.resolved_community_area,
        community_area_name=plan.location.resolved_community_area_name,
        resolved_address=plan.location.resolved_address,
        data_as_of=data_as_of,
        data_lag_note=lag_note,
        data_lag_days=lag_days,
        data_lag_cutoff=lag_cutoff,
        crime_last_90d=crime,
        open_311_requests=three11,
        address_311=addr_311,
        permits=permits,
        violations=violations,
        businesses=businesses,
        vacant_buildings=vacant,
        food_inspections=food,
        code_chunks=chunks,
        parcel_zoning=parcel_zoning,
        regulatory=regulatory_summary,
        property=property_summary,
        incentives=incentives_summary,
        neighborhood=neighborhood_summary,
        requires_disclaimer=plan.requires_disclaimer,
        partial_failures=partial_failures or [],
    )
