from typing import Literal

from pydantic import BaseModel, Field


SourceTag = Literal[
    "crime_api",
    "311_api",
    "permits_api",
    "violations_api",
    "business_api",
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


class RetrievalPlan(BaseModel):
    sources: list[SourceTag] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    intent: IntentTag = "neighborhood_overview"
    time_range_days: int = 90
    requires_disclaimer: bool = False
    search_query: str | None = None
    clarification: str | None = None
    workflow_hint: WorkflowHint = "general"


class CrimeSummary(BaseModel):
    total: int
    arrest_rate: float
    by_type: dict[str, int]
    capped: bool = False


class ThreeOneOneSummary(BaseModel):
    total: int
    oldest_open_days: int | None
    by_department: dict[str, int]
    top_types: list[str]
    capped: bool = False


class PermitSummary(BaseModel):
    total: int
    total_estimated_cost: float
    by_type: dict[str, int] = Field(default_factory=dict)
    top_work_descriptions: list[str]
    capped: bool = False


class ViolationSummary(BaseModel):
    total: int
    open_count: int
    by_category: dict[str, int] = Field(default_factory=dict)
    top_descriptions: list[str]
    capped: bool = False


class BusinessSummary(BaseModel):
    total: int
    by_license_type: dict[str, int] = Field(default_factory=dict)
    top_activities: list[str]
    capped: bool = False


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


class PropertySummary(BaseModel):
    pin14: str | None = None
    address: str | None = None
    bldg_class: str | None = None
    bldg_class_description: str | None = None
    bldg_sqft: int | None = None
    land_sqft: int | None = None
    stories: int | None = None
    units: int | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    full_baths: int | None = None
    half_baths: int | None = None
    bldg_age: int | None = None
    total_assessed_value: float | None = None
    estimated_annual_tax: float | None = None
    tax_code: str | None = None
    tax_breakdown: list[TaxLineItem] = Field(default_factory=list)
    assessment_history: list[AssessmentRecord] = Field(default_factory=list)
    sales_history: list[SaleRecord] = Field(default_factory=list)
    parcel_geometry: dict | None = None


class IncentivesSummary(BaseModel):
    in_tif_district: bool = False
    tif_name: str | None = None
    tif_year_start: int | None = None
    tif_end_year: int | None = None
    tif_total_revenue: float | None = None
    tif_total_expenditure: float | None = None
    tif_financials: list[dict] = Field(default_factory=list)
    tif_districts_in_area: list[dict] | None = None
    in_opportunity_zone: bool = False
    oz_tract: str | None = None
    in_enterprise_zone: bool = False
    enterprise_zone_name: str | None = None
    census_tract: str | None = None


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


class NeighborhoodSummary(BaseModel):
    demographics: DemographicsSummary | None = None
    census_tract: CensusTractDemographics | None = None
    transit: TransitAccess | None = None
    walkscore: WalkScoreSummary | None = None


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
    change_pct: int


class AnalyticsSummary(BaseModel):
    crime_trends: list[TrendItem] | None = None
    three11_trends: list[TrendItem] | None = None
    permit_trends: list[TrendItem] | None = None
    trend_period: str | None = None


class ContextObject(BaseModel):
    community_area: int | None = None
    community_area_name: str | None = None
    resolved_address: str | None = None
    data_as_of: str | None = None
    data_lag_note: str | None = None
    crime_last_90d: CrimeSummary | None = None
    open_311_requests: ThreeOneOneSummary | None = None
    permits: PermitSummary | None = None
    violations: ViolationSummary | None = None
    businesses: BusinessSummary | None = None
    code_chunks: list[CodeChunk] = Field(default_factory=list)
    parcel_zoning: ZoningSummary | None = None
    regulatory: RegulatorySummary | None = None
    property: PropertySummary | None = None
    incentives: IncentivesSummary | None = None
    neighborhood: NeighborhoodSummary | None = None
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


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)
    conversation_id: str | None = None
    upload_ids: list[str] = Field(default_factory=list)


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
