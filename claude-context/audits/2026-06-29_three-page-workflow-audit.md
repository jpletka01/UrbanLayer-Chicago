# Workflow Audit — Home, Scorecard, Discovery

**Date:** 2026-06-29
**Frame:** Run each page as a real user workflow, not a component inventory. Find where trust/conversion
breaks for an attorney/developer deciding whether a parcel is worth an hour — and whether to pay $25.
**No code changed.** Audit + prioritized punch list; we set priorities together after.

## Skills applied (which guidance, where)
- **chatbot-flow-design → knowledge-base grounding.** "The bot does not invent answers; it retrieves and
  presents." This is the exact lens for #1: our chat is a *structured-guided-conversation* in name, but on
  the paths users actually take it degrades to the *hallucinating/ungrounded-bot* (answers from nothing).
- **comparison-tool-design → feature-list-dump + "cut all-checkmark rows."** The Scorecard wall of cards,
  and the area-level violations/crime padding (#2/#3), are decoration that doesn't support a decision.
- **quiz-and-assessment-design → result-page composition + honest segmentation.** A thin verdict must
  produce a short result page (#3); page length should track the verdict's confidence, not imply depth.
- **information-architecture → labeling + "navigation that hides primary content."** The violations/crime
  cards are a *labeling* failure (no scope), and chat is hidden from the Home front door.
- **journey-mapping → front-stage/back-stage disconnect.** The user perceives one continuous "this parcel"
  session; the router/back-end perceives unrelated turns (#1). That seam is the friction.

---

## PAGE 1 — Home (`HeroEntrance.tsx`)

**For, in one sentence:** "Type an address, get its Scorecard." The front door is a single address box +
example chips → `/scorecard?address=`.

**First screen delivers it?** Yes — the one job is the one element. This page is the *least* broken of the
three. The address box is the hero; nothing competes.

**Where the workflow breaks (ranked):**
1. **Chat is undiscoverable (MEDIUM).** `HeroEntrance.tsx:10` — *"There is no chat box on the front door."*
   Our second product (code-research / neighborhood chat — the differentiator) has no labeled door from
   Home; it's reachable only via persona cards or a failed-address recovery. `information-architecture`
   failure pattern: "the most important pages should be one click from home." A returning user who came to
   *ask a code question* has nowhere obvious to go. (Carried from the 2026-06-29 design audit, P3.)
2. **No example of the payoff (LOW).** The hero asks for an address but doesn't show what comes back (a
   verdict, a scorecard). A first-time visitor types blind. A single "here's what you get" preview would
   de-risk the first action.

**Load-bearing vs noise:** Home is lean. The address box + examples are load-bearing. Nothing is noise.
The gap is *omission* (the second product, the payoff preview), not clutter.

---

## PAGE 2 — Scorecard (`ScorecardPage.tsx`) — the page carrying the product

**For, in one sentence:** "Tell me whether this parcel is worth an hour, and let me interrogate it."

**First screen delivers it?** Now, post-Verdict-Band: **partly.** The verdict leads (good). But below it the
page is a fixed ~10-block wall regardless of how much the verdict actually concluded — and two of those
blocks are actively misleading (#2). The user still has to hunt, and some of what they find is false.

### Broken workflow A — Context injection is gutted (CRITICAL, #1)
This is the single highest-impact defect in the product. Our differentiator is "interrogate the parcel with
its facts loaded." On the paths real users take, the chat receives **nothing about the parcel.** Traced:

| Path | What's actually shipped to `/chat` | Result |
|---|---|---|
| Per-card "Investigate →" / verdict CTA, **pin present** | `parcel_pin` + full `scorecard_context` (zoning/property/regulatory/incentives/comps) | **Grounded** — works (the demo-clean case) |
| Per-card / verdict CTA, **pin withheld** (the 622 W Deming case, ~75% of parcels) | nothing — `InvestigateButton.tsx:9` omits pin when null → `App.tsx:400` bare `sendMessage(q)` | **Generic** (no pin, no context) |
| "Ask about this property" button, pin withheld | button is **hidden entirely** (`resolved_pin === null`) | no entry at all |
| **Any free-typed follow-up** ("what about the setbacks here") | `sendMessage` called **without `opts`** (`useChat.ts:122`) → `parcel_pin=null, scorecard_context=null` | **Generic** — grounding is one-shot, never conversation-sticky |

Three structural leaks, one pattern: **grounding is bolted onto specific handoff *clicks*, not to the state
of "I am looking at this parcel."**
- **Leak 1 — pin-gated.** `buildScorecardContext` returns `null` whenever `resolved_pin` is null
  (`scorecardContext.ts:22`). The exact parcels where data is thin (unverified/missing) get *zero* grounding.
- **Leak 2 — one-shot.** Only the handoff message carries context; every subsequent typed turn re-derives
  retrieval from the question text alone. The memory even flags this as the deferred "conversation-pinned"
  track — but from the user's seat it reads as "the feature doesn't work."
- **Leak 3 — the verdict isn't shipped.** `buildScorecardContext` omits the verdict + signals we just
  computed. Even on the happy path, the chat can't speak to "the binding constraint" the band just named.
- **Compounding back-end seam** (`chatbot-flow-design` grounding gate): even when `scorecard_context` *is*
  sent, `_scorecard_grounding_applies()` gates on a property-scoped intent, and the router types intent from
  the raw text first. "What about the setbacks here" can route as generic code-research → grounding never
  read. The handoff questions are *engineered* to carry the address precisely to dodge this; a human's
  natural follow-up isn't.

**Why this is #1:** it's the gap between a demo (clean parcel, the one scripted click) and a real session
(thin parcel, a typed follow-up). The feature *demos*; it doesn't *work*. Docs say "grounding shipped &
live" — true but narrow; the lived experience on a real parcel is blank-ChatGPT.

### Broken workflow B — Parcel vs. area data conflated (CRITICAL trust bug, #2)
`_fetch_scorecard_data` (`backend/main.py`) fetches three different spatial scopes and the page renders them
side by side as if all parcel-level:

| Card | Backend call | Real scope | Card label honest? |
|---|---|---|---|
| ViolationsCard ("642 / 535 open") | `buildings.violations_by_community_area(ca)` | **whole community area** | **No** — title "Building Violations," no scope |
| CrimeYoYCard ("964 incidents") | `crime.crime_by_community_area(ca)` + `crime_yoy_by_community_area(ca)` | **whole community area** | **No** — title "Crime," "{count} incidents (90d)" |
| Address311Card | `three11.address_311_complaints(lat, lon)` | point/address | **Yes** — "311 Complaints at Address" |
| Property / Zoning / Incentives / Regulatory / Comparables | parcel/point lookups | parcel | parcel |

A single-family RS-2 lot showing "642 building violations / 535 open" and "964 crimes" reads, to a careful
attorney, as *this building is distressed.* It's the neighborhood. Only the 311 card discloses its scope.
**Pattern:** the page silently mixes three spatial scopes with no visual or label distinction — the same bug
class we caught in verdict calibration (area-level violations + citywide ARO masquerading as parcel
friction). This actively misleads on the exact dimension (risk/condition) an attorney is scanning for.

### Broken workflow C — Density buries (and pads) the verdict (HIGH, #3)
The page renders VerdictBand → Report CTA → FinancialSnapshotStrip → up to **9 cards**, each with an
investigate link, at **fixed depth** — independent of the verdict's confidence. On 622 W Deming the verdict
is *"Constrained / building area unavailable / capacity not computed"* (we have little to say) yet it's
followed by ~10 blocks, two of which are the misleading area cards. **Pattern:** layout is fixed-depth; it
doesn't scale to confidence. `quiz-and-assessment-design` result-page composition: a thin result should be a
short page. Worse, the area cards supply fake "depth" (big numbers) that's both noise *and* untrue — #2 and
#3 compound: the wall isn't just long, its longest, highest-number blocks are the misleading ones.

### Load-bearing vs noise (per block, for a developer triaging the parcel)
| Block | Verdict |
|---|---|
| Verdict Band | **Load-bearing** (the conclusion) |
| Zoning (FAR/height/uses) | **Load-bearing** — the capacity question |
| Incentives (TIF $/OZ/EZ) | **Load-bearing** when present |
| Regulatory (landmark/flood/PD/overlays) | **Load-bearing** — the friction |
| Property (sqft/units/assessed/tax) | **Load-bearing** when present; often the "unavailable" gap |
| Comparables | **Load-bearing** — value sanity |
| Report CTA + sticky bar | Load-bearing (monetization), but two CTAs for one action |
| FinancialSnapshotStrip | **Partial** — overlaps the property/incentives cards; redundant for many parcels |
| Violations card (area) | **Noise + misleading** (#2) — demote/relabel or drop from the parcel view |
| Crime card (area) | **Noise + misleading** (#2) — relabel as neighborhood context, below the fold |
| 311 card | Borderline — honestly scoped, low decision-weight for development triage |
| Neighborhood (demographics/transit/walk) | **Context, not load-bearing** for "is this parcel worth an hour" |

---

## PAGE 3 — Discovery (`discovery/DiscoveryPage.tsx`)

**For, in one sentence:** "Filter the city's parcels down to a prospect list, then open one."

**First screen delivers it?** Mostly yes — it's a genuine 3-pane workbench (left: search + **recipe shelf**
goal-first starters + Refine filters; middle: results list; right: map). The recipe shelf is the strongest
single piece of UX in the product: it's `comparison-tool-design`'s "honest defaults" — goal-first entry with
honest "Live · N / No matches yet" badges instead of a blank query box. Discovery is the most coherent of the
three pages.

**Where the workflow breaks (ranked):**
1. **Cold-start comprehension (MEDIUM).** A first-time user lands on a dense filter rail. Recipes mitigate it,
   but the value ("what is this for, what will I get") isn't stated above the filters. The `discovery.subtitle`
   micro-line carries the whole burden.
2. **Dead-ends into the paywall (MEDIUM).** Free tier returns top-10 + a teaser wall. The transition from "I
   found 240 matches" to "you can see 10" is a conversion moment that currently reads as a wall, not a value
   ladder (`comparison-tool-design`: the recommendation/CTA should feel earned, not gated).
3. **No Discovery → chat seam (LOW-MED).** A user who finds 40 teardown candidates can open one Scorecard
   (row → `?pin=`), but can't ask the analyst about the *set*. The cross-page intelligence is parcel-only and
   one-directional (carried from the prior audit, P5).

**Parcel/area conflation here?** **Clean.** Discovery rows are per-parcel from the index (address-first row
cards); the map colors by per-parcel upside/land-use. The #2 bug does **not** recur here — which is itself
evidence that the Scorecard's area-as-parcel rendering is an isolated, fixable seam, not a data-model
problem.

**Load-bearing vs noise:** Lean. Recipe shelf, filter panel, results list, map are all load-bearing. The risk
is comprehension density, not decoration.

---

## The three patterns behind the issues
1. **Grounding is attached to clicks, not to parcel-state.** Any deviation from the one scripted handoff
   (thin parcel, typed follow-up, the verdict itself) falls back to ungrounded. (#1)
2. **The Scorecard mixes spatial scopes without disclosing them.** Parcel / point / community-area numbers sit
   as visual peers; only 311 is labeled. (#2)
3. **The Scorecard is fixed-depth.** It renders the same wall whether the verdict is rich or "we don't know,"
   and the padding blocks are the misleading ones. (#3)

All three are *presentation/workflow* failures, not data or model failures — which is why they're high-ROI:
the data to do it right is already loaded on the page.

---

## Prioritized punch list (highest trust/conversion impact first)

| # | Fix | Page | Why it's here | Pattern |
|---|---|---|---|---|
| **1** | **Make chat grounding conversation-sticky + ship the verdict + handle pin-withheld parcels.** Hold `scorecard_context` (incl. the computed verdict/signals) for the whole parcel-scoped conversation, not just the handoff turn; ground by lat/lon when `resolved_pin` is null; widen the back-end grounding gate so a natural follow-up doesn't need an engineered address. | Scorecard↔Chat | The differentiator is gutted on every real path. Demos, doesn't work. | #1 |
| **2** | **Disambiguate every number's scope.** Relabel Violations/Crime as "in {community area}" (or move them into a clearly-separated "Neighborhood context" group below the parcel cards); keep parcel cards visually distinct from area cards. | Scorecard | Actively misleads attorneys on risk — a trust bug, not polish. | #2 |
| **3** | **Scale page depth to verdict confidence.** When the verdict is thin/caveated (capacity not computed, few signals), render a short page — collapse area/context cards by default; expand only on a rich verdict. | Scorecard | A wall that implies depth we don't have erodes trust at the decision moment. | #3 |
| **4** | **Collapse the duplicate report CTAs + reconcile FinancialSnapshotStrip** with the property/incentives cards (one CTA, no redundant strip). | Scorecard | Hierarchy: one primary money action; cut the overlap. | #3 |
| **5** | **Give chat a labeled door from Home** (and the returning-user nav), keeping the address-first funnel intact. | Home | The second product is invisible. | IA |
| **6** | **Soften the Discovery free→paid wall into a value ladder**, and add a Discovery→chat seam for the result set. | Discovery | Conversion moment + cross-page intelligence. | — |
| **7** | **Add a "what you get" payoff preview** to the Home hero. | Home | De-risks the first action. | — |

**Recommended sequencing for discussion:** #1 and #2 are the two that decide whether a fence-sitter trusts us
enough to pay, and both are isolated seams with the data already in hand. #3 compounds #2 (the padding blocks
*are* the misleading ones), so #2+#3 are natural to do together. #5–#7 are real but second-order.

## Appendix — primary evidence
`HeroEntrance.tsx:10`; `InvestigateButton.tsx:9`; `App.tsx:337-448` (sendMessage/autosend/starters);
`useChat.ts:122-173`; `lib/scorecardContext.ts:21-42`; `backend/main.py` `_fetch_scorecard_data`
(`violations_by_community_area` / `crime_by_community_area` / `crime_yoy_by_community_area` /
`address_311_complaints`); `ScorecardPage.tsx` (card grid + fixed depth); `discovery/DiscoveryPage.tsx:174-263`.
