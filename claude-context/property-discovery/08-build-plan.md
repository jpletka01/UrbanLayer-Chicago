# 08 — Build Plan

## Module breakdown

### Backend (Python / FastAPI)
| Module | Responsibility | Reads |
|---|---|---|
| `discovery/registry.py` | Load + validate the static registry artifact; expose typed accessors | registry JSON |
| `discovery/cqs.py` | CQS + Predicate dataclasses, canonical serialization, equality | — |
| `discovery/evaluator.py` | `evaluate(cqs, dataVersion)` — filter + sort. **The single path (INV-1).** | parcel collection, registry |
| `discovery/predicates.py` | `satisfies(predicate, parcel, unknownPolicy)` per kind; `withinScope` | registry |
| `discovery/diagnostics.py` | broad, conflicts, droppedInvalid, excludedUnknown, mostRestrictive | evaluator (black-box), registry |
| `discovery/compile_text.py` | deterministic text → fragment + residual | registry |
| `discovery/compile_merge.py` | precedence merge + compile-time validation → canonical CQS | registry |
| `discovery/api.py` | `/api/discovery/registry`, `/api/discovery/search` | all above |

### Frontend (React / TS)
| Module | Responsibility |
|---|---|
| `discovery/registryClient.ts` | fetch/cache registry; staleness check |
| `discovery/uiCompiler.ts` | panel control state → `userFilters` (source:user) |
| `discovery/topicCompiler.ts` | topicId → preset values (static registry expand) |
| `discovery/searchClient.ts` | build `SearchRequest`, call `/api/discovery/search` |
| `discovery/chips.tsx` + `summary.ts` | render chips + plain-English summary **from response.cqs** |
| `discovery/results/` | map + list rendering, render-cap, empty/broad/conflict affordances |

## Execution order (strict)

1. **Registry artifact + `registry.py` + schema validation.** Everything references it; predicate kinds
   and `unknownPolicy` originate here. Author the full filter set (03) as data.
2. **`cqs.py` + `predicates.py`.** The contract types and per-kind `satisfies`/`withinScope`. Unit-test
   each predicate kind incl. missing-value `unknownPolicy` and inverted-range.
3. **`evaluator.py`.** Filter + sort over fixtures. This is the invariant-critical core — build and
   freeze it before any plumbing. Test determinism (repeat calls byte-identical; total order; PIN
   tie-break; missing-sort-field sorts last).
4. **`diagnostics.py`.** Depends on a working evaluator (D5 calls it black-box). Test mostRestrictive,
   excludedUnknown counts.
5. **`compile_text.py`.** Deterministic parser; table-driven tests (same string → same fragment).
6. **`compile_merge.py`.** Precedence + validation; test cleared-field rule, density-needs-zoning drop.
7. **`api.py`.** Wire compile → merge → evaluate → diagnostics; return canonical CQS. Contract tests on
   `SearchRequest`/`SearchResponse`.
8. **FE `registryClient` + `uiCompiler` + `topicCompiler`.** Pure, unit-testable.
9. **FE `searchClient` + renderers.** Render chips/summary from `response.cqs` (INV-4 test).
10. **Integration + determinism suite.** Same envelope → same canonical CQS → same pins. Mode-equivalence
    test: topic vs manual-filters vs text that compile to equal CQS return identical pins (the headline
    acceptance test).

## Dependency graph

```
registry ──┬─► cqs/predicates ──► evaluator ──► diagnostics ─┐
           │                          ▲                       │
           ├─► compile_text ──────────┤                       │
           └─► compile_merge ─────────┘                       │
                                       └──────► api ◄──────────┘
                                                  ▲
   FE: registryClient ─► uiCompiler ─┐            │
                          topicCompiler ─► searchClient ─► renderers(chips/summary/results)
```

Critical path: **registry → predicates → evaluator**. Nothing user-visible is correct until the
evaluator is frozen; build it first and gate it behind the determinism suite before plumbing.

## Definition of done (per the invariants)
- [ ] Determinism suite green (repeat calls byte-identical per dataVersion).
- [ ] Mode-equivalence test green (topic ≡ text ≡ UI for equal CQS).
- [ ] No result-producing code outside `evaluator.py` (grep-enforced in CI).
- [ ] FE chips/summary sourced from `response.cqs` (component test).
- [ ] `unknownPolicy` covered for every filter; `excludedUnknown` populated.
