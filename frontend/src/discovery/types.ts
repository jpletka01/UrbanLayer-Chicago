// TS mirrors of the Property Discovery wire contracts (backend docs 02/03/06/07).
// These are the frozen cross-team types; the frontend never evaluates or filters — it
// compiles inputs into a SearchRequest and renders from the canonical response.cqs (INV-4).

export type FilterId = string;
export type RegionRef = string;

export type EnumPredicate = { kind: "enum"; values: string[] };
export type RangePredicate = { kind: "range"; min?: number; max?: number };
export type FlagPredicate = { kind: "flag"; value: boolean };
export type RegionPredicate = { kind: "region"; regions: RegionRef[] };
export type Predicate = EnumPredicate | RangePredicate | FlagPredicate | RegionPredicate;

export type Source = "user" | "text" | "topic" | "default";

export interface FilterAssignment {
  predicate: Predicate;
  source: Source;
}

export interface SortSpec {
  key: string;
  dir: "asc" | "desc";
}

export interface SpatialScope {
  mode: "all" | "viewport" | "region";
  bbox?: [number, number, number, number];
  regions?: RegionRef[];
}

export interface QueryMeta {
  topicId?: string | null;
  rawText?: string | null;
  textResidual?: string[];
}

export interface CQS {
  filters: Record<FilterId, FilterAssignment>;
  sort: SortSpec;
  scope: SpatialScope;
  meta: QueryMeta;
}

// --- Registry (03) ---

export type FilterCategory =
  | "location"
  | "property_use"
  | "zoning_dev"
  | "incentives"
  | "financial"
  | "condition_risk";

export type PredicateKind = "enum" | "range" | "flag" | "region";

// Range control metadata (PR2) — presentation only; the evaluator never reads it.
export type RangeDisplay =
  | "number"
  | "usd"
  | "percent"
  | "far"
  | "mi"
  | "score"
  | "count"
  | "year";
export type BoundMode = "min" | "max" | "both";

export interface RangePreset {
  label: string;
  min?: number | null;
  max?: number | null;
}

export interface RangeMeta {
  domain: [number, number];
  step: number;
  boundMode: BoundMode;
  display: RangeDisplay;
  presets?: RangePreset[] | null;
}

export interface FilterDef {
  id: string;
  category: FilterCategory;
  kind: PredicateKind;
  field: string;
  unknownPolicy: "exclude" | "include";
  enumValues?: string[] | null;
  unit?: string | null;
  contradicts?: string[];
  // PR2 display + control metadata (consumed by the panel in PR4)
  range?: RangeMeta | null;
  requires?: string[];
  label?: string | null;
  help?: string | null;
  enumLabels?: Record<string, string> | null;
}

export interface TopicDef {
  id: string;
  label?: string | null;
  description?: string | null;
  presets: Record<FilterId, Predicate>;
  defaultSort?: SortSpec | null;
}

export interface SortKeyDef {
  key: string;
  field: string;
}

// Coverage (PR4) — what geography the index covers. Presentation only; sourced from the
// registry response and rendered as a standalone banner OUTSIDE the response.cqs chips.
export interface Coverage {
  mode: "none" | "partial" | "all";
  liveAreas: number[];
  asOf?: string | null;
}

export interface Registry {
  version: string;
  filters: FilterDef[];
  topics: TopicDef[];
  sortKeys: SortKeyDef[];
  defaultSort: SortSpec;
  broadMinFilters: number;
  // PR4 index-derived: drive the coverage banner + the panel/recipe "coming" affordances.
  coverage: Coverage;
  populatedFields: string[];
}

// --- Diagnostics (06) ---

export interface Conflict {
  filters: string[];
}

export interface DroppedInvalid {
  filterId: string;
  reason: string;
}

export interface MostRestrictive {
  filterId: string;
  countWithoutIt: number;
}

export interface Diagnostics {
  resultCount: number;
  broad: boolean;
  appliedFilters: number;
  conflicts: Conflict[];
  droppedInvalid: DroppedInvalid[];
  excludedUnknown: Record<string, number>;
  mostRestrictive: MostRestrictive[];
}

// --- Wire (07) ---

export interface SearchRequest {
  userFilters: Record<FilterId, Predicate>;
  topicId?: string;
  text?: string;
  sort?: SortSpec;
  scope?: SpatialScope;
  registryVersion: string;
  limit?: number; // page-window size (default server-side); infinite scroll fetches more
  offset?: number; // window start into the ordered result
}

// One hydrated result parcel. `pin` is the frozen identity; the rest is hydrated from the
// dataVersion snapshot. Derived fields (value_percentile/upside_score/is_teardown_candidate)
// stay null until the index computes them (PR-INDEX).
export interface ResultRow {
  pin: string;
  lat: number | null;
  lon: number | null;
  address: string | null;
  community_area: number | null;
  land_use: string | null;
  class: string | null;
  lot_sqft: number | null;
  bldg_sqft: number | null;
  year_built: number | null;
  units: number | null;
  assessed_value: number | null;
  price_per_sf: number | null;
  last_sale_price: number | null;
  last_sale_date: string | null;
  improvement_ratio: number | null;
  value_percentile: number | null;
  upside_score: number | null;
  is_teardown_candidate: boolean;
  sortValue: number | string | null; // value of the active sort key, for row display
}

export interface SearchResult {
  rows: ResultRow[];
  total: number;
  nextOffset: number | null;
}

// Map coord set (PR6) — the FULL ordered match set (capped), decoupled from the list window.
export interface PinPoint {
  pin: string;
  lat: number | null;
  lon: number | null;
  upside: number | null; // upside_score; null → distinct "no data" map color
}

export interface PinsResponse {
  dataVersion: string;
  total: number;
  points: PinPoint[];
  truncated: boolean; // total > cap → some matches omitted from the map
}

export interface SearchResponse {
  dataVersion: string;
  cqs: CQS;
  result: SearchResult;
  diagnostics: Diagnostics;
}

// --- Frontend-only: filter-panel control state ---
// One predicate-shaped value per active control; a cleared control omits its key
// (absent = no constraint). This is the single source of `userFilters` (cleared-field rule).
export type PanelState = Record<FilterId, Predicate>;
