"""Query FEMA National Flood Hazard Layer (NFHL) via ArcGIS REST."""

import asyncio
import logging

import httpx

from backend.retrieval.cache import TTLCache

log = logging.getLogger(__name__)

_fema_client: httpx.AsyncClient | None = None


def _get_fema_client() -> httpx.AsyncClient:
    global _fema_client
    if _fema_client is None or _fema_client.is_closed:
        _fema_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
    return _fema_client


_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="flood")
_NOT_FOUND = object()

# The registry id of this service (data_health/registry.py): the live failure rate and DATA_HEALTH_FAULT use it.
SOURCE_ID = "fed.fema.nfhl"

# hazards.fema.gov resets a large share of fresh connections (5 of 8 measured 2026-10-21, 2 of 3 on 2026-10-22; a
# kept-alive connection is not reset). A reset is a quick failure, so it is retried a few times; a timeout is not
# (it would make a Profile wait on a hung service). Every other failure is final.
_ATTEMPTS = 4
_RETRY_PAUSE_S = 0.3
_RETRYABLE = (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)

# FEMA relocated the public NFHL service from /gis/nfhl/rest/services to
# /arcgis/rest/services. Layer 28 is "Flood Hazard Zones".
FEMA_NFHL_URL = (
    "https://hazards.fema.gov/arcgis/rest/services"
    "/public/NFHL/MapServer/28/query"
)


class FloodLookupError(Exception):
    """FEMA's flood map did not answer (or answered with an error), so the point's flood zone is UNKNOWN.

    Distinct from ``None``, which is FEMA's answer that the point is in no mapped flood zone.
    """


async def query_flood_zone(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query the FEMA NFHL for the flood zone at a point.

    Returns ``{"fld_zone": "AE", "zone_subty": "...", "sfha_tf": "T"}``
    or ``None`` if the point is outside any mapped flood zone (FEMA answered, with no feature).
    Raises :class:`FloodLookupError` when FEMA could not be asked or did not answer properly; that is
    never cached, and never to be read as "not in a flood zone".
    """
    from backend.data_health import live

    # A forced fault beats the cache, so the dev flag reproduces the failure on a point already looked up.
    if live.fault("source", SOURCE_ID, SOURCE_ID):
        live.record(SOURCE_ID, False)
        raise FloodLookupError("forced by DATA_HEALTH_FAULT")

    key = f"flood:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    if client is None:
        client = _get_fema_client()
    try:
        data = await _fetch(client, params)
    except Exception as exc:
        log.warning("FEMA flood zone query failed for (%s, %s): %s", lat, lon, exc)
        live.record(SOURCE_ID, False)
        raise FloodLookupError(str(exc) or type(exc).__name__) from exc

    live.record(SOURCE_ID, True)
    features = data["features"]
    if not features:
        _cache.set(key, _NOT_FOUND)
        return None
    attrs = features[0].get("attributes", {})
    fld_zone = attrs.get("FLD_ZONE")
    if not fld_zone:
        _cache.set(key, _NOT_FOUND)
        return None
    result = {
        "fld_zone": fld_zone,
        "zone_subty": attrs.get("ZONE_SUBTY"),
        "sfha_tf": attrs.get("SFHA_TF"),
    }
    _cache.set(key, result)
    return result


async def _fetch(client: httpx.AsyncClient, params: dict) -> dict:
    """One answer from the service as a dict that has a ``features`` list, or an exception.

    ArcGIS answers some failures with HTTP 200 and an ``error`` body, or without ``features``: those are
    failures, not "no features".
    """
    for attempt in range(_ATTEMPTS):
        try:
            resp = await client.get(FEMA_NFHL_URL, params=params)
            break
        except _RETRYABLE:
            if attempt == _ATTEMPTS - 1:
                raise
            await asyncio.sleep(_RETRY_PAUSE_S)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise FloodLookupError(f"unexpected response: {data!r:.80}")
    if data.get("error"):
        raise FloodLookupError(f"service error: {data['error']!r:.200}")
    if not isinstance(data.get("features"), list):
        raise FloodLookupError("no 'features' in response")
    return data
