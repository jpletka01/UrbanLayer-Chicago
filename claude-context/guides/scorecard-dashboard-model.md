# Scorecard as a Property Dashboard — design model (2026-07-01, NO CODE YET)

> **2026-07-06 partial supersede** (`archive/2026-07-06_scorecard-usability.md`): diagnosis #1
> (stretch gaps) is mitigated in production — section grids are `md:items-start` + the regulatory
> card has a top-6 constraint budget; diagnosis #3 (action afterthought) is RESOLVED differently
> than proposed: the sticky **ask bar is superseded by MiniChatDock** (bottom-right grounded
> quick-chat; per-card chips now open it in place via `InvestigateButton onAsk` instead of dying
> or navigating away; ephemeral-unless-escalated). Open question 2 (ask bar vs chat page) is
> thereby answered. Still open: the fixed-height 12-col module layout, KPI strip w/ benchmarks,
> identity rail, and the Phase A/B insight layer.

Companion to `bento-pro-phase3-app-surfaces.md`. Output of the "what is this page
for" discussion with Jack; supersedes the question-section layout as the *target*
(what shipped on the branch stays until this is approved and built).

## The jobs (agreed framing)

| Job | Who / entry | Needs | Tempo |
|---|---|---|---|
| Triage — go/no-go | developer/investor via hero or Discovery | verdict, capacity, catch, basis | < 1 min |
| Verification | pre-offer diligence, attorney | citable exact facts, provenance, dates | careful read |
| Client-answer | architect/attorney/broker | one pointed answer + handoff to analyst | in & out |
| Underwriting inputs | investor | copyable numbers (tax, comps, incentives) | extract |

Funnel constraint: useful enough to return to; incomplete enough to buy the $25
report. **Present-state insight is free; forward-looking analysis (development $,
tax projections, permit outlook) is teased and gated.**

## Diagnosis the model must fix

1. **Gaps**: current model is "card = data source, height = data volume." Invert it:
   **the layout fixes module size; content is elastic** (top-N + "and N more",
   internal disclosure, fixed-size empty states). Modules never collapse or stretch
   the grid.
2. **Insight-less**: facts without benchmarks. Insight = fact + benchmark +
   implication. Every headline number must carry a comparison.
3. **Action afterthought**: per-card investigate chips die. One persistent
   ask-the-analyst affordance owns that job.

## Layout model (12-col, fixed-height module rows)

```
┌────────────────────────────────────────────────────────────┬──────────────┐
│ VERDICT BAND (exec summary — narrative, unchanged role)    │ IDENTITY RAIL│
│ headline · reasons · one next step · caveats               │ locator map  │
├────────────────────────────────────────────────────────────┤ PIN · badges │
│ KPI STRIP — 6 fixed tiles, each value + benchmark delta    │ data-as-of   │
│ [FAR use][Eff tax vs area][$ /sqft vs area][Assess Δ3yr]   │ provenance   │
│ [Upside score][Constraints]                                │ report CTA   │
├──────────────────────────────┬─────────────────────────────┤ (violet)     │
│ CAPACITY (fixed h)           │ RULES (fixed h)             │ export CSV   │
│ envelope meter, standards,   │ top-3 constraints + "+N",   │              │
│ uses in prose                │ top opportunities           │              │
├──────────────────────────────┼─────────────────────────────┤              │
│ ECONOMICS (fixed h)          │ MARKET (fixed h)            │              │
│ assessment sparkline,        │ comps price strip, median,  │              │
│ tax bars + vs-area line      │ $/sqft percentile           │              │
├──────────────────────────────┼─────────────────────────────┤              │
│ RECORD (fixed h)             │ ENVIRONMENT (fixed h)       │              │
│ violations/311 mini-table    │ flood, brownfields          │              │
└──────────────────────────────┴─────────────────────────────┴──────────────┘
│ ASK BAR (sticky bottom): "Ask anything about this parcel…" → grounded chat │
└────────────────────────────────────────────────────────────────────────────┘
```

- **Identity rail** (right, sticky): identity/confidence/provenance + the ONE money
  CTA + export. Frees the header; gives verification-job users a permanent home.
- **KPI strip** replaces the band's tile rail — same deep-link behavior, but every
  tile shows value + benchmark ("2.07% · area median 1.7%").
- **Ask bar** (sticky bottom): typed question → existing `/?q=&pin=` grounded
  handoff. Replaces ALL per-card chips. Optionally per-module "ask" on hover only.
- Neighborhood context stays a collapsed appendix (scope policy unchanged).
- Mobile: rail folds under verdict; modules stack; ask bar stays sticky.

## The insight layer — what powers the benchmarks

**Phase A — computable today, no backend work:**
- FAR utilization (existing verdict signals) → "using 55% of envelope"
- Building/land assessed split (assessment records) → teardown ratio ("improvements
  = 0.2× land")
- Assessment 3-yr trajectory + delta (already drawn)
- Overlay implications (static copy per type: landmark → design review months, TOD
  → parking relief)

**Phase B — backend seams (design before building):**
- Neighborhood benchmarks: area median eff-tax, $/sqft, assessment trend. Candidate
  source: **Discovery index already holds per-parcel AV, sqft, ratios citywide** —
  an aggregate-by-CA endpoint over it gives medians/percentiles cheaply.
- Parcel percentile ("this lot's $/sqft is P23 of West Town") — same seam.
- Reuse `upsideColor`/upside score on the Scorecard KPI strip (same encoding as
  Discovery = cross-page consistency).

## Open questions (blocking approval)

1. Density vs first-timer trust: is the verdict band + KPI strip enough narrative
   for a cold visitor? (Phase 2 interviews should answer.)
2. Ask bar vs chat page: does an embedded input compete with "Ask the analyst" nav?
   (Proposal: same destination, one affordance on-page.)
3. Which KPIs make the strip of 6? (Proposed above; needs Jack's cut.)
4. Analytics pull — DONE 2026-07-01, and the answer is "no signal": prod events
   table (tracking live since ~2026-06-10) holds 42 events / ~33 visitors total.
   page_view: `/` 33 visitors, `/scorecard` 2, `/discovery` 2; exactly one each of
   investigate_click (verdict), report_cta_click, sample_report_click,
   chat_message_sent, hero_address_submit. Traffic ≈ 1/day, likely incl. Jack +
   bots. CONSEQUENCES: (a) usage data cannot arbitrate module priority — Phase 2
   interviews are the only evidence source; (b) the funnel drop is at the
   homepage or before it (acquisition), not inside the Scorecard; (c) instrument
   the redesign properly from day one (add csv_export, section-visibility, and
   scroll-depth events) so the next audit has data.

## Status
- 2026-07-01: model drafted, discussion-stage. No implementation.
