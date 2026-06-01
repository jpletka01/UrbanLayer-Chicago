export type Role = "user" | "assistant";

export interface UploadMeta {
  id: string;
  conversation_id: string;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  created_at: number;
}

export interface Message {
  role: Role;
  content: string;
  context?: ContextObject;
  plan?: RetrievalPlan;
  mapData?: MapData;
  mapFetchedAt?: number;
  attachments?: UploadMeta[];
}

export type SourceTag =
  | "crime_api"
  | "311_api"
  | "permits_api"
  | "violations_api"
  | "business_api"
  | "vector_search"
  | "regulatory_domain"
  | "property_domain"
  | "incentives_domain"
  | "neighborhood_domain";

export interface Location {
  raw: string;
  type: "intersection" | "address" | "neighborhood" | "community_area" | "none";
  resolved_community_area: number | null;
  resolved_community_area_name: string | null;
  resolved_address: string | null;
  resolved_lat: number | null;
  resolved_lon: number | null;
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

export interface TrendItem {
  category: string;
  current_count: number;
  prior_count: number;
  change_pct: number;
}

export interface AnalyticsSummary {
  crime_trends: TrendItem[] | null;
  three11_trends: TrendItem[] | null;
  permit_trends: TrendItem[] | null;
  trend_period: string | null;
}

export interface ZoningSummary {
  zone_class: string;
  zone_type: number | null;
  ordinance_num: string | null;
  zoning_map_url: string;
}

export interface OverlayDistrict {
  layer_type: string;
  name: string | null;
  ordinance: string | null;
  description: string | null;
}

export interface RegulatorySummary {
  overlays: OverlayDistrict[];
  in_planned_development: boolean;
  in_landmark_district: boolean;
  is_landmark_building: boolean;
  in_historic_district: boolean;
  on_national_register: boolean;
  in_lakefront_protection: boolean;
  on_pedestrian_street: boolean;
  in_special_district: boolean;
  in_pmd: boolean;
  in_tod_area: boolean;
  in_adu_area: boolean;
  in_aro_zone: boolean;
  in_ssa: boolean;
  ssa_name: string | null;
  flood_zone: string | null;
  flood_zone_subtype: string | null;
  in_special_flood_hazard: boolean;
  brownfield_sites: Record<string, unknown>[];
}

export interface AssessmentRecord {
  year: number | null;
  land: number | null;
  building: number | null;
  total: number | null;
}

export interface SaleRecord {
  date: string | null;
  price: number | null;
  deed_type: string | null;
}

export interface PropertySummary {
  pin14: string | null;
  address: string | null;
  bldg_class: string | null;
  bldg_class_description: string | null;
  bldg_sqft: number | null;
  land_sqft: number | null;
  stories: number | null;
  units: number | null;
  rooms: number | null;
  bedrooms: number | null;
  full_baths: number | null;
  half_baths: number | null;
  bldg_age: number | null;
  total_assessed_value: number | null;
  assessment_history: AssessmentRecord[];
  sales_history: SaleRecord[];
  parcel_geometry?: Record<string, unknown> | null;
}

export interface IncentivesSummary {
  in_tif_district: boolean;
  tif_name: string | null;
  tif_year_start: number | null;
  tif_end_year: number | null;
  tif_total_revenue: number | null;
  tif_total_expenditure: number | null;
  tif_financials: Record<string, unknown>[];
  in_opportunity_zone: boolean;
  oz_tract: string | null;
  in_enterprise_zone: boolean;
  enterprise_zone_name: string | null;
  census_tract: string | null;
}

export interface DemographicsSummary {
  community_area: number | null;
  community_area_name: string | null;
  population: number | null;
  median_household_income: number | null;
  median_home_value: number | null;
  median_gross_rent: number | null;
  median_age: number | null;
  poverty_rate: number | null;
  unemployment_rate: number | null;
  owner_occupied_pct: number | null;
  bachelors_degree_pct: number | null;
  vacancy_rate: number | null;
}

export interface TransitAccess {
  nearest_cta_rail: string | null;
  cta_rail_distance_mi: number | null;
  cta_lines: string[];
  nearest_metra: string | null;
  metra_distance_mi: number | null;
  metra_line: string | null;
  tod_eligible: boolean;
  tod_type: string | null;
}

export interface NeighborhoodSummary {
  demographics: DemographicsSummary | null;
  transit: TransitAccess | null;
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
  parcel_zoning?: ZoningSummary | null;
  regulatory?: RegulatorySummary | null;
  property?: PropertySummary | null;
  incentives?: IncentivesSummary | null;
  neighborhood?: NeighborhoodSummary | null;
  requires_disclaimer: boolean;
  analytics?: AnalyticsSummary | null;
  partial_failures?: string[];
}

export type ChatChunk =
  | { type: "plan"; plan: RetrievalPlan; t_ms?: number }
  | { type: "context"; context: ContextObject; t_ms?: number }
  | { type: "map_data"; map_data: MapData; t_ms?: number }
  | { type: "token"; text: string; t_ms?: number }
  | { type: "error"; error: string; t_ms?: number }
  | { type: "done"; t_ms?: number };

export interface PhaseTimings {
  router_ms?: number;
  retrieval_ms?: number;
  first_token_ms?: number;
  total_ms?: number;
}

export interface TransitStation {
  name: string;
  lat: number;
  lon: number;
  type: "cta_rail" | "metra";
  lines?: string[];
  line?: string;
}

export type SidebarView = "data" | "sources";

export interface MapCrime {
  latitude: number;
  longitude: number;
  primary_type: string;
  date: string;
  description: string;
  arrest: boolean | string;
}

export interface MapRequest311 {
  latitude: number;
  longitude: number;
  sr_type: string;
  status: string;
  created_date: string;
  owner_department: string;
}

export interface MapPermit {
  latitude: number;
  longitude: number;
  permit_type: string;
  work_description: string;
  estimated_cost: number;
  issue_date: string;
}

export interface QueriedAddress {
  latitude: number;
  longitude: number;
  label: string;
}

export interface MapData {
  crimes: MapCrime[];
  requests_311: MapRequest311[];
  building_permits: MapPermit[];
  zoning?: Record<string, unknown> | null;
  queried_address: QueriedAddress | null;
  capped?: Record<string, boolean>;
}

export type DataSource = "crime" | "311" | "permits" | "violations" | "business";

export interface AddressSuggestion {
  address: string;
  lat: number;
  lon: number;
}

export interface Conversation {
  id: string;
  title: string;
  message_count: number;
  createdAt: number;
  updatedAt: number;
}

export interface StoredMessage {
  role: Role;
  content: string;
  context?: ContextObject | null;
  plan?: RetrievalPlan | null;
  map_data?: MapData | null;
  map_fetched_at?: number | null;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: StoredMessage[];
  created_at: number;
  updated_at: number;
}

// ---------------------------------------------------------------------------
// Admin dashboard types
// ---------------------------------------------------------------------------

export interface ModelUsage {
  count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface PhaseUsage {
  count: number;
  input_tokens: number;
  output_tokens: number;
  avg_duration_ms: number;
  estimated_cost_usd: number;
}

export interface AdminOverview {
  total_requests: number;
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_tokens: number;
  estimated_cost_usd: number;
  error_count: number;
  by_model: Record<string, ModelUsage>;
  by_phase: Record<string, PhaseUsage>;
}

export interface TimeseriesBucket {
  bucket: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  avg_duration_ms: number;
  error_count: number;
}

export interface LatencyPercentiles {
  phase: string;
  p50_ms: number;
  p90_ms: number;
  p99_ms: number;
  count: number;
}

export interface ConversationStats {
  total_conversations: number;
  total_messages: number;
  avg_messages_per_conversation: number;
  conversations_today: number;
}

export interface RequestLogEntry {
  id: number;
  request_group: string;
  conversation_id: string | null;
  user_message: string;
  intent: string | null;
  community_area_name: string | null;
  sources: string[];
  total_duration_ms: number;
  status: string;
  error_message: string | null;
  created_at: number;
}

export interface BenchmarkResults {
  grade_distribution: Record<string, number>;
  total_queries: number;
  avg_score: number;
  last_run: string | null;
  per_query: Array<{ id: string; grade: string; score: number; issues: string[] }>;
}

export interface JudgeDimensionScore {
  dimension: string;
  grade: string;
  reasoning: string;
}

export interface JudgeQueryResult {
  id: string;
  question: string;
  overall_grade: string;
  overall_reasoning: string;
  dimensions: JudgeDimensionScore[];
}

export interface JudgeDimensionSummary {
  avg_numeric: number;
  grade_distribution: Record<string, number>;
}

export interface JudgeResults {
  overall_grade_distribution: Record<string, number>;
  dimension_summaries: Record<string, JudgeDimensionSummary>;
  total_queries: number;
  skipped_queries: number;
  avg_score: number;
  last_run: string | null;
  per_query: JudgeQueryResult[];
}
