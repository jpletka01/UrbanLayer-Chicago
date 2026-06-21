"""Cook County GIS parcel lookup — lat/lon to PIN14.

Primary: ArcGIS spatial query on Cook County GIS MapServer layer 44.
Fallback: Socrata Parcel Universe (pabr-t5kh) bounding-box query when GIS
is down or returns no results.
"""

import logging
import math

import httpx

from backend.config import get_settings
from backend.retrieval.cache import TTLCache
from backend.retrieval.socrata import socrata_get

log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="parcels")
_NOT_FOUND = object()

def _esri_to_geojson(esri_geom: dict | None) -> dict | None:
    """Convert Esri JSON rings to GeoJSON Polygon."""
    if not esri_geom:
        return None
    rings = esri_geom.get("rings")
    if not rings:
        return None
    return {"type": "Polygon", "coordinates": rings}


PARCEL_QUERY_URL = (
    "https://gis.cookcountyil.gov/traditional/rest/services"
    "/cookVwrDynmc/MapServer/44/query"
)

_BBOX_DELTA = 0.002  # ~220m at Chicago's latitude

# With server-side distance ordering the bbox fallback only needs the nearest few
# rows — a small window the dense-area row cap can never truncate past. (Without
# ordering, a 2000-row cap still evicted the true nearest in Lincoln Park and
# returned a neighbor parcel — see 2026-06-21_resolver-investigation.md.)
_SOCRATA_NEAREST_LIMIT = 64

# Hard cap on the GIS point query. Cook County GIS is intermittently down; a bounded
# timeout keeps a hanging GIS call from stretching the report request (and its
# memory-pressure window) before the Socrata fallback fires.
_GIS_TIMEOUT_S = 8.0


def _distance_order_expr(lat: float, lon: float) -> str:
    """SoQL ``$order`` expression: squared planar distance from each parcel's
    (lat, lon) to the query point. Pushes nearest-first to the server so the
    row cap returns the *closest* parcels, not an arbitrary truncated slice —
    the bug that returned a wrong neighbor in dense blocks. (lon is negative in
    Chicago, hence the parenthesised subtraction.)"""
    return f"(lat-{lat})*(lat-{lat})+(lon-({lon}))*(lon-({lon}))"


async def lookup_parcel(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Query Cook County for the parcel at a point.

    Tries ArcGIS first, falls back to Socrata Parcel Universe if GIS
    returns nothing (service has been intermittently/fully down since
    mid-2026 due to broken spatial index).
    """
    key = f"parcel:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    result = await _lookup_parcel_gis(lat, lon, client=client)
    if result is None:
        result = await _lookup_parcel_socrata(lat, lon, client=client)
    if result is None:
        _cache.set(key, _NOT_FOUND)
    else:
        _cache.set(key, result)
    return result


async def lookup_parcel_by_pin(
    pin14: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Resolve a parcel directly from a known PIN — no coordinate round-trip.

    Used when the PIN is already authoritative (supplied, or derived via the
    Address Points address→PIN map). Returns the **same dict shape** as
    `_lookup_parcel_socrata` so `_build_summary` is identical downstream. Pure
    Socrata (Parcel Universe), so it is correct throughout the GIS outage.
    Geometry is None (Parcel Universe has no polygon; GIS layer is down).
    """
    settings = get_settings()
    key = f"parcel_pin:{pin14}"
    cached = _cache.get(key)
    if cached is _NOT_FOUND:
        return None
    if cached is not None:
        return cached

    params = {
        "$where": f"pin='{pin14}'",
        "$select": "pin,pin10,class,lat,lon,zip_code,township_name,nbhd_code,tax_code",
        "$limit": 1,
    }
    try:
        rows = await socrata_get(
            settings.dataset_ccao_parcels,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )
    except Exception as exc:
        log.warning("Parcel-by-PIN lookup failed for %s: %s", pin14, exc)
        return None

    if not rows:
        _cache.set(key, _NOT_FOUND)
        return None
    row = rows[0]
    result = {
        "pin14": str(row.get("pin", pin14)).replace("-", "").zfill(14),
        "bldg_class": row.get("class"),
        "bldg_sqft": None,
        "land_sqft": None,
        "total_value": None,
        "address": None,
        "geometry": None,
        "zip_code": row.get("zip_code"),
        "township_name": row.get("township_name"),
        "nbhd_code": row.get("nbhd_code"),
        "tax_code": row.get("tax_code"),
    }
    _cache.set(key, result)
    return result


async def _lookup_parcel_gis(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Primary: ArcGIS spatial point query on Cook County GIS."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(_GIS_TIMEOUT_S))
    try:
        # Pass an explicit per-request timeout so a shared client (e.g. the property
        # orchestrator's 15 s client) can't impose a longer stall, and use a single
        # attempt: the retry rarely helps Cook County GIS's broken spatial index and
        # only widens the request/contention window. GIS down → Socrata fallback.
        resp = await client.get(
            PARCEL_QUERY_URL, params=params, timeout=httpx.Timeout(_GIS_TIMEOUT_S)
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        pin_raw = attrs.get("PIN14") or attrs.get("PIN")
        if not pin_raw:
            return None
        pin14 = str(pin_raw).replace("-", "").zfill(14)
        geometry = _esri_to_geojson(features[0].get("geometry"))
        return {
            "pin14": pin14,
            "bldg_class": attrs.get("BLDGClass"),
            "bldg_sqft": attrs.get("BldgSqft"),
            "land_sqft": attrs.get("LandSqft"),
            "total_value": attrs.get("TotalValue"),
            "address": attrs.get("Address"),
            "geometry": geometry,
            "zip_code": attrs.get("ZipCode"),
            "township_name": attrs.get("Township"),
            "nbhd_code": None,
            "tax_code": None,
        }
    except Exception as exc:
        log.warning("GIS parcel lookup failed for (%s, %s): %s", lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()


async def _lookup_parcel_socrata(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Fallback: nearest parcel from Socrata Parcel Universe within a small bbox.

    The bbox bounds the scan; **server-side distance ordering** makes the row cap
    truncation-proof — the nearest parcels are returned first, so the true nearest
    is always in the window regardless of how dense the block is. If the ordered
    query is rejected (older SoQL), we fall back to an unordered bbox and **refuse
    on a full cap** rather than return a guess that may not be the real nearest.
    """
    settings = get_settings()
    where = (
        f"lat between '{lat - _BBOX_DELTA}' and '{lat + _BBOX_DELTA}' "
        f"and lon between '{lon - _BBOX_DELTA}' and '{lon + _BBOX_DELTA}'"
    )
    select = "pin,pin10,class,lat,lon,zip_code,township_name,nbhd_code,tax_code"

    async def _query(params: dict) -> list[dict] | None:
        return await socrata_get(
            settings.dataset_ccao_parcels,
            params,
            client=client,
            base_url=settings.cook_county_socrata_base,
            app_token=settings.cook_county_socrata_token or None,
        )

    try:
        rows: list[dict] | None
        try:
            # Primary: nearest-first, small window — truncation can't drop the true nearest.
            rows = await _query({
                "$where": where,
                "$select": select,
                "$order": _distance_order_expr(lat, lon),
                "$limit": _SOCRATA_NEAREST_LIMIT,
            })
        except Exception as exc:
            # Ordering unsupported/rejected → unordered bbox, but now truncation IS a
            # hazard, so refuse to guess when the result set hit the cap.
            log.warning(
                "Ordered parcel bbox query failed at (%s, %s): %s — retrying unordered",
                lat, lon, exc,
            )
            rows = await _query({
                "$where": where, "$select": select, "$limit": settings.limit_ccao_parcels,
            })
            if rows and len(rows) >= settings.limit_ccao_parcels:
                log.warning(
                    "Parcel bbox fallback hit the %d-row cap at (%s, %s) without distance "
                    "ordering; refusing to guess a nearest parcel (dense/condo area).",
                    settings.limit_ccao_parcels, lat, lon,
                )
                return None

        if not rows:
            return None
        # Defensive: with server ordering rows[0] is already nearest; recompute anyway.
        closest = min(rows, key=lambda r: _distance_sq(lat, lon, r))
        pin_raw = closest.get("pin", "")
        if not pin_raw:
            return None
        pin14 = str(pin_raw).replace("-", "").zfill(14)
        return {
            "pin14": pin14,
            "bldg_class": closest.get("class"),
            "bldg_sqft": None,
            "land_sqft": None,
            "total_value": None,
            "address": None,
            "geometry": None,
            "zip_code": closest.get("zip_code"),
            "township_name": closest.get("township_name"),
            "nbhd_code": closest.get("nbhd_code"),
            "tax_code": closest.get("tax_code"),
        }
    except Exception as exc:
        log.warning("Socrata parcel fallback failed for (%s, %s): %s", lat, lon, exc)
        return None


def _distance_sq(lat: float, lon: float, row: dict) -> float:
    """Squared Euclidean distance — good enough for nearest-neighbor in a small box."""
    try:
        rlat = float(row["lat"])
        rlon = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return math.inf
    return (lat - rlat) ** 2 + (lon - rlon) ** 2
