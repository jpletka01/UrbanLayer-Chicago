# Property Discovery — Implementation Handoff

This folder is the **engineering handoff spec** for the Property Discovery (filter/search) system.
Design is locked. Docs 00–09 are normative; code from them directly.

> **Status (2026-06-13): BUILT end-to-end, not yet deployed** — backend (steps 1–10) + offline
> prospecting index + frontend, on branch `feat/discovery-evaluator-core` (not pushed). See
> **`10-implementation-status.md`** for what was built, the in-build decisions/reasoning, and what
> remains. Read that doc first when resuming this work.

**Reading order:**

| Doc | Purpose |
|---|---|
| `00-overview.md` | What the system does, the pipeline in one page |
| `01-invariants.md` | The non-negotiable invariants + enforcement checklist. **Read first.** |
| `02-cqs-schema.md` | Canonical Query State — the one contract everything compiles into |
| `03-filter-registry.md` | Filter registry, predicate kinds, `unknownPolicy` |
| `04-compilers.md` | UI, topic, and text → CQS compilation + precedence merge |
| `05-evaluator.md` | The single evaluator: filter + sort + determinism |
| `06-diagnostics.md` | Conflict detection + diagnostics (advisory, non-mutating) |
| `07-data-flow.md` | Input → CQS → evaluation → results, with the wire contracts |
| `08-build-plan.md` | Module breakdown, execution order, dependency graph |
| `09-module-contracts.md` | Exact data contracts between every module + FE/BE boundary |
| `10-implementation-status.md` | **What was actually built + in-build decisions + what remains** (read first when resuming) |

**Conformance language:** MUST / MUST NOT / SHALL = mandatory. MAY = optional. Unmarked = mandatory.

**Scope note:** This build implements **filter + single-key sort** only. There is no scoring/relevance
layer (see `01-invariants.md`, INV-3). The two correctness rules folded in from the spec-lock —
`unknownPolicy` for missing values and boolean `flag` polarity — are definitional, not features:
the determinism invariant is undefined without them.
