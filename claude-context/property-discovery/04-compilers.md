# 04 — Compilers (UI · Topic · Text) + Merge

Three compilers each produce a **CQS fragment** (a partial `filters` map + optional `sort`/`scope`,
every assignment tagged with its `source`). A single deterministic **merge** combines them into one CQS.
Compilers have no side effects and never touch results (INV-5).

## Compiler outputs (all the same shape)

```ts
interface CqsFragment {
  filters: Record<FilterId, FilterAssignment>;  // each tagged source
  sort?:   SortSpec;                            // topic may set; user may override
  scope?:  SpatialScope;
  meta?:   Partial<QueryMeta>;
}
```

## 4.1 UI compiler  (frontend)
Reads the filter-panel control state and emits one assignment per active control, `source: "user"`.
- Cleared control → key omitted (absent = no constraint).
- A multi-select control → `enum`/`region` predicate; a min/max control → `range`; a toggle → `flag`.
- Pure function of panel state. No network.

## 4.2 Topic compiler  (frontend, static registry lookup)
A topic is a **named static patch** in the registry (`TopicDef`):

```ts
interface TopicDef {
  id: string;
  presets: Record<FilterId, Predicate>;   // values written with source:"topic"
  defaultSort?: SortSpec;
}
```
- Emits each preset as `source: "topic"`, plus `meta.topicId`.
- MUST be fully reducible: every value it writes is individually removable; clearing them all returns
  to a blank CQS (INV-5). `meta.topicId` MAY remain (inert, INV-2).
- A topic MUST NOT write anything not representable as a registry filter assignment.

## 4.3 Text compiler  (backend, deterministic parser)
A **rule/grammar-based** parser — NOT the LLM (the LLM is non-deterministic and would break INV-2).
`text → (assignments, residual)`:
- Emits zero or more assignments, `source: "text"`, each conforming to the registry predicate kind.
- Tokens it cannot map go to `meta.textResidual`. Residual MUST NOT constrain results (INV-5).
- Total and deterministic: same string → same fragment, always.
- Lives in one place (backend) so all clients parse identically.

## 4.4 Merge (backend)
Combines fragments into the canonical CQS. **Precedence, strict highest-wins:**

```
user  >  text  >  topic  >  default
```

Algorithm (deterministic):
1. Start with `filters = {}`, `sort = registry.defaultSort`, `scope = { mode:"all" }`.
2. Apply fragments in ascending precedence (default→topic→text→user); for each `filterId`, a
   higher-precedence assignment overwrites a lower one. Equal precedence cannot occur for the same id
   within one request (UI is the only `user` source; text the only `text` source; topic the only
   `topic` source).
3. `sort`: user override (if any) beats topic `defaultSort` beats `registry.defaultSort`.
4. Drop any INVALID predicate (empty enum/region) per 02-R1; record in diagnostics.
5. Run compile-time validations (e.g., `density_band` requires `zoning_group`); on violation, drop the
   dependent predicate and record a diagnostic. (Validation drops are deterministic and visible.)
6. Result is the canonical CQS. Echo it back to the frontend (INV-4).

### Cleared-field rule (prevents a topic re-filling what the user removed)
The frontend sends the **current chip state** as the `user` fragment — i.e. topic expansion + user edits
already applied client-side. The backend does NOT re-expand the topic during merge; `topicId` rides in
`meta` for telemetry only. Therefore a field the user cleared simply isn't in the `user` fragment and
cannot reappear. The text fragment only fills genuinely-absent fields (lower precedence than user).

> Consequence: topic expansion is a **frontend** compile step (static lookup), text parsing is a
> **backend** compile step, and the **merge + evaluate** are backend. All three compilers share the one
> registry artifact (03), so there is no semantic drift. This split is permitted by INV-5 (compilers may
> live anywhere); only the evaluator must be singular (INV-1).
