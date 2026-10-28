"""Where each Property Profile fact came from, and how current that is.

A fact a reader could act on carries a dated source: the official record it was read
from (layer, ordinance, feature), or the code section it is computed from, with the
date the source says it is current and the date we queried it. This is the data
behind "click a number, see the source" (V2); it makes a claim checkable instead of
asking to be trusted.

Every entry is a plain dict (JSON-safe), keyed by a stable fact id:

    zoning.district                    the district + the ordinance that set it
    zoning.far / .max_height /
      .min_lot_area_per_unit           the standard + the code section it comes from
    overlay.<layer_type>               each overlay found + the layer it came from
    parcel.identity                    which parcel, and how it was identified
    property.land_sqft / .bldg_sqft    the area figure + which dataset supplied it
    code.vintage                       how current the indexed Municipal Code is

Fields: ``label`` (plain words), ``kind`` (official_record | code_text | derived),
``source`` (the dataset or code), ``record_id``, ``url``, ``section`` (a code section
id the source viewer can open), ``as_of`` (when the source says its record last
changed / the code is current through), ``effective_date`` (when the rule took
effect, e.g. the ordinance date) and ``query_date`` (when we asked). Any may be None;
an entry always carries a ``query_date``.

Schema v2 (WS0 M2, see ``claude-context/guides/source-confidence.md``) adds, all additive:
``tier`` / ``source_id`` (who published it), ``as_of_basis`` / ``age_days`` (what the date
means), ``scope`` / ``geography`` / ``coverage`` (how much it covers), ``precision``,
``method_key`` / ``method`` (how it was made), ``value`` (the figure as displayed) and the
derived ``confidence`` / ``confidence_reasons``. ``kind`` stays one release as an alias of
``tier``. Entries are built through :func:`make_entry`; the confidence state is computed
once, in :func:`confidence_state`, and every surface reads it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.code_vintage import get_code_vintage
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS
from backend.retrieval.zoning_definitions import _parse_zone_prefix

log = logging.getLogger(__name__)

ZONING_LAYER = "City of Chicago Zoning Districts, Zoning MapServer layer 1"
CODE_SOURCE = "Municipal Code of Chicago, Title 17 (Zoning Ordinance)"

# Code sections each standard comes from, by district family. Pinned to the ingested
# code's section headings in tests/test_provenance.py. None = the code sets no such
# standard for the family (M districts have no height or per-unit standard).
BULK_SECTIONS: dict[str, dict[str, str | None]] = {
    "R": {"far": "17-2-0304-A", "max_height": "17-2-0311-A", "min_lot_area_per_unit": "17-2-0303-A"},
    "BC": {"far": "17-3-0403-A", "max_height": "17-3-0408-A", "min_lot_area_per_unit": "17-3-0402-A"},
    "M": {"far": "17-5-0404", "max_height": None, "min_lot_area_per_unit": None},
    "D": {"far": "17-4-0405-A", "max_height": "17-4-0407", "min_lot_area_per_unit": "17-4-0404-A"},
}

_BULK_LABELS = {
    "far": "Floor area ratio",
    "max_height": "Maximum building height",
    "min_lot_area_per_unit": "Minimum lot area per dwelling unit",
}

_LAYER_ID_BY_TYPE = {meta["type"]: lid for lid, meta in OVERLAY_LAYERS.items()}

_AREA_SOURCES = {
    "assessor": "Cook County Assessor (parcel characteristics)",
    "gis": "Cook County GIS parcel layer",
    "geometry": "Parcel polygon area (Cook County property-tax database)",
    "condo_unit": "Cook County Assessor condominium characteristics (one unit's area)",
    "commercial_valuation": "Cook County Assessor commercial valuation (economic-unit total)",
    "footprint": "City of Chicago building footprints (ground-floor area)",
    "energy_benchmark": "City of Chicago energy benchmarking (owner-reported gross floor area)",
}


def bulk_family(zone_class: str | None) -> str | None:
    """'R', 'BC', 'M', 'D' for the districts that have bulk tables; None for PD/POS/unknown."""
    if not zone_class:
        return None
    prefix, _ = _parse_zone_prefix(zone_class.strip().upper())
    if prefix in ("RS", "RT", "RM"):
        return "R"
    if prefix in ("B1", "B2", "B3", "C1", "C2", "C3"):
        return "BC"
    if prefix in ("M1", "M2", "M3"):
        return "M"
    if prefix in ("DX", "DC", "DR", "DS"):
        return "D"
    return None


# --- schema v2 -----------------------------------------------------------------------------------

Tier = Literal[
    "official_record", "official_publication", "official_estimate",
    "our_calculation", "ai_extracted", "non_government",
]
MethodKey = Literal[
    "recorded", "published_text", "code_table", "hand_reviewed",
    "survey_estimate", "government_model", "bracket_median", "calculation", "keyword_grouping",
    "ai_read_code", "ai_read_ordinance", "ai_read_filing",
    "commercial_index",
]
# ``record_updated`` is the one addition to the guide's list: the date one record last changed
# (a zoning district's map edit). It says nothing about how current the dataset is, so it
# never triggers the 24-month ``old_source`` rule that ``source_updated`` does.
AsOfBasis = Literal[
    "source_updated", "record_updated", "current_through", "period_end", "vintage", "tax_year", "queried",
]
# ``puma`` (WS4 PR2): a Public Use Microdata Area, a union of tracts that does not nest in community areas.
Scope = Literal["parcel", "address", "radius", "tract", "puma", "community_area", "city", "county"]
Confidence = Literal["standard", "low", "withheld"]
# What kind of n a coverage figure counts, which decides which n rule applies (guide §3):
# ``area_sample`` = a median/rate from a sample of records; ``comps`` = a comparable-sales set.
# None = a list where every record is shown, or a share with no sample-size rule.
SampleKind = Literal["area_sample", "comps"]

# Strongest to weakest, by the guide's letters A-F. A calculation is never read as stronger
# than its weakest input.
TIER_ORDER: tuple[str, ...] = (
    "official_record", "official_publication", "official_estimate",
    "our_calculation", "ai_extracted", "non_government",
)
_KIND_BY_TIER = {"official_record": "official_record", "official_publication": "code_text"}

# Thresholds (guide §3). Boundary tests pin them: a value exactly at a constant is not past it.
HIDE_COVERAGE_BELOW = 0.10
FADE_COVERAGE_BELOW = 0.25
FADE_CV_ABOVE = 0.30
HIDE_CV_ABOVE = 0.50
HIDE_N_BELOW = 30
COMPS_FADE_N_BELOW = 5
COMPS_HIDE_N_BELOW = 3
AI_CORROBORATED_RATE = 0.95
AI_CORROBORATED_MIN_N = 30
OLD_SOURCE_DAYS = 730  # "more than 24 months" (guide §4.1)
_OLD_SOURCE_BASES = ("source_updated", "vintage", "period_end", "tax_year")

METHOD_TEXT: dict[str, str] = {
    "recorded": "Read as recorded by the publisher",
    "published_text": "Quoted from the published Municipal Code",
    "code_table": "Our Title 17 table, checked against the code text",
    "hand_reviewed": "An ordinance passed but not yet in the published code, read by us",
    "survey_estimate": "Census survey estimate",
    "government_model": "A government agency's model",
    "bracket_median": "Median interpolated from published brackets",
    "calculation": "Our calculation",
    "keyword_grouping": "Our grouping of free text into categories",
    "ai_read_code": "Read by AI from Municipal Code text",
    "ai_read_ordinance": "Read by AI from a scanned ordinance",
    "ai_read_filing": "Read by AI from the applicant's filing",
    "commercial_index": "A private company's index",
}


class Coverage(BaseModel):
    """How much of a universe a figure rests on. ``None`` on a parcel record means "not applicable"."""

    n: int | None = None
    share: float | None = None
    universe: str | None = None
    unit: str | None = None
    sample: SampleKind | None = None


class Agreement(BaseModel):
    n: int
    agree: int


class Precision(BaseModel):
    """Published error (``moe`` at ``moe_level``, ``cv``) or, for an AI reading, a measured agreement rate."""

    moe: float | None = None
    moe_level: float | None = None
    cv: float | None = None
    # How a margin we derived ourselves was derived (``acs_handbook_median``: the ACS Handbook's standard
    # error of an interpolated median). Absent when the publisher states the margin.
    moe_method: str | None = None
    agreement: Agreement | None = None


class ProvenanceEntry(BaseModel):
    """One fact's source, date, coverage, precision and method. Dumps to the dict the wire carries."""

    model_config = ConfigDict(extra="forbid")

    # v1 fields (unchanged meaning)
    label: str
    kind: Literal["official_record", "code_text", "derived"]
    source: str | None = None
    record_id: str | None = None
    url: str | None = None
    section: str | None = None
    as_of: str | None = None
    effective_date: str | None = None
    query_date: str
    note: str | None = None
    # 1. who published it
    tier: Tier
    source_id: str | None = None
    # 2. how old
    as_of_basis: AsOfBasis
    period: str | None = None
    age_days: int | None = None
    # 3. how much it covers
    scope: Scope | None = None
    geography: str | None = None
    coverage: Coverage | None = None
    # 4. how precise
    precision: Precision | None = None
    # 5. how made
    method_key: MethodKey
    method_params: dict[str, Any] | None = None
    method: str
    # calculations: what they rest on, and the weakest of it
    inputs: list[str] | None = None
    basis_tier: Tier | None = None
    # AI readings: a deterministic check agreed (guide §3)
    corroborated: bool | None = None
    # derived, set once by make_entry
    confidence: Confidence = "standard"
    confidence_reasons: list[str] = Field(default_factory=list)
    value: str | int | float | bool | None = None

    def to_dict(self) -> dict:
        """The wire dict. The v1 keys are always present (``note`` too: v1 carried it as null);
        v2 extras only when set."""
        d = self.model_dump(mode="json")
        always = {*_V1_KEYS, "tier", "as_of_basis", "method_key", "method", "confidence", "confidence_reasons"}
        for nested in ("coverage", "precision"):  # "not published" stays absent, never a block of nulls
            if isinstance(d.get(nested), dict):
                d[nested] = {k: v for k, v in d[nested].items() if v is not None} or None
        return {k: v for k, v in d.items() if k in always or (v is not None and v != [])}


_V1_KEYS = ("label", "kind", "source", "record_id", "url", "section", "as_of", "effective_date", "query_date", "note")


@dataclass(frozen=True)
class FactSpec:
    """A figure's static identity. Per-source facts (publisher, tier, vintage) live in the
    data-health registry, read by ``source_id``; a spec only names the source."""

    label: str
    source_id: str
    method_key: str
    scope: str
    tier: str
    # other sources that can supply the same recorded figure (lot/building area, parcel identity)
    alt_source_ids: tuple[str, ...] = ()
    # sources the figure is computed or located from in some variants (a polygon area, the nearest
    # parcel, the geocode). They carry the fact id in the registry, but the figure is then tier D,
    # so tier-equality is not asserted for them
    input_source_ids: tuple[str, ...] = ()


def _overlay_facts() -> dict[str, FactSpec]:
    return {
        f"overlay.{meta['type']}": FactSpec(
            label=meta.get("name", meta["type"]), source_id=f"chi.zoning.overlay.{meta['type']}",
            method_key="recorded", scope="parcel", tier="official_record",
        )
        for meta in OVERLAY_LAYERS.values()
    }


# Every fact id the Profile emits today. A fact names its source; the registry's ``fact_keys``
# is checked against this in tests/test_provenance.py. Ids are a stable contract: a rename
# ships with a migration map here, because stored answers and reports reference them.
FACTS: dict[str, FactSpec] = {
    "zoning.district": FactSpec("Zoning district", "chi.zoning.districts", "recorded", "parcel", "official_record"),
    "zoning.far": FactSpec("Floor area ratio", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    "zoning.max_height": FactSpec("Maximum building height", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    "zoning.min_lot_area_per_unit": FactSpec("Minimum lot area per dwelling unit", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    **_overlay_facts(),
    "parcel.identity": FactSpec(
        "Parcel identity", "cook.address_points", "recorded", "parcel", "official_record",
        alt_source_ids=("cook.parcel_addresses",), input_source_ids=("cook.parcel_universe", "cook.gis.parcels", "census.geocoder"),
    ),
    "property.land_sqft": FactSpec(
        "Lot area", "cook.assessor.characteristics", "recorded", "parcel", "official_record",
        alt_source_ids=("cook.gis.parcels",), input_source_ids=("cook.ptaxsim",),
    ),
    "property.bldg_sqft": FactSpec(
        "Building area", "cook.assessor.characteristics", "recorded", "parcel", "official_record",
        alt_source_ids=(
            "cook.gis.parcels", "cook.assessor.condo_characteristics", "cook.assessor.commercial_valuation",
            "chi.building_footprints", "chi.energy_benchmarking",
        ),
    ),
    "code.vintage": FactSpec(
        "Municipal Code vintage", "code.municipal_text", "published_text", "city", "official_publication",
        input_source_ids=("code.qdrant_index",),  # the index we answer from must be the same vintage
    ),
    "regulatory.upcoming_zoning.records": FactSpec(
        "Current zoning filings", "chi.clerk.legislation", "recorded", "radius", "official_record",
    ),
    "regulatory.upcoming_zoning.placement": FactSpec(
        "Upcoming zoning placement", "cook.address_points", "calculation", "radius", "our_calculation",
        input_source_ids=("chi.clerk.legislation", "internal.pending_legislation"),
    ),
    "regulatory.upcoming_zoning.text_impacts": FactSpec(
        "Pending Title 17 amendments", "chi.clerk.legislation", "recorded", "city", "official_record",
    ),
    "regulatory.upcoming_zoning.relevance": FactSpec(
        "Pending amendment relevance to this parcel", "internal.pending_impact_review", "calculation", "parcel",
        "our_calculation", input_source_ids=("chi.clerk.legislation", "internal.pending_legislation"),
    ),
}


def _rec(label: str, source_id: str, scope: str = "parcel", **kw) -> FactSpec:
    return FactSpec(label, source_id, "recorded", scope, "official_record", **kw)


def _calc(label: str, source_id: str, scope: str = "parcel", method_key: str = "calculation") -> FactSpec:
    return FactSpec(label, source_id, method_key, scope, "our_calculation")


# WS0 M5: what the $25 report reads from the precomputed zoning cache. The cache's setbacks, uses, parking and
# notes are read from the code text by AI (tier E); FAR, height and the lot standards stay with the Title 17
# table (``zoning.far`` etc., tier B). The envelope is our arithmetic on the AI-read setbacks.
FACTS.update({
    "zoning.setbacks": FactSpec("Required setbacks", "artifact.zoning_cache", "ai_read_code", "parcel", "ai_extracted"),
    "zoning.permitted_uses": FactSpec("Permitted uses", "artifact.zoning_cache", "ai_read_code", "parcel", "ai_extracted"),
    "zoning.special_uses": FactSpec("Special uses", "artifact.zoning_cache", "ai_read_code", "parcel", "ai_extracted"),
    "zoning.parking": FactSpec("Parking requirements", "artifact.zoning_cache", "ai_read_code", "parcel", "ai_extracted"),
    "zoning.notes": FactSpec("Zoning notes", "artifact.zoning_cache", "ai_read_code", "parcel", "ai_extracted"),
    "zoning.envelope": FactSpec("Buildable envelope", "artifact.zoning_cache", "calculation", "parcel", "our_calculation"),
})


_TRACT_FIELDS = {
    "population": "Tract population",
    "median_household_income": "Tract median household income",
    "per_capita_income": "Tract per-capita income",
    "median_home_value": "Tract median home value",
    "median_gross_rent": "Tract median gross rent",
    "owner_occupied_pct": "Tract owner-occupied share",
    "vacancy_rate": "Tract housing vacancy rate",
    "poverty_rate": "Tract poverty rate",
    "unemployment_rate": "Tract unemployment rate",
    "bachelors_or_higher_pct": "Tract share with a bachelor's degree or more",
    "foreign_born_pct": "Tract foreign-born share",
    "city_median_income": "Chicago median household income",
    "county_median_income": "Cook County median household income",
}

# WS0 M3: every figure the Profile shows (and every area feed a chat turn can carry) names its
# source here. Ids are a stable contract, like the facts above.
FACTS.update({
    "property.assessed_value": _rec("Assessed value", "cook.assessor.values"),
    "property.assessment_history": _rec("Assessment history", "cook.assessor.values"),
    "property.implied_market_value": _calc("Implied market value", "cook.assessor.values"),
    "property.tax_estimate": FactSpec(
        "Estimated annual tax", "cook.ptaxsim", "government_model", "parcel", "official_estimate",
        input_source_ids=("cook.assessor.values",),  # the fallback estimate is our arithmetic on the assessed value
    ),
    "property.effective_rate": _calc("Effective tax rate", "cook.ptaxsim"),
    "property.tax_class_norm": _calc("Class-norm effective tax rate", "cook.ptaxsim", scope="city"),
    "property.exemptions": FactSpec("Tax exemptions", "cook.ptaxsim", "government_model", "parcel", "official_estimate"),
    "property.sales": _rec("Sales history", "cook.assessor.sales"),
    "property.year_built": _rec(
        "Year built", "cook.assessor.characteristics",
        alt_source_ids=("cook.assessor.condo_characteristics", "cook.assessor.commercial_valuation", "chi.building_footprints"),
    ),
    "property.stories": _rec("Stories", "cook.assessor.characteristics", alt_source_ids=("chi.building_footprints",)),
    "property.units": _rec("Dwelling units", "cook.assessor.characteristics", alt_source_ids=("cook.assessor.commercial_valuation",)),
    "property.energy": _rec("Energy benchmarking", "chi.energy_benchmarking"),
    "property.assessor_permits": _rec("Assessor permits", "cook.assessor.permits"),
    "property.appeals": _rec("Assessment appeals", "cook.assessor.appeals", alt_source_ids=("cook.bor.appeals",)),
    "property.flags.chrs": _rec("Historic Resources Survey rating", "artifact.chrs"),
    "property.flags.tax_sale": _rec("Tax-sale history", "cook.treasurer.tax_sale", alt_source_ids=("cook.treasurer.scavenger_sale",)),
    "property.flags.city_owned": _rec("City-owned land", "chi.city_owned_land"),
    "property.flags.scofflaw": _rec("Building-code scofflaw list", "chi.scofflaw"),
    "property.flags.str_prohibited": _rec("Short-term-rental prohibited building", "chi.str_prohibited"),
    "property.violations": _rec("Building violations at the address", "chi.violations", scope="address"),
    "property.311": _rec("311 requests at the address", "chi.311", scope="address"),
    "property.far_used": _calc("FAR used", "cook.assessor.characteristics"),
    "zoning.unit_yield": _calc("Maximum units by lot area", "code.hand_table.zoning_definitions"),
    "zoning.adu": _calc("Accessory dwelling unit status", "code.hand_table.zoning_definitions"),
    "zoning.tod_benefits": _calc("Transit-served benefits", "code.hand_table.zoning_definitions"),
    "regulatory.flood": _rec("FEMA flood zone", "fed.fema.nfhl"),
    "regulatory.environmental": _rec("EPA-registered sites near the parcel", "fed.epa.frs", scope="radius"),
    "incentive.tif": _rec("TIF district", "chi.tif.boundaries", alt_source_ids=("chi.tif.projects", "chi.tif.fund_analysis")),
    "incentive.enterprise_zone": _rec("Enterprise zone", "chi.enterprise_zones"),
    "incentive.opportunity_zone": _rec("Opportunity zone", "fed.hud.opportunity_zones", scope="tract"),
    "incentive.lihtc": _rec("Qualified census tract", "fed.hud.qct", scope="tract"),
    "incentive.nmtc": _rec("New Markets Tax Credit tract", "fed.cdfi.nmtc", scope="tract"),
    "incentive.grants": _rec("City incentive grants in the area", "chi.sbif", scope="community_area", alt_source_ids=("chi.nof_large", "chi.nof_small")),
    "incentive.aro": _rec("Affordable rental housing in the area", "chi.aro_projects", scope="community_area"),
    "neighborhood.ward": _rec("Ward and alderman", "chi.wards", alt_source_ids=("chi.ward_offices",)),
    "geo.community_area": _rec("Community area", "chi.community_areas", alt_source_ids=("artifact.community_areas_geojson",)),
    "neighborhood.transit": _rec("Nearest transit", "chi.cta.gtfs", scope="radius", alt_source_ids=("chi.metra.gtfs", "artifact.transit_stations")),
    "neighborhood.divvy": _rec("Nearest Divvy station", "chi.divvy", scope="radius"),
    "neighborhood.traffic": _rec("Daily traffic on the nearest counted street", "chi.traffic", scope="radius"),
    "neighborhood.walkscore": FactSpec("Walk Score", "private.walkscore", "commercial_index", "address", "non_government"),
    **{
        f"area.tract.{k}": FactSpec(label, "census.reporter.acs", "survey_estimate",
                                    "city" if k == "city_median_income" else "county" if k == "county_median_income" else "tract",
                                    "official_estimate")
        for k, label in _TRACT_FIELDS.items()
    },
    # WS4 PR2: current official rent. The community-area figure is our aggregation of the Census's bracket
    # counts (tier D on a C input); the bedroom figures are the Census's own published medians, for the
    # parcel's tract or, where that is suppressed or too uncertain, its PUMA (the entry's scope says which).
    "area.rent.community_area": FactSpec(
        "Community-area median gross rent", "artifact.rent_by_area", "bracket_median", "community_area", "our_calculation"),
    **{
        f"area.rent.{g}": FactSpec(f"Median gross rent, {label}", "census.reporter.acs", "survey_estimate", "tract", "official_estimate")
        for g, label in (("1_bedroom", "1 bedroom"), ("2_bedrooms", "2 bedrooms"), ("3_bedrooms", "3 bedrooms"))
    },
    "area.community_area.population": FactSpec("Community-area population", "chi.acs_community_area", "survey_estimate", "community_area", "official_estimate"),
    "area.community_area.median_household_income": _calc("Community-area median household income", "chi.acs_community_area", "community_area", "bracket_median"),
    "area.crime": _rec("Crime", "chi.crime", "community_area"),
    "area.311": _rec("311 requests", "chi.311", "community_area"),
    "area.permits": _rec("Building permits", "chi.permits", "community_area"),
    "area.violations": _rec("Building violations", "chi.violations", "community_area"),
    "area.violations.categories": _calc("Violation categories", "chi.violations", "community_area", "keyword_grouping"),
    "area.business": _rec("Business licenses", "chi.business_licenses", "community_area"),
    "area.vacant": _rec("Vacant and abandoned buildings", "chi.vacant_buildings", "community_area"),
    "area.food": _rec("Food inspections", "chi.food_inspections", "community_area"),
    "area.benchmarks.market_value_per_land_sqft": _calc("Area median market value per land ft²", "internal.discovery_index", "community_area"),
    "property.comps.median_price": _calc("Median comparable sale price", "cook.assessor.sales", "radius"),
    "property.comps.median_price_per_land_sqft": _calc("Median comparable price per land ft²", "cook.assessor.sales", "radius"),
    "property.comps.median_price_per_bldg_sqft": _calc("Median comparable price per building ft²", "cook.assessor.sales", "radius"),
    "property.comps.median_price_per_buildable_sqft": _calc("Median comparable price per buildable ft²", "cook.assessor.sales", "radius"),
})


def weakest_tier(tiers: list[str]) -> str | None:
    """The weakest of ``tiers`` by the guide's A-F order; None for an empty list."""
    known = [t for t in tiers if t in TIER_ORDER]
    return max(known, key=TIER_ORDER.index) if known else None


def _tier_of(ref: str) -> str | None:
    """A calculation's input is a fact id or a registry source id; both resolve to a tier."""
    if ref in FACTS:
        return FACTS[ref].tier
    from backend.data_health.registry import BY_ID

    spec = BY_ID.get(ref)
    return spec.tier if spec and spec.tier != "internal" else None


def resolve_as_of(
    source_id: str | None, *, response_date: str | None = None, response_basis: str | None = None,
) -> tuple[str | None, str]:
    """``(as_of, as_of_basis)`` by the guide's precedence: a date the response carries, then
    data health's latest check (the newest date in the data: ``period_end``; else when the
    publisher last touched it: ``source_updated``), then the registry's frozen vintage, else
    none and ``queried``. The query date is never an as-of.

    Entries built before WS0 M3 pass only the response date, so their v1 ``as_of`` is unchanged.
    """
    if response_date:
        return response_date, response_basis or "source_updated"
    if source_id:
        try:
            from backend.data_health import status

            latest = status.latest(source_id)
        except Exception:  # an unreadable store: fall through
            latest = None
        if latest:
            if latest.get("content_through"):
                return str(latest["content_through"])[:10], "period_end"
            if latest.get("published_at"):
                return str(latest["published_at"])[:10], "source_updated"
        from backend.data_health.registry import BY_ID

        spec = BY_ID.get(source_id)
        if spec and spec.frozen and _ISO.match(spec.frozen.as_of or ""):
            return spec.frozen.as_of, "vintage"
    return None, "queried"


def _age_days(as_of: str | None, query_date: str) -> int | None:
    if not (as_of and _ISO.match(as_of) and _ISO.match(query_date)):
        return None
    return (date.fromisoformat(query_date) - date.fromisoformat(as_of)).days


def confidence_state(entry: ProvenanceEntry | dict) -> tuple[str, list[str]]:
    """``(state, reasons)`` for one entry, by the guide's §3 rules. The only place these are
    decided; components, prompts and templates read ``confidence`` and never recompute it.

    Reasons that do not change the state (``old_source``) still ride along for the caption.
    """
    e = entry.model_dump() if isinstance(entry, ProvenanceEntry) else entry
    cov = e.get("coverage") or {}
    prec = e.get("precision") or {}
    n, share, sample = cov.get("n"), cov.get("share"), cov.get("sample")
    cv = prec.get("cv")
    hide: list[str] = []
    fade: list[str] = []

    if share is not None:
        if share < HIDE_COVERAGE_BELOW:
            hide.append("low_coverage")
        elif share < FADE_COVERAGE_BELOW:
            fade.append("low_coverage")
    if n is not None and sample == "area_sample" and n < HIDE_N_BELOW:
        hide.append("small_sample")
    if n is not None and sample == "comps":
        if n < COMPS_HIDE_N_BELOW:
            hide.append("small_sample")
        elif n < COMPS_FADE_N_BELOW:
            fade.append("small_sample")
    if cv is not None:
        if cv > HIDE_CV_ABOVE:
            hide.append("high_cv")
        elif cv > FADE_CV_ABOVE:
            fade.append("high_cv")
    if e.get("method_key") == "bracket_median" and prec.get("moe") is None and cv is None:
        fade.append("bracket_median")
    if e.get("tier") == "ai_extracted" or str(e.get("method_key", "")).startswith("ai_read"):
        agr = prec.get("agreement") or {}
        measured = (
            agr.get("n", 0) >= AI_CORROBORATED_MIN_N and agr.get("agree", 0) / agr["n"] >= AI_CORROBORATED_RATE
        )
        if not (e.get("corroborated") or measured):
            fade.append("ai_unverified")

    reasons = list(dict.fromkeys(hide + fade))
    age = e.get("age_days")
    if age is not None and age > OLD_SOURCE_DAYS and e.get("as_of_basis") in _OLD_SOURCE_BASES:
        reasons.append("old_source")
    state = "withheld" if hide else "low" if fade else "standard"
    return state, reasons


def make_entry(
    fact_id: str, *, query_date: str, tier: str | None = None, source_id: str | None = None,
    method_key: str | None = None, scope: str | None = None, label: str | None = None, **fields,
) -> dict:
    """A validated provenance entry as its wire dict. The spec for ``fact_id`` supplies the
    defaults; per-call arguments override (a calculation on a record is not the record's tier).
    ``kind`` is derived from the tier, ``age_days``, ``method``, ``basis_tier`` and the
    confidence state are computed here so no caller can contradict them.
    """
    spec = FACTS.get(fact_id)
    tier = tier or (spec.tier if spec else None)
    method_key = method_key or (spec.method_key if spec else None)
    if tier is None or method_key is None:
        raise KeyError(f"no spec for fact {fact_id!r}: pass tier and method_key")
    as_of = fields.get("as_of")
    fields.setdefault("as_of_basis", "source_updated" if as_of else "queried")
    inputs = fields.get("inputs")
    if inputs and "basis_tier" not in fields:
        fields["basis_tier"] = weakest_tier([t for t in (_tier_of(i) for i in inputs) if t])
    entry = ProvenanceEntry(
        label=label or (spec.label if spec else fact_id),
        kind=_KIND_BY_TIER.get(tier, "derived"),
        query_date=query_date,
        tier=tier,
        source_id=source_id if source_id is not None else (spec.source_id if spec else None),
        method_key=method_key,
        method=fields.pop("method", None) or METHOD_TEXT[method_key],
        scope=scope or (spec.scope if spec else None),
        age_days=_age_days(as_of, query_date),
        **fields,
    )
    entry.confidence, entry.confidence_reasons = confidence_state(entry)
    return entry.to_dict()


def _scalar(v: Any) -> str | int | float | bool | None:
    """A figure as a JSON scalar for ``value``."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


# Which registry source supplied a lot/building area, by the area dataset code on PropertySummary.
_AREA_SOURCE_IDS = {
    "assessor": "cook.assessor.characteristics",
    "gis": "cook.gis.parcels",
    "geometry": "cook.ptaxsim",
    "condo_unit": "cook.assessor.condo_characteristics",
    "commercial_valuation": "cook.assessor.commercial_valuation",
    "footprint": "chi.building_footprints",
    "energy_benchmark": "chi.energy_benchmarking",
}


def _vintage_for(src: str | None, prop, qd: str) -> dict:
    """as_of / basis / period for a lot or building area by the dataset behind it (WS0 M3), so the
    2015 footprints and a commercial valuation year say so. Computed areas keep their v1 dates."""
    from backend.provenance_figures import _building_dates

    if src in (None, "geometry"):
        return {}
    d = _building_dates(src, prop, qd)
    return {k: v for k, v in d.items() if v is not None}


def _area_basis(fact: str, src: str | None) -> dict:
    """tier/source/method overrides for a lot or building area, by the dataset that supplied it.
    A polygon area is our arithmetic on the County's geometry (tier D on its source's tier), not
    a recorded figure; every other dataset states its area."""
    sid = _AREA_SOURCE_IDS.get(src or "")
    if src == "geometry":
        return {"tier": "our_calculation", "source_id": sid, "method_key": "calculation", "inputs": [sid]}
    return {"source_id": sid} if sid else {}


def build_provenance(
    *,
    context,
    zone_definition: dict | None,
    resolved_pin: str | None,
    resolved_confidence: str | None,
    query_date: str | None = None,
    comparables=None,
    address_scoped_violations: bool = False,
) -> dict[str, dict]:
    """Provenance for the facts the Profile shows. ``context`` is the assembled
    ContextObject; a fact that isn't present gets no entry (never a made-up one)."""
    qd = query_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    vintage = get_code_vintage()
    zoning = getattr(context, "parcel_zoning", None)

    if zoning is not None:
        out["zoning.district"] = make_entry(
            "zoning.district", query_date=qd,
            label=f"Zoning district {zoning.zone_class}",
            source=ZONING_LAYER,
            record_id=zoning.ordinance_num,
            url=zoning.clerk_url or zoning.zoning_map_url,
            as_of=zoning.map_updated,
            as_of_basis="record_updated" if zoning.map_updated else "queried",
            effective_date=zoning.ordinance_date,
            note=(
                f"Application {zoning.application_num}. " if zoning.application_num else ""
            ) + "as_of is when this district's map record was last edited.",
            geography=zoning.zone_class,
            value=_scalar(zoning.zone_class),
        )

        fam = bulk_family(zoning.zone_class)
        zd = zone_definition or {}
        if fam and not zd.get("is_fallback"):
            for fact, section in BULK_SECTIONS[fam].items():
                if section is None or zd.get(fact) in (None, ""):
                    continue
                out[f"zoning.{fact}"] = make_entry(
                    f"zoning.{fact}", query_date=qd,
                    label=f"{_BULK_LABELS[fact]} for {zoning.zone_class}",
                    source=CODE_SOURCE, record_id=f"§{section}", section=section,
                    as_of=(vintage or {}).get("current_through"), as_of_basis="current_through",
                    note=f"Code text current through {(vintage or {}).get('label')}." if vintage else None,
                    method_params={"section": section},
                    geography=zoning.zone_class,
                    value=_scalar(zd.get(fact)),
                )

    regulatory = getattr(context, "regulatory", None)
    for ov in (regulatory.overlays if regulatory else []):
        lid = _LAYER_ID_BY_TYPE.get(ov.layer_type)
        layer_name = OVERLAY_LAYERS.get(lid, {}).get("name", ov.layer_type) if lid else ov.layer_type
        out[f"overlay.{ov.layer_type}"] = make_entry(
            f"overlay.{ov.layer_type}", query_date=qd,
            label=ov.name or layer_name,
            source=f"City of Chicago Zoning MapServer, {layer_name}" + (f" (layer {lid})" if lid else ""),
            record_id=ov.ordinance or ov.name,
            url=ov.link,
            value=_scalar(ov.name or layer_name),
        )

    upcoming = getattr(context, "upcoming_zoning", None)
    if upcoming is not None and upcoming.checked_at:
        as_of = upcoming.checked_at[:10]
        shown = len(upcoming.subject_filings) + len(upcoming.nearby_filings)
        out["regulatory.upcoming_zoning.records"] = make_entry(
            "regulatory.upcoming_zoning.records", query_date=qd,
            source="City Clerk eLMS current non-final zoning docket",
            record_id=f"{shown} placed filing(s)",
            as_of=as_of, as_of_basis="queried",
            note="Applicant filings are proposals, not approvals.",
            value=_scalar(shown),
        )
        out["regulatory.upcoming_zoning.placement"] = make_entry(
            "regulatory.upcoming_zoning.placement", query_date=qd,
            source="UrbanLayer placement using Cook County Address Points",
            record_id=f"{upcoming.radius_mi:g} mile radius",
            as_of=as_of, as_of_basis="queried",
            note=(
                f"{upcoming.unplaced_count} current zoning filing(s) could not be placed."
                if upcoming.placement_status == "partial" else None
            ),
            coverage={
                "n": upcoming.placed_count,
                "share": upcoming.placement_coverage,
                "universe": "current zoning filings citywide",
                "unit": "filings",
            },
            inputs=["chi.clerk.legislation", "cook.address_points"],
            value=_scalar(upcoming.placement_status),
        )

    if resolved_pin:
        authoritative = resolved_confidence == "authoritative"
        method = (
            "Cook County Address Points or Assessor Parcel Addresses"
            if authoritative
            else "Nearest parcel to the geocoded point (approximate)"
        )
        extra = {} if authoritative else {
            # the nearest parcel is our computation on the Parcel Universe, not a recorded match
            "tier": "our_calculation", "source_id": "cook.parcel_universe", "method_key": "calculation",
            "inputs": ["cook.parcel_universe"],
        }
        out["parcel.identity"] = make_entry(
            "parcel.identity", query_date=qd,
            label=f"Parcel {resolved_pin}",
            source=method, record_id=resolved_pin,
            url=f"https://www.cookcountyassessor.com/pin/{resolved_pin}",
            note=None if authoritative else "Identity not confirmed against an address record.",
            value=resolved_pin,
            **extra,
        )

    prop = getattr(context, "property", None)
    if prop is not None:
        for fact, label, value, src in (
            ("land_sqft", "Lot area", prop.land_sqft, prop.land_sqft_source),
            ("bldg_sqft", "Building area", prop.bldg_sqft, prop.bldg_sqft_source),
        ):
            if value:
                out[f"property.{fact}"] = make_entry(
                    f"property.{fact}", query_date=qd, label=label,
                    source=_AREA_SOURCES.get(src or "", src or "Cook County records"),
                    record_id=prop.pin14,
                    value=_scalar(value),
                    **{**_vintage_for(src, prop, qd), **_area_basis(fact, src)},
                )

    if vintage:
        out["code.vintage"] = make_entry(
            "code.vintage", query_date=qd,
            source=vintage.get("source") or CODE_SOURCE, as_of=vintage["current_through"],
            as_of_basis="current_through",
            note=vintage.get("label"),
            value=_scalar(vintage["current_through"]),
        )

    # WS0 M3: every other figure the Profile shows, and every area feed a chat turn can carry.
    from backend.provenance_figures import figure_entries

    out.update(figure_entries(
        context, comparables=comparables, qd=qd, existing=out, address_scoped_violations=address_scoped_violations,
    ))
    return out


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def entry_is_dated(entry: dict | None) -> bool:
    """True when the entry carries at least one valid date saying how current it is."""
    if not entry:
        return False
    return any(isinstance(entry.get(k), str) and _ISO.match(entry[k]) for k in ("as_of", "effective_date", "query_date"))


# --- chat: what the model is not given, and how to name what it is (WS0 M6) -----------------------

# Where a withheld figure lives on a ContextObject, by fact id: (container attribute, field(s) to clear).
_COMPS_FIELDS = {
    "property.comps.median_price": ("median_sale_price",),
    "property.comps.median_price_per_land_sqft": ("median_price_per_land_sqft",),
    "property.comps.median_price_per_bldg_sqft": ("median_price_per_bldg_sqft",),
    "property.comps.median_price_per_buildable_sqft": (
        "median_price_per_buildable_sqft", "buildable_median_basis", "buildable_median_n",
    ),
}
_COMMUNITY_AREA_FIELDS = {
    "area.community_area.population": "population",
    "area.community_area.median_household_income": "median_household_income",
}
# A caption-bearing figure is told to the model only when it is an estimate of our own making or someone
# else's (a low-confidence figure, our calculation, an AI reading, a private company's index). An ACS tract
# figure is a standard official estimate: the prompt asks for its period and margin, which the summary carries.
_NOTED_TIERS = {"our_calculation", "ai_extracted", "non_government"}
_MAX_FIGURE_NOTES = 16
_NOT_SHOWN = "Not shown: "


def _own(context, attr: str):
    """The context's ``attr`` as a copy this turn owns. Retrieval results are cached and shared between
    requests; clearing a field on the shared object would withhold it from every later answer."""
    obj = getattr(context, attr, None)
    if obj is None:
        return None
    mine = obj.model_copy(deep=True)
    setattr(context, attr, mine)
    return mine


def _clear_figure(context, fact_id: str) -> bool:
    """Remove one withheld figure's value from ``context``. False when we do not know where it lives
    (the caller still lists it as withheld, so the model is told not to state it)."""
    if fact_id.startswith("area.tract."):
        field = fact_id.rsplit(".", 1)[1]
        hood = _own(context, "neighborhood")
        ct = hood.census_tract if hood else None
        if ct is None or field not in type(ct).model_fields:
            return False
        setattr(ct, field, None)
        ct.moe.pop(field, None)
        ct.cv.pop(field, None)
        return True
    if fact_id == "area.rent.community_area":
        hood = _own(context, "neighborhood")
        ca = hood.rent.community_area if hood and hood.rent else None
        if ca is None:
            return False
        ca.median = ca.moe = ca.cv = None
        return True
    if fact_id.startswith("area.rent."):
        hood = _own(context, "neighborhood")
        group = fact_id.rsplit(".", 1)[1]
        cells = [b for b in (hood.rent.bedrooms if hood and hood.rent else []) if b.bedrooms == group]
        for b in cells:
            b.estimate = b.moe = b.cv = None
        return bool(cells)
    if fact_id in _COMMUNITY_AREA_FIELDS:
        hood = _own(context, "neighborhood")
        dm = hood.demographics if hood else None
        if dm is None:
            return False
        setattr(dm, _COMMUNITY_AREA_FIELDS[fact_id], None)
        return True
    if fact_id in _COMPS_FIELDS:
        comps = _own(context, "comparables")
        if comps is None:
            return False
        for field in _COMPS_FIELDS[fact_id]:
            setattr(comps, field, None)
        return True
    return False


def withhold_low_evidence(context, provenance: dict[str, dict]) -> dict[str, dict]:
    """Apply the confidence standard to a chat turn's context (guide §3). ``provenance`` is the turn's
    ``build_provenance`` map; returns it with each withheld figure's value dropped.

    - a ``withheld`` figure's value is removed from ``context``, so the model cannot state it, and listed in
      ``context.withheld_figures`` with the reason in plain words (the sidebar shows the same reason);
    - an estimate, our calculation, AI reading or private index that survives is listed in
      ``context.figure_notes`` so the model names it as such;
    - ``context.provenance`` is set to the returned map (stored with the answer; the synthesizer excludes it).

    The state comes from ``confidence_state`` through each entry's ``confidence``; nothing is recomputed here.
    """
    from backend.models import FigureNote, WithheldFigure
    from backend.report_i18n import make_translator
    from backend.report_provenance import _withheld_text, caption

    t = make_translator("en")
    out: dict[str, dict] = {}
    withheld: list[dict] = []
    notes: list[dict] = []
    for fact_id, e in provenance.items():
        if e.get("confidence") == "withheld":
            if not _clear_figure(context, fact_id):
                log.warning("withheld figure %s has no known place in the context; the model is told not to state it", fact_id)
            reason = _withheld_text(e, t)
            withheld.append({
                "fact_id": fact_id, "figure": e.get("label") or fact_id,
                "reason": (reason[len(_NOT_SHOWN):] if reason.startswith(_NOT_SHOWN) else reason).rstrip("."),
            })
            out[fact_id] = {k: v for k, v in e.items() if k != "value"}
            continue
        out[fact_id] = e
        if len(notes) < _MAX_FIGURE_NOTES and (e.get("confidence") == "low" or e.get("tier") in _NOTED_TIERS):
            c = caption(e, t, "en")
            if c and not c["withheld"] and (c["lead"] or c["text"]):
                notes.append({"fact_id": fact_id, "figure": e.get("label") or fact_id,
                              "note": " · ".join(x for x in (c["lead"], c["text"]) if x)})
    context.withheld_figures = [WithheldFigure(**w) for w in withheld] or None
    context.figure_notes = [FigureNote(**n) for n in notes] or None
    context.provenance = out
    return out


def text_impact_entries(upcoming, query_date: str) -> dict[str, dict]:
    """Provenance for the pending Title 17 text-impact block: the Clerk's record, and UrbanLayer's
    reviewed relevance mapping (never restated as the government's opinion). Built after the
    impacts are computed because the parcel's own fact ids decide them."""
    review = getattr(upcoming, "text_review", None)
    if upcoming is None or review is None or not upcoming.checked_at or review.status == "unavailable":
        return {}
    as_of = upcoming.checked_at[:10]
    shown = len(upcoming.text_impacts)
    note = None
    if review.status == "incomplete":
        note = f"{len(review.unreviewed)} pending Title 17 proposal(s) have no current review for relevance to this parcel."
    return {
        "regulatory.upcoming_zoning.text_impacts": make_entry(
            "regulatory.upcoming_zoning.text_impacts", query_date=query_date,
            source="City Clerk eLMS pending Title 17 text amendments",
            record_id=f"{review.pending_count} pending proposal(s)",
            as_of=as_of, as_of_basis="queried",
            note="Pending proposals are not law and are shown beside, never in place of, current law.",
            value=_scalar(review.pending_count),
        ),
        "regulatory.upcoming_zoning.relevance": make_entry(
            "regulatory.upcoming_zoning.relevance", query_date=query_date,
            source="UrbanLayer reviewed mapping of pending proposals to Profile rules (backend/pending_impacts.json)",
            record_id=f"{review.reviewed_count} of {review.pending_count} reviewed",
            as_of=as_of, as_of_basis="queried",
            method="A person-supervised reading of each pending ordinance's text, applied to this parcel's district, overlays and shown facts",
            note=note,
            coverage={
                "n": review.reviewed_count, "share": (review.reviewed_count / review.pending_count) if review.pending_count else 1.0,
                "universe": "pending Title 17 text proposals", "unit": "proposals",
            },
            inputs=["chi.clerk.legislation", "internal.pending_legislation"],
            value=_scalar(shown),
        ),
    }
