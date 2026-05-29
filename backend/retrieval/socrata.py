import asyncio
import logging
from typing import Any

import httpx

from backend.config import get_settings


log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5


class SocrataError(RuntimeError):
    pass


async def socrata_get(
    dataset_id: str,
    params: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if "$limit" not in params:
        raise ValueError(f"Socrata query for {dataset_id} missing $limit guard")

    url = f"{settings.socrata_base}/{dataset_id}.json"
    headers: dict[str, str] = {}
    if settings.socrata_app_token:
        headers["X-App-Token"] = settings.socrata_app_token

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    try:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"socrata {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise SocrataError(f"Socrata request failed for {dataset_id}: {exc}") from exc
                wait = _BACKOFF_BASE * (2 ** attempt)
                log.warning("Socrata retry %d for %s after %.1fs: %s", attempt + 1, dataset_id, wait, exc)
                await asyncio.sleep(wait)
        return []
    finally:
        if owns_client:
            await client.aclose()


async def grouped_count(
    dataset_id: str,
    *,
    where: str,
    group: str,
    select: str,
    limit: int,
    order: str = "count DESC",
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Run a grouped `count(*) as count` aggregation — the shape every retrieval
    module's "top N by category" query shares."""
    return await socrata_get(
        dataset_id,
        {
            "$where": where,
            "$group": group,
            "$select": f"{select},count(*) as count",
            "$order": order,
            "$limit": limit,
        },
        client=client,
    )
