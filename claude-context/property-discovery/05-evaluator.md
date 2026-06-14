# 05 — Evaluator (the single path)

`evaluate(cqs, dataVersion) → OrderedResult` is the **only** function that produces results (INV-1).
It is pure: no clock, no RNG, no I/O beyond reading the parcel collection bound to `dataVersion`.

## Signature

```ts
interface OrderedResult {
  dataVersion: string;
  pins: string[];        // ordered, total order, no duplicates
  total: number;         // pins.length (no semantic cap; render caps live in FE)
}

function evaluate(cqs: CQS, dataVersion: string): OrderedResult;
```

## Stage 1 — Filter (recall boundary)

A parcel `p` is in the candidate set `S` iff it satisfies the conjunction of all applied predicates
and the scope:

```
p ∈ S  ⟺  withinScope(p, cqs.scope)
          ∧  ∀ (id, a) ∈ cqs.filters : satisfies(a.predicate, p, registry[id].unknownPolicy)
```

- **AND across filters**, **OR within** a multi-value `enum`/`region` (02, 03).
- `satisfies` applies `unknownPolicy` when `p.field` is missing (03). No other missing-value branching.
- `scope.mode="all"` adds no constraint. When both a `region` Location filter and a `viewport`/`region`
  scope are present, **both** apply (AND) — scope never overrides a Location filter.
- Contradictory predicates are evaluated honestly; an unsatisfiable conjunction yields `S = ∅`. The
  evaluator MUST NOT drop or auto-edit a predicate to avoid emptiness (06 handles surfacing).

## Stage 2 — Sort (ordering only)

Order `S` by `cqs.sort.key` then `cqs.sort.dir`, with a **final ascending-PIN tie-break** so the order
is a **total order with no ties**:

```
order(a, b) = compareByKey(a, b, sort.key, sort.dir)  ||  comparePinAsc(a, b)
```

- `sort.key` ∈ `registry.sortKeys`. Default from `registry.defaultSort`.
- Parcels whose sort field is missing sort **last** within their group (deterministic), then PIN-ordered.
- Ordering MUST NOT depend on input mode, provenance, `meta`, or which filters are active (INV-3).
- There is no score. This is the entire ordering logic.

## Determinism contract (INV-2)
- `evaluate` is a pure function of `(canonical CQS, dataVersion)`.
- Equal canonical CQS (02 equality) + equal `dataVersion` ⇒ byte-identical `pins`.
- `dataVersion` identifies the parcel snapshot; it is returned in every response. The determinism claim
  is **per dataVersion** only.

## Backend responsibility note
How parcels are stored/iterated and how spatial `region` membership is resolved are backend
implementation details **behind** `satisfies`/`withinScope`. They MUST be pure w.r.t. `dataVersion`.
This doc does not prescribe storage (out of scope) — only that the function is pure and total.
