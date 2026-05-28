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


class ThreeOneOneSummary(BaseModel):
    total: int
    oldest_open_days: int | None
    by_department: dict[str, int]
    top_types: list[str]


class PermitSummary(BaseModel):
    total: int
    total_estimated_cost: float
    top_work_descriptions: list[str]


class ViolationSummary(BaseModel):
    total: int
    open_count: int
    top_descriptions: list[str]


class BusinessSummary(BaseModel):
    total: int
    top_activities: list[str]


class CodeChunk(BaseModel):
    text: str
    source_document: str
    section: str
    section_title: str
    subsection: str | None = None
    score: float
    cross_references: list[str] = Field(default_factory=list)


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
    requires_disclaimer: bool = False


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)


class ChatChunk(BaseModel):
    type: Literal["plan", "context", "token", "error", "done"]
    plan: RetrievalPlan | None = None
    context: ContextObject | None = None
    text: str | None = None
    error: str | None = None
