from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get


async def businesses_by_community_area(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "$where": f"community_area='{community_area}'",
        "$select": (
            "legal_name,doing_business_as_name,license_description,"
            "business_activity,address"
        ),
        "$limit": 100,
    }
    return await socrata_get(settings.dataset_business, params, client=client)
