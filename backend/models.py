from typing import Literal

from pydantic import BaseModel, Field


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


class ZoningSummary(BaseModel):
    zone_class: str
    zone_type: int | None = None
    ordinance_num: str | None = None
    zoning_map_url: str = "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"


class OverlayDistrict(BaseModel):
    layer_type: str
    name: str | None = None
    ordinance: str | None = None
    description: str | None = None


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
    in_special_flood_hazard: bool = False
    brownfield_sites: list[dict] = Field(default_factory=list)
    aro_housing: AROHousingSummary | None = None


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
    community_area: int | None = None
    community_area_name: str | None = None
    population: int | None = None
    median_household_income: int | None = None
    median_home_value: int | None = None
    median_gross_rent: int | None = None
    median_age: float | None = None
    poverty_rate: float | None = None
    unemployment_rate: float | None = None
    owner_occupied_pct: float | None = None
    bachelors_degree_pct: float | None = None
    vacancy_rate: float | None = None


class DistributionBucket(BaseModel):
    label: str
    value: float


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
    bachelors_or_higher_pct: float | None = None
    foreign_born_pct: float | None = None

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


class NeighborhoodSummary(BaseModel):
    demographics: DemographicsSummary | None = None
    census_tract: CensusTractDemographics | None = None
    transit: TransitAccess | None = None
    walkscore: WalkScoreSummary | None = None
    ward: WardInfo | None = None
    traffic: TrafficSummary | None = None


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


class ComparablesSummary(BaseModel):
    median_sale_price: float | None = None
    median_price_per_land_sqft: float | None = None
    median_price_per_bldg_sqft: float | None = None
    price_range_min: float | None = None
    price_range_max: float | None = None
    sales_volume: int = 0
    # Human-readable basis describing the comp set used (class + radius + window),
    # set by the progressive-widening search so the reader can judge comparability.
    comp_basis: str | None = None
    sales: list[ComparableSale] = Field(default_factory=list)


class ContextObject(BaseModel):
    community_area: int | None = None
    community_area_name: str | None = None
    resolved_address: str | None = None
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
    content: str


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
    conversation_id: str | None = None
    upload_ids: list[str] = Field(default_factory=list)
    cached_community_area: int | None = None
    language: str = "en"
    # 14-digit parcel hint from a Scorecard handoff — resolves the turn's
    # location authoritatively instead of re-geocoding the question text.
    parcel_pin: str | None = Field(default=None, max_length=20)
    # Pre-resolved parcel grounding from the Scorecard (bypass: skips the
    # property/regulatory/incentives re-fetch, see _retrieve). Never persisted
    # into stored history — same stripping rule as the context/plan/map blobs.
    scorecard_context: ScorecardContext | None = None


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


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int
    message_count: int


class StoredMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    context: ContextObject | None = None
    plan: RetrievalPlan | None = None
    map_data: dict | None = None
    map_fetched_at: int | None = None
    summary: TurnSummary | None = None


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[StoredMessage]
    created_at: int
    updated_at: int


class SaveMessagesRequest(BaseModel):
    messages: list[StoredMessage]


class UploadMeta(BaseModel):
    id: str
    conversation_id: str
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: int


class ImportConversation(BaseModel):
    id: str
    title: str
    messages: list[dict]
    createdAt: int
    updatedAt: int


class ImportRequest(BaseModel):
    conversations: list[ImportConversation]


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture_url: str | None = None
    tier: str = "free"


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_required: bool = True
    user: UserResponse | None = None


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
