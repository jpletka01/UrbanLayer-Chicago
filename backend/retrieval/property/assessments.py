"""CCAO assessed values by PIN."""

import logging
from typing import Any

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)


async def get_assessments(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch assessment history for a PIN (most recent 5 years)."""
    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "tax_year DESC",
        "$limit": settings.limit_ccao_assessments,
    }
    try:
        return await socrata_get(
            settings.dataset_ccao_assessments,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("CCAO assessments failed for PIN %s: %s", pin14, exc)
        return []
