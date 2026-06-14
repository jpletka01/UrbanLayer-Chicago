# 06 — Conflicts & Diagnostics (advisory, non-mutating)

Diagnostics explain a result; they NEVER change it. Computing diagnostics MUST NOT alter `pins`
(INV-2/INV-6). All diagnostic numbers are deterministic functions of `(CQS, dataVersion)`.

## Diagnostics object

```ts
interface Diagnostics {
  resultCount:    number;                       // == OrderedResult.total
  broad:          boolean;                       // resultCount-irrelevant; see below
  appliedFilters: number;                        // count of keys in cqs.filters
  conflicts:      Conflict[];                     // static contradictions detected
  droppedInvalid: { filterId: string; reason: string }[];  // empty enum/region, failed validation
  excludedUnknown:Record<string, number>;        // filterId → parcels dropped solely for missing value
  mostRestrictive:{ filterId: string; countWithoutIt: number }[];  // only when resultCount === 0
}
```

## Rules

- **D1 — broad flag.** `broad = appliedFilters < registry.broadMinFilters`. Advisory only; it MUST NOT
  add/remove/modify any constraint and MUST NOT cap or sample results. (Render caps are FE, not here.)

- **D2 — conflicts.** Using `registry.filters[].contradicts` (static table), report any pair of applied
  filters that are statically contradictory (e.g. `vacancy=true` flag vs a `building_size` range with
  `min>0`). Conflicts are **reported, not resolved** — the evaluator already returns the honest (often
  empty) set. The frontend offers the user a one-tap fix by re-issuing a modified CQS (07); the
  evaluator never auto-relaxes.

- **D3 — droppedInvalid.** Records predicates the compiler dropped (empty enum/region per 02-R1, or a
  failed compile-time validation per 04 step 5). Lets the UI explain why a typed/selected constraint
  didn't take effect.

- **D4 — excludedUnknown.** For each applied filter with `unknownPolicy="exclude"`, the count of parcels
  excluded **solely** because the attribute was missing (they passed every other predicate). Surfaces the
  silent-data-gap effect that `unknownPolicy` makes explicit (03). Deterministic; advisory.

- **D5 — mostRestrictive (zero-result diagnosis).** Computed **only** when `resultCount === 0`. For each
  applied filter `f`, compute `|evaluate(CQS \ f, dataVersion).pins|`; report the filters whose removal
  most increases the count, descending, ties broken by `filterId` ascending. This reuses the evaluator
  as a black box (no special path, INV-1). It informs the FE's one-tap relaxation; it does NOT mutate the
  result.

## Resolution lives in re-issue, not in the evaluator
When results are empty or over-broad, **the input layer constructs and re-evaluates a modified CQS**
(drop/loosen a filter). The evaluator never auto-relaxes. This keeps INV-1/INV-2/INV-6 intact: every
result the user ever sees is a plain `evaluate()` of some CQS.
