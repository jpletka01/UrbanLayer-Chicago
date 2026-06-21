# Scorecard Chat Grounding (bypass)

**Completed**: 2026-06-21
**Status**: Shipped to production & browser-verified live (`main` @ `43ad976`)

## What Was Built

When a chat turn is launched from a Scorecard for a specific parcel, the turn now
carries the parcel's **already-resolved facts** (`scorecard_context`) so the
answerer reads them directly instead of re-fetching them. The Scorecard already
assembled a full `ContextObject`; the chat path substitutes those sub-objects for
live retrieval (bypass) and the synthesizer — which already serializes
`ContextObject` — reads them with no change. The "Ask about this property" entry
+ dynamic, flag-aware prompt-starters make the grounded path the obvious one.

## The central design question (per surface): augment retrieval vs. bypass it

Two candidate surfaces were analyzed (Scorecard + Discovery). This shipped the
Scorecard track only.

- **Scorecard = BYPASS for the resolved-fact layer; AUGMENT for everything else.**
  The facts behind "what can I build / explain zoning / what incentives / how do
  comps look" are *already resolved* in `data.context`. Re-running router→retrieve
  to rebuild them is redundant (~2 s) and reintroduces the neighbor-parcel drift
  `_apply_parcel_hint` exists to fight. So those questions read the shipped
  grounding (no fetch). But a Scorecard visitor can still ask a **code** question
  (needs `vector_search`) or a **neighborhood-activity** question (crime/311, not
  shipped) — those must still retrieve. Net: the router still runs every turn (it
  owns sources/intent); the only change is *skip the sub-retrievals the grounding
  already covers*. Page context never drives the router — the seam is respected.
- **Discovery = AUGMENT, but the discovery engine, NOT the chat router** (deferred,
  not built). Refinement ("narrow to vacant lots") should route through Discovery's
  own `compile_text`→CQS pipeline, not the RAG `RetrievalPlan`. Mapping CQS onto
  the RAG router would break both patterns. See "Deferred" below.

## Implementation

**Backend (Checkpoint A, `492ec7a`)**
- `ScorecardContext` model (selective): `parcel_zoning`, `zone_definition`,
  `property`, `regulatory`, `incentives`, `comparables` (+ identity). Deliberately
  **excludes** crime/311/permits/violations/businesses/vacant/food/`code_chunks`/
  analytics/full-demographics — those are stale-prone or cheaply re-fetched when a
  question actually needs them. Added `scorecard_context` to `ChatRequest`.
- Two optional `ContextObject` fields (`comparables`, `zone_definition`) — they have
  no other home and the synthesizer serializes the whole object, so grounding
  reaches the LLM **with zero synthesizer change**.
- `_scorecard_grounding_applies(plan, sc)` gate: grounding present **AND**
  `plan.location.pin == sc.pin` **AND** property-scoped (`{property,regulatory,
  incentives}_domain` in sources, or `workflow_hint == site_due_diligence`).
- `_retrieve(plan, scorecard_context)`: when the gate passes, skip the
  property/regulatory/incentives/`zoning_lookup`/`aro` fetches, then **post-hoc
  overwrite** those sub-objects on the assembled `ContextObject` + set
  comparables/zone_definition.

**Frontend (Checkpoints B + C, `a47663b` / `648a073`)**
- `SelectedParcelContext` retains the full `ScorecardResponse` (identity-paired).
- `buildScorecardContext()` lifts the selective set off the held response (sales
  trimmed to 8); returns null without an authoritative pin.
- `chatStream`/`useChat.sendMessage` thread `scorecardContext` → `body.scorecard_context`.
- Grounded empty-state: dynamic, flag-aware starters; "Ask about this property →"
  entry → `/?pin=` (no auto-send) lands on the grounded starters.

## Key Decisions

1. **Post-hoc overwrite, not feed-through-assembler.** `assemble_context` builds
   `ZoningSummary` from a raw `zoning_info` *dict*, whereas the Scorecard already
   holds the post-assembly `ZoningSummary`. Feeding it back through the assembler
   would be a shape mismatch. Overwriting after assembly is type-correct (same
   shapes) and preserves the assembler's tax-class enrichment (the Scorecard ran
   the same assembler, so `sc.incentives` already carries it).
2. **Skip set verified lossless on real data.** Beyond Phase-2's
   property/regulatory/incentives, we also skip `zoning_lookup` and `aro`:
   `lookup_zoning` returns exactly the 3 fields the assembler maps into
   `parcel_zoning` (= `sc.parcel_zoning`); `aro_housing` feeds *only*
   `regulatory.aro_housing` (= `sc.regulatory`, which the Scorecard already built).
   Live diff confirmed grounded ≥ ungrounded — in fact **richer**: `comparables`
   and `zone_definition` are present only when grounded (the chat path never
   fetches them). Faster too (retrieval 4.8 s vs 6.0 s; total 32 s vs 47 s).
3. **413 is a non-issue.** `scorecard_context` is ~6–8 KB (vs the 16 MB nginx
   cap). The original 413 was *history accumulation* (10 turns × multi-blob), a
   different scale. It's a request param, never written to stored history.
4. **Scope: grounding rides the explicit `parcel_pin` handoff ONLY** (canned
   InvestigateButtons + starters), never free-typed composer follow-ups —
   deliberate, to avoid a drift surface (see lesson below). The multi-turn
   *typed*-follow-up win is the deferred pinned-conversation track.
5. **Starter trigger narrowed to TIF/OZ/EZ.** ARO/TOD/grants are near-universal in
   real data (ARO true on 8/8 parcels probed), so including them would fire the
   incentives starter on ~every parcel and make the neighborhood fallback dead code.

## The router-seam lesson (carry into the deferred track)

Three bugs, **one root cause**: *the router decides intent from raw text BEFORE the
pin can anchor anything, and `_apply_parcel_hint` only rescues address-typed plans.*
Any design that relies on the pin to anchor a typed question is fragile at this seam.
1. **Drift hazard** (Checkpoint B) — blanket-shipping the held pin on every composer
   turn would let a follow-up naming a *different* address get force-anchored to the
   old parcel; the backend gate can't catch it (the hint already set
   `plan.location.pin`). → scoped to explicit handoffs.
2. **Deictic starters → clarification** (live finding) — "What can I build on **this
   lot**?" has no address → router returns `clarification_needed` (short-circuits
   before retrieval) and the pin never rescues it. → embed the address in the sent
   question (mirrors InvestigateButton: `"<question> — <address>"`).
3. **Bare `?pin=` → splash** (live browser finding) — the no-auto-send entry left
   `active = messages || streaming || composing` false, so the splash rendered, not
   the workspace. → `setComposing(true)` in the bare-pin effect. **Invisible to
   API + unit tests; only a real browser click-through caught it.**

The deferred conversation-pinned-to-parcel model must address intent/anchoring **at
the router level** (resolve a typed same-parcel follow-up to the held parcel; clear
the pin on a detected location switch), not just ship grounding downstream.

## Verification

- Unit: `test_chat_scorecard_grounding.py` (gate + skip/merge + augment-path
  survival of neighborhood/activity feeds). Backend 261 unit pass; 65 FE + 14
  i18n-parity pass.
- Live (local + prod) via a Playwright click-through: cold deep-link `/?pin=` →
  grounded empty state → click starter → grounded RM-5 answer (FAR/height from
  `zone_definition`, no clarification); no property-starter leak on bare `/`.
- Deploy verified by serving the live prod bundle, not just git HEAD.

## Files Changed

- Backend: `models.py` (ScorecardContext, 2 ContextObject fields, moved
  ComparableSale/ComparablesSummary above ContextObject), `main.py`
  (`_scorecard_grounding_applies`, `_retrieve` skip+merge),
  `tests/test_chat_scorecard_grounding.py`.
- Frontend: `contexts/SelectedParcelContext.tsx`, `lib/scorecardContext.ts` (new),
  `lib/api.ts`, `lib/useChat.ts`, `lib/types.ts`, `App.tsx`,
  `components/ChatInterface.tsx`, `components/ScorecardPage.tsx`, locales en/es
  (`chat.propertyStarters.*`, `scorecard.askAboutProperty`).

## Deferred (next tracks)

1. **Conversation-pinned-to-parcel model** — the headline multi-turn win: same-parcel
   *typed* follow-ups also bypass. Needs router-level anchoring + location-switch
   detection that clears the pin. (See router-seam lesson.)
2. **Discovery refine-grammar assistant** — via Discovery's own `compile_text`→CQS
   engine, not the chat router. Read `compile_text.py` to scope NL→filter coverage
   first.

## Known Limitation

Has-pin-but-no-address parcels (rare GIS address-backfill quirk, e.g. some PDs): the
address-embed fix has nothing to embed, so the starter stays deictic and may hit the
clarification dead-end. Most pinned parcels have addresses. Candidate follow-up:
suppress grounded starters (show generic) when `address` is null.
