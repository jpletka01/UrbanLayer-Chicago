from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import get_settings
from backend.models import (
    BusinessSummary,
    CodeChunk,
    ContextObject,
    CrimeSummary,
    PermitSummary,
    RetrievalPlan,
    ThreeOneOneSummary,
    ViolationSummary,
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
    )


def _permit_summary(rows: list[dict[str, Any]]) -> PermitSummary | None:
    if not rows:
        return None
    settings = get_settings()
    descs: Counter[str] = Counter()
    cost_total = 0.0
    for row in rows:
        desc = (row.get("work_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
        try:
            cost_total += float(row.get("reported_cost") or row.get("estimated_cost") or 0)
        except (TypeError, ValueError):
            pass
    return PermitSummary(
        total=len(rows),
        total_estimated_cost=round(cost_total, 2),
        top_work_descriptions=[d for d, _ in descs.most_common(settings.top_permits)],
    )


def _violation_summary(rows: list[dict[str, Any]]) -> ViolationSummary | None:
    if not rows:
        return None
    settings = get_settings()
    descs: Counter[str] = Counter()
    open_count = 0
    for row in rows:
        desc = (row.get("violation_description") or "").strip()
        if desc:
            descs[desc[:120]] += 1
        if (row.get("violation_status") or "").upper() == "OPEN":
            open_count += 1
    return ViolationSummary(
        total=len(rows),
        open_count=open_count,
        top_descriptions=[d for d, _ in descs.most_common(settings.top_violations)],
    )


def _business_summary(rows: list[dict[str, Any]]) -> BusinessSummary | None:
    if not rows:
        return None
    settings = get_settings()
    activities: Counter[str] = Counter()
    for row in rows:
        activity = (row.get("business_activity") or "").strip()
        if activity:
            primary = activity.split("|")[0].strip()
            activities[primary] += 1
    return BusinessSummary(
        total=len(rows),
        top_activities=[a for a, _ in activities.most_common(settings.top_businesses)],
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
        requires_disclaimer=plan.requires_disclaimer,
    )
