# 00 — System Overview

## What it does
Property Discovery turns a user's intent — expressed as filter-panel selections, a topic preset, a
free-text phrase, or any combination — into a deterministic set of matching Chicago parcels, rendered
on a map + list. Selecting a parcel hands off to the existing Scorecard.

## The pipeline (one page)

```
        ┌─────────── inputs (raw, pre-CQS) ───────────┐
  UI panel selections    topic id    free-text    sort/scope
        └───────────────────┬─────────────────────────┘
                            ▼
                     COMPILERS  (UI, topic, text)  →  precedence merge
                            ▼
                  ┌──────────────────┐
                  │ Canonical Query  │   ← the ONLY thing the evaluator reads
                  │   State (CQS)    │
                  └────────┬─────────┘
                            ▼
                    SINGLE EVALUATOR
                  evaluate(CQS, dataVersion):
                     1. filter  → candidate set (hard predicates, AND/OR)
                     2. sort    → total order (single key + dir, PIN tie-break)
                            ▼
              ┌───────────────────────────────┐
              │ results (ordered parcel refs) │ + diagnostics (advisory)
              └───────────────────────────────┘
```

## The three things that are always true
1. **Inputs are compilers.** Topic, text, and UI never produce results directly — they only write CQS.
2. **One evaluator.** Exactly one function turns CQS into results. No input mode has a private path.
3. **CQS is canonical.** What the user sees (chips, summary) is rendered from the CQS that was evaluated.

## What this build is NOT
- Not a ranking/recommendation system. Ordering is one declared sort key (`01-invariants.md` INV-3).
- Not a new data layer. All filterable attributes are assumed already available to the backend.
- Not a backend redesign. The evaluator is a pure function over an existing parcel collection.

See `01-invariants.md` before writing any code.
