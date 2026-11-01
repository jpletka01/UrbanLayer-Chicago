import type { Provenance } from "./api";

export type Role = "user" | "assistant";

// Parcel identity: pin/confidence are authoritative (backend-resolved only),
// lat/lon are derived map anchors, address is display-only.
export interface SelectedParcel {
  pin: string | null;
  confidence: "authoritative" | "approximate";
  lat: number;
  lon: number;
  address: string | null;
}

export type ParcelQuery =
  | { pin: string }
  | { address: string }
  | { lat: number; lon: number };

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
  /** When the server stored this message (epoch ms): set on a reopened or shared conversation, never on an
      answer from this session. Its presence is what puts "Answered <date>" under an answer. */
  createdAt?: number;
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
  /** null = prior-year count was 0 (percentage undefined; renders as "new"). */
  change_pct: number | null;
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
  /** Council amendments passed after this text's vintage that touch the section. */
  amended_since?: Amendment[];
}

/** One City Council amendment passed after the code text's vintage (backend `legislation.currency.public`). */
export interface Amendment {
  record: string;
  /** ISO day (America/Chicago). */
  passed_on: string;
  title: string;
  /** Reviewed one-liner; null until someone has read the ordinance. Never inferred from the title. */
  summary: string | null;
  sections: string[];
  url: string | null;
  relevance?: "title17" | "cited_other" | "other" | null;
  review_status: "reviewed" | "unreviewed" | null;
  /** applied: this page reflects it; none: reviewed, no change to what we show; pending: not read yet. */
  product_effect: "applied" | "none" | "pending" | null;
  codified?: boolean | null;
  /** True when it touches a section this Profile cites or its map effect reaches the address. */
  parcel_relevant?: boolean;
}

/** What the Profile (and chat) carry about how current the code text is (backend `ContextObject.code_currency`). */
export interface CodeCurrency {
  current_through: string;
  label: string | null;
  source?: string | null;
  checked_at: string | null;
  /** fresh (<72 h) | aging (3-14 d) | unknown (no count is shown, never "none"). */
  check_state: "fresh" | "aging" | "unknown";
  /** Null when check_state is unknown. */
  since: { title17: number; cited_other: number } | null;
  clerk_url: string;
  amendments: Amendment[];
}

export interface TrendItem {
  category: string;
  current_count: number;
  prior_count: number;
  /** null = prior-month count was 0 (percentage undefined; renders as "new"). */
  change_pct: number | null;
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
  /** The ordinance identifier (clerk number for a recent amendment). An
      application number (e.g. 23082T1) is kept apart in application_num. */
  ordinance_num: string | null;
  application_num?: string | null;
  /** ISO dates from the City's zoning layer: when the ordinance behind this district
      passed, and when this district's record was last edited. */
  ordinance_date?: string | null;
  map_updated?: string | null;
  clerk_url?: string | null;
  /** Ordinance passed within ~180 days — the map can lag a passed amendment by up to 90. */
  recently_rezoned?: boolean;
  zoning_map_url: string;
}

/** How current the indexed Municipal Code is (its "current through" date). */
export interface CodeVintage {
  current_through: string;
  label: string;
  source?: string;
}

export interface OverlayDistrict {
  layer_type: string;
  name: string | null;
  ordinance: string | null;
  description: string | null;
  /** What this overlay means for the parcel, pinned to the code (null when the code
      doesn't say), and where to read the source (code section or PD ordinance PDF). */
  detail?: string | null;
  link?: string | null;
}

/** Coach house / conversion-unit status for this parcel's district (backend adu_status). */
export interface AduStatus {
  status: "allowed_by_right" | "allowed_with_limits" | "not_allowed";
  zone: string | null;
  limits: string | null;
  note: string;
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
  /** null = unknown: FEMA's flood map didn't answer (`flood_unchecked`). Never render it as "not in". */
  in_special_flood_hazard: boolean | null;
  /** FEMA's flood map didn't answer, so `flood_zone` is null because it is UNKNOWN, not because the parcel is clear. */
  flood_unchecked?: boolean;
  brownfield_sites: Record<string, unknown>[];
  aro_housing: AROHousingSummary | null;
  /** Overlay layer types the City map couldn't answer for. Their in_* flags are
   *  false because they're UNKNOWN — never render them as "not in". */
  unchecked_overlays?: string[];
  /** Plain-language labels for those (also merged into partial_failures). */
  data_gaps?: string[];
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

/** EAV deduction (taxable value removed before rates), NOT dollars off the bill.
    Owner-occupancy exemptions drop at transfer — bill understates a buyer's bill. */
export interface TaxExemption {
  kind: string;
  eav_reduction: number;
}

/** Distress/opportunity flags. Tax-sale years are HISTORIC (datasets end
    ~2014) — render with the years, never as current distress. */
export interface ParcelFlags {
  tax_sale_years: number[];
  scavenger_sale_years: number[];
  city_owned: boolean;
  city_owned_status: string | null;
  city_owned_sales_status: string | null;
  city_owned_application_url: string | null;
  scofflaw: boolean;
  scofflaw_case: string | null;
  str_prohibited: boolean;
  /** CHRS 1996 survey rating ("orange" | "red") — triggers the 90-day demolition hold. */
  chrs_rating?: string | null;
  chrs_name?: string | null;
}

/** Chicago Energy Benchmarking (buildings >=50k sqft). A null rating with
    not_submitted=true is a compliance fact (owner didn't report), not a score. */
export interface EnergyBenchmark {
  chicago_energy_rating: number | null;
  energy_star_score: number | null;
  gross_floor_area: number | null;
  year_built: number | null;
  primary_property_type: string | null;
  site_eui: number | null;
  ghg_intensity: number | null;
  data_year: number | null;
  not_submitted: boolean;
}

export interface AppealRecord {
  year: number | null;
  stage: "assessor" | "board_of_review" | string;
  before_total: number | null;
  after_total: number | null;
  result: string | null;
  reduction_pct: number | null;
  appeal_type: string | null;
}

export interface AppealsSummary {
  records: AppealRecord[];
  nearby_window_years: number[];
  nearby_appeal_count: number;
  nearby_reduced_count: number;
  nearby_median_reduction_pct: number | null;
  /** True when the nearby query hit its row cap — the count is a floor ("500+"). */
  nearby_capped?: boolean;
}

export interface AssessorPermit {
  date_issued: string | null;
  status: string | null;
  amount: number | null;
  /** null = the source left it blank, which is NOT the same as false. */
  assessable: boolean | null;
  job_code: string | null;
  work_description: string | null;
}

export interface AssessorPermitSummary {
  permits: AssessorPermit[];
  count: number;
  truncated: boolean;
  window_years: number;
  total_declared_amount: number | null;
  assessable_pending: boolean;
  latest_date: string | null;
}

export interface PropertySummary {
  pin14: string | null;
  address: string | null;
  bldg_class: string | null;
  bldg_class_description: string | null;
  bldg_sqft: number | null;
  land_sqft: number | null;
  /** Provenance labels ("assessor" | "gis" | "geometry" | "condo_unit" |
      "commercial_valuation" | "footprint") — absent when the field is null. */
  land_sqft_source?: string | null;
  bldg_sqft_source?: string | null;
  /** Set when this parcel is one of several in a commercial "economic unit" whose
      building-area total is the WHOLE complex's, not this lot's (bldg_sqft stays null). */
  complex_bldg_sqft?: number | null;
  complex_member_pins?: string[] | null;
  year_built_source?: string | null;
  stories_source?: string | null;
  units_source?: string | null;
  stories: number | null;
  units: number | null;
  commercial_units: number | null;
  rooms: number | null;
  bedrooms: number | null;
  full_baths: number | null;
  half_baths: number | null;
  bldg_age: number | null;
  total_assessed_value: number | null;
  /** A token assessment (under $100, or a >99% drop from a prior real value): a common area or the remainder
      of a divided lot. Then total_assessed_value, implied_market_value, estimated_annual_tax and
      effective_tax_rate are null, and the County's number sits here, never shown as a figure (Item 46). */
  nominal_assessment?: boolean;
  nominal_assessed_value?: number | null;
  estimated_annual_tax: number | null;
  /** Class-aware tax interpretation, computed server-side (assessment_level.py):
      level is the ordinance assessment level for this class (0.10 residential,
      0.25 commercial); market = assessed ÷ level; rate = tax ÷ market as a
      fraction. NEVER recompute these client-side — the old hardcoded 10%
      showed 2.06% for a commercial parcel whose true rate was ~5.15%. */
  assessment_level?: number | null;
  implied_market_value?: number | null;
  effective_tax_rate?: number | null;
  /** ptaxsim bill year for estimated_annual_tax (lags the calendar 1–2 yrs). */
  tax_year?: number | null;
  tax_code: string | null;
  tax_breakdown: TaxLineItem[];
  tax_exemptions: TaxExemption[];
  appeals?: AppealsSummary | null;
  flags?: ParcelFlags | null;
  energy?: EnergyBenchmark | null;
  assessment_history: AssessmentRecord[];
  sales_history: SaleRecord[];
  parcel_geometry?: Record<string, unknown> | null;
  assessor_permits: AssessorPermitSummary | null;
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

/** Community-area figures from the City's ACS extract. The median income is
    interpolated from 5 brackets (no margin of error). Rent, home value, poverty and
    the other fields this dataset never held were removed 2026-10-20 (WS0 M1). */
export interface DemographicsSummary {
  community_area: number | null;
  community_area_name: string | null;
  population: number | null;
  median_household_income: number | null;
  /** The ACS 5-year window, e.g. "2019–2023". Absent on older stored contexts. */
  acs_period?: string | null;
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
  /** Absent on contexts stored before 2026-10-20. */
  unemployment_rate?: number | null;
  bachelors_or_higher_pct: number | null;
  foreign_born_pct: number | null;
  /** The ACS release's years, e.g. "2020–2024". */
  acs_period?: string | null;
  age_distribution: DistributionBucket[];
  income_distribution: DistributionBucket[];
  race_distribution: DistributionBucket[];
  education_distribution: DistributionBucket[];
  transportation_distribution: DistributionBucket[];
  county_median_income: number | null;
  city_median_income: number | null;
}

export interface WardInfo {
  ward: number;
  alderman: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
}

export interface DivvyAccess {
  nearest_station: string | null;
  distance_mi: number | null;
  docks: number | null;
  stations_within_radius: number;
  radius_mi: number;
}

/** Overall median gross rent of a community area, summed from Census tract bracket counts (backend `CommunityAreaRent`). */
export interface CommunityAreaRent {
  community_area: number;
  households: number;
  median?: number | null;
  moe?: number | null;
  cv?: number | null;
  top_coded?: boolean;
  moe_method: string;
  design_factor?: number | null;
  acs_period?: string | null;
  acs_release?: string | null;
  period_end?: string | null;
}

/** The Cook County Assessor's modeled apartment income for a community area: its OWN series, not an ACS rent and
    never by bedroom (backend `AssessorModelRent`). `median_per_unit_month` is potential gross income before vacancy. */
export interface AssessorModelRent {
  community_area: number;
  buildings: number;
  /** Buildings the median rests on (the sample the n rule reads). */
  priced: number;
  units: number;
  households?: number | null;
  /** Modeled units over ACS renter households with cash rent; above 1 the two are not comparable. */
  coverage?: number | null;
  median_per_unit_month?: number | null;
  year: string;
  cycle: string;
  as_of: string;
  dataset: string;
}

/** The Census's published median gross rent for one bedroom count: the parcel's tract, else its PUMA. */
export interface BedroomRent {
  bedrooms: "1_bedroom" | "2_bedrooms" | "3_bedrooms";
  scope: "tract" | "puma";
  geography?: string | null;
  geoid?: string | null;
  /** Null = the Census publishes no usable median here. */
  estimate?: number | null;
  moe?: number | null;
  cv?: number | null;
  /** Why the tract's own figure was not used. */
  tract_fallback?: "suppressed" | "low_confidence" | null;
}

/** The API omits null fields, so each is optional. Current official rent for the parcel's area (WS4 PR2). `unchecked` = parts that could not be fetched today. */
export interface RentEvidence {
  community_area?: CommunityAreaRent | null;
  assessor_model?: AssessorModelRent | null;
  bedrooms: BedroomRent[];
  acs_period?: string | null;
  acs_release?: string | null;
  tract_name?: string | null;
  puma_geoid?: string | null;
  puma_name?: string | null;
  unchecked: Array<"community_area_rent" | "tract_rent" | "puma_rent" | "assessor_model">;
}

export interface NeighborhoodSummary {
  demographics: DemographicsSummary | null;
  census_tract: CensusTractDemographics | null;
  rent?: RentEvidence | null;
  transit: TransitAccess | null;
  walkscore: WalkScoreSummary | null;
  ward?: WardInfo | null;
  traffic?: TrafficSummary | null;
  divvy: DivvyAccess | null;
}

/** Daily traffic on the nearest counted street (both directions summed,
    last-week average) — retail exposure context. */
export interface TrafficSummary {
  road: string | null;
  daily_vehicles: number | null;
  directions: number;
  from_street: string | null;
  to_street: string | null;
  as_of: string | null;
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
  zone_class: string | null;
  far: number | null;
  price_per_buildable_sqft: number | null;
  land_sqft_source: string | null;
  deed_type: string | null;
  sale_type: string | null;
  distance_mi: number | null;
  lat: number | null;
  lon: number | null;
}

export interface ComparablesSummary {
  median_sale_price: number | null;
  median_price_per_land_sqft: number | null;
  median_price_per_bldg_sqft: number | null;
  median_price_per_buildable_sqft: number | null;
  /** "land_only" = clean land basis; "mixed" = includes improved sales. */
  buildable_median_basis: string | null;
  buildable_median_n: number | null;
  price_range_min: number | null;
  price_range_max: number | null;
  sales_volume: number;
  sales: ComparableSale[];
}

// Pre-resolved parcel grounding shipped to /chat on a Scorecard handoff. Mirrors
// backend ScorecardContext. Built from the held ScorecardResponse (see
// lib/scorecardContext.ts); the backend reads it directly and skips the
// property/regulatory/incentives re-fetch when its pin matches the turn.
export interface ScorecardContext {
  pin: string | null;
  address: string | null;
  community_area_name: string | null;
  lat: number | null;
  lon: number | null;
  parcel_zoning?: ZoningSummary | null;
  zone_definition?: Record<string, unknown> | null;
  // property + comparables are PIN/identity-dependent — omitted on a pin-null
  // (unverified) parcel so the chat never grounds on a possible neighbor's data.
  property?: PropertySummary | null;
  regulatory?: RegulatorySummary | null;
  incentives?: IncentivesSummary | null;
  comparables?: ComparablesSummary | null;
  // Distilled ScorecardVerdict so the chat can speak to the verdict + carry caveats.
  verdict?: VerdictGrounding | null;
  // Address-scoped building-violation tri-state, so chat affirms the same
  // at-address fact the Scorecard shows. ADDRESS-scoped — never the area feed.
  address_violations?: AddressViolationsGrounding | null;
  // Nearest counted street segment (Tier-2 traffic chip) — lat/lon-scoped, not
  // parcel identity, so it ships in both tiers.
  traffic?: TrafficSummary | null;
}

// Parcel-scoped (address-keyed) building-violation tri-state shipped in grounding.
// status: present (records on file) / confirmed_zero (lookup ran, none on record) /
// unconfirmed (address didn't parse — NOT zero). Mirrors backend AddressViolations.
export interface AddressViolationsGrounding {
  status: "present" | "confirmed_zero" | "unconfirmed";
  summary: ViolationSummary | null; // set only when status === "present"
}

// Distilled verdict shipped in the grounding payload (UI-only nextStep/cardAnchor dropped).
export interface VerdictGrounding {
  category: string;
  headline: string;
  binding_constraint: string | null;
  reasons: { text: string; polarity: string }[];
  confidence: "high" | "caveated";
  caveats: string[];
  signals: {
    allowedFar: number | null;
    existingFar: number | null;
    capacityBand: string;
    incentiveStrength: string;
    frictionFlags: string[];
  };
}

// What transit-served status does and does not change for this parcel's
// district. Computed by the backend (backend/retrieval/zoning_definitions.py
// tod_benefits) so the page, chat and report never disagree: parking relief
// applies to every district, density/FAR/height bonuses only to dash-3 ones.
export interface TodBenefits {
  parking_relief: boolean | null; // null = Planned Development, ordinance governs
  parking_max_reduction_pct: number | null;
  density_bonus_eligible: boolean;
  entitlement_required: boolean;
  note: string;
}

// Max dwelling units the lot AREA allows (backend max_units_by_lot_area): shows its
// inputs and says it is one limit among several, never "the" buildable count.
export interface UnitYield {
  units: number;
  lot_sqft: number;
  min_lot_area_per_unit: number;
  arithmetic: string;
  basis: string;
  caveat: string;
  lot_area_note: string;
  /** Units by the base district rule alone (before the 606 rule). */
  base_units?: number;
  /** RS-3 only: whether the Predominance of the Block (606) rule applied, was not in play, or could not be checked. */
  rule_606?: "applied" | "not_in_district" | "unchecked" | null;
}

/** One "what this page does not cover" note for this parcel (backend coverage_notes). */
export interface CoverageNote {
  id: string;
  /** "parcel": found on THIS parcel and not assessed here; "general": true of every parcel. */
  applies: "parcel" | "general";
  /** English text (what chat restates); the UI translates by id + params. */
  text: string;
  params: Record<string, string | number | null>;
  link: string | null;
  section: string | null;
  /** True for law Council passed that the published code text lacks (WS1 M4b). */
  ahead_of_code?: boolean;
}

/** A rezoning ordinance whose legal description lists this address and that the City's map does not
    carry yet (backend `ContextObject.passed_not_on_map`, WS1 M5). "Listing", never "rezoned": it can
    name only part of a range, and what it changes to is not read. */
export interface PassedNotOnMap {
  record: string;
  /** ISO date Council passed it. */
  passed_on: string;
  url: string;
  /** The listed range that reaches this address, in the ordinance's words ("6701-6731 S Western Ave"). */
  segment: string | null;
  maps: string | null;
  matched_by: "pin" | "address";
  /** WS1 M6: the district the ordinance changes it to, AI-read and validated against the live map; absent when not read. */
  from_district?: string;
  to_district?: string;
  district_source?: "ai_read_ordinance";
  agreement?: { n: number; agree: number };
}

/** A Chicago Landmark designation ordinance that lists this parcel's address (or, for a district, a block it
    is on) and that the City's landmark map doesn't show this parcel for yet (backend/legislation/designations.py). */
export interface PassedLandmarkDesignation {
  record: string;
  /** ISO date Council passed it. */
  passed_on: string;
  url: string;
  /** What the title calls it ("Chicago Daily News Building"); "building" when the title names none. */
  name: string | null;
  kind: "building" | "district";
  /** The listed range that reaches this address, in the ordinance's words ("900-1199 W Bryn Mawr Ave"). */
  segment: string | null;
  /** False when the landmark layers did not answer for this parcel: the map's answer is unknown. */
  map_checked: boolean;
  matched_by: "pin" | "address";
}

export interface UpcomingZoningFiling {
  record_number: string;
  title: string;
  status: string;
  sub_status: string;
  introduced_at?: string | null;
  latest_action_at?: string | null;
  url: string;
  application_number?: string | null;
  segment?: string | null;
  match_kind: "subject_pin" | "subject_range" | "nearby";
  distance_mi?: number | null;
}

export interface UpcomingZoningProvenance {
  source_id: string;
  as_of?: string | null;
  method: string;
  confidence: "standard" | "low";
}

export interface PendingTextAffectedFact {
  fact_id: string;
  label: string;
  current_value?: string | number | boolean | null;
  section?: string | null;
  current_law?: string | null;
}

export interface PendingTextEffect {
  id: string;
  sections: string[];
  could_change: string;
  reach: "parcel" | "untested";
  reach_note?: string | null;
  affected: PendingTextAffectedFact[];
}

export interface PendingTextImpact {
  record_number: string;
  lifecycle_id: string;
  title: string;
  status: string;
  sub_status: string;
  introduced_at?: string | null;
  latest_action_at?: string | null;
  url: string;
  reviewed_on: string;
  reviewed_by: string;
  basis: "ordinance";
  summary?: string | null;
  effects: PendingTextEffect[];
}

export interface PendingTextUnreviewed {
  record_number: string;
  title: string;
  url: string;
  introduced_at?: string | null;
  reason: "unreviewed" | "outdated";
  waiting_days?: number | null;
}

export interface PendingTextReview {
  status: "complete" | "incomplete" | "unavailable";
  pending_count: number;
  reviewed_count: number;
  unreviewed: PendingTextUnreviewed[];
  oldest_unreviewed_days?: number | null;
  overdue: boolean;
  review_provenance?: UpcomingZoningProvenance | null;
}

export interface UpcomingZoningSummary {
  status: "ready" | "stale" | "unavailable";
  placement_status: "complete" | "partial";
  checked_at?: string | null;
  radius_mi: number;
  subject_filings: UpcomingZoningFiling[];
  nearby_filings: UpcomingZoningFiling[];
  placed_count: number;
  unplaced_count: number;
  placement_coverage?: number | null;
  record_provenance: UpcomingZoningProvenance;
  placement_provenance: UpcomingZoningProvenance;
  text_impacts?: PendingTextImpact[];
  text_review?: PendingTextReview | null;
}

export interface ContextObject {
  passed_landmark_designations?: PassedLandmarkDesignation[] | null;
  passed_not_on_map?: PassedNotOnMap[] | null;
  upcoming_zoning?: UpcomingZoningSummary | null;
  coverage_notes?: CoverageNote[] | null;
  adu?: AduStatus | null;
  code_vintage?: CodeVintage | null;
  code_currency?: CodeCurrency | null;
  tod_benefits?: TodBenefits | null;
  unit_yield?: UnitYield | null;
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
  /** Where each figure came from and how far to trust it, keyed by fact id (backend/provenance.py).
      Set once when the answer was assembled and stored with the message: a reopened answer keeps its dates. */
  provenance?: Record<string, Provenance> | null;
  /** Figures the data could not support (too few sales, too wide a margin). Their values are absent above. */
  withheld_figures?: WithheldFigure[] | null;
}

export interface WithheldFigure {
  fact_id: string;
  figure: string;
  reason: string;
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
  | { type: "done"; t_ms?: number; timings?: PhaseTimings; truncated?: boolean }
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

export type DataSource = "crime" | "311" | "permits" | "violations" | "business" | "vacant_buildings" | "food_inspections";

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
  created_at?: number | null;
}

/** What changed since an answer or a report was made (WS6 M9; backend `data_health/diff.py`). */
export type SinceThenChange =
  | { kind: "district"; old: string; new: string; record?: string | null; passed_on?: string | null; url?: string | null }
  | { kind: "overlay"; change: "added" | "removed"; layer: string; name?: string | null }
  | { kind: "standards"; field: string; old: string | number; new: string | number; zone_class?: string | null }
  | { kind: "amendment"; phase: "after_answer" | "before_answer"; record: string; title?: string | null; passed_on: string; url?: string | null; sections: string[] }
  | { kind: "map_amendment"; record: string; passed_on?: string | null; url?: string | null }
  | { kind: "designation"; record: string; passed_on?: string | null; url?: string | null; name?: string | null }
  | { kind: "text_refresh"; current_through: string; sections: string[] }
  | { kind: "correction"; id: string; date: string; summary: string };

export interface SinceThenResult {
  status: "changes" | "none" | "partial" | "unavailable" | "too_soon" | "skipped" | "no_parcel";
  answered_on?: string | null;
  reconstructed?: boolean;
  changes: SinceThenChange[];
  unchecked: string[];
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

export interface BehaviorReturnRate {
  total: number;
  returned: number;
  rate: number;
}

export interface EngagementMetrics {
  investigate_clicks: Record<string, number>;
  hero_address_submits: Record<string, number>;
  hero_librarian_clicks: Record<string, number>;
  scorecard_bridge_clicks: Record<string, number>;
  report_cta_clicks: number;
  sample_report_clicks: number;
  report_purchases_count: number;
  chat_messages: number;
  unique_visitors: number;
  returning_visitors: number;
  avg_days_between_visits: number | null;
  scorecard_to_chat_rate: number | null;
  return_rate_by_behavior: Record<string, BehaviorReturnRate>;
  page_views: Record<string, number>;
  funnel: FunnelStep[];
  channels: Record<string, number>;
}

export interface FunnelStep {
  step: string;
  visitors: number;
}
