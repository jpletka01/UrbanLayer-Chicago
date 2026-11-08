"""FEMA flood zone at a point: the committed Chicago NFHL artifact, else FEMA's NFHL ArcGIS service.

FEMA's hazards.fema.gov resets every TLS handshake from the production server (decision Item 84), so a point
inside the city is answered from ``ingestion/data/fema_flood_chicago.json.gz`` (FEMA's own layer 28 polygons,
clipped to the city, built by ``ingestion.build_flood_artifact``) by point-in-polygon, with no network call.
A point outside the artifact's coverage, or any point when the artifact is missing, still asks FEMA live.
"""

import asyncio
import gzip
import json
import logging
import threading

import httpx

from backend.config import get_settings
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


ARTIFACT_FILENAME = "fema_flood_chicago.json.gz"
# The artifact's registry id (data_health/registry.py).
ARTIFACT_SOURCE_ID = "artifact.fema_flood_chicago"

_art_lock = threading.Lock()
_art_loaded = False
_art: dict | None = None  # {"coverage": prepared geometry, "tree": STRtree, "geoms": [...], "attrs": [...], "retrieved": str}


def _load_artifact() -> None:
    """Build the STRtree once per process. A missing or invalid artifact leaves every point to the live service
    (which, from production, fails as "couldn't check"): never a silent "no flood zone"."""
    global _art_loaded, _art
    with _art_lock:
        if _art_loaded:
            return
        try:
            from shapely.geometry import shape
            from shapely.prepared import prep
            from shapely.strtree import STRtree

            path = get_settings().data_dir / ARTIFACT_FILENAME
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                raw = json.load(fh)
            geoms = [shape(f["g"]) for f in raw["features"]]
            attrs = [{"fld_zone": f["z"], "zone_subty": f.get("s"), "sfha_tf": f.get("t")} for f in raw["features"]]
            if not geoms:
                raise ValueError("no features")
            _art = {
                "coverage": prep(shape(raw["coverage"])), "tree": STRtree(geoms), "geoms": geoms, "attrs": attrs,
                "retrieved": raw.get("retrieved"),
            }
            log.info("FEMA flood artifact loaded: %d zones, retrieved %s", len(geoms), raw.get("retrieved"))
        except Exception as exc:  # noqa: BLE001 — degrade to the live service
            log.warning("FEMA flood artifact unavailable (%s): flood lookups go to FEMA live", exc)
            _art = None
        finally:
            _art_loaded = True


_NOT_COVERED = object()


def _from_artifact(lat: float, lon: float):
    """The artifact's answer: a zone dict, ``None`` (inside the city, in no mapped zone), or ``_NOT_COVERED``."""
    if not _art_loaded:
        _load_artifact()
    if _art is None:
        return _NOT_COVERED
    from shapely.geometry import Point

    pt = Point(lon, lat)
    if not _art["coverage"].contains(pt):
        return _NOT_COVERED
    hits = [int(i) for i in _art["tree"].query(pt, predicate="intersects")]
    if not hits:
        return None
    # Polygons that share an edge both match a point on it; the higher-risk zone (an SFHA) wins, then the
    # lowest index for a stable answer.
    best = min(hits, key=lambda i: (_art["attrs"][i]["sfha_tf"] != "T", i))
    return dict(_art["attrs"][best])


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
    """The FEMA NFHL flood zone at a point: from the committed artifact inside Chicago, else FEMA live.

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

    local = _from_artifact(lat, lon)
    if local is not _NOT_COVERED:
        return local

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
