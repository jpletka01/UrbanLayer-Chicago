export type Role = "user" | "assistant";

export interface Message {
  role: Role;
  content: string;
}

export type SourceTag =
  | "crime_api"
  | "311_api"
  | "permits_api"
  | "violations_api"
  | "business_api"
  | "vector_search";

export interface Location {
  raw: string;
  type: "intersection" | "address" | "neighborhood" | "community_area" | "none";
  resolved_community_area: number | null;
  resolved_community_area_name: string | null;
  resolved_address: string | null;
}

export interface RetrievalPlan {
  sources: SourceTag[];
  location: Location;
  intent: string;
  time_range_days: number;
  requires_disclaimer: boolean;
  search_query: string | null;
  clarification: string | null;
}

export interface CrimeSummary {
  total: number;
  arrest_rate: number;
  by_type: Record<string, number>;
}

export interface ThreeOneOneSummary {
  total: number;
  oldest_open_days: number | null;
  by_department: Record<string, number>;
  top_types: string[];
}

export interface PermitSummary {
  total: number;
  total_estimated_cost: number;
  top_work_descriptions: string[];
}

export interface ViolationSummary {
  total: number;
  open_count: number;
  top_descriptions: string[];
}

export interface BusinessSummary {
  total: number;
  top_activities: string[];
}

export interface CodeChunk {
  text: string;
  source_document: string;
  section: string;
  section_title: string;
  subsection: string | null;
  score: number;
  cross_references: string[];
}

export interface ContextObject {
  community_area: number | null;
  community_area_name: string | null;
  resolved_address: string | null;
  data_as_of: string | null;
  data_lag_note: string | null;
  crime_last_90d: CrimeSummary | null;
  open_311_requests: ThreeOneOneSummary | null;
  permits: PermitSummary | null;
  violations: ViolationSummary | null;
  businesses: BusinessSummary | null;
  code_chunks: CodeChunk[];
  requires_disclaimer: boolean;
}

export type ChatChunk =
  | { type: "plan"; plan: RetrievalPlan; t_ms?: number }
  | { type: "context"; context: ContextObject; t_ms?: number }
  | { type: "token"; text: string; t_ms?: number }
  | { type: "error"; error: string; t_ms?: number }
  | { type: "done"; t_ms?: number };

export interface PhaseTimings {
  router_ms?: number;
  retrieval_ms?: number;
  first_token_ms?: number;
  total_ms?: number;
}

export type SidebarView = "data" | "sources";
