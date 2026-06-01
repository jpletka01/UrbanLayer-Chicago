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
        skip_brownfield = workflow in ("business_launch",)

        coros: dict[str, object] = {
            "overlays": query_all_overlays(lat, lon, client=client),
            "flood": query_flood_zone(lat, lon, client=client),
        }
        if not skip_brownfield:
            coros["brownfield"] = query_brownfield_sites(lat, lon, client=client)

        results_list = await asyncio.gather(*coros.values(), return_exceptions=True)
        results_map = dict(zip(coros.keys(), results_list))

        overlay_hits = results_map["overlays"] if not isinstance(results_map["overlays"], Exception) else []
        flood_result = results_map["flood"] if not isinstance(results_map["flood"], Exception) else None
        brownfield_result = results_map.get("brownfield")
        if isinstance(brownfield_result, Exception):
            log.warning("Brownfield query failed: %s", brownfield_result)
            brownfield_result = []
        elif brownfield_result is None:
            brownfield_result = []

        if isinstance(results_map["overlays"], Exception):
            log.warning("Overlay queries failed: %s", results_map["overlays"])
        if isinstance(results_map["flood"], Exception):
            log.warning("Flood zone query failed: %s", results_map["flood"])

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
