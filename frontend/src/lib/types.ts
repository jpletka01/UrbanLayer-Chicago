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
  turnSummary?: TurnSummary;
}

export type SourceTag =
  | "crime_api"
  | "311_api"
  | "permits_api"
  | "violations_api"
  | "business_api"
  | "vacant_buildings_api"
  | "food_inspections_api"
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

export interface CrimeYoYItem {
  category: string;
  current_count: number;
  prior_year_count: number;
  change_pct: number;
}

export interface CrimeSummary {
  total: number;
  arrest_rate: number;
  by_type: Record<string, number>;
  yoy?: CrimeYoYItem[] | null;
  yoy_period?: string | null;
  capped?: boolean;
}

export interface ThreeOneOneSummary {
  total: number;
  oldest_open_days: number | null;
  by_department: Record<string, number>;
  top_types: string[];
  capped?: boolean;
}

export interface Address311Summary {
  total: number;
  open_count: number;
  by_type: Record<string, number>;
  high_risk_flags: string[];
}

export interface PermitSummary {
  total: number;
  total_estimated_cost: number;
  by_type: Record<string, number>;
  top_work_descriptions: string[];
  recent_contractors?: string[];
  capped?: boolean;
}

export interface ViolationSummary {
  total: number;
  open_count: number;
  by_category: Record<string, number>;
  top_descriptions: string[];
  capped?: boolean;
}

export interface BusinessSummary {
  total: number;
  by_license_type: Record<string, number>;
  top_activities: string[];
  capped?: boolean;
}

export interface VacantBuildingReport {
  address: string;
  date: string | null;
  violation_type: string | null;
  responsible_entity: string | null;
  amount_due: number | null;
}

export interface VacantBuildingSummary {
  total: number;
  by_department: Record<string, number>;
  recent_reports: VacantBuildingReport[];
}

export interface FoodInspectionDetail {
  name: string;
  facility_type: string | null;
  risk: string | null;
  result: string | null;
  date: string | null;
}

export interface FoodInspectionSummary {
  total: number;
  by_result: Record<string, number>;
  by_risk: Record<string, number>;
  fail_rate: number | null;
  recent_inspections: FoodInspectionDetail[];
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
  aro_housing: AROHousingSummary | null;
}

export interface AROHousingProject {
  name: string;
  address: string | null;
  units: number | null;
  property_type: string | null;
}

export interface AROHousingSummary {
  total_projects: number;
  total_units: number;
  projects: AROHousingProject[];
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

export interface TaxLineItem {
  agency: string;
  rate: number;
  amount: number;
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
  estimated_annual_tax: number | null;
  tax_code: string | null;
  tax_breakdown: TaxLineItem[];
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
  tif_property_tax_revenue: number | null;
  tif_cumulative_revenue: number | null;
  tif_fund_balance: number | null;
  tif_annual_expenditure: number | null;
  tif_fund_history: Record<string, unknown>[];
  tif_financials: Record<string, unknown>[];
  tif_districts_in_area?: Record<string, unknown>[] | null;
  in_opportunity_zone: boolean;
  oz_tract: string | null;
  in_enterprise_zone: boolean;
  enterprise_zone_name: string | null;
  in_qct: boolean;
  qct_tract: string | null;
  in_nmtc: boolean;
  nmtc_tract: string | null;
  nmtc_severe_distress: boolean;
  nmtc_poverty_rate: number | null;
  census_tract: string | null;
  property_tax_class: string | null;
  tax_incentive_description: string | null;
  grant_programs: GrantProgramSummary | null;
}

export interface GrantProject {
  name: string;
  program: string;
  incentive_amount: number | null;
  total_cost: number | null;
  property_type: string | null;
  description: string | null;
  date: string | null;
}

export interface GrantProgramSummary {
  total_projects: number;
  total_funding: number;
  by_program: Record<string, number>;
  recent_projects: GrantProject[];
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

export interface WalkScoreSummary {
  walk_score: number | null;
  walk_description: string | null;
  transit_score: number | null;
  transit_description: string | null;
  bike_score: number | null;
  bike_description: string | null;
  ws_link: string | null;
}

export interface DistributionBucket {
  label: string;
  value: number;
}

export interface CensusTractDemographics {
  tract_fips: string;
  tract_name: string | null;
  census_reporter_url: string | null;
  population: number | null;
  median_household_income: number | null;
  per_capita_income: number | null;
  median_age: number | null;
  median_home_value: number | null;
  median_gross_rent: number | null;
  owner_occupied_pct: number | null;
  vacancy_rate: number | null;
  poverty_rate: number | null;
  bachelors_or_higher_pct: number | null;
  foreign_born_pct: number | null;
  age_distribution: DistributionBucket[];
  income_distribution: DistributionBucket[];
  race_distribution: DistributionBucket[];
  education_distribution: DistributionBucket[];
  transportation_distribution: DistributionBucket[];
  county_median_income: number | null;
  city_median_income: number | null;
}

export interface NeighborhoodSummary {
  demographics: DemographicsSummary | null;
  census_tract: CensusTractDemographics | null;
  transit: TransitAccess | null;
  walkscore: WalkScoreSummary | null;
}

export interface ComparableSale {
  pin: string;
  sale_date: string | null;
  sale_price: number | null;
  class_code: string | null;
  class_description: string | null;
  land_sqft: number | null;
  bldg_sqft: number | null;
  price_per_land_sqft: number | null;
  price_per_bldg_sqft: number | null;
  deed_type: string | null;
  sale_type: string | null;
  distance_mi: number | null;
}

export interface ComparablesSummary {
  median_sale_price: number | null;
  median_price_per_land_sqft: number | null;
  median_price_per_bldg_sqft: number | null;
  price_range_min: number | null;
  price_range_max: number | null;
  sales_volume: number;
  sales: ComparableSale[];
}

export interface ContextObject {
  community_area: number | null;
  community_area_name: string | null;
  resolved_address: string | null;
  data_as_of: string | null;
  data_lag_note: string | null;
  data_lag_days: number | null;
  data_lag_cutoff: string | null;
  crime_last_90d: CrimeSummary | null;
  open_311_requests: ThreeOneOneSummary | null;
  address_311?: Address311Summary | null;
  permits: PermitSummary | null;
  violations: ViolationSummary | null;
  businesses: BusinessSummary | null;
  vacant_buildings: VacantBuildingSummary | null;
  food_inspections: FoodInspectionSummary | null;
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

export interface TurnSummary {
  turn_index: number;
  user_question: string;
  location_community_area: number | null;
  location_community_area_name: string | null;
  location_address: string | null;
  workflow_hint: string;
  sources_used: string[];
  key_facts: string[];
  code_sections_cited: string[];
  data_as_of: string | null;
}

export type ChatChunk =
  | { type: "plan"; plan: RetrievalPlan; t_ms?: number }
  | { type: "context"; context: ContextObject; t_ms?: number }
  | { type: "map_data"; map_data: MapData; t_ms?: number }
  | { type: "token"; text: string; t_ms?: number }
  | { type: "error"; error: string; t_ms?: number }
  | { type: "done"; t_ms?: number; timings?: PhaseTimings }
  | { type: "turn_summary"; turn_summary: TurnSummary; t_ms?: number };

export interface PhaseTimings {
  conv_synth?: number;
  router?: number;
  retrieval?: number;
  first_token?: number;
  total?: number;
}

export interface TransitStation {
  name: string;
  lat: number;
  lon: number;
  type: "cta_rail" | "metra";
  lines?: string[];
  line?: string;
}

export type SidebarView = "data" | "sources" | "map";

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
  overlay_districts?: Record<string, unknown> | null;
  incentive_zones?: Record<string, unknown> | null;
  queried_address: QueriedAddress | null;
  capped?: Record<string, boolean>;
}

export type DataSource = "crime" | "311" | "permits" | "violations" | "business";

export interface ActivityItem {
  id: string;
  label: string;
  status: "active" | "done";
}

export interface AddressSuggestion {
  address: string;
  lat: number;
  lon: number;
}

export interface Conversation {
  id: string;
  title: string;
  language?: string;
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
  summary?: TurnSummary | null;
}

export interface ConversationDetail {
  id: string;
  title: string;
  language?: string;
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
