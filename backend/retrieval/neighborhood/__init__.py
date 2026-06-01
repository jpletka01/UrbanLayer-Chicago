"""Neighborhood domain orchestrator.

Fetches community area demographics, transit proximity data,
and Walk Score for a given location. Demographics are keyed on
community area; transit proximity and Walk Score use lat/lon.
"""

import asyncio
import logging

import httpx

from backend.config import get_settings
from backend.models import NeighborhoodSummary, WalkScoreSummary
from backend.retrieval.neighborhood.demographics import fetch_demographics
from backend.retrieval.neighborhood.transit import (
    build_transit_access,
    check_tod_eligibility,
    find_nearest_stations,
)
from backend.retrieval.neighborhood.walkscore import fetch_walkscore

log = logging.getLogger(__name__)


async def neighborhood_domain(
    lat: float,
    lon: float,
    *,
    community_area: int | None = None,
    address: str | None = None,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> NeighborhoodSummary:
    """Fetch demographics, transit, and Walk Score data for a location."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        tasks: dict[str, asyncio.Task] = {}

        skip_demographics = workflow in ("property_intelligence",)
        if community_area is not None and not skip_demographics:
            tasks["demographics"] = asyncio.create_task(
                fetch_demographics(community_area, client=client)
            )

        has_coords = lat != 0.0 or lon != 0.0
        if has_coords:
            tasks["stations"] = asyncio.create_task(
                find_nearest_stations(lat, lon)
            )
            tasks["tod"] = asyncio.create_task(
                check_tod_eligibility(lat, lon, client=client)
            )

        if has_coords and address:
            settings = get_settings()
            if settings.walkscore_api_key and workflow not in ("property_intelligence",):
                tasks["walkscore"] = asyncio.create_task(
                    fetch_walkscore(lat, lon, address, client=client)
                )

        results: dict[str, object] = {}
        if tasks:
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for key, value in zip(tasks.keys(), done):
                if isinstance(value, Exception):
                    log.warning("Neighborhood %s failed: %s", key, value)
                    results[key] = None
                else:
                    results[key] = value

        return _build_summary(
            results.get("demographics"),
            results.get("stations"),
            results.get("tod"),
            results.get("walkscore"),
        )
    finally:
        if owns:
            await client.aclose()


def _build_summary(
    demographics,
    station_result: dict | None,
    tod_result: dict | None,
    walkscore_result: WalkScoreSummary | None = None,
) -> NeighborhoodSummary:
    transit = build_transit_access(station_result, tod_result)
    return NeighborhoodSummary(
        demographics=demographics,
        transit=transit,
        walkscore=walkscore_result,
    )
