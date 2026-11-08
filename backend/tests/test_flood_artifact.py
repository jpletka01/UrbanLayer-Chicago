"""The committed Chicago flood artifact answers points inside the city without asking FEMA (decision Item 84).

FEMA resets every TLS handshake from the production server, so the live lookup failed on every Profile. Inside
the artifact's coverage the answer is FEMA's own polygons, no network; outside it (or with no artifact) the
lookup still asks FEMA, and a failure there is still "couldn't check", never "no flood zone".
"""

from __future__ import annotations

import gzip
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.config import get_settings
from backend.data_health import live
from backend.data_health.registry import BY_ID
from backend.retrieval.regulatory import flood
from backend.retrieval.regulatory.flood import FloodLookupError, query_flood_zone


def _square(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


# A 1 x 1 coverage holding a zone X square with an AE square on its east edge, and a gap in the north-west.
FIXTURE = {
    "retrieved": "2026-11-07",
    "coverage": _square(0, 0, 1, 1),
    "features": [
        {"z": "X", "s": "AREA OF MINIMAL FLOOD HAZARD", "t": "F", "g": _square(0, 0, 0.5, 0.5)},
        {"z": "AE", "s": "FLOODWAY", "t": "T", "g": _square(0.5, 0, 1, 0.5)},
    ],
}


def _reset_artifact(monkeypatch):
    monkeypatch.setattr(flood, "_art_loaded", False)
    monkeypatch.setattr(flood, "_art", None)


@pytest.fixture
def fixture_artifact(tmp_path, monkeypatch):
    with gzip.open(tmp_path / flood.ARTIFACT_FILENAME, "wt", encoding="utf-8") as fh:
        json.dump(FIXTURE, fh)
    monkeypatch.setattr(flood, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    _reset_artifact(monkeypatch)
    live.reset()
    yield
    live.reset()


def _no_network():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=AssertionError("FEMA must not be asked for a covered point"))
    return client


@pytest.mark.asyncio
async def test_a_covered_point_in_a_zone_is_answered_without_fema(fixture_artifact):
    got = await query_flood_zone(0.25, 0.25, client=_no_network())  # lat, lon
    assert got == {"fld_zone": "X", "zone_subty": "AREA OF MINIMAL FLOOD HAZARD", "sfha_tf": "F"}
    assert flood.SOURCE_ID not in live.pending()  # the live FEMA service was not used


@pytest.mark.asyncio
async def test_a_point_on_a_shared_edge_takes_the_flood_hazard_zone(fixture_artifact):
    got = await query_flood_zone(0.25, 0.5, client=_no_network())
    assert got["fld_zone"] == "AE" and got["sfha_tf"] == "T"


@pytest.mark.asyncio
async def test_a_covered_point_in_no_polygon_is_no_mapped_zone(fixture_artifact):
    assert await query_flood_zone(0.75, 0.25, client=_no_network()) is None


@pytest.mark.asyncio
async def test_a_point_outside_coverage_still_asks_fema(fixture_artifact):
    body = {"features": [{"attributes": {"FLD_ZONE": "A", "ZONE_SUBTY": None, "SFHA_TF": "T"}}]}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=httpx.Response(200, json=body, request=httpx.Request("GET", flood.FEMA_NFHL_URL)))
    got = await query_flood_zone(5.0, 5.0, client=client)
    assert got["fld_zone"] == "A" and client.get.await_count == 1


@pytest.mark.asyncio
async def test_outside_coverage_a_fema_failure_is_still_couldnt_check(fixture_artifact, monkeypatch):
    monkeypatch.setattr(flood, "_RETRY_PAUSE_S", 0)
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("Connection reset by peer"))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(5.0, 5.0, client=client)


@pytest.mark.asyncio
async def test_a_missing_artifact_falls_back_to_fema_and_never_says_no_zone(tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))  # empty dir
    monkeypatch.setattr(flood, "_RETRY_PAUSE_S", 0)
    _reset_artifact(monkeypatch)
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("Connection reset by peer"))
    with pytest.raises(FloodLookupError):
        await query_flood_zone(0.25, 0.25, client=client)


@pytest.mark.asyncio
async def test_the_forced_fault_still_beats_the_artifact(fixture_artifact, monkeypatch):
    monkeypatch.setenv("DATA_HEALTH_FAULT", "source:fed.fema.nfhl")
    with pytest.raises(FloodLookupError):
        await query_flood_zone(0.25, 0.25, client=_no_network())


# --- the committed artifact itself ------------------------------------------------------------------------------------

def _committed():
    path = get_settings().data_dir / flood.ARTIFACT_FILENAME
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def test_the_committed_artifact_is_fema_and_covers_the_city():
    art = _committed()
    meta = json.loads((get_settings().data_dir / "fema_flood_chicago.meta.json").read_text())
    assert "hazards.fema.gov" in art["source_url"] and art["retrieved"] == meta["retrieved"]
    assert meta["city_share_covered"] >= 0.98 and len(art["features"]) == meta["features"] > 300
    zones = {f["z"] for f in art["features"]}
    assert "X" in zones and zones & {"A", "AE", "AH", "AO"}  # minimal-hazard land and real flood hazard areas


@pytest.mark.asyncio
@pytest.mark.parametrize("lat, lon, zone", [
    (41.9105, -87.6775, "X"),     # 1601 N Milwaukee Ave: FEMA answered X live on 2026-11-07
    (41.8789, -87.6359, "X"),     # the Loop, Willis Tower
    (41.97216, -87.8578, "AE"),   # Des Plaines River floodway: FEMA answered AE / FLOODWAY live on 2026-11-07
])
async def test_the_committed_artifact_matches_fema_at_known_points(lat, lon, zone, monkeypatch):
    _reset_artifact(monkeypatch)
    got = await query_flood_zone(lat, lon, client=_no_network())
    assert got is not None and got["fld_zone"] == zone


def test_the_artifact_is_registered_and_the_flood_fact_cites_it():
    from backend.provenance import FACTS

    spec = BY_ID["artifact.fema_flood_chicago"]
    assert spec.locator == "ingestion/data/fema_flood_chicago.json.gz" and spec.probe == "artifact_sidecar"
    assert FACTS["regulatory.flood"].source_id == "artifact.fema_flood_chicago"
