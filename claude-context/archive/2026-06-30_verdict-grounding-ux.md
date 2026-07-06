# Scorecard Verdict Band + grounding seam + UX punch list (2026-06-30) — SHIPPED

Shipped & image-verified live in two decoupled deploys (theming `679e236`, then scorecard `499cef7`).
Conclusion-first deterministic **Verdict Band** leads the Scorecard (`lib/scorecardVerdict.ts` — 6 categories, no
LLM, thresholds calibrated on 59 parcels); the parcel-vs-area conflation killed end-to-end (UI + chat grounding);
grounding deepened to **conversation-sticky** (`activeGroundingRef` on every turn) with verdict+caveats in context
and an **address-violations tri-state** (present / confirmed-zero / unconfirmed) so chat affirms "none on record at
this address" instead of retreating to the area count (prompt rule 29). One report CTA; labeled subordinate chat
doors. The #7 payoff card was built then **reverted** (jargon to a context-less newcomer).

**Reusable lessons:** verify what ships in the form it ships (served image over git HEAD; `npm run build`/`tsc -b`
over `tsc --noEmit` — a leftover import silently skipped a CI-gated deploy); live-review + measured WCAG contrast
as the gate (caught a 4.20 hover AA miss); decouple deploys you can't jointly vouch for; a push to main is never a
no-op (recreates containers → brief 521). Current Scorecard is the About page → **The Scorecard**. Historical marker.
