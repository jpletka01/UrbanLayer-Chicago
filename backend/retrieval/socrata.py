import asyncio
import logging
from typing import Any

import httpx

from backend.config import get_settings


log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5

_shared_client: httpx.AsyncClient | None = None


class SocrataError(RuntimeError):
    pass


class SocrataClientError(SocrataError):
    """Non-retryable client error (4xx) from the Socrata API."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            http2=True,
        )
    return _shared_client


async def close_shared_client() -> None:
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None


async def socrata_get(
    dataset_id: str,
    params: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    base_url: str | None = None,
    app_token: str | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if "$limit" not in params:
        raise ValueError(f"Socrata query for {dataset_id} missing $limit guard")

    url = f"{base_url or settings.socrata_base}/{dataset_id}.json"
    headers: dict[str, str] = {}
    token = app_token if app_token is not None else settings.socrata_app_token
    if token:
        headers["X-App-Token"] = token

    if client is None:
        client = get_shared_client()

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
            if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                raise SocrataClientError(
                    f"Socrata client error {exc.response.status_code} for {dataset_id}: {exc}",
                    status_code=exc.response.status_code,
                ) from exc
            if attempt == _MAX_RETRIES - 1:
                raise SocrataError(f"Socrata request failed for {dataset_id}: {exc}") from exc
            wait = _BACKOFF_BASE * (2 ** attempt)
            log.warning("Socrata retry %d for %s after %.1fs: %s", attempt + 1, dataset_id, wait, exc)
            await asyncio.sleep(wait)
    return []


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


async def socrata_aggregate(
    dataset_id: str,
    *,
    where: str,
    group: str,
    select: str,
    limit: int,
    order: str = "count DESC",
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Run a grouped aggregation with caller-defined $select expressions."""
    return await socrata_get(
        dataset_id,
        {
            "$where": where,
            "$group": group,
            "$select": select,
            "$order": order,
            "$limit": limit,
        },
        client=client,
    )
