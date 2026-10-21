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
from backend.retrieval.regulatory.overlay_facts import describe_overlay
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS, OverlayResults, query_overlays_checked

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

# What a failed layer means to a reader, for partial_failures ("Couldn't check ...").
UNCHECKED_LABELS: dict[str, str] = {
    "planned_development": "planned development status",
    "lakefront_protection": "Lakefront Protection District",
    "pedestrian_street": "pedestrian street status",
    "landmark_building": "landmark designation",
    "historic_district": "historic and landmark districts",
    "national_register": "National Register districts",
    "special_district": "special districts",
    "fema_floodplain": "local floodplain map",
    "pmd_subarea": "PMD subareas",
    "tod_cta": "transit-served (TOD) area",
    "tod_metra": "transit-served (TOD) area",
    "adu_area": "ADU eligibility",
    "aro_zone": "ARO zone",
    "ssa": "Special Service Area",
}
_UNCHECKED_SUFFIX = "(City zoning map didn't answer)"


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
            "overlays": query_overlays_checked(lat, lon, client=client),
            "flood": query_flood_zone(lat, lon, client=client),
        }
        if not skip_brownfield:
            coros["brownfield"] = query_brownfield_sites(lat, lon, client=client)

        results_list = await asyncio.gather(*coros.values(), return_exceptions=True)
        results_map = dict(zip(coros.keys(), results_list))

        overlay_results = results_map["overlays"]
        if isinstance(overlay_results, Exception):
            # Nothing was checked, which is not the same as "in no overlay".
            overlay_results = OverlayResults(failed=list(OVERLAY_LAYERS))
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

        return _build_summary(
            overlay_results.hits, flood_result, brownfield_result,
            failed_layers=overlay_results.failed,
        )
    finally:
        if owns:
            await client.aclose()


def _build_summary(
    overlay_hits: list[tuple[int, dict]],
    flood_result: dict | None,
    brownfield_sites: list[dict],
    *,
    failed_layers: list[int] | None = None,
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

        if layer_type == "lakefront_protection":
            # The Lakefront Protection District legitimately extends inland; this flag
            # is correct for near-lake parcels. But the feature NAME is a subtype
            # ("Private Lakefront" / "Public Lakefront") that, used as a standalone
            # label, misleads a reader into thinking the parcel has private waterfront.
            # Lead with the regulatory district name and keep the subtype as a qualifier.
            display_name = layer_name
            description = feature_name or layer_name
        else:
            display_name = feature_name or layer_name
            description = layer_name

        # Layer-specific facts (the special district's real name, the ADU zone and its
        # limits, the PD number and PDF, the landmark's name and what it requires).
        facts = describe_overlay(layer_type, attrs)
        overlays.append(OverlayDistrict(
            layer_type=layer_type,
            name=facts["name"] or display_name,
            ordinance=ordinance,
            description=description,
            detail=facts["detail"],
            link=facts["link"],
        ))

        flag_field = FLAG_MAP.get(layer_type)
        if flag_field:
            flags[flag_field] = True
        # The Historic Districts layer flags the districts that are Chicago Landmark districts
        # (LANDMARK=Y); those need the same Commission approval as an individual landmark.
        if layer_type == "historic_district" and str(attrs.get("LANDMARK") or "").strip().upper() == "Y":
            flags["in_landmark_district"] = True

        if layer_type == "ssa":
            ssa_name = feature_name or attrs.get("SSA") or attrs.get("SSA_NUM")

    flood_zone = None
    flood_zone_subtype = None
    in_sfha = False
    if flood_result:
        flood_zone = flood_result.get("fld_zone")
        flood_zone_subtype = flood_result.get("zone_subty")
        in_sfha = flood_result.get("sfha_tf", "").upper() == "T"

    unchecked = list(dict.fromkeys(
        OVERLAY_LAYERS.get(lid, {}).get("type", f"layer_{lid}") for lid in failed_layers or []
    ))
    if failed_layers and len(set(failed_layers)) >= len(OVERLAY_LAYERS):
        data_gaps = [f"regulatory overlays {_UNCHECKED_SUFFIX}"]
    else:
        data_gaps = [
            f"{label} {_UNCHECKED_SUFFIX}"
            for label in dict.fromkeys(UNCHECKED_LABELS.get(t, t) for t in unchecked)
        ]

    return RegulatorySummary(
        overlays=overlays,
        unchecked_overlays=unchecked,
        data_gaps=data_gaps,
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
