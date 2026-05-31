"""Fetch raw geo-located rows for the map panel.

Unlike the other retrieval modules (which return aggregated counts), these
functions return individual rows with lat/lon for plotting on a map.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get
from backend.retrieval.utils import cutoff_iso

log = logging.getLogger(__name__)


def _float_or_none(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _clean_rows(rows: list[dict]) -> list[dict]:
    """Drop rows with null coordinates and cast lat/lon to float."""
    out = []
    for r in rows:
        lat = _float_or_none(r.get("latitude"))
        lon = _float_or_none(r.get("longitude"))
        if lat is None or lon is None:
            continue
        r["latitude"] = lat
        r["longitude"] = lon
        out.append(r)
    return out


async def crimes_for_map(
    community_area: int,
    *,
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    settings = get_settings()
    cutoff = cutoff_iso(days, lag_days=settings.crime_lag_days)
    rows = await socrata_get(
        settings.dataset_crime,
        {
            "$where": (
                f"community_area='{community_area}'"
                f" AND date > '{cutoff}'"
                " AND latitude IS NOT NULL"
            ),
            "$select": "latitude,longitude,primary_type,date,description,arrest",
            "$order": "date DESC",
            "$limit": settings.limit_map_crime,
        },
        client=client,
    )
    return _clean_rows(rows)


async def requests_311_for_map(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    settings = get_settings()
    rows = await socrata_get(
        settings.dataset_311,
        {
            "$where": (
                f"community_area='{community_area}'"
                " AND status != 'Open - Dup'"
                " AND latitude IS NOT NULL"
            ),
            "$select": "latitude,longitude,sr_type,status,created_date,owner_department",
            "$order": "created_date DESC",
            "$limit": settings.limit_map_311,
        },
        client=client,
    )
    return _clean_rows(rows)


async def permits_for_map(
    community_area: int,
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    settings = get_settings()
    cutoff = cutoff_iso(days)
    rows = await socrata_get(
        settings.dataset_permits,
        {
            "$where": (
                f"community_area='{community_area}'"
                f" AND issue_date > '{cutoff}'"
                " AND latitude IS NOT NULL"
            ),
            "$select": "latitude,longitude,permit_type,work_description,reported_cost,issue_date",
            "$order": "issue_date DESC",
            "$limit": settings.limit_map_permits,
        },
        client=client,
    )
    cleaned = _clean_rows(rows)
    for r in cleaned:
        cost = _float_or_none(r.pop("reported_cost", None))
        r["estimated_cost"] = cost or 0
    return cleaned


async def zoning_for_map(
    community_area: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch zoning district polygons as GeoJSON from the Socrata .geojson endpoint."""
    settings = get_settings()
    url = f"{settings.socrata_base}/{settings.dataset_zoning}.geojson"
    headers: dict[str, str] = {}
    if settings.socrata_app_token:
        headers["X-App-Token"] = settings.socrata_app_token

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))

    try:
        resp = await client.get(
            url,
            params={"$where": f"community_area='{community_area}'"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        log.warning("Zoning fetch failed for CA %s, returning empty", community_area, exc_info=True)
        return {"type": "FeatureCollection", "features": []}
    finally:
        if owns_client:
            await client.aclose()
