"""The overlay geometry lookup the chat map uses (the Profile's /api/parcel-map was retired with the old UI, Phase 10)."""

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
