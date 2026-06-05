"""City grant program data: SBIF and Neighborhood Opportunity Fund."""

import asyncio
import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="grant_programs")


async def grant_programs_by_community_area(
    community_area_name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch SBIF + NOF projects for a community area (by name)."""
    key = f"grants:{community_area_name}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        ca_filter = f"community_area='{community_area_name}'"
        limit = settings.limit_grant_programs_detail

        sbif_task = socrata_get(
            settings.dataset_sbif,
            {
                "$where": ca_filter,
                "$select": (
                    "project_name,incentive_amount,total_project_cost,"
                    "property_type,project_description,completion_date,"
                    "tif_district"
                ),
                "$order": "completion_date DESC",
                "$limit": limit,
            },
            client=client,
        )
        nof_large_task = socrata_get(
            settings.dataset_nof_large,
            {
                "$where": ca_filter,
                "$select": (
                    "project_name,incentive_amount,total_project_cost,"
                    "property_type,project_description,completion_date"
                ),
                "$order": "completion_date DESC",
                "$limit": limit,
            },
            client=client,
        )
        nof_small_task = socrata_get(
            settings.dataset_nof_small,
            {
                "$where": ca_filter,
                "$select": (
                    "project_name,incentive_amount,total_project_cost,"
                    "property_type,project_description,completion_date"
                ),
                "$order": "completion_date DESC",
                "$limit": limit,
            },
            client=client,
        )

        sbif, nof_large, nof_small = await asyncio.gather(
            sbif_task, nof_large_task, nof_small_task,
            return_exceptions=True,
        )
        sbif = sbif if not isinstance(sbif, Exception) else []
        nof_large = nof_large if not isinstance(nof_large, Exception) else []
        nof_small = nof_small if not isinstance(nof_small, Exception) else []

        if isinstance(sbif, Exception):
            log.warning("SBIF query failed: %s", sbif)
            sbif = []
        if isinstance(nof_large, Exception):
            log.warning("NOF large grants query failed: %s", nof_large)
            nof_large = []
        if isinstance(nof_small, Exception):
            log.warning("NOF small grants query failed: %s", nof_small)
            nof_small = []

        for row in sbif:
            row["_program"] = "SBIF"
        for row in nof_large:
            row["_program"] = "NOF"
        for row in nof_small:
            row["_program"] = "NOF"

        result = {
            "sbif": sbif,
            "nof_large": nof_large,
            "nof_small": nof_small,
        }
        _cache.set(key, result)
        return result
    finally:
        if owns:
            await client.aclose()
