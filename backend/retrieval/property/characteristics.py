"""CCAO property characteristics by PIN."""

import logging

import httpx

from backend.config import get_settings
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)


async def get_characteristics(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Fetch the most recent property characteristics for a PIN."""
    settings = get_settings()
    params = {
        "pin": pin14,
        "$order": "year DESC",
        "$limit": settings.limit_ccao_characteristics,
    }
    try:
        rows = await socrata_get(
            settings.dataset_ccao_characteristics,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
        if not rows:
            return None
        return rows[0]
    except Exception as exc:
        log.warning("CCAO characteristics failed for PIN %s: %s", pin14, exc)
        return None
