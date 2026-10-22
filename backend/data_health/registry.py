"""The source registry: every data source the product shows, in one list.

A Python list of :class:`SourceSpec` (not JSON) so probes can reference code and tests can
import it. ``id`` is the stable slug WS0 puts on provenance entries; the rest says who owns
the source in the code, how to read its latest data date, and how stale is too stale.

Dates are judged on *content* where we can read it (``max(<date column>)``, release years,
tax year, ``current_through``), and on the publisher's own ``rowsUpdatedAt`` otherwise.
Frozen sources alarm on *change*, not age. An ``ack`` keeps a known-stale source amber until
its ``until`` date and lives here so each one is reviewed in a PR.

Completeness is enforced by ``tests/test_data_health_registry.py``: a Socrata dataset id, an
ArcGIS service URL, an ``OVERLAY_LAYERS`` id or a committed data artifact in the code without
an entry here fails CI, so a new source can't ship without a freshness rule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Literal

Tier = Literal[
    "official_record", "official_publication", "official_estimate",
    "our_calculation", "ai_extracted", "non_government", "internal",
]
Kind = Literal[
    "socrata", "arcgis_layer", "api", "http_file", "artifact",
    "local_db", "vector_index", "hand_table", "internal",
]
Severity = Literal["critical", "standard", "info"]
Surface = Literal["profile", "chat", "report", "discovery", "map"]

CITY = "city"      # data.cityofchicago.org
COOK = "cook"      # datacatalog.cookcountyil.gov
PORTAL_HOSTS = {CITY: "https://data.cityofchicago.org", COOK: "https://datacatalog.cookcountyil.gov"}

ZONING_MAPSERVER = "https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer"
KIT_WEEKLY_RUNS_URL = (
    "https://api.github.com/repos/jpletka01/UrbanLayer-Chicago/actions/workflows/kit-weekly.yml/runs"
)


@dataclass(frozen=True)
class Content:
    """How to read the date of the data itself (as opposed to when the publisher touched it)."""

    kind: Literal["max_date", "max_year", "newest_edit", "release_year"]
    column: str | None = None
    # A year column judged against another source's latest year, in releases (ACS):
    # warn at ``lag_warn`` releases behind, alarm at ``lag_alarm``.
    reference: Literal["census_latest_release"] | None = None
    lag_warn: int = 1
    lag_alarm: int = 2


@dataclass(frozen=True)
class Frozen:
    """A source that should never change. ``as_of`` is the publisher date we expect to see forever."""

    as_of: str
    label: str


@dataclass(frozen=True)
class Ack:
    reason: str
    until: date
    owner: str


@dataclass(frozen=True)
class ValueSpec:
    """A field's distinct values must stay inside a known set (WS6 M4). Exactly one of ``allowed``
    (exact values) or ``prefixes`` (each value must start with one of them) is used. ``where`` narrows
    the rows read (Address Points is county-wide, the contract is about Chicago)."""

    field: str
    allowed: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    where: str | None = None


@dataclass(frozen=True)
class Contract:
    """What a source must keep being: fields we read, the layer's name, a feature-count band, and
    value sets for fields whose meaning we derive facts from (WS6 plan §3.6)."""

    required_fields: tuple[str, ...] = ()
    layer_name: str | None = None
    count_band: tuple[int, int] | None = None
    values: tuple[ValueSpec, ...] = ()


@dataclass(frozen=True)
class SourceSpec:
    id: str
    name: str
    publisher: str
    tier: Tier
    kind: Kind
    locator: str
    owner_modules: tuple[str, ...]
    surfaces: tuple[Surface, ...] = ()
    fact_keys: tuple[str, ...] = ()
    severity: Severity = "standard"
    cadence_days: int | None = None
    content: Content | None = None
    warn_days: int | None = None
    alarm_days: int | None = None
    frozen: Frozen | None = None
    displayed_label: str | None = None
    contract: Contract | None = None
    ack: Ack | None = None
    # The probe that reads this source; None means the kind's generic probe. "none" = no
    # probe yet (the milestone that adds it is in ``note``).
    probe: str | None = None
    retired: bool = False
    # Judged on its findings (reachability, layer name, a known answer, coherence), not on a date.
    availability_only: bool = False
    # The named source whose health lets this one only warn (a source with a working fallback).
    warns_only_while_ok: str | None = None
    note: str = ""


def _band(n: int) -> tuple[int, int]:
    """A count band around a measured feature count (small layers get a tight, nonzero one)."""
    return max(1, int(n * 0.8)), int(n * 1.25) + 1


def _socrata(portal: str, dataset: str, id: str, name: str, publisher: str, owner: str, **kw) -> SourceSpec:
    kw.setdefault("tier", "official_record")
    return SourceSpec(id=id, name=name, publisher=publisher, kind="socrata", locator=f"{portal}:{dataset}",
                      owner_modules=(owner,), **kw)


def _layer(url: str, id: str, name: str, publisher: str, owner: str, **kw) -> SourceSpec:
    kw.setdefault("tier", "official_record")
    return SourceSpec(id=id, name=name, publisher=publisher, kind="arcgis_layer", locator=url,
                      owner_modules=(owner,), **kw)


CITY_GIS = "City of Chicago GIS"
COOK_ASSESSOR = "Cook County Assessor"
_ACK_UNTIL = date(2027, 1, 31)
_OWNER = "jack"
_PROP = ("profile", "chat", "report")
_OVERLAYS = "backend/retrieval/regulatory/overlays.py"

# Overlay layers: (layer id, OVERLAY_LAYERS type, the layer's own name, measured feature count).
# Layer 7 is deliberately absent (F8, 2026-10-02): a unit test asserts it stays out of OVERLAY_LAYERS.
_OVERLAY_ROWS: tuple[tuple[int, str, str, int], ...] = (
    (3, "lakefront_protection", "Lakefront", 2),
    (4, "pedestrian_street", "Pedestrian Street", 2),
    (5, "landmark_building", "Landmark Boundaries", 412),
    (6, "historic_district", "Historic Districts", 70),
    (8, "national_register", "National Register", 389),
    (9, "special_district", "Special District", 81),
    (11, "fema_floodplain", "FEMA Floodplain 2021", 10824),
    (12, "pmd_subarea", "PMD SubArea", 8),
    (13, "tod_cta", "TSL Station", 1),
    (17, "adu_area", "ADU Area", 10),
    (20, "aro_zone", "Affordable Requirements (ARO)", 54),
    (23, "ssa", "SSA", 58),
    (24, "tod_metra", "TSL METRA STATION", 1),
)


def _overlay(layer_id: int, kind: str, layer_name: str, count: int) -> SourceSpec:
    return _layer(
        f"{ZONING_MAPSERVER}/{layer_id}", f"chi.zoning.overlay.{kind}",
        f"Zoning overlay layer {layer_id}: {layer_name}", CITY_GIS, _OVERLAYS,
        surfaces=("profile", "chat", "report", "map"), fact_keys=(f"overlay.{kind}",),
        severity="critical", contract=Contract(layer_name=layer_name, count_band=_band(count)),
        note="Layer name and count band only: the layer has no edit-date field, so its date status is unknown, not red.",
    )


_BASE_SOURCES: tuple[SourceSpec, ...] = (
    # --- Regulatory: City Zoning MapServer -------------------------------------------------
    _layer(
        f"{ZONING_MAPSERVER}/1", "chi.zoning.districts", "Zoning districts (layer 1)", CITY_GIS,
        "backend/retrieval/zoning.py", surfaces=("profile", "chat", "report", "map"),
        fact_keys=("zoning.district",), severity="critical", cadence_days=7,
        content=Content("newest_edit", "UPDATE_TIMESTAMP"), warn_days=30, alarm_days=60,
        contract=Contract(
            required_fields=("ZONE_CLASS", "ORDINANCE_NUM", "ORDINANCE_DATE", "UPDATE_TIMESTAMP", "CLERK_URL", "PD_NUM"),
            layer_name="Zoning Boundaries", count_band=(14131, 15618),
        ),
    ),
    _layer(
        f"{ZONING_MAPSERVER}/2", "chi.zoning.overlay.planned_development", "Planned Developments (layer 2)", CITY_GIS,
        _OVERLAYS, surfaces=("profile", "chat", "report", "map"), fact_keys=("overlay.planned_development",),
        severity="critical", content=Content("newest_edit", "UPDATE_TIMESTAMP"), warn_days=90, alarm_days=270,
        contract=Contract(layer_name="Planned Developments", count_band=_band(1458)),
    ),
    *(_overlay(*row) for row in _OVERLAY_ROWS),
    _layer(
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28", "fed.fema.nfhl",
        "FEMA National Flood Hazard Layer (flood zones)", "FEMA", "backend/retrieval/regulatory/flood.py",
        surfaces=_PROP, fact_keys=("regulatory.flood",), severity="standard",
        contract=Contract(layer_name="Flood Hazard Zones"),
        availability_only=True,
        note="Availability and layer name. A known-answer parcel is M4's sentinel work.",
    ),
    _layer(
        "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/FRS_INTERESTS_ACRES/FeatureServer/0",
        "fed.epa.frs", "EPA Facility Registry Service (environmental interests)", "US EPA",
        "backend/retrieval/regulatory/environmental.py", surfaces=_PROP, fact_keys=("regulatory.environmental",),
        warn_days=30, alarm_days=120, contract=Contract(layer_name="FRS_INTERESTS_ACRES"),
    ),
    # --- Parcels and assessor (Cook County portal) ------------------------------------------
    _socrata(
        COOK, "pabr-t5kh", "cook.parcel_universe", "Assessor - Parcel Universe", COOK_ASSESSOR,
        "backend/retrieval/property/parcels.py", surfaces=_PROP, fact_keys=("parcel.identity",),
        severity="critical", cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "78yw-iddh", "cook.address_points", "Cook County Address Points", "Cook County GIS",
        "backend/retrieval/property/address_points.py", surfaces=_PROP, fact_keys=("parcel.identity",),
        severity="critical", warn_days=365, alarm_days=730,
        ack=Ack("Rows last updated 2024-04-08 ('as needed'). Mitigated by Parcel Addresses 3723-97qp, the second "
                "authoritative address-to-PIN source consulted when Address Points has no confident match.",
                _ACK_UNTIL, _OWNER),
    ),
    _socrata(
        COOK, "3723-97qp", "cook.parcel_addresses", "Assessor - Parcel Addresses", COOK_ASSESSOR,
        "backend/retrieval/property/parcel_addresses.py", surfaces=_PROP, fact_keys=("parcel.identity",),
        cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "uzyt-m557", "cook.assessor.values", "Assessor - Assessed Values", COOK_ASSESSOR,
        "backend/retrieval/property/assessments.py", surfaces=_PROP,
        fact_keys=("property.assessed_value", "property.assessment_history", "property.implied_market_value", "property.tax", "property.tax_estimate"), severity="critical", cadence_days=365,
        content=Content("max_year", "year"), warn_days=365, alarm_days=730,
    ),
    _socrata(
        COOK, "wvhk-k5uv", "cook.assessor.sales", "Assessor - Parcel Sales", COOK_ASSESSOR,
        "backend/retrieval/property/sales.py", surfaces=_PROP, fact_keys=("property.sales", "property.comps"),
        content=Content("max_date", "sale_date"), warn_days=60, alarm_days=120,
        note="Recording lag, so 60/120 days on the newest sale date.",
    ),
    _socrata(
        COOK, "x54s-btds", "cook.assessor.characteristics", "Assessor - Residential Improvement Characteristics",
        COOK_ASSESSOR, "backend/retrieval/property/characteristics.py", surfaces=_PROP,
        fact_keys=("property.building", "property.land_sqft", "property.bldg_sqft", "property.year_built", "property.stories", "property.units", "property.far_used"), cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "3r7i-mrz4", "cook.assessor.condo_characteristics", "Assessor - Residential Condominium Unit Characteristics",
        COOK_ASSESSOR, "backend/retrieval/property/building_facts.py", surfaces=_PROP,
        fact_keys=("property.building", "property.bldg_sqft", "property.year_built"), cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "csik-bsws", "cook.assessor.commercial_valuation", "Assessor - Commercial Valuation Data", COOK_ASSESSOR,
        "backend/retrieval/property/building_facts.py", surfaces=_PROP, fact_keys=("property.building", "property.bldg_sqft", "property.year_built", "property.units"),
        cadence_days=365, content=Content("max_year", "year"), warn_days=450, alarm_days=750,
    ),
    _socrata(
        COOK, "y282-6ig3", "cook.assessor.appeals", "Assessor - Appeals", COOK_ASSESSOR,
        "backend/retrieval/property/appeals.py", surfaces=("profile", "report"), fact_keys=("property.appeals",),
        cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "7pny-nedm", "cook.bor.appeals", "Board of Review Appeal Decision History", "Cook County Board of Review",
        "backend/retrieval/property/appeals.py", surfaces=("profile", "report"), fact_keys=("property.appeals",),
        cadence_days=365, warn_days=400, alarm_days=550,
    ),
    _socrata(
        COOK, "6yjf-dfxs", "cook.assessor.permits", "Assessor - Permits", COOK_ASSESSOR,
        "backend/retrieval/property/assessor_permits.py", surfaces=("profile",), fact_keys=("property.assessor_permits",),
        cadence_days=7, warn_days=14, alarm_days=45,
    ),
    _socrata(
        COOK, "55ju-2fs9", "cook.treasurer.tax_sale", "Treasurer - Annual Tax Sale", "Cook County Treasurer",
        "backend/retrieval/property/parcel_flags.py", surfaces=("profile",), fact_keys=("property.flags.tax_sale",),
        frozen=Frozen("2016-12-06", "tax sales 2014-2015; dataset not updated since 2016"),
        note="A flag that never fires for a recent sale; the Profile must not read 'none' as 'never sold'.",
    ),
    _socrata(
        COOK, "ydgz-vkrp", "cook.treasurer.scavenger_sale", "Treasurer - Scavenger Tax Sale", "Cook County Treasurer",
        "backend/retrieval/property/parcel_flags.py", surfaces=("profile",), fact_keys=("property.flags.tax_sale",),
        frozen=Frozen("2016-12-06", "scavenger sales through 2015; dataset not updated since 2016"),
    ),
    SourceSpec(
        id="cook.ptaxsim", name="PTAXSIM (property tax simulation database)", publisher=COOK_ASSESSOR,
        tier="official_estimate", kind="local_db", locator="backend/data/ptaxsim.db", probe="ptaxsim",
        owner_modules=("backend/retrieval/property/tax_estimate.py", "backend/retrieval/property/parcel_geometry.py"),
        surfaces=_PROP, fact_keys=("property.tax_estimate", "property.effective_rate", "property.tax_class_norm", "property.exemptions", "property.land_area", "property.land_sqft"), severity="critical",
        cadence_days=365, warn_days=800, alarm_days=1200,
        note="Content date = the last tax year in the database. Also probes the upstream release.",
    ),
    _layer(
        "https://gis.cookcountyil.gov/traditional/rest/services/cookVwrDynmc/MapServer/44", "cook.gis.parcels",
        "Cook County GIS parcels (layer 44)", "Cook County GIS", "backend/retrieval/property/parcels.py",
        surfaces=_PROP, fact_keys=("parcel.identity", "property.land_sqft", "property.bldg_sqft"), contract=Contract(layer_name="Current Parcel"),
        warns_only_while_ok="cook.parcel_universe",
        availability_only=True,
        note="Availability only. Warns and never alarms while the Parcel Universe fallback works.",
    ),
    # --- City data portal: live area statistics ---------------------------------------------
    _socrata(
        CITY, "ijzp-q8t2", "chi.crime", "Crimes - 2001 to Present", "Chicago Police Department",
        "backend/retrieval/crime.py", surfaces=("chat", "map"), fact_keys=("area.crime",), cadence_days=1,
        content=Content("max_date", "date"), warn_days=10, alarm_days=21, note="7-day lag by design.",
    ),
    _socrata(
        CITY, "v6vf-nfxy", "chi.311", "311 Service Requests", "City of Chicago", "backend/retrieval/three11.py",
        surfaces=("profile", "chat", "map"), fact_keys=("area.311", "property.311"), cadence_days=1,
        content=Content("max_date", "created_date"), warn_days=7, alarm_days=21,
    ),
    _socrata(
        CITY, "ydr8-5enu", "chi.permits", "Building Permits", "Department of Buildings", "backend/retrieval/buildings.py",
        surfaces=("profile", "chat", "map"), fact_keys=("area.permits", "property.permits"), cadence_days=1,
        content=Content("max_date", "issue_date"), warn_days=7, alarm_days=21,
    ),
    _socrata(
        CITY, "22u3-xenr", "chi.violations", "Building Violations", "Department of Buildings",
        "backend/retrieval/buildings.py", surfaces=("profile", "chat"), fact_keys=("area.violations", "property.violations"),
        cadence_days=1, content=Content("max_date", "violation_date"), warn_days=7, alarm_days=21,
    ),
    _socrata(
        CITY, "4ijn-s7e5", "chi.food_inspections", "Food Inspections", "Chicago Department of Public Health",
        "backend/retrieval/food_inspections.py", surfaces=("chat",), fact_keys=("area.food",), cadence_days=1,
        content=Content("max_date", "inspection_date"), warn_days=7, alarm_days=21,
    ),
    _socrata(
        CITY, "uupf-x98q", "chi.business_licenses", "Business Licenses - Current Active", "BACP",
        "backend/retrieval/business.py", surfaces=("chat",), fact_keys=("area.business",), cadence_days=1,
        content=Content("max_date", "date_issued"), warn_days=3, alarm_days=14,
    ),
    _socrata(
        CITY, "bbyy-e7gq", "chi.divvy", "Divvy Bicycle Stations", "CDOT", "backend/retrieval/neighborhood/divvy.py",
        surfaces=("profile",), fact_keys=("neighborhood.divvy",), cadence_days=1, warn_days=3, alarm_days=14,
    ),
    _socrata(
        CITY, "gc7y-n4xa", "chi.traffic", "Average Daily Traffic Counts", "CDOT",
        "backend/retrieval/neighborhood/traffic.py", surfaces=("profile", "chat"), fact_keys=("neighborhood.traffic",),
        cadence_days=1, warn_days=14, alarm_days=45,
    ),
    _socrata(
        CITY, "htai-wnw4", "chi.ward_offices", "Ward Offices", "City Clerk", "backend/retrieval/neighborhood/wards.py",
        surfaces=("profile",), fact_keys=("neighborhood.ward",), warn_days=30, alarm_days=90,
    ),
    _socrata(
        CITY, "kc9i-wq85", "chi.vacant_buildings", "Vacant and Abandoned Buildings - Violations",
        "Department of Buildings", "backend/retrieval/vacant.py", surfaces=("chat",), fact_keys=("area.vacant",),
        cadence_days=1, content=Content("max_date", "issued_date"), warn_days=120, alarm_days=365,
        ack=Ack("The publisher says 'updated daily' but rows last updated 2025-10-08 and the newest issued_date is "
                "2025-08-21: the feed has stopped. Chat states the date; nothing on the Profile depends on it.",
                _ACK_UNTIL, _OWNER),
    ),
    _socrata(
        CITY, "xq83-jr8c", "chi.energy_benchmarking", "Chicago Energy Benchmarking", "Department of Environment",
        "backend/retrieval/property/energy.py", surfaces=("profile",), fact_keys=("property.energy", "property.bldg_sqft"),
        cadence_days=365, content=Content("max_year", "data_year"), warn_days=730, alarm_days=1460,
        note="Warns when the newest data year is more than two years behind the current year.",
    ),
    _socrata(
        CITY, "aksk-kvfp", "chi.city_owned_land", "City-Owned Land Inventory", "DPD",
        "backend/retrieval/property/parcel_flags.py", surfaces=("profile",), fact_keys=("property.flags.city_owned",),
        cadence_days=1, warn_days=30, alarm_days=120,
    ),
    _socrata(
        CITY, "crg5-4zyp", "chi.scofflaw", "Building Code Scofflaw List", "Department of Law",
        "backend/retrieval/property/parcel_flags.py", surfaces=("profile",), fact_keys=("property.flags.scofflaw",),
        cadence_days=180, warn_days=200, alarm_days=400, note="Published twice a year.",
    ),
    _socrata(
        CITY, "7bzs-jsyj", "chi.str_prohibited", "House Share Prohibited Buildings List", "BACP",
        "backend/retrieval/property/parcel_flags.py", surfaces=("profile",), fact_keys=("property.flags.str_prohibited",),
        warn_days=180, alarm_days=540,
    ),
    _socrata(
        CITY, "syp8-uezg", "chi.building_footprints", "Building Footprints", "City of Chicago",
        "backend/retrieval/property/building_facts.py", surfaces=("profile",), fact_keys=("property.building", "property.bldg_sqft", "property.year_built", "property.stories"),
        frozen=Frozen("2015-08-15", "footprints from 2015"),
    ),
    _socrata(
        CITY, "igwz-8jzy", "chi.community_areas", "Boundaries - Community Areas", "City of Chicago",
        "backend/config.py", surfaces=("profile", "chat"), fact_keys=("geo.community_area",),
        frozen=Frozen("2025-04-22", "community area boundaries"),
    ),
    _socrata(
        CITY, "p293-wvbd", "chi.wards", "Boundaries - Wards (2023-)", "City of Chicago",
        "backend/retrieval/neighborhood/wards.py", surfaces=("profile",), fact_keys=("neighborhood.ward",),
        frozen=Frozen("2022-06-15", "2023 ward map; unchanged until the next remap"),
    ),
    _socrata(
        CITY, "kn9c-c2s2", "chi.socioeconomic_2008_2012", "Census Data - Selected socioeconomic indicators, 2008-2012",
        "City of Chicago", "backend/retrieval/neighborhood/demographics.py", tier="official_estimate",
        frozen=Frozen("2014-09-12", "2008-2012 poverty and unemployment"), retired=True,
        note="No longer read (WS0 M1); kept so old answers still resolve.",
    ),
    # --- Incentives --------------------------------------------------------------------------
    _socrata(
        CITY, "eejr-xtfb", "chi.tif.boundaries", "Boundaries - Tax Increment Financing Districts", "DPD",
        "backend/retrieval/incentives/tif.py", surfaces=("profile", "chat", "map"), fact_keys=("incentive.tif",),
        warn_days=400, alarm_days=700,
    ),
    _socrata(
        CITY, "72uz-ikdv", "chi.tif.projects", "TIF Annual Report - Projects", "City Clerk / DPD",
        "backend/retrieval/incentives/tif.py", surfaces=("profile", "chat"), fact_keys=("incentive.tif",),
        cadence_days=365, warn_days=400, alarm_days=540,
    ),
    _socrata(
        CITY, "qm7s-3ctt", "chi.tif.fund_analysis", "TIF Annual Report - Analysis of Special Tax Allocation Fund",
        "City Clerk / DPD", "backend/retrieval/incentives/tif.py", surfaces=("profile", "chat"),
        fact_keys=("incentive.tif",), cadence_days=365, warn_days=400, alarm_days=540,
    ),
    _socrata(
        CITY, "64xf-pyvh", "chi.enterprise_zones", "Boundaries - Enterprise Zones", "DPD",
        "backend/retrieval/incentives/enterprise_zones.py", surfaces=("profile", "chat"),
        fact_keys=("incentive.enterprise_zone",), warn_days=400, alarm_days=700,
    ),
    _socrata(
        CITY, "etqr-sz5x", "chi.sbif", "Financial Incentive Projects - SBIF", "DPD",
        "backend/retrieval/incentives/grant_programs.py", surfaces=("chat",), fact_keys=("incentive.grants",),
        cadence_days=90, warn_days=120, alarm_days=270,
    ),
    _socrata(
        CITY, "j7ew-b73u", "chi.nof_large", "Financial Incentive Projects - NOF Large", "DPD",
        "backend/retrieval/incentives/grant_programs.py", surfaces=("chat",), fact_keys=("incentive.grants",),
        cadence_days=90, warn_days=120, alarm_days=270,
        ack=Ack("Stale since 2023-09-19 against a quarterly claim; no successor dataset found. Only a project list "
                "in chat. Revisit when WS0 audits grant data.", _ACK_UNTIL, _OWNER),
    ),
    _socrata(
        CITY, "rym7-49n8", "chi.nof_small", "Financial Incentive Projects - NOF Small", "DPD",
        "backend/retrieval/incentives/grant_programs.py", surfaces=("chat",), fact_keys=("incentive.grants",),
        cadence_days=90, warn_days=120, alarm_days=270,
    ),
    _socrata(
        CITY, "s6ha-ppgi", "chi.aro_projects", "Affordable Rental Housing Developments", "DOH",
        "backend/retrieval/regulatory/aro_housing.py", surfaces=("chat",), fact_keys=("incentive.aro",),
        warn_days=365, alarm_days=730,
        note="Rows 2024-12-30; the metadata says 'current as of March 2013'. WS0 decides how it is labeled.",
    ),
    _layer(
        "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Opportunity_Zones/FeatureServer/13",
        "fed.hud.opportunity_zones", "Opportunity Zones", "HUD / US Treasury",
        "backend/retrieval/incentives/opportunity_zones.py", surfaces=("profile", "chat"),
        fact_keys=("incentive.opportunity_zone",), frozen=Frozen("2026-02-24", "the 2018 designation, re-published"),
        contract=Contract(layer_name="Opportunity_Zones"),
    ),
    _layer(
        "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Qualified_Census_Tracts/FeatureServer/0",
        "fed.hud.qct", "Qualified Census Tracts (LIHTC)", "HUD", "backend/retrieval/incentives/lihtc.py",
        surfaces=("profile", "chat"), fact_keys=("incentive.lihtc",), cadence_days=365, warn_days=400, alarm_days=700,
        contract=Contract(layer_name="QUALIFIED_CENSUS_TRACTS_2025"),
        note="The layer name carries the designation year; a rename to 2026 is the annual refresh, so it alarms for review.",
    ),
    _layer(
        "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/NMTC20/FeatureServer/0",
        "fed.cdfi.nmtc", "New Markets Tax Credit eligible tracts", "CDFI Fund / HUD",
        "backend/retrieval/incentives/nmtc.py", surfaces=("profile", "chat"), fact_keys=("incentive.nmtc",),
        cadence_days=365, warn_days=500, alarm_days=900, contract=Contract(layer_name="NMTC_16_20"),
    ),
    # --- Neighborhood ------------------------------------------------------------------------
    SourceSpec(
        id="census.reporter.acs", name="ACS 5-year tract data (via Census Reporter)", publisher="US Census Bureau",
        tier="official_estimate", kind="api", locator="https://api.censusreporter.org/1.0", probe="census_release",
        owner_modules=("backend/retrieval/neighborhood/census_tract.py",), surfaces=("profile", "chat", "report"),
        fact_keys=("area.tract",), severity="standard", cadence_days=365,
        content=Content("release_year"), warn_days=800, alarm_days=1200,
        note="Content date = the end year of the newest release. The page's period label is read from the data.",
    ),
    _socrata(
        CITY, "t68z-cikk", "chi.acs_community_area", "ACS 5 Year Data by Community Area", "City of Chicago",
        "backend/retrieval/neighborhood/demographics.py", tier="official_estimate", surfaces=("profile", "chat"),
        fact_keys=("area.community_area",), cadence_days=365,
        content=Content("max_year", "acs_year", reference="census_latest_release"),
        contract=Contract(required_fields=("community_area", "acs_year", "under_25_000", "_25_000_to_49_999",
                                           "_50_000_to_74_999", "_75_000_to_125_000", "_125_000")),
        note="Amber when one ACS release behind Census Reporter's latest, red when two behind.",
    ),
    SourceSpec(
        id="census.geocoder", name="Census Geocoder", publisher="US Census Bureau", tier="official_record", kind="api",
        locator="https://geocoding.geo.census.gov/geocoder", probe="census_geocoder",
        owner_modules=("backend/retrieval/geo.py",), surfaces=_PROP, fact_keys=("parcel.identity",),
        severity="critical", availability_only=True,
        note="Availability plus a known answer: 121 N LaSalle St geocodes within 50 m of the expected point.",
    ),
    SourceSpec(
        id="fed.fcc.area", name="FCC Census Block API", publisher="FCC", tier="official_record", kind="api",
        locator="https://geo.fcc.gov/api/census/area", probe="fcc_area", owner_modules=("backend/retrieval/geo.py",),
        surfaces=("profile", "chat"), fact_keys=("geo.census_tract",), availability_only=True,
        note="Availability plus a known answer: a Loop point returns a Cook County (17031) block.",
    ),
    SourceSpec(
        id="private.walkscore", name="Walk Score", publisher="Walk Score (private company)", tier="non_government",
        kind="api", locator="https://api.walkscore.com/score", probe="walkscore",
        owner_modules=("backend/retrieval/neighborhood/walkscore.py",), surfaces=("profile",),
        fact_keys=("neighborhood.walkscore",), availability_only=True, note="Availability, plus that the API key is accepted.",
    ),
    SourceSpec(
        id="chi.cta.gtfs", name="CTA GTFS feed", publisher="Chicago Transit Authority", tier="official_record",
        kind="http_file", locator="https://www.transitchicago.com/downloads/sch_data/google_transit.zip",
        probe="gtfs_head", owner_modules=("ingestion/build_transit_stations.py",), surfaces=("profile", "map"),
        fact_keys=("neighborhood.transit",), cadence_days=90, warn_days=120, alarm_days=365,
        note="HEAD only (Last-Modified); the 68 MB zip is never downloaded.",
    ),
    SourceSpec(
        id="chi.metra.gtfs", name="Metra GTFS feed", publisher="Metra", tier="official_record", kind="http_file",
        locator="https://schedules.metrarail.com/gtfs/schedule.zip", probe="gtfs_head",
        owner_modules=("ingestion/build_transit_stations.py",), surfaces=("profile", "map"),
        fact_keys=("neighborhood.transit",), cadence_days=90, warn_days=120, alarm_days=365,
    ),
    # --- Code and law ------------------------------------------------------------------------
    SourceSpec(
        id="code.municipal_text", name="Municipal Code of Chicago (text we serve)", publisher="American Legal Publishing",
        tier="official_publication", kind="artifact", locator="backend/code_vintage.json", probe="code_text",
        owner_modules=("backend/code_vintage.py", "backend/legislation/currency.py"),
        surfaces=("profile", "chat", "report"), fact_keys=("code.vintage",), severity="critical", cadence_days=30,
        warn_days=60, alarm_days=90,
        ack=Ack("American Legal publishes about four months behind Council: the newest export available (2026-10-21) is "
                "current through 2026-06-17, already 126 days old, so the 90-day alarm would fire on day one and every "
                "day until their next export. The monthly 'download a new export' reminder (.github/workflows/"
                "code-export-reminder.yml) carries the nudge instead; WS1 M7's checklist says what to do. Re-decide the "
                "thresholds against the publisher's real lag when this expires.", date(2026, 12, 15), _OWNER),
        note="Content date = current_through. Thresholds are WS1's. Reports the amendments passed since.",
    ),
    SourceSpec(
        id="code.qdrant_index", name="Municipal Code vector index (Qdrant)", publisher="UrbanLayer", tier="official_publication",
        kind="vector_index", locator="qdrant:municipal_code", probe="qdrant",
        owner_modules=("backend/retrieval/vector_search.py", "ingestion/push_index.py"),
        surfaces=("chat",), fact_keys=("code.vintage",), severity="critical", availability_only=True,
        note="Coherence: the served alias holds the vintage's chunk count (catches image/index skew after a push).",
    ),
    SourceSpec(
        id="artifact.zoning_cache", name="Precomputed zoning standards cache", publisher="UrbanLayer", tier="ai_extracted",
        kind="artifact", locator="ingestion/data/zoning_cache.json", probe="zoning_cache",
        owner_modules=("backend/zoning_cache.py", "backend/zoning_cache_build.py"), surfaces=("report",),
        fact_keys=("zoning.setbacks", "zoning.permitted_uses", "zoning.special_uses", "zoning.parking", "zoning.notes",
                   "zoning.envelope"),
        severity="critical", availability_only=True,
        note="Its vintage must equal the code vintage. M5 writes code_vintage into _meta; until then the rebase record is read.",
    ),
    SourceSpec(
        id="code.hand_table.zoning_definitions", name="Zoning district table (hand-maintained)", publisher="UrbanLayer",
        tier="official_publication", kind="hand_table", locator="backend/retrieval/zoning_definitions.py",
        probe="hand_table", owner_modules=("backend/retrieval/zoning_definitions.py",),
        surfaces=("profile", "chat", "report"), fact_keys=("zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit", "zoning.unit_yield", "zoning.adu", "zoning.tod_benefits"), severity="critical", availability_only=True,
        note="VERIFIED_AGAINST must equal code_vintage.current_through, so someone re-verifies after each refresh.",
    ),
    SourceSpec(
        id="chi.clerk.legislation", name="City Clerk eLMS API (legislation)", publisher="City Clerk", tier="official_record",
        kind="api", locator="https://api.chicityclerkelms.chicago.gov", probe="clerk_latest",
        owner_modules=("backend/retrieval/clerk.py", "backend/legislation/sync.py"), surfaces=("profile", "chat", "report"),
        fact_keys=("code.amendments",), severity="critical", cadence_days=1, warn_days=5, alarm_days=14,
        note="Content date = newest recordCreateDate (never introductionDate, which can be in the future).",
    ),
    # --- Committed artifacts -----------------------------------------------------------------
    SourceSpec(
        id="artifact.transit_stations", name="Transit stations (committed)", publisher="UrbanLayer from CTA/Metra GTFS",
        tier="official_record", kind="artifact", locator="ingestion/data/transit_stations.json", probe="artifact_sidecar",
        owner_modules=("ingestion/build_transit_stations.py",), surfaces=("profile", "map"),
        fact_keys=("neighborhood.transit",), cadence_days=180, warn_days=180, alarm_days=365,
        note="Build date from transit_stations.meta.json (written by the build script). The probe also notes when the "
             "CTA feed was last modified, so a rebuild is visible as due.",
    ),
    SourceSpec(
        id="artifact.chrs", name="Chicago Historic Resources Survey, orange/red (committed)", publisher="City of Chicago",
        tier="official_record", kind="artifact", locator="ingestion/data/chrs_orange_red.json.gz", probe="none",
        owner_modules=("backend/retrieval/property/chrs.py", "ingestion/build_chrs_artifact.py"), surfaces=("profile",),
        fact_keys=("property.flags.chrs",), frozen=Frozen("1996", "1996 survey, still legally in force"),
    ),
    SourceSpec(
        id="artifact.community_areas_geojson", name="Community area boundaries (committed)", publisher="City of Chicago",
        tier="official_record", kind="artifact", locator="ingestion/data/community_areas.geojson", probe="none",
        owner_modules=("ingestion/load_community_areas.py",), surfaces=("profile", "chat"),
        fact_keys=("geo.community_area",), frozen=Frozen("2025-04-22", "community area boundaries"),
    ),
    SourceSpec(
        id="internal.discovery_index", name="Property Discovery index", publisher="UrbanLayer", tier="our_calculation",
        kind="local_db", locator="backend/data/discovery_index.db", probe="discovery_index",
        owner_modules=("backend/discovery/parcel_index.py", "backend/discovery/index_build.py"),
        surfaces=("discovery", "profile"), fact_keys=("area.benchmarks",), cadence_days=30, warn_days=40, alarm_days=70,
        note="Rebuilt by a monthly timer. Absent in a dev checkout, where its status is unknown.",
    ),
    # --- Internal checks (their probes arrive with the milestone in ``note``) -----------------
    SourceSpec(
        id="eval.kit_weekly", name="Weekly parcel kit against production (Profile, no model)", publisher="UrbanLayer",
        tier="internal", kind="api", locator=KIT_WEEKLY_RUNS_URL, probe="kit_weekly",
        owner_modules=(".github/workflows/kit-weekly.yml",), severity="standard", cadence_days=7, warn_days=9, alarm_days=16,
        note="The newest successful run of .github/workflows/kit-weekly.yml (public GitHub Actions API; Mondays 10:00 UTC). "
             "A failed latest run alarms at once; no run yet reads unknown until the first scheduled Monday.",
    ),
    SourceSpec(
        id="internal.sentinels", name="Daily sentinels: the 12 kit parcels + a landmark control against the answer key",
        publisher="UrbanLayer", tier="internal", kind="internal", locator="backend/data_health/sentinels.json",
        probe="sentinels", owner_modules=("backend/data_health/sentinels.py",),
        surfaces=("profile", "chat", "report"), severity="critical", availability_only=True,
        note="Runs the production zoning and overlay lookups at each key parcel and compares the district and the "
             "overlay set with eval/kit/parcels.json. A mismatch is either a data change to review (re-key) or a bug "
             "(the F8 landmark misread). Cost: about 15 City map calls per parcel a day; no model.",
    ),
    SourceSpec(
        id="internal.checker", name="The data-health checker itself (dead-man)", publisher="UrbanLayer", tier="internal",
        kind="internal", locator="backend/data/data_health.db", probe="checker",
        owner_modules=("backend/data_health/check.py",), severity="critical", cadence_days=1, warn_days=1, alarm_days=3,
        note="Its last finished run. The real dead-man is /health (checker: ok|late) plus the Sentry Cron monitor "
             "and the scheduled GitHub workflow; this row colours the admin panel.",
    ),
    SourceSpec(
        id="internal.backups", name="Nightly database backup (age of the newest copy)", publisher="UrbanLayer",
        tier="internal", kind="internal", locator="backend/data/backup_status.json", probe="backup_status",
        owner_modules=("scripts/backup_db.sh",), severity="critical", availability_only=True,
        note="scripts/backup_db.sh writes backup_status.json beside chicago.db after each backup. The age rule "
             "(warn 30 h, alarm 36 h) is in the probe. Covers the on-box copy only; the off-box pull to the Mac is not seen here.",
    ),
)

# --- M4: contracts layered over the sources above -------------------------------------------------------

# Zone-class families in the City's layer 1 (verified 2026-10-22 over all 1,526 distinct values: the layer
# also holds typos like "RM4-.5", which still start with a known family). A value that starts with none of
# these is a new kind of district the zoning table does not know.
ZONE_FAMILIES = ("B1", "B2", "B3", "C1", "C2", "C3", "DC", "DR", "DS", "DX", "M1", "M2", "M3", "PD", "PMD", "POS", "RM", "RS", "RT", "T")

_VALUE_CONTRACTS: dict[str, tuple[ValueSpec, ...]] = {
    "chi.zoning.districts": (ValueSpec("ZONE_CLASS", prefixes=ZONE_FAMILIES),),
    "chi.zoning.overlay.historic_district": (ValueSpec("LANDMARK", allowed=("Y", "N")),),
    "cook.address_points": (ValueSpec("st_predir", allowed=("NORTH", "SOUTH", "EAST", "WEST"), where="inc_muni='Chicago'"),),
}
# Datasets whose row count is fixed by law or by the map: the wards (50), community areas (77), ward offices.
_COUNT_BANDS: dict[str, tuple[int, int]] = {
    "chi.wards": (50, 50), "chi.community_areas": (77, 77), "chi.ward_offices": (45, 55),
}

FIELDS_READ_PATH = Path(__file__).with_name("fields_read.json")


def load_fields_read(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """``{source_id: columns the owning module reads}`` (generated by ``contracts --scan``)."""
    try:
        raw = json.loads((path or FIELDS_READ_PATH).read_text())
    except (OSError, ValueError):
        return {}
    return {k: tuple(v) for k, v in raw.items() if isinstance(v, list)}


def _with_contracts(spec: SourceSpec, fields_read: dict[str, tuple[str, ...]]) -> SourceSpec:
    c = spec.contract
    fields = fields_read.get(spec.id, ())
    values = _VALUE_CONTRACTS.get(spec.id, ())
    band = _COUNT_BANDS.get(spec.id)
    if not (fields or values or band):
        return spec
    c = c or Contract()
    merged = tuple(dict.fromkeys((*c.required_fields, *fields)))
    return replace(spec, contract=replace(c, required_fields=merged, values=(*c.values, *values),
                                          count_band=c.count_band or band))


SOURCES: tuple[SourceSpec, ...] = tuple(_with_contracts(s, load_fields_read()) for s in _BASE_SOURCES)

BY_ID: dict[str, SourceSpec] = {s.id: s for s in SOURCES}


def socrata_locator(spec: SourceSpec) -> tuple[str, str]:
    """(portal, dataset id) of a Socrata source."""
    portal, _, dataset = spec.locator.partition(":")
    return portal, dataset


def layer_id_of(spec: SourceSpec) -> int | None:
    """The MapServer layer id of an ArcGIS source in the City Zoning service, else None."""
    if spec.kind == "arcgis_layer" and spec.locator.startswith(ZONING_MAPSERVER + "/"):
        return int(spec.locator.rsplit("/", 1)[1])
    return None
