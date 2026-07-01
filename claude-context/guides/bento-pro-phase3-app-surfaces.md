# Bento Pro Phase 3 — Scorecard & Discovery Redesign (working doc)

**Status:** PLANNING on branch `feat/bento-pro`. Started 2026-07-01.
**This is the project workspace** for the app-surface overhaul: spec, decisions log, and
status live here. Companion to `bento-pro-redesign.md` (Phases 0–2, homepage — done there
stays there). Homepage *visualization* work (real-map section, ChaosToVerdict rebuild) is
DEFERRED by Jack — do not pick it up from this doc.

## Diagnosis (from the 2026-07-01 live audit, dark mode @1440px)

Both pages inherited the Bento palette but never got an information-design pass. The data
display is not actionable:

**Scorecard** (`ScorecardPage.tsx`, 808 lines, cards inline):
- Verdict band content hugs the left ~40%; right 60% is empty black. The page's most
  important element looks unfinished.
- No hierarchy: FAR/zoning capacity (decision-critical) and "Blue Recycling Cart: 3
  complaints" (trivia) get identical card weight in a 2-col masonry with no reading order.
- A parcel page with no real map — only a ~100px static thumbnail.
- Every number is text; assessment/sales/tax history hide behind `>` disclosure rows.
- Incentives leads with five gray negatives ("Not in TIF", "Not in Opportunity Zone"…).
- 7 regulatory overlays render as identical boxes whether constraint (landmark district)
  or opportunity (TOD, ADU-eligible).

**Discovery** (`discovery/`, ~2.9k lines):
- Default state = blank middle column ("Set filters and run a search") — reads as broken.
- Indexed-area banner collides with the floating nav.
- REFINE filter panel is invisible (all collapsed, faint `+`) in a product that IS a
  filter workbench.
- Result rows are dense mono text; "● Upside 90" is plain text, unconnected to the map's
  color ramp; no indication of what drives the score.
- List and map are not visibly linked.

## Hard constraints (do not violate)

1. **Verdict logic is calibrated** — `lib/scorecardVerdict.ts` (deterministic, 6
   categories, thresholds calibrated on 59 parcels). Visual redesign only; no threshold
   or copy-semantics changes.
2. **2026-06-30 seam decisions are policy** (see archive/2026-06-30_verdict-grounding-ux.md):
   address-exact tri-state violations; neighborhood context demoted + labeled "describes
   {area}, not this parcel"; ONE report CTA; nearest-parcel amber caveat; card-linked
   verdict reasons.
3. **Discovery INV-4**: the FE never evaluates queries — chips/summary render from
   `response.cqs`. CoverageBanner never merges into the CQS.
4. **Functional data colors exempt from theming**: `upsideColor.ts`, `DataPill`,
   `mapColors.ts`, map layers. The redesign *uses* the upside ramp in more places; it
   never re-hues it.
5. **Premium gating stays**: Discovery free teaser/top-10, CSV export gate, report CTA
   violet = "costs money".
6. Dataviz work must follow the `dataviz` skill method (read it before writing any chart
   code) adapted to Bento tokens.

## Scorecard redesign spec

Target IA — three tiers, one-column narrative with side rail (replaces flat masonry):

**Tier 1 — The decision (full-width hero band):**
- Left: verdict (existing computeVerdict output: label, reasons deep-linking to cards,
  ONE next step, caveats) — visually rebuilt, not recomputed.
- Center: 3–4 stat tiles justifying the verdict: zoning capacity (FAR as-of-right, max
  height), assessed value + eff. tax rate, comps median, biggest constraint. Tiles
  deep-link to their evidence cards (keep existing anchor mechanism).
- Right: **real map panel** — parcel location + overlay footprints. Decision needed
  (see Open questions): Mapbox GL (interactive, heavier) vs larger Static API image
  with overlay badges (cheap, fast). Recommendation: static-first, GL later.
- The band uses the full width in all states; empty-right-side bug dies here.

**Tier 2 — The evidence (the money + rules, each with a visualization):**
- Property: `assessment_history` → sparkline w/ YoY delta; `tax_breakdown` (11
  agencies) → horizontal stacked bar, top 4 + "other"; keep raw table behind disclosure.
- Comparables: dot strip of sale prices on a price axis, subject's assessed value marked;
  median + range as labels, existing rows behind disclosure.
- Zoning: keep ZoningCard content, add a small FAR-used vs FAR-allowed meter when
  building area is known (data may be null — degrade to text).
- Overlays: severity-sorted chip rows — constraint (orange border), opportunity
  (positive), neutral (muted) — instead of 7 identical boxes. Mapping: landmark/historic/
  national-register = constraint; TOD/ADU/SSA/ARO = context-dependent, default
  opportunity; flood X = neutral-positive.
- Incentives: active/eligible programs first as real cards; the "Not in X" set collapses
  to one muted line ("Not in: TIF · OZ · Enterprise Zone · QCT · NMTC").

**Tier 3 — The record (compact, demoted):**
- Violations tri-state, 311, permits, neighborhood-context section — dense compact rows,
  collapsed by default except a one-line summary each. Existing collapse mechanics stay.

**Refactor while touching:** extract inline cards from ScorecardPage.tsx into
`components/scorecard/` as they're redesigned (no big-bang rewrite; page shrinks card by
card). Charts: extend the existing custom SVG chart primitives (`PieChart`/`BarChart` in
sidebar analytics) or add small purpose-built SVGs; no chart library.

## Discovery redesign spec

1. **Kill the blank state**: on load with a live index, auto-run the first recipe with a
   live badge (cheap: counts are already fetched for badges; run the top-1). Query-param
   deep links and the teaser path unchanged.
2. **Fix banner/nav collision**: CoverageBanner moves below the floating nav's clearance
   (or becomes a compact chip row under the results header). Never under the nav pill.
3. **Upside score becomes visual + map-linked**: score badge tinted from `upsideColor.ts`
   ramp (same encoding as map dots) + small meter bar in each row. Legend language then
   matches rows 1:1.
4. **Result cards**: address-first (stays), then a "why" line — the 2–3 fields driving
   the recipe (e.g. bldg/land value ratio for teardowns, $/sqft percentile for
   undervalued) as compact labeled values instead of an undifferentiated mono blob.
   PIN stays demoted/mono.
5. **Filter affordance**: the group relevant to the active recipe opens automatically;
   groups get filled-count chips (`Property & Use (1)` exists — make it visible);
   sticky "N results" + Search at the panel bottom.
6. **List ↔ map linkage**: row hover highlights the map dot (ring/pulse), map dot hover
   highlights + scrolls the row. deck.gl picking already exists for premium tier.
7. **Chrome reskin** (the original Phase 3 item): bento cards for recipes/rows, tokens
   everywhere — but data colors untouched (constraint 4).

## Order of work

1. Scorecard Tier 1 (verdict hero band + stat tiles + map panel) — highest value.
2. Scorecard Tier 2 visualizations (tax bar, assessment sparkline, comps strip, overlay
   severity, incentives flip).
3. Scorecard Tier 3 demotions + extract-to-components cleanup.
4. Discovery items 1–3 (blank state, banner, upside visual) — the usability floor.
5. Discovery items 4–6 (result cards, filters, linkage).
6. Chrome sweep + update stale docs (`frontend/CLAUDE.md` tokens section,
   `design-system.md`, `light-dark-theming.md` — still describe azure/vellum).

Verification per step: `npm run build` (CI gate) + Playwright screenshots dark AND light
+ `npx vitest run` (Discovery has real tests; don't break INV-4 suites).

## Decisions log

- 2026-07-01 — Plan created. Homepage visualization work deferred by Jack.
- 2026-07-01 — Hero backdrop: plat-map variant chosen (periphery-masked, achromatic,
  currentColor inversion); accent plat-rails added below hero @ 16% alpha.

## Open questions (for Jack)

1. **Scorecard map panel**: static image + overlay badges (fast, ships in step 1) or
   interactive Mapbox GL with parcel polygon + overlay toggles (better, heavier)?
   Recommendation: static now, GL as a later upgrade.
2. **Discovery auto-run**: OK to fire one search on page load (backend cost per visit)?
   Alternative: render the first recipe's cached top-10 as a preview.
3. **"Documents section / workspace"** — needs a scope decision:
   - If this meant *repo workspace for the redesign*: this doc is it (claude-context/ is
     the established mechanism; guides/ + archive/ on ship).
   - If this meant a *product feature* (users maintain a dossier/workspace of saved
     scorecards, reports, notes per project): that's product scope, not part of this
     visual overhaul — belongs on the North Star / coherence-audit track. Flag which.
