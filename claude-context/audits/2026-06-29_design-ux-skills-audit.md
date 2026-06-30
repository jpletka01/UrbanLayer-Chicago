# Design & UX Audit — UrbanLayer vs. rampstackco/claude-skills

**Date:** 2026-06-29
**Auditor:** Claude (skills-grounded review)
**Working hypothesis (owner):** *The design is overcomplicated — it explains more than it shows, which is hurting the product.* Spans card components, color usage, and how users interact with components.
**Scope:** No code changed. This is the written audit + prioritized punch list that precedes any implementation.

Reference corpus: `rampstackco/claude-skills` (103 skills). Cloned, inventoried, and the design/UX-relevant subset read in full.

---

## Verdict (one paragraph)

The hypothesis is correct, and it has a precise name in the skills corpus. The Scorecard — the product's center of gravity — is a **feature-list-dump** (`comparison-tool-design`) / **vanity-result** (`quiz-and-assessment-design`): it presents a large volume of accurate, well-tokenized data and asks the attorney/developer to synthesize the conclusion themselves. The page literally documents this in code: the verdict line is commented *"every clause restates a flag that is already rendered in a card below — no scoring, no interpretation"* (`ScorecardPage.tsx:391`). That is the disease, stated as a design principle. Separately, the chat — a genuinely strong, RAG-grounded `structured-guided-conversation` — has been **removed from primary navigation** and is reachable only by indirect paths, which is a discoverability failure (`information-architecture`). The design *system* (tokens, primitives, palette) is actually in good shape; the problem is not visual chaos, it's **information architecture and decision-support**: the product shows everything and concludes nothing.

---

## Task 1 — Relevant skills inventory

Of 103 skills, these are the ones that bear directly on this audit. Each with why.

### Tier 1 — directly decisive

| Skill | Why it's relevant |
|---|---|
| **quiz-and-assessment-design** | Its trigger list literally includes "**scorecard**." Its keystone framing — *clickbait → vanity-result → actionable-segmentation* — is the exact lens for Task 3. The litmus test ("after using it, can a stranger name the next thing they should do?") is the test our Scorecard fails. |
| **comparison-tool-design** | Keystone framing *feature-list-dump → hidden-recommendation → honest-comparison-with-guidance* describes our Scorecard precisely. "8–12 decision-relevant axes, cut decoration" and "recommendation visible and defended" are the redesign spine. |
| **design-standards** | The 6-standard rubric (tokens, AA contrast, hierarchy, spacing, mobile, component consistency) is the checklist for the "overcomplicated" complaint. Our system passes most of it — which is *itself* a finding: the problem isn't the standards, it's altitude/hierarchy. |
| **information-architecture** | Task 2's "how reachable is each tool from a single page" is an IA question. Failure pattern "Navigation that hides primary content — the most important pages should be one click from home" maps 1:1 to chat being de-navved. |

### Tier 2 — strongly informing

| Skill | Why it's relevant |
|---|---|
| **chatbot-flow-design** | Task 2's chat evaluation. Our chat is the *good* pattern (RAG-grounded, cited, escalation-free because it's the destination) — the skill helps articulate *why it's good but invisible*, and where intent/fallback discipline could surface it better. |
| **journey-mapping** | Task 2's "does context carry across pages, or does the user start over?" This is a touchpoint/friction-across-the-journey question. The Scorecard↔chat↔Discovery handoffs are the journey seams to map. |
| **calculator-design** | Sister skill to quiz: *vanity-calculator → lead-trap → transparent-decision-tool*. The $25 report is our "tool that gives a number"; the Scorecard should behave like a transparent decision tool (give the answer, earn the upsell), not a lead-trap. |
| **frontend-component-build** | Card component states/props/altitude — the mechanism for any card consolidation work. |

### Tier 3 — supporting / situational

`accessibility-audit` (the confidence badges + color-only state encoding need a WCAG pass), `cro-optimization` (the Scorecard→$25 funnel is the money path), `usability-testing` (validate the redesign with the 2 personas before shipping), `jtbd-framing` (sharpen "what job is the attorney/developer hiring the Scorecard to do"), `landing-page-copy` (lead-with-verdict copy patterns), `design-system` (governance for the tokens we already have).

> Note on corpus fit: the skills repo is **growth/marketing-tooling-oriented** (SEO, ads, funnels, brand). The *decision-support tooling* skills (quiz/comparison/calculator/chatbot) transfer cleanly to our product surfaces; the SEO/ads/brand bulk does not, and we should not force it.

---

## Task 2 — Pressure-testing our design decisions against real usage

Our recent design history is well-documented and mostly sound: the design-system refactor (`design-system.md`, shipped `bf33d70`), the coherence audits (`product-coherence-audit.md`), and the light/dark theming work. The decisions below are where the documented rationale and the skills disagree, or where a past decision has a cost the docs underweight.

### 2a. Accessibility / discoverability — how reachable is each tool from one page?

**Finding (HIGH):** Chat — our single most differentiated capability — is **not in the primary nav**. `PageHeader.tsx:10-17`: `NAV_ITEMS = [Scorecard, (Discovery), Pricing]`. The comment says *"Chat ('Analyst') was [removed]"*. The front door (`HeroEntrance.tsx`) is address-only with *"There is no chat box on the front door."* Chat is reachable only via: (a) persona cards on the landing, (b) per-card "Investigate" links *after* a Scorecard loads, (c) a failure-recovery redirect when an address search fails.

- Against `information-architecture` failure pattern: *"Navigation that hides primary content. The most important pages should be one click from home."* Chat is zero-click from home only if you already failed at something else.
- This was a **deliberate** coherence-audit decision ("focused funnel, not a launcher" — `2026-06-15_homepage-coherence-pass.md`), and the funnel logic is defensible. But the decision optimized the *acquisition* funnel (address → Scorecard → $25) at the cost of *discoverability of the second product*. The cross-examination: a returning user who came for code research has **no labeled door**. "Analyst" exists as a concept, a URL (`/?analyst=1`), and a removed nav item — but not as anything a user can see.
- **Verdict:** The funnel-first homepage is right. Removing chat from the *signed-in / returning-user* nav entirely is over-rotation. These are different audiences and the nav serves both.

**Finding (MEDIUM):** Discovery is nav-gated on index data (`navItemsFor(discoveryLive)`), which is correct, but it means the nav silently changes shape between environments — a consistency cost the `design-standards` "component consistency" standard would flag if it were chrome rather than data-driven. Low harm; note only.

### 2b. Chat integration — is it surfaced well and genuinely useful in context?

**Finding:** The chat itself is the **good** pattern from `chatbot-flow-design` — *structured-guided-conversation*: RAG-grounded over municipal code, citations (`CitationPill`/`DataPill`), per-message context, and the Scorecard→chat grounding handoff (`scorecard_context`) so the bot reads pre-resolved facts instead of re-deriving them. This is genuinely better than most production chatbots. **Quality is not the problem.**

**Finding (HIGH):** Surfacing *in context* is uneven. On the Scorecard, every one of the ~9 cards carries its own "Investigate" link plus an "Ask about this property" button plus "Full analysis" (`ScorecardPage.tsx:565-772`). That is **9+ chat entry points competing as peers**, which is the inverse of the discoverability problem — not hidden, but *diluted*. `design-standards` standard #3: *"If three things compete for primary attention, none wins."* The contextual chat affordance is everywhere and therefore nowhere. A single, prominent "Ask the analyst about this parcel" anchored to the verdict would outperform nine muted links.

**Finding (MEDIUM):** The 9 per-card investigate prompts are pre-baked questions, which is good grounding, but they read as *"here is more data you could go fetch"* rather than *"here is the open question a pro would actually ask."* The prompts restate the card topic ("Tell me about the building and property characteristics…") instead of advancing the decision ("Is this lot's FAR the binding constraint, or is it height?").

### 2c. Cross-page intelligence — does context carry, or does the user start over?

**Finding:** Mechanically, context carries **well** — better than the hypothesis assumes. `SelectedParcelContext` holds parcel identity; `?pin=` is the canonical handoff; the Scorecard→chat path ships `scorecard_context`; the chat→Scorecard bridge (`ScorecardBridgeCard`) reverses it. This is real cross-page intelligence and it's a genuine strength.

**Finding (MEDIUM):** The seams are *one-directional and parcel-only*. (1) **Discovery → Scorecard** carries a pin, but **Discovery → chat** and **chat filters → Discovery** don't exist — a user who finds 40 teardown candidates in Discovery can't ask the analyst about the *set*. (2) The grounding rides the **explicit pin handoff only**, never free-typed turns (documented drift hazard at the router seam, `2026-06-21_scorecard-chat-grounding.md`). So a user who *types* a follow-up about the parcel they're plainly looking at can fall back to re-geocoding. The journey map (`journey-mapping`) would flag this as a "front-stage/back-stage disconnect": the user perceives one continuous session; the router perceives unrelated turns.

---

## Task 3 — Scorecard deep-dive: it dumps, it doesn't score

### The diagnosis, stated in the skills' own vocabulary

The Scorecard is a **feature-list-dump** (`comparison-tool-design`) and a **vanity-result** (`quiz-and-assessment-design`). Evidence, in code:

- `ScorecardPage.tsx:391-405` — the "verdict line" is explicitly **facts-only, no scoring, no interpretation**. It concatenates flags (`R-4 Residential · in TIF · Opportunity Zone · TOD-eligible · flood X`) that are *already rendered as cards below*. It restates; it does not conclude.
- `ScorecardPage.tsx:638-773` — ~9 cards (Property, Comparables, Zoning, Incentives, Regulatory, Violations, Crime, 311, Neighborhood) rendered in a `columns-2` masonry. Every card is a *peer*. There is no hierarchy of decision-relevance — crime YoY and FAR sit at the same altitude.
- The litmus tests both fail. `quiz`: *"can a stranger name the next thing they should do?"* — No; they get 9 cards and a flag list. `comparison`: *"does it tell the user what to choose for their situation, with reasoning?"* — No; there is no recommendation object at all.

The irony: **we already have the data to score.** `ScorecardResponse` (`api.ts:559`) + `ContextObject` carry FAR, max height, lot coverage, allowed uses (`ZoneDefinition`), TIF with dollar figures (`tif_cumulative_revenue`, `tif_fund_balance`), OZ/EZ/QCT/NMTC, TOD/ADU/ARO eligibility, flood zone, building vs. land sqft, units, assessed value, tax, and comparables. We have a developer's whole feasibility input set and we render it as a filing cabinet.

### What a Scorecard should *conclude* — for our two personas

`jtbd-framing` question: what is the attorney / developer hiring the Scorecard to do? Not "show me the data" (they can pull the county records). They're hiring it to answer: **"Is this parcel worth my next hour?"** The Scorecard is a *triage / qualification* instrument. That makes it, in `quiz-and-assessment-design` terms, an **actionable-segmentation** tool: it should place the parcel into a defined category with a specific next step.

A real Scorecard concludes on a small number of **decision axes** (`comparison-tool-design`: 8–12 decision-relevant axes, cut decoration):

1. **As-of-right capacity vs. existing** — does zoning (FAR/height/coverage) allow materially more than what's built? (The single biggest "is there a deal here" signal. We have FAR + bldg_sqft + land_sqft to compute a buildable-vs-built ratio.)
2. **Incentive stack** — is this parcel in money? TIF (with available balance), OZ, EZ, QCT/NMTC. We have dollar figures, not just booleans.
3. **Entitlement friction** — what stands between the buyer and a permit? Landmark/historic, PD, planned-development, ARO obligation, flood. These are *cost/risk*, and we flag them but never weigh them.
4. **Bonus eligibility** — TOD / ADU unlock density. Upside levers.
5. **Site/condition risk** — open violations, high-risk 311 flags, flood hazard.
6. **Value context** — comparables + assessed value as a sanity band.

### Proposed redesign — lead with the verdict, support with evidence

**Structure (top to bottom):**

1. **The Verdict Band (new).** Replaces the facts-only flag string. A single conclusion the page commits to, in the honest-recommendation discipline of `comparison-tool-design` (visible, defended, overridable):
   - A **headline call** — e.g. *"Strong upzoning candidate in an incentive-rich district"* / *"Constrained: built near max, landmark friction"* / *"Thin: as-of-right only, no incentives."* This is the *segment* (`quiz` result-categorization: 4–6 named, distinguishable categories, honestly not all flattering).
   - **2–4 reasons**, each a clause that *defends* the call and **deep-links to the card that proves it** (`comparison-tool-design`: "reasoning shown, source linkable"). E.g. "≈2.1× more buildable area than built (FAR 3.0 vs. ~1.4 existing) →".
   - **The next step** (`quiz`: result-to-recommendation mapping — the result must tell them what to DO): the single most relevant action — *Ask the analyst about the FAR constraint* / *Buy the Feasibility Report* / *See comparable sales* — not nine equal links.
   - **Confidence + caveats** inline (we already compute `nearest_parcel_unverified`, `partial_failures`, parcel-confidence badges — surface them *as part of the verdict's honesty*, not as scattered banners).

2. **Decision axes (re-grouped cards).** Demote the 9 peer cards into the 5–6 decision axes above, ordered by decision-relevance, not data-source. Capacity and Incentives lead; Crime/311/Neighborhood become a single collapsible "Context & risk" group (real for some deals, decoration for most — `comparison-tool-design`: cut all-checkmark rows). This is where the "overcomplicated / explains more than it shows" hypothesis gets resolved: the *evidence* stays (we don't delete data), but it moves **below** the conclusion and **under** progressive disclosure.

3. **One contextual chat anchor + the report CTA.** Collapse the 9 investigate links to a single verdict-anchored "Ask the analyst" plus the existing $25 CTA. (`calculator-design` transparent-decision-tool: give the answer, *earn* the upsell with the depth the report adds — don't lead-trap.)

**Honesty discipline (non-negotiable, from `comparison-tool-design` + `evidence-based-reviews`):** the verdict must be a **defensible, rules-based scoring** of facts we hold, not an LLM guess, and it must be honest about negatives ("landmark district — expect design review"). When a competitor axis is weak, say so. The override path is the evidence cards directly below. A biased or hand-wavy verdict is worse than no verdict — it's the *hidden-recommendation* anti-pattern and it would torch trust with attorneys specifically.

**Scoring mechanism:** deterministic and transparent — a small rules engine over `ScorecardResponse` (thresholds on FAR-ratio, incentive presence + balance, friction flags), not a model call. This keeps it fast (the Scorecard's whole promise is ~2s), explainable in court-adjacent contexts, and testable. Show the inputs; never a black-box grade (`quiz` anti-pattern: the black-box quiz).

---

## Prioritized punch list (highest user impact first)

| # | Change | Impact | Effort | Skill basis | Files |
|---|---|---|---|---|---|
| **P0** | **Scorecard Verdict Band** — replace facts-only flag line with a rules-scored headline call + 2–4 defended, card-linked reasons + one next step. | ★★★★★ | M | quiz-and-assessment-design, comparison-tool-design | `ScorecardPage.tsx:391-405,549-553`; new `lib/scorecardVerdict.ts` |
| **P1** | **Re-group the 9 peer cards into 5–6 decision axes**, ordered by decision-relevance; Crime/311/Neighborhood → one collapsible "Context & risk." | ★★★★★ | M | comparison-tool-design (axis selection, cut decoration) | `ScorecardPage.tsx:638-773` |
| **P2** | **Collapse 9 investigate links → 1 verdict-anchored "Ask the analyst"** + keep the $25 CTA. Rewrite prompts to advance the decision, not restate the card. | ★★★★ | S | design-standards #3, chatbot-flow-design | `ScorecardPage.tsx:565-772`, `InvestigateButton.tsx` |
| **P3** | **Put chat back in the nav** for returning users (a labeled "Analyst" door), keeping the address-first homepage funnel intact. | ★★★★ | S | information-architecture (hidden primary content) | `PageHeader.tsx:10-29` |
| **P4** | **Surface the verdict's honesty inline** — fold `nearest_parcel_unverified` / `partial_failures` / confidence into the verdict band instead of separate banners. | ★★★ | S | comparison-tool-design (honest recommendation) | `ScorecardPage.tsx:521-563,618-625` |
| **P5** | **Cross-page seam: Discovery→chat and typed-follow-up grounding.** Let a Discovery result set hand off to chat; close the typed-turn grounding gap. (Larger; the documented router-seam track.) | ★★★ | L | journey-mapping, chatbot-flow-design | router/`_apply_parcel_hint`, `useChat.ts`, discovery |
| **P6** | **Accessibility pass on state encoding** — confidence/risk currently lean on color (`text-state-negative` etc.); add non-color cues; verify AA on the new verdict tones. | ★★ | S | accessibility-audit, design-standards #2 | scorecard cards, `index.css` tokens |
| **P7** | **Validate the redesign with 2–3 attorneys/developers** (the litmus test: can they name the next step?) before broad rollout. | ★★★ | S | usability-testing, quiz litmus test | n/a (research) |

### What NOT to do
- **Don't touch the design system tokens/primitives.** They're good (`design-system.md`). The fix is altitude and IA, not repainting. Resist the urge to "simplify" by restyling.
- **Don't make the verdict an LLM call.** Rules-based, deterministic, fast, defensible. An attorney will not trust (and may be liability-exposed by) a black-box grade.
- **Don't delete evidence.** "Show less" here means *demote and progressively disclose*, not remove. The data is a real asset and the $25 report depends on it.
- **Don't force the SEO/ads/brand skills** onto this product. The decision-support tooling skills transfer; the growth-marketing bulk does not.

---

## Appendix — skills read in full for this audit
`quiz-and-assessment-design`, `comparison-tool-design`, `design-standards`, `information-architecture`, `chatbot-flow-design`, `journey-mapping` (full SKILL.md). Inventoried all 103; the design/UX-relevant subset is Tasks 1's three tiers.

## Appendix — primary code reviewed
`frontend/src/components/ScorecardPage.tsx` (811 lines), `PageHeader.tsx`, `landing/HeroEntrance.tsx`, `lib/api.ts` (ScorecardResponse/ZoneDefinition), `lib/types.ts` (PropertySummary/IncentivesSummary/RegulatorySummary), `frontend/CLAUDE.md`, memory + `claude-context` design/coherence docs.
