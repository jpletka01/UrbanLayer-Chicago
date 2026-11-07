# Front-end rewrite: engineering decisions

The rewrite of the front end described in `guides/frontend-redesign-vision.md` (the vision brief). Format: see `README.md` in this folder. The wireframes and the visual-system draft are private design pages in the owner's account; the decisions below restate what a reader of the code needs.

---

## Item 73: SnowUI is the visual base; three other kits fill single jobs (2026-11-07)

**Decision: the new front end takes its look from the SnowUI dashboard kit ("Dashboard UI Kit - Dashboard, Free Admin Dashboard", by ByeWind, Figma Community, CC BY 4.0).** It sets the visual language: quiet neutral surfaces separated by fill rather than borders or shadows, 16px card radius, tiles with one key figure, wide chart blocks, and one highlighted bar among gray ones. It is a reference for the look, not a component library: SnowUI ships Figma drawings, and the components are built in this repo's React + Tailwind stack. Three other files each fill one job:

| Job | File (Figma Community, all CC BY 4.0) | What we take |
|---|---|---|
| Phone sheets (map Key and Layers, filters, the sign-in card) | Bottom Sheet Library: 11 Variants | Sheet shapes and states; its magenta is replaced by our colors |
| Side panel behavior | Minimalist sidebar component (a Figma Make file, so readable React source) | The icon strip plus the panel that collapses into it, and the collapse motion. Rebuilt, not copied: the source is dark-only with hard-coded colors, a fixed 800px height and no keyboard support |
| Side panel in both themes | Sidebars (Full Interactive) | A light and dark check for the side panel |

Icons stay Lucide (`lucide-react` is already a dependency); the 1,800-icon Figma pack was not adopted.

**Alternatives considered** (all 11 files were opened and compared against the wireframes' five patterns: the side panel, a full-width tab bar, tiles with small charts, centered frosted cards, phone bottom sheets):
- **DashStack free admin kit.** Capable, with two light and two dark styles, but it reads as a stock admin template (blue menu, pastel icon badges, busy layout). That is close to the problem a builder reported on the current site: nothing said what mattered.
- **One whole-app template.** None of the candidates covers the Profile's full-width tab bar or a map; the tab bar is designed by scaling up SnowUI's in-card tabs, and the map follows the brief's map rules (reference: the Cities: Skylines 2 OSM toolkit map, MIT).
- **Find Your Dream Home website template.** Built for home buyers, not builders, and its beige palette is close to the earth tones the owner already rejected for the site.
- **Glass-effect sidebar and frosted-glass card files.** Decorative glass over bright wallpaper; the one frosted card the design needs is a CSS `backdrop-filter`.
- **Charts kit (line, bar, pie, donut, radar, scatter, bubble, radial).** Kept as a styling reference for bar, line and scatter; SnowUI's charts are cleaner and consistent with the base. Pie, donut, radar and bubble have no slot in the wireframes.
- **Rendering real 3D with variables.** A Figma technique; the product's 3D is Mapbox extrusions on the real map.

**Why (evidence).** Read through the Figma tools (until the Starter plan's monthly cap on those calls) and then in the Figma desktop app, 2026-11-07. SnowUI's free file has light, dark and phone versions of its dashboard, but no saved color variables, so colors are taken from its screens and redrawn as our own tokens.

**Licensing.** All four adopted files are CC BY 4.0: the public About page must carry a credits line naming each file and author. This is a build task for the rewrite, not done yet.

**Revisit if:**
- Detailed mockups of the Profile Overview or Discovery show SnowUI's density does not fit the data (it was drawn for a sales dashboard).
- The owner moves to a paid Figma plan and wants components pulled straight into code (Code Connect); SnowUI's paid version has variables and components that would then matter.

**Numbers.** None measured; this item changes no code.
- **Not measured:** how builders read the new look. That waits for the clickable prototype test in the brief's plan (two or three builders on a real task).

---

## Item 74: the visual system: SnowUI's frame, the Coastal chart palette, black for this lot (2026-11-07)

**Decision: the new front end uses SnowUI's own colors for everything except charts.** Sampled from the SnowUI file in Figma and from the owner's screenshots of its light, dark and phone screens:

| Role | Light | Dark |
|---|---|---|
| Page | `#FFFFFF` | `#1C1C1C` |
| Blocks (chart and table panels) | `#F7F9FB` | `#282828` |
| Stat cards, alternating | `#E3F5FF`, `#E5ECF6` | same, with dark text |
| Text, the selected tab, this lot | Black `#1C1C1C` (SnowUI "Primary"), with 80/40/20/10/5% steps | White, same steps |
| Main button | Black, white label | Lavender `#C6C7F8`, dark label |
| Status | SnowUI's pills: pale fill, colored word (Recorded, In progress, Introduced, Open, Not a sale) | Same, tinted for dark |
| The analyst | The question box's lavender-to-blue edge and Send button (from SnowUI's chat screen), the only place that gradient appears | Same |
| Paid | One small black "Pro" tag on the Deep analysis tab | White tag |

Type is Inter (14px body, 12px labels, 18px answer sentence, 24px figures with tabular numbers); blocks have a 16px radius and 24px padding with 28px gaps; icons stay Lucide at 1.5 stroke.

**Decision: charts use the "Coastal" palette, taken from a reference palette the owner supplied, in this order:** Sapphire `#72B0AB`, Ballet Slipper `#FE9179`, Spruce `#355E58`, Pistachio `#B89D47`, Bubblegum `#FDC1B4`. Sapphire is the ordinary bar and context color; this lot (or the value the user chose) is black, white in dark mode. Charts with one to three series use the first three only.

**Decision: brief rule 9 ("color has jobs") is met partly by form.** "This property" is black in charts and a black outline with a white edge on maps; "you can click this" is the main button plus the shape of controls (selected tab, underlined links, hover fill), because SnowUI has no separate link color; "this costs money" is the Pro tag; status is the pills, always a word, never color alone.

**Decision: the side panel drops recent lots and chat history.** It is Search, Discovery, Saved, and Chat with a small menu for past chats. The owner's reasons: recent lots would push the chats out of view, neither list could be cleared, and chat gets its own history panel on the chat page. The analyst stays an on-demand drawer opened from the Ask icon in the top bar; SnowUI's permanent right-hand panel was not adopted (the brief already rules out a permanent chat or sources panel).

**Alternatives considered** (all shown to the owner on the private visual-system page, drafts 1-7):
- **A role-color scheme of our own on SnowUI's layout** (blue actions, orange lot, violet analyst). Rejected by the owner: it did not look like SnowUI.
- **SnowUI's own pastel chart colors.** Rejected: too similar to each other (the rent slider's two bands were hard to tell apart).
- **A high-saturation validated palette** (blue, orange, aqua, yellow...). Rejected: the colors did not harmonize.
- **Known palettes:** Tableau 10, Observable 10, Okabe-Ito. Superseded when the owner supplied reference palettes.
- **Two other palettes from the references:** "Teal and coral" (`#257C93`, `#EF5835`, `#E29F17`, ...) and "Dusk" (`#8F9AC9`, `#165B6D`, `#E29F17`, ...). Both pass the color-blind check more cleanly; the owner chose Coastal.

**Why (evidence).** Every palette was run through the data-viz palette validator (OKLab ΔE, Machado 2009 color-blind simulation), light surface `#F7F9FB` and dark surface `#282828`. Coastal's first three on every pair: normal vision ΔE 20.5 (pass, floor 15); color-blind ΔE 6.8 for Sapphire against Ballet Slipper (protan), in the 6-8 band that is acceptable only with secondary encoding. Its five-color order passes on neighbors for normal vision (worst ΔE 18.5).

**Rules that follow from Coastal's color-blind margin:**
- Every chart that uses both Sapphire and Ballet Slipper labels them directly (names beside the marks or a legend with values), never color alone.
- Scatter plots and maps use at most Sapphire, Spruce and black, or carry shape or labels as well.
- Spruce is weak on the dark background; keep it to third-series use.

**Still provisional:** the zoning colors (pastel family colors, darker as density rises; the five pass the color-blind check on every pair in light): residential lavender `#CDB7F6`, business and commercial `#ED8A8E`, manufacturing gold `#B99C3A`, downtown `#63A8CF`, parks `#A7E2B2`, transport mid gray `#8F959C`. The owner swapped residential and manufacturing (2026-11-07) and flagged the first transport gray, `#D5D8DD`, as too close to the palest steps: measured OKLab ΔE 2.8-6.2 against them, versus 23-26 for `#8F959C`. They will be settled with the map mockups.

**Revisit if:**
- The clickable prototype shows builders missing what is clickable without a link color.
- A color-blind tester confuses Sapphire and Ballet Slipper even with labels; Teal and coral is the drop-in replacement.
- Detailed mockups need more than three chart colors often.

**Numbers.** None measured on the product; this item changes no code. The validator figures above are from 2026-11-07. Reproduce: `node <dataviz skill>/scripts/validate_palette.js "#72B0AB,#FE9179,#355E58" --mode light --surface "#F7F9FB" --pairs all` (and `--mode dark --surface "#282828"`).
- **Not measured:** how builders read the look (waits for the prototype test); contrast of every text and pill pairing (to check when the tokens are built).

---

## Item 75: how the rewrite is built: a preview boundary, a tested prototype first, gated map and data tracks (2026-11-07)

The implementation plan itself is local (`plans/2026-11-07_frontend-implementation-plan.md`, revision 3, approved by the owner after two outside reviews). This item records the decisions a reader of the code needs.

**Decision: the new UI is built inside the existing app, behind a preview boundary, route by route.** A single `UiVersionProvider` and one **readiness registry** decide which new routes exist; the registry also drives the side panel, analytics names and preview access, so "is this route ready?" has one answer. `?ui=next` / `?ui=old` set a versioned flag (localStorage, failures tolerated); a visible "Preview" badge exits in one click; routes that aren't ready fall back to the old page; a build-time environment switch turns preview off; preview-only pages are `noindex`; analytics and Sentry are tagged with the UI version. A destination appears in the side panel only once its route exists (Saved stays hidden until it is built). *Alternatives:* a separate site or subdomain (new hosting, no real data path), one switch per route (several sources of truth), building on a long-lived branch (a big-bang merge).

**Decision: old and new must not leak into each other.** Shared primitives (`ui/Button`, `StatusLabel`, `ConfidenceState`, `ToolTray`, `Toggletip`) keep their current default look; the new UI changes them only through `.ui-next` CSS-variable overrides or an explicit `uiVersion="next"` variant. A test renders old and new surfaces together and fails if new tokens reach old pages. With preview off, production must look unchanged; this is a Phase 1 acceptance criterion.

**Decision: stack.** Keep React 19, Vite 8, TypeScript, react-router 7, Tailwind v3, i18next, lucide-react, Mapbox GL and deck.gl. Components are rebuilt from the SnowUI look rather than imported from template code (SnowUI is drawings; the Make file is dark-only demo code on Tailwind v4). Radix supplies behavior only for Dialog/Sheet, Tabs, DropdownMenu and Popover. Charts are our own SVG shapes, each added when a page needs it and shared from its second use. If the prototype misses the SnowUI look, the fallbacks are SnowUI's paid kit, then the DashStack kit, then shadcn/ui restyled with our tokens.

**Decision: standards for every new screen.**
- *Icons beside words, not instead of them:* icon + short visible label + figure + unit, with definitions, sources, method and caveats in tooltips. Icon-only buttons only for the established tools (Ask, Sources, Export, Dates, Code, Explain). One icon registry gives each concept one Lucide icon everywhere. An outside review pointed out that icon-only facts would confuse exactly the first-time builders the redesign is for.
- *Reuse:* a component becomes shared on its second use; a test flags unauthorized colors in components (token files and functional map and chart palettes are exempt).
- *Light and dark* from day one; *Spanish* (Mexican, formal usted) in the same PR with a glossary of fixed terms and a native read-through before the final flip; *accessibility* (keyboard paths, focus restoration, reduced motion, contrast, axe).
- *One source for the design rules:* the two `page-design-rules` skill copies (`.agents/` and `.claude/`) differ today; `claude-context/guides/page-design.md` becomes canonical with a parity check, and the rules are rewritten after the builder test, not before.

**Decision: order of work.** (1) A thin prototype behind preview: the frame, Profile Overview and Build on today's `/api/scorecard`, today's parcel map with a cleaned base style, the Ask drawer on the existing chat path, one Discovery flow. (2) A latency spike: p50/p95 per retrieval task, cold and warm, on the four budget parcels; only catastrophic critical-path fixes or honest progressive loading before the test. (3) A builder test. (4) The Profile response split, designed from the measurements. (5) Map tracks M1–M3. (6) The remaining Profile tabs and Discovery, route by route. (7) Data tracks M4–M6. (8) Full chat and landing. (9) Commercial epics (quotas, billing and entitlements, identity, Saved), each with its own plan and threat model. (10) Restyles, the Spanish read-through, a stabilization window, then deletion of the old UI. *Why the prototype comes before the map:* the brief puts a tested prototype before the build, and building the map platform first would prove the engineering before proving that builders understand the workflow.

**Success criteria (written before the test).** The builder test runs two cases, a prewarmed parcel (workflow) and a fresh parcel the builder picks (the real first visit). It passes if at least two of three builders can, without coaching: find the units or floor area allowed; name the main blocker or uncertainty; open the supporting evidence; ask a follow-up without losing the Profile; return to Discovery or open another lot; explain the allowed-vs-built bars in their own words. Task time, hesitations, wrong conclusions and unexplained labels are recorded. Latency targets are proposed as first useful content under 3 s warm and 6 s cold, to be confirmed from the spike.

**Decision: map rules.**
- *M1, one persistent map per page,* outside the tab panels, receiving layer and camera settings from the active tab; tab content stays mounted or is restored without remounting the map; theme swaps keep sources, feature state, camera and deck.gl layers; camera moves respect reduced motion and don't take focus. This is also the fix for "WebGL context was lost".
- *M3, official zoning geometry is preserved.* Streets stay visible by drawing them above zoning (or with a road mask), not by clipping zoning to blocks, which could draw a cleaner but wrong map. Any simplification is checked against the source and may not change the district of any parcel in the validation panel; a boundary test compares source, simplified and rendered geometry at boundary parcels.
- *M5, land in use* is modeled as separate fields (observed use; infrastructure or public designation; utilization from the capacity contract), each with source, vintage, confidence and conflict state. "Underused" is a derived judgment, not a land use. High-confidence infrastructure is hidden by default in Discovery with a visible count and a Show option; nothing is permanently excluded. OpenStreetMap-derived inputs stay separate and traceable, with attribution and a licensing review before publication.
- *M6, 3D* starts with a coverage and performance spike; a lot's shape is an "illustrative zoning mass" listing the rules included and not checked, never a "largest allowed" claim, and is not drawn when parcel identity or geometry is approximate. The landing page uses a static image of it.
- *Data tracks are gated:* failing a threshold (capacity: zero false "underused" on the labeled panel; land use: per-class precision, conflict rate, coverage; 3D: footprint coverage, measured vs story-derived heights, geometry failures, payload) blocks display.

**Decision: working rules.** Branches and PRs may be opened whenever the local gates are green; nothing merges to `main` (which deploys) without green CI, verification and the owner's go. CI runs the build, vitest (including new pages rendered from typed fixtures, component axe checks and the isolation test), lint and backend tests; the mobile matrix, page budgets, Playwright axe and a keyboard walkthrough are required local release gates because they need a running backend. No production model calls in automated development or tests; human prototype testing may use a small, recorded production budget (amount to be approved), with preview conversations tagged by UI version. After the last route flips, `?ui=old` stays available until a release cycle has passed and every route has been exercised on production.

**Revisit if:**
- The builder test fails the criteria: revise the structure before building more pages.
- The latency spike shows the slow work sits inside the Overview's own dependencies: the response split alone won't meet the target.
- Our components miss the SnowUI look at the Phase 1 review: switch to a fallback above.

**Numbers.** None measured yet; this item changes no code.
- **Not measured:** per-task Profile latency (Phase 2 measures it); map payload and frame rate (M1–M3 gates).

---

## Item 76: Phase 1, the thin prototype behind `?ui=next` (2026-11-07)

**Decision: the preview boundary is one provider and one data-only registry, and the new pages are a lazy chunk.** `frontend/src/ui-next/UiVersionProvider.tsx` resolves the version (kill switch `VITE_UI_PREVIEW=off` → `?ui=` → the stored flag `urbanlayer-ui-preview:v1` → old), removes `?ui=` from the address bar with a replace, and tags Sentry (`ui_version`) and analytics. `readiness.ts` is the registry: `profile` and `discovery` are `ready`, `chat` is `old` (the side panel links to today's chat page), `saved` is `hidden`. `VersionedRoute` renders the new page only for a ready entry with the preview on, adds `noindex` while it is on screen, and loads it from `pages.ts` (React.lazy). The Preview badge shows on every page while the preview is on, today's pages included, with one-click exit. *Alternatives:* putting the registry in `main.tsx` as JSX (the side panel in the lazy chunk would then import every old page), a per-route flag (several sources of truth), tagging every production event with `ui_version: "old"` (changes today's payloads for no reader; absence means old).

**Decision: the new look reaches shared components only through scoped variables.** `ui-next.css` defines the SnowUI frame and Coastal tokens (`--nx-*`, Tailwind `nx-*`) and re-points today's role variables (`--text-secondary`, `--status-*`, `--action-primary`, ...) inside `.ui-next` only, so `StatusLabel`, `ConfidenceState`, `Toggletip`, `AddressInput` and `MessageBubble` are reused unchanged. The file sets no `background`/`color`/`font` on `.ui-next` itself (it loads after Tailwind and would beat utilities on the same element), and the global focus ring is `:where(.ui-next) :focus-visible` so a component's own focus utility can replace it. Portaled menus and dialogs (Radix) wrap their content in their own `.ui-next` div. Stat cards stay pale in dark mode (Item 74), so labels on them use a `.nx-on-card` light-role scope.

**Decision: AA contrast over the sampled SnowUI values, where they fail.** Secondary text is ink at 64% in light (SnowUI's 40% is 2.5:1 on white) and 60% in dark; light pill words are darker than SnowUI's (its `#8A8CD9` on `#EDEEFC` is 2.7:1); the analyst's Send keeps the gradient with a dark label (white is 2.5:1). `tokens.contrast.test.ts` reads the CSS file and checks every text and pill pairing in both themes; Playwright axe (contrast included) passes on every preview route in both themes.

**Decision: the Profile prototype reads today's `/api/scorecard` through a pure model.** `profile/profileModel.ts` derives allowed vs built, the deciding limit, pending rezonings, rule chips and the Overview tiles from the response, the verdict's signals and the backend's provenance states; nothing the backend decided is recomputed. The deciding limit is the most used-up of the limits that can be compared; height is never compared (the records give stories, not feet), and a missing built figure keeps its slot, hatched, with "built: not on record". The Overview's tiles are Item 77.

**Decision: a Clerk filing's stage comes from the Clerk's numbered state, never its words.** First version matched words and read "3-Council Introduction" as "Council vote" (caught on the real 1601 N Milwaukee response, 2026-11-07). `stageOf` now maps the states in `backend/retrieval/clerk.py` (2/3 introduced, 4 committee, 5 council, 90-Final + a passed sub-status in effect); anything else shows the Clerk's words with no tracker.

**Decision: the Ask drawer shares the dock's chat path.** `lib/useParcelChat.ts` is the dock's grounding, address-carrying ask and new-tab escalation, extracted on its second use; `MiniChatDock` now calls it (its tests pass unchanged). The drawer owns no chat state: the page holds it, so the conversation survives closing the drawer and switching tabs. Tests mock `useChat`; no production model call was made in development.

**Decision: `ParcelMap` gets `look="next"`, not a fork.** The lot is a black outline over a white edge (white over dark on dark streets), comps are Sapphire, the satellite/streets switch sits beside the zoom buttons, and `useMapboxOverlay({ quiet: true })` applies `lib/mapQuietStyle.ts` (hides nature/water/airport/sub-area/shield labels as well as POIs, street names from zoom 15). Found on the way and fixed for both looks: re-applying the style the map already had brought the hidden POI labels back without a `style.load`; `ParcelMap` now calls `setStyle` only on a real change.

**Alternatives considered:** a separate `next.urbanlayerchicago.com` (Item 75), shadcn/ui now (Item 75's third fallback; Radix behavior alone was enough), Radix for the drawer (a plain non-modal region with managed focus is simpler and lets the page stay usable beside it).

**Revisit if:** the builder test shows the deciding-limit rule confuses ("most used-up" is a reading aid, not a feasibility claim); `old`-status destinations in the side panel feel like leaving the app (then Chat waits until its route is built).

**Numbers** (measured 2026-11-07, local build of this branch vs `origin/main` 8b65246):
- First load (index.html's scripts + modulepreloads, gzip): 1,319,856 → 1,334,171 bytes (+14.3 KB, +1.1%); CSS 18,096 → 20,277 bytes gzip. Radix is not in the first-load chunks; the new pages are `ProfileNextPage`/`DiscoveryNextPage` chunks. *Reproduce:* `npm run build`, then gzip-sum the assets named in `dist/index.html`.
- Tests: vitest 986 → 1,041 (new: isolation, preview switch, contrast, tabs, drawer, frame, Discovery, map); lint 66 warnings before and after (cap 67).
- Playwright axe (WCAG 2 A/AA): 0 violations on the preview search, Profile (Overview and Build) and Discovery, light and dark. *Reproduce:* `npx playwright test e2e/ui-next.spec.ts --project="Pixel 3"` with the dev stack up.
- **Not measured:** latency (Phase 2), how builders read it (Phase 3), the Spanish by a native reader.

---

## Item 77: the Overview has one tile per tab (2026-11-07)

**Decision: the Overview shows one tile per Profile tab, each with that tab's key figure, a small visual and at most one warning.** In Phase 1: **Build**, units allowed vs built; **Money**, property tax; **Neighborhood**, walk score; **History**, last market sale. The zoning district is in the answer sentence and the map band, not in a tile. No Deep analysis tile in Phase 1 (the tab isn't built). Each tile names its tab; a tile opens its tab once that tab exists (only Build in Phase 1). Confirmed by the owner through the planning session, 2026-11-07; the figures can still change at the Phase 1 review.

**Why.** The brief's approved Overview section already said "one tile per tab"; the open question "units, zoning, tax, price per sq ft?" (carried into the plan as "four provisional tiles") was a leftover that contradicted it, and is removed from the brief. A prototype first built the four (Item 76's first commit); this replaces it.

**Decision: "last market sale" is a conservative client-side test until the response says it.** Today's `sales_history` is the parcel's unfiltered CCAO rows (date, price, deed type). A sale counts as a market sale only at $10,000 or more with a Warranty or Trustee deed, the same lines the County's own `sale_filter_less_than_10k` and `sale_filter_deed_type` draw for comparables (`backend/retrieval/property/sales.py`); an unknown deed type does not count. A newer non-market transfer is the tile's one warning ("A 2022 transfer isn't counted as a sale"); a parcel with only transfers says so instead of showing a price (brief rule 4). The walk score is labeled as a private company's index (its provenance entry says the same).

**Alternatives:** the four provisional tiles (contradicted the approved rule); price per sq ft from nearby sales for Money (a market figure, not this lot's cost; it belongs inside Money); assessed value for Money (property tax is what a builder pays).

**Revisit if:** the Phase 4 response split carries an arm's-length flag per sale (then use it and drop the client test); the builder test shows a tile nobody reads; a fifth or sixth tab is built (its tile joins; a seventh tab means two should merge, per the brief).

**Numbers:** none measured on users. The market-sale rule is pinned by `profileModel.test.ts` (a $1 transfer, a quit claim and an unknown deed never show as the price).
