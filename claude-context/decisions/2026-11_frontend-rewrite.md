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

**Decision: `ParcelMap` gets `look="next"`, not a fork.** The lot is a black outline over a white edge (white over dark on dark streets), comps are Sapphire, there is no satellite view (Item 78), and `useMapboxOverlay({ quiet: true })` applies `lib/mapQuietStyle.ts` (hides nature/water/airport/sub-area/shield labels as well as POIs, street names from zoom 15). Found on the way and fixed for both looks: re-applying the style the map already had brought the hidden POI labels back without a `style.load`; `ParcelMap` now calls `setStyle` only on a real change.

**Alternatives considered:** a separate `next.urbanlayerchicago.com` (Item 75), shadcn/ui now (Item 75's third fallback; Radix behavior alone was enough), Radix for the drawer (a plain non-modal region with managed focus is simpler and lets the page stay usable beside it).

**Revisit if:** the builder test shows the deciding-limit rule confuses ("most used-up" is a reading aid, not a feasibility claim); `old`-status destinations in the side panel feel like leaving the app (then Chat waits until its route is built).

**Numbers** (measured 2026-11-07, local build of this branch vs `origin/main` 8b65246):
- First load (index.html's scripts + modulepreloads, gzip): 1,319,856 → 1,334,171 bytes (+14.3 KB, +1.1%); CSS 18,096 → 20,277 bytes gzip. Radix is not in the first-load chunks; the new pages are `ProfileNextPage`/`DiscoveryNextPage` chunks. *Reproduce:* `npm run build`, then gzip-sum the assets named in `dist/index.html`.
- Tests: vitest 986 → 1,044 at the end of Phase 1 (new: isolation, preview switch, contrast, tabs, drawer, frame, Discovery, map); lint 66 warnings before and after (cap 67).
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

---

## Item 78: no satellite map in the new UI; one set of docs governs it (2026-11-07)

**Decision: the new UI has no satellite view, anywhere.** The owner's call (2026-11-07): imagery competes with the lot and the data it is meant to show, and the target is the quiet Cities: Skylines-style map (muted land, streets as gaps between blocks, names only zoomed in). `ParcelMap look="next"` opens on the theme's street style (`light-v11` / `dark-v11`) with the quiet base (`lib/mapQuietStyle.ts`) and has no satellite switch; `mapNoSatellite.test.tsx` pins it, and pins today's place map as unchanged (satellite default, with its switch). The full Skylines-style base, zoning palette and On / Dim / Off layers remain map track M1 (Item 75); Phase 1 only removes imagery and noise. The first prototype had followed two brief lines ("opening on satellite", "Overview satellite + this lot"); both are corrected.

**Decision: during the rewrite, the brief and this file govern new UI work; older design docs describe today's live UI only.** Root `CLAUDE.md`, `frontend/CLAUDE.md`, the docs manifest, the `page-design-rules` and `load-urbanlayer-context` skills, and the Bento Pro, `page-design`, `scorecard-dashboard-model` and `frontend-guide` guides now say so at the top, so their orange/violet tokens, components and map choices don't leak into `frontend/src/ui-next/`. The same sweep found the brief still said "zoning clipped to blocks", which Item 75 (M3) had rejected; corrected.

**Alternatives:** satellite as an opt-in layer (rejected by the owner: out entirely); rewriting the old guides now (they still govern the live site until each route flips; banners are enough, and Phase 10 deletes them with the old UI).

**Revisit if:** a builder test task can't be done without imagery (then raise it with the owner; don't add it back silently).

**Numbers:** none measured. Local plan files outside the repo that still mention satellite (`plans/2026-11-01_profile-discovery-redesign-plan.md` and its assets) are pre-rewrite and superseded by the brief.

---

## Item 79: the owner's first look at the prototype (2026-11-07)

Notes from the owner's first walkthrough of the Phase 1 prototype. **Outcome: the owner approved Phase 1 ("thumbs up", 2026-11-07) after the changes below**, with the map's look explicitly left to the map tracks (Item 80).

**Changed now:**
- **Map focus.** A four-arrow icon button at the map's bottom right, just left of the zoom buttons (icon only, the owner's call; "Expand map" / "Close map" as its label and tooltip; the key keeps the top-right corner) makes the map the focus of the screen (a full-window view; "Close map" or Escape returns, focus stays on the toggle). `ParcelMap` now resizes with its own box (a `ResizeObserver` calls `map.resize()`), which also stops the canvas stretching when the Ask drawer narrows the page.
- **Chat is a folder in the side panel**, like a directory: the row opens and closes, "New chat" comes first, then the signed-in visitor's recent chats (anonymous: a sign-in line). Replaces the "Past chats" dropdown, which read oddly in a side panel. The owner pointed to the "Sidebars (Full Interactive)" Figma file (Item 73) as the reference for the panel's finished look; that restyle belongs to Phase 6.
- **Ask uses a chat icon** (`MessageCircleQuestion`, the "ask" icon today's tool tray already uses), not the sparkle.
- **The quiet base hides building footprints, pier/structure shapes and airport shapes** ("the polygons look ugly"); blocks read as plain land between streets. The real Cities: Skylines-style base is still map track M1.

**Carried forward (not Phase 1):**
- **Loading screens.** A cold Profile takes 15–40 s and the current skeleton plus a seconds counter isn't good enough. Phase 2 measures where the time goes and adds honest progressive loading; Phase 4 splits the response.
- **The page feels thin.** With only Overview and Build, the Profile "doesn't stand out." Expected at this scope (Money, Neighborhood, History come in Phase 6), but the builder test (Phase 3) should record whether the Overview alone earns attention, and the Phase 4 contract should make sure the first screen carries enough.

**Numbers:** none measured.

---

## Item 80: the Cities: Skylines map style is a requirement of the rewrite (2026-11-07)

**Decision: every map in the new UI takes the look of the Cities: Skylines 2 OSM toolkit map, and the rewrite is not complete without it.** The owner has asked for this repeatedly (most recently after reviewing the Phase 1 prototype, whose map is Mapbox's stock `light-v11`/`dark-v11` with layers hidden). What the look is made of, from the teardown in `research/15-ui-data-inspiration.md` §2.4:
- a dimmed, desaturated base (theirs: Esri Dark Gray raster at 45% brightness, −25% saturation);
- the map's own vector tiles, where each shape (theirs: OSM buildings; ours: County parcels, buildings and official zoning) is filled and outlined thinly in a color that carries meaning;
- roads drawn by the map itself in a handful of classes with set widths and colors, on top of the fills, so streets read as clean gaps;
- On / Dim / Off per layer, counts in the key, confidence shown in the drawing.

**What follows:**
- **Tuning Mapbox's stock style is not the path.** It can hide layers, not draw the look. The map tracks (M1 base and roads, M2 parcels, M3 zoning, later M5 land in use) build it with our own tiles and style. Discovery's parcel-outline tiles (Item 68) are the first piece.
- **Technology may change.** MapLibre GL (what the reference uses; open source, no per-load billing), our own vector tiles (MBTiles or PMTiles), a custom style document and a different basemap source are all allowed; deck.gl stays if it fits. The choice is made and measured in M1 (payload, frame rate, both themes).
- **Our data, not OpenStreetMap guesses.** The reference labels 76% of Chicago buildings from surrounding land use; we use County and City records (parcels, Assessor class, official zoning) and keep OSM-derived inputs separate and attributed (Item 75, M5).
- **Gate:** no route flips to the new UI by default until its map meets this look in light and dark, reviewed by the owner against the reference. Phase 1's quiet stock base (Items 76, 78) is a placeholder; the building footprints it hides come back as our own styled shapes.

**Timing (owner, 2026-11-07):** the map tracks stay where Item 75 put them, after the builder test (Phase 5). The builder test runs on the Phase 1 placeholder map, and its notes should treat the map's look as known-unfinished.

**Alternatives:** keeping Mapbox's stock styles with more layers hidden (cannot reach the look; the owner rejected it); a satellite base (rejected, Item 78).

**Revisit if:** M1's measurements show the chosen stack can't hold the first-view payload or frame rate on a phone; then change the stack, not the look.

**Numbers:** none measured yet; M1 records payload and frame rate before and after.

---

## Item 81: Phase 2, where a cold Profile's time goes (2026-11-07)

**Status: measured; one defect fixed; the progressive loading below was approved by the owner on 2026-11-07 and built (Item 82)** (the phase prompt: propose before building beyond catastrophic fixes).

**Decision: measure with a request-scoped timing collector, not a new code path.** `backend/timing.py` opens a collector per `/api/scorecard` request; `timed(name, awaitable)` / `span(name)` record start, duration, success and (through `main._limited(coro, name)`) the wait on the retrieval semaphore. Tasks started inside the request inherit it, so every domain orchestrator names its sub-tasks (`property.sales`, `regulatory.flood`, `neighborhood.walkscore`, ...) and `socrata_get` records one `socrata.<dataset id>` span per HTTP attempt. Outside a collector (chat, the report) the helpers are pass-throughs; a span re-raises unchanged. Every Profile request logs one `scorecard timings` line (total, resolution, fetch, three slowest tasks); the full breakdown rides the response as `_timings` only with `PROFILE_TIMINGS=true` and never in production (`test_timing.py`). *Alternatives:* OpenTelemetry/Sentry tracing (a new dependency and a vendor for one measurement), a `Server-Timing` header (needs `Response` in the handler signature, which the direct-call tests don't pass; the log line already serves production), timing in the eval script only (it could not see inside the orchestrators).

**Decision: the measurement runs in-process, cold and warm, no model.** `eval/profile_latency.py` calls the handler with the collector on the four page-budget parcels plus three fresh ones. *Cold* = every TTL cache emptied (a parcel and community area nobody opened since start; shared connections and startup artifacts stay warm, as on a running server). *Warm* = the same parcel straight after. Round 0 (the process's first Profile) is reported apart. `--isolate` runs each slow lookup alone, cold; `--base URL` times a running server over HTTP. Local only so far: production needs the owner's go.

**What the numbers say** (table below):
1. **No catastrophic single task.** A cold Profile makes ~36 Socrata requests (32–44) plus ArcGIS, FEMA, EPA, Census, FCC and Walk Score calls, and waits for the slowest. The task that finishes last varies run to run (property 10/35, 311 7, crime YoY 6, incentives 6, violations 2, others 1 each). Whole response: **cold p50 26.8 s, p95 46.0 s; warm p50 41 ms.**
2. **The City data portal is the tail.** A one-row query to `data.cityofchicago.org` took 1.7–9.6 s (median 6.4 s) during the run; the County portal 0.4–1.9 s. The same lookups run alone are mostly 0.4–3 s at the median with 6–10 s outliers; inside a Profile, beside ~35 other requests, their medians roughly double (crime 3.1 → 6.9 s, parcel flags 1.1 → 6.5 s). Crime (`ijzp-q8t2`, community-area aggregates over the full crime table) is the largest single cost: its requests sum to 25 s p50 / 43 s p95 per cold Profile.
3. **The known suspect, confirmed and bounded.** The Cook County GIS point lookup runs only when an address resolves approximately (geocode, no Address Points PIN): 10.0–10.8 s on every such run (3300 W Armitage, 5 of 35 cold runs). It alone puts the lot-on-the-map time at 12 s for those parcels.
4. **Hidden ordering inside the property domain.** The building-facts fallback (stories, year built, floor area for non-residential classes; it feeds "units built") starts only after the whole first property batch finishes, including parcel flags (City-owned land, scofflaw, short-term-rental lists: 6.5 s p50, one run 56 s on `aksk-kvfp`). That ordering, not the fallback (1.4 s p50), makes the Overview's own dependencies end at 15.7 s p50.
5. **A warm-path defect, fixed.** TIF financial reports (`72uz-ikdv`, `qm7s-3ctt`) had no cache, so every visit to a parcel in a TIF district re-fetched the same annual rows: warm 1.5–12 s on the two TIF parcels. **Fixed** with a 24 h cache per district, successes only (`tif._financials_cache`; a failure still raises and is never cached, Item 65; tests in `test_incentives_tif.py`). Warm p95 on those parcels: 12.25 s → 0.50 s (n=6).
6. **Crime caches for 15 minutes** (`crime._cache`, 900 s). The source publishes daily, and the Profile's crime figures are per community area, so on production most visits re-pay crime's 7 s p50 / 21 s p95. **Proposed, not changed** (a freshness choice): 6 h.

**Targets, confirmed and revised.** Item 75's "first useful content under 3 s warm and 6 s cold" holds if *first useful content* means **the lot on the map, its address and district, and what the district allows** (resolution + zoning point + PTAXSIM outline + the Title 17 table): measured **1.85 s p50 / 3.87 s p95 cold** on exactly resolved parcels, 19 ms / 0.44 s warm. Approximate parcels can't meet it while they wait on County GIS (12 s): they show the point and district first and the outline when it comes. Proposed second target: **the full Overview (answer sentence and the four tiles) under 8 s cold p95.** Its dependencies with the two late starts removed (`overview_unblocked`) end at 3.7 s p50 / 6.6 s p95 on exact parcels (16 s p95 including approximate ones); today, waiting for everything, it is 26.8 / 46.0 s. Everything else loads after and is named while it does.

**Proposed progressive loading for the preview Profile (needs the owner's go before building).**
- *First (about 2 s):* a small request beside today's, `GET /api/scorecard/first` (same parameters): the resolved identity (address, PIN, confidence, point), the parcel outline and lot area from PTAXSIM, the zoning district and its Title 17 row. The page drops the skeleton at once: the map band with the lot, the address, "Zoned B3-2" and what the district allows on this lot.
- *While the rest loads:* the four tiles hold their places with their labels, each saying what it waits for ("Units built: checking County building records", "Property tax: checking", "Walk score: checking", "Last sale: checking County sales"), and one quiet line lists what is still on its way by source ("Still checking: overlays and flood (City map, FEMA) · sales and tax history (Cook County) · neighborhood (crime, 311, transit)"). No seconds counter. Until Phase 4 the page gets the rest as one response, so it cannot say which source is still out: the line names what the rest contains, not its progress.
- *Then:* today's full response replaces it (one swap, no re-layout: the tiles keep their slots). If the first request fails, today's loading state shows; if the full one fails, what the first request showed stays with an honest "couldn't load the rest. Retry".
- *Cost:* one extra request with three or four public calls on a cold visit (both requests start together, so they can ask the same source twice until Phase 4 shares one identity), new strings in English and Mexican Spanish, a contract test that the first response's figures equal the full response's.
- *Not in Phase 2:* streaming parts, dedup of in-flight work, cancelling, reordering the property domain. Those are Phase 4.

**Sketch of the Phase 4 contract, from these numbers.**
- *Overview part* (target: under 8 s cold p95): identity; outline and lot area; zoning point + Title 17 row; characteristics, assessments, sales (with a **per-sale arm's-length flag** computed server-side from the County's own sale filters, retiring Item 77's client test), PTAXSIM tax; the overlays the verdict and the 606 rule read; Walk Score; the verdict and the answer sentence's inputs; the building-facts fallback started as soon as characteristics and the outline are in, not after the flags. Budgeted dependencies: Address Points or the PIN row, the zoning point, PTAXSIM (local), four County Assessor datasets, the overlay layers, Walk Score.
- *Late parts:* parcel flags, appeals and Assessor permits (History); comparables and FAR comps (Money, they need the class and the zoning quilt); incentives, TIF reports and grants; neighborhood (tract, transit, traffic, Divvy, rent); crime, 311, violations, ARO; the RS-3 block-face test (a late "unchecked → checked" on the units tile, as the 606 rule already is); upcoming zoning (local, 13 ms, can ride the Overview).
- *Sequencing:* the Overview's requests go first; the late parts start once it has answered (the burst roughly doubles the City portal's medians); one resolved identity shared by all parts (Item 75, plan item 14). A per-source deadline for the late parts ("couldn't check in time", never "none") is a choice for the owner then, measured against how often it would fire.

**Alternatives considered:** parallel tuning (a bigger semaphore or connection pool: the wait on our own semaphore is 0 for the domain tasks and 1–2 s only for violations and 311, and more parallel requests make the City portal slower, not faster); hard timeouts now (would turn slow answers into "couldn't check" rows on the live Profile, a product change); caching everything longer (the cold case is the first visit to a parcel; only area-level caches like crime help across visitors).

**Revisit if:** production numbers (another network, other hours) differ a lot from these; the City portal's one-row baseline returns to well under a second (then the in-Profile contention, not the portal, is the thing to fix); the builder test says the first screen without the tiles reads as "broken" rather than "loading".

**Numbers** (2026-11-07, MacBook Pro arm64, home network, in-process, git `627bdb7` + the TIF fix measured separately; 7 parcels × 5 rounds = **n 35 cold, 35 warm**; nearest-rank percentiles). *Reproduce:* `PYTHONPATH=. python -m eval.profile_latency --label <label> --rounds 5` (~25 min, public APIs, no model); `--isolate --rounds 5 --parcels milwaukee`; results in `eval/results/2026-11-profile-latency/` (`local-2026-11-07`, `local-2026-11-07-tif-cache`, `isolate-2026-11-07`).

| Task | cold p50 | cold p95 | warm p50 | warm p95 |
|---|---|---|---|---|
| **Whole response** | **26.8 s** | **46.0 s** | 41 ms | 12.3 s (TIF defect; 0.5 s after the fix) |
| Lot + district (`first_content`) | 1.9 s | 12.3 s (3.9 s exact parcels) | 19 ms | 0.44 s |
| Overview deps, as ordered today | 15.7 s | 45.9 s | 22 ms | 0.44 s |
| Overview deps, unblocked | 3.8 s | 16.2 s (6.6 s exact parcels) | 22 ms | 0.44 s |
| resolution (Address Points / PIN / geocode) | 0.40 s | 2.42 s | 0 | 0.41 s |
| property (domain) | 12.5 s | 27.4 s | 22 ms | 33 ms |
| ↳ parcel by PIN / by point (County GIS) | 1.41 s / 10.0 s | 3.12 s / 10.8 s | 0 | 0 |
| ↳ characteristics · assessments · sales | 0.38 · 1.40 · 1.60 s | 0.62 · 2.81 · 1.88 s | 0 | 0 |
| ↳ tax · outline (PTAXSIM, local) | 9 ms · 9 ms | 13 ms · 12 ms | 3 ms · 0 | 4 ms · 0 |
| ↳ parcel flags · appeals · Assessor permits | 6.47 · 1.95 · 1.50 s | 19.5 · 4.53 · 2.84 s | 0 | 0 |
| ↳ building-facts fallback | 1.42 s | 13.8 s | 0 | 0 |
| regulatory (overlays, flood, brownfield) | 2.12 s | 3.31 s | 15 ms | 20 ms |
| zoning point | 0.58 s | 1.35 s | 0 | 0 |
| incentives | 11.2 s | 24.6 s | 12 ms | 10.7 s (TIF defect) |
| ↳ grants (SBIF, NOF) | 7.85 s | 17.9 s | 0 | 0 |
| neighborhood | 5.09 s | 15.2 s | 6 ms | 8 ms |
| ↳ census tract · walk score · traffic · Divvy | 2.31 · 1.82 · 2.07 · 1.68 s | 2.67 · 2.83 · 12.4 · 11.0 s | 0 | 0 |
| crime · crime YoY | 6.94 · 6.69 s | 20.4 · 21.9 s | 0 | 0 |
| violations (address) · 311 (address) | 4.70 · 4.03 s | 16.4 · 27.9 s | 0 | 0 |
| ARO housing | 1.90 s | 13.9 s | 0 | 0 |
| comparables + FAR comps (after the fetch) | 3.49 + 1.72 s | 5.81 + 2.35 s | 0 + 5 ms | 0 + 19 ms |
| RS-3 block-face test (n=5) | 7.67 s | 15.9 s | 0 | 0 |
| upcoming zoning · provenance · serialize | 13 · 2 · 2 ms | 21 · 2 · 2 ms | — | — |

- Queue wait on the retrieval semaphore (8): 0 for the domain tasks; p95 1.2 s (violations) and 2.4 s (311).
- Failures: 1 of 35 cold runs lost a source (311 on 233 S Wacker); no Socrata retries.
- First Profile after process start: 19.2 s (round 0). Payload median 98.9 KB.
- Lookups alone, cold, 5 runs each (median / max): City portal one row 6.4 / 9.6 s; County portal one row 0.57 / 1.9 s; crime 3.1 / 7.7 s; crime YoY 0.74 / 6.4 s; 311 0.92 / 9.8 s; grants 3.0 / 10.3 s; traffic 2.6 / 6.8 s; parcel flags 1.1 / 2.5 s; energy benchmarking 2.2 / 9.2 s.
- **Not measured:** production (needs the owner's go; a different network, a 4-vCPU box, other visitors' caches); the browser side (JS parse, map tiles; the new Profile is gated on this one response); `/api/parcel-map`, `/api/area-stats` and `/api/capacity-map` (today's Profile only).

## Item 82: Phase 2, the Profile's first screen while the rest loads (2026-11-07)

**Status: built on the Phase 2 branch, checked locally; the owner gave the localhost review a thumbs up on 2026-11-07.** The owner approved Item 81's proposal ("Yes, build it"). His Sentry weekly report (Oct 31 to Nov 7) shows the same picture on production: `/api/scorecard` p95 17.3 s, the `/scorecard` page p95 13.6 s.

**Decision: a second, small request beside today's, `GET /api/scorecard/first`.** Same parameters, same resolution (`_resolve_location`, the Chicago check). It returns the identity and point, the zoning district at the point with its Title 17 row, and, for a PIN-resolved parcel, the lot outline and lot area. Measured locally (n=5, first visit to each parcel, home network): 3.4 s for 2541 N Spaulding (the process's first request), 2.9 s for 7600 S Halsted, 0.93 to 0.98 s for 5600 N Clark, 233 S Wacker and the PIN 14-28-319-007; the full response took 20.6 s and 29.3 s for the two fresh addresses. A small sample: production timing comes from the request's own log line. *Alternatives:* streaming the full response in parts (Phase 4's job: it changes the response contract the live Profile and chat read); computing the first screen on the client from cached data (nothing is cached on a first visit, which is the slow case); a skeleton with a better message only (the owner named slow loading, Item 79; words don't shorten 27 s).

**Decision: the first screen uses the full response's own rules, so no figure changes at the swap.**
- *Lot area:* one function, `property.lot_area`, now decides the area for both: the Assessor's stated area wins, the PTAXSIM outline fills a gap, a shared outline is no lot's. `first_lot_facts` reads the same three inputs as the PIN path of `property_domain` (characteristics, assessments, the outline) and drops a stale vacant-lot characteristics row by the same test. `test_scorecard_first.py` runs both on five cases (Assessor area, outline fill, shared outline, stale row, no outline) and asserts equal areas, sources and outlines.
- *Allowed floor area:* the same arithmetic and rounding as the Build tab's "Allowed vs built" (`fmtInt(FAR × lot area)`); `firstModel.test.tsx` checks the sentence contains the Build tab's figure, and the Playwright check reads it on the live stack (1601 N Milwaukee: 26,292 sq ft in both).
- *The ratio:* written as the answer sentence that replaces it writes it (`fmtFar`, and in Spanish the same term, "coeficiente de edificabilidad (FAR)").
- *Edge kept on purpose:* when the PIN lookup misses and the full response falls back to the County GIS point lookup, it can read GIS's area where the first screen used the outline's. Rare (the PIN path carries no GIS area), and the full response wins at the swap.

**Decision: an approximate match shows no lot.** Without an Address Points PIN the first request doesn't wait for the 10 s County GIS lookup (Item 81, point 3): it shows the point, the district, the ratio and the "Approximate match" label. The full response may still find the parcel near the point and draw it.

**Decision: what the page shows while the rest loads.**
- The map band with the lot and the address, then the tab bar (Build greyed out until the rest arrives), then one sentence in the answer's place: "Zoned B3-2: up to 26,292 sq ft of floor area on this 11,951 sq ft lot." (with "up to N ft tall" when the table's height is one plain number).
- The four Overview tiles in their final order, each with its label and what it waits for ("Checking County building records", "Checking County tax records", "Checking Walk Score", "Checking County sales"), a placeholder bar the height of a figure, so the grid doesn't move when the figures arrive.
- One quiet line: "Still checking: overlays and flood (City map, FEMA) · sales and tax history (Cook County) · neighborhood (crime, 311, transit)." No seconds counter. It names what the rest contains, not its progress (the rest is still one response until Phase 4).
- Ask, Sources and Export stay in place, disabled, with "Available once the profile has loaded" in their names.
- *Then* the full response fills the same screen: one component (`ProfileScreen`) keyed per lookup, so the map isn't remounted (the Playwright check marks the canvas before the swap and finds it after). If the first request fails or is slower than the full one, today's loading state shows as before. If the full one fails after the first screen, the first screen stays with "Couldn't load the rest of this profile. Retry", and Retry asks for the full response again.
- Strings in English and Mexican Spanish (usted), under `next:profile.first.*`.

**What this costs.** One extra request per Profile visit: the resolution (Address Points, cached), the zoning point, two County requests (characteristics, assessments) and the local PTAXSIM table. On a cold visit both requests start together and can ask the same source twice (the TTL caches are filled by whichever answers first); Phase 4's shared identity removes that.

**Not done here (Phase 4):** streaming parts, sharing one resolution between the two requests, cancelling, reordering the property domain, the late parts' deadlines.

**Found on the way, not fixed (follow-up):** the preview formats Spanish numbers with Spain's locale (`es`: `24.750`, `2,2`) instead of Mexico's (`es-MX`: `24,750`, `2.2`) in `profileModel.ts`, `BuildTab.tsx` and the money figures; today's live UI already maps `es` to `es-MX` (`lib/format.ts`). The first screen follows the preview's current formatting so the floor area agrees with the Build tab; one change can fix all of them.

**Revisit if:** the builder test (Phase 3) reads the first screen as finished rather than loading, or the tiles' waiting state as broken; production timing of `/api/scorecard/first` (its own `scorecard first timings` log line) is well over 3 s p95; Phase 4 lands (this request becomes the Overview part's first slice or goes away).

**Tests:** `backend/tests/test_scorecard_first.py` (10: the five lot-area cases, a failed County call raises, exact and approximate payloads, failed parts are unchecked, outside Chicago is refused); `frontend/src/ui-next/profile/firstModel.test.tsx` (8: the sentence equals the Build tab's figure, the fallbacks, failures, tile order, axe, Retry, Spanish); `e2e/ui-next.spec.ts` "first screen before the full Profile" (axe light and dark, no overflow at 360 px, disabled tools, one swap with the same map canvas, the Build tab's floor area equals the first screen's).

## Item 83: closing Phase 2: crime cache, production numbers, and the model-call rule for testing (2026-11-07)

**Decision: crime aggregates cache for 6 hours (was 15 minutes).** The owner: crime is "one of the less important things", cache it. The City publishes crimes daily with a lag, the Profile's crime figures are per community area, and Item 81 measured crime as the largest single cost of a cold Profile (7 s p50 / 21 s p95), re-paid by every visitor to an area after 15 minutes. `crime.CRIME_CACHE_TTL_S`; still successes only (a failed request raises before the cache is written, Item 65). Chat reads the same cache. Test: `test_crime_cache.py`. *Alternatives:* dropping crime from the Overview's critical path (Phase 4 does that by making it a late part); 24 h (a day-boundary refresh would then lag a whole day).

**Measured on production (owner's permission, the evening of 2026-11-07).** Production doesn't run the per-task timing yet (it ships with this PR), so this is whole-request time from outside: 10 addresses unlikely to have been opened, one request at a time, each loaded twice (raw: `eval/results/2026-11-profile-latency/prod-http-2026-11-07.txt`).
- *First visit:* p50 24.7 s, p95 44.1 s (16.8–44.1 s). Matches the local cold numbers (Item 81: 26.8 / 46.0 s), so local measurement stands in for production on the cold path.
- *Repeat visit:* p50 4.0 s, p95 14.4 s (3.5–14.4 s). Locally a repeat takes 41 ms.
- *Why:* every production Profile reported "FEMA flood zone" as couldn't-check. FEMA's NFHL service answered the same query from a home connection in 1.4–1.6 s (three tries) but fails from the production server; the Sentry weekly report shows the matching `fed.fema.nfhl` stale alarm. Because a failure is never cached (Item 65, deliberately), every visit asks FEMA again and waits about 4 s. The three slowest repeats (8.7, 9.7, 14.4 s) look like TIF parcels, whose financial reports this PR now caches (Item 81).
- *Consequence:* the FEMA failure is a production data problem, not a latency design question: until it is fixed, every Profile says flood couldn't be checked. Listed as its own task. Re-measure after this PR deploys, from the `scorecard timings` and `scorecard first timings` log lines.

**Decision: model calls in testing (owner, 2026-11-07).** Chat is tested only when chat is what a change updates or fixes; it stays out of every other automated check, verification sweep and localhost review, because chat turns spend production credits quickly and the rewrite ships many updates. The Phase 3 human builder test may spend **up to $2** (cut from the proposed $10): the "ask a follow-up" task is its one chat use, recorded and tagged with the UI version.

**Phase 2 is closed** with Items 81–83: instrumentation, the measurement script, the TIF and crime caches, and the first screen. Phase 4 (the response split) starts from Item 81's contract sketch and these numbers.

**Revisit if:** crime figures need same-day freshness for a feature (alerts); the FEMA fix lands (repeat visits should drop to well under a second, otherwise look again); production per-task numbers differ from Item 81's local ones.


## Item 84: FEMA's flood zones come from a committed Chicago copy, because FEMA blocks the production server (2026-11-07)

**Decision: a point inside Chicago is answered from `ingestion/data/fema_flood_chicago.json.gz`, FEMA's own NFHL layer 28 polygons clipped to the city, by point-in-polygon with no network call.** A point outside the copy's coverage, or every point when the copy is missing or unreadable, still asks FEMA live, and a failure there is still "couldn't check" (`FloodLookupError`, Item 65), never "no flood zone". The dev fault flag (`DATA_HEALTH_FAULT=source:fed.fema.nfhl`) still beats both paths. Built by `python -m ingestion.build_flood_artifact` from a machine FEMA answers; registry `artifact.fema_flood_chicago` (sidecar-dated, warn at 200 days, alarm at 400); the `regulatory.flood` fact now cites it, with `fed.fema.nfhl` as the alternate source.

**Why: FEMA's edge refuses the production server.** Item 83 found every production Profile reporting flood as couldn't-check. Measured from the server on 2026-11-07: `hazards.fema.gov` accepts the TCP connection and resets the TLS handshake after about 0.23 s, 10 of 10 tries across both of its IPs (IPv4; the box resolves no IPv6 for it), with curl as well as httpx and with any User-Agent; `www.fema.gov` answers 403 and `msc.fema.gov` doesn't answer. The server's address geolocates to Germany. The same query from a US home connection answers in 0.3–1.6 s. So it is a block by source address or country, not a moved URL, a timeout or a TLS-version problem, and the October "about half of fresh connections reset" pattern (the retry logic in `flood.py` and `probes.py`) has become all of them. No client-side change can fix it.

**Alternatives:**
- *Esri's Living Atlas "USA Flood Hazard Areas" mirror.* Reachable from the server, but it is a third party's derivative, and its reduced set holds only the high-risk zones (the test point returned no feature where FEMA says X), so "no feature" there doesn't mean what FEMA's "no feature" means. Rejected under the source-authority rule.
- *A proxy in the US (a Cloudflare Worker or a small US host).* It keeps the answer live, but it is new infrastructure in the request path, and FEMA could block that address too.
- *A short negative cache of the failure.* It would cut the 4 s repeat cost, but every Profile would still say couldn't-check. It treats the symptom.

**The trade-off is data vintage.** The copy is FEMA's data as of the build date (2026-11-07): the Cook County FIRM panels (`17031C`, plus the edge panels `17043C` and `18089C`) with whatever LOMRs FEMA had folded in by then. A Letter of Map Revision issued later won't show until the next rebuild. Chicago's flood maps change rarely, a few LOMRs a year, and the Profile already says flood is a FEMA designation to confirm. The registry's 200/400-day warn/alarm puts a rebuild on the calendar about every six months, and sooner when FEMA announces a Cook County revision.

**Build guards:** the build pages FEMA tile by tile (one large page answers 500), refuses to write if any page fails, and refuses to write if the polygons cover less than 98% of the city's land. That guard caught the first build: deduplicating by `GFID`, which is not unique, kept 3 polygons. On a shared edge the flood-hazard zone wins.

**Numbers:**
- Production Profiles listing flood in `failed_sources`: 10 of 10 (Item 83, 2026-11-07) → expected 0 after deploy (to verify on the live API).
- FEMA cost of a repeat Profile visit: about 4 s on production (Item 83) → 0 network calls inside the city. The artifact loads once per process in 81 ms; a lookup takes about 22 µs (1,000 lookups in 22 ms, local, 2026-11-07).
- Agreement with live FEMA: 400 of 400 points (300 uniform over the city, 100 in or within ~50 m of a flood-hazard area), zone and SFHA flag both equal, 2026-11-07.
- Artifact: 395 zones, 100.0% of the city covered, 0.5 MB gzipped; flood-hazard areas are 3.5% of the city's land.
- Reproduce: the server measurement is curl to `.../NFHL/MapServer/28/query` from `ssh urbanlayer-prod` (exit 35, connection reset); the build is `PYTHONPATH=. python -m ingestion.build_flood_artifact`; the agreement check is a script comparing `flood._from_artifact` with live FEMA at random city points (not committed: it calls FEMA 400 times).
- Not measured: the production repeat-visit time after deploy (from the `scorecard timings` log line, Item 81).

**Still open:** the `fed.fema.nfhl` data-health probe asks FEMA live from the server, so it keeps failing there and its stale alarm will continue. The Profile no longer depends on it. Acknowledging the alarm or running the probe off-box is the owner's call.

**Revisit if:** FEMA unblocks the server's address (then a live check of the copy against FEMA could join data health); FEMA issues a Cook County map revision; UrbanLayer covers places outside Chicago (they would all go to the blocked live path).

## Item 85: the backend's own info lines reach the production logs (2026-11-08)

**Decision: at startup, `log_safety.configure()` gives the root logger a stderr handler (`LEVEL logger: message`) and sets the `backend` logger to INFO; the root stays at WARNING, so libraries (httpx, uvicorn's internals, sentence-transformers) stay quiet.** It runs before `log_safety.install()`, so the CR/LF filter now has a handler to sit on.

**Why: found while verifying Item 84.** The `scorecard timings` lines Item 81 added, and Item 83 planned to re-measure from, never reached production. `grep 'scorecard timings'` over two hours of backend logs returned nothing. Uvicorn configures only its own loggers, so the root logger had no handler. The app's warnings reached stderr through Python's last-resort handler, which shows WARNING and up and runs no filters, and every `log.info` was dropped. The same gap meant `log_safety.install()` (which attaches to root handlers) found nothing to attach to, so the app's own warnings were written unescaped.

**Privacy: two lines move down to DEBUG.** `conversation.py` logged the user's chat message ("Synthesized query", "Neighborhood switch") at INFO. Turning INFO on would have started writing chat text to the production logs, so both are DEBUG now (a test checks that). The remaining info lines, 44 of them, are startup and model loads, migrations, Stripe webhook outcomes (user and Stripe ids, as the existing warnings already log), parcel-lookup notes and the timings.

**Alternatives:** `uvicorn --log-config` with a dictConfig file (the same effect, but it would live in the Dockerfile and compose, apart from the code it serves); `logging.basicConfig(level=INFO)` (turns INFO on for every library too, noisy); raising the timings line to WARNING (it isn't a warning, and every Profile request would then read as one).

**Numbers:**
- `scorecard timings` lines in two hours of production logs, 2026-11-08: 0 → expected one per Profile request after deploy.
- Reproduce: `sudo docker logs --since 2h urbanlayer-backend-1 2>&1 | grep 'scorecard timings'` on the server.
- Not measured: log volume after the change (expected small: 46 info call sites, about two per Profile request).

**Revisit if:** log volume becomes a cost (then move per-request lines to a sampled logger); the app moves to structured (JSON) logs.

## Item 86: the blocked live FEMA probe warns, and never alarms, while the Chicago copy is fresh (2026-11-08)

**Decision: `fed.fema.nfhl` gets `warns_only_while_ok="artifact.fema_flood_chicago"`,** the same rule `cook.gis.parcels` has had with its Parcel Universe fallback. The daily check still probes FEMA from the server. Because FEMA refuses the server (Item 84), that probe fails every day, and now it is a `warn`, which shows on the admin panel and never reaches Sentry, for as long as the committed copy is fresh. When the copy goes stale (warn at 200 days, alarm at 400), the cap lifts and the FEMA failure alarms again. That's right, because then neither path can be trusted.

**Why:** Item 84 moved every Chicago flood answer to the committed copy. The live service now serves only points outside the city and the artifact build, both run from somewhere FEMA answers. An alarm that fires every day for a reason the Profile no longer depends on would train its reader to ignore the data-health alarms.

**Alternatives:** `probe="none"` (stops watching FEMA altogether, so a URL move would go unnoticed until the next rebuild failed); an `Ack` until a date (it silences the alarm whether or not the copy is fresh, and runs out on a calendar date instead of on a condition); running the probe off-box (needs a second machine for one source).

**Numbers:** 
- Sentry alarm on `fed.fema.nfhl`: firing (weekly report, 2026-11-07) → expected to drop to warn at the first daily check after deploy.
- Local dry run 2026-11-08 (`PYTHONPATH=. python -m backend.data_health.check --dry-run --only artifact.fema_flood_chicago,fed.fema.nfhl`): both ok, the artifact built 2026-11-07, age 1 day. From the Mac FEMA answers, so this cannot show the production warn. The unit test `test_a_blocked_live_fema_only_warns_while_the_artifact_is_fresh` covers it with a reset connection and the real registry entries.
- Not measured: the production panel state after the next daily check.

**Revisit if:** FEMA unblocks the server (the probe then goes back to ok on its own); the server moves to a US region.

## Item 87: Phase 3, production Profile latency after the first screen and the FEMA fix (2026-11-08)

**Status: measured from outside; the per-task view from the server's `scorecard timings` lines is still to come** (reading them needs `sudo` on the server, so the owner pulls them). Item 83 asked for this re-measurement once #204 (the first screen) was live; the FEMA fix (Items 84–86) landed the same morning.

**What was measured.** 8 Chicago addresses nobody had opened in this test series (`eval/results/2026-11-profile-latency/prod-http-2026-11-08.txt`), one visit at a time from a home connection outside the US, through Cloudflare. A visit starts `/api/scorecard/first` and `/api/scorecard` together, as the preview page does, and each address was visited twice. No model calls (the Profile has none).

| | first screen (`/first`) p50 · p95 | full Profile p50 · p95 |
|---|---|---|
| First visit (n=8) | **2.5 s · 4.8 s** (1.7–4.8 s) | **20.4 s · 22.8 s** (12.4–22.8 s) |
| Repeat visit (n=8) | 1.1 s · 1.6 s | **1.8 s · 2.5 s** |
| Item 83, 2026-11-07, before both fixes (n=10) | not live | first 24.7 s · 44.1 s; repeat 4.0 s · 14.4 s |

- **Failed sources: 0 of 16 full responses** (the day before: flood failed on 10 of 10). Flood is answered from the committed copy (Item 84).
- **Repeat visits dropped from 4.0 s to 1.8 s p50.** Server-side a repeat takes 44–52 ms (Item 84's close-out); the rest is the network route from outside the US to the Nuremberg server, so a US visitor should see less.
- **The first screen meets Item 81's targets on production**: under 3 s warm at p95 (1.6 s) and under 6 s cold at p95 (4.8 s, n=8).
- **The full first visit is still 20 s**, as expected: the response split is Phase 4. That's the wait builders see on their own lot in the builder test (Item 88).
- One of 8 resolved approximately (3100 N Sheffield); its first screen showed no lot, as designed (Item 82).

**Decision: none needed; the latency is fit for the builder test.** The first screen holds; the full-Profile wait on a fresh lot is what case 2 of the test observes.

**Not measured:** the per-task split on production (the `scorecard timings` lines: total, resolution, fetch, three slowest tasks); a US network; more than 8 addresses (p95 of 8 is the slowest run).

**Revisit if:** the server-side log lines show a task far slower than Item 81's local numbers; the first screen's p95 goes above 6 s cold on more visits.

## Item 88: the builder test is deferred; the kit stays ready (2026-11-08)

**Decision (owner, 2026-11-08): Phase 3's builder test doesn't run now, because no builders are lined up to interview.** The rewrite moves on to Phase 4 (the Profile response split). Item 75's pass criteria are unchanged and still unapplied: nothing in the rewrite has been tested with a first-time builder yet.

**What is ready for when it runs.** A moderated test kit, kept locally in `research/16-builder-test-kit/` (gitignored, since it will hold builders' names): a no-coaching moderator script, a consent form and task cards (one per Item 75 criterion) in English and Mexican Spanish, an observation sheet, an answer key, and a template for scoring. The owner's choices so far: he moderates over video with screen share, English only, prewarmed parcel 2541 N Spaulding Ave (an RS-3 two-flat; its bars have real fills, units 2 of 2 is the deciding limit). The alternative, 1601 N Milwaukee, has every bar hatched, so the bars criterion can't be scored there. Model budget still $2, for the follow-up task only (Item 83).

**What can proceed without it, and what can't.**
- *Phase 4 (response split)* and *Phase 5 (map tracks)* proceed. Both are driven by measurements (Items 81, 87) and the map requirement (Item 80), not by how builders read the page.
- *The gate moves:* the builder test runs **before any route flips to the new UI by default**, and before the page-design rules are rewritten for the new system (Item 75). The test's "revise the structure before building more pages" still holds: if the test fails then, pages built in the meantime are revised first.
- *Retest cost goes up with every page built before it.* Running it on Phase 4's faster Profile is fine (the criteria don't depend on load time); running it after Phase 6 means several tabs could need rework.

**Alternatives:** an unmoderated link sent to builders (can't observe hesitation or coaching, so it can't score Item 75's criteria); testing with people who aren't builders (the brief's audience is small developers, and Item 75 names builders); holding the rewrite until builders are found (blocks work the test doesn't inform).

**Revisit if:** builders become available (run the kit, record results as a new Item); Phase 6 is about to start without a test (raise it with the owner first).

**Numbers:** none measured on users. n = 0 builders.

## Item 89: Phase 4, the Profile in parts (2026-11-08)

**Status: built on `feat/ui-next-phase-4-parts`, checked locally; the contract was approved by the owner before it was built ("Yes, build it", 2026-11-08), with his four answers below and two more during the build (the City's building records; grants and ARO cached 24 h). The local Overview target is not yet shown at p95 (numbers below); production after deploy is the measurement of record (the owner: no more hour-long local runs until a change promises a large cut).** The full `/api/scorecard` is unchanged and still serves today's Profile, chat grounding and the $25 report (owner: the old Profile stays on it until its route flips).

**Production per-task numbers first** (the `scorecard timings` lines since #206, pulled by the owner, 48 h to 2026-11-08, 50 lines, no addresses in them). `/api/scorecard/first`: n=18, all ok, p50 0.2 s, p95 2.0 s server-side. Full Profile, first visit (> 3 s): n=16, **p50 18.8 s, p95 25.6 s**, max 29.7 s; resolution p50 0.8 s / p95 2.8 s. Repeat: n=16, p50 57 ms, p95 0.9 s. Slowest task on first visits: property 6 of 16, 311 4, incentives 4, crime 1, violations 1; in the top three: property 12× (median 12.8 s), 311 7× (16.2 s), crime YoY 7× (9.2 s), crime 7× (8.3 s), incentives 6× (11.5 s), neighborhood 5× (9.2 s). No failures. These include Item 87's 16 test visits. They match Item 81's local picture: the property domain holds the Overview, and 311, crime and incentives are the tail.

**Decision: separate part endpoints with a signed lookup (owner's pick).**
- `GET /api/profile/overview?address|pin|lat&lon` resolves once, reconciles identity (the approximate round trip runs here and only here), and returns `lookup` (HMAC-signed with the JWT secret under its own context string, 30 minutes) plus the Profile so far.
- `GET /api/profile/part/{building|history|money|incentives|neighborhood|activity|block_face}?lookup=…&have=…` never resolves again; a forged or expired lookup is a 409 and the page asks the Overview again.
- `/api/scorecard/first` (Item 82) stays as the first slice; it and the Overview start together and share one resolution, one zoning lookup and the County characteristics/assessments calls (`backend/inflight.py`).
- *Alternative:* one streamed response (NDJSON/SSE): one request and server-side ordering, but nginx needs an unbuffered location, a failed part still needs its own endpoint for Retry, and one slow source holds the connection.

**Decision: one record per lookup; every response is the whole Profile so far.** Derived figures read several parts at once (the unit yield reads the zoning, the lot, the 606 layer and the block face; code currency reads the CHRS flag; coverage notes, provenance and the data dates read everything), so a part can't compute them alone. Each part writes its raw results into an in-memory record (`TTLCache`, 30 min) and every response is assembled from all of it by the full path's own functions (`main._scorecard_data_from`, `main._finish_scorecard_payload`). The page keeps the response with the highest `version`, so nothing is merged by hand and the order parts land in doesn't matter. Once every part is in, the Profile equals `/api/scorecard`'s for the same sources (`test_profile_parts.py`, four cases incl. a commercial lot, a failed block face and an approximate match). A record the server lost is rebuilt from the token plus the parts the page says it has. *Cost:* each response carries the whole Profile (about 100 KB, gzipped on the wire), up to eight per first visit. *Alternative:* each part returns only its own keys and the page merges them (the derived figures would be wrong until a final recompute, and every derived field would need its own merge rule).

**What the Overview holds.** Identity and resolution record, the zoning point and its Title 17 row, the core property record (characteristics, assessments, sales with a per-sale arm's-length flag, PTAXSIM tax and outline, the County's building records: condo rows and Commercial Valuation), regulatory (overlays, flood, brownfield), program membership by point (TIF, EZ, OZ), Walk Score, upcoming zoning, code currency and the passed-ordinance checks, with their provenance and data dates.
- **Late parts:** `building` (the City portal's building records: energy benchmarking and footprints), `history` (parcel flags, appeals, Assessor permits), `money` (comparables and FAR comps), `incentives` (TIF reports, grants, and the tract-keyed QCT and NMTC: the FCC/Census tract lookup took up to 16 s inside the Overview), `neighborhood` (tract, transit, traffic, Divvy, rent, HUD SAFMR), `activity` (crime, crime trend, 311, violations, ARO), `block_face` (RS-3 only). A part that doesn't apply isn't asked (no History without a property record, no Money without a class, no area parts without a community area, no block face outside RS-3, no building part when the Assessor's row has the facts).
- **The verdict shows with the Overview and can update late (owner's pick).** It reads parcel flags, the TIF fund balance, appeals and open violations, which are late; while History waits the Overview says "Still checking the City's lists (City-owned land, scofflaw, short-term rentals), which can add a caveat."
- **The City's building records are a late part (owner's pick, during the build).** The first measurement showed the Overview's tail on commercial lots was two City-portal lookups in the building-facts fallback: energy benchmarking (`xq83-jr8c`, up to 22.7 s) and footprints (`syp8-uezg`, up to 12.9 s). The Overview keeps the County's records; the `building` part reruns the core with the City's (the County calls are cached by then) through the same fill-only merge. Until it lands a missing built figure reads "Checking City building records", never "not on record". *Alternatives:* the Overview waits (17–26 s p95 on commercial lots); a 4 s deadline inside the Overview.
- **The address candidates** (every parcel the address sources list, read only by the "how we found this parcel" panel in Sources) start with the Overview but no longer hold it (up to 10.8 s seen); the late parts take them, and Sources turns on only once every part is in.
- **Grants and ARO per community area cache 24 h** (owner's pick; were 1 h): area-level lists that change rarely, the main reason incentives passed the deadline (grants 15 s p50 in the run below). Successes only (Item 65). *Alternative:* a daily background pre-warm of all 77 areas (about 154 City requests a day), not chosen.
- **The building-facts fallback starts once characteristics, assessments and the outline are in** (Item 81 point 4; it waited for the parcel flags), and with an exact 14-digit PIN the core lookups start beside the parcel row instead of after it (1.4 s p50, Item 81); if the row names another parcel they are redone for it. Both apply to the full path too, with the same output.

**Decision: a 20 s deadline per late source (owner's pick), counted from the source's own start.** Past it the part answers without that source and lists it in `timed_out`; the page says "Couldn't check in time: crime and 311 requests. Retry", never "none", and it is not a failure label. The fetch keeps running so its cache fills, and a Retry joins it or finds it cached. Late sources share a cap of 8 at a time, the retrieval semaphore's (the contract proposed 4: it halved today's parallelism and the whole Profile took 41.5 s p50 locally, so it was raised). The first build counted the wait for a slot against the 20 s, which made queued sources (311, crime trend) time out on a third of visits, fixed. A visitor who leaves (a new lookup, or leaving the page) aborts the requests and the server cancels work nobody else waits for.

**Decision: a per-sale arm's-length flag from the County's own filters** (`property.arms_length`): not under $10,000, not an excluded deed type, not a multi-parcel sale, the three filters the comparables already use; null when the row carries none. Only the parts carry it (`SaleRecord.arms_length` is excluded from every dump, so the full response, chat context and the report are byte-identical). It retires Item 77's client-side deed test.

**What the page does** (`useProfileParts`, `PartsStatus`). The first screen (Item 82), then the Overview in the same screen (one component per lookup, so the map is never remounted; the Playwright check marks the canvas before the Overview and finds it after every part), then the late parts once the Overview has painted, each named while it waits ("Still checking: nearby sales, TIF reports and grants, …"). Ask, Sources and Export read the whole Profile, so they turn on once every part has answered; then the assembled Profile goes to the parcel context (`adopt`) for chat grounding, so grounding still reads the full shape. Strings in English and Mexican Spanish (usted).

**The owner's localhost review (2026-11-08).**
- *Search on the Profile (for Phase 6):* "Look up another address" should be pinned to the bottom of the screen and stay there on every Profile tab, so a visitor can search again without scrolling down to the end of the page. Deferred by the owner to Phase 6, built with the phone layout (the bottom of the screen also holds the preview badge, the expanded map's controls and the phone keyboard).
- *Fixed here:* the line before the first screen said "A first lookup can take 15 to 40 seconds" with a seconds counter; the Overview now follows within seconds, so the line and counter are gone (the address being looked up stays).
- *Skeletons (owner: "the outline of the website that loads ... before the whole thing comes in"; before, one dark pulsing box).* **Built here:** the moment before the first screen draws the Profile's own outline in its final sizes (`ProfileSkeleton`: the map band with the address, the tab bar, the answer's line, the four tiles in their pale stat colors), so the first screen fills that exact shape. **Rule for Phase 6 and later:** every block that waits on a late part shows its own skeleton in its final size and shape (a chart: its axes and a faint placeholder; a map layer: the map with a small "Loading crime…" tag), named while it waits; if its source passes the deadline it says "Couldn't check in time · Retry" in that same place, never a blank. Seen on the way, not changed: while the browser downloads a new page's code, the preview shows an empty page (`VersionedRoute`'s Suspense fallback is blank, mostly noticeable on the dev server); Phase 6 should give that moment the frame's outline too.

**Alternatives considered:** keeping the full response and only caching more (the cold first visit is the slow case); hard timeouts on today's endpoint (a product change on the live page); streaming (above).

**Revisit if:** production `scorecard part timings` lines show the Overview over 8 s at p95 on exact parcels; the deadline fires on more than about 10% of first visits for any source (then look at that source, not the deadline); the builder test reads the late fill-in as broken; the old Profile's route flips (then it moves to the parts and `/api/scorecard` serves chat and the report only).

**Numbers:** 2026-11-08, MacBook Pro arm64, home network, in-process (`PYTHONPATH=. python -m eval.profile_latency --parts`, PROFILE_TIMINGS on for spans); the 7 parcels of Item 81 plus 4 fresh ones (`PHASE4_FRESH`); a visit = the first screen and the Overview together, then every late part the Overview names, together; cold = every TTL cache emptied first; nearest-rank percentiles. **The City portal was slow all evening**: the first screen alone took 3.5–3.6 s p50 in every run (Item 81: 1.9 s; production, Item 87: 2.5 s), so these are pessimistic.

| Run (results in `eval/results/2026-11-profile-latency/`) | Overview, exact parcels p50 · p95 (n) | Overview, approximate p50 | whole Profile p50 · p95 | deadline fired (of 55 cold visits) |
|---|---|---|---|---|
| Item 81 baseline: Overview deps as ordered today / full response | 15.7 s · 45.9 s / 26.8 s · 46.0 s (35) | – | 26.8 s · 46.0 s | – |
| `parts-local-2026-11-08`: first build | 5.99 s · 17.40 s (45) | 17.9 s | 26.5 s · 45.4 s | 311 17, crime YoY 10, incentives 5, violations 4, neighborhood 4, … |
| `parts-diag-2026-11-08`: same, with spans | 7.05 s · 26.18 s (18) | 19.3 s | – | – |
| `parts-local-2026-11-08b`: + City building records late, deadline from the source's start | **4.13 s · 10.73 s (45)** | 16.7 s | 41.5 s · 66.0 s (cap 4) | incentives 18, 311 13, crime 7, neighborhood 7, building 5, crime YoY 5, history 5, ARO 2 |
| `parts-smoke-2026-11-08c`: + cap 8, candidates and tract off the Overview, grants/ARO 24 h; the three slowest parcels of run b only | 3.5–4.8 s (3; 5.6 s in round 0) | – | 17.0–26.6 s (3) | incentives 1 of 3 |

- What held the slowest Overviews of run b (spans): resolution at Address Points 10.8 s (p4_uptown, 20.0 s), the Census tract 16.0 s (fresh_north, 18.6 s), the address candidates 10.7 s and 8.2 s (twoflat, p4_westtown), County sales 8.7 s (downtown). The last two fixes take the tract and the candidates off the Overview; a slow resolution or County sales request can still hold it (single public requests; nothing on our side to shorten).
- Warm (run b): Overview 31 ms p50 / 1.56 s p95 on exact parcels; whole Profile 2.6 s p50 (its p95 20 s = sources still past the deadline from the cold visit, by design).
- First screen (run b, cold): 3.58 s p50 / 10.11 s p95.
- Approximate parcels wait on County GIS (Item 81 point 3, about 10 s), so their Overview is reported apart.
- **Not measured:** run b's full panel with the last fixes (the owner asked for no more hour-long local runs); production (after deploy, one visit at a time, as in Item 87; the `scorecard part timings` lines give the per-part split).
- The eval script can hang at interpreter exit on idle worker threads after writing its results (seen once, local); it is not a request path.

---

## Item 90: Phase 5 (M1), the map stack: MapLibre over a base made from the City's own streets (2026-11-08)

**Status: decided by the owner on the measurements below (2026-11-08), before any of the look was built.**

**Decision: the new UI's maps run on MapLibre GL (6.15) with our own vector tiles and our own style document; deck.gl stays (`MapboxOverlay` works on MapLibre).** Owner's pick over keeping Mapbox with a custom style. Today's pages keep Mapbox until their routes flip (Phase 10 deletes it with the old UI).

**Decision: the base is ours, cut from government data.** Roads from the City's street centerlines (`pr57-gg9e`: 57k segments, `class` 1 expressway, 2 arterial, 3 collector, 4 local, street names, one-way, z-levels; rows last updated 2021), with parks, the lake and the river, drawn dimmed in light and dark. Chicago only: outside the city the map is a plain dim fill. Owner's pick over a hosted OpenStreetMap vector base (OpenFreeMap: free, keyless, no SLA) and a keyed raster like the reference's.

**Decision: street names use Noto Sans glyphs committed to the repo** (Latin ranges from `protomaps/basemaps-assets` at commit `028c18f`, SIL Open Font License, license file beside them), served by us. Owner's pick over OpenFreeMap's font server.

**Decision: only the Profile's map moves in Phase 5;** Discovery's map moves with its route in Phase 6 (owner). **The builder test stays undated** (Item 88; owner).

**Evidence (2026-11-08, this Mac: Playwright Chromium on the real GPU, ANGLE Metal / Apple M4 Pro; cache off).** Same view on every stack: 1601 N Milwaukee at zoom 16 with our parcel tiles (community areas 22 and 24, built from the citywide 2026-10-29 index). Desktop 1440×900 at 2×; "phone" 390×844 at 3×, touch, CPU slowed 4×. Frame rate = frame intervals over an 8 s scripted pan and zoom between zooms 14.5 and 17. First view = bytes transferred until the map first went idle.

| Stack | Library (gzip) | Base, first view: desktop / phone | Our parcels: desktop / phone | Frame rate: desktop / phone |
|---|---:|---:|---:|---|
| Mapbox GL 3, `light-v11`/`dark-v11` (today) | 511 KB (worker inside) | ≈442 / ≈288 KB | 81 / 44 KB | 60 / 60 fps, p95 16.8 ms, no frame over 50 ms |
| MapLibre 6.15 + OpenFreeMap vector | 285 + 143 KB worker = 428 KB | ≈560 / ≈408 KB (incl. a 120 KB sprite) | 81 / 44 KB | 60 / 60 |
| MapLibre 6.15 + CARTO raster, dimmed | 428 KB | 73–89 / 31–38 KB | 81 / 44 KB | 60 / 60 |
| MapLibre + the City's streets (estimate) | 428 KB | zoom-16 view: 516 segments, 14 KB as gzipped GeoJSON | 81 / 44 KB | not measured |

- **Frame rate didn't separate the stacks** on this machine (the CPU slow-down doesn't slow the GPU); a real phone is the check that counts.
- **The base is the heavy part of a first view**; a hosted vector base costs 300–560 KB, our streets about 15 KB close in.
- **CARTO's free raster tiles now carry "API KEY REQUIRED" watermarks**, so a raster base like the reference's means a keyed or paid service.
- **Mapbox bills per map load** (each `new Map()`; about 50,000 a month free, then roughly $5 per 1,000 per third-party pricing write-ups; not confirmed on mapbox.com). MapLibre with our tiles has no per-load bill.
- `mapbox-gl` rides in today's main chunk (the app imports every page eagerly), so a `?ui=next` visitor downloads both libraries until today's maps load lazily or are deleted; that split is a separate, cheap win (not done here).

**Revisit if:** a real phone drops frames on the new map; the City stops publishing street centerlines or they fall far behind (then OpenFreeMap or Protomaps tiles of OSM roads, attributed); Mapbox's billing stops mattering.

**Numbers:** above; harness (bench page, tile server, Playwright runner) kept in the session notes, not in the repo.

---

## Item 91: Phase 5 (M1–M3), the one map: our tiles, its gates, and what it does (2026-11-08)

**Status: built on `feat/ui-next-phase-5-maps`, checked locally; waiting for the owner's look review against the Cities: Skylines reference in light and dark (Item 80's gate).** Production also needs the two tile files built once on the server (below).

**Decision: three tile sets, all ours, served by one route.** `GET /api/map/tiles/{base|zoning}/{z}/{x}/{y}.mvt` (MBTiles on the `backend/data` volume, 404 = not installed, 204 = empty, gzipped, a day of caching) plus Discovery's parcel tiles (Item 68) for the lots; `GET /api/map/info` says which are installed. The encoder is Item 68's hand-written one, extended with lines, points, several layers per tile and per-layer minimum zooms (`backend/map_tiles/tiler.py`); no new dependency.
- **Base** (`base_tiles.py`, zooms 10–16): the City boundary as land, water incl. the lake (`knfe-65pw`), Park District parks (`ejsh-fztr`, from 11) and street centerlines (`pr57-gg9e`) as highway / major / minor / local / ramp with sign-style names (arterials from 10, collectors and ramps from 12, locals from 13). Lower-level streets, river lines, runways and proposed/vacated/closed segments are left out and counted. Citywide: 54,557 road segments, 617 parks, 605 water shapes, 8.4 MB, 72 s; largest tile 3.9 KB at 16, 15 KB at 14.
- **Zoning** (`zoning_tiles.py`, zooms 13–16): the City's Zoning MapServer layer 1, all 15,043 districts with their source attributes (zone class and type, ordinance number and date, case number, PD number, PMD sub-area, Clerk document number; staff user ids are not copied), plus a `family` and intensity `level` for color, and one label point per district part (polylabel, from a zoom by size). 11.3 MB, 18 s; largest tile 93 KB at 13, 8.8 KB at 16.

**Decision: zoning is never simplified.** Shared-edge simplification (`coverage_simplify`) was tried and refused: the City's layer is not a valid coverage (`coverage_is_valid` false; 124 districts needed repair), so its output can't be trusted. The tiles carry the source polygons quantized only to the tile grid (about 0.9 m at zoom 13, 0.1 m at 16), which ends the sliver problem (research/15 §1.2) and can't move a lot's district. Cost: payload at zoom 13 (93 KB tiles), hence zoning starts at 13. Streets stay visible because roads draw above zoning, never by clipping zoning to blocks. *Alternatives:* per-feature simplification (the old slivers), clipping zoning to blocks (rejected in Item 75).

**Gate: boundary accuracy** (`PYTHONPATH=. python -m eval.zoning_tile_accuracy --boundary 400`, no network, 7 s). For the lot panel (97 of 100 with an outline), the 13 data-health sentinels and 400 seeded boundary parcels (a PTAXSIM outline touching two or more districts), the district by largest share and at the representative point, from the source and from the decoded tiles at each zoom 13–16: **0 differences in 2,040 comparisons; all 13 sentinels match their answer key.** A recorded-fixture test does the same on a point grid at every zoom (`test_map_tiles.py`).

**Decision: one MapLibre map per page, never remounted** (`ui-next/map/NextMap.tsx`). The Profile hands it the active tab's `view` (camera + On / Dim / Off): Overview = zoom 17 at the lot, zoning dimmed, lots, recent sales and transit on; Build = zoom 15.6, zoning on, sales off, transit dimmed. A visitor's choice holds until the tab changes. Camera moves ease, or jump under reduced motion, and never take focus. **A theme switch repaints every layer in place** (`themePaint`), so sources, feature state, the camera and the key survive it (no style reload). The Playwright check still finds the same canvas across every Profile swap.
- **Look** (`mapStyle.ts`): light = pale cool land with streets as white gaps and warm arterials; dark = dim gray land with the reference's warm arterials and quiet gray side streets; zoning in Item 74's provisional family hues, four steps darker as intensity rises, fill 0.42 light / 0.30 dark, thin same-hue outlines; parcel lines at 14–16% ink; street names from zoom 15; district codes as labels; this lot black with a white edge (white with a dark edge in dark), dashed when the match is approximate.
- **The key builds itself:** one row per layer with something to show, its count on screen ("14 districts", "285 lots", "1 station"), On / Dim / Off (Dim = opacity × 0.3), and the districts in view with their colors. It starts collapsed on a map under 440 × 640 px (the Profile's band) and open on the expanded map.
- **Every outline opens something:** a lot → its address, use and "Open its Profile" (`/api/discovery/parcel` by PIN10), and the lot is marked; a district → its code and ordinance; a sale → price and date. The lot's own outline is marked in the parcel layer by feature-state (exact matches only).
- **Late layers follow Item 89's skeleton rule:** recent sales wait on the `money` part; the map says "Loading recent sales…" in place, and "Couldn't check recent sales in time · Retry" when the source passed the deadline.
- **Failure states:** no WebGL → a note in the map's place, the page works; no base file → "Street map not installed" over the parcels and zoning; a lost GL context is swallowed so the browser restores it. *Not shown:* Sentry's "Failed to initialize WebGL" can only be checked after deploy.

**Gate: first-view payload** (this Mac, local stack built the production way with relative API URLs, cache off; transferred bytes until the map settled). Library: MapLibre 285 KB + worker 143 KB gzip (Mapbox was 511 KB; both still ship until today's maps load lazily, Item 90).

| View | Base | Zoning | Lots | Glyphs | Total map data |
|---|---:|---:|---:|---:|---:|
| Before (Item 90): Mapbox `dark-v11`/`light-v11`, desktop / phone | ≈442 / ≈288 KB | – | – | (inside) | ≈442 / ≈288 KB |
| Overview, desktop (zoom 17) | 6.5 KB | 21.4 KB | 29.3 KB | 150.6 KB* | 208 KB* |
| Overview, phone | 3.1 KB | 11.8 KB | 14.4 KB | 150.6 KB* | 180 KB* |
| Build, desktop (zoom 15.6; after the Overview) | 21.6 KB | 72.5 KB | 128.9 KB | – | 223 KB |
| Build, phone | 9.1 KB | 33.5 KB | 60.3 KB | – | 103 KB |

*Measured with two font weights from the dev server, uncompressed. Since then the second weight is dropped and nginx gzips glyphs (one 0–255 range: 76 KB raw, 46 KB gzipped), so production should spend roughly 50–60 KB on glyphs; to re-measure after deploy.

**Gate: frame rate.** 60 fps with no frame over 50 ms on this Mac for every stack (Item 90); the page's map is the same engine and tiles. **Not measured on a real phone** (owner's phone at the localhost review, or after deploy).

**Gate: coverage.** Base and zoning cover the whole city; lots = Discovery's tiles (604,220 outlines, 0.14% of PIN10s without one, Item 68).

**Production steps (once, on the server, then monthly with the index timer later):** `docker compose run --rm --no-deps backend python -m backend.map_tiles.base_tiles` and `... python -m backend.map_tiles.zoning_tiles` (they read the City portal and the zoning layer; outputs and a source copy land in `backend/data/`). Until then the new map shows "Street map not installed" with lots only. Also new in this change: the CSP allows same-origin workers (`worker-src 'self' blob:`, MapLibre's worker) and nginx serves `/map/fonts/` gzipped with a month's caching (not syntax-checked locally: no Docker or nginx on this Mac).

**Not done, for later:** a refresh timer and data-health sources for the two tile files (zoning changes with every passed map amendment; the base rarely); Discovery's map (Phase 6, owner); the zoning palette's final check at real size by the owner (Item 74 still calls it provisional); deck.gl isn't used by the new map (nothing needed it yet).

**Revisit if:** the owner's review asks for a different look; a phone drops frames; zoning tiles at zoom 13 matter (then a valid shared-edge simplification after repairing the coverage, re-run through the accuracy gate).

**The owner's first look (2026-11-08), changed the same day:**
- **On / Off only.** Dim is gone ("it looks much better with On"); zoning is on in both tabs. With zoning dimmed, the side streets and the districts had blurred into one shade.
- **Streets at their real width.** From zoom 14 up each street class is drawn in ground metres (local 16 m, collector 20, arterial 24, expressway 34, ramp 8: a little under Chicago's usual right-of-way), scaling with the map, so a street fills the gap between the lots on either side. Below 14 they keep a readable minimum. In dark the side streets are lighter grays (`#6B7178` / `#8A9097`) so every street shows, not only the arterials.
- **Map controls like a full-page map.** No +/- buttons. In the expanded map the wheel zooms at once; in the page band the wheel still scrolls the page until the map is clicked (so the page can't get stuck on the map). The expand button sits in the bottom-right corner.
- **"Back to the property"** appears once the lot leaves the middle of the view or the zoom moves more than 1.5 steps from the tab's; it eases back (jumps under reduced motion).
- **The key fits the band:** it scrolls inside the map's height instead of running off it.
- **Why the lot looks wavy (found, not changed):** PTAXSIM stores every parcel outline rounded to 5 decimals (about 1 m), so straight edges step. The County's own parcel layer has full precision (`77tz-riq7`, the 2021 vintage, the newest published with geometry). Swapping the source for the map's lot and lot tiles is the owner's call.
- **How the reference draws roads and buildings:** OSM street centerlines as colored lines of set pixel widths per class over building footprints (OSM buildings); streets read as gaps because the fills are buildings, not lots. Building footprints for us would come from the City's footprints (`syp8-uezg`, last updated 2015) or an outside source; the owner's call.

---

## Item 92: the map draws lots from the County's full-precision outlines where they still match (2026-11-08)

**Decision (owner, "Yes, switch outlines", 2026-11-08): the new map draws each lot from the County's GIS parcel layer at full precision, and falls back to PTAXSIM's outline only where the County's no longer describes today's lot.** PTAXSIM stores every outline rounded to 5 decimals (about 1 m), so a straight edge drew as small steps (the owner's "wave" on 1601 N Milwaukee). The County's newest layer published with geometry is 2021 (`77tz-riq7`, "ccgisdata - Parcel 2021").
- **The rule** (`backend/map_tiles/county_outlines.py`, `still_matches`): the County's outline is used when its area is within 10% of PTAXSIM's newest outline and the two overlap by at least 85% (intersection over union). A lot split, merged or redrawn since 2021 keeps PTAXSIM's newer outline.
- **Where it applies:** the lot tiles (`parcel_tiles.load_parcels` reads the local copy when it exists; Discovery's map draws the same tiles, so its outlines sharpen too) and the subject lot (`GET /api/map/lot?pin10=`, which the new map uses in place of the page's rounded outline). MapLibre's own GeoJSON simplification is off for the lot (`tolerance: 0`).
- **Where it doesn't:** land area, every Profile figure, capacity, the report and chat still read PTAXSIM exactly as before. This is drawing only.
- **The copy:** `python -m backend.map_tiles.county_outlines` reads Chicago's 612,202 rows (604,830 PIN10s; pieces of one PIN10 united), refuses a read under 500,000 rows, and writes `backend/data/county_outlines_2021.db` (108 MB, 99 s) atomically.

**Numbers (this Mac, citywide, 2026-11-08):** of 604,220 lot outlines, **593,658 (98.3%) now draw the County's outline** and 10,562 keep PTAXSIM's; tile file 28.7 MB (largest tile 74 KB at zoom 14, 10 KB at 16); 133 s. The lot endpoint returns the County outline for 1601 N Milwaukee (12 vertices at full precision, where PTAXSIM's had 15 steps). Zoning accuracy (Item 91) is unaffected: it reads PTAXSIM outlines on purpose, the same lots the Profile reasons about.

**Alternatives:** keep PTAXSIM (the wave stays); the County's live GIS service (times out, Known Issues); smoothing PTAXSIM's outlines (changes the shapes, rejected).

**Production:** once on the server, `docker compose run --rm --no-deps backend python -m backend.map_tiles.county_outlines`, then rebuild the lot tiles (`... python -m backend.discovery.parcel_tiles`; the monthly index rebuild also picks the copy up from then on). Without the copy everything draws PTAXSIM's outlines, as today.

**Revisit if:** the County publishes a newer parcel layer with geometry (swap the dataset id and re-fetch); the fallback share grows past about 5% (the copy has aged); a lot's two outlines disagree in a way the 85% rule misses.

**The owner's second look (2026-11-08):**
- **Tried and reverted the same day (owner):** near-black side streets in dark, and parks and water redrawn in a new green and blue. The owner preferred the earlier street grays and park green ("the colors aren't in harmony").
- **Kept: water draws above the zoning fill.** The City zones lagoons with their parks (POS), and the zoning fill covered the water, so a lagoon barely showed. Now water draws over zoning in its original color; parks stay under the zoning, so their green is the POS fill over the park color, as before.
- **Why some streets are colored:** the City's own centerline class (`pr57-gg9e`): North, Chicago and Ashland are class 2 arterials (warm); Damen, Division and Milwaukee are class 3 collectors (drawn gray like side streets). The owner: no change needed.
- **Wheel zoom on the first turn after Expand:** growing the map to full screen fired a pointer-leave event that switched the wheel off; it now turns back on when the pointer moves over the expanded map (checked: the first turn zooms 17 → 16.4).
- **Not resolved:** what the owner saw as park buildings versus parkland. The map draws no buildings yet; footprints are a separate decision (Item 91, above).
- **Noted for later (owner):** a land-use map with surface parking: map track M5 (Phase 7); CMAP's 2020 Land Use Inventory has a surface-parking category.

---

## Item 93: zoning on the new map comes in NAD83, so it sits on the lot lines (2026-11-08)

**Found by the owner:** zoning sat consistently a little west and north of the lot lines (under a meter).

**Cause:** the City's Zoning MapServer stores districts in Illinois State Plane East on NAD83 (`wkid 102671` / `3435`). Asked for `outSR=4326` (WGS84), the server applies a NAD83→WGS84 datum shift: in Chicago about 0.48 m west and 0.87 m north (measured on one district: 4326 `-87.70426365, 41.81542837` vs 4269 `-87.70425788, 41.81542054`). Every other layer the map draws (the County's parcels, the City portal's streets, parks, water) is NAD83 latitude/longitude as published, with no shift.

**Decision:** the zoning tiles request `outSR=4269` (NAD83) (`zoning_tiles.OUT_SR`). Measured on 4,363 zoning boundary points in three neighborhoods against the nearest County lot edge: mean offset **+0.05 m east, +0.10 m north, median 0.00 m** (before: about 0.5 m west and 0.8 m north of the lot lines, median about 1 m).

**Accuracy gate re-run** (`eval.zoning_tile_accuracy --boundary 400`): 0 differences in 2,040 comparisons. With zoning and lots now coinciding, a few sample points fall within one tile unit of a district line (10 at zoom 13, 6 at 14, 3 at 15, 1 at 16): those are counted and compared by area only, because tile coordinates can move an edge by up to one unit (0.9 m at 13, 0.1 m at 16). The one zoom-13 point that differed was 0.18 m from a line; its lot's district by area matched.

**Also (owner):** the "Loading recent sales…" tag no longer shows in the expanded map; the key's row says it.

**Not changed here (a separate task):** the live Profile's district lookup (`retrieval/zoning.py`) and today's zoning maps also send and receive `4326` while our points are NAD83, so they carry the same ~1 m shift. It matters only for a point within about a meter of a district line, but it changes live answers, so it needs its own measurement on the lot panel and sentinels before any change.

---

## Item 94: Street View as a link out to Google (2026-11-09)

**Decision (owner, "Yes, link-out"):** the new map offers Google Street View by opening Google's public Maps link in a new tab (`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lon>`; Maps URLs need no key, no account and no billing; only the coordinates leave the page, and Google snaps to the nearest panorama).
- **On every map card** (a lot, a district, a sale): "Street View (Google)", at the clicked point (a sale: its own point).
- **In the expanded map:** a "Street View" button under the address; while on, the cursor is a crosshair and a hint says "Click a street to open Street View · Esc cancels"; the next click opens Street View there and the mode turns off (no card opens). Esc cancels without closing the expanded map. Not in the page band (no room; the card link covers it).
- Cards opened near the map's bottom edge now open above the click.

**The owner's first try (2026-11-09): it often opened the alley behind the lot, not facing the building.** Google opens the panorama nearest the point it is sent, and a point inside a lot is often nearer the alley. Now the viewpoint is moved onto the street first (`map/streetView.ts`, `viewpointFor`): for a lot, the nearest spot on its own address street (the address from the lot lookup, matched to the City centerline names in our base tiles); otherwise the nearest named, non-expressway street; within 60 m, else the point as clicked. The link carries a `heading` facing the clicked place. Checked on 1530 N Milwaukee Ave: the link stands 0.0 m from N Milwaukee Ave's centerline facing 220° (toward the lot). Tests: `map/streetView.test.ts`.

**Alternatives:** a draggable figure like Google's (about a day more for the same result as click-to-open); Street View inside the page (needs a Google API key, and Google's terms are stricter about its imagery beside another map; not worth it); Mapillary (free and open, patchy Chicago coverage).

**Revisit if:** builders ask to see frontage without leaving the page (then price the Maps Embed API's Street View mode, which needs a key), or Google changes the Maps URL format.

**Numbers:** checked in the browser with `window.open` stubbed: the mode's click opened `…viewpoint=41.909845,-87.677183` with `_blank` and `noopener,noreferrer`; the card link's `href` and `target="_blank"` checked; test `map/mapInfo.test.ts`.

---

## Item 95: points as pins, a key that explains zoning by color family, and "Show" for off-screen points (2026-11-09)

**From the owner's review:**
- **Recent sales and transit are map pins** (`map/pins.ts`), like Google Maps': a teardrop with a white edge and a soft shadow, its tip on the point, a white Lucide icon inside ($ for a sale, a train for a station), 32 × 42 px drawn at 2x, slightly smaller below zoom 15.5; drawn above every other layer, labels included, never hidden by collision. Sales use Coastal's Spruce `#355E58` and stations ink `#1C1C1C` (Item 74: maps use Sapphire, Spruce and black). They replace 6 px dots that disappeared under the zoning fills. Our own icons, not Google's yellow figure or pin art.
- **Points out of view are said, not lost.** The owner could find only one of three sales: all three sat about half a mile north of the lot (0.44–0.53 mi), outside the default view. When some of a group's points are off screen the key says "0 of 3 in view" with **Show**, which fits the map to the lot and those points.
- **The key explains zoning by color family**, for the families in view (Residential, Business and commercial, Manufacturing, Downtown, Planned development, Parks and open space, Transportation), each with a lighter and a darker swatch and "Darker = more intensive (taller, denser)", instead of up to eight individual district codes. The codes stay on the map as labels.
- **Kept simple (owner):** no drag-a-figure Street View; the card link and the expanded-map mode are enough.

**Numbers:** checked in the browser at 1601 N Milwaukee Ave (dark): key reads "Recent sales 0 of 3 in view · Show", "Transit 1 of 3 in view · Show"; Show framed the lot and all three sale pins. Tests: `mapStyle.test.ts` (pins are the top two layers), `streetView.test.ts`, `mapInfo.test.ts`.
