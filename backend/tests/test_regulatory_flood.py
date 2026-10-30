from unittest.mock import AsyncMock

import httpx
import pytest

from backend.data_health import live
from backend.retrieval.regulatory import flood
from backend.retrieval.regulatory.flood import FEMA_NFHL_URL, FloodLookupError, query_flood_zone


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", FEMA_NFHL_URL),
    )


@pytest.mark.asyncio
async def test_returns_flood_zone_data():
    resp_data = {
        "features": [
            {"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}}
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_flood_zone(41.93, -87.65, client=client)

    assert result is not None
    assert result["fld_zone"] == "AE"
    assert result["zone_subty"] == "FLOODWAY"
    assert result["sfha_tf"] == "T"


@pytest.mark.asyncio
async def test_returns_none_when_not_in_flood_zone():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_for_missing_fld_zone():
    resp_data = {"features": [{"attributes": {"ZONE_SUBTY": "X", "SFHA_TF": "F"}}]}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response(resp_data))

    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result is None


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    """The retry pause is real time otherwise; the live counts are module state."""
    monkeypatch.setattr(flood, "_RETRY_PAUSE_S", 0)
    live.reset()
    yield
    live.reset()


def _client(*effects):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=list(effects))
    return client


# --- a failed lookup is not "no flood zone": it raises, and is never cached ----------------------------------------------

@pytest.mark.asyncio
async def test_an_http_error_raises_instead_of_reading_as_no_flood_zone():
    client = _client(_mock_response({"error": "fail"}, status_code=500))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.93, -87.65, client=client)
    assert client.get.await_count == 1  # an answer, even a bad one, is final: only connection resets are retried


@pytest.mark.asyncio
async def test_a_connection_that_never_opens_raises_after_the_retries():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("Connection reset by peer"))
    with pytest.raises(FloodLookupError, match="reset"):
        await query_flood_zone(41.93, -87.65, client=client)
    assert client.get.await_count == flood._ATTEMPTS


@pytest.mark.asyncio
async def test_a_reset_connection_is_retried_and_the_answer_still_counts():
    resp = {"features": [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}}]}
    client = _client(httpx.ConnectError("reset"), httpx.ReadError("reset"), _mock_response(resp))
    result = await query_flood_zone(41.93, -87.65, client=client)
    assert result["fld_zone"] == "AE" and client.get.await_count == 3
    assert live.pending()[flood.SOURCE_ID] == (1, 0)  # one call, not one per attempt


@pytest.mark.asyncio
async def test_a_timeout_is_not_retried():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.93, -87.65, client=client)
    assert client.get.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"error": {"code": 500, "message": "Service not started"}},   # ArcGIS: HTTP 200 with an error body
    {"currentVersion": 11.1},                                      # no features list at all
    {"features": None},
    ["not", "a", "dict"],
])
async def test_a_200_that_is_not_an_answer_raises_and_is_not_cached_as_not_found(body):
    client = _client(_mock_response(body), _mock_response({"features": []}))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.93, -87.65, client=client)
    # the failure was not remembered as "no flood zone": the next call reaches FEMA again and gets its real answer
    assert await query_flood_zone(41.93, -87.65, client=client) is None
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_raises():
    html = httpx.Response(200, text="<html>Service Unavailable</html>", request=httpx.Request("GET", FEMA_NFHL_URL))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.93, -87.65, client=_client(html))


@pytest.mark.asyncio
async def test_a_failure_is_not_cached_but_a_genuine_empty_answer_is():
    client = _client(httpx.ConnectError("reset"), httpx.ConnectError("reset"), httpx.ConnectError("reset"),
                     httpx.ConnectError("reset"), _mock_response({"features": []}))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.93, -87.65, client=client)
    assert await query_flood_zone(41.93, -87.65, client=client) is None  # FEMA's answer: no mapped flood zone
    calls = client.get.await_count
    assert await query_flood_zone(41.93, -87.65, client=client) is None  # served from the cache, FEMA not asked
    assert client.get.await_count == calls


@pytest.mark.asyncio
async def test_a_success_is_cached_for_the_next_lookup():
    resp = {"features": [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F"}}]}
    client = _client(_mock_response(resp))
    first = await query_flood_zone(41.93, -87.65, client=client)
    assert await query_flood_zone(41.93, -87.65, client=client) == first and client.get.await_count == 1


# --- the live failure rate and the dev fault flag ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_each_call_is_counted_once_by_outcome():
    ok = _client(_mock_response({"features": []}))
    await query_flood_zone(41.9, -87.6, client=ok)
    bad = AsyncMock(spec=httpx.AsyncClient)
    bad.get = AsyncMock(side_effect=httpx.ConnectError("reset"))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(41.8, -87.6, client=bad)
    assert live.pending()[flood.SOURCE_ID] == (2, 1)


@pytest.mark.asyncio
async def test_the_fault_flag_forces_the_failure_even_for_a_point_already_cached(monkeypatch):
    client = _client(_mock_response({"features": []}))
    assert await query_flood_zone(41.93, -87.65, client=client) is None  # now cached
    monkeypatch.setenv("DATA_HEALTH_FAULT", f"source:{flood.SOURCE_ID}")
    with pytest.raises(FloodLookupError, match="DATA_HEALTH_FAULT"):
        await query_flood_zone(41.93, -87.65, client=client)
    assert client.get.await_count == 1  # the forced failure never reached the network
    assert live.pending()[flood.SOURCE_ID] == (2, 1)
    monkeypatch.delenv("DATA_HEALTH_FAULT")
    assert await query_flood_zone(41.93, -87.65, client=client) is None  # nothing was left behind


@pytest.mark.asyncio
async def test_sends_correct_params():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_response({"features": []}))

    await query_flood_zone(41.93, -87.65, client=client)

    params = client.get.call_args.kwargs.get("params") or client.get.call_args[1].get("params")
    assert params["outFields"] == "FLD_ZONE,ZONE_SUBTY,SFHA_TF"
    assert params["geometry"] == "-87.65,41.93"


# --- live integration tests (real FEMA NFHL service, free) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fema_nfhl_endpoint_reachable():
    """Confirm FEMA_NFHL_URL points at the live NFHL service.

    Distinguishes a path regression (404 -> the old /gis/nfhl/ host returns
    an auth page) from the service simply being overloaded (504 -> skip).
    """
    params = {"where": "1=1", "outFields": "FLD_ZONE",
              "returnGeometry": "false", "f": "json", "resultRecordCount": "1"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(FEMA_NFHL_URL, params=params)
        except httpx.HTTPError as exc:
            pytest.skip(f"FEMA NFHL unreachable: {exc}")
    if resp.status_code >= 500:
        pytest.skip(f"FEMA NFHL returned {resp.status_code} (service intermittently slow)")
    assert resp.status_code == 200, f"FEMA NFHL path looks wrong (HTTP {resp.status_code})"
    assert "application/json" in resp.headers.get("content-type", "")
    data = resp.json()
    assert "fields" in data or "features" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_flood_zone_live_smoke():
    """The wrapper returns a valid dict or None, or raises FloodLookupError when FEMA doesn't answer."""
    try:
        result = await query_flood_zone(41.9307, -87.6411)
    except FloodLookupError as exc:
        pytest.skip(f"FEMA NFHL did not answer: {exc}")
    assert result is None or isinstance(result.get("fld_zone"), str)
