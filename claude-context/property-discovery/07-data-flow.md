# 07 — Data Flow (input → CQS → results)

## Wire contracts

### Request — `POST /discovery/search`
The frontend sends a **pre-CQS envelope** (raw inputs), not a CQS. The backend compiles + merges +
evaluates and returns the canonical CQS.

```ts
interface SearchRequest {
  userFilters: Record<FilterId, Predicate>;  // current chip state = topic-expand + user edits (FE-applied)
  topicId?:    string;                        // telemetry only; backend does NOT re-expand (04)
  text?:       string;                        // parsed by backend text compiler
  sort?:       SortSpec;                       // user override; else registry default
  scope?:      SpatialScope;                   // default { mode: "all" }
  registryVersion: string;                     // FE's registry version, for staleness check
}
```

### Response
```ts
interface SearchResponse {
  dataVersion:  string;
  cqs:          CQS;          // canonical, post-merge — FE renders chips/summary from THIS (INV-4)
  result:       { pins: string[]; total: number };
  diagnostics:  Diagnostics;
}
```

`GET /discovery/registry` → `Registry` (03). Cached by the FE; `registryVersion` mismatch on a search
triggers a refetch.

## End-to-end sequence

```
1. FE captures inputs:
     - UI compiler (04.1) turns panel state into userFilters (source:user)
     - Topic compiler (04.2) pre-filled those values earlier; user edits already merged in
     - free text stays raw in `text`
2. FE → POST /discovery/search { userFilters, topicId?, text?, sort?, scope?, registryVersion }
3. BE text compiler (04.3) parses `text` → text fragment (source:text) + residual
4. BE merge (04.4): default ⊂ text ⊂ user  →  canonical CQS  (+ droppedInvalid/validation diagnostics)
5. BE evaluate (05): filter → sort → OrderedResult, stamped with dataVersion
6. BE diagnostics (06): broad, conflicts, excludedUnknown; mostRestrictive iff total==0
7. BE → SearchResponse { dataVersion, cqs, result, diagnostics }
8. FE renders:
     - map + list from result.pins (FE may cap RENDER count; result.total is the true count)
     - chips + plain-English summary from response.cqs  (INV-4)
     - empty/broad/conflict affordances from diagnostics → user one-tap re-issue = back to step 2
9. User clicks a pin → existing Scorecard handoff (out of scope here)
```

## Determinism across the wire
The canonical CQS in the response is the exact object evaluated. Re-sending the same envelope against
the same `dataVersion` yields the same canonical CQS and the same `result.pins` (INV-2). The backend MAY
cache on `(canonicalCQS, dataVersion)` since canonical CQS serializes deterministically (02 canonical form).
