"""Contract tests for the Property Profile parcel-map endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


FIXTURE = Path(__file__).parent / "fixtures" / "ws3_milwaukee_zoning_adjacent.geojson"
EMPTY_FC = {"type": "FeatureCollection", "features": []}


def _zoning_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def _source_patches(*, zoning, overlays=EMPTY_FC, tif=None, ez=None):
    return (
        patch("backend.retrieval.zoning.zoning_polygons_near", new=AsyncMock(side_effect=zoning) if isinstance(zoning, Exception) else AsyncMock(return_value=zoning)),
        patch("backend.main._fetch_overlay_geojson", new=AsyncMock(return_value=overlays)),
        patch("backend.retrieval.incentives.tif.tif_geojson_feature", new=AsyncMock(return_value=tif)),
        patch("backend.retrieval.incentives.enterprise_zones.ez_geojson_feature", new=AsyncMock(return_value=ez)),
    )


@pytest.mark.asyncio
async def test_parcel_map_returns_geometry_labels_and_availability():
    from backend import main

    patches = _source_patches(zoning=_zoning_fixture())
    with patches[0] as zoning_mock, patches[1], patches[2], patches[3]:
        payload = await main.parcel_map(41.91085876, -87.67777584)
        cached = await main.parcel_map(41.91085876, -87.67777584)

    assert payload == cached
    assert payload["availability"] == {
        "zoning": "available",
        "overlays": "available",
        "tif": "available",
        "ez": "available",
    }
    assert {label["zone_class"] for label in payload["zoning_labels"]} == {"RT-4", "RS-3"}
    assert zoning_mock.await_count == 1


@pytest.mark.asyncio
async def test_parcel_map_failed_source_is_unavailable_and_not_cached():
    from backend import main

    patches = _source_patches(zoning=RuntimeError("zoning down"))
    with patches[0] as zoning_mock, patches[1], patches[2], patches[3]:
        first = await main.parcel_map(41.91085876, -87.67777584)
        second = await main.parcel_map(41.91085876, -87.67777584)

    assert first["zoning"] is None
    assert first["zoning_labels"] == []
    assert first["availability"]["zoning"] == "unavailable"
    assert second["availability"]["zoning"] == "unavailable"
    assert zoning_mock.await_count == 2


@pytest.mark.asyncio
async def test_parcel_map_complete_empty_result_is_cached():
    from backend import main

    patches = _source_patches(zoning=EMPTY_FC)
    with patches[0] as zoning_mock, patches[1] as overlays_mock, patches[2] as tif_mock, patches[3] as ez_mock:
        first = await main.parcel_map(41.5, -88.0)
        second = await main.parcel_map(41.5, -88.0)

    assert first == second
    assert first["zoning"]["features"] == []
    assert all(value == "available" for value in first["availability"].values())
    assert zoning_mock.await_count == 1
    assert overlays_mock.await_count == 1
    assert tif_mock.await_count == 1
    assert ez_mock.await_count == 1


@pytest.mark.asyncio
async def test_overlay_point_failure_raises_before_geometry_is_cached():
    from backend import main
    from backend.retrieval.regulatory.overlays import OverlayLayerError, OverlayResults

    with patch(
        "backend.retrieval.regulatory.overlays.query_overlays_checked",
        new=AsyncMock(return_value=OverlayResults(failed=[5])),
    ), patch(
        "backend.retrieval.regulatory.overlays.overlay_geojson_features",
        new=AsyncMock(),
    ) as geometry_mock:
        with pytest.raises(OverlayLayerError, match=r"layer\(s\) 5"):
            await main._fetch_overlay_geojson(41.91085876, -87.67777584)

    geometry_mock.assert_not_awaited()
