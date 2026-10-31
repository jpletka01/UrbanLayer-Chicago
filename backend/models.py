import builtins
import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


SourceTag = Literal[
    "crime_api",
    "311_api",
    "permits_api",
    "violations_api",
    "business_api",
    "vacant_buildings_api",
    "food_inspections_api",
    "vector_search",
    "regulatory_domain",
    "property_domain",
    "incentives_domain",
    "neighborhood_domain",
]

IntentTag = Literal[
    "neighborhood_overview",
    "incident_lookup",
    "legal_question",
    "event_query",
    "trend_analysis",
    "clarification_needed",
]

WorkflowHint = Literal[
    "general",
    "site_due_diligence",
    "development_feasibility",
    "business_launch",
    "property_intelligence",
    "neighborhood_overview",
]


LocationType = Literal[
    "intersection",
    "address",
    "neighborhood",
    "community_area",
    "none",
]


class Location(BaseModel):
    raw: str = ""
    type: LocationType = "none"
    resolved_community_area: int | None = None
    resolved_community_area_name: str | None = None
    resolved_address: str | None = None
    resolved_lat: float | None = None
    resolved_lon: float | None = None
    # Authoritative parcel key when the turn arrived with a parcel hint
    # (Scorecard→chat handoff). Read-only flow: chat never writes the
    # selection back (truth-model §3) — this only replaces text re-geocoding.
    pin: str | None = None
    # How an address-typed location was pinned down. "authoritative": the PIN
    # came from Address Points / Assessor Parcel Addresses (same path the
    # Property Profile uses). "approximate": only the street-interpolated
    # geocode point is known, which can fall in a neighboring parcel or zoning
    # district — the answer must say so. None: not an address-typed location,
    # or resolution was not attempted.
    resolution: Literal["authoritative", "approximate"] | None = None
    # Which record matched (backend/resolution.py): address_points | assessor_addresses |
    # pin | coordinates | geocode_nearest. Lets the answer say HOW the parcel was found.
    resolution_method: str | None = None


class RetrievalPlan(BaseModel):
    sources: list[SourceTag] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    intent: IntentTag = "neighborhood_overview"
    time_range_days: int = 90
    requires_disclaimer: bool = False
    search_query: str | None = None
    clarification: str | None = None
    workflow_hint: WorkflowHint = "general"


class CrimeYoYItem(BaseModel):
    category: str
    current_count: int
    prior_year_count: int
    # None = prior-year count was 0 (percentage undefined; renders as "new").
    change_pct: int | None


class CrimeSummary(BaseModel):
    total: int
    arrest_rate: float
    by_type: dict[str, int]
    yoy: list[CrimeYoYItem] | None = None
    yoy_period: str | None = None
    capped: bool = False


class ThreeOneOneSummary(BaseModel):
    total: int
    oldest_open_days: int | None
    by_department: dict[str, int]
    top_types: list[str]
    capped: bool = False


class Address311Summary(BaseModel):
    total: int
    open_count: int
    by_type: dict[str, int]
    high_risk_flags: list[str] = Field(default_factory=list)
    routine_service_flags: list[str] = Field(default_factory=list)


class PermitSummary(BaseModel):
    total: int
    total_estimated_cost: float
    by_type: dict[str, int] = Field(default_factory=dict)
    top_work_descriptions: list[str]
    recent_contractors: list[str] = Field(default_factory=list)
    capped: bool = False


class ViolationSummary(BaseModel):
    total: int
    open_count: int
    by_category: dict[str, int] = Field(default_factory=dict)
    top_descriptions: list[str]
    capped: bool = False


class AddressViolations(BaseModel):
    """Parcel-scoped (address-keyed) building-violation tri-state, lifted from the
    Scorecard so the chat agrees with the page.

    ADDRESS-scoped — deliberately DISTINCT from the area-level
    ``ContextObject.violations`` the chat fetches via community-area retrieval.
    Never merge the two. ``status``:
      - ``present``       — records on file at this address (``summary`` set).
      - ``confirmed_zero``— the address-exact lookup ran and found none on record.
      - ``unconfirmed``   — the address didn't parse; the lookup never ran. This is
                            NOT zero — must never be reported as "no violations."
    """
    status: Literal["present", "confirmed_zero", "unconfirmed"]
    summary: ViolationSummary | None = None


class BusinessSummary(BaseModel):
    total: int
    by_license_type: dict[str, int] = Field(default_factory=dict)
    top_activities: list[str]
    capped: bool = False


class VacantBuildingReport(BaseModel):
    address: str
    date: str | None = None
    violation_type: str | None = None
    responsible_entity: str | None = None
    amount_due: float | None = None


class VacantBuildingSummary(BaseModel):
    total: int
    by_department: dict[str, int] = Field(default_factory=dict)
    recent_reports: list[VacantBuildingReport] = Field(default_factory=list)


class FoodInspectionDetail(BaseModel):
    name: str
    facility_type: str | None = None
    risk: str | None = None
    result: str | None = None
    date: str | None = None


class FoodInspectionSummary(BaseModel):
    total: int
    by_result: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    fail_rate: float | None = None
    recent_inspections: list[FoodInspectionDetail] = Field(default_factory=list)


# A district changed by ordinance within this many days is flagged "recently
# rezoned": the City says amendments can take up to 90 days to reach the map, and
# the kit's P7 parcel was rezoned 65 days before the layer caught up.
RECENT_REZONING_DAYS = 180


class ZoningSummary(BaseModel):
    zone_class: str
    zone_type: int | None = None
    # The ordinance identifier (clerk's number for a recent amendment, a legacy id
    # for older ones). An *application* number (23082T1) is kept apart, below.
    ordinance_num: str | None = None
    application_num: str | None = None
    # ISO dates from the City's zoning layer: when the ordinance that set this
    # polygon passed, and when this polygon's record was last edited. Neither is
    # "when the whole map was refreshed" — they describe THIS district's record.
    ordinance_date: str | None = None
    map_updated: str | None = None
    clerk_url: str | None = None
    zoning_map_url: str = "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def recently_rezoned(self) -> bool:
        """True when the ordinance behind this district passed within the last
        RECENT_REZONING_DAYS (computed at serialization, so a cached lookup ages)."""
        if not self.ordinance_date:
            return False
        try:
            passed = datetime.date.fromisoformat(self.ordinance_date)
        except ValueError:
            return False
        return 0 <= (datetime.date.today() - passed).days <= RECENT_REZONING_DAYS


class OverlayDistrict(BaseModel):
    layer_type: str
    name: str | None = None
    ordinance: str | None = None
    description: str | None = None
    # What this overlay means for the parcel, in one pinned-to-the-code sentence
    # (overlay_facts.describe_overlay), and where to read the source (code section
    # or the PD ordinance PDF). None when the code doesn't say / no link exists.
    detail: str | None = None
    link: str | None = None


class AROHousingProject(BaseModel):
    name: str
    address: str | None = None
    units: int | None = None
    property_type: str | None = None


class AROHousingSummary(BaseModel):
    total_projects: int = 0
    total_units: int = 0
    projects: list[AROHousingProject] = Field(default_factory=list)


class RegulatorySummary(BaseModel):
    overlays: list[OverlayDistrict] = Field(default_factory=list)
    in_planned_development: bool = False
    in_landmark_district: bool = False
    is_landmark_building: bool = False
    in_historic_district: bool = False
    on_national_register: bool = False
    in_lakefront_protection: bool = False
    on_pedestrian_street: bool = False
    in_special_district: bool = False
    in_pmd: bool = False
    in_tod_area: bool = False
    in_adu_area: bool = False
    in_aro_zone: bool = False
    in_ssa: bool = False
    ssa_name: str | None = None
    flood_zone: str | None = None
    flood_zone_subtype: str | None = None
    # None = UNKNOWN (FEMA's flood map didn't answer, ``flood_unchecked``); never state "not in" for it.
    in_special_flood_hazard: bool | None = False
    flood_unchecked: bool = False
    brownfield_sites: list[dict] = Field(default_factory=list)
    aro_housing: AROHousingSummary | None = None
    # Overlay layer types the City map couldn't answer for (timeout, HTTP error, 200 +
    # error body). Their in_* flag is False because it is UNKNOWN, not because the
    # parcel is clear: never state "not in <overlay>" for these.
    unchecked_overlays: list[str] = Field(default_factory=list)
    # Plain-language labels for those, merged into partial_failures.
    data_gaps: list[str] = Field(default_factory=list)


class AssessmentRecord(BaseModel):
    year: int | None = None
    land: float | None = None
    building: float | None = None
    total: float | None = None


class SaleRecord(BaseModel):
    date: str | None = None
    price: float | None = None
    deed_type: str | None = None


class TaxLineItem(BaseModel):
    agency: str
    rate: float
    amount: float


class ParcelFlags(BaseModel):
    """Distress / opportunity flags. Tax-sale years are HISTORIC (the public
    datasets end ~2014) — always present with the years, never as current
    distress. City-owned = acquisition opportunity (ChiBlockBuilder)."""
    tax_sale_years: list[int] = Field(default_factory=list)
    scavenger_sale_years: list[int] = Field(default_factory=list)
    city_owned: bool = False
    city_owned_status: str | None = None
    city_owned_sales_status: str | None = None
    city_owned_application_url: str | None = None
    scofflaw: bool = False
    scofflaw_case: str | None = None
    str_prohibited: bool = False
    # CHRS (1996 survey, frozen): "orange" | "red" — either rating triggers the
    # 90-day demolition-permit hold. From the committed local artifact.
    chrs_rating: str | None = None
    chrs_name: str | None = None

    def any_flag(self) -> bool:
        return bool(
            self.tax_sale_years or self.scavenger_sale_years or self.city_owned
            or self.scofflaw or self.str_prohibited or self.chrs_rating
        )


class EnergyBenchmark(BaseModel):
    """Chicago Energy Benchmarking (xq83-jr8c) — buildings ≥ 50,000 sq ft.

    ``chicago_energy_rating`` is the city's 0–4 placard scale; a "0" on a
    non-submitting row is a compliance placeholder, so it surfaces here as
    None + ``not_submitted=True`` (a compliance fact, not a performance score).
    ``gross_floor_area`` is owner-reported for the whole property.
    """
    chicago_energy_rating: float | None = None
    energy_star_score: int | None = None
    gross_floor_area: int | None = None
    year_built: int | None = None
    primary_property_type: str | None = None
    site_eui: float | None = None
    ghg_intensity: float | None = None
    data_year: int | None = None
    not_submitted: bool = False


class AppealRecord(BaseModel):
    """One assessment appeal outcome for the parcel."""
    year: int | None = None
    stage: str  # "assessor" | "board_of_review"
    before_total: float | None = None
    after_total: float | None = None
    result: str | None = None  # Decrease / No Change / Increase ("change"/"no change" at assessor stage)
    reduction_pct: float | None = None  # positive = assessed value was reduced
    appeal_type: str | None = None


class AppealsSummary(BaseModel):
    """Parcel appeal history + nearby Board-of-Review outcome stats.

    The nearby aggregate ("N appeals within a block over the last reassessment
    cycle, median reduction X%") is direct-dollars context: it tells the reader
    whether appealing here historically works.
    """
    records: list[AppealRecord] = Field(default_factory=list)
    nearby_window_years: list[int] = Field(default_factory=list)
    nearby_appeal_count: int = 0
    nearby_reduced_count: int = 0
    nearby_median_reduction_pct: float | None = None
    # The nearby query returns at most NEARBY_ROW_CAP rows; when saturated the
    # count is a floor ("500+"), not an exact count — dense areas hit the cap.
    nearby_capped: bool = False


class TaxExemption(BaseModel):
    """An exemption applied to the parcel's most recent tax bill.

    ``eav_reduction`` is the equalized-assessed-value deduction (taxable value
    removed before rates apply) — NOT dollars off the bill. A buyer loses
    owner-occupancy exemptions at transfer, so their presence means the listed
    bill understates the buyer's future bill.
    """
    kind: str
    eav_reduction: float


class AssessorPermit(BaseModel):
    """One row of the Cook County Assessor's permit record for a parcel."""

    date_issued: str | None = None
    status: str | None = None
    amount: float | None = None
    # The assessor's own call on whether the work changes the assessment.
    # None = the source left it blank, which is NOT the same as False.
    assessable: bool | None = None
    job_code: str | None = None
    work_description: str | None = None


class AssessorPermitSummary(BaseModel):
    permits: list[AssessorPermit] = Field(default_factory=list)
    count: int = 0
    truncated: bool = False
    window_years: int = 5
    total_declared_amount: float | None = None
    # True when an ASSESSABLE permit has not closed out — a future assessment
    # (and so tax) change already attached to the parcel.
    assessable_pending: bool = False
    latest_date: str | None = None


class PropertySummary(BaseModel):
    pin14: str | None = None
    address: str | None = None
    bldg_class: str | None = None
    bldg_class_description: str | None = None
    bldg_sqft: int | None = None
    land_sqft: int | None = None
    # Per-field provenance so non-assessor numbers can be labeled honestly.
    # land: "assessor" | "gis" | "geometry" (PTAXSIM parcel polygon area).
    # bldg: "assessor" | "gis" | "condo_unit" | "commercial_valuation" (economic-
    #   unit total) | "footprint" (city layer, uneven freshness).
    # year/stories: "assessor" | "commercial_valuation" (year only) | "footprint".
    # units: "assessor" (decoded 2xx chars) | "commercial_valuation" (CCAO
    #   valuation tot_units — filled only for single-PIN economic units).
    land_sqft_source: str | None = None
    bldg_sqft_source: str | None = None
    # The Commercial Valuation vintage (assessment year) behind any field whose source is
    # "commercial_valuation"; None when no field came from it.
    commercial_valuation_year: int | None = None
    # This parcel is one of several in a CCAO commercial "economic unit" whose
    # valuation total (a whole complex's building area) is NOT this parcel's own.
    # Set only when no per-parcel area could be established; ``bldg_sqft`` stays
    # empty so no FAR is computed from the wrong denominator.
    complex_bldg_sqft: int | None = None
    complex_member_pins: list[str] | None = None
    year_built_source: str | None = None
    stories_source: str | None = None
    units_source: str | None = None
    # Fractional values are real ("1.5 Story" is a CCAO residence type)
    stories: float | None = None
    units: int | None = None
    # char_ncu — number of commercial units on the parcel (mostly class 212
    # mixed-use). Distinct from dwelling `units`; was wrongly shown as stories.
    commercial_units: int | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    full_baths: int | None = None
    half_baths: int | None = None
    bldg_age: int | None = None
    year_built: int | None = None
    exterior_wall: str | None = None
    roof_type: str | None = None
    basement: str | None = None
    garage_size: str | None = None
    air_conditioning: str | None = None
    tax_exempt: bool = False
    total_assessed_value: float | None = None
    estimated_annual_tax: float | None = None
    # True when estimated_annual_tax was derived from assessed value via a
    # documented effective-rate fallback (ptaxsim bill unavailable), not a
    # parcel-specific ptaxsim computation. Drives an "estimated" label.
    tax_estimate_is_fallback: bool = False
    # Class-aware tax interpretation, computed server-side ONCE so every
    # surface (scorecard, chat sidebar, $25 report) shows the same math.
    # assessment_level: ordinance level for this class (0.10 residential,
    # 0.25 commercial, …). implied_market_value = assessed ÷ level.
    # effective_tax_rate = annual tax ÷ implied market value (fraction).
    # tax_year: which ptaxsim bill year estimated_annual_tax came from — the
    # DB lags the calendar 1–2 years, so an unlabeled bill next to the current
    # assessed value silently mixes years.
    assessment_level: float | None = None
    implied_market_value: float | None = None
    effective_tax_rate: float | None = None
    tax_year: int | None = None
    tax_code: str | None = None
    tax_breakdown: list[TaxLineItem] = Field(default_factory=list)
    tax_exemptions: list[TaxExemption] = Field(default_factory=list)
    appeals: AppealsSummary | None = None
    flags: ParcelFlags | None = None
    energy: EnergyBenchmark | None = None
    assessment_history: list[AssessmentRecord] = Field(default_factory=list)
    sales_history: list[SaleRecord] = Field(default_factory=list)
    parcel_geometry: dict | None = None
    data_gaps: list[str] = Field(default_factory=list)
    # The subset of those that are a call that FAILED (a source didn't answer), as opposed to a figure the
    # source has no record of (no assessments for an exempt parcel). Only these are "couldn't check" (WS6 M7).
    failed_calls: list[str] = Field(default_factory=list)
    assessor_permits: AssessorPermitSummary | None = None


class GrantProject(BaseModel):
    name: str
    program: str
    incentive_amount: float | None = None
    total_cost: float | None = None
    property_type: str | None = None
    description: str | None = None
    date: str | None = None


class GrantProgramSummary(BaseModel):
    total_projects: int = 0
    total_funding: float = 0.0
    by_program: dict[str, int] = Field(default_factory=dict)
    recent_projects: list[GrantProject] = Field(default_factory=list)


class IncentivesSummary(BaseModel):
    in_tif_district: bool = False
    tif_name: str | None = None
    tif_year_start: int | None = None
    tif_end_year: int | None = None
    tif_total_revenue: float | None = None
    tif_total_expenditure: float | None = None
    tif_property_tax_revenue: float | None = None
    tif_cumulative_revenue: float | None = None
    tif_fund_balance: float | None = None
    tif_annual_expenditure: float | None = None
    tif_fund_history: list[dict] = Field(default_factory=list)
    tif_financials: list[dict] = Field(default_factory=list)
    tif_districts_in_area: list[dict] | None = None
    in_opportunity_zone: bool = False
    oz_tract: str | None = None
    in_enterprise_zone: bool = False
    enterprise_zone_name: str | None = None
    in_qct: bool = False
    qct_tract: str | None = None
    in_nmtc: bool = False
    nmtc_tract: str | None = None
    nmtc_severe_distress: bool = False
    nmtc_poverty_rate: float | None = None
    census_tract: str | None = None
    property_tax_class: str | None = None
    tax_incentive_description: str | None = None
    grant_programs: GrantProgramSummary | None = None


class DemographicsSummary(BaseModel):
    """Community-area figures from the City's ACS extract (t68z-cikk). Holds only what
    that dataset publishes; ``median_household_income`` is interpolated from 5 brackets
    with no margin of error. Stored contexts may carry fields removed 2026-10-20
    (rent, home value, poverty, …); pydantic ignores them."""

    community_area: int | None = None
    community_area_name: str | None = None
    population: int | None = None
    median_household_income: int | None = None
    acs_period: str | None = None  # e.g. "2019–2023"


class DistributionBucket(BaseModel):
    label: str
    value: float


class RentCell(BaseModel):
    """One published median gross rent with its 90% margin of error and coefficient of variation."""

    estimate: int | None = None
    moe: float | None = None
    cv: float | None = None


class CensusTractDemographics(BaseModel):
    tract_fips: str
    tract_name: str | None = None
    census_reporter_url: str | None = None

    population: int | None = None
    median_household_income: int | None = None
    per_capita_income: int | None = None
    median_age: float | None = None
    median_home_value: int | None = None
    median_gross_rent: int | None = None
    owner_occupied_pct: float | None = None
    vacancy_rate: float | None = None
    poverty_rate: float | None = None
    unemployment_rate: float | None = None
    bachelors_or_higher_pct: float | None = None
    foreign_born_pct: float | None = None
    acs_period: str | None = None  # the release's years, e.g. "2020–2024"
    acs_release: str | None = None  # Census Reporter's release id, e.g. "acs2024_5yr"
    # Published margins of error (90% level; percentage points for the *_pct and *_rate fields)
    # and coefficients of variation (SE / estimate), keyed by the field name above.
    moe: dict[str, float] = Field(default_factory=dict)
    cv: dict[str, float] = Field(default_factory=dict)
    # The Census's published median gross rent by bedroom count (B25031) for this tract, keyed by
    # ``backend.retrieval.neighborhood.rent.BEDROOM_GROUPS``. An absent key or a null estimate is a
    # suppressed cell, not a zero.
    rent_by_bedroom: dict[str, RentCell] = Field(default_factory=dict)

    age_distribution: list[DistributionBucket] = Field(default_factory=list)
    income_distribution: list[DistributionBucket] = Field(default_factory=list)
    race_distribution: list[DistributionBucket] = Field(default_factory=list)
    education_distribution: list[DistributionBucket] = Field(default_factory=list)
    transportation_distribution: list[DistributionBucket] = Field(default_factory=list)

    county_median_income: int | None = None
    city_median_income: int | None = None


class TransitAccess(BaseModel):
    nearest_cta_rail: str | None = None
    cta_rail_distance_mi: float | None = None
    cta_lines: list[str] = Field(default_factory=list)
    nearest_metra: str | None = None
    metra_distance_mi: float | None = None
    metra_line: str | None = None
    tod_eligible: bool = False
    tod_type: str | None = None


class DivvyAccess(BaseModel):
    """Nearest in-service Divvy bike-share station. None on the summary = none in range."""

    nearest_station: str | None = None
    distance_mi: float | None = None
    docks: int | None = None
    stations_within_radius: int = 0
    radius_mi: float = 0.5


class WalkScoreSummary(BaseModel):
    walk_score: int | None = None
    walk_description: str | None = None
    transit_score: int | None = None
    transit_description: str | None = None
    bike_score: int | None = None
    bike_description: str | None = None
    ws_link: str | None = None


class WardInfo(BaseModel):
    """The parcel's ward + alderman — the operative political unit for any
    rezoning/variance/PD conversation (aldermanic prerogative)."""
    ward: int
    alderman: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None


class TrafficSummary(BaseModel):
    """Daily traffic on the nearest counted street (Chicago traffic counts,
    live daily dataset). ``daily_vehicles`` sums both directions of the
    fronting road, averaged over the last week — retail exposure context."""
    road: str | None = None
    daily_vehicles: int | None = None
    directions: int = 0
    from_street: str | None = None
    to_street: str | None = None
    as_of: str | None = None


class CommunityAreaRent(BaseModel):
    """Overall median gross rent of a community area, rebuilt from summed tract bracket counts
    (``ingestion/build_rent_artifact.py``). ``moe`` is the ACS Handbook's margin for an interpolated
    median (``moe_method``), 90% level; ``median`` is None when it falls in the open-ended top bracket."""

    community_area: int
    households: int
    median: int | None = None
    moe: int | None = None
    cv: float | None = None
    top_coded: bool = False
    moe_method: str = "acs_handbook_median"
    design_factor: float | None = None
    acs_period: str | None = None
    acs_release: str | None = None
    period_end: str | None = None


class AssessorModelRent(BaseModel):
    """The Cook County Assessor's modeled apartment income for a community area (WS4 PR3), its OWN series:
    not an ACS rent, not an asking or achieved rent, and never by bedroom count. ``median_per_unit_month`` is
    the median over apartment buildings of the model's potential gross income (before vacancy) per unit per
    month. ``coverage`` is the modeled units' share of the area's ACS renter households with cash rent (None
    when no household count exists); ``priced`` is the sample size the n rule reads. A row with no
    buildings is an area the Assessor models none in, which is a finding, not an error."""

    community_area: int
    buildings: int = 0
    priced: int = 0
    units: int = 0
    households: int | None = None
    coverage: float | None = None
    median_per_unit_month: int | None = None
    year: str
    cycle: str = "city reassessment"
    as_of: str
    dataset: str = "csik-bsws"


class BedroomRent(BaseModel):
    """Median gross rent for one bedroom count, from the parcel's tract when the Census's figure
    passes the confidence rules, otherwise from its PUMA. ``scope`` says which; a PUMA is never
    presented as a community area."""

    bedrooms: str  # one of rent.BEDROOM_GROUPS
    scope: str  # "tract" | "puma"
    geography: str | None = None
    geoid: str | None = None
    estimate: int | None = None
    moe: float | None = None
    cv: float | None = None
    # why the tract's own figure was not used ("suppressed" | "low_confidence"); None when it was used
    tract_fallback: str | None = None


class RentEvidence(BaseModel):
    """Current official rent for a parcel's area (WS4 PR2): the community area's overall median, and the
    published bedroom medians for its tract (else PUMA). ``unchecked`` names the parts that could not be
    fetched, which is never the same as 'the Census publishes none'."""

    community_area: CommunityAreaRent | None = None
    assessor_model: AssessorModelRent | None = None
    bedrooms: list[BedroomRent] = Field(default_factory=list)
    acs_period: str | None = None
    acs_release: str | None = None
    tract_name: str | None = None
    puma_geoid: str | None = None
    puma_name: str | None = None
    unchecked: list[str] = Field(default_factory=list)


class NeighborhoodSummary(BaseModel):
    demographics: DemographicsSummary | None = None
    census_tract: CensusTractDemographics | None = None
    rent: RentEvidence | None = None
    transit: TransitAccess | None = None
    walkscore: WalkScoreSummary | None = None
    ward: WardInfo | None = None
    traffic: TrafficSummary | None = None
    divvy: DivvyAccess | None = None


class TurnSummary(BaseModel):
    """Compact summary of one conversation turn (~100-200 tokens)."""
    turn_index: int
    user_question: str
    location_community_area: int | None = None
    location_community_area_name: str | None = None
    location_address: str | None = None
    workflow_hint: str = "general"
    sources_used: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    code_sections_cited: list[str] = Field(default_factory=list)
    data_as_of: str | None = None


class CodeChunk(BaseModel):
    text: str
    source_document: str
    section: str
    section_title: str
    subsection: str | None = None
    score: float
    cross_references: list[str] = Field(default_factory=list)


class TrendItem(BaseModel):
    category: str
    current_count: int
    prior_count: int
    # None = prior-month count was 0 (percentage undefined; renders as "new").
    change_pct: int | None


class AnalyticsSummary(BaseModel):
    crime_trends: list[TrendItem] | None = None
    three11_trends: list[TrendItem] | None = None
    permit_trends: list[TrendItem] | None = None
    trend_period: str | None = None


class ComparableSale(BaseModel):
    pin: str
    sale_date: str | None = None
    sale_price: float | None = None
    class_code: str | None = None
    class_description: str | None = None
    land_sqft: int | None = None
    bldg_sqft: int | None = None
    price_per_land_sqft: float | None = None
    price_per_bldg_sqft: float | None = None
    deed_type: str | None = None
    sale_type: str | None = None
    distance_mi: float | None = None
    lat: float | None = None
    lon: float | None = None
    # FAR-normalized land basis: sale_price / (land_sqft * FAR). Zone comes from a
    # point-in-polygon against the zoning quilt; None when the comp has no
    # coordinates, falls outside the quilt, or sits in a district with no
    # published FAR (PDs).
    zone_class: str | None = None
    far: float | None = None
    price_per_buildable_sqft: float | None = None
    # "geometry" when land_sqft was backfilled from the ptaxsim parcel polygon
    # because CCAO characteristics (residential-only) had none. None = as-sourced.
    land_sqft_source: str | None = None


class ComparablesSummary(BaseModel):
    median_sale_price: float | None = None
    median_price_per_land_sqft: float | None = None
    median_price_per_bldg_sqft: float | None = None
    median_price_per_buildable_sqft: float | None = None
    # "land_only" (clean land basis) or "mixed" (no vacant-land comps available, so
    # the median includes sales whose price carries a building). Never omit this
    # alongside the median — it is what makes the number readable.
    buildable_median_basis: str | None = None
    buildable_median_n: int | None = None
    price_range_min: float | None = None
    price_range_max: float | None = None
    sales_volume: int = 0
    # Human-readable basis describing the comp set used (class + radius + window),
    # set by the progressive-widening search so the reader can judge comparability.
    comp_basis: str | None = None
    # The comp set's actual search basis (the progressive search widens): radius in miles,
    # window in years, and whether it widened past the first tier.
    comp_radius_mi: float | None = None
    comp_window_years: int | None = None
    comp_widened: bool = False
    sales: list[ComparableSale] = Field(default_factory=list)


class WithheldFigure(BaseModel):
    """A figure the context would have carried but the confidence standard withholds
    (too small a sample, too wide a margin). Its value is removed from the context before the model sees it."""

    fact_id: str
    figure: str  # the figure's label, in words the reader sees
    reason: str  # plain words: "only 2 sales (needs 3)"


class FigureNote(BaseModel):
    """How to name a figure the answer states when it is an estimate, our own calculation, AI-read or from a
    private company (the Profile's captions, in words). Present only for those figures."""

    fact_id: str
    figure: str
    note: str


class UpcomingZoningFiling(BaseModel):
    """One current applicant filing from the Clerk's non-final zoning docket."""

    record_number: str
    title: str
    status: str
    sub_status: str
    introduced_at: str | None = None
    latest_action_at: str | None = None
    url: str
    application_number: str | None = None
    segment: str | None = None
    match_kind: Literal["subject_pin", "subject_range", "nearby"]
    distance_mi: float | None = None


class UpcomingZoningProvenance(BaseModel):
    source_id: str
    as_of: str | None = None
    method: str
    confidence: Literal["standard", "low"]


class PendingTextAffectedFact(BaseModel):
    """A current Profile fact a pending proposal could change, as the Profile states it today."""

    fact_id: str
    label: str
    current_value: str | int | float | bool | None = None
    section: str | None = None
    current_law: str | None = None


class PendingTextEffect(BaseModel):
    """One reviewed way a pending Title 17 amendment could change a rule this Profile uses."""

    id: str
    sections: list[str]
    could_change: str
    reach: Literal["parcel", "untested"]
    reach_note: str | None = None
    affected: list[PendingTextAffectedFact] = Field(default_factory=list)


class PendingTextImpact(BaseModel):
    """A pending (not adopted) Title 17 amendment a committed review maps to this Profile."""

    record_number: str
    lifecycle_id: str
    title: str
    status: str
    sub_status: str
    introduced_at: str | None = None
    latest_action_at: str | None = None
    url: str
    reviewed_on: str
    reviewed_by: str
    basis: Literal["ordinance"]
    summary: str | None = None
    effects: list[PendingTextEffect]


class PendingTextUnreviewed(BaseModel):
    record_number: str
    title: str
    url: str
    introduced_at: str | None = None
    reason: Literal["unreviewed", "outdated"]
    waiting_days: int | None = None


class PendingTextReview(BaseModel):
    """Whether every pending Title 17 text proposal has a current committed review.

    ``complete`` is the only state that lets the Profile say none of the reviewed
    proposals maps to it; ``incomplete`` and ``unavailable`` never read as "none".
    """

    status: Literal["complete", "incomplete", "unavailable"]
    pending_count: int = 0
    reviewed_count: int = 0
    unreviewed: list[PendingTextUnreviewed] = Field(default_factory=list)
    oldest_unreviewed_days: int | None = None
    overdue: bool = False
    review_provenance: UpcomingZoningProvenance | None = None


class UpcomingZoningSummary(BaseModel):
    """Conservative parcel placement of current zoning filings.

    ``ready`` with empty lists is a checked zero. ``stale`` preserves the last-good
    evidence with a warning. ``unavailable`` never claims a zero.
    """

    status: Literal["ready", "stale", "unavailable"]
    placement_status: Literal["complete", "partial"]
    checked_at: str | None = None
    radius_mi: float = 0.5
    subject_filings: list[UpcomingZoningFiling] = Field(default_factory=list)
    nearby_filings: list[UpcomingZoningFiling] = Field(default_factory=list)
    placed_count: int = 0
    unplaced_count: int = 0
    placement_coverage: float | None = None
    record_provenance: UpcomingZoningProvenance
    placement_provenance: UpcomingZoningProvenance
    # Pending Title 17 text amendments that a committed review maps to this Profile
    # (WS2 PR3). Pending proposals never change a current-law answer; they only sit beside it.
    text_impacts: list[PendingTextImpact] = Field(default_factory=list)
    text_review: PendingTextReview | None = None


class ContextObject(BaseModel):
    community_area: int | None = None
    community_area_name: str | None = None
    resolved_address: str | None = None
    # Parcel identity behind the parcel-scoped fields below (see Location.resolution).
    parcel_pin: str | None = None
    parcel_resolution: Literal["authoritative", "approximate"] | None = None
    parcel_resolution_method: str | None = None
    data_as_of: str | None = None
    data_lag_note: str | None = None
    data_lag_days: int | None = None
    data_lag_cutoff: str | None = None
    crime_last_90d: CrimeSummary | None = None
    open_311_requests: ThreeOneOneSummary | None = None
    address_311: Address311Summary | None = None
    permits: PermitSummary | None = None
    violations: ViolationSummary | None = None
    businesses: BusinessSummary | None = None
    vacant_buildings: VacantBuildingSummary | None = None
    food_inspections: FoodInspectionSummary | None = None
    code_chunks: list[CodeChunk] = Field(default_factory=list)
    parcel_zoning: ZoningSummary | None = None
    regulatory: RegulatorySummary | None = None
    # Profile-only. Built from the daily Clerk/Address Points snapshot after
    # parcel identity is reconciled; never fetched from Clerk on the request path.
    upcoming_zoning: UpcomingZoningSummary | None = None
    property: PropertySummary | None = None
    incentives: IncentivesSummary | None = None
    neighborhood: NeighborhoodSummary | None = None
    # Set only on the chat path when a Scorecard handoff supplies pre-resolved
    # grounding (the synthesizer serializes ContextObject, so these reach the LLM
    # with no synthesizer change). The /api/scorecard ContextObject leaves them
    # None — comparables / zone_definition live as siblings on ScorecardResponse.
    comparables: ComparablesSummary | None = None
    zone_definition: dict | None = None
    # The Scorecard's computed verdict (category + binding constraint + caveats),
    # grafted on a parcel handoff so the chat can speak to "what's the constraint
    # here" and carry the verdict's caveats. PARCEL-scoped. Serialized to the LLM
    # with ContextObject (no synthesizer change).
    verdict: dict | None = None
    # Address-scoped building-violation tri-state, grafted from a Scorecard handoff
    # so the chat affirms the SAME at-address fact the page shows. PARCEL-scoped —
    # distinct from the area-level `violations` above (never merge the two).
    address_violations: AddressViolations | None = None
    requires_disclaimer: bool = False
    analytics: AnalyticsSummary | None = None
    partial_failures: list[str] = Field(default_factory=list)
    # WS0 M6, chat path only (None elsewhere, so the Profile's context payload is unchanged).
    # `withheld_figures` and `figure_notes` ride to the model; `provenance` does NOT (the synthesizer
    # excludes it): it is the dated source of every figure, set once when the answer is assembled,
    # sent to the sidebar and stored with the message so a reopened answer keeps the dates it was given.
    provenance: dict[str, dict] | None = Field(default=None, max_length=400)
    withheld_figures: list[WithheldFigure] | None = None
    figure_notes: list[FigureNote] | None = None

    # `property` is a field name in this class body, so spell the builtin out.
    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def adu(self) -> dict | None:
        """Coach house / conversion unit status for THIS parcel's district: allowed by
        right (RT, RM, B1-C2), allowed with the ADU zone's limits (RS in an ADU-Allowed
        Area), or not allowed (RS outside one). Derived from parcel_zoning and the ADU
        overlay, so the Profile, a cold chat turn and a handoff agree. None when the
        district's use table doesn't answer it."""
        if self.parcel_zoning is None:
            return None
        from backend.retrieval.zoning_definitions import adu_status

        adu_overlay = next((o for o in (self.regulatory.overlays if self.regulatory else []) if o.layer_type == "adu_area"), None)
        limits = adu_overlay.detail if adu_overlay else None
        return adu_status(self.parcel_zoning.zone_class, adu_overlay is not None, adu_overlay.name if adu_overlay else None, limits)

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def coverage_notes(self) -> list[dict] | None:
        """Where this page stops, for THIS parcel: what it found that it does not
        assess (a PD, a landmark, a CHRS demolition hold, a recent rezoning, ADU limits)
        and what is true of every parcel (alderman's role, map lag, code vintage, the
        City's official letter). Derived, so the Profile, a cold chat turn and a handoff
        agree. None when no parcel zoning was resolved."""
        if self.parcel_zoning is None:
            return None
        from backend.retrieval.coverage_notes import build_coverage_notes

        return build_coverage_notes(
            zoning=self.parcel_zoning,
            regulatory=self.regulatory,
            property_=self.property,
            neighborhood=self.neighborhood,
            adu=self.adu,
            code_vintage=self.code_vintage,
            code_currency=self.code_currency,
            address=self.resolved_address,
            passed_not_on_map=self.passed_not_on_map,
            passed_landmark_designations=self.passed_landmark_designations,
        )

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def passed_not_on_map(self) -> list[dict] | None:
        """Rezoning ordinances Council has passed that list this address and that the City's zoning
        map does not carry yet (WS1 M5). The district on this page is then the OLD one. Offline: the
        daily sync's snapshot, matched on the parcel's PIN (or, when the PIN is unresolved, its
        address). None when nothing matches or the snapshot can't be trusted. Says "a rezoning listing
        this address", never "this parcel was rezoned", and never to what."""
        if self.parcel_zoning is None:
            return None
        from backend.legislation.rezonings import matches_for

        pin = None if self.parcel_resolution == "approximate" else self.parcel_pin
        return matches_for(
            pin, self.resolved_address, self.parcel_zoning.ordinance_num,
            live_district=getattr(self.parcel_zoning, "zone_class", None),
        ) or None

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def passed_landmark_designations(self) -> list[dict] | None:
        """Chicago Landmark designation ordinances passed lately whose title lists this address, for a parcel
        the City's landmark map does not already show as a landmark (WS1 M5b). A designation reaches the map
        weeks to months after it passes, so the overlays on this page can read "no landmark" in the meantime.
        Offline: the daily sync's snapshot, matched on the parcel's PIN (or, when the PIN is unresolved, its
        address); the parcel's own overlay result decides whether the map already knows (no name is matched).
        None when nothing matches or the snapshot can't be trusted. Says "a designation ordinance listing this
        address", never "this is a landmark"."""
        if self.parcel_pin is None and not self.resolved_address:
            return None
        from backend.legislation.designations import matches_for

        pin = None if self.parcel_resolution == "approximate" else self.parcel_pin
        return matches_for(pin, self.resolved_address, self.regulatory) or None

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def code_currency(self) -> dict | None:
        """The code text's vintage plus what City Council has passed since (WS1 M2):
        for a parcel, every Title 17 amendment, the ones touching what its Profile cites
        first (``parcel_relevant``); for a parcel-less code question, only the amendments
        touching a retrieved chunk's section. Offline (the daily sync's snapshot + the
        committed review file). None when nothing applies."""
        from backend.legislation.currency import code_currency, parcel_cited_sections

        chunk_sections = [c.section for c in self.code_chunks]
        if self.parcel_zoning is None:
            if not chunk_sections:
                return None
            cc = code_currency(chunk_sections=chunk_sections, only_touching=True)
            return cc if cc and cc["amendments"] else None
        overlays = list(self.regulatory.overlays) if self.regulatory else []
        chrs = (getattr(getattr(self.property, "flags", None), "chrs_rating", None) or "").lower()
        cited = parcel_cited_sections(
            self.parcel_zoning.zone_class, overlays, ["14A-4-407.6"] if chrs in ("orange", "red") else [],
        )
        return code_currency(
            cited_sections=cited, chunk_sections=chunk_sections, address=self.resolved_address,
            overlay_types=[o.layer_type for o in overlays],
        )

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def code_vintage(self) -> dict | None:
        """How current the indexed Municipal Code is (its 'current through' date).
        Present whenever the turn resolved a parcel's zoning, so the answer and the
        Profile can say the code text is a snapshot, not live law."""
        if self.parcel_zoning is None:
            return None
        from backend.code_vintage import get_code_vintage

        return get_code_vintage()

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def unit_yield(self) -> dict | None:
        """Max dwelling units this parcel's LOT AREA allows at its district's
        minimum lot area per unit, with the arithmetic and the caveat that other
        standards can bind first. Derived (never stored) from parcel_zoning and
        property.land_sqft, so the Profile, a cold chat turn and a handoff all
        agree. None for districts with no per-unit minimum, or an unknown lot."""
        if self.parcel_zoning is None or self.property is None:
            return None
        from backend.retrieval.regulatory.overlay_facts import in_606_district
        from backend.retrieval.zoning_definitions import max_units_by_lot_area

        return max_units_by_lot_area(self.parcel_zoning.zone_class, self.property.land_sqft,
                                     in_606=in_606_district(self.regulatory))

    @computed_field  # type: ignore[prop-decorator]
    @builtins.property
    def tod_benefits(self) -> dict | None:
        """What transit-served status does and does not change for THIS parcel's
        district (parking relief vs. dash-3-only density bonuses). Derived, never
        stored, so it is right on every path: the Profile payload, a cold chat
        turn, and a Profile->chat handoff that grafts zoning/regulatory in after
        construction. None when the parcel isn't transit-served."""
        reg = self.regulatory
        if reg is None or not reg.in_tod_area:
            return None
        from backend.retrieval.zoning_definitions import tod_benefits

        zone = self.parcel_zoning.zone_class if self.parcel_zoning else None
        return tod_benefits(zone, True, tuple(o.layer_type for o in reg.overlays))


class MapDataRequest(BaseModel):
    community_area: int
    time_range_days: int = 90
    sources: list[str] = Field(default_factory=lambda: ["crime_api", "311_api", "permits_api"])
    address_lat: float | None = None
    address_lon: float | None = None
    address_label: str | None = None


class MapDataResponse(BaseModel):
    crimes: list[dict] = Field(default_factory=list)
    requests_311: list[dict] = Field(default_factory=list)
    building_permits: list[dict] = Field(default_factory=list)
    zoning: dict | None = None
    overlay_districts: dict | None = None
    incentive_zones: dict | None = None
    queried_address: dict | None = None
    capped: dict[str, bool] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    # An assistant answer is bounded by synthesizer_max_tokens (~8k chars); the
    # cap leaves headroom for that while bounding what a forged history can cost.
    content: str = Field(max_length=12_000)


# Chat languages the synthesizer can answer in (keys of synthesizer.LANGUAGE_NAMES + "en").
SUPPORTED_CHAT_LANGUAGES = ("en", "es", "pl", "zh-CN", "zh-TW")
MAX_HISTORY_CHARS = 60_000


class ScorecardContext(BaseModel):
    """Pre-resolved parcel grounding shipped from the Scorecard on a chat handoff.

    The Scorecard already assembled a full ContextObject for this parcel; rather
    than re-running the property/regulatory/incentives retrieval, the chat path
    reads these (post-assembly) sub-objects directly and skips those fetches.
    Selective by design: the neighborhood-activity feeds (crime/311/permits/
    violations/businesses/etc.) and code_chunks are deliberately omitted — those
    are stale-prone or cheaply re-fetched when a question actually needs them.
    The frontend lifts these straight off the held ScorecardResponse:
    `context.{property,regulatory,incentives,parcel_zoning}` + sibling
    `comparables` (sales trimmed) + `zone_definition`.
    """
    pin: str | None = Field(default=None, max_length=20)
    address: str | None = None
    community_area_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    parcel_zoning: ZoningSummary | None = None
    zone_definition: dict | None = None
    property: PropertySummary | None = None
    regulatory: RegulatorySummary | None = None
    incentives: IncentivesSummary | None = None
    comparables: ComparablesSummary | None = None
    # Distilled ScorecardVerdict {category, headline, binding_constraint, reasons,
    # confidence, caveats, signals} — lifted from the held response so the chat
    # can speak to the verdict + carry its caveats. PARCEL-scoped.
    verdict: dict | None = None
    # Address-scoped building-violation tri-state (present/confirmed_zero/
    # unconfirmed), lifted from the held response's address-exact violation lookup
    # so the chat agrees with the page. ADDRESS-scoped — never the area feed.
    address_violations: AddressViolations | None = None
    # Nearest counted street segment (Scorecard Tier-2 traffic chip), lifted so
    # "what's the traffic like here" answers from the number the page shows.
    # Scoped to the nearest measured street — not a parcel attribute.
    traffic: TrafficSummary | None = None


class ChatRequest(BaseModel):
    message: str = Field(max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=20)
    conversation_id: str | None = Field(default=None, max_length=100)
    upload_ids: list[str] = Field(default_factory=list, max_length=3)
    cached_community_area: int | None = None
    language: str = Field(default="en", max_length=16)
    # 14-digit parcel hint from a Scorecard handoff — resolves the turn's
    # location authoritatively instead of re-geocoding the question text.
    parcel_pin: str | None = Field(default=None, max_length=20)
    # Pre-resolved parcel grounding from the Scorecard (bypass: skips the
    # property/regulatory/incentives re-fetch, see _retrieve). Never persisted
    # into stored history — same stripping rule as the context/plan/map blobs.
    scorecard_context: ScorecardContext | None = None

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, v: str) -> str:
        # The value is interpolated into the system prompt, so only known codes
        # get through. Browser locales like "es-ES" map to their base language;
        # anything else falls back to English rather than failing the request.
        if v in SUPPORTED_CHAT_LANGUAGES:
            return v
        base = v.split("-")[0].lower()
        return base if base in SUPPORTED_CHAT_LANGUAGES else "en"

    @model_validator(mode="after")
    def _cap_history_size(self) -> "ChatRequest":
        total = sum(len(m.content) for m in self.history)
        if total > MAX_HISTORY_CHARS:
            raise ValueError(f"history too large ({total} chars; max {MAX_HISTORY_CHARS})")
        return self


class ChatChunk(BaseModel):
    type: Literal["plan", "context", "map_data", "token", "error", "done", "turn_summary"]
    plan: RetrievalPlan | None = None
    context: ContextObject | None = None
    map_data: MapDataResponse | None = None
    text: str | None = None
    error: str | None = None
    turn_summary: dict | None = None
    # Wall-clock milliseconds since the /chat request was received. Set on
    # phase-boundary events (plan, context, done, error) and on the first
    # synthesis token. Lets clients render per-phase latency without holding
    # their own timer, and lets the eval harness compute p50/p95 offline.
    t_ms: int | None = None
    timings: dict[str, int] | None = None
    # On `done`: citation markers in the answer that aren't backed by this
    # turn's context (see backend/citations.py). Empty/None when all check out.
    citation_warnings: list[str] | None = None
    # On `done`: True when the answer hit the synthesizer's token cap and was cut
    # off mid-answer. A visible notice is also appended to the streamed text, so
    # clients that ignore this flag (and saved/exported conversations) still show it.
    truncated: bool | None = None


class StoredMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    context: ContextObject | None = None
    plan: RetrievalPlan | None = None
    map_data: dict | None = None
    map_fetched_at: int | None = None
    summary: TurnSummary | None = None


class SaveMessagesRequest(BaseModel):
    messages: list[StoredMessage]


class ImportConversation(BaseModel):
    id: str
    title: str
    messages: list[dict]
    createdAt: int
    updatedAt: int


class ImportRequest(BaseModel):
    conversations: list[ImportConversation]


# --- PDF Report v2 models ---


class ZoningStandards(BaseModel):
    far: float | None = None
    max_height_ft: int | None = None
    max_stories: int | None = None
    lot_coverage_pct: float | None = None
    # Minimum lot AREA (size of the zoning lot — an R-district standard only).
    min_lot_area_sqft: int | None = None
    # Minimum lot area PER DWELLING UNIT (the as-of-right density control in
    # R/B/C/D districts) — a different standard; do not conflate with the above.
    min_lot_area_per_unit_sqft: int | None = None
    front_setback_ft: int | None = None
    side_setback_ft: int | None = None
    rear_setback_ft: int | None = None
    parking_residential: str | None = None
    parking_commercial: str | None = None
    permitted_uses: list[str] = Field(default_factory=list)
    special_uses: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # "definitions" = synthesized from the deterministic Title 17 zone-class
    # reference table (zoning_definitions.py) when AI extraction was unavailable
    # or low-confidence. Treated as authoritative for base-district standards.
    extraction_confidence: Literal["high", "medium", "low", "definitions"] = "medium"


class DevelopmentPotential(BaseModel):
    max_buildable_sqft: int | None = None
    max_lot_coverage_sqft: int | None = None
    development_surplus_sqft: int | None = None
    parking_spaces_estimated: int | None = None


class NearbyDevelopment(BaseModel):
    new_construction_count: int = 0
    demolition_count: int = 0
    # True area/window total of reported_cost over NEW CONSTRUCTION permits
    # (server-side aggregate; excludes demolition costs). The old figure summed
    # the capped recent_projects sample and mixed both permit types.
    new_construction_cost: float = 0.0
    recent_projects: list[dict] = Field(default_factory=list)


class ReportData(BaseModel):
    address: str | None = None
    lat: float = 0.0
    lon: float = 0.0
    # Render language for the PDF report ("en"/"es"). Set by _fetch_report_data so
    # the deterministic narrative builders localize their output (no LLM).
    language: str = "en"
    community_area: int | None = None
    community_area_name: str | None = None
    context: ContextObject
    zoning_standards: ZoningStandards | None = None
    development_potential: DevelopmentPotential | None = None
    comparables: ComparablesSummary | None = None
    address_permits: list[dict] = Field(default_factory=list)
    address_violations: list[dict] = Field(default_factory=list)
    adjacent_zoning: dict[str, str | None] = Field(default_factory=dict)
    nearby_development: NearbyDevelopment | None = None
    effective_tax_rate: float | None = None
    market_value: float | None = None
    # Cook County assessment level used to derive market_value (0.10
    # residential, 0.25 commercial, …) — rendered in the market-value hint so
    # the derivation is stated, not assumed residential.
    assessment_level: float | None = None
    assessment_trend: dict | None = None
    ownership_signals: list[dict] = Field(default_factory=list)
    parcel_map_b64: str | None = None
    parcel_dimensions: dict | None = None
    static_map_url: str | None = None
    comps_chart_b64: str | None = None
    comps_map_b64: str | None = None
    zoning_map_b64: str | None = None
    construction_map_b64: str | None = None
    bulk_standards_text: str = ""
    zone_definitions: list[dict] = Field(default_factory=list)
    partial_failures: list[str] = Field(default_factory=list)
    # R7 parcel-resolution provenance. resolved_pin is the system-of-record parcel
    # identity; resolved_confidence is "authoritative" or "approximate" and drives
    # the INV-5 disclosure on the report cover when resolution was degraded.
    resolved_pin: str | None = None
    resolved_confidence: str | None = None
    # WS0 M5: where each figure came from and how far to trust it (report_provenance.entries_for_report),
    # filled when the report is rendered; the Data Sources table is built from it.
    provenance: dict[str, dict] = Field(default_factory=dict)
    # V5 synthesis fields
    opportunities: list[dict] = Field(default_factory=list)
    constraints: list[dict] = Field(default_factory=list)
    estimated_land_value: dict | None = None
    approval_pathway: dict | None = None
    development_trend: dict | None = None
    incentive_stacking_narrative: str | None = None
    envelope_summary: str | None = None
    envelope_map_b64: str | None = None
    buildable_footprint_sqft: float | None = None
    # Phase 3 — decision-quality synthesis (all deterministic, no LLM)
    decision_box: dict | None = None
    far_utilization: dict | None = None
    unit_yield: dict | None = None
    comp_valuation: dict | None = None
    ownership_interpretation: str | None = None


# ---------------------------------------------------------------------------
# Usage analytics
# ---------------------------------------------------------------------------

class EventPayload(BaseModel):
    event_name: str
    event_data: dict | None = None
    session_id: str
    visitor_id: str
    page: str | None = None
    address: str | None = None
    timestamp: int | None = None


class EventBatch(BaseModel):
    events: list[EventPayload] = Field(max_length=50)
