"""Tests for Divvy bike-share proximity (backend/retrieval/neighborhood/divvy.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.neighborhood.divvy import find_nearest_divvy


def _row(name, dist_m, docks=15, total=15, status="In Service"):
    return {
        "station_name": name,
        "total_docks": str(total),
        "docks_in_service": str(docks),
        "status": status,
        "dist_m": str(dist_m),
    }


# Socrata orders by dist_m server-side, so row 0 is the nearest.
ROWS = [
    _row("Damen Ave & Pierce Ave", 132.41446982, docks=24, total=24),
    _row("Damen Ave & Wabansia Ave", 194.48852188, docks=11, total=11),
    _row("Milwaukee Ave & Wabansia Ave", 418.17787571, docks=24, total=24),
]

LAT, LON = 41.9105, -87.6773


# conftest's autouse _clear_ttl_caches already resets every TTLCache between tests.


def _patch(rows):
    return patch(
        "backend.retrieval.neighborhood.divvy.socrata_get",
        new=AsyncMock(return_value=rows),
    )


@pytest.mark.asyncio
async def test_returns_nearest_station_with_distance_in_miles():
    with _patch(ROWS):
        access = await find_nearest_divvy(LAT, LON)

    assert access is not None
    assert access.nearest_station == "Damen Ave & Pierce Ave"
    # 132.41 m / 1609.34 = 0.0823 mi
    assert access.distance_mi == 0.08
    assert access.docks == 24
    assert access.stations_within_radius == 3


@pytest.mark.asyncio
async def test_returns_none_when_no_station_in_range():
    """No chip beats an empty chip."""
    with _patch([]):
        assert await find_nearest_divvy(LAT, LON) is None


@pytest.mark.asyncio
async def test_caches_the_empty_result_without_returning_it():
    """A known-empty area must not re-query, but must still read as None."""
    mock = AsyncMock(return_value=[])
    with patch("backend.retrieval.neighborhood.divvy.socrata_get", new=mock):
        assert await find_nearest_divvy(LAT, LON) is None
        assert await find_nearest_divvy(LAT, LON) is None
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_caches_a_hit():
    mock = AsyncMock(return_value=ROWS)
    with patch("backend.retrieval.neighborhood.divvy.socrata_get", new=mock):
        first = await find_nearest_divvy(LAT, LON)
        second = await find_nearest_divvy(LAT, LON)
    assert mock.await_count == 1
    assert second == first


@pytest.mark.asyncio
async def test_query_filters_to_in_service_and_orders_by_distance():
    """Out-of-service docks aren't an amenity; the ordering is what makes row 0 nearest."""
    mock = AsyncMock(return_value=ROWS)
    with patch("backend.retrieval.neighborhood.divvy.socrata_get", new=mock):
        await find_nearest_divvy(LAT, LON)

    params = mock.await_args.args[1]
    assert "status='In Service'" in params["$where"]
    assert "within_circle" in params["$where"]
    assert params["$order"] == "dist_m ASC"


@pytest.mark.asyncio
async def test_falls_back_to_total_docks_when_in_service_count_missing():
    row = _row("Somewhere", 100.0)
    del row["docks_in_service"]
    with _patch([row]):
        access = await find_nearest_divvy(LAT, LON)
    assert access.docks == 15


@pytest.mark.asyncio
async def test_survives_a_failed_lookup():
    """One dead source must never fail the neighborhood fan-out."""
    with patch(
        "backend.retrieval.neighborhood.divvy.socrata_get",
        new=AsyncMock(side_effect=RuntimeError("socrata down")),
    ):
        assert await find_nearest_divvy(LAT, LON) is None


@pytest.mark.asyncio
async def test_handles_unparseable_distance():
    row = _row("Weird", "not-a-number")
    with _patch([row]):
        access = await find_nearest_divvy(LAT, LON)
    assert access is not None
    assert access.distance_mi is None
    assert access.nearest_station == "Weird"
