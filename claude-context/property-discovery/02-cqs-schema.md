# 02 — Canonical Query State (CQS)

The CQS is the single, total, serializable representation of a search request. It is the contract that
crosses the FE/BE boundary (echoed back canonical) and the only input the evaluator reads.

## Schema

```ts
type FilterId  = string;   // must exist in the registry (03)
type RegionRef = string;   // neighborhood id, ward id, or a serialized polygon/radius handle

interface CQS {
  filters: Record<FilterId, FilterAssignment>;  // absent key = filter not applied
  sort:    SortSpec;                            // ALWAYS present (default in registry)
  scope:   SpatialScope;                        // ALWAYS present; default { mode: "all" }
  meta:    QueryMeta;                           // advisory only — evaluator MUST NOT read
}

interface FilterAssignment {
  predicate: Predicate;
  source:    "user" | "text" | "topic" | "default";  // provenance; merge-only, evaluator ignores
}

type Predicate =
  | { kind: "enum";   values: string[] }              // non-empty; OR within
  | { kind: "range";  min?: number; max?: number }    // at least one bound; inclusive
  | { kind: "flag";   value: boolean }                // true = must have; false = must not have
  | { kind: "region"; regions: RegionRef[] };         // non-empty; OR within

interface SortSpec   { key: string; dir: "asc" | "desc"; }   // key ∈ registry sortable set
interface SpatialScope {
  mode: "all" | "viewport" | "region";
  bbox?:    [number, number, number, number];   // when mode = "viewport"
  regions?: RegionRef[];                         // when mode = "region"
}
interface QueryMeta  { topicId?: string; rawText?: string; textResidual?: string[]; }
```

## Rules

- **R1 — Absent ≠ empty.** A missing `filters[id]` means "no constraint." A predicate with an empty
  `values`/`regions` array is INVALID; the compiler MUST drop the key, never emit an empty set
  (an empty enum must not be allowed to mean "match nothing").
- **R2 — Predicate kind is fixed by the registry.** A filter's `kind` is defined once in the registry
  (03) and MUST NOT vary by input mode.
- **R3 — `meta` is inert.** `topicId`, `rawText`, `textResidual` are for telemetry/UX. Removing them
  MUST NOT change results (INV-2). The evaluator MUST NOT read `meta`.
- **R4 — `source` is merge-only.** Provenance is consumed at compile-time precedence (04) and is
  invisible to `evaluate()`.
- **R5 — `sort` and `scope` are always present.** Defaults come from the registry. `scope.mode="all"`
  contributes no constraint.
- **R6 — Inverted range is honest.** `min > max` is a valid, **unsatisfiable** predicate; it is
  evaluated as matching zero parcels (not auto-corrected). Surfaced via diagnostics (06).

## Canonical form
Two CQS values are **equal** iff their `filters` (by predicate value), `sort`, and `scope` are equal.
`meta` and every `source` tag are excluded from equality. INV-2 determinism is defined over this
equality. Backend SHALL serialize CQS with sorted object keys so equal CQS serialize identically
(enables response caching keyed on canonical CQS + dataVersion).
