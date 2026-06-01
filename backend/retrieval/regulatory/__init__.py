"""Regulatory domain orchestrator.

Runs zoning overlay queries, FEMA flood zone lookup, and EPA brownfield
search in parallel and assembles a :class:`RegulatorySummary`.
"""

import asyncio
import logging

import httpx

from backend.models import OverlayDistrict, RegulatorySummary
from backend.retrieval.regulatory.environmental import query_brownfield_sites
from backend.retrieval.regulatory.flood import query_flood_zone
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS, query_all_overlays

log = logging.getLogger(__name__)

FLAG_MAP: dict[str, str] = {
    "planned_development": "in_planned_development",
    "lakefront_protection": "in_lakefront_protection",
    "pedestrian_street": "on_pedestrian_street",
    "landmark_district": "in_landmark_district",
    "historic_district": "in_historic_district",
    "landmark_building": "is_landmark_building",
    "national_register": "on_national_register",
    "special_district": "in_special_district",
    "pmd_subarea": "in_pmd",
    "tod_cta": "in_tod_area",
    "tod_metra": "in_tod_area",
    "adu_area": "in_adu_area",
    "aro_zone": "in_aro_zone",
    "ssa": "in_ssa",
}


async def regulatory_domain(
    lat: float,
    lon: float,
    *,
    workflow: str = "general",
    client: httpx.AsyncClient | None = None,
) -> RegulatorySummary:
    """Fetch all regulatory overlay, flood, and environmental data for a point."""
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        overlay_task = query_all_overlays(lat, lon, client=client)
        flood_task = query_flood_zone(lat, lon, client=client)
        brownfield_task = query_brownfield_sites(lat, lon, client=client)

        results = await asyncio.gather(
            overlay_task, flood_task, brownfield_task, return_exceptions=True,
        )

        overlay_hits = results[0] if not isinstance(results[0], Exception) else []
        flood_result = results[1] if not isinstance(results[1], Exception) else None
        brownfield_result = results[2] if not isinstance(results[2], Exception) else []

        if isinstance(results[0], Exception):
            log.warning("Overlay queries failed: %s", results[0])
        if isinstance(results[1], Exception):
            log.warning("Flood zone query failed: %s", results[1])
        if isinstance(results[2], Exception):
            log.warning("Brownfield query failed: %s", results[2])

        return _build_summary(overlay_hits, flood_result, brownfield_result)
    finally:
        if owns:
            await client.aclose()


def _build_summary(
    overlay_hits: list[tuple[int, dict]],
    flood_result: dict | None,
    brownfield_sites: list[dict],
) -> RegulatorySummary:
    overlays: list[OverlayDistrict] = []
    flags: dict[str, bool | str] = {}
    ssa_name: str | None = None

    for layer_id, attrs in overlay_hits:
        meta = OVERLAY_LAYERS.get(layer_id, {})
        layer_type = meta.get("type", f"layer_{layer_id}")
        layer_name = meta.get("name", f"Layer {layer_id}")

        feature_name = (
            attrs.get("NAME")
            or attrs.get("DIST_NAME")
            or attrs.get("PD_NAME")
            or attrs.get("name")
            or attrs.get("SSA_NAME")
            or attrs.get("AREA_NAME")
        )
        ordinance = attrs.get("ORDINANCE") or attrs.get("ORDINANCE_NUM") or attrs.get("ORD_NUM")

        overlays.append(OverlayDistrict(
            layer_type=layer_type,
            name=feature_name or layer_name,
            ordinance=ordinance,
            description=layer_name,
        ))

        flag_field = FLAG_MAP.get(layer_type)
        if flag_field:
            flags[flag_field] = True

        if layer_type == "ssa":
            ssa_name = feature_name or attrs.get("SSA") or attrs.get("SSA_NUM")

    flood_zone = None
    flood_zone_subtype = None
    in_sfha = False
    if flood_result:
        flood_zone = flood_result.get("fld_zone")
        flood_zone_subtype = flood_result.get("zone_subty")
        in_sfha = flood_result.get("sfha_tf", "").upper() == "T"

    return RegulatorySummary(
        overlays=overlays,
        in_planned_development=flags.get("in_planned_development", False),
        in_landmark_district=flags.get("in_landmark_district", False),
        is_landmark_building=flags.get("is_landmark_building", False),
        in_historic_district=flags.get("in_historic_district", False),
        on_national_register=flags.get("on_national_register", False),
        in_lakefront_protection=flags.get("in_lakefront_protection", False),
        on_pedestrian_street=flags.get("on_pedestrian_street", False),
        in_special_district=flags.get("in_special_district", False),
        in_pmd=flags.get("in_pmd", False),
        in_tod_area=flags.get("in_tod_area", False),
        in_adu_area=flags.get("in_adu_area", False),
        in_aro_zone=flags.get("in_aro_zone", False),
        in_ssa=flags.get("in_ssa", False),
        ssa_name=ssa_name,
        flood_zone=flood_zone,
        flood_zone_subtype=flood_zone_subtype,
        in_special_flood_hazard=in_sfha,
        brownfield_sites=brownfield_sites,
    )
