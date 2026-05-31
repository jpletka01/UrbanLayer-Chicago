from typing import Literal

from pydantic import BaseModel, Field


SourceTag = Literal[
    "crime_api",
    "311_api",
    "permits_api",
    "violations_api",
    "business_api",
    "vector_search",
]

IntentTag = Literal[
    "neighborhood_overview",
    "incident_lookup",
    "legal_question",
    "event_query",
    "trend_analysis",
    "clarification_needed",
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
    requires_disclaimer: bool = False
    analytics: AnalyticsSummary | None = None


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
    queried_address: dict | None = None
    capped: dict[str, bool] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)
    conversation_id: str | None = None


class ChatChunk(BaseModel):
    type: Literal["plan", "context", "map_data", "token", "error", "done"]
    plan: RetrievalPlan | None = None
    context: ContextObject | None = None
    map_data: MapDataResponse | None = None
    text: str | None = None
    error: str | None = None
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


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[StoredMessage]
    created_at: int
    updated_at: int


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
