# 01 — Invariants (non-negotiable)

These are enforced in code and in review. A change that violates one is rejected regardless of benefit.

## INV-1 — Single evaluator
There SHALL be exactly one function that maps CQS → results: `evaluate(cqs, dataVersion)`. Topic, text,
and UI inputs MUST NOT contain any result-producing logic. No "fast path," "topic search," or "text
search" engine may exist. *Why:* mode equivalence and determinism are only provable if there is one path.

## INV-2 — Determinism per dataVersion
For a fixed `dataVersion`, `evaluate(cqs, dataVersion)` SHALL be a pure function returning a
byte-identical ordered result for equal CQS. Equality of CQS is compared on `filters`, `sort`, `scope`
only — `meta` and provenance tags are excluded from the comparison and MUST NOT be read by the
evaluator. Every response carries the `dataVersion` it was computed against. *Why:* "I searched the
same thing and got different results" must only ever be explained by a dataVersion change.

## INV-3 — No hidden scoring or ranking
Ordering is governed **solely** by `cqs.sort` (one key + direction) with a final ascending-PIN
tie-break. No filter contributes a relevance score. No implicit relevance, boost, or multi-term scoring
exists. *Why:* this build is filter + sort; any scoring layer is explicitly out of scope and would
create a hidden prioritization path.

## INV-4 — CQS is the only source of truth
The evaluator reads **only** the CQS. UI chips and the plain-English summary SHALL be rendered from the
canonical CQS returned by the backend, not from the frontend's pre-send guess. *Why:* display must
equal what was evaluated.

## INV-5 — Inputs are compilers only
Topic, text, and UI are pure compilers `input → CQS fragment`. They MAY write filter/sort/scope values;
they MUST NOT introduce constraints that are not representable as registry filter assignments, and MUST
NOT influence evaluation by any channel other than the CQS they produce. *Why:* keeps INV-1/INV-2 holding.

## INV-6 — Compile-time vs evaluate-time separation
All ambiguity resolution — provenance merge, text parsing, topic expansion, invalid-predicate dropping,
missing-value policy selection — happens at **compile time** and is fully captured in the CQS.
`evaluate()` performs no inference, defaulting, or conflict resolution. *Why:* given a CQS the result is
mechanically determined; this is what makes INV-2 testable.

---

## Enforcement checklist (PR gate)
- [ ] No code outside `evaluator/` produces or filters a result set.
- [ ] `evaluate()` takes only `(cqs, dataVersion)` and reads no globals, clock, or RNG.
- [ ] CQS equality tests ignore `meta` and `source`; result is byte-stable across repeated calls.
- [ ] No sort/score path other than `cqs.sort` + PIN tie-break.
- [ ] Frontend renders chips/summary from `response.cqs`, never from local pre-send state.
- [ ] Every compiler returns a CQS fragment and nothing else (no side effects, no I/O into results).
- [ ] Missing-value behavior comes from registry `unknownPolicy`, never from evaluator branching.
