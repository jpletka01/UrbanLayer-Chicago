# Chat Usability Arc (mobile + i18n)

**Completed**: 2026-07-03
**Status**: Shipped to production (`main` @ `7f128f0`, 8 commits `deffe1d..7f128f0`; CI test+deploy green; verified against the served bundle `index-CEzESkhz.js` — per-phase markers incl. es strings, cluster layers, density CSS, CHRS starter; live `/api/scorecard` serves traffic)

## What Was Built

Seven usability fixes for the chat workspace, worst-case-first on mobile and Spanish: the nav
stopped overflowing in es (conversation actions moved out of the chrome), the mobile map became
legible and touch-first, per-message context chips made the invisible per-message data model
visible, Tier-2 facts (CHRS/energy/traffic) entered chat grounding with notable-only starter
chips, the mobile sheet's data cards read at a comfortable size, and the 10-message limit
announces itself before it hits. Plus two pre-existing bugs found during verification: a flaky
race where the splash swallowed streaming answers, and the mobile nav painting icons over the
wordmark.

## Implementation Details

**Phase 0 — bubble jitter** (`deffe1d`). `ActivityStatus` rendered inside the assistant bubble's
shrink-to-fit `max-w-[85%]` wrapper, so the 1.2s activity-label cycle resized the bubble every
tick. Moved to a sibling of the flex row; bubble sizes to its own content. Verified by sampling
`getBoundingClientRect().width` at 250ms through a live stream: constant 162px across the
activity phase.

**Phase A — nav declutter** (`e56a72d`). Rule: **icons in chrome, words in menus** (vertical
menus are width-unconstrained → i18n-proof by construction).
- Export/Share → new `ConversationMenu.tsx` (⋯ kebab, UserMenu dropdown pattern; trigger renders
  only when ≥1 row is visible; Export stays reachable for anonymous users — their only way to
  keep work).
- New chat → icon-only `+` (labeled row stays pinned in HistorySidebar).
- Admin → `UserMenu` dropdown row (was `hidden md:flex` — now reachable on mobile).
- Sign-in nudge → short `signInToSaveShort` ("Sign in to save" / "Guardar tu trabajo").
- Workspace omits the self-referential "Ask the analyst" center link (`FloatingNav omitNavKey`).
- Nav badge-dot removed (superseded by Phase C chips).
- CI guard: `PageHeader.nav.test.ts` asserts every nav-chrome string ≤20 chars in every locale.

**Bonus fix 1 — splash swallowed streaming answers** (`2942568`, pre-existing, flaky).
`sendMessage` cleared `composing` before the awaited conversation creation, so
`active = messages.length || streaming || composing` dipped false for ~200ms. AnimatePresence
(`mode="wait"`) began swapping the splash in; when `active` flipped back mid-transition it
dropped the workspace's re-entry — app stranded on the splash at `/c/:id` while the answer
streamed unseen. Bisected against `main` (reproduced there 2/3 → pre-existing, not a branch
regression), diagnosed with temporary state-trace instrumentation (state was healthy —
`active=true, n=2` — while the DOM stayed on splash → rendered-tree bug, not state bug).
Fix: `setComposing(false)` moved to after `sendChat()` (which appends the user message
synchronously), so `active` never dips. 4/6 repro pre-fix on mobile emulation, 0/3 post-fix.

**Phase B — mobile map legibility** (`abab8e7`).
- Mobile: the 5 layer-toggle chips (covering `max-w-[calc(70%-8px)]` of a phone map) + separate
  filter popover collapsed into ONE "Layers"/"Capas" button + popover (layers section on top,
  filter sections gated on `showPoints`). Desktop top-left chips unchanged (extracted to a shared
  `layerChips` JSX var).
- **Cluster dots**: >`DENSE_POINT_THRESHOLD` (300) filtered points below zoom
  `CLUSTER_MAX_ZOOM` (13) render as count-labeled cluster dots (hand-rolled web-mercator grid
  clustering, ~56px cells → Scatterplot + Text layers). ⚠️ **deck.gl aggregation layers
  (HeatmapLayer & co) do NOT render in interleaved MapboxOverlay mode** — verified empirically
  (empty map, no errors); `@deck.gl/aggregation-layers` was added then removed. Applies on both
  surfaces so the encoding is consistent. Zoom tracked via `zoomend` (one rebuild per gesture).
- `pickingRadius` option on `useMapboxOverlay` (14px on touch).
- Tap detail: bottom-docked card on mobile (map stays visible/pannable; empty-map tap dismisses
  via the existing null-pick) instead of a modal over the sheet; desktop keeps the modal.
- `MobileSidebarSheet` peek snap (20vh) shows a one-line summary strip ("1143 crimes · …", tap →
  default height) as an OVERLAY — never replacing content, so the map's GL context survives.

**Bonus fix 2 — mobile nav overlap** (in `abab8e7`, pre-existing). At 390px the right-zone
actions (~240px) + brand text overflowed and PAINTED OVER the wordmark. Invisible to
`scrollWidth` checks (the pill clips internally) — caught only by screenshot. Fix:
`FloatingNav compactBrand` (wordmark `hidden md:inline`) + the community-area crumb
`hidden md:flex` (the sheet header already shows it on mobile).

**Phase C — per-message context chips** (`d6322ab`). `ContextChipStrip` under each completed
assistant answer: `Map · N` / `Data · N` / `Sources · N` (chip-button idiom), opening the side
panel (desktop) / bottom sheet (mobile) on that tab **scoped to that message's turn** (reuses
`handleMessageClick`'s turn-loading; `"map"` falls back to the Data tab on desktop — `map` is a
mobile-sheet-only SidebarView). Rendered via a new `MessageBubble footer` slot; suppressed while
streaming and on shared read-only views. `countDataCategories` moved from App.tsx to
`lib/contextSummary.ts`. Makes the per-message context model visible; replaces the nav badge dot.

**Phase D — Tier-2 grounding + notable-only starters** (`2c5a483`). CHRS + energy already rode
grounding via `property.*`; traffic never shipped and no prompt rule scoped any of them.
- `ScorecardContext.traffic` (backend + `types.ts`), lifted in `buildScorecardContext` `base`
  (lat/lon-scoped → ships in BOTH tiers incl. pin-null).
- Backend graft (main.py, next to verdict/address_violations): into `ctx.neighborhood.traffic`,
  creating the `NeighborhoodSummary` shell when the turn skipped the neighborhood orchestrator;
  never overwrites a fresher fetched row. Serializes automatically (synthesizer dumps the whole
  ContextObject).
- prompts.py rule 27: `property.flags` (CHRS) + `property.energy` named THIS-PARCEEL; new
  NEAREST-STREET scope for `neighborhood.traffic` ("about N vehicles/day on <road>", never the
  parcel, never the area).
- Starters: pure `propertyStarterKeys()` (lib/scorecardContext.ts) — priority-ordered
  `build, zoning, [chrs], [comparables], [traffic ≥15k ADT], [incentives], neighborhood`,
  capped at 4. CHRS fires on orange/red only (demolition-permit review = consequence-laden);
  traffic on `HEAVY_TRAFFIC_ADT` (15000) — **first-guess calibration, revisit with usage**.
- Verified live: 2648 W Crystal St (CHRS orange) → chip + answer citing the 90-day demolition
  review; 1601 N Milwaukee (Noel State Bank — genuinely CHRS orange) ships 11.5k ADT in the
  payload with no traffic chip (below threshold).

**Phase E — mobile sheet reading density** (`d2e7b43`). `[data-density="comfortable"]` CSS scope
in index.css (the type-axis sibling of the `[data-theme]` island idiom): `.text-micro` → 13px,
`.text-sm` → 15px inside the scope. Applied by `MobileSidebarSheet`'s Data pane wrapper — every
sidebar card inherits it, zero component forks. Desktop rail verified unchanged (micro 11px).
**Deviation from the approved plan** (per-card `density` prop → scoped override): same visual
outcome, ~15 lines instead of a ~200-line 4-card fork; flagged to Jack at ship time.

**Phase F — message-limit counter** (`7f128f0`). `useChat` exports `messagesRemaining`; from 2
remaining a quiet caption above the composer says "N questions left in this chat" + New-chat
link. Removed the vestigial `errorMsg !== "MESSAGE_LIMIT_REACHED"` guard in App.tsx (useChat
sets the translated string, never that literal).

## Key Decisions

- **Icons in chrome, words in menus** — the structural fix for i18n overflow, enforced by a
  20-char CI budget on nav strings rather than pixel tests.
- **Share/Export live with the current conversation (⋯ menu), NOT the history panel** —
  anonymous users have no history panel but need Export (their only way to keep work).
- **Cluster dots over heatmap** — forced by the interleaved-MapboxOverlay limitation, but also
  better UX (counts are legible; density blobs aren't).
- **Chips as a `footer` slot on MessageBubble** — keeps ContextChipStrip dumb and the per-message
  wiring in ChatInterface/App; avoids threading context deeper into MessageBubble.
- **Notable-only starter slots** — the answer to "surface new data without overload": a chip
  appears only when the fact is decision-relevant (CHRS orange/red, ≥15k ADT).
- **Density as a scoped token override** — consistent with how theming already works
  (CSS-var tokens + attribute scopes); trivially swappable for a prop if explicitness wins later.

## Verification / process lessons

- All phases driven end-to-end with Playwright against the local dev stack (mobile = 390×844 +
  `hasTouch`); deploy verified against the SERVED bundle, not server git HEAD.
- Dev rate limit (anon 3/day + 3/hour) is in-memory → `touch backend/rate_limit.py` reloads
  uvicorn (`--reload`) and resets it without killing the server.
- Playwright `networkidle` never fires with Mapbox tiles streaming — use `domcontentloaded` +
  DOM waits. The dev-mode browser counts as anonymous for /chat rate limits.
- `JS=$(curl …); echo "$JS" | grep` false-negatives on big bundles (zsh echo mangles escapes) —
  pipe `curl | grep -qF` directly. Caused a false "deploy not live" reading.
- Bisect-before-fixing paid off: the splash race looked like a branch regression but reproduced
  on `main` (1/2, then 2/3) — evidence, not vibes, decided whose bug it was.

## Files Changed

Frontend: `App.tsx`, `ChatInterface.tsx`, `MessageBubble.tsx`, `MobileSidebarSheet.tsx`,
`FloatingNav.tsx`, `UserMenu.tsx`, `PageHeader.nav.test.ts`, `sidebar/MapView.tsx`, `index.css`,
`lib/{useChat,useMapboxOverlay,scorecardContext,types}.ts`, `lib/scorecardContext.test.ts`,
locales `{en,es}/{common,chat,map,sidebar}.json`; **new**: `ConversationMenu.tsx`,
`ContextChipStrip.tsx`, `lib/contextSummary.ts`.
Backend: `models.py` (ScorecardContext.traffic), `main.py` (graft + NeighborhoodSummary import),
`prompts.py` (rule 27), `tests/test_chat_scorecard_grounding.py` (+2 traffic tests).

## Open tail

- Cluster thresholds (300 pts / z13) and `HEAVY_TRAFFIC_ADT` (15k) are first-guess calibrations.
- Desktop map-legend right-edge clipping (pre-existing, spotted during verification) still open.
- Loading an EMPTY conversation at `/c/:id` renders the splash (edge case, pre-existing; only
  reachable if a conversation is created but its first send never persists).
