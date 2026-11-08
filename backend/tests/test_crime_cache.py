"""Crime aggregates are cached for 6 hours, successes only (decision Item 83)."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.retrieval import crime

pytestmark = pytest.mark.asyncio


def test_crime_cache_holds_six_hours():
    assert crime.CRIME_CACHE_TTL_S == 6 * 60 * 60
    assert crime._cache._ttl == crime.CRIME_CACHE_TTL_S


async def test_a_second_visit_reuses_the_area_and_a_failure_is_not_cached(mock_settings):
    rows = [{"primary_type": "THEFT", "count": "10"}]
    with patch("backend.retrieval.crime.get_settings", return_value=mock_settings), \
         patch("backend.retrieval.crime.grouped_count", new_callable=AsyncMock) as gc, \
         patch("backend.retrieval.crime.socrata_get", new_callable=AsyncMock) as get:
        gc.side_effect = [RuntimeError("portal down"), rows]
        get.return_value = [{"primary_type": "THEFT", "arrests": "2"}]
        with pytest.raises(RuntimeError):
            await crime.crime_by_community_area(24)
        first = await crime.crime_by_community_area(24)
        again = await crime.crime_by_community_area(24)
    assert first == again and first[0]["arrests"] == "2"
    assert gc.await_count == 2  # the failure was retried, the success was reused
