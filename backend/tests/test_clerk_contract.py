"""Live contract test for the City Clerk eLMS API (BETA). Integration only: it calls the
real API (a handful of requests), never the model. WS6 can run it weekly as a probe.

    python -m pytest backend/tests/test_clerk_contract.py -m integration -v
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from backend.retrieval import clerk
from backend.retrieval.zoning import ZONING_QUERY_URL

pytestmark = pytest.mark.integration

# A passed rezoning already on the City zoning map (layer 1 CLERK_DOCNO), checked 2026-10-21.
ON_MAP_REZONING = "SO2026-0022502"


async def test_matter_schema_and_vocabulary_hold():
    since = date.today() - timedelta(days=120)
    amendments = await clerk.passed_since(since, (clerk.CODE_AMENDMENTS,))
    assert amendments, "no code amendment passed in 120 days: contract drift, not a quiet Council"
    rezonings = await clerk.passed_since(since, (clerk.ZONING_RECLASSIFICATIONS,))
    assert rezonings
    subs = {m.sub_status for m in amendments + rezonings}
    assert subs <= clerk.KNOWN_FINAL_SUBSTATUSES
    assert {"Passed", "Passed as Substitute"} <= subs


async def test_incremental_filter_on_last_publication_date_works():
    stamp = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    matters, count = await clerk.search_matters(f"lastPublicationDate gt {stamp}", top=5)
    assert count >= len(matters)


async def test_newest_record_is_recent():
    assert datetime.now(timezone.utc) - await clerk.latest_record_date() < timedelta(days=14)


async def test_sorting_on_record_create_date_is_still_rejected():
    """If this starts passing, latest_record_date can sort server-side instead."""
    with pytest.raises(clerk.ClerkQueryError):
        await clerk.search_matters("recordCreateDate gt 2026-10-01T00:00:00Z", top=1, sort="recordCreateDate desc")


async def test_clerk_docno_joins_the_city_zoning_map():
    m = await clerk.get_matter_by_record(ON_MAP_REZONING)
    assert m is not None and m.passed and m.category.startswith(clerk.ZONING_RECLASSIFICATIONS)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(ZONING_QUERY_URL, params={
            "where": f"CLERK_DOCNO = '{ON_MAP_REZONING}'", "outFields": "CLERK_DOCNO",
            "returnGeometry": "false", "f": "json",
        })
    assert r.json().get("features"), f"{ON_MAP_REZONING} not on zoning layer 1"
