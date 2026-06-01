"""Opportunity Zone lookup via FCC census tract resolution + HUD ArcGIS."""

import logging

import httpx

log = logging.getLogger(__name__)

FCC_CENSUS_URL = "https://geo.fcc.gov/api/census/area"

HUD_OZ_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/Opportunity_Zones/FeatureServer/0/query"
)


async def resolve_census_tract(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Resolve lat/lon to an 11-character census tract FIPS code via the FCC API."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        resp = await client.get(
            FCC_CENSUS_URL,
            params={"lat": str(lat), "lon": str(lon), "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        fips = results[0].get("block_fips", "")
        if len(fips) >= 11:
            return fips[:11]
        return None
    except Exception as exc:
        log.warning("FCC census tract resolution failed for (%s, %s): %s", lat, lon, exc)
        return None
    finally:
        if owns:
            await client.aclose()


async def check_opportunity_zone(
    tract_fips: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """Check if a census tract is a designated Opportunity Zone via HUD ArcGIS.

    Returns ``{"tract": "17031...", "designated": True}`` or ``None``.
    """
    params = {
        "where": f"GEOID='{tract_fips}'",
        "outFields": "GEOID,DESIGNATED",
        "returnGeometry": "false",
        "f": "json",
    }
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(HUD_OZ_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        return {
            "tract": attrs.get("GEOID", tract_fips),
            "designated": bool(attrs.get("DESIGNATED")),
        }
    except Exception as exc:
        log.warning("HUD Opportunity Zone query failed for tract %s: %s", tract_fips, exc)
        return None
    finally:
        if owns:
            await client.aclose()
