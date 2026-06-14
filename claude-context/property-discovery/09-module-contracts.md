# 09 — Module Contracts & FE/BE Boundary

## The boundary (locked)

| Concern | Owner | Rationale |
|---|---|---|
| Registry artifact (filters, topics, sort keys) | **Backend authors & serves**; FE consumes | one source ⇒ no predicate-kind / topic drift (03) |
| UI compile (panel → userFilters) | **Frontend** | it's the FE's own control state; trivial, no network |
| Topic expand (topicId → presets) | **Frontend** (static registry lookup) | avoids re-fill-after-clear bug; keeps backend re-expansion out (04.4) |
| Text parse (text → fragment) | **Backend** | must be deterministic & identical for all clients (INV-2) |
| Merge (precedence) | **Backend** | one place resolves provenance → canonical CQS |
| Evaluate (filter + sort) | **Backend** | the single evaluator (INV-1) |
| Diagnostics | **Backend** | derived from the evaluator |
| Chips / summary / map / list | **Frontend**, rendered from `response.cqs` | display == evaluated (INV-4) |
| Empty/broad/conflict resolution | **Frontend** re-issues a modified CQS | evaluator never auto-relaxes (06) |

> The frontend never evaluates and never filters. The backend never renders. The CQS is the only object
> that crosses with semantic authority; the request envelope is raw pre-CQS input.

## Inter-module contracts (backend, in-process)

```
registry.load() -> Registry                       # validated at startup; raises on bad artifact
predicates.satisfies(pred, parcel, unknownPolicy) -> bool
predicates.within_scope(parcel, scope) -> bool
evaluator.evaluate(cqs: CQS, data_version: str) -> OrderedResult   # pure; reads parcels + registry
diagnostics.build(cqs, data_version, evaluator) -> Diagnostics     # evaluator passed in (black-box)
compile_text.parse(text: str) -> CqsFragment                       # + residual in fragment.meta
compile_merge.merge(user_frag, text_frag, sort?, scope?) -> (CQS, list[Dropped])
```

### Contract rules
- `evaluate` MUST NOT import `compile_*`, `api`, or `diagnostics` (acyclic; evaluator is a leaf core).
- `diagnostics.build` receives `evaluate` as a dependency and calls it as a black box for `mostRestrictive`
  — it MUST NOT reimplement filtering.
- `compile_merge` is the ONLY writer of canonical CQS. `api` calls `parse → merge → evaluate → build` in
  that fixed order and assembles `SearchResponse`.
- `registry` is read-only after startup. A registry change ships as a new artifact version + redeploy;
  no evaluator code change (03).

## Wire contracts (authoritative types)
See `07-data-flow.md` for `SearchRequest` / `SearchResponse` and `02-cqs-schema.md` for `CQS`.
These three are the frozen cross-team contracts. Any change to them is a versioned, reviewed event.

## Test ownership
- **Backend:** predicate unit tests, evaluator determinism + total-order, merge precedence + cleared-field,
  text-parser table tests, diagnostics counts, API contract tests, mode-equivalence.
- **Frontend:** uiCompiler/topicCompiler purity, registry staleness handling, "chips render from
  response.cqs" component test, one-tap re-issue builds a valid modified envelope.
- **Shared acceptance:** identical inputs across topic/text/UI that compile to equal CQS return identical
  `pins` (the headline invariant, owned jointly).
