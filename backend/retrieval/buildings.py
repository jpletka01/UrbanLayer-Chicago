from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get


def _cutoff_iso(days_ago: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return cutoff.strftime("%Y-%m-%dT00:00:00.000")


async def permits_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            f"AND issue_date > '{_cutoff_iso(days)}'"
        ),
        "$select": (
            "permit_type,work_description,issue_date,"
            "street_number,street_direction,street_name,estimated_cost"
        ),
        "$order": "issue_date DESC",
        "$limit": 50,
    }
    return await socrata_get(settings.dataset_permits, params, client=client)


async def violations_by_community_area(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            f"AND violation_date > '{_cutoff_iso(days)}'"
        ),
        "$select": (
            "violation_date,violation_description,violation_status,"
            "street_number,street_name"
        ),
        "$order": "violation_date DESC",
        "$limit": 50,
    }
    return await socrata_get(settings.dataset_violations, params, client=client)
