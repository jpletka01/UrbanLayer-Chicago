# Report evolution V3→V6 + R5–R7 (2026-06-09 → 2026-06-18) — SHIPPED

The full planning/audit trail for the $25 Feasibility Report, collapsed. **Current architecture and
known limits live in `guides/report.md`.** The complete design-decision narrative (Development Snapshot,
render isolation, the "works on my machine" OOM story, honesty rules) is on the website **About page →
"Feasibility Report (PDF)"** section. Git history has the original plan docs if needed.

## What shipped, in order

- **V3–V5** (through 2026-06-10): synthesis rules, envelope rendering spec, approval-pathway logic,
  deterministic-where-it-must-be number discipline.
- **V6 Phases 1–3** (2026-06-10, `f0c1996`+): viability → credibility → decision-quality. Page-1
  Development Snapshot decision box, FAR-utilization framing, unit-yield from min-lot tables,
  SIMPLE/MODERATE/COMPLEX approval pathway, Ownership Intelligence, overlay-type labels, comps map.
- **V6 Phase 4** — Tier 0/1/2 + **R5/R6/R7** (2026-06-11, DEPLOYED & VERIFIED LIVE): the address→PIN
  resolution pass (R7, `a9b7e6b`) reached 98–100% exact-PIN. Lesson: a live integration probe caught the
  `78yw-iddh` `st_predir` word-vs-letter defect — trace input data, not just render logic.
- **Reranker removed from the report path** (2026-06-18, `69d8481`): the report's AI zoning extraction was
  silently failing (partial-chunk retrieval of the 30K-char Title-17 bulk table + a markdown-fence
  `json.loads` throw). Replaced by the offline precomputed **zoning cache** → 57/59 high-confidence, 0 FAR
  errors. See `guides/zoning-cache.md` + `archive/2026-06-16_report-oom-reranker.md`.

## Reusable lessons

- **Verify the running image, not git HEAD** — a live-API probe caught defects local render didn't.
- **Honesty over completeness** — ship "Valuation Indicators" / "Tax-Exempt" fallbacks rather than
  fabricating land-value ranges or comps; refuse pro-forma/IRR and "PERMITTED" verdicts by design.
- **A generous dev machine hides resource bugs** a constrained prod box surfaces as a hard OOM kill —
  reproduce on production-like limits.

## Verification parcels

EX subject `14283190070000` (481 W Deming Pl) · taxable control `14331030110000` (642 W Belden).
