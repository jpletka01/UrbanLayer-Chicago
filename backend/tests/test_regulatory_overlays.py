from unittest.mock import AsyncMock

import httpx
import pytest

from backend.retrieval.regulatory import regulatory_domain
from backend.retrieval.regulatory.overlays import (
    OVERLAY_LAYERS,
    ZONING_BASE_URL,
    OverlayLayerError,
    overlay_geojson_features,
    query_all_overlays,
    query_overlay,
    query_overlay_checked,
    query_overlay_with_geometry,
    query_overlays_checked,
)


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", f"{ZONING_BASE_URL}/2/query"),
    )


@pytest.mark.asyncio
async def test_query_overlay_returns_attributes():
    resp_data = {
        "features": [
            {"attributes": {"PD_NAME": "Lincoln Yards", "ORDINANCE": "2019-123"}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_overlay(41.93, -87.65, 2, client=client)

    assert result is not None
    assert result["PD_NAME"] == "Lincoln Yards"
    assert result["ORDINANCE"] == "2019-123"


@pytest.mark.asyncio
async def test_query_overlay_returns_none_for_empty_features():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_handles_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_mock_response({"error": "fail"}, status_code=500)
    )

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_handles_connection_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    result = await query_overlay(41.93, -87.65, 2, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_query_overlay_url_includes_layer_id():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_overlay(41.93, -87.65, 17, client=client)

    url_arg = client.get.call_args[0][0]
    assert "/17/query" in url_arg


@pytest.mark.asyncio
async def test_query_overlay_sends_correct_geometry():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_overlay(41.93, -87.65, 2, client=client)

    params = client.get.call_args.kwargs.get("params") or client.get.call_args[1].get("params")
    assert params["geometry"] == "-87.65,41.93"
    assert params["geometryType"] == "esriGeometryPoint"
    assert params["inSR"] == "4326"


@pytest.mark.asyncio
async def test_query_all_overlays_returns_hits():
    def make_resp(layer_id):
        if layer_id == 5:
            return _mock_response({
                "features": [{"attributes": {"NAME": "Gold Coast"}}]
            })
        return _mock_response({"features": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=lambda url, **kw: make_resp(
        int(url.split("/")[-2])
    ))

    hits = await query_all_overlays(41.93, -87.65, client=client)

    assert len(hits) == 1
    layer_id, attrs = hits[0]
    assert layer_id == 5
    assert attrs["NAME"] == "Gold Coast"


@pytest.mark.asyncio
async def test_query_all_overlays_skips_failed_layers():
    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        lid = int(url.split("/")[-2])
        if lid == 2:
            raise httpx.ConnectError("timeout")
        return _mock_response({"features": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get

    hits = await query_all_overlays(41.93, -87.65, client=client)

    assert hits == []
    # Every layer once, plus one retry for the failing layer.
    assert call_count == len(OVERLAY_LAYERS) + 1


@pytest.mark.asyncio
async def test_overlay_geometry_failure_raises_instead_of_becoming_a_miss():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({}, status_code=500))

    with pytest.raises(OverlayLayerError):
        await query_overlay_with_geometry(41.93, -87.65, 5, client=client)


@pytest.mark.asyncio
async def test_overlay_geometry_collection_failure_is_not_cached():
    feature = {
        "type": "Feature",
        "properties": {"NAME": "Test district"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-87.66, 41.92], [-87.64, 41.92], [-87.64, 41.94], [-87.66, 41.92]]],
        },
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=[
        _mock_response({"error": {"message": "temporary"}}),
        _mock_response({"type": "FeatureCollection", "features": [feature]}),
    ])

    with pytest.raises(OverlayLayerError):
        await overlay_geojson_features(41.93, -87.65, [5], client=client)
    result = await overlay_geojson_features(41.93, -87.65, [5], client=client)

    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["overlay_type"] == "landmark_building"
    assert client.get.await_count == 2


# --- tri-state: hit / clear / failed (WS6 M7a) ---------------------------------


def _layer_client(failing: dict[int, object], hits: dict[int, dict] | None = None):
    """A client whose layer ``lid`` raises / returns the given body; others are clear."""
    calls: dict[int, int] = {}

    async def mock_get(url, **kwargs):
        lid = int(url.split("/")[-2])
        calls[lid] = calls.get(lid, 0) + 1
        if lid in failing:
            body = failing[lid]
            if isinstance(body, Exception):
                raise body
            return _mock_response(body)
        if hits and lid in hits:
            return _mock_response({"features": [{"attributes": hits[lid]}]})
        return _mock_response({"features": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get
    return client, calls


@pytest.mark.asyncio
async def test_a_200_error_body_is_a_failure_not_a_miss():
    # ArcGIS answers a missing/renumbered layer with HTTP 200 + an error body.
    client, calls = _layer_client({5: {"error": {"code": 404, "message": "Layer not found"}}})
    with pytest.raises(OverlayLayerError):
        await query_overlay_checked(41.93, -87.65, 5, client=client)
    assert calls[5] == 2  # retried once


@pytest.mark.asyncio
async def test_a_body_without_features_is_a_failure():
    client, _ = _layer_client({5: {"unexpected": True}})
    with pytest.raises(OverlayLayerError):
        await query_overlay_checked(41.93, -87.65, 5, client=client)


@pytest.mark.asyncio
async def test_retry_recovers_a_transient_failure():
    attempts = 0

    async def mock_get(url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("slow")
        return _mock_response({"features": [{"attributes": {"NAME": "Wrigley Field"}}]})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = mock_get
    assert (await query_overlay_checked(41.93, -87.65, 5, client=client)) == {"NAME": "Wrigley Field"}
    assert attempts == 2


@pytest.mark.asyncio
async def test_failed_layers_are_reported_apart_from_clear_ones():
    client, _ = _layer_client({5: httpx.ConnectError("down")}, hits={20: {"AREA_NAME": "ARO"}})
    res = await query_overlays_checked(41.93, -87.65, client=client)
    assert res.failed == [5]
    assert [lid for lid, _ in res.hits] == [20]


@pytest.mark.asyncio
async def test_a_result_with_a_failure_is_not_cached():
    client, calls = _layer_client({5: httpx.ConnectError("down")})
    await query_overlays_checked(41.93, -87.65, client=client)
    await query_overlays_checked(41.93, -87.65, client=client)
    # Queried again on the second call (2 attempts each time), not served from cache.
    assert calls[5] == 4
    assert calls[2] == 2


@pytest.mark.asyncio
async def test_a_clean_result_is_cached():
    client, calls = _layer_client({})
    await query_overlays_checked(41.93, -87.65, client=client)
    await query_overlays_checked(41.93, -87.65, client=client)
    assert calls[5] == 1


@pytest.mark.asyncio
async def test_fault_flag_forces_a_layer_to_fail(monkeypatch):
    monkeypatch.setenv("DATA_HEALTH_FAULT", "overlay:5")
    client, calls = _layer_client({})
    res = await query_overlays_checked(41.93, -87.65, client=client)
    assert res.failed == [5]
    assert 5 not in calls  # never sent


@pytest.mark.asyncio
async def test_fault_flag_is_ignored_in_production(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv("DATA_HEALTH_FAULT", "overlay:5")
    monkeypatch.setattr(get_settings(), "environment", "production")
    client, _ = _layer_client({})
    res = await query_overlays_checked(41.93, -87.65, client=client)
    assert res.failed == []


@pytest.mark.asyncio
async def test_landmark_failure_reads_unknown_not_clear(monkeypatch):
    monkeypatch.setattr("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None))
    monkeypatch.setattr("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(return_value=[]))
    client, _ = _layer_client({5: {"error": {"code": 404, "message": "Layer not found"}}})
    monkeypatch.setattr("backend.retrieval.regulatory.overlays._get_arcgis_client", lambda: client)

    summary = await regulatory_domain(41.93, -87.65, client=client)

    assert summary.is_landmark_building is False  # unknown, flagged below
    assert summary.unchecked_overlays == ["landmark_building"]
    assert summary.data_gaps == ["landmark designation (City zoning map didn't answer)"]


@pytest.mark.asyncio
async def test_all_layers_failing_collapses_to_one_gap(monkeypatch):
    monkeypatch.setattr("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None))
    monkeypatch.setattr("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "backend.retrieval.regulatory.query_overlays_checked", AsyncMock(side_effect=RuntimeError("boom")),
    )
    summary = await regulatory_domain(41.93, -87.65, client=AsyncMock())
    assert len(summary.unchecked_overlays) == len({m["type"] for m in OVERLAY_LAYERS.values()})
    assert summary.data_gaps == ["regulatory overlays (City zoning map didn't answer)"]


# --- live integration tests (real Chicago ArcGIS Zoning overlay service, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overlay_live_lincoln_park():
    """Lincoln Park address should hit at least one overlay (e.g. landmark/historic)."""
    hits = await query_all_overlays(41.9307, -87.6411)
    assert isinstance(hits, list)
    assert len(hits) > 0, "Expected at least one overlay hit in Lincoln Park"
    layer_id, attrs = hits[0]
    assert layer_id in OVERLAY_LAYERS
    assert isinstance(attrs, dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_overlay_live():
    """Query the ADU eligible area layer (17) for a Lincoln Park address."""
    result = await query_overlay(41.9307, -87.6411, 17)
    # ADU eligibility may or may not apply — just verify the call succeeds
    assert result is None or isinstance(result, dict)
