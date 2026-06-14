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

export interface FilterDef {
  id: string;
  category: FilterCategory;
  kind: PredicateKind;
  field: string;
  unknownPolicy: "exclude" | "include";
  enumValues?: string[] | null;
  unit?: string | null;
  contradicts?: string[];
}

export interface TopicDef {
  id: string;
  presets: Record<FilterId, Predicate>;
  defaultSort?: SortSpec | null;
}

export interface SortKeyDef {
  key: string;
  field: string;
}

export interface Registry {
  version: string;
  filters: FilterDef[];
  topics: TopicDef[];
  sortKeys: SortKeyDef[];
  defaultSort: SortSpec;
  broadMinFilters: number;
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
}

export interface SearchResult {
  pins: string[];
  total: number;
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
