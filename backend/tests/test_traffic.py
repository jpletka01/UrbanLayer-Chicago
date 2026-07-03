"""Tests for street traffic volume retrieval (backend/retrieval/neighborhood/traffic.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.neighborhood.traffic import get_traffic_context


def _row(sid, road, direction, count, mlat, mlon, day, frm="W A ST", to="W B ST"):
    return {
        "segmentid": sid, "roadname": road, "direction": direction,
        "fromsegment": frm, "tosegment": to, "vehiclecount": str(count),
        "midpointlat": str(mlat), "midpointlon": str(mlon),
        "timestamp": f"{day}T00:00:00.000",
    }


ROWS = [
    # Nearest road: ASHLAND, NB segment right at the point — two days of counts.
    _row("100", "ASHLAND", "NB", 15000, 41.9361, -87.6685, "2026-06-30"),
    _row("100", "ASHLAND", "NB", 17000, 41.9361, -87.6685, "2026-07-01"),
    # Same road, SB twin.
    _row("101", "ASHLAND", "SB", 14000, 41.9362, -87.6686, "2026-07-01"),
    # Same road+direction, NEXT block (must not double-count).
    _row("102", "ASHLAND", "NB", 16000, 41.9380, -87.6685, "2026-07-01"),
    # A different, farther road inside the radius (must not be picked).
    _row("200", "BELMONT", "EB", 25000, 41.9395, -87.6690, "2026-07-01"),
]


@pytest.mark.asyncio
async def test_nearest_road_sums_directions_without_block_chaining():
    with patch("backend.retrieval.neighborhood.traffic.socrata_get",
               new=AsyncMock(return_value=ROWS)):
        r = await get_traffic_context(41.9361, -87.6685)
    assert r is not None
    assert r["road"] == "ASHLAND"
    # NB nearest segment avg = (15000+17000)/2 = 16000; SB = 14000. The
    # next-block NB segment (16000) and BELMONT are excluded.
    assert r["daily_vehicles"] == 30000
    assert r["directions"] == 2
    assert r["as_of"] == "2026-07-01"


@pytest.mark.asyncio
async def test_none_when_no_counted_segments_nearby():
    """Side streets aren't counted — expected absence, negative-cached."""
    with patch("backend.retrieval.neighborhood.traffic.socrata_get",
               new=AsyncMock(return_value=[])) as mock:
        assert await get_traffic_context(41.75, -87.60) is None
        assert await get_traffic_context(41.75, -87.60) is None
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_none_on_transport_failure():
    with patch("backend.retrieval.neighborhood.traffic.socrata_get",
               new=AsyncMock(side_effect=Exception("boom"))):
        assert await get_traffic_context(41.75, -87.60) is None
