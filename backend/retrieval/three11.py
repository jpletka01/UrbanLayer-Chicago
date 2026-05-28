from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get


def _cutoff_iso(days_ago: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return cutoff.strftime("%Y-%m-%dT00:00:00.000")


async def open_311_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND status='Open' "
            "AND sr_type!='Open - Dup'"
        ),
        "$group": "owner_department,sr_type",
        "$select": "owner_department,sr_type,count(*) as count",
        "$order": "count DESC",
        "$limit": 50,
    }
    return await socrata_get(settings.dataset_311, params, client=client)


async def open_311_oldest(
    community_area: int,
    *,
    limit: int = 1,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND status='Open' "
            "AND sr_type!='Open - Dup'"
        ),
        "$select": "sr_number,sr_type,created_date",
        "$order": "created_date ASC",
        "$limit": limit,
    }
    return await socrata_get(settings.dataset_311, params, client=client)


async def response_times_by_community_area(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": (
            f"community_area='{community_area}' "
            "AND status='Closed' "
            f"AND created_date > '{_cutoff_iso(days)}'"
        ),
        "$select": "sr_type,avg(date_diff_d(closed_date,created_date)) as avg_days",
        "$group": "sr_type",
        "$order": "avg_days DESC",
        "$limit": 10,
    }
    return await socrata_get(settings.dataset_311, params, client=client)
