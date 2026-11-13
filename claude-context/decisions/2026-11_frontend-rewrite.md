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
- **Production, after the deploy** (2026-11-08, PR #210 merged as `3d5025b`; `parts-prod-2026-11-08`; 4 addresses nobody had opened, one visit at a time from a home connection outside the US through Cloudflare, each visited twice, as in Item 87): first screen 1.4–7.6 s (p50 2.1 s); **Overview on exact parcels 3.1, 7.2 and 7.9 s** (n=3; one approximate match 11.7 s); whole Profile 22.6–32.8 s (p50 25.0 s), a few seconds over Item 87's single response (20.4 s p50), the expected cost of starting the late parts after the Overview; deadline fired twice in 4 first visits (City lists once, 311 once). Repeat visits: Overview 0.6–2.1 s, whole Profile 2.1–4.0 s. n=3 can't show a p95; the server's `scorecard part timings` lines (the owner pulls them, as for this Item's first numbers) are the next read.
- **Not measured:** run b's full panel with the last fixes (the owner asked for no more hour-long local runs).
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

---

## Item 96: the property stands out, and gets its own pin when zoomed out (2026-11-09)

**From the owner's review:** the lot was only a slightly different shade from its neighbors, and it disappears when the map is zoomed out.
- **The lot stands out:** a fill in "this lot" ink over the zoning (black at 30% in light, white at 32% in dark), a wider contrasting edge (6.5 px) and a 3 px line (was 5 px and 2.5 px, no fill). Approximate matches stay dashed.
- **The property's own pin** (`lot-pin`) below zoom 15.5 (where a lot is roughly 15-30 px wide): a house in "this lot" ink, black with a white edge in light and white with a black edge in dark, on top of every other pin. A theme switch swaps its image in place (a layout property, set beside the paint).

**Numbers:** checked in the browser at 1601 N Milwaukee Ave in dark and light, close in (no pin, filled lot) and zoomed out (house pin above the sales and station pins). Test: `mapStyle.test.ts` (the property's pin is the top layer).

**Color-blind check (owner's question, 2026-11-09; measured, nothing changed yet).** The zoning fills as drawn (family color at 42% over the light land, 30% over the dark), Machado 2009 simulation, OKLab ΔE×100 (under about 6 is hard to tell apart; 6-10 needs labels):
- Even with full color vision some families sit close because the fills are pale: downtown vs transportation 3.5, residential vs planned development 3.6, park vs planned 4.0 (light; dark slightly lower).
- **Protanopia:** business vs transportation 1.0 (the same color), park vs planned 3.0, downtown vs transportation 3.1, residential vs planned 3.4. **Deuteranopia:** park vs planned 2.2, downtown vs transportation 2.9, residential vs planned 3.0. **Tritanopia:** residential vs planned 1.7, park vs planned 2.5.
- The weak pairs mostly involve the two gray families (planned development, transportation).
- **What already does not depend on color:** every district's code is on the map as a label (by size, from zoom 13), a click names the district, and the lot (light/dark fill and outline), the pins (icon shapes: $, train, house), the streets (width) and the approximate-match dash all read by lightness or shape.
- **Candidate fix, for the owner:** a texture for the two gray families (a light diagonal hatch for planned development, a dotted fill for transportation) so they no longer depend on hue, leaving the main colors as they are.

---

## Item 97: textures for the two gray zoning families (2026-11-09)

**Decision (owner, "Yes, add textures", after the color-blind check in Item 96):** planned development gets a light diagonal hatch and transportation a dot grid (`map/patterns.ts`, layer `zoning-texture` over their fill), in the lot's ink at low opacity (black ~40% in light, white ~38% in dark); the key's swatches show the same textures. The colors themselves are unchanged.

**Changed the same day (owner):** the hatch became small separate "+" marks (3 px arms on an 8 px grid): continuous lines, diagonal or straight, read like the lot lines they sit among. Transportation keeps its dots. The key's swatches use a stronger ink so the marks read at 16 px.

**Changed again (owner):** planned development's fill moved from gray `#C9CED6` to Coastal's Bubblegum `#FDC1B4` (the gray took over downtown, where most districts are PDs). Of seven candidates measured against the other families as drawn, it stands furthest from all of them (min ΔE×100 5.0 light / 4.3 dark, vs residential); the "+" marks keep it apart for color-blind readers. Not yet looked at downtown in the browser (usage limit).

**Effect:** the weakest pairs (business vs transportation ΔE 1.0 under protanopia; park, residential or downtown vs the grays at 1.7-4.0 under the three deficiencies) are now told apart by texture, not hue. Checked in the browser: the marks on PD 1235/1258/58 (and, before the change, hatching on PD 569/847) in light and dark; dots on the 606 trail's transportation strip.

**What still depends on color (measured, ΔE×100 of the fills as drawn):** among the five colored families the closest pairs are residential vs downtown 3.6 (protanopia, light), business vs manufacturing 4.2 (deuteranopia) and 3.5 (tritanopia), residential vs park 3.2 (tritanopia, dark); with full color vision residential vs business is 6.4 light / 5.5 dark. These lean on the district-code labels and the click card. Residential and downtown are rarely neighbors.

**Revisit if:** a color-blind tester still confuses business and manufacturing (then a second texture for manufacturing, or Item 74's "Teal and coral" alternative, which passes the color-blind check more cleanly).

---

## Item 98: parks read as parks, the two textures swapped and softened, failed tiles retried (2026-11-09)

**From the owner's review:**
- **Parks zoned as planned developments looked like downtown.** The City zones some lakefront parks as PDs (Northerly Island PD 618; the Museum Campus PDs 664, 778, 794; Millennium Park PD 677), so they took the PD color. The Park District's outlines now draw over the zoning fill and textures in the open-space look (`park-top` = the park color, `park-tint` = the POS green at the zoning opacity, part of the Zoning group); district outlines and labels stay above, so a park's zoning code is still on the map. Millennium Park is run by the City, not the Park District, so it is not in that layer and keeps its PD look (said, not hidden). Checked: the Museum Campus parks read green with their PD labels.
- **The two textures swapped, and planned development took transportation's look** (owner: the gray with dots suits the far more common PDs): planned development = gray `#8F959C` with dots; transportation = Bubblegum `#FDC1B4` with "+" marks.
- **Softer textures:** ink at about 23% instead of about 40%, a 10 px repeat instead of 8, dots of radius 1 px, so the lot lines stay readable through them.
- **Square holes after zooming out and in (owner, at 1259 N Wood St).** Not reproduced here; every tile in the three files decodes with MapLibre's own parser (`@mapbox/vector-tile`: 4,309 zoning, 6,387 base, 4,143 lot tiles, 0 failures), the server logged no errors and only the two empty lake tiles are absent at zoom 13. The likely cause is a tile request that failed during a fast zoom: MapLibre does not retry it, which leaves exactly one tile-sized gap. The map now reloads that source's tiles 1.5 s after a tile error (at most every 4 s) and logs other map errors as warnings. **Revisit if** a hole still appears: note the address and theme, and check the console.

- **Tried (owner's question, pending his call):** the planned-development dots in Coastal's Sapphire (deeper teal in light, lighter in dark) instead of ink, radius 1.2 px; the fill stays gray. At this size the color reads as a faint accent rather than a pop; a stronger effect would need bigger or denser dots, which start to compete with the lot lines again.

**Planned development, in one line (owner's question):** a site-specific zoning district Council adopts by ordinance for a large or special project (required above certain size or height thresholds, along the lakefront and in some downtown areas), with its own rules on uses, height and density in place of the base district's; it can cover a single building or a whole campus, and its number points to that ordinance.

**Owner's call on the teal dots (2026-11-09): back to gray** (the try was reverted). **Noted for later (owner):** the darkest downtown blue (`#2A6488`, DX/DC-12 and up) sits close to the water color, especially the river through the Loop in dark; revisit the downtown ramp or the water color when the zoning palette is settled (Item 74 still calls it provisional).

**Phase 5 approved (2026-11-09):** the owner reviewed the map on localhost in light and dark against the reference and gave a thumbs up after the reviews recorded in Items 91–98. Item 80's gate is met for the Profile's map; Discovery's map follows in Phase 6.

---

## Item 99: Phase 6, the Money tab, and the pinned search bar (2026-11-09)

**Status: approved by the owner ("Thumbs up", 2026-11-09) after five localhost review rounds (below), built on `feat/ui-next-phase-6-money` (cut from Phase 5's branch, rebased onto `main` once #212 merged); **merged and live 2026-11-10 with Neighborhood and the parts fix (PR #215, merge `0a07849`, which carried #214 and #213)**. No route flips (Item 88).** The owner's answers before the build (2026-11-09): Money first, then Neighborhood, History, then Discovery; Discovery marks its matches as lot outlines only (no dots or pins); the builder test runs later, so no route flips yet (Item 88 stands); #212 merges with the first Phase 6 PR.

**Decision: the Money tab takes the shape every tab has (brief, "Property Profile").** One sentence, then one wide visual, then three smaller ones, then a collapsed details table.
- **The sentence:** the tax bill and the Assessor's value ("About $12,478 a year in property tax, on an Assessor's value of $619,000"), plus the nearby sales' median only when the backend shows that median (a withheld median stays out of the sentence). Exempt, nominal and no-bill lots say so in words.
- **Main visual, nearby market sales:** the search's own rule as chips (class "like this lot", radius, years, count, and "Search widened to find enough" when it did), the median and the median per buildable sq ft with the backend's confidence state (both withheld below its sample threshold), a price strip (3 or more sales only: one dot says nothing) and the five newest sales (date, price, per buildable sq ft, zoning, distance); the rest in the details. The same sales are the map's pins.
- **Taxes and value:** the bill with its year and confidence state, its rate beside the class's typical rate (`property.tax_class_norm`, the backend's own figure), where the bill goes (one stacked bar, the four largest taxing bodies and "others"), and the Assessor's value by year (assessed ÷ the class's level; building and land stacked, the latest year in this lot's black).
- **Rent nearby:** the Census's 1, 2 and 3-bedroom medians for the tract (or its PUMA, said), one "Estimate" state for the survey, the area median, and this building's typical unit size in black when the records give bedrooms and units on a residential class (2xx/3xx; bedrooms ÷ units, rounded).
- **Incentives:** TIF, Opportunity Zone, Enterprise Zone, QCT and NMTC as yes / no / not checked chips (a failed source is never "no"); QCT and NMTC are tract-keyed and late (Item 89), so they read "Checking" until the incentives part lands.
- **Details:** assessed value, assessment level, Assessor's value, effective and typical rates, exemptions, tax code, every taxing body's dollars, the tax-class note, and all nearby sales.

**Decision: the Assessor's value is flagged only against this lot's own recent market sale** (brief: "flagged when far below sales"): when it is under 60% of a market sale (the server's `arms_length`) from the last 5 years, one warning line says "The Assessor's value is N% below this lot's YEAR sale". *Alternatives:* against the nearby median (other buildings of other sizes and classes, and the median is often withheld on small samples); a tighter ratio such as the County's 0.9–1.1 sales-ratio band (reassessment cycles and remodels would flag ordinary lots). *Revisit if* builders read the flag as an appeal tip (rule 11: no advice), or the backend gains a sales-ratio figure of its own.

**Decision: the map's Money view frames the lot and its sales.** `MapView.fit` (new) frames the lot plus a group's points when the view opens and once when they arrive late, instead of a fixed zoom; zoning is off on this tab so the sale pins read, parcels and streets stay on. Reason: on both test lots the widened search found its sales about half a mile out, off the band at any useful fixed zoom. "Back to the property" re-frames the same way.

**Decision: "Look up another address" is pinned to the bottom of the screen on every tab** (owner, Item 89): a sticky bar with the compact address field, its suggestions opening upward (`AddressInput dropUp`, a shared prop; today's pages don't pass it), room left under it for the preview badge (52 px tall on touch screens, so 4.25 rem plus the safe area while the preview is on), and the expanded map covers it. The preview badge no longer wraps "Exit preview" to two lines on a phone.

**Also from the carried-over list:** while the browser downloads a new page's code, `VersionedRoute` now shows the frame's outline (`frame/FrameOutline`: side panel, header, map band and a line) instead of a blank page; the new UI formats numbers in Spanish as Mexico's `es-MX`, never Spain's `es` (`profileModel.numLocale`, used by the Build table, the first screen's sentence and Discovery's counts; Item 82).

**Late parts (Item 89's skeleton rule):** the sales block and the rent block each show their own outline in their final shape, named ("Checking nearby sales…", "Checking rent…"), while `money` or `neighborhood` waits, and "Couldn't check in time" or "Couldn't load" with Retry in the same place.

**Gates (local, 2026-11-09):**
- *Words:* 112 visible words on the whole tab with the details closed, 19 on its first screen under the map (2541 N Spaulding Ave, 1024 × 768). The new UI has no budget spec yet; these are the baseline for one.
- *Timing:* the `money` part 14.3 s cold locally on 1601 N Milwaukee (comparables only; the City portal was returning 503s that morning); Overview p50/p95 unchanged (nothing moved into it). Production per-part timing comes from the `scorecard part timings` lines after deploy.
- *Failure states:* a held `money` part shows the sales outline and its name (Playwright); timed out and failed show Retry in place (vitest); a failed incentive source reads "Not checked"; no rent reads "Couldn't check rent today", never "none".
- *Map:* the Playwright check finds the same canvas after the switch to Money; `mapNoSatellite.test.tsx` passes.
- `npm run build`, `npm run test` (1,098), `npm run lint` (67 warnings, the cap), `e2e/ui-next.spec.ts` (with the new Money check, light and dark axe, 360 px) pass.

**Not measured:** how builders read the tab (the builder test, Item 88); production timings.

**Numbers on the two test lots (local, live sources):** 2541 N Spaulding Ave (RS-3 two-flat, class 211): tax $12,478 (2024), 2.02% vs typical 2.1%, Assessor's value $619,000; 1 nearby sale ($395,000, Class 2xx within 0.55 mi, last 5 years, widened; median withheld); 2-bedroom rent $2,106 in black (4 bedrooms ÷ 2 units). 1601 N Milwaukee Ave (B3-2, class 592): tax $82,586, 5.19% vs 5.3%, Assessor's value $1,592,480 (down from about $3.5 M in 2023); 2 nearby sales, median withheld; no unit size (commercial class).

**The owner's first review of Money (2026-11-09), all changed here:**
- *The map's Street View button* (Item 94's expanded-map mode) crowded the map on phones and repeated what a lot's card already offers: removed. Street View stays as the link on every map card.
- *Where the tax bill goes* was shown as a stacked bar and a list: removed, per the 2026-07-07 decision that builders care what they pay (the agencies stay in the CSV and the report). The tax is a number with its year and its rate beside the class's typical rate.
- *Cards stretched to the tallest one in their row*, leaving gaps: the smaller blocks now keep their own height (`items-start`).
- *"Lackluster", and was it the look we scoped?* Only partly: it used blocks and Coastal colors but none of SnowUI's stat cards and thin, legend-heavy charts. Now, per Items 73–74: a row of four stat tiles on the pale stat fills, one key figure each (property tax, the Assessor's value with the below-sale warning, the nearby median, rent for this building's unit size or the area median); the nearby sales as one bar each on a shared scale with the median as a dashed line (Sapphire: none of them is this lot); the Assessor's value as a column chart with a year under every column, ordinary years Sapphire and the latest in this lot's black (white in dark), its value above it (land and building split moved to the details); rent as bars with this building's size in black. Shared `StatTile` in `ui/Blocks` for the next tabs.
- *Definitions that are easy to ask about without crowding the page:* every tile and block title, and each incentive program, is a `Term` (`ui/Term`): the words stay plain, a small Info icon opens a one- or two-sentence definition and "Ask about this", which opens the Ask drawer with a question about this lot written in the box, not sent (the page provides it through `ask/askContext`; it waits like the Ask button until every part is in). Shared `Toggletip` now flips to the other edge when it would leave the window (today's page benefits too).
- *Map:* a framing view's framed camera counts as home, so "Back to the property" no longer shows just because the view framed its sales; the view frames once per visit.

**Owner's open question (not built): a right sidebar for rules** such as "Lakefront protection" or "Flood zone". Recommendation given: no second right panel; the brief's frame rule keeps the right side for the analyst (left for getting around, right for the analyst, never two panels on one side), and `Term` already puts a definition one click from each rule with "Ask about this" opening that right panel. Waiting for the owner's call; if he wants more than a popover (the rule's text, what it means for this lot, the map layer), a rule could open the right drawer in a "rule" mode beside the chat rather than a second panel.

**Owner's call on rules (2026-11-09): the popover is enough for now; a rule panel may be cleaner later.** He prefers reading over asking (questions cost money), so definitions must stand on their own and Ask stays secondary. For a later rule panel: it opens in the right drawer's place (right is the analyst's side, never two panels on one side) and is built for reading (the rule in plain words, what it means for this lot, its map layer), with Ask last.

**Second review round (2026-11-09):**
- *Definitions on a phone:* a floating popover with a 14 px icon is poor on touch (cramped, small target), so below `md` the same icon (44 px hit area) opens a bottom sheet: title, the definition in body-size text, then a quiet "Ask the analyst" link; it slides up and back down (200 ms) over a dimmed page. Desktop keeps the popover. Every definition's Ask is now a muted secondary link ("Ask the analyst").
- *The Ask drawer appeared and vanished with no motion:* it now slides in and out (200 ms, ease-out): on a desktop it widens from the right as the page makes room, on a phone it slides up from the bottom and fades; closing slides it out before it unmounts. A new question while it is open replaces the box without sliding again. Reduced motion skips both. Measured headless with motion on: desktop width 0 → 290 → 377 → 421 px at 0/50/100/300 ms, back to 0 by 150 ms after closing; phone top 659 → 352 → 137 → 33 px.
- *The Assessor's value by year had no scale:* a dollar scale on the left with faint gridlines at 0, half and a rounded top (1, 2, 2.5 or 5 × a power of ten, `niceCeil`), the latest year bold under its column and its value under the chart.
- Not built yet: the Build tab's rule chips using `Term` (next, with Neighborhood and History, unless the owner wants it first).

**Third review round (2026-11-09):**
- *The drawer still jumped at the start and end.* Measured frame by frame (headless, motion on): at the start, focusing the question box inside the still-narrow drawer scrolled its wrapper sideways (`scrollLeft` 66 → 0 over the first frames); at the end, MapLibre resized the map's canvas a frame or two after its box (a 589 px canvas in a 756 px band), flashing a blank strip. Fixed: focus with `preventScroll` (and on return), a wrapper that can't scroll (`overflow-clip`) with the panel anchored to its right edge (the panel stays put while its edge sweeps), and `.ui-next .maplibregl-canvas` stretched to its box between redraws. After: page scroll and wrapper scroll constant through open and close.
- *"How do we tell a builder what a TIF means for this lot without sending him to chat?"* and *"I'd expect those pills to be clickable to open the side tab":* **decision: incentive chips open a program page in the right panel** (`ProgramPanel`), the reading-first rule panel the owner leaned toward. The right side holds one panel at a time (`ui/RightDrawer`, shared with Ask: same slide, Escape, focus return); a program's Ask link swaps the panel to the analyst with the question written in. The page, top to bottom: the program's name and whether this lot is inside; *what it means for this lot* (facts, nothing promised); for a TIF, its years and years left, its fund balance by report year on a dollar scale (this lot's latest year black), the projects it has paid for (TIF and private dollars, top five, link to the City's TIF project dataset `72uz-ikdv`) and City grants in the community area (SBIF is paid from TIF money, NOF from downtown density fees); for NMTC the tract's poverty rate and severe-distress flag; *who decides*; *what it is*; the source; then Ask, quiet. Copy for every program in English and Mexican Spanish, consistent with the chat prompt's wording (QCT's 130% basis, NMTC targeting). *Alternatives:* a second right-side panel beside Ask (breaks the frame rule); a longer popover (cramped, and its icon is a poor phone target). *Not yet:* the Build tab's rule chips (Flood zone, Lakefront protection, …) open the same panel; a TIF layer on the map.
- *A false "No" found while testing (6300 S Cottage Grove, inside the Woodlawn TIF):* when the late parts land concurrently, a later part's response sometimes carries the Overview's membership-only incentives (no tract, no TIF reports) after the incentives part's full answer had landed, so QCT and NMTC read `false` and the TIF's figures are blank. Reproduced against the local backend: 3 concurrent trials, the newest response lost the tract in 2 (sequential requests never do). **Guarded on the page:** a tract-keyed program with no tract reads "Not checked", never "No"; a timed-out or failed incentives part makes QCT and NMTC "Not checked"; a TIF lot whose reports are missing says so (with Retry when the part timed out). The backend cause is a separate fix (proposed as its own task; it also decides what the page keeps as the highest `version`).

**Fourth review round (2026-11-09): Build's rule chips open a page too.** The owner: Build's "Rules on this lot" pills should work like Money's incentive pills. **Decision:** every rule chip is a button opening a rule page in the same right panel (`profile/RulePanel` + pure `ruleModel.ts`); the TIF chip opens the TIF's program page. The page shows whether the rule applies (and "Changes what can be built" when it is verdict friction); *what it means for this lot*, leading with the City's own code-pinned sentence for each record when the backend has one (`OverlayDistrict.detail`, e.g. the Landmarks Commission's approval under §2-120-740), else the backend's computed note (transit-served parking relief, ADU), else our sentence; the City's records with their source links; FEMA's zone and whether it is a special flood hazard area; affordable projects in the community area (ARO); who decides; what it is; the source; Ask last. A Chicago Landmark district on the City's Historic Districts layer (LANDMARK=Y, marked by the backend's "Chicago Landmark district:" sentence) is listed under Landmark as well as Historic district. A failed overlay check reads "Not checked", never "Doesn't apply". English and Mexican Spanish.

**Owner's calls for the Neighborhood tab (2026-11-09):** race and ethnicity are **left out** (the brief's fair-housing steering concern); schools are **in** (which measures and their sources are proposed when the tab is built, from official CPS/ISBE data only). On a phone the owner wants the clearest layout possible and left the form open; the proposal comes with the Neighborhood build, shown on a phone before it is built out.

**Fifth review round (2026-11-09): chart values on demand.** The owner: hovering the Assessor's value bars showed the browser's own tooltip, which "didn't feel like part of the graphic". **Decision:** a shared `ui/ColumnChart` (also the TIF fund chart): hovering a column shows its year and value in a callout drawn above it (dark in light mode, light in dark); a click pins it until the same column is clicked again (Escape also unpins), with a ring on the pinned column; with nothing active, this lot's latest column keeps its value shown, so the chart always states one figure. Each column is a named button (keyboard focus shows the value, Enter or Space pins). No `title` tooltips. One quiet line under the chart says how ("Hover a year for its value; click to keep it shown").

## Item 100: a part's version orders the data it holds, not when its assembly finished (2026-11-09)

**Found while building the Money tab's incentive panel (Item 99):** the TIF panel showed no fund data and QCT/NMTC read "No" for a lot inside them. Against a local backend (no model calls): the Overview for 6300 S Cottage Grove Ave, then every pending part at once (8 threads). In 2 of 3 trials a higher-version response had the Overview's membership-only incentives (`census_tract` null, no `tif_fund_history`, `in_qct` false) after a lower-version one had tract 17031420700 (building v4 had it; history v5 and activity v7 didn't). Run one by one, every part kept it.

**Cause:** nothing rewrote the record (`rec.results["incentives"]` is written only by the incentives part; the incentives module has no shared mutable cache). The response was stamped late. `_part` built its answer as `_response(rec, name, timed_out, await _profile(rec))`: `_profile` snapshots the record synchronously (`_scorecard_data_from`), then awaits `_finish_scorecard_payload` (upcoming zoning and pending text impacts run in a thread), and only after that `_response` took `rec.version += 1`. A part that snapshotted the record before the incentives part landed could finish its assembly after the incentives response and take the higher version. The page keeps the highest version (Item 89), so it replaced the full incentives with the older membership-only ones.

**Fix (`backend/profile_parts.py`):** `_respond` snapshots the record (`_assemble`) and stamps the response (`_stamp`: version, `parts_in`, `parts_pending`, lookup, timed-out lists) in one synchronous step, then awaits `_finish`. The version now orders the data each response holds, so the newest response is never older than another. The candidate PIN lists are copied at the same moment.

**Evidence:** `test_concurrent_parts_never_stamp_older_data_with_a_newer_version` runs every late part at once with an assembly that finishes sooner for each later call, and asserts that every response from the incentives part's version on keeps the tract and QCT, and that the newest has nothing pending. It failed before the fix (`money` v7 had no tract) and passes after. Live on a local backend from this branch, 4 concurrent runs (6300 S Cottage Grove × 3, 4800 N Broadway): every response stamped at or after incentives keeps the tract (e.g. incentives v6, building v7 both 17031420700 with 5 fund-history years). `make test` green.

**Alternatives:** (a) merge on the page (keep each part's newest field-by-field): rejected, every response is meant to be the whole Profile so far, and the page's highest-version rule is right once the version means what it says; (b) a per-record lock across the whole response: rejected, it serializes the thread work for nothing; (c) re-snapshot after the finish: the finish mutates the context it was given, so a second assembly would double the work. The new UI's guard stays (`moneyModel.ts` `incentiveChips`: no tract reads "Not checked").

**Revisit if** a part needs to await between reading the record and stamping its response: stamp in the same synchronous step as the read, or the race returns. **Follow-up:** the rebuild of a lookup the server lost had the same kind of gap; fixed in Item 101.

## Item 101: a lost lookup is rebuilt once, with versions above what the page holds (2026-11-09)

**The gap (found with Item 100):** when the server loses a lookup record (a restart, or eviction from the 256-entry `_records` cache), `_part` rebuilt it from the token. Every request that found it missing built its own `Record` under the same id, with `version` starting at 0 again. The page asks every late part at once, so after a restart each part built a separate record, and the last one stored won. Worse, the page drops a response from the same record whose version isn't higher than the one it holds (`useProfileParts.ts` `accept`), so a page already holding v3 threw the rebuilt v1s away.

**Fix (`backend/profile_parts.py`):** (1) one rebuild per record id, shared through `inflight.shared(("profile_rebuild", id), …)` (`_rebuild`: the Overview's calls, then the parts the first request's page `have`s); each request then runs any part in its own `have` the shared rebuild didn't, before its own part. (2) The token now carries its response's `version` (`"v"` in the claims), and a rebuilt record's versions start at that plus `len(PARTS)` (`_rebuilt_version`). The page sends the token of the newest response it kept, and at most one answer per part can have landed after it, so the rebuilt answers are always newer. A token without `"v"` (signed before this change) starts at `len(PARTS)`.

**Evidence:** `test_a_lost_lookup_asked_by_every_part_at_once_is_rebuilt_once_above_the_pages_version` (the burst still carrying the Overview's token, and a retry carrying the newest one): history and money land, the records are cleared, the other four parts run at once. It asserts one rebuild, one record id, versions all above the page's and distinct, and the newest equal to the full `/api/scorecard`. On the old code every rebuilt response was v1 against the page's v3. `make test` green (2,847 backend, 188 eval, 1,081 vitest), `make lint` clean.

**Alternatives:** (a) a new record id for the rebuild (the page accepts any other record): rejected, a request still holding the old token would miss again and rebuild again, and a straggler from the old record would also be accepted; (b) a clock as the version (µs since epoch): rejected as a wider change to what `version` means for every response, for a case the token can carry; (c) a frontend change: none needed.

**Revisit if** a page can hold more than one answer per part past the token it sends (several retries of one part in flight at once): raise the gap, or carry the page's version in the request.

## Item 102: Phase 6, the Neighborhood tab (2026-11-09)

**Status: approved by the owner (2026-11-10: "once that's in, I think we're good to go", after five localhost review rounds, below) on `feat/ui-next-phase-6-neighborhood` (cut from `feat/ui-next-phase-6-money`, PR #214, with PR #213's branch merged in for the review); **merged and live 2026-11-10 with Money and the parts fix (PR #215, merge `0a07849`)**: the served Profile chunk has the Neighborhood code, `/api/profile/part/activity` returns `next_ui`, the live-site sweep was clean. No route flips (Item 88).**

**The owner's calls (2026-11-09), from a phone mockup of three layouts and four questions:**
- **Phone layout: one column plus sticky jump links** (mockup option B). Below `md`, a row of chips sticks under the tab bar (Getting around, Building, Safety, 311, People, Schools); a tap scrolls to that block and the chip of the block in view is lit. Desktop keeps the shared tab shape. *Alternatives shown:* the plain long column of Money (schools at the bottom of a long scroll); an answer list where each row opens a reading page (shortest screen, but charts one tap away and a different shape from every other tab).
- **Schools: the lot's assigned schools with the state's report card.** The attendance-boundary elementary and high school (CPS boundaries), each with ISBE's own summative designation, % meeting state standards in reading and math, enrollment, and the high school's graduation rate; links to CPS and the Illinois Report Card. Official CPS and ISBE data only, never a private rating. *Alternatives:* names and links only; every school within ½ mile with CPS facts and no scores.
- **Crime per resident: the community area, 90 days, with the yearly change.** Violent and property crimes per 1,000 residents of the community area over the last 90 days (the existing source and window), with the change from the same 90 days a year earlier. Compared with itself, never the city (brief rule 6). *Alternative:* tract-level crime over 12 months against the community area (a new query; small tracts give noisy counts).
- **Construction nearby: new construction and major renovations.** City building permits within ½ mile: New Construction, plus renovation/alteration permits over a reported-cost floor so large rehabs show. *Alternatives:* new construction only; every permit.
- Already decided before (Item 99): race and ethnicity left out (`race_distribution` appears nowhere in the new UI); schools in.

**Decision: the tab's shape** (brief, "Property Profile"; the shape every tab has). The sentence (walk score, how many permits within ½ mile, violent crime's change from a year ago, each clause only when its source answered) → four stat tiles (walk, transit and bike scores, a private company's index, named as such; violent crime per 1,000 residents) → one wide block, **construction nearby** (the search as chips, counts of new buildings, major renovations and homes added, the six newest permits with what is being built in the City's words minus its review-track boilerplate, the rest in the details; the same permits are the map's pins) → **safety**, **top 311 requests**, **who lives here**, **assigned public schools** → a collapsed details table (nearest CTA rail, Metra and Divvy, traffic on the nearest counted street, ward, community-area population, property crime, census tract, every permit).

**Decision: the sources the tab needs that the Profile didn't carry are fetched only by the parts** (`next_ui` on the payload; `main.NEXT_UI_TASK_KEYS`, in the `activity` part), so the full `/api/scorecard` behind today's Profile, chat grounding and the $25 report is unchanged in output and cost. *Alternative:* add them to the full response (three or four more City calls on every live Profile and every report, for a page that doesn't show them).
- *Schools:* CPS's SY2025-26 attendance boundaries on the City portal (`x72b-38qv` elementary, `xg7c-d8rm` high school; one point-in-polygon query each, cached a day) and ISBE's 2025 Illinois Report Card public data set, reduced offline to a committed CPS-only extract (`ingestion/data/cps_schools.json`, 621 schools, 255 KB; `ingestion/build_cps_schools_artifact.py`). The workbook has no CPS id: the join goes through CPS's School Progress Reports (`twrw-chuq`), whose report-card link carries each school's RCDTS code (621 joined, 28 progress rows unmatched). Measures (owner's pick): ISBE's summative designation in its own words, % meeting state standards in reading and math (the combined sheet; where ISBE suppressed it for a school with high-school grades, its high-school assessment rate, marked on the page as "(high school test)"), enrollment, the 4-year graduation rate. The extract holds no demographic breakdowns (a test checks). A point inside no boundary says so (citywide and selective schools have none), never "no school".
- *Construction:* City building permits within a true ½-mile circle (`within_circle` on the permit's location), the last 24 months, `PERMIT - NEW CONSTRUCTION` plus `PERMIT - RENOVATION/ALTERATION` with a reported cost of $250,000 or more (the owner chose new plus major renovations; $250k is the floor proposed with the question), newest first, capped at 300. Each carries the City's own `residential_unit_change` ("adds 8 homes"). The report's box query (with demolitions) is untouched.
- *Crime per resident (owner's pick):* the community area's crimes over the existing 90-day window (the newest week left out, as today) per 1,000 residents of the community area, and the change from the same 90 days a year earlier. Violent = the CPD primary types against a person (homicide, criminal sexual assault, robbery, assault, battery, kidnapping, human trafficking); property = burglary, theft, motor vehicle theft, arson, criminal damage; the rest in neither. Counted server-side from every type (`main._crime_next`): the Profile's crime summary keeps only the top five types, which would undercount the split. The definition says it is the whole community area, not the block.
- *311:* the community area's requests by type over **90 days**, duplicates removed, information calls and parking-ticket reviews left out. A year (the first build) took 43 s from the City portal against 6.5 s for 90 days (2026-11-09), so it missed the 20 s deadline on every cold visit; 90 days is also the crime window.
- *Community-area population and income:* the Profile's neighborhood lookup skips the community area's figures for a parcel (`skip_demographics` for `property_intelligence`), so the parts add them (`area_demographics`, preloaded at startup, no network). The area's income is the City extract's bracket estimate with no margin, so it always reads "Low confidence".

**Decision: who lives here compares the tract with its community area only where the City publishes the same figure** (rule 6): median household income as two bars (the tract, the area). Owner-occupied homes, a bachelor's degree or more, poverty and median age are the tract's own, said once ("only income is published for West Town as a whole"); a figure the backend withholds stays withheld, one it marks low reads "Low confidence". Race and ethnicity are not read anywhere (a test renders a fixture carrying `race_distribution` and checks it never appears).

**Decision: the map's Neighborhood view frames the lot and the permits** (`fit: "building"`, zoning off so the pins read, transit on). The permits are a new `building` group: Coastal's Ballet Slipper for a new building, Bubblegum for a renovation, a hammer inside, dark icons for contrast; the key names both; a pin opens a card (address, kind, reported cost, what is being built, the issue date, Street View). While `activity` waits, the map names it in place ("Loading construction…").

**Decision: on a phone, the jump links stick under the tab bar** (owner's pick). Their offset follows the tab bar's measured height (`--nx-tabbar-h`, set by the page); the chip of the block in view is lit (an intersection observer) and scrolled into view in its row; a tap scrolls to the block with the bar's height as margin. Found on the way: with four tabs the stuck tab strip hid the open tab behind the slim header's tools on a 375 px phone, so the open tab now scrolls into view and the strip's scrollbar is hidden.

**Late parts (Item 89's skeleton rule):** each block that reads `activity` (construction, safety, 311, schools) or `neighborhood` (who lives here) keeps its own outline, named ("Checking building permits…"), and says "Couldn't check in time: schools. Retry" or "Couldn't load" in place, per source (a source past the deadline or failed doesn't blank the others). The shared slot moved out of `MoneyTab` into `profile/LateSlot.tsx`.

**Found while testing: the parts version race (Item 100) blanks a whole tab, not only incentives.** One local load showed every `activity` block as "Couldn't load" while every request had answered 200: a later part's response with a higher `version` carried no `activity` results. PR #213 fixes it, so this branch merges #213's branch for the review; the three PRs (#213, #214, this one) merge together.

**The owner's first review of Neighborhood (2026-11-10), all changed here:**
- *Scores as rings:* the walk score (Overview tile and Neighborhood) and the transit and bike scores are a ring filled to the score, the number inside, on the card's right (`ui/ScoreRing`; `StatTile` gained a `visual` slot; the Overview tile's bar is gone for the walk score).
- *New building vs renovation on the map read as two pinks with one icon:* a new building is Ballet Slipper with Lucide's building, a renovation Pistachio with a wrench; the key, the list and the counts use the same badge.
- *Construction nearby couldn't be opened and "68 more in the details below" was odd.* How a builder uses it: how much is being built around the lot and how fast, of what kind and size, and the detail of one project. So: four counts (new buildings, major renovations, homes added, reported cost), permits by quarter as stacked columns (`ColumnChart` gained `segments`), a filter (All / New / Renovations) and a sort (newest, closest, largest), five rows then "Show all N" in place; each row (kind badge, address, what's built, date, distance, cost, homes as pills) opens **the permit's own page** in the right panel (`profile/PermitPanel`): what is being built in the City's words, where it stands (applied, issued, inspections, complete; a suspended or revoked permit says so), its facts (cost, homes, distance, the City's review time and type, the permit number), "Show on the map" (the map flies to it and opens its card), the City's building-records search and the permits dataset, Ask last. The City's building-records site takes no deep link (a click-through agreement and a form POST), so the page says to search the address there. The parts carry each permit's status, stage, application date and review days. A blank unit change reads "not stated on the permit", never "no change".
- *The two-column blocks left gaps beside a short block:* explicit columns that each pack from the top.
- *The details table should be cards:* "Around the lot" cards for the nearest CTA train (its line color, a walk in minutes at 20 minutes a mile), Metra, Divvy (docks, stations within ½ mile), traffic (vehicles a day, cars a minute as a row of car icons), the ward and alderman (phone, email, website) and the community area (residents, renter households' change).
- *Growth infographics:* "How the area is changing": the community area's median sale price by year (2020 on) with a building-type switch (2–6 units, single-family, condos) and the change, and median rent in the two latest five-year Census periods with the change after inflation and renter households then and now (`rent.trend`, `rent.sales_trend`, already on the payload). No population trend: the City's community-area extract has one period; the renter-household change stands in, named as such.
- *"Who lives here" in Census Reporter's style* (the owner's reference screenshots): headline figures with a comparison line, donuts for shares, columns labeled with their percentages, a dagger on any share whose margin of error is at least 10% of it (Census Reporter's rule, computed with the Census's proportion formula), sections for income (median household and per capita, poverty, household income), housing (units, median home value, occupied vs vacant, owners vs renters, homes by building size, year moved in, value of owner-occupied homes), households (count, people per household, by type), getting to work (average travel time, means, travel time) and age, schooling and moving. The extra tables (B01002, B25024, B25038, B25075, B11001, B25010, B07003, B08303, B08135) ride in the tract's one existing Census Reporter request; parsed into `CensusTractDemographics.extras`, excluded from every dump (chat, the report and the full response are unchanged) and carried only by the parts as `next_ui.tract`. **Comparisons stay with the community area (rule 6):** the reference compares with Chicago, Cook County and Illinois; the same request already returns Chicago's figures (kept in `next_ui.tract.city`), so showing them is one change if the owner relaxes rule 6 (asked).

**The owner's second review of Neighborhood (2026-11-10), all changed here:**
- *Rings felt off* (thin, the number floating, 99 reading as 100): thicker, smaller (56 px), flat ends on a darker track so 99 stops visibly short; only the number inside, "99 of 100" said beside it. Every Neighborhood tile has an icon in a square, like the "Around the lot" cards (walk, transit, bike, violent crime).
- *With the right drawer open the rings pushed into the text, and construction felt stretched by default:* **layout by the space a block has, not the screen** (CSS container queries in `ui-next.css`, `.nx-cq` + `.nx-tiles` / `.nx-split` / `.nx-cards`): the tiles go 1 → 2 → 4 across by their own width; construction puts the counts and the quarterly chart beside the list once the block is at least 50 rem wide (one column with the drawer open); chart and figure cards go 1 → 2 → 3 across. Media-query breakpoints can't see the drawer.
- *Once "Show all" was open there was no easy way to close it:* the expanded list scrolls inside its own height (34 rem) and "Show fewer" also sits in the list's toolbar.
- *Top 311 requests as a pie with colors:* a donut, the top five in the Coastal palette and everything else gray, counts in the key, the total in the middle.
- *"Who lives here" copied the reference's look; the owner wanted its data:* our style instead. Headline figures as small cards, one card per chart (two charts never read as one), Money's hover column chart for breakdowns in order (household income, year moved in, travel time, age), bars for the rest (homes by building size, home value, how people get to work), donuts for shares of a whole (occupied vs vacant, owners and renters, households by type, education, where people lived a year ago). The per-value daggers are gone: a chart with any share whose margin of error is at least 10% of it says "Low confidence" once in its header, and one line under the section says what that means.
- *"Around the lot" promoted:* right under the tiles; the jump links follow the new order.

**The owner's third review of Neighborhood (2026-11-10), all changed here:**
- *Gaps between cards of different heights in "Who lives here":* the figure and chart cards of each section pack in columns, top to bottom (`.nx-masonry`, CSS columns by the block's own width: 1 / 2 / 3). "Around the lot" cards stretch to one height per row; the traffic card is one line (the row of car icons is gone).
- *Insights as small visuals, not tiny text:* badges (a Pill with a trend icon): "1.5× West Town" on the tract's income (purple; West Town's figure under it), "▲ 38% since 2020" on sale prices, "▲ 31% · 8% after inflation" on rent, renter households' change, and crime's change from a year ago on the tile and both safety rows, green when crime fell and red when it rose (prices and rents are blue: neither good nor bad).
- *Rings small and off-centre:* the score tiles put the icon and label on top and the description below, with the ring (64 px, the same thickness ratio) on the right with the card's own padding around it; four across only when the block is at least 60 rem wide.
- *"Low confidence" wasn't defined where it shows:* the label itself opens its definition on hover or tap (`ui/LowConfidence`, the shared Toggletip); the line at the bottom of the section is gone.
- *School ratings ("out of 10", "A+"):* those are private companies' ratings (GreatSchools, Niche), which the owner ruled out for this tab. **Decision: the state's own rating is the highlight**, drawn as a five-step scale from Intensive to Exemplary with this school's step lit and named, its definition on hover or tap; beside it CPS's own 5Essentials culture-and-climate rating as a second five-step scale (from CPS's School Progress Reports, added to the committed extract: 610 of 621 schools rated). CPS's attainment and growth ratings were checked and left out: "no data available" for 488 and 611 of 649 schools in SY2024-25.
- Found on the way: "Around the lot" said "Nothing on record" while its part was still loading; it now keeps its outline and says "Checking…" like every late block.

**The owner's fourth review of Neighborhood (2026-11-10), all changed here:**
- *Violent crime stacked everything on one side:* its figure, window ("90 days in West Town") and change badge sit together on the card's right, like the score rings; icon and label on the left.
- *Assigned schools read tight and wordy:* reading, math and graduation rates are small rings (the score ring, `suffix="%"`, page ink) with an icon and a short label each, students as an icon and a number; "(high school test)" under a ring where it applies.
- *Education's key looked like it was missing entries:* every entry was there, but a 0% slice ("No degree") had a swatch and no slice, Spruce vanished on a dark card, and the two pinks sat side by side. Donuts now leave out 0% slices and draw from category tokens in an order where neighbors read apart (`--nx-cat-1…6`: Sapphire, Ballet Slipper, Pistachio, Spruce, Bubblegum, gray), with Spruce lightened in dark.
- *Which area?:* each "Who lives here" section names it beside its title ("Census tract 8310, a few blocks around the lot").
- How people get to work stays as bars (the owner: every mode readable, however small).

**The owner's fifth review (2026-11-10), the last:** how people get to work is a donut too (it sums to 100%), led by its largest share ("Work from home 41%"), "Other" always the neutral gray and a sixth category color (`--nx-cat-7`, a muted lavender); a school's rate rings take one column each, so three or four always fill the row evenly, with more room above and below. Then the owner's go.

**Gates (local, 2026-11-10):**
- *Words:* not measured against a budget (the new UI has none yet; Item 99's Money counts are the baseline). The tab is long by design: the owner asked for the Census data and the charts; phones get the jump links.
- *Timing:* the `activity` part now carries crime, crime's yearly comparison, 311 by type, schools, construction and the community area's figures; on 1601 N Milwaukee cold, every block filled in about 45 s locally (two City-portal lookups dominate), warm about 2 s. 311 over a year missed the 20 s deadline on every cold visit (43 s), so it is 90 days (6.5 s). The tract's extra Census tables ride in its one existing request (no new request). Production per-part timing comes from the `scorecard part timings` lines after deploy.
- *Failure states:* each late block keeps its outline, named, and says "Couldn't check in time" or "Couldn't load" with Retry in place, per source (vitest); a failed source is listed in `next_ui.failed`, never "none" (pytest); "Around the lot" no longer says "Nothing on record" while loading.
- *Map:* the Playwright check finds the same canvas after the switch to Neighborhood; `mapNoSatellite.test.tsx` passes.
- `make test`, `npm run build`, `npm run test` (1,137), `npm run lint` (67 warnings, the cap), `e2e/ui-next.spec.ts` (with the new Neighborhood check: late outlines, same map, jump links, axe light and dark at 360 px) and the mobile matrix: see the PR for the final run.

**Not measured:** how builders read the tab (the builder test, Item 88); production timings. **Open, the owner's call:** whether "Who lives here" also compares with Chicago (rule 6 says the community area; the same Census request already returns Chicago's figures, in `next_ui.tract.city`).

**After approval (2026-11-10), two small requests from the owner:** how people get to work lists its key from the largest share to the smallest; the 311 donut's key gives each type's count and its share ("1,835 · 23%").

## Item 103: Phase 6, the History tab, and the address-permit lookup fixed (2026-11-10)

**Status: approved by the owner on the first localhost review (2026-11-10: "pretty clean … a pretty nice way to display the data … a thumbs up as is") on `feat/ui-next-phase-6-history` (cut from `main` after #215); not merged (merge = deploy, the owner's call). No route flips (Item 88).**

**The owner's calls before the build (2026-11-10), from a mockup on 2541 N Spaulding Ave's real records and six questions:**
- **The timeline's default filter: everything but the noise.** Market sales, permits, violations and zoning on, every year on record; tax appeals and non-market transfers ($1 deeds, quit claims, multi-parcel sales) off by default, one chip away, labeled for what they are. *Alternatives shown:* everything on; market sales only; the last 10 years.
- **City permits at the address: added, and the shared lookup fixed** (below), so the $25 report lists them again. *Alternatives:* a History-only lookup leaving the report broken; the Assessor's permits only.
- **"Records differ": a badge that opens a page** (option C of three on the mockup): the tile and the building block show the range ("1899–1992") with a "Records differ" badge; the badge opens a reading page in the right panel with every source's value. *Alternatives:* a range with a badge and no page (no way to see which source said what); the sources side by side on every lot (most room).
- **Map and phone: the lot alone, one plain column.** The History map view frames the lot (zoom 17.2) with zoning on so its district reads; no jump links (one main block). *Alternatives:* jump links like Neighborhood; nearby rezoning filings as pins.
- **Carried over:** "Who lives here" stays local (tract vs community area, rule 6); the Build tab's sentence gains the Overview's landmark clause ("…; a Chicago Landmark district") when the lot is a landmark or in a landmark district.

**Found while sizing the data: the City's address-permit lookup had been finding nothing.** The building-permits dataset (`ydr8-5enu`) now stores `street_name` with its suffix ("SPAULDING AVE"); `buildings.address_specific_permits` matched the bare name ("SPAULDING") exactly, so it returned zero rows for every address. The $25 report's address permits use it. 2541 N Spaulding has 3 City permits (2011–2015), 1601 N Milwaukee 36. **Fix:** match the name with its suffix or the bare name (`upper(street_name) in ('SPAULDING', 'SPAULDING AVE')`); with no suffix known, the name or the name plus one word. `parse_chicago_address` is unchanged (callers compare its dict); `street_suffix()` reads the suffix. The violations dataset still stores bare names, so its lookup was never broken. *Revisit if* the City changes the field again: `test_address_permits_match_the_street_name_with_its_suffix` pins the query, not the live data.

**Decision: the tab's shape** (the shape every tab has). The sentence (the last market sale, then the City's permits and the violations, each only when its source answered) → four tiles (last market sale, year built, City permits, open violations) → **the timeline** (kind chips with counts; one lane per kind across the years, one mark per kind per year with its count, hover or focus names it, a click lists only that year; then the events newest first, six shown, "Show all" scrolling in place) → **the building** (year built, stories, floor area, units, each with its source) beside **on the record** (City-owned, the scofflaw list, the short-term-rental ban, the 1996 historic survey rating, past tax sales, tax appeals with "Show on the timeline") → a collapsed list of the sources and what each covers. A permit opens `PermitPanel` (now also for a permit at the address: any kind, no distance, no "Show on the map"); an inspection expands its violations in place; a zoning record opens the Clerk in a new tab. Each kind has an icon and a Coastal category color (a market sale is this lot's black); dark icons on the pale colors.

**What the timeline holds:** County sales (the 10 most recent; a market sale by the server's `arms_length`, else a transfer, never a price for the lot); the City's permits at the address (every year on record, 2006 on); the City's violations at the address (every year, one event per inspection: a visit writes several violations on one day); zoning (the ordinance behind today's district from the zoning map's `ordinance_date`, the Clerk's filings listing this address, passed rezonings and landmark designations not yet on the map); tax appeals (year only). 311 requests are left out: the Profile's 311 lookup is a ~50 m box, not this property.

**Decision: History's own sources ride the `history` part under `next_ui`** (Item 102's rule), so the full `/api/scorecard`, chat grounding and the report are unchanged in output and cost: `permits_at_address` and `violations_at_address` (`buildings.py`: 30 years, up to 300 rows each, raising on a failed call; the Profile's own 5-year lookups keep returning `[]` on failure as before, and the violations cache key now includes years and limit so the two never share an entry) and `building_records` (`retrieval/property/building_records.py`). A failed one is listed in `next_ui.failed`, never "none"; an address the City's records can't be searched by is `null` ("not asked"). When the City's permits fail, the Assessor's permit copies stand in, named as such.

**Decision: building records list every source; we never pick a winner.** The summary keeps one value per fact (the Assessor first, then fill-only fallbacks) and drops the rest, so a disagreement was invisible. `building_records` lists the summary's own value under its source, then asks the City's building footprints (point-in-parcel, cached a day) for every lot that has a building and, outside class 2xx, the Assessor's Commercial Valuation, plus energy benchmarking when the summary carries it. **When values differ** (owner-facing, shown on the page): years 2 or more apart (a one-year gap is assessment-year rounding: 1601 N Milwaukee's 1920 and 1921 is not flagged, though the page lists both), stories a whole story or more apart, floor areas 15% or more apart. **A footprint larger than the lot by the Profile's own `_FOOTPRINT_SPAN_SLACK` gives no floor area** (1601 N Milwaukee's 21,800 sq ft footprint on an 11,951 sq ft lot), so History never shows an area the Build tab refuses. *Alternatives:* any difference flags (most 2-flats would carry a badge for a year's rounding); show the summary's value only (the brief asks for the disagreement). *Revisit if* builders read the range as a fact about the building rather than about the records.

**Late parts (Item 89's skeleton rule):** the Overview's sales and zoning show at once; the permit and violation tiles and the building block keep their outline, named ("Checking City permits…", "Checking building records…"), and say "Couldn't check in time: City permits · Retry" in place, per source. "On the record" waits only on its own lookup (`property_history`), so a permits timeout doesn't blank it (found by the tab's test).

**Gates (local, 2026-11-10):**
- *Words:* not measured against a budget (the new UI has none yet; Item 99's counts are the baseline).
- *Timing:* the `history` part 1.3–6.4 s cold locally (the City's permits the slowest at 1.2–6.3 s), about 0.3 s warm; well under the 20 s deadline. Production per-part timing comes from the `scorecard part timings` lines after deploy.
- *Failure states:* a held `history` part shows the tiles' and blocks' outlines named (vitest, Playwright); a timed-out source says Retry in place while the others show (vitest); a failed source is listed, never none (pytest).
- *Map:* the Playwright check finds the same canvas after the switch to History; `mapNoSatellite.test.tsx` passes.
- `make test` (2,880 backend, 188 eval, 1,146 vitest), `npm run build`, `npm run lint` (67 warnings, the cap), `e2e/ui-next.spec.ts` (with the new History check: late sources in place, same map, kind chips, axe light and dark at 360 px, no overflow) and the mobile matrix.

**Not measured:** how builders read the tab (the builder test, Item 88); production timings. A failed parcel-flags lookup still reads as nothing flagged (the property history lookup logs and leaves it empty, as the live Profile does).

## Item 104: Phase 6, Discovery on the one map (2026-11-10)

**Status: approved by the owner ("Thumbs up", 2026-11-10) after five localhost review rounds (below), on `feat/ui-next-phase-6-discovery` (cut from History's branch, PR #216, unmerged: merge = deploy, the owner's call; the two merge together). No route flips (Item 88). Phase 6 is complete with this route.**

**The owner's calls before the build (2026-11-10), from a mockup of the Explore map, the list cards and two phone layouts:**
- **Quick filters:** Vacant · Near the L (½ mi) · Lot 5,000+ sq ft · Sold in 2 years · In a TIF (all 68-100% known).
- **The map's measure:** room to build, **on condition that its coverage is fixed** ("50% known is super unreliable"). Fixed in this route (below).
- **Phone:** the map first, the list in a bottom sheet over it.
- **Card picture:** the lot's own outline, drawn by us (free); Street View stays a link (Item 94).
- **Serious warnings (one per card):** a demolition permit, a vacant-building case, a pending rezoning, a landmark; and a nominal assessment.
- **No bookmark until Saved (Phase 9); the address ring now.**

**Decision: room to build is known for 85.7% of lots, up from 0% stored (its inputs 80%).** Measured on the citywide index (590,174 lots, base PINs; the 292,154 condo unit PINs have no lot of their own, which is why the old "50%" read low):

| Lots | Count | Room known before | After |
|---|---:|---:|---:|
| Residential | 446,351 | 97% (inputs) | 95% |
| Vacant | 32,280 | 100% (inputs) | 93% |
| Multifamily (7+) | 14,191 | 9% | 77% |
| Commercial | 44,666 | 2% | 72% |
| Industrial | 479 | 0% | 31% |
| No land use (exempt, railroad) | 52,207 | 6% | 13% |
| **All** | 590,174 | 80% (inputs) | **85.7%** |

How (`backend/discovery/lot_facts.py`, `index_backfill.py`; the monthly build runs the same `enrich_rows`): one building-area source per lot, named in `bldg_sqft_source`: the Assessor's characteristics, else the Assessor's Commercial Valuation for a building that is this lot's own (already in the builder since 2026-11-02; the local index predated it), else the City's building footprints (`syp8-uezg`) whose own interior point is inside the lot, area x stories, withheld when a footprint has no stories (48% of footprints) or is larger than the lot by the Profile's 1.1 slack. A **multi-parcel complex** (a shopping center, a campus: one Commercial Valuation area for several PIN10s) is read as one site: allowed floor area summed over its lots minus the complex's area, shown on each member as "room for the whole N-lot complex" (`room_scope: complex`; 21,742 of 27,143 commercial complex lots computable). Room = the base district's FAR x lot area minus the building, never below 0, absent when any input is unknown. *Alternatives:* footprints alone (adds only 9,877 lots: most commercial lots lacking an area are complex members); apportioning a complex's area by land share (a guess about which building sits where). *Revisit if* the County publishes per-PIN commercial areas, or the City's footprints gain stories.

**Decision: a local copy of the City sources lots need** (`lot_sources.py` → `backend/data/discovery_lot_sources.db`, 139 MB, 5 min): 820,456 active footprints, vacant-building cases (`kc9i-wq85`, 3 years), demolition permits (`ydr8-5enu`, 24 months), Chicago Landmarks (zoning layer 5) and landmark districts (layer 6). Refuses a partial read. Card warnings from it: 2,619 lots with a demolition permit, 19,732 in a landmark or landmark district, 2,406 listed by a pending rezoning filing (`pending_legislation.db`), and **only 11 vacant-building cases**: the City's dataset has few recent rows (5,012 since 2011), so that warning is nearly silent; said here, not hidden.

**Decision: the lot tiles carry the measures as bands** (`measure_bands`: `r` room, `s` lot size, `y` years since the last sale, `u` land use; `g` zoning family as before). Display only: which lots match a search is never in the tiles (Item 68). Tile file 28.7 → 33.4 MB (+16%). A lot with no value is drawn dotted, never as "low".

**Decision: the page** (`ui-next/discovery/`):
- **Explore** opens on the city: below zoom 14 the 77 community areas (`GET /api/discovery/areas`, simplified outlines, 103 KB), from 14 every lot filled by the measure (Room to build by default; Lot size, Last sale, Land use, Zoning family), zoning off by default and one switch away.
- **Quick filters dim rather than hide:** the server evaluates them for the view (`scope: viewport`, one row, the points), the matches are outlined, the rest fade; in the city view each area is labeled with its count (`includeAreaCounts`, from the same evaluation). "Search N lots in view" turns the view into a search.
- **Matches are outlines only** (owner, Item 99): a black line over a white edge by feature state on the lot tiles; no dots, no pins.
- **One search box:** an address (autocomplete) offers its Profile or "Search around it" with a ring of ¼, ½ or 1 mi and a drag handle (the existing `radius` filter); a community area by name; anything else is a description for the rule-based compiler, its unread words shown as "Not understood".
- **Goals as "Try" chips** with their counts; a goal with no data says "needs data" (coach houses: 0 matches, units and ADU areas aren't in the index).
- **One focus at a time:** List (picture cards) or Map ("N lots in view · List them"). Cards: the lot's outline, address, zoning, lot size, room to build (with its source when it isn't the Assessor's record, or the complex), the last sale (a sale under $10,000 reads "Transfer", the County's own filter), one warning.
- **New sort key `room_to_build`** (most room first, unknowns last; the server sorts): the new page's default. The registry's default (assessed value ascending) put 10 sq ft slivers first.
- **Filters sheet:** only filters with data, each with "Known for N% of lots" (`GET /api/discovery/distribution`), presets plus a custom value, a histogram across the city with the unknowns as their own hatched bar, "Also include lots with no data" (a new optional `includeUnknown` on a predicate, overriding the filter's policy in the evaluator; unset it serializes as before, so every cache key and wire shape is unchanged), and a live "Show N lots" count from the server. Transit is one control (5/10/15-minute walk to the L; Metra, bus and Divvy aren't in the index, said once).
- **Phone:** the map first; the list a sheet (peek, half, full; drag or tap), its peek clearing the preview badge.

**Gates (local, 2026-11-10):**
- `make test` (2,896 backend, 188 eval, 1,158 vitest), `npm run build`, `npm run lint` (67 warnings, the cap), `e2e/ui-next.spec.ts` (new Discovery check at 360 px: a quick filter's request, a goal's area counts, the list, the same map canvas, axe light and dark, no overflow; axe on the preview routes), the mobile matrix: see the PR.
- *Map:* MapLibre over our tiles, no satellite (`mapNoSatellite.test.tsx` passes); the Cities: Skylines look of Items 90-98, unchanged.
- *Words:* not measured against a budget (none exists yet for the new UI).
- *Timing:* a quick-filter view search answers in well under a second locally (cached evaluation over the in-memory index); `/api/discovery/distribution` scans the index once per filter per data version.
- *Failure states:* no WebGL says so and the list still works; a failed search says so; a lot card says "not in Discovery's index" or "couldn't load", never "none".

**Production steps (with the merge):** `docker compose run --rm --no-deps backend python -m backend.discovery.lot_sources`, then `... python -m backend.discovery.index_backfill` (minutes; or the monthly `--refresh` does it), then `... python -m backend.discovery.parcel_tiles`. Without the source copy the build skips the footprint fill and the warnings, with a warning in the log.

**Found on the way:** each card fetched its outline at once (50 requests), which knocked over a local dev server's worker once; the page now fetches four at a time.

**Not done:** Metra, bus and Divvy in the transit control; units, violations, flood and overlays as filters (0% in the index); a land-use map (M5, Phase 7); production timings.

**The owner's first review of Discovery (2026-11-10), all changed here:**
- *The map went fully black on a refresh.* The local server had crashed: a segfault inside SQLite. The County-outline store (Item 92) kept one connection shared across FastAPI's threads (`check_same_thread=False`); the Profile asks for one outline at a time, but Discovery's cards asked for several at once. **Fixed for every caller with one connection per thread** (`county_outlines.Outlines`); 200 concurrent `/api/map/lot` requests answered, server up; a test runs 2,000 lookups on 16 threads. Production has the same code (one outline per Profile view), so the fix ships with this PR. The cards also fetch their outlines four at a time.
- *The map looked empty when it opened* (lots appear only from zoom 14). Every lot citywide costs 6.1 MB at zoom 11 (measured; 1-2 MB per view at 13), too heavy for a phone. **Owner's pick: a grid zoomed out** (`parcel_tiles.grid_cells`, `GET /api/discovery/grid/{z}/{x}/{y}.mvt`): squares of about a block (0.0018° × 0.0024°, ~200 m), each the median band of its lots for the chosen measure (the most common for land use and zoning), a cell with under 3 lots left out and a measure known for under half its lots dotted. 11,965 cells, 114-169 KB per zoom for the whole city, 7 s to build; it turns into lots at 14. Built with the lot tiles.
- *Filters were one long uncategorized form, with jargon (FAR min/max, "upside 40+/70+") and no icons; the search box too wide, Filters crushed beside it; an empty "Discovery" bar; the Try chips felt like examples.* **Owner's picks:** the search box moves into the top bar (the frame's new `bar` slot replaces the breadcrumb, kept for screen readers); filters become **groups** beside it (Lot, Zoning, Building, Transit, Price and sales, Incentives; `filterGroups.ts`), each an icon button with its count, each opening its own small panel (a bottom sheet on a phone) of **plain-language choice cards with icons**: Density (FAR) becomes "How big it can be": Houses (≤ 1, about a story's worth), Flats (1-2), Apartments (2-5), Towers (5+); zoning families as Homes / Shops and offices / Industry / Downtown / Planned development; lot size as small / a city lot / a double lot / large. **Redevelopment upside is replaced by Room to build** (a new registry filter `room_to_build` on `room_sqft`, tier "more", so today's page is unchanged); upside, the improvement ratio and the value percentile are not offered in the new UI. Technical names and coverage are small print under each filter. **Transit is one slider** (1-20 minutes' walk to the nearest L, 20 minutes a mile) and the map draws that walk around every L station while the panel is open. **The goals are a "Start from a goal" card on the map** (a list in the phone's sheet) with plain names, icons and counts, folding away; a new goal "Lots with room to build" (5,000+ sq ft more allowed than built: 45,385 lots).

**The owner's second review of Discovery (2026-11-10), all changed here:**
- *Choices in one filter group were lost on switching to another without pressing Show.* **One draft for the whole bar** (`FilterBar`): choices build up across groups, each group's count reflects them, and a "Show N lots" button appears in the bar while choices wait; the live count runs only while a panel is open or choices wait (it had run a citywide count on every page load).
- *On a smaller screen the group buttons scrolled sideways, most hidden.* **They wrap to a second row** (owner's pick); the frame's top bar grows for a full-screen page (`AppFrame fill`).
- *Odd-shaped lots that can't be buildable.* Measured by each lot's real width (the diameter of the largest circle inside it): 1,200 empty lots under 10 ft, 793 at 10-16 ft (6% of empty lots); 6,265 built lots under 16 ft not already hidden. **Owner's pick: a lot under 16 ft wide is a "narrow strip", hidden by default with the other unusual parcels** (`lot_facts.lot_width_ft`, `index_build.unusual_rule`; "N unusual lots hidden … · Show" names strips), and its card says "Narrow strip, N ft wide: rarely buildable alone". 7,985 lots; "empty lots" goes from 32,437 to 30,022.
- *The map shows where room to build is unknown; what can fill it?* The 84,367 unknown lots (14.3%) broke down as: 43,204 with no building area (no footprint inside, no Assessor record; 27,580 exempt), 31,901 with no base FAR (planned developments, parks, unknown zoning), 8,192 footprints without stories, 587 footprints larger than the lot, 483 with no lot area. **The owner asked for all four fills where justifiable and accurate; each was measured first:**
  - **No base FAR is named, not unknown** (`lot_facts.no_far_scope`): a planned development or planned manufacturing district "sets its own size by ordinance" (28,104 lots), a POS district is open space, a T district railroad or transit land (named once the index carries the exact district: the local copy predates `zone_class`, production's doesn't). Drawn in the zoning map's PD gray, park green and transportation peach, named in the key and on cards; never a number.
  - **No building on record = empty: only where a government record says so.** Validated against the City's own land inventory (`aksk-kvfp`, 12,012 City-owned lots, almost all vacant land for sale) and new-construction permits since 2015 (18,347): of 36,721 exempt lots with no footprint, 9,905 are City-owned vacant land; 505 (1.4%) had new construction since 2015, so absence from the footprint map does **not** mean empty in general. Applied: a lot with no footprint that the City's inventory lists as City-owned has no building (`bldg_sqft_source: city_land_inventory`, 9,994 lots). Not applied to the other exempt lots (churches, schools, CHA: no independent check) or to any lot classed residential or commercial (the class says a building exists).
  - **Condo buildings from the Assessor's whole-building area: rejected on accuracy.** `char_building_sf` (3r7i-mrz4) exists for 12,180 Chicago condo buildings; against footprints x stories on 4,334 of them the median ratio is 1.28 and only 41% agree within ±25% (10th-90th percentile 0.91-2.3). Not used until the disagreement is understood.
  - **Stories from building heights: no open source adds anything yet.** OpenStreetMap carries `building:levels` on 424,519 Chicago buildings, the same City import as the footprints with stories (427,924). Real heights need the County's LiDAR survey, which is also what Phase 7's 3D track (M6) needs; proposed there.
  - **After (local citywide index):** room to build known for **87.3%** of lots (was 85.7%), named "own ordinance" 4.8%, **unknown 8.0%** (was 14.3%).

**The owner's third review: search within a neighborhood (2026-11-10).** The search box knew the 77 community areas, not neighborhoods ("Wicker Park" is inside West Town: "vacant lots in Wicker Park" read Vacant and searched the whole city, saying "wicker park" wasn't understood), and picking an area replaced the search on screen. The owner: by neighborhood is how to get use out of "largest upside", which otherwise concentrates in a few underdeveloped areas. **Decision:**
- **The City's 98 named neighborhoods** (`y6yq-dbs2`, "Boundaries - Neighborhoods", 2012), simplified to about 5 m and committed (`backend/discovery/neighborhoods.geojson`, 107 KB; `neighborhoods.py` builds it, refusing under 90). The index tags every lot with the neighborhood its point falls in (`attrs["hood"]`, in `enrich_rows`); a search region `hood:<slug>` matches it in the server (`parcel_index.in_region`). Registered in data health (`chi.neighborhoods`, a fixed 98).
- **The rule-based reader understands places:** a neighborhood's name, else a community area's ("in Wicker Park or Bucktown" → both, OR); and "teardown(s)" (it was the example of a phrase it couldn't read).
- **The search box suggests neighborhoods first, then community areas;** `GET /api/discovery/neighborhoods` gives names and outlines.
- **A picked place narrows the search on screen, never replaces it:** its filters stay, and choices still waiting in the filter bar go along. The chosen place is outlined on the map and framed (read from the evaluated query, so a typed "in Wicker Park" outlines it too); the chip says its name. Vacant + Wicker Park: 55 lots.

**The owner's fourth review: the list cards (2026-11-10).** "Nothing about any of those lots would stick out": an address, a bare outline, room to build, and a last sale that half the cards answered "None on record". **Owner's picks from a mockup, all built** (`ui-next/discovery/LotCard.tsx`):
- **A slice of the block, colored like the map:** the lot and its neighbors within about 50 m (`GET /api/discovery/lot-context?pin10=`, outlines with each lot's room band, cached), this lot in its room-to-build color with an ink outline, the neighbors faded in theirs; the zoning as a tag in its family color.
- **Room to build as the headline with built vs allowed as a bar** ("Built 2,400 · Allowed 6,150 · 39% used"; the bar's free part in the lot's room color), and its basis when it isn't the Assessor's record.
- **The neighborhood and what's there now:** "Bucktown · Commercial, built 1890, 924 sq ft" (an empty lot shows no year: that is a demolished building's record).
- **Colored chips for only what applies:** a walk to the L in minutes (20 minutes a mile, shown up to 20), In a TIF, Enterprise Zone, Old building on valuable land, a narrow strip, the one serious warning.
- **The sale only when there is one** (no "None on record" line). Price per buildable sq ft was offered and not chosen.
- **One card per multi-parcel complex:** its lots share one figure, the site's, and sorted by room they filled the top of the list card after card; the first card says "N more of its lots in this list" (`foldComplexes`, presentation only; the count above the list stays the server's).
- New row fields: `hood`, `transit_mi`, `in_tif`, `in_enterprise_zone`.

## Item 105: Phase 7 step 1, building heights from LiDAR, measured before use (2026-11-10)

**Status: measured; nothing changed in the app or on the live site. Owner's calls (2026-11-10): Discovery's story-less lots stay unknown (the recommended no-go); Phase 7's order is M6 (3D), then M4 (capacity), then M5 (land in use).** Asked by the Phase 7 brief: can LiDAR fill the stories that 8,192 City footprints lack (Item 104), and give M6 (3D) its neighbors' heights?

**The sources found (newest first):**
- **Cook County's 2022 building footprints** (`gis.cookcountyil.gov/traditional/rest/services/buildingFootprint_2022/MapServer/0`, item `7c4f47a3b32944e58c5f18652880fc05`): 1,960,186 polygons countywide, **779,930 inside Chicago**. Made from the County's spring-2022 LiDAR (20 points/m²) and 2022 orthophotos; each polygon has `Ground_Z`, `Max_Point` and `Height` = the **highest LiDAR return inside it** minus ground, in feet (minimum 7 ft: smaller structures aren't in it). Public ArcGIS service, the County's "as is" open-data terms. Read with the `httpx` and `shapely` we already have: about 3 minutes for Chicago's bounding box (1,254,045 polygons, 490 MB in SQLite), 25 s to match. **No new dependency.**
- The 2022 point cloud itself isn't published (only a bare-earth DEM, `imagery/rest/services/DEM2022/ImageServer`, and contours).
- **USGS 3DEP `IL_4_County_QL1_LiDAR_2016_B16`** (the County's spring-2017 flight, QL1, public domain): LAZ tiles of 2,500 ft, about 140 MB each, about 1,000 tiles for the city (about 140 GB). Not in 3DEP's cloud-optimized copy (no EPT), so reading it means downloading every tile and decoding LAZ (`laspy` + `lazrs`, not in our dependencies). **Not run:** USGS's download host answered scripted requests with a bot check, and we don't get around one. That makes the brief's "median of roof returns" untested (see below).
- OpenStreetMap heights add nothing (Item 104).

**Method** (scripts kept outside the repo, in the session notes folder `lidar_item105/`, since nothing ships): each City footprint (`syp8-uezg`, the local copy: 820,456 active) is matched to the County polygon containing its interior point; a match is "clean" when the two outlines' intersection over union is at least 0.6. Stories from height were fitted on half the footprints that have stories and tested on the other half (split by a hash of `bldg_id`): `stories = round((H − 3 ft) / 14.75 ft)` under 40 ft, `round(H / 14 ft)` above (a lookup table by 1-ft height did no better). The footprints' year built, units and garage flag come from the same City dataset.

**Coverage:** 773,579 City footprints (94.3%) sit inside a County polygon; 659,717 (80.4%) match cleanly, 80,781 partly (IoU 0.3-0.6), 33,081 poorly. Of the 392,532 footprints without stories, 276,108 match cleanly.

**Accuracy against the City's own stories** (191,872 held-out clean matches; note the City's footprints were last edited in 2015 and the LiDAR is 2022, so part of any disagreement is change, not error):

| | n | Exact | Within ±1 |
|---|---|---|---|
| All | 191,872 | **79.9%** | 99.2% |
| *Baseline: guess 2 stories for every building* | | 45.7% | 99.2% |
| 1 story | 89,023 | 79.8% | 99.3% |
| 2 stories | 87,639 | 83.1% | 99.9% |
| 3 stories | 13,645 | 68.5% | 99.5% |
| 4-6 stories | 962 | 47.7% | 84.5% |
| 7-15 stories | 332 | 14.8% | 47.9% |
| 16+ stories | 271 | 4.4% | 14.0% |
| 1 unit / 2-4 units / 5+ units | 124,457 / 54,410 / 6,324 | 78.7 / 86.9 / 68.9% | 99.9 / 99.9 / 95.6% |
| No units recorded (mostly non-residential) | 6,680 | 56.0% | 85.8% |
| Built before 1920 / 1920-45 / 1946-79 / 1980-2015 | | 78.8 / 81.4 / 81.1 / 72.1% | 99.5 / 99.5 / 99.4 / 94.9% |
| Partial match (IoU 0.3-0.6) / poor (<0.3) | 12,754 / 4,579 | 66.5 / 49.6% | 95.9 / 87.2% |

**Within ±1 story is not a useful test for Chicago:** most buildings have one to three stories, so guessing 2 for all of them scores the same 99.2%. Exact is the number that matters, because floor area is footprint × stories and one story off on a two-story building is a 50% error.

**Floor area against an independent source**, the Assessor's building area (lots whose area comes from the Assessor or its Commercial Valuation, not in a multi-parcel complex), share of lots within ±25%:

| | Lots computable both ways | Footprint × City stories (in use today) | Footprint × LiDAR stories |
|---|---|---|---|
| All | 92,508 | **53.2%** (median ratio 1.19) | **48.8%** (1.21) |
| Residential | 83,955 | 51.0% | 48.3% |
| Multi-family | 2,962 | 81.9% | 62.8% |
| Commercial | 4,669 | 74.1% | 50.2% |

The City's stories run high against the Assessor too (median 1.19; the Assessor's area leaves out basements and garages), but LiDAR is worse. The gap is widest for apartments and commercial buildings, where heights include rooftop equipment, parapets and towers on podiums.

**The 8,192 lots:** 8,188 found again. LiDAR would fill all the missing stories on **4,433** of them (54%); the rest have a footprint the County doesn't have (2,689 footprints, mostly under 400 sq ft or under the County's 7-ft minimum) or a different outline (2,245). These lots aren't like the validation set: their story-less footprints are small sheds and garages (median 768 sq ft, 10th percentile 276) or large buildings (90th percentile 11,495 sq ft), and 645 of the matched ones come out at 4+ stories, where accuracy is 15-48%. 3,734 of the 8,188 are blocked only by footprints under 600 sq ft; there's no independent check for those either, because the City records no stories for garages (one storied garage in the validation set) and its small storied footprints are mostly 2-3 story rear additions (4.7% one-story).

**Recommendation:**
- **Discovery's missing stories: no-go as measured.** The fill would be worse than the method already in use, on the building types the gap lots skew to. Item 104's rule (justifiable and measured accurate) isn't met. *Revisit if* a median-of-roof height can be measured (needs the 2017 point cloud downloaded by hand, about 140 GB, or the County's 2022 point cloud on request) and beats footprint × City stories against the Assessor's area. Or if the owner wants a narrower rule for small accessory structures (under 600 sq ft, highest point under 20 ft = one story, or left out of floor area), which this data can't check.
- **M6 neighbor heights: go, in feet, without stories.** 3D draws height, not stories, and the County's measured height is the best source for that: 2022, 94.3% of City footprints, 779,930 buildings in Chicago (median 20 ft, 99th percentile 58 ft). Caveats for M6's spike: the height is a roof's highest point (chimneys, rooftop equipment, a tower over a podium: a block shows each building's tallest point, not its roof line); buildings demolished or built since 2022 are wrong; the raw outlines are 262 MB (15.7 M vertices) in WKB, so they need tiles and a payload and frame-rate check on a phone. Whether to draw County outlines (2022) or City footprints (2015) is part of the spike.
- **Stories shown to people** (History's building records, Item 103) stay the City's and the Assessor's; a LiDAR height could be one more source there later, labeled as a measured height.

*Alternatives considered:* the 2017 point cloud with our own median (blocked, above); a learned model (the inputs are one height and an outline; gains would be small against 2015-vs-2022 change); OSM `building:levels` (same City import, Item 104).

## Item 106: Phase 7 M6 spike, 3D buildings: coverage, payload and frame rate (2026-11-11)

**Status: on `claude/phase-7-lidar`, unmerged; after the owner's first look (below) 3D is a 2D/3D button on the ui-next maps (preview only, `?ui=next`), shown only where the server has building tiles (production has none until the step below runs). **Owner's calls (2026-11-11): a 2D/3D button on every map, beside Map key, with Build opening in 3D; on a phone, 3D only in the expanded map (the band stays flat).** M6's acceptance (Item 75) starts with this spike: footprint coverage, measured vs story-derived heights, geometry failures, payload, frame rate on a phone.

**Built:** `backend/map_tiles/building_tiles.py` cuts the County's 2022 LiDAR footprints (Item 105) into vector tiles (`map_buildings.mbtiles`, layer `building`, one property `h` = height in whole feet, zooms 14-16), served by the existing `GET /api/map/tiles/buildings/...` and listed in `/api/map/info`. It keeps a local copy of the source (`map_sources/county_buildings_2022.db`, `--offline` rebuilds from it) and refuses a short read (under 1.1 M polygons in Chicago's box, or 700k inside the city). `frontend/src/ui-next/map/buildings3d.ts` adds one `fill-extrusion` layer under the labels and pins, neutral grays that lighten with height (no hue: the lot and zoning keep the map's meaning, Item 74), a soft viewport light, and tilts the camera (pitch 55°). Theme switches repaint it in place like every other layer.

**Coverage:** 779,930 County buildings inside the city; 94.3% of the City's 820,456 footprints sit inside one (80.4% match cleanly). The plan in the brief, neighbors raised by the City's 2015 stories, would cover **52%** (427,924 footprints with stories) and is approximate: against the measured heights, stories × 14 ft is within 10 ft for 82.8% of low buildings but off by a median 30.7 ft at 7+ stories. **Decision: measured heights, not story-derived.**

**Geometry:** 804 invalid County outlines repaired (`make_valid`), none dropped, none unclipped.

**Payload:** 68 MB file, built in 3 min. Per zoom (gzipped): z14 233 tiles, 16.1 MB, mean 69 KB, max 189 KB (the Loop); z15 825 tiles, 20.1 MB, max 64.5 KB; z16 2,946 tiles, 29.3 MB, max 27.7 KB. Measured per view: the Profile's map band on desktop loaded 8-26 building tiles (20-504 KB); on a 390-px phone 8-10 tiles (20-192 KB).

**Frame rate:** a 6-second camera rotation held 60 fps (median and 10th percentile, worst frame 17 ms) at three places (Wicker Park, the Loop, a bungalow block on Fullerton), on desktop and a 390×844 phone viewport with the CPU slowed 4×, light and dark. **This is not a phone measurement:** the GPU was the Mac's (Apple M4 Pro), which CPU throttling doesn't slow. A real phone is still to be checked, the same open item as Phase 5's map.

**What the look gets wrong (shown in the review screenshots):**
- **A building is one prism to its highest point.** The County gives one height per outline: the Willis Tower is one 120,366 sq ft block raised to 1,727 ft (its antennas), and the Hancock to 1,422 ft. Stepped towers, rooftop equipment and towers on podiums read too bulky. A roof line needs the point cloud (Item 105); until then the key should say "highest point measured in 2022".
- **The lot itself** isn't yet treated in 3D: its black outline sits on the ground under its own building. M6's next step draws today's building on the lot in the lot's color and the illustrative zoning mass around it.
- Buildings since 2022 are missing; demolished ones remain.

**Production steps (only when 3D ships):** `docker compose run --rm --no-deps backend python -m backend.map_tiles.building_tiles` (about 3 min fetch + 3 min cut), then verify `/api/map/info` lists `buildings`. **The County's LiDAR service (gis.cookcountyil.gov) blocks the prod server** (found 2026-11-12), as FEMA does (Item 84): the source copy `map_sources/county_buildings_2022.db` is fetched on the Mac, installed on the server, and the tiles are built there with `--offline`. A data-health source and a refresh cadence come with that PR (the County flew in 2017 and 2022).

*Alternatives:* the City's footprints raised by stories (52% coverage, approximate, 2015); OpenStreetMap heights (the same City import, Item 104); deck.gl's 3D layers (MapLibre's own extrusion is enough and keeps one map).

**The owner's first look (2026-11-11): "visually, it turned out really well". Changed here:**
- **Buildings tinted by their zoning.** Each building carries the zoning family under its interior point (`f`, `l`, from the City's zoning layer the zoning tiles use); the style mixes that family's color into the neutral (42% light, 34% dark at the base, less toward the top). 5 of 782,406 pieces sit on no district and stay neutral.
- **A one-story building drawn 11+ stories (616 W Diversey).** The County's LiDAR outline 675614 (79,277 sq ft, 173 ft) merged a 16-story tower with three low City footprints beside it (no stories recorded), so all four rose to 173 ft. Measured citywide: 17,918 County outlines merge 49,336 City footprints (mostly row houses of one height, harmless); 852 outlines 60 ft and up hold a footprint with two stories or fewer or none, and 235 hold footprints whose recorded stories differ by 3+. **Fix:** an outline 60 ft and up that covers two or more City footprints, at least one with stories, is split along them (`building_tiles.split_outline`): the footprint with the most stories keeps the measured height; one with stories gets a height from them (Item 105's fit, capped at the measured height); one without is drawn low (12 ft) and see-through, marked not measured (`m: u`); what's left of the outline keeps the measured height only where it touches the tallest footprint, else it's not measured, and slivers under 2,000 sq ft are dropped. 874 outlines split into 1,084 pieces from stories and 1,118 not measured. At Diversey the three low buildings now stand 12 ft and the tower alone 173 ft. *Not checked against an independent source:* the stories are the City's 2015 ones, and the not-measured pieces are drawn, not measured; nothing in Discovery or the Profile's figures reads them. *Revisit if* the point cloud gives real roof heights.
- **The 2D/3D button** (owner's picks): on every map, bottom-right beside Expand; Build opens in 3D; on a phone only the expanded map shows it (the band stays flat and the button is hidden there). In 3D: Turn left / Turn right (45°), Tilt more / Tilt less (10° steps, 0-70°), and Reset the angle (back to 55°, -20°), each a labeled icon button; a right-drag, Ctrl-drag or two fingers also turn and tilt. A tab change keeps the angle the mode asks for. Presses in quick succession add up. `?map3d=1` is gone. Gates: `buildings3d.test.ts`, `test_building_tiles.py`, and an `e2e/ui-next.spec.ts` check (phone band flat, expanded 3D, controls labeled, axe light and dark).

**The owner's second look (2026-11-11): "616 W Diversey still renders at the tower's height"; 642 W Diversey (about 4-5 stories) and 2830 N Clark (about 7) look the same height.**
- *616:* the lot he clicked is PIN 14-28-121-008 ("~616 W Diversey", no address of its own), Assessor class **5-17, one-story commercial**, 5,722 sq ft of building on 6,736 sq ft. Not the lot the first fix touched: the City's own 2015 footprint for the 1926 tower (16 stories, 51,769 sq ft) covers it, so splitting along the City's footprints couldn't see it. (The address lot itself, PIN -007, is the tower's: class 9-91, sold for $119M in 2023.) **Fix: a tall piece is also cut along the lots the Assessor classes as one-story buildings** (2-02, 2-03, 2-04 houses; 5-17 one-story commercial), drawn at 22 ft (the measured median of the City's one-story buildings), `m: a` (`building_tiles.cut_one_story`; a cut over 80% of the piece is the tall building itself and is left alone). *Measured before use:* on one-story-class lots 80% of the City's recorded stories are 1 and 85% of the LiDAR heights are 25 ft or less, and only 127 of 317,508 measured buildings there reach 60 ft (0.04%), so the rule almost never lowers a real tall building. *Rejected:* stories implied by the Assessor's building area over the footprint (exact 70.6% vs the City's stories, but within ±1 only 31.8% at 7+ stories). Citywide it cut 65 outlines into 92 one-story pieces. The shop now stands 22 ft beside the 173-ft tower.
- *642 W Diversey and 2830 N Clark:* **not fixable with today's data.** One County outline (676492, 80,946 sq ft, 112 ft) covers both; the City recorded no stories for either footprint; the Assessor values them only as parts of multi-lot complexes (3 lots, 58,213 sq ft; 11 lots, 290,621 sq ft), so there is no per-building figure. Both stay at 112 ft. Telling them apart needs per-building roof heights from the point cloud (Item 105's open item).
- **Owner: "Looks right" (2026-11-11)** for 616 after the one-story cut; the 3D buildings, zoning tint and 2D/3D controls are approved. Next M6 step: the lot in 3D (today's building in the lot's color) and the illustrative zoning mass (below).
- *Why a fix may not show:* tiles are cached for a day. `/api/map/info` now gives the building tiles a `version` (the file's time) and the map asks for `...mvt?v=<version>`, so a rebuild shows at once.

**M6 next step: the lot in 3D and the illustrative zoning mass (2026-11-11; owner: "this looks good"):**
- **Today's building on the lot** is drawn in the lot's color (black in light, white in dark, Item 74) on every tab in 3D: the building pieces whose middle stands on the lot's outline (the County's full-precision outline when it matches, Item 92) are marked by feature state (`buildings3d.markLotBuildings`; tile features carry stable ids). Not when the lot is approximate.
- **The illustrative zoning mass, Build only:** the lot's outline raised to the district's floor-area ratio x lot area spread evenly over the whole lot at 12 ft a floor, cut at the district's height limit (a range's lower end, e.g. B3-2's "45-50 ft, varies" → 45 ft), drawn nearly solid in the district's darkest zoning color (`profileModel.zoningMass`, `buildings3d.massData`). While it shows, today's building on the lot becomes a see-through ghost in the lot's color so a taller building never hides the mass (its pieces leave the measured layer by an id filter: MapLibre doesn't apply feature state to an extrusion's height). A label on the map, "Zoning mass (illustrative)", opens what it includes (FAR, lot area, floor area, height and its limit), that it may not all fit under the limit, what is **not checked** (setbacks, lot coverage, units by lot area, parking, bonuses, landmark and overlay rules) and "not the largest building allowed" (Item 75's rule). **Not drawn** for an approximate lot, a district without a base FAR (planned developments set their own size) or a lot without an area.
- *Found on the way:* a flat layer listed after an extrusion paints over it, so the 3D layers now go above the last flat layer (the lot's fill and lines), below the labels and pins.
- *Example:* 1601 N Milwaukee (B3-2, FAR 2.2, 11,951 sq ft): 26,292 sq ft spread over the lot is about 26 ft, under the 45 ft limit; the building on the lot today is taller and shows as the ghost around it.
- Gates: `profileModel.test.ts` (mass arithmetic, range limit, approximate withheld), `buildings3d.test.ts` (family, mass data, lot test, the filter), the e2e 3D check (mass label on Build, gone in 2D).

**A square of the map missing at 1601 N Milwaukee (owner, 2026-11-11; not from M6).** About a quarter mile square (one z16 tile there is about 0.28 mi) didn't draw until a zoom. Every tile request answered 200; what every load logged was "Image pattern-dots-light could not be loaded": the planned-development dot pattern (PD 1235 and PD 1258 sit beside the lot) was added only on the map's `load` or a `styleimagemissing` event, after the first tiles were cut, and a tile cut while its fill pattern is missing can draw without it until a zoom reloads it. **Fix:** `NextMap` and `ExploreMap` add the pin and pattern images right after the map is created, before any tile (the handlers stay as a safety net). The warning is gone at 1280, 1512 and 1728 px wide, light and dark. The hole never appeared in the headless runs; **the owner confirmed it gone after the fix ("It's gone", 2026-11-11).**

## Item 108: Discovery's lot card stands on the address street for Street View (2026-11-11)

**Problem (owner, 2026-11-11): "Street View still opens in the alley sometimes."** Item 94 fixed the Profile map's cards, but Discovery's lot card (`ExploreMap` `LotCard`) still sent the raw click point with no heading. Google opens the panorama nearest the point sent, and a click in a Chicago lot's middle is usually nearer the alley behind it than the street in front.

**Fix:** the card uses Item 94's `viewpointFor` with the road lines the map has loaded at the click and, once the lot's row arrives, `streetOfAddress(row.address)`: it stands on the address street (within 60 m) and faces the lot; with no address, the nearest named street (never an unnamed alley line); with none near, the point itself. `loadedRoads` moved from `NextMap` into `map/streetView.ts` so both maps read the same road lines. Checked every `streetViewUrl` call in `ui-next`: the Profile map (`NextMap`) already snaps; Discovery's card was the only one left.

*Alternatives:* compute the viewpoint on the server from the lot's frontage (needs a frontage dataset we don't have and an extra request for a link); geocode the address to Google's own point (sends the address to Google before the click and still lands mid-lot); copy `loadedRoads` into `ExploreMap` (two copies of one rule drift).

*Evidence:* `discovery/ExploreMap.test.tsx` renders the card for a lot whose middle is ~10 m from an alley and ~50 m from its address street: the link stands on the address street, heading 90 (facing the lot); without an address it takes the nearest named street, not the alley. *Revisit if* the base tiles start naming alleys, or a lot's address street isn't in the loaded tiles (the card then falls back to the nearest named street).

## Item 109: Discovery shows the Assessor's own address where it lands on the lot, else keeps "~" (2026-11-11)

**Problem (owner, 2026-11-11, labeling lots for M4).** Discovery's index gives 116,999 of 590,174 base lots an approximate address: the nearest Address Point, marked `~` (`index_build._address_for`). That point is, by construction, another parcel's. "~2624 S Troy" (16-25-300-030) is the house next door; the Assessor calls this empty lot 2626 S Troy. The address and Street View led him to the wrong building. The Cook County Assessor's Parcel Addresses (`3723-97qp`, `prop_address_full`) had an address for all 168 approximate lots on the M4 panel, and only 16 matched the number shown.

**Measured (no model calls; `eval/assessor_address_check.py`, read-only, offline over the local index and source copy).** The Assessor's address was never taken on trust. It is checked against sources that don't come from the Assessor: the City's street centerlines (`pr57-gg9e`: block-face ranges, odd/even side), the lot's own outline (PTAXSIM) and the County's Address Points (`78yw-iddh`).
- *Prototype, 400 random approximate lots (seed 20261111).* 396 had a 2026 Assessor address. 391 of those parse as number + direction + street; the rest are placeholders: "W TILDEN AVE", "S CALIFORNIA AVE", "1538 RAILROAD", "UNKNOWN". 17 carry a unit tail ("2 FL", "B", "REAR", "HSE", "1400"). 64 share their address with other PINs, from 2 up to 275 ("55 W WACKER DR"). Only 40 (10%) equal the `~` address. The Assessor address was an Address Point for 73 of them: 30 on the lot, 25 within 60 ft, 18 farther away (another building's address).
- *A block-face range check alone is not enough.* Chicago numbers a block 00-98, so 2624 and 2626 both pass it. The finer test interpolates the number the lot's position implies along its block face. **Calibration on 2,000 random lots with their own Address Point:** the full check accepts 96.4% of their real addresses (1,907/1,979 parseable; misses are 49 position, 13 unmatched street names, 9 block face, 1 far). The same street's address 20 numbers on (five lots down) is wrongly accepted 0.25% of the time, 8 on 24%, and 4 on (the next lot) 80%. **The check catches gross errors; it cannot tell next-door lots apart.**
- *Whose number is right next door.* Among lots that pass where the Assessor and `~` give the same street but different numbers, the Assessor's number is nearer the lot's position in 42,069 cases and the `~` number in 16,062 (7 ties). Position error is about 2 numbers (median 1.8), so this is evidence, not proof. It agrees with how the `~` address is made: it always belongs to another parcel.
- *Citywide, the production rule:* **80,319 of 116,999 approximate lots (68.6%) get a checked address**; 115,726 have an Assessor address at all. Reasons the rest keep `~`: off the block face (wrong side, parity or range) 12,455; off position 11,473; street over 250 ft away 8,125; the address is an Address Point more than 60 ft from the lot 1,777; no Assessor address 1,273; placeholder 1,150; street not found 427. Of the passes, 9,418 equal the `~` address (the `~` simply goes), 3,454 had a unit tail (dropped), and 5,224 share their address with other PINs (one building across lots; the check put the address on this lot's frontage).

**Decision (the rule, `backend/discovery/assessor_address.py`).** Show the Assessor's address (unit tail dropped, the street spelled as the City's centerlines spell it) when all of these hold. 1) It parses with a number and direction. 2) The nearest block face of that street lies within 250 ft of the lot outline. 3) The side facing the lot has the number's parity and holds it in its range. 4) The number is within 6 of the number implied by the lot's position (calibration p95 4.8). 5) If that address is an Address Point anywhere, one of its points is within 60 ft of the lot. Every other lot keeps its `~` nearest address, so `~` still means "approximate". The street-name normalization covers SAINT→ST, LASALLE→LA SALLE, the King Drive variants and South Park → Dr Martin Luther King Jr, plus a street type the City doesn't use when the name has only one. It is measured: unmatched streets in calibration fell from 32 to 13, and passes went from 79,157 to 80,319. `own_address` stays the Address Points' answer, so Discovery's hidden-by-default set (Item 60) is unchanged; 43 of the 464 vacant lots over an acre would pass. Each row keeps `address_source: assessor` and `address_nearest` (the replaced `~` address), so a rerun whose check fails restores it.

**Built.** `lot_sources` adds three tables to the local copy: `assessor_address` (590,779 Chicago base PINs, latest year, the address field only, never a name: `mail_address_name` names people), `address_points` (581,882) and `centerlines` (56,002). It refuses a short read below 500k / 500k / 50k rows. `--addresses-only` adds them to an existing copy in one transaction (135 s on the Mac). `index_backfill.apply_assessor_addresses` runs inside `enrich_rows`, so a full `index_build` and the in-place `index_backfill` both apply it; no network call per lot. A copy without the tables warns and changes nothing. It is not inside `_address_for` itself, because it needs the lot outline and the centerlines, which that per-point step doesn't have; `_address_for`'s docstring points to it. The backfill prints `approximate_addresses` before and after. A report-only backfill of the local citywide index (136 s) went from 117,172 base lots with a `~` or no address to 36,758; it also gave 95 lots with no address at all an Assessor address. Room-to-build coverage was unchanged (87.3%).

**Profile links send only the PIN for these lots (owner, 2026-11-11).** Discovery's "Open profile" (lot card and list) passed an address beside the PIN whenever it wasn't `~`. The Profile opens by PIN either way, but it searches the City's permits and violations, and passed rezonings, by that address. Since the check can't tell next-door lots apart, an Assessor address could put the neighbor's permits on this lot's History tab. Rows now carry `address_source` (`assessor` or absent; `ResultRow.address_source`), and `rowFigures.profileAddress` passes an address only when it is an Address Point. The owner chose this over sending it labeled as the Assessor's (which would need History to caveat it). Tests: `rowFigures.test.ts`, `ExploreMap.test.tsx`. *Revisit if* a labeled sample shows the Assessor address is right next door often enough to search records by.

*Alternatives rejected:* **take the Assessor address unchecked.** About 31% fail an independent check: placeholders, addresses on another block face, institutions' main addresses on outlying lots, and one building's address on 275 PINs. **Block-face range only.** It cannot place a lot within its block, and lets 2690 stand for a lot at 2626. **Require an Address Point for the Assessor address.** Only 18% of these lots' Assessor addresses are Address Points; that is why they had none. **Snap `~` to the nearest point on the lot's own street** keeps another parcel's number. **Geocode with Census or Google** sends a request per lot, is a second guess at the same thing, and Census interpolates from the same ranges. **Show the address on any lot that passes with `own_address` true** would unhide 43 large vacant lots without the owner's say (Item 60). Left for him.

*Revisit if* the owner wants checked Assessor addresses to count as own addresses for the hidden-by-default rule; the Assessor's `prop_address_full` format changes (watch `placeholder` and `no_street` in the eval); the centerlines' ranges are replaced; or labeling finds a passing address on the wrong lot (tighten `TOLERANCE_NUMBERS`, which costs real addresses: calibration accepts 86% at 4).

**Production steps** (server, after merge): if Item 104's steps have not run yet, its full `docker compose run --rm --no-deps backend python -m backend.discovery.lot_sources` now writes the address tables too; otherwise `docker compose run --rm --no-deps backend python -m backend.discovery.lot_sources --addresses-only` adds them to `backend/data/discovery_lot_sources.db` (about 2 min). Then `docker compose run --rm --no-deps backend python -m backend.discovery.index_backfill` (rewrites the index's attrs in place and finalizes a new `data_version`; check `approximate_addresses.after` ≈ 37k), then restart the backend so it loads the new index. The parcel tiles carry no address and need no rebuild. Verify on the live API: `GET /api/discovery/parcel?pin=16-25-300-030-0000` gives `2626 S TROY ST`. The monthly `--refresh` keeps it through `enrich_rows`, but the address tables are refreshed only when `lot_sources` is rerun.

## Item 110: which lots are physically empty, measured from what stands on them, not the tax class (2026-11-11)

**Problem (owner, 2026-11-11):** "there's no way for someone to discover if there is a plot of land that doesn't have any buildings on it that is in a desirable area." Discovery decides "vacant" from the Assessor's class alone (`is_vacant` = class 1-xx) and hides land over an acre with no address of its own (Item 60), so empty land taxed some other way is missed, and empty land with no street number is hidden or mislabeled (Item 109).

**Measured** (`eval/empty_land.py`; read-only, offline, no model calls; summary in `eval/results/2026-11-11-empty-land/summary.json`). For every base lot (590,174) the evidence is checked against its PTAXSIM outline:
- the City's active footprints (`syp8-uezg`), counted when the footprint's interior point is inside the outline;
- the County's 2022 LiDAR outlines (Item 105), counted when at least 8 ft tall and at least 150 sq ft of the outline is on the lot, and that is half the outline or 30% of the lot (one County outline often spans a row of houses or a building on several lots);
- the City's demolition permits since 2006 (21,892) and new-construction permits since June 2022 (6,318), as points on the lot.

The 30% lot-cover term came from the first run, where a half-the-outline rule alone called row houses empty.

States:
- **empty:** no structure in either source, or nothing in LiDAR plus a demolition permit showing the City's footprint is out of date;
- **demolished since 2022:** a demolition permit after the flight;
- **new construction:** a new building permitted since the flight;
- **accessory only:** everything under 700 sq ft, a garage or shed;
- **built**, or **disagree.**

- *The two building sources agree on 92.4% of lots:* 84,827 both empty and 460,216 both with a structure. 30,097 have a LiDAR building but no City footprint, mostly commercial lots where the City's footprints have gaps. 14,569 have a City footprint but nothing in LiDAR.
- *The City's footprints keep demolished buildings.* Of the 6,340 vacant-class lots with a footprint and no LiDAR building, 74.5% have a demolition permit on the lot, against 7.6% of 20,000 built houses and 3.8% of vacant lots both sources call empty. So a demolition permit plus an empty LiDAR overrides the footprint (6,282 lots).
- *Against the owner's M4 labels (counts only; the labels file stays out of the repo):*
  - **Precision of "empty":** of the 36 labeled lots this calls empty, the owner judged 27 empty and 9 built. 5 of those 9 carry his note that the address pointed at the house next door (Item 109's problem, not this one), so 27 of 31 (87%) excluding them.
  - **Recall:** of his 35 empty lots, 27 are empty here (77%); 4 are accessory only (a neighbor's garage or shed), 3 disagree, 1 demolished since 2022.
  - The sample is small; a Street View check of a fresh random sample of "empty" lots is the next measure.
- *Citywide: 89,785 lots are empty, 1,796 demolished since 2022, 3,126 under new construction.* By kind of land:

| Land | Lots | Empty | Note |
|---|---|---|---|
| Vacant class (1-xx), what the Vacancy filter shows today | 32,121 | 27,394 (85%) | 568 demolished since 2022, 455 new construction, 1,367 accessory, 345 built, 1,946 disagree |
| City-owned (the City's land inventory) | 11,718 | 10,453 | all missed by the Vacancy filter (exempt class) |
| Commercial 5-90 / 5-80 (minor improvement: mostly parking) | 13,597 | 11,988 | missed |
| Residential classes | 452,902 | 5,409 | missed |
| Exempt (not City-owned) | 36,831 | 23,493 | missed; includes school grounds, church lots, institutional land: buildable only case by case |
| Side yard (2-41, held with the house next door) | 8,318 | 6,561 | missed; usually not a separate site |
| Other commercial | 31,010 | 1,767 | missed |
| Railroad | 2,771 | 2,472 | not a building site |

- *The old building areas on empty lots.* Of the 8,011 vacant-class lots carrying an Assessor building area, 5,793 are empty and 475 demolished since 2022 (78%). 138 are built, 142 under new construction, 256 accessory, and 1,166 disagree. Those areas come from the last characteristics row of a demolished building (the Profile already drops it, `_chars_describe_prior_structure`), so the index understates room to build on them.
- *Hidden and unaddressed.* 5,405 empty lots are hidden by default as unusual: 1,976 vacant class, 1,071 side yards, 927 exempt. 82,543 of the 89,785 (92%) have no City address of their own, which is why Item 109 and the "lot next to …" label matter.

**Decision: go for a measured "physically empty" flag, built from the two building sources plus demolition and new-construction permits, never the tax class alone.**
- Discovery needs it beside a `land_kind` (vacant class, City-owned, parking/minor improvement, side yard, exempt, railroad, other) so a search can ask for buildable empty land and leave out rail, side yards and institutional grounds.
- On a vacant-class lot that is empty or demolished, the old Assessor building area is dropped (6,268 lots).
- Next, in order (the plan the owner approved 2026-11-11):
  - step 2: index fields + the area fix;
  - step 3: hide by land kind (railroad, utility, narrow strip, common area), not by address;
  - steps 4-6: the "Empty land" quick filter, true labels, search by PIN or block.
  - Each is measured and needs the owner's review on localhost.

**Precision, measured by the owner (2026-11-11, counts in `eval/results/2026-11-11-empty-land/precision.json`; the labels stay out of the repo).** 60 random "empty" lots, by kind of land and none from his M4 panel, labeled blind in Street View and satellite (`eval/empty_land_label.py`). The page drew the County's buildings around the lot for orientation, cut out of the lot itself.

| Kind of land | Empty | Building | Can't tell | Precision (95% range) |
|---|---|---|---|---|
| Vacant class | 14 | 0 | 1 | 100% (78.5-100) |
| City-owned | 10 | 0 | 0 | 100% (72.2-100) |
| Parking / minor improvement | 10 | 0 | 0 | 100% (72.2-100) |
| Exempt | 9 | 0 | 1 | 100% (70.1-100) |
| Residential classes | 4 | 5 | 1 | 44% (18.9-73.3) |
| Other commercial | 2 | 2 | 1 | 50% (15.0-85.0) |

- The four kinds together: **43 of 43 empty (95% range 91.8-100%)**. Weighted by each kind's share of the empty pool, overall precision is 95.2%.
- The misses are all on lots whose tax class says a building exists. Two were rebuilt after a demolition, where the demolition override wrongly beat the improved class. The rest have a building neither source shows: newer than 2022 with no permit point on the lot, or a small row or townhouse PIN.

**So the "Empty land" offer is scoped:**
- It covers vacant class, City-owned, parking and minor improvement (5-90, 5-80) and exempt land: 73,293 lots, measured at 43/43.
- On lots taxed as residential or other commercial, "no building in either source" is not enough. Those stay out of the offer (shown at most as "no building on record, unconfirmed"), and the demolition override applies only to the four kinds.
- Step 2 goes ahead on this scope.

*Alternatives rejected:*
- **The tax class alone** (today): misses 10,453 City-owned and 11,988 parking or minor-improvement lots, and 15% of vacant-class lots aren't empty.
- **City footprints alone:** they keep demolished buildings (the 74.5% above).
- **LiDAR alone:** it is 2022, so it misses 1,796 later demolitions and 3,126 new buildings, and it can't see a garage under 8 ft.
- **Satellite or Street View imagery classification:** a model call per lot, no.

*Revisit if:* a Street View sample of "empty" lots finds precision under 90%; the City refreshes its footprints (the demolition override may become unnecessary); or the County publishes newer LiDAR.

**Built: step 2, the index fields (2026-11-11).**

*New per-lot fields* (`lot_facts.mark_empty_land`, run by `index_backfill.enrich` on base lots, so both the full build and the in-place backfill apply it):
- `land_kind`: vacant, city_owned, parking, side_yard, exempt, railroad, commercial, residential or other.
- `structure`: empty, accessory, built, disagree, demolished_since_2022 or new_construction.
- `empty_land: true`: only on the four kinds, when the lot is empty or demolished since 2022. The two demolition overrides apply only to those kinds.
- On an empty vacant-class lot, the Assessor's building area from a demolished building is set aside as `bldg_sqft_assessor_old`, with `bldg_sqft` 0 and source `empty_lot`, so room to build reads the empty lot. A rerun restores it before deciding again.

*Data path:* the build never loads the 1.25 million LiDAR outlines (about 1.4 GB). `lot_sources --structures-only` measures them against every lot outline once (72 s) and writes three things into `discovery_lot_sources.db`:
- `lidar_on_lot`: one row per PIN10 with a structure, giving the largest and the total area on the lot;
- every demolition permit since 2006;
- every new-construction permit since the flight.

A copy without the table marks no lot empty. `lot_sources` reads the County copy at `map_sources/county_buildings_2022.db` (Item 106) and PTAXSIM beside it.

*Verified against the measurement:* a report-only backfill of the local citywide index gives the same empty counts per kind as above. Adding the 765 lots demolished since 2022, **74,093 lots get `empty_land`**:

| Kind | Lots |
|---|---|
| Vacant | 27,962 |
| Exempt | 23,661 |
| Parking | 12,014 |
| City-owned | 10,456 |

6,268 old Assessor areas are set aside. Lots taxed as residential or commercial get a `structure` but never `empty_land`. The backfill prints `empty_land`, `structure_by_kind` and `assessor_area_set_aside`. Tests: `test_discovery_empty_land.py`.

*Not yet:* hiding by land kind instead of by address (step 3), the "Empty land" filter and labels (steps 4-6). Nothing on the page reads these fields yet.

**Production steps** (server, after merge; with Item 109's):
1. The County LiDAR copy must exist at `backend/data/map_sources/county_buildings_2022.db` (Item 106's `building_tiles` fetch).
2. `docker compose run --rm --no-deps backend python -m backend.discovery.lot_sources --structures-only` (a few minutes; or the full `lot_sources` writes it).
3. `... python -m backend.discovery.index_backfill`; check `empty_land` totals about 74k.
4. Restart the backend.

**Step 3: hidden by default by what the land is, not by whether it has an address (2026-11-11).** `index_build.unusual_rule` now hides three things:
- railroad land (class RR);
- vacant land on a development's shared outline (a common area);
- any lot narrower than 16 ft.

Item 60's "vacant over an acre with no street address of its own" is gone.

*Measured on the local citywide index* (report-only backfill, `unusual` before/after):
- **Today's 8,516 hidden lots:** 7,985 are strips under 16 ft and 531 are large vacant lots hidden only for lacking an address. Those 531 are not rail or utility strips: median 188 ft wide (10th percentile 102 ft), median about 2 acres, mostly zoned manufacturing (291) or planned development (163), and 373 of them are physically empty. They are the large sites a developer looks for, and now show.
- **Railroad parcels:** 2,771, of which only 148 were hidden (as strips). They are now hidden, because a railroad parcel is not a building site.
- **After:** 10,629 hidden. 2,991 empty-land lots stay hidden because they are strips under 16 ft (Item 104's rule, unchanged).

*Utility land is not detected.* The Assessor has no utility class we can read without owner names, so the page now says "railroad or common land, or strips under 16 ft wide" and no longer claims utility (en + es-MX).

*Alternatives rejected:*
- **Keep the address rule:** it hid the 373 empty large sites.
- **A width or length "corridor" rule for utility land:** the 531 lots are wide, and there was no measured corridor to target.
- **Hide side yards (2-41):** they are ordinary residential parcels and never `empty_land`, so the empty-land filter already leaves them out.

*Revisit if* the owner sees utility corridors among the large sites now shown.

**Steps 4-6: on the page (2026-11-11, awaiting the owner's localhost review).**
- **Filter `empty_land`** (registry, flag on the index field, `unknownPolicy: exclude`). The new UI's first quick filter is now "Empty land" instead of the tax-class "Vacant", and so is the Lot group's toggle. The live UI keeps `vacancy` unchanged, so it reads the same before and after the production backfill.
  - Local citywide copy: **71,102 lots**, the 74,093 empty-land lots minus 2,991 strips hidden by default. The page shows the count by community area.
- **Labels:**
  - The new UI's card already said "Near {address}" for an approximate address.
  - Its "what's there now" now reads empty from `empty_land`, by kind ("Empty lot, City-owned", "Empty lot or parking", "Empty lot, tax-exempt"), not from the tax class. A vacant-class lot with a building shows that building. An index built before Item 110 falls back to the class.
  - The live UI's "Approx." badge now says "Nearest address", with a tooltip saying the lot has no street address of its own.
  - Rows carry `land_kind` and `empty_land` (`ResultRow`).
- **Search by PIN:** the box takes a PIN typed any common way (14 or 10 digits, dashes or spaces) and offers it as a "PIN" choice. It opens the lot's own row and goes to it at zoom 17.5. A PIN not in the data says so.
  - The place card's "Open its Profile" sends the PIN, never the Assessor address, because the Profile searches records by address (Item 109).
  - Searching by block already works through an address on that block.

Tests: `discoveryModel.test.ts` (PIN parsing, the quick filter), `LotCard.test.tsx` (empty from what stands on the lot), registry counts.

*Open for the owner:* lots with only a garage or shed (`structure: accessory`, e.g. 2626 S Troy) are not empty land. Should a filter offer them?

**Owner's localhost review of steps 4-6 (2026-11-11): two map fixes.**
1. *Filters swapped the map for the list.* Applying filters, a ring, a place or a typed search set the view to the list on desktop. Now the page keeps whichever view the visitor is on. Only "List them" and a recipe pick switch to the list.
2. *A broad search drew nothing on the map.* Residential zoning plus density 1-2 matches 156,039 lots, but a search returns at most 5,000 map points (`MAX_MAP_POINTS`), the largest room to build first. Most neighborhoods had none of them, while the list paged through everything.
   - Now, zoomed in to lots after a search, the map asks for the search's own query (its evaluated filters via `panelFromCqs`, its unusual opt-in) scoped to the viewport, the same per-view request Explore's quick filters use. The "N lots in view" count and the "more than the map can outline" notice read that answer.
   - A search limited to the view it started in keeps its own points.
   - Checked on the local citywide copy: in Lincoln Park the matching lots outline, with 131 in view.
   - Test: `DiscoveryNextPage.test.tsx` "filters keep the map in view...".

**Owner approved on localhost (2026-11-11):** the Empty land filter, the labels, PIN search and both map fixes. Still open, for him: should lots with only a garage or shed (`structure: accessory`) count as empty land?

**A garage or shed alone counts as empty land (owner, 2026-11-11).** Asked whether a lot with only a garage or shed is different in practice, the code answers it is easier to clear. Table 14A-12-1204.2 lists "Wrecking detached private garage or carport" as a stand-alone permit with no drawings and no zoning fee, at $125 (our code text, March 2026 vintage). A building's demolition is a full wrecking permit.

`empty_land` now includes `structure: accessory` (every structure under 700 sq ft) on the four kinds. The card says "Empty lot, garage or shed only", rows carry `structure`, and the filter's help says "at most a garage or shed".

| Kind | Garage-or-shed lots added |
|---|---|
| Vacant | 1,367 |
| Exempt | 656 |
| Parking | 541 |
| City-owned | 170 |
| **Total** | **2,734** |

On the local citywide copy, `empty_land` is now **76,827** lots (73,482 shown; 3,345 strips under 16 ft stay hidden). The stale-area fix now covers 6,524 lots, up from 6,268, because empty vacant lots with a garage get it too. 2626 S Troy (16-25-300-030) is now empty land.

*Not measured:* the owner's blind check sampled only "empty" lots. The 2,734 garage-or-shed lots carry the accessory rule's own error: in his M4 labels, 4 of the 35 empty lots read as accessory because of a neighbor's garage. 12,416 lots taxed as residential have only a garage or shed and stay out, under the four-kind rule. *Revisit if* a check of the accessory lots finds real buildings.

## Item 111: the builder test moves to the end of the rewrite (2026-11-11)

**Decision (owner, 2026-11-11):** "postpone the builder's test until the very end of the development process", because there are still no builders lined up to take it. This replaces Item 88's gate. The builder test is no longer what a route waits on to become the new UI's default. It runs once, at the end of the rewrite, in Phase 10 before the stabilization window ends and before the old UI is deleted. Until then, a route switches to the new UI on the owner's approval after his localhost review, as in Phases 4-7.

**What doesn't change:**
- Item 75's pass criteria and the kit (`research/16-builder-test-kit/`, local);
- the $2 model budget for its follow-up task (Item 83);
- the rule that a failing test sends pages back for revision before the old UI is deleted.

**What it costs:** Item 88's warning grows. Every page built and switched before the test is a page the test may send back, and by the end that is every page. The old UI stays deployable until the test passes, so a failed criterion can be fixed without anyone being stranded on a broken new page.

*Alternatives:*
- **Keep the gate on route switches:** the new UI stays preview-only until builders are found, with no date.
- **Test with non-builders:** the brief's audience is small developers.
- **An unmoderated link:** it can't score the criteria.

*Revisit if* the owner lines up builders earlier: the test can run at any phase boundary, and earlier is cheaper.

## Item 112: Phase 7 M5 step 1, land in use: three sources measured, surface parking first (2026-11-12)

**Status: measured, and the owner's blind panel labeled (86 of 86, 2026-11-12). Nothing live changes and no UI is built** until the owner answers the questions at the end. Eval code: `eval/land_use.py` (fetch + measure), `eval/land_use_label.py` + `eval/land_use_label_page.html` (blind check), panel `eval/land_use_panel.json`, counts in `eval/results/2026-11-12-land-use/summary.json`. Read-only, offline after the fetch, no model calls. Tests: `eval/tests/test_land_use.py`.

**The sources.**
- **CMAP's Land Use Inventory, 2023:** the newest release, not 2020.
  - Published 2026-03-25 as the ArcGIS feature service `LUI_2023_view`; 477,225 polygons for the seven counties, 231,348 in Chicago's box (a 146 MB local copy, fetched in about 2 minutes by id batches).
  - Licence: "Not restricted. Users are expected to cite the Chicago Metropolitan Agency for Planning (CMAP)."
  - How it is made: CMAP staff update the 2020 inventory from Spring 2023 aerial photography, "supplemented by County Assessor files". The update focuses on parcels whose Assessor record or geometry changed since 2020, so an unchanged parcel carries an older code.
  - Fields: 57 codes in `LANDUSE`, a second use in `LANDUSE2`, `MODIFIER` (multi-use, stalled construction, transitional) and `OS_MGMT` (park manager).
  - Parcels are **dissolved on a common use**, so a lot is matched by overlap area, never by PIN. The median lot is 98% inside one CMAP polygon (5th percentile 87%).
  - Not fully independent of the Assessor: CMAP's vacant subtypes and its rule for a lot held with the house next door both read the Assessor's files.
  - **Parking, code 1540**, means *independent* parking, "with or without a multi-level structure". A parking lot that serves an adjacent use is coded to that use (classification schema, December 2020). So CMAP alone can't say "surface", and it misses most accessory lots.
  - FAC_NAME (facility names) is not kept.
- **The Assessor's class:** already on every lot as `land_kind` (Item 110). Only 5-90 / 5-80 (minor improvement) say parking.
- **OpenStreetMap,** through Overpass inside the City (relation 122604), as of 2026-11-12:
  - 9,314 `amenity=parking` areas and 21,835 `landuse` areas. On-street parking (`parking=lane / street_side / layby`, 1,175 areas) is not counted as a lot; `multi-storey / underground / rooftop` count as a garage.
  - Kept in its own file and attributed "(c) OpenStreetMap contributors" (ODbL 1.0). Never merged into a government source.
- **What stands on the lot:** Item 110's `structure` (City footprints + 2022 LiDAR + permits), unchanged and reused.

**Measured on the local citywide index** (590,174 base lots, 589,574 with an outline):
- *Coverage:* CMAP 100% (every lot with an outline; 157 "non-parcel" or "uncodeable"). OSM `landuse` 515,626 lots (87%), mostly block-sized residential areas. OSM parking touches 19,609 lots. The Assessor's crosswalk covers 577,641 (City-owned land has no use class).
- *CMAP vs the Assessor* (CMAP's main code over half the lot):
  - Residential classes 99.3% (96.4% residential, 2.9% mixed use).
  - Commercial classes 87.3% (incl. mixed use).
  - Industrial classes 83.4%.
  - Vacant class 1-xx 69.3%: CMAP calls 5,838 residential, by its same-owner rule or because something was built. Side yards (2-41) are 84% "residential" in CMAP, by that same rule.
  - **Exempt land (36,736 lots) is where CMAP adds what the Assessor can't say:** institutional 13,628, road right-of-way 6,635, vacant 4,374, park or open space 3,939, residential 3,489, rail 1,349.
- *CMAP vs what stands on the lot:* CMAP "vacant" lots have a building on 279 (plus 945 new construction since 2022), so its codes trail new construction.
- *OSM `landuse` vs CMAP:* agree on 87.6% of 505,121 lots, but OSM's areas are block-sized and sparse beyond residential: 3,079 grass, 3,057 brownfield, 2,141 railway.

**Surface parking** = a source says parking on at least half the lot, and Item 110 finds no building (empty, or a garage or shed only).

| Sources saying parking | Lots | No building |
|---|---|---|
| Assessor only (5-90 / 5-80) | 9,456 | 8,570 |
| OSM only | 5,446 | 4,497 |
| OSM + Assessor | 3,732 | 3,591 |
| CMAP + OSM + Assessor | 327 | 316 |
| CMAP only | 144 | 69 |
| CMAP + OSM | 74 | 67 |
| CMAP + Assessor | 55 | 49 |

- **17,159 surface-parking candidates.** 16,157 (94%) are already Empty land under Item 110's four-kind rule. 1,002 aren't, because they are taxed as residential (516), other commercial (357), railroad (53), other (45) or side yards (31). 480 are hidden as unusual.
- **CMAP finds little parking:** 1540 covers half of only 600 lots. Of the 13,568 lots the Assessor classes as parking, CMAP codes 6,946 commercial, 3,427 industrial and only 382 parking, because they serve a business.
- **OSM-only parking** (4,497) is mostly exempt land (2,614, which CMAP calls institutional: church, school and hospital lots), then City-owned (564), residential (509) and commercial (345). OSM maps only 4,352 of the Assessor's 12,526 parking lots, so its recall is low.
- **Garages:** 702 lots carry a parking use and a building; 695 are OSM multi-storey or underground.

**Found on the way: about one in five Empty-land lots is not a building site, per CMAP.**
- 14,610 of today's 76,732 Empty-land lots (19.0%) are coded as road right-of-way (7,166), park or open space (4,130), rail (1,377), utility (1,073), transport (708), water (103) or cemetery (53). 13,955 of them are shown by default.
- By kind:
  - exempt: road 6,563, open space 3,568, rail 1,233, transport 464;
  - vacant class: utility 656, road 431;
  - parking: utility 342.
- This is Item 75's "high-confidence infrastructure hidden by default", and the blind panel measures it before anything changes.
- Item 110's 43/43 checked *empty*, which these are. They are empty but not buildable.

**The blind owner check (labeled 2026-11-12; counts in `eval/results/2026-11-12-land-use/precision.json`, labels in gitignored `labels.json`).**
- The panel holds 86 lots, drawn seeded (112) from the measured pools. Lots on the Item 109 and 110 panels are left out.
- The labeler answers what the lot is used for today, from 12 choices; surface parking and parking garage are separate answers.
- The page shows only the outline, the neighbors' own addresses, street names, the City's footprints *around* the lot, a Street View link and **Lot from above** (Google's satellite view with a pin on the lot's middle). The owner asked for the overhead view on 2026-11-12, as Item 110's check had it. Item 78 bans satellite from the product's maps; this is an internal labeling page. The source answers and strata never reach the page (`/data` checked).

| Stratum | Lots | Pool | Measures |
|---|---|---|---|
| Parking, by sources (7 strata) | 42 | 16,652 | precision of "surface parking" per source and combination |
| Parking with a building | 4 | 702 | "parking garage" |
| No building, CMAP business/institution, no parking source | 6 | 2,434 | parking the sources miss |
| Empty land, CMAP road/rail/utility/transport | 8 | 8,964 | whether those leave Empty land |
| Empty land, CMAP park or open space | 6 | 4,042 | same |
| Empty land, no parking source | 6 | 44,517 | parking inside Empty land the sources miss |
| CMAP and the Assessor agree / disagree on the use | 6 / 8 | 460,180 / 25,069 | which source is right on disagreement |

`python -m eval.land_use_label score` gives precision per source and per category (Wilson 95% range) and the surface-parking rule's precision weighted by pool. Proposed thresholds (Item 75), for the owner:
- a category or source is shown at standard confidence only with blind precision of 90% or more;
- under that it is "low" (shown with its source, never filtered on), or withheld if under 70%;
- a lot where the sources disagree shows the conflict, never a silent pick.

**What the owner found** (86 lots labeled, none skipped; Wilson 95% ranges):
- **Surface parking, the rule** (a parking source on half the lot and no building): **39 of 42 were surface parking (92.9%, 81.0-97.5%)**, and 99.8% weighted by each source combination's share of the 16,652 candidates. Two of the three misses are parking lots under an elevated line or beside a railway, which the owner labeled rail; one CMAP-only lot on exempt land is empty.
- *By source:*
  - the Assessor's 5-90 / 5-80: **23 of 23 (85.7-100%)**;
  - OSM: **22 of 23 (95.7%; 79.0-99.2%)**;
  - CMAP 1540: 18 of 21 (85.7%; 65.4-95.0%). All three misses carry CMAP's parking code, and two of them nothing else, so CMAP alone is the weak source (4 of 6 CMAP-only lots were parking).
- **Parking garages: 0 of 4** (0-49%). OSM's multi-storey tag landed on commercial buildings.
- **Parking the sources miss:** of 6 lots with no building that CMAP calls a business or institution and no source calls parking, **4 were surface parking** (30-90%; pool 2,434). Inside Empty land with no parking source, 6 of 6 were empty: no hidden parking there.
- **Empty land that CMAP calls infrastructure: 7 of 8 are rail or road land** (52.9-97.8%). All seven were **CMAP road right-of-way on exempt land, 7 of 7** (64.6-100%). The miss was CMAP "utility" on a vacant-class lot, which was empty. No rail, transport or City-owned lot was drawn, so those aren't measured.
- **Empty land that CMAP calls park or open space: 2 of 6 are parks** (9.7-70.0%); 4 were plain empty lots. CMAP's open space doesn't separate a park from empty exempt land.
- **Use, where CMAP and the Assessor agree: 6 of 6 right** (homes). **Where they disagree (8):** the owner's answer matched CMAP on 4 (institution over commercial class; mixed use over a residential class, twice; vacant over a residential class), the Assessor on 2 (a new home CMAP still calls vacant; an empty lot CMAP calls residential), neither on 1 (a special district with a park, church and homes), and 1 can't tell.
- *Against the proposed 90% threshold:*
  - pass: the surface-parking rule, the Assessor's and OSM's parking;
  - short of 90%: CMAP parking alone (85.7%, 4 of 6 alone), CMAP infrastructure overall (87.5%) and use on disagreement;
  - under 70%: garages and CMAP open space;
  - too few lots to call: use categories beyond homes, and CMAP road on exempt land (7 of 7, but the lower bound is 64.6%).

**So, the recommendation (for the owner's answers; not built):**
- **Surface parking ships as its own field** from the Assessor (5-90 / 5-80) or OSM plus no building, both at standard confidence: **17,090 lots** (Assessor 8,619, OSM 4,564, both 3,907). CMAP alone stays out (it would add 69 lots at 4 of 6). **16,097 of them are already Empty land**; the other 993 are taxed as residential (511), commercial (354), railroad (52), other (45) or side yards (31) and stay out of Empty land under Item 110's four-kind rule.
- **Garage: not shown** (0 of 4).
- **Infrastructure:** hide by default from Empty land only **CMAP road right-of-way on exempt land, 6,563 lots (6,279 shown today)**, with a visible count and a Show option (Item 75). The 7-of-7 sample is small: a second blind draw of 20 such lots would settle the 90% bar before it ships. Rail, utility and transport stay in Empty land (unmeasured or missed).
- **Parks: no change.** CMAP's open space isn't shown or used to hide anything (2 of 6).
- **Use field:** homes, business and industrial from the Assessor; institution and mixed use from CMAP; on any disagreement the lot shows both with the conflict, never a pick (CMAP matched 4 of 8, the Assessor 2). Not filterable until a larger random panel measures it.
- **OSM:** a licensing review before OSM-only parking (4,564 lots) is shown; until then those lots show surface parking only where the Assessor agrees, or the OSM attribution rides with the field.

**Open for the owner (2026-11-12):**
1. Surface parking as its own filter and card line (17,090 lots), or only as a label inside Empty land (16,097 of them already there)?
2. Hide CMAP road right-of-way on exempt land from Empty land by default (6,279 shown lots), now on 7 of 7, or after a second blind draw of 20?
3. OSM-only parking (4,564 lots): show it with OSM's attribution now, or wait for a licensing review?
4. Land use on the map: a mode of the one map, a filter, or both, and what a phone shows (a mockup comes with the answer).
5. The 2,434 lots with no building that CMAP calls a business and no source calls parking (4 of 6 were parking): leave them out, or offer them as "possibly parking, unconfirmed"?

**Owner's answers (2026-11-12):**
1. **Surface parking gets its own filter and a card line** on all qualifying lots; Empty land keeps its lots and labels the parking ones.
2. **Road right-of-way: a second blind draw of 20 first.** `eval/land_use_road_panel.json` (seed 113, from the 6,268 eligible lots not on an earlier panel; `draw --road-recheck`). Hidden by default only if the 27 together reach 90%. **Result (2026-11-12): 20 of 20 were road or rail land (83.9-100%), so 27 of 27 together (100%; 95% range 87.5-100%). It passes: in the build step, Empty land hides these 6,563 lots by default (6,279 shown today) behind a visible count and a Show option (Item 75), using CMAP 2023's `1512` code on exempt land only.** Counts in `precision_road_recheck.json`.
3. **OSM-only parking waits for a licensing review.** Surface parking ships from the Assessor's classes alone for now: 12,526 lots (8,619 Assessor only + 3,907 with OSM agreeing), at 23 of 23. The 4,564 OSM-only lots join after the review.
4. **The 2,434 "possibly parking" lots stay out** (4 of 6 is under the 70% floor).
5. Still open: land use as a map mode, a filter or both, and the phone (a mockup with the build step).

**Built: surface parking and road land on the lot (2026-11-12; the owner approved it on localhost, "Looks right").**
- *Data path:*
  - `backend/discovery/cmap_land_use.py` holds the CMAP fetch (moved from the eval) and `codes_on_lots`, CMAP's main code and its share of every lot outline.
  - `lot_sources --land-use-only` writes it as `cmap_on_lot` (957,545 PIN10s in Chicago's box, 7.8 min) from `map_sources/cmap_lui_2023.db`. The full `lot_sources` writes it too when the copy is there, and warns when it isn't.
  - `LotSources.cmap_on_lot` is None on an older copy, so no lot is marked road land.
- *Fields* (`lot_facts.mark_land_use`, run by `index_backfill.enrich` right after `mark_empty_land`, so the full build and the in-place backfill both apply it):
  - `surface_parking: true` with `surface_parking_source: "assessor_class"`: `land_kind` parking (5-90 / 5-80) and `structure` empty or a garage or shed only.
  - `infrastructure: "road"` with `infrastructure_source: "cmap_2023"`: CMAP 1512 over at least half the lot, on exempt land that is `empty_land`.
  - Vintage: the Assessor's class year and CMAP 2023 (index `cmap_vintage`); confidence: both measured standard (23 of 23, 27 of 27). CMAP codes a parking lot to the business it serves, so no conflict field is kept for parking.
- *Hidden by default:* `index_build.unusual_rule` adds `infrastructure: road`. The existing "N unusual lots hidden · Show" names road land (en + es-MX); nothing is excluded for good.
- *Filter:* registry `surface_parking` (flag, `unknownPolicy: exclude`, tier more). In the new UI it is a toggle in the Lot group under Empty land. Rows carry `surface_parking` and `infrastructure`; the card says "Surface parking lot" (es "Estacionamiento en superficie").
- *Local citywide copy* (backfill of a private copy):
  - 12,529 surface-parking lots (12,195 shown; 334 strips under 16 ft stay hidden);
  - 6,563 road lots, all now hidden;
  - unusual 10,629 → 16,908;
  - Empty land shown 73,482 → **67,203**.
- *Gates:*
  - `test_discovery_land_use.py` (21);
  - registry counts 35 → 36;
  - `LotCard.test.tsx`;
  - `e2e/ui-next.spec.ts`: a new surface-parking check (request + axe light and dark). The Discovery test's stale "Vacant" quick filter now clicks "Empty land" (Item 110 renamed it).
  - The mobile matrix's Discovery audit waited for a "Try:" row that Discovery hasn't had since Item 104 (it is the Profile's search page), so it timed out on every phone; it now opens the phone sheet and picks the first goal. All 110 routes × devices pass (100 skipped by design).
  - Data Health registers CMAP's layer (`cmap.land_use_inventory`, the ArcGIS completeness test); `make test` backend 2,952 + eval 229, vitest 1,188, `npm run build`, `npm run lint` (warning cap).
- *Not built:*
  - a land-use map mode (the owner's open question 5; a mockup first);
  - the Profile line;
  - OSM-only parking (licensing review).

**Built: land use as a mode of the one map (2026-11-12, the owner's "Map mode first"; approved on localhost after three phone passes, "Looks right").**
- *Mode:* in the new UI, "Color lots by → Land use" now shows land IN use, not the tax class.
  - The old mode called every vacant-class lot "Vacant", even one with a house on it, and knew nothing about parking.
  - The lot tiles carry a new band `l` (`lot_facts.LAND_IN_USE`/`land_in_use`); the block grid takes the most common value.
  - Categories: empty land (Item 110), surface parking, homes, apartments, business, industrial, tax-exempt, road or railroad land (CMAP road land + railroad class). A vacant-class lot with a building gets no band and is drawn dotted ("not known"), never "vacant".
  - Coastal colors and a gray, each named in the key. Surface parking (lavender) carries small "P" marks and road land (peach) the transportation "+" marks (`patterns.ts`), so neither relies on color alone. They are marks, not lines (Item 97).
  - A tile file built before this has only the tax-class `u`. The mode then reads it with "vacant" left unknown, so the map is never blank before the tile rebuild.
  - The live UI and its `u` band are unchanged.
- *Phone, from the owner's look at the screenshots* ("a lot of dead space", "the key isn't collapsible"):
  - the filter groups are one row that scrolls sideways (edge fade; "Show N lots" first) instead of three wrapped rows;
  - the key has a visible close button ("Hide the key"), folds when the map is touched, and lays out in two columns without the notes.
  - the key sits on its own line below the quick filters at the right, never over them (the owner's second and third looks).
  - e2e: "Discovery on a phone: one row of filter groups, a key that folds".
- *Local tiles:* rebuilt into a private folder (33.7 MB, 154 s).
- *Gates:* backend 2,964, vitest 1,189, build, lint 67 (cap), the Discovery e2e checks, the mobile matrix's Discovery page on five phones.

**Built: the Profile line (2026-11-12, the owner's "Profile line first"; approved on localhost, "Looks right").**
- *What:* the new UI's Overview says, under the answer sentence, "Surface parking lot" or "Empty lot …" (the Discovery card's own words, "garage or shed only" when one stands there). Behind the Info tool: how we know (the class and the two building sources; for parking, the hand check of 23 lots), and Ask pre-fills "What could be built on …".
- *Source:* Discovery's own row for the lot (`GET /api/discovery/parcel?pin=<PIN10>`, every tier; `profile/useLotInUse.ts`), asked only for an exact match: a nearest parcel may be a neighbor's. `/api/scorecard`, chat and the report are unchanged.
- *What it never says:* a failed or missing row, or any other lot, shows nothing, never "not parking". An approximate match never shows it.
- *Example:* 2802 S Michigan Ave (C2-3, Assessor 5-90, nothing in the footprints or LiDAR).
- *Tests:* `profileModel.test.ts` (`lotInUse`), `ProfileTabs.test.tsx` (the line, its Info tool, axe; hidden for an approximate match). Gates as above; vitest 1,191.

**The owner's look at the Profile on a phone (2026-11-12): three map fixes (approved, "Looks right").**
- *The expand button's icon sat off-center.* On a touch screen `.touch-target` turned every square icon button (grid, centered) into an inline-flex 44 px tall and 32 px wide with its icon at the left. The new `.touch-icon` (index.css: 44 x 44 minimum, centering kept) replaces it on the new UI's 12 icon buttons (expand, close buttons, the frame's tools). Measured: 44 x 44, the icon 14 px in from every side.
- *A dark ring around the expand button on load* (localhost): React's development mode runs effects twice, so the "skip the first render" flag let the second run focus the button. It now moves focus only when the map really switches.
- *"City of Chicago, Cook County" took room:* the credit starts folded to MapLibre's small "i" button on both maps (`map/attribution.ts`) instead of open until the first drag. A tap still shows it, so the sources stay credited.
- *No 3D on a phone's map band:* intentional, the owner's call in Item 106. The 2D/3D button shows in the expanded map.

**Merged and live (2026-11-12):** PR #225 → `f9ed18f`, deploy passed, live sweep clean. Server steps run by the owner the same day: the CMAP copy (139 MB) installed from the Mac into the `backend_data` volume, `lot_sources --land-use-only`, the backfill (surface_parking 12,520, road_land 6,563, `assessor_area_set_aside` 6,554, which also closes PR #224's rerun), `parcel_tiles`, restart. Verified live: the registry lists `surface_parking` as populated; the Lot group offers 12,193 surface-parking lots and 67,254 empty-land lots; 2802 S Michigan's row is `surface_parking`; a z16 tile at the United Center carries the `l` band (54 parking, 29 empty, 19 business, 16 exempt, 3 homes). Parcel tiles are cached a day with no version in the URL, so a browser that opened the map recently sees the tax-class fallback colors until then. Whether CMAP answers the prod server directly was never tested: the Mac copy was the path.

**Production steps** (server, after merge; Jack types sudo):
1. Fetch CMAP on the Mac and install the copy as `backend/data/map_sources/cmap_lui_2023.db` (`python -m backend.discovery.cmap_land_use`). First check whether CMAP answers the server; if not, the Mac copy is the path, as for FEMA and the County's LiDAR.
2. `docker compose run --rm --no-deps backend python -m backend.discovery.lot_sources --land-use-only` (about 8 minutes).
3. `... python -m backend.discovery.index_backfill`; check `surface_parking` about 12,500 and `road_land` 6,563.
4. `... python -m backend.discovery.parcel_tiles` (about 3 min), so the lot tiles carry the land-in-use band `l`.
5. Restart the backend.

**The first recommendation, before the panel (kept for the record):**
- *Categories:* one observed-use field:
  - homes, business (commercial and mixed use), industrial, institution, park or open space, surface parking, parking garage, empty, under construction.
  - Plus a separate **infrastructure** field (road right-of-way, rail, utility, transport) and Item 75's utilization later from M4. No "underused".
- *Sources per category:*
  - Homes, business and industrial: **the Assessor's class** (current tax year), with CMAP as the cross-check. On disagreement the conflict shows.
  - Institution, park and infrastructure: **CMAP** (the Assessor's "exempt" and the City's inventory say who owns or pays, not the use).
  - Surface parking: **Assessor 5-90 / 5-80, CMAP 1540 or OSM surface parking, AND no building** (Item 110), each source's precision from the panel.
  - Garage: OSM multi-storey/underground or CMAP 1540 with a building.
  - Empty: Item 110 unchanged.
  - **OSM is never the only source of a shown fact until a licensing review** (ODbL share-alike may reach a derived database). Until then it raises or lowers confidence and marks conflicts.
- *Fields on a lot* (index, so the evaluator can filter):
  - `use` and `use_source` (assessor / cmap / osm / rule);
  - `use_vintage` (Assessor tax year, "CMAP 2023", the OSM date);
  - `use_confidence` (standard / low);
  - `use_conflict` (the sources that disagree);
  - `infrastructure`, `parking` (surface / garage) with `parking_sources`.
  - OSM inputs in their own `osm_*` keys.

*Alternatives rejected:*
- **CMAP 2020:** superseded by 2023.
- **CMAP alone for parking:** it finds 600 lots and codes accessory lots to the use they serve.
- **OSM alone:** sparse (4,352 of 12,526 Assessor parking lots) and licence-bound.
- **Classifying imagery:** a model call per lot, and imagery we must not use (Items 78, 110).
- **A new copy of `land_kind` / `structure`:** reused as is (the phase rule).

*Not measured yet:*
- use precision on a random panel (this one drew agreements and disagreements on purpose);
- CMAP rail, transport and utility inside Empty land (one utility lot, wrong);
- whether CMAP and Overpass answer from the prod server (prod access was not available to this session). The likely path is a fetch on the Mac and an installed copy, as for FEMA and the County's LiDAR.

*Revisit if:* the panel's precision for a source is under 90%, CMAP publishes a newer inventory, or the licensing review clears OSM.

## Item 113: Phase 8, the full chat page on the shared chat path (2026-11-12)

**Decision.** The new UI's chat lives at `/chat` and `/c/:id` (`ui-next/chat/ChatNextPage.tsx`) and runs on the same conversation logic as today's chat, moved out of `App.tsx` into `lib/useChatSession.ts` (load `/c/:id` and shared links, store turns, create the conversation on the first send, the `?q` / `?pin` / `?handoff` / `?ask` doors, New chat, the sign-in moment). Both UIs call the hook; nothing is forked. `VersionedRoute`'s new `door` prop sends a chat door that lands on `/` to `/chat` with its parameters.

- **Thinking, not a spinner:** `ThinkingSteps` names the steps as they happen (shimmer text, one step every 2.4 s at most), then folds to one line, "Checked N sources · S s".
- **A turn that fails to save is saved without its maps** (`lib/history.ts`: on a 422, retry text + map-only). The owner lost one turn on 2026-11-12 and it could not be reproduced. The backend now logs a rejected save's field paths and types, never values (`RequestValidationError` handler for `PUT …/messages`).
- **A chat that fails to load stops loading** and says so (`useChatSession`: a network error used to leave the outline forever; shared links too).
- **Alternatives:** a copy of App's state machine for the new page (rejected: two chats to keep correct); a new backend chat endpoint (not needed; the SSE contract is unchanged).
- **Evidence:** 5 model turns on the local stack, about $0.25 of the owner's $1 (Item 83), logged in the session notes. The owner's localhost review on 2026-11-12.
- **Revisit if** the old UI's chat is deleted (Phase 10): the hook then has one caller.

## Item 114: Phase 8, the landing and the signed-in home at `/` (2026-11-12)

**Decision.** `/` shows the landing to a visitor who isn't signed in and the home to one who is (`ui-next/home/RootNextPage.tsx`; `/?landing=1` shows the landing to anyone, linked from the panel's "About UrbanLayer"). Both follow wireframe v5, which the owner approved before build.

- **Landing:** one address search in the hero over the drifting 3D block, then the Profile's figures counting up as they scroll in (units, floors and height filling, sales, rent and tax counting), a pulsing grid, dark mode.
- **Home (B1):** search first; saved lots before recent ones; recent lots kept in this browser (`ui-next/home/lotMemory.ts`, at most 6, newest first), with "Clear all" and a bookmark on each (filled when saved; clicking a saved one unsaves it), no per-lot remove; then recent chats.
- **Alternatives:** recent lots on the server (waits for Saved, Phase 9); a per-lot remove (the owner preferred bookmark + Clear all).
- **Revisit if** Saved lands in Phase 9: saved lots move to the account.

## Item 115: Phase 8, chat evidence in a side panel: sources as what they are, and a map that matches the question (2026-11-12)

**Decision.** An answer's evidence opens in the right panel beside it (the owner chose a side panel over inline previews), with two tabs, Sources and Map, from the chips under the answer or any citation. On a phone it is a sheet.

- **Sources (`EvidenceSources.tsx`, `evidenceModel.ts`, `recordModel.ts`):** one numbered list under three headings, each with its own number color: *Municipal code* (purple), *This lot* (green: the address match and the County's facts) and *Around the lot* (blue: the City's records). A code section opens on the passage the answer used, highlighted. A code table is cut to the district's row, with the whole table one click away. Records look like the Profile's: crime split violent/property with arrests as a percentage, construction as permit cards, 311 as bars, the lot's facts as tiles. Each record links to its official source (the Assessor's PIN page, the City dataset). Code the answer read but never cited says "Read, not cited".
- **How the passage is found:** every sentence of the answer that cites the section (the reference list left out) is matched against the section's sentences. Shared numbers and district names weigh 3, other words weigh 1 and are matched on their first five letters ("reduction" meets "reduced"), and "RS-3" equals "RS3". The best sentence needs a score of 4 or it isn't highlighted. The owner found older answers bare; after this, all 5 cited sections in the 2 stored local answers with code are highlighted (uncited ones have nothing to match).
  - *Alternative:* have the analyst name the passage in its answer. Rejected for now: it needs a prompt change and more tokens, and chat isn't changing in this phase.
- **Map (`ChatMap.tsx`, `chatLens.ts`):** the Profile's own pieces (MapLibre, our tiles, the building pins and colors), with layer chips (Building nearby, Violent incidents, Zoning), hover labels, a card per point with Street View, and the ½-mile ring. What is on depends on the question: construction questions show new buildings, demolitions and renovations over $500k; safety questions show violent incidents of the last 30 days. Crime is off otherwise and never shown as squares (the owner read them as a bug). "Show on map" from a source turns its layer on and frames the ring. One map grows to full screen in place (no second map).
- **Revisit if** chat answers start naming their passages, or a lens is added (incentives, sales, conditions are open questions to the owner).

## Item 116: Phase 8 owner review, answers in the new UI and a chat list beside the panel (2026-11-12)

**Decision.** The new chat renders answers itself (`ChatMessage.tsx`), not with today's `MessageBubble`: the question is a quiet bubble, the answer is plain text, and a citation is a chip whose number takes its source's color (the Sources colors). Hovering or focusing a citation shows a card with the highlighted passage; a click opens that source. Copy sits beside "Answered <date>".

- **The chat list** (`ChatList.tsx`, `chatListModel.ts`) sits beside the main panel, which the chat page opens folded to its icons (`AppFrame secondary`). It holds New chat, a search over titles, and chats grouped Today / Yesterday / Previous 7 days / Previous 30 days / Older with the open one marked. Hiding it folds it to a strip in place, whose top button opens it again. The owner first found it "gone" when it hid completely. Hiding lasts for the tab (sessionStorage): every new visit on a wide screen opens it. On a phone it is a sheet from the top bar.
- **Alternatives:** keep the panel's Chat folder only (the owner: three clicks to reach history when the panel is folded); remember "hidden" across visits (the owner wants it open by default).

## Item 117: parcel and grid tiles carry their file's version (2026-11-12)

**Decision.** `/api/map/info` returns a `version` (the file's modified time) for the parcel, grid and building tile files, and the client adds it as `?v=` to their tile URLs (`mapStyle.versionedTiles`; Discovery's grid and the 3D buildings use it). A rebuilt tile file therefore reaches browsers at once instead of after their cache expires. Test: `backend/tests/test_map_tiles.py`, `mapStyle.test.ts`.

## Item 119: Phase 9 epic 1, Saved: lots and Discovery searches in the account, and what changed since (2026-11-12)

**Phase 9 order (owner, 2026-11-12):** Saved → Quotas → Identity (Apple, Microsoft) → Billing and entitlements → Deep analysis and the subscription flow. Only switching purchases on waits for production Stripe. Defaults the owner approved for the later epics: free accounts 50 questions a month, Pro 200 (not 300: a first question about a lot costs 4–9¢, so 300 could cost more than $19), signed-out visitors 3 questions in total, a $5 daily and $75 monthly spend cap, the 10-per-chat cap retired, no time trial at launch (the free tier and one free Deep analysis are the trial), Pro $19 a month or $199 a year, $0 model budget for the phase. There are no users or paying customers yet, so nothing needs migrating.

**Decision: Saved v1 (plan approved as proposed).** One list of saved lots, each with a private note (≤ 2,000 characters), and saved Discovery searches (≤ 20), in the account; the `/saved` page and the side panel's Saved entry (readiness `ready`); bookmarks on the Profile's tools, Discovery's lot cards and the home. Conversations stay in the chat list (Saved links to it). Recent lots stay in the browser. Out of v1: named lists, compare, sharing, email alerts (no email sending exists; owner: later), export.

- **Storage:** schema v17, `saved_lots` (key `pin:<14 digits>` or `addr:<address>`, the browser's own rule; `UNIQUE(user_id, key)`) and `saved_searches` (the page's draft to reopen it, the compiled request to re-run it, the canonical query, the match count and the matching PINs gzipped up to 20,000; a broader search keeps its count only). Both cascade with the user and `delete_user_account` deletes them.
- **API** (`backend/saved.py`, all `require_auth`, every statement `WHERE user_id = ?`, another user's id is 404): lots list/save/merge/note/unsave and `/changes`; searches list/save/new/seen/rename/delete. Bodies forbid unknown fields. Per-user rate limits (`rate_limit.check_saved_limit`: writes 60/min, merges 10/min, checks 120/min); at most four checks run at once in the app and three per page.
- **Before sign-in:** saving works in the browser (`lotMemory`). When the account first loads in a browser, its saved lots move in once through `/lots/merge` (insert-if-absent in one transaction, keeping when each was saved, clamped to the last year) and leave the browser; a lot with no point to place it stays there and the page says how many. One store (`ui-next/saved/savedStore.ts`) serves every page, so a bookmark anywhere shows everywhere.
- **What changed since a lot was saved**, on demand with no model calls: records dated after the save day (Chicago time): sales (County, by PIN), the City's permits and violations at the address (one line per inspection), a rezoning filed on the lot (the Clerk's pending docket on disk); and zoning, overlays and passed ordinances by the existing "since then" diff against a baseline the server takes at the lot's first check (never from the client; today's facts cached per parcel per day). A source that failed is listed as "Couldn't check today", never "nothing new".
- **Alternatives:** take the zoning baseline at save time (rejected: a merge of 200 lots would make 200 zoning lookups at once; the first check takes it instead, so zoning is watched from that day, which the card says); a nightly job (later, with email alerts; it reuses the same functions); store every match PIN for any search (rejected: a citywide search is 880,000 PINs).
- **Evidence:** localhost, 2026-11-12: a lot saved on its Profile, back-dated to 2023-01-01, showed the City's violations and a sign permit since then; a fresh save says "Nothing new on record" and "Zoning and overlays checked against" today; a saved "Empty land near the L" search (4,993 lots) reopened in Discovery with the same filters. A lot's first check takes 20–40 s (the City's 30 years of permits and violations, live); later checks the same hour take about 10 ms.
- **Tests:** `backend/tests/test_saved.py` (50: 401 on every route, another user's lot and search 404 on every route, forged `user_id`/`snapshot_json` rejected, bad points and outlines, caps, rate limit, merge idempotent, clamped and capped newest first, five concurrent merges never duplicate, account deletion, changes after the save day only, a failed source unchecked, the baseline taken once and reused, rezoning filed, searches new/seen/broad), `ui-next/saved/saved.test.tsx`, the Phase 9 test in `e2e/ui-next.spec.ts`, `/saved` in the phone matrix.
- **Owner's first look (2026-11-12):** a saved lot's card draws the block around it the way Discovery's list does (`ui-next/ui/BlockSlice`, now shared by Discovery, Saved and the home; a lot with no PIN draws its own County outline, never a placeholder pin), with the zoning as the colored tag; a lot saved from Discovery keeps its card's zoning tag and the "Near" of an approximate address. A saved bookmark is the palette's lavender (`nx-pill-purple` on its pale fill, `saved/bookmark.ts`), not black, everywhere it appears, the Profile's tool included.
- **Owner's second look (2026-11-12):**
  - *Chat in the main side panel is a plain link to `/chat`* (it is also marked on a conversation, `/c/:id`). The panel's Chat folder (New chat + recent chats, Phase 8) is gone: past chats and New chat live only in the chat page's own list (Item 116), one place instead of two.
  - *An approximate address is a flag, not text:* a lot saved from Discovery with a stand-in "~" address stores `approximate: true` and its raw address; cards say "Near …" in the reader's language, and the City's permits and violations at that address are never asked (they would be the neighbor's). The card says so in its own line, not as "Couldn't check today". A first attempt stored "Near …" inside the address, which broke the address lookup; caught on the owner's look.
  - *Two lots with no block* were test data saved with neither a PIN nor an outline; a lot like that now says "No lot outline on record" instead of an empty box, and the e2e fixtures carry real PINs.
- **Revisit if:** email alerts come (a nightly job over the same functions); first checks feel slow to the owner (warm the records when a lot is saved); people ask for named lists or compare.

## Item 120: Phase 9 epic 2, Quotas: one durable counter per visitor, and a spend cap that sees every model call (2026-11-12)

**Decision (plan approved as proposed).** Chat questions are counted on the server in SQLite, not in memory: a signed-out visitor gets **3 in total**, a free account **50 a calendar month** and Pro **200** (a paid plan or a voucher's `premium_until`, which `auth` already reports as `premium`), months in Chicago (reset on the 1st). Admins are counted, never refused. Limits are environment settings (`QUOTA_ANON_TOTAL`, `QUOTA_FREE_MONTH`, `QUOTA_PRO_MONTH`, `QUOTA_ANON_IP_DAY`).

- **Accounting (`backend/quotas.py`, schema v18 `usage_counters(subject, period, used)`):** before the pipeline runs, one atomic upsert per counter adds 1 only while under the limit (`ON CONFLICT … DO UPDATE … WHERE used < limit`, row count = taken). No explicit transaction: the app shares one SQLite connection, and two `BEGIN`s from concurrent requests collide (the same fix went into Saved's merge). Eighty requests at once against a limit of 50 admit exactly 50 (tested).
- **What counts:** a question that gets an answer. A clarification or a turn that fails before any answer gives it back (once; `Ticket.refund`). The full chat, the Profile's Ask drawer and the quick-chat dock share the counter.
- **Signed out:** the id is a signed, httpOnly cookie (`ul_anon`, HMAC on the JWT secret, a year); a forged cookie is a new visitor. A soft ceiling of **15 signed-out questions a day per network** (IPv4 address or IPv6 /64, read only through `client_ip()`) stops cookie clearing from minting questions while an office behind one address still works. Anonymous and network rows are pruned after 90 days (`quotas.prune`).
- **Spend cap:** `check_daily_budget(user)` sums every `llm_calls` row since Chicago midnight ($5, `DAILY_API_BUDGET_USD`) and since the 1st ($75, `MONTHLY_API_BUDGET_USD`); admins are exempt. It now sees everything: the clarification translation logged `phase="translation"`, which the table's CHECK rejected, so it was never counted. `llm_calls` was rebuilt without the phase CHECK (SQLite can't drop one; rows copied in place, tested on a v17 copy), and every call now records `user_id` (`llm.CURRENT_USER`, set per `/chat` request).
- **Retired:** the 10-questions-per-conversation cap (`config.message_limit`, the server's `MESSAGE_LIMIT_REACHED`, `useChat.MESSAGE_LIMIT`); history sent to the model is already capped at 20 messages / 60,000 characters. The in-memory limiter stays as an hourly burst guard only (signed out 10, free 10, Pro 30).
- **API and words:** `GET /api/usage` (plan, used, limit, resets on, the next plan's limit); a refused question is a 429 with `{error: "quota", plan, limit, used, resets_on, free_limit | pro_limit}`, a paused chat a 503 `{error: "paused", until}`. `useChat` exposes `atQuota`, `questionsLeft`, `usagePlan`, `quotaMessage`; both UIs say: signed out → "You've used your 3 free questions. Sign in to keep asking: 50 a month, free" (with the sign-in card); free → "They come back on December 1. Pro gives you 200 a month" (Pro named once, quietly); Pro → the date. The count shows only when 10 or fewer remain. English and Mexican Spanish.
- **Alternatives:** count dollars per user instead of questions (rejected for now: `llm_calls` had no user until this change, and questions are what people understand); keep limits in memory with a restart-safe snapshot (rejected: still per process); IP as the signed-out identity (rejected as the primary key: offices and phones share addresses, so it is only the soft ceiling); a billing-cycle month for Pro (later, with Billing).
- **Evidence:** `backend/tests/test_quotas.py` (21: Chicago month boundary incl. 05:30 UTC on Dec 1, plans, cookie tamper, free limit and reset, Pro, admin, 80-at-once race, refund once, counts survive a restart, 3 in total, network ceiling and give-back, forged cookie, prune, the real `/chat` route with the stream stubbed: answer counts, clarification and failure don't, signed-out cookie, `/api/usage`, translation logged and counted, admin exempt, monthly cap across days, the v17→v18 rebuild); `useChat.quota.test.ts` (wording in English and Spanish, a refusal stops further sends, the count from usage); the e2e test with the server's replies stubbed. One real question end to end on localhost, signed out with the allowance set to 1: counted on the cookie and the network, both model calls logged, the composer then locked with the sign-in message; **$0.056** of the owner's $0.25.
- **Owner's look (2026-11-12):** the new chat's box swapped its self-typing example for a second placeholder sentence on click (it stayed until the first letter) and could scroll a sliver; now clicking leaves an empty box with the cursor, it scrolls only past six lines, and a box at the limit shows no example (a disabled box can't take focus, so the example never stopped). A new chat at the limit says so under the box, with Sign in for a signed-out visitor. A refused question no longer leaves an empty conversation in the list (`useChatSession` skips creating one at the limit and removes one a first refusal created).
- **Rollout:** merges with Saved (PR #230). The limits are server-side, so on merge they apply to today's live UI too (signed out 3/day → 3 in total, free 25/day → 50/month, Pro 100/day → 200/month, no per-chat cap). There are no users yet.
- **Revisit if:** Billing lands (Pro may follow its billing date); real costs differ from 3.7¢ a question after a month of users; the "connect your own Claude/ChatGPT" path past the limit is built; one uvicorn worker becomes several (the counters are already safe across processes; the in-memory burst guard is not).

## Item 121: rail on the map, and rail right-of-way out of "room to build" (2026-11-13)

**Status: measured; the owner's blind panel (70 lots) is drawn and waiting for labels. Nothing live changes and nothing is built** until the owner labels the panel and answers the questions at the end. Eval code: `eval/rail_land.py` (fetch + measure), `eval/rail_land_label.py` + `eval/rail_land_label_page.html` (blind check), panel `eval/rail_land_panel.json`, counts in `eval/results/2026-11-13-rail-land/summary.json`. Read-only, offline after the fetch, no model calls. Tests: `eval/tests/test_rail_land.py` (27).

**The owner's report (2026-11-12):** the map shows roads but no rail (CTA L lines such as the Brown Line, Metra, Amtrak, freight), and lots under or along L structures read as "room to build" in Discovery.

**The sources.**
- **CTA 'L' lines**, City of Chicago `xbyr-jnvx` (updated 2024-07-23): 153 segments, 92 miles "Elevated or At Grade" and 11 miles "Subway", each with its lines ("Brown Line") and a stretch name. The City says the lines are drawn "approximately".
- **North American Rail Network lines** (FRA, in USDOT/BTS's National Transportation Atlas Database, updated **2026-10-19**; public domain, 17 U.S.C. § 101): 2,203 segments in Chicago's box with owner (UP, NS, BNSF, CN, NIRC = Metra, AMTK ...), trackage rights, passenger service (Amtrak / commuter / both) and network type. Kept: main and other lines 605 miles, yards 275 miles, industry spurs 75 miles. Left out: abandoned (A), trail (T), out of service (X: includes The 606), rail-banked (R). No CTA lines in it.
- **CMAP's 2023 Land Use Inventory** (the Item 112 copy): code **1511, rail right-of-way**, 1,687 polygons in Chicago's box.
- **The Assessor's railroad class (RR)**, already on every lot as `land_kind: railroad` and hidden as unusual since Item 60.
- *Considered and left out:* the City's "Railroads" (2010) and "Metra Lines" (2011) shapefiles (superseded by NARN, 15 years newer); OpenStreetMap railways (the ODbL licensing review from Item 112 is still open).

**How the lines sit against each other** (points every 50 ft along each line, distance to the other source):
- *CTA elevated/at-grade vs CMAP rail or an RR-class lot:* 46.9% inside, median **5 ft**. Of 9,766 points: 4,580 on rail land, 1,867 on another lot, 3,319 on no lot at all (the L over streets: Wells, Lake, Wabash, the expressway medians). So the CTA line is where CMAP's rail land is wherever both have it; elsewhere it runs over streets or over lots CMAP codes otherwise (mostly road right-of-way: below).
- *NARN main lines vs CMAP rail or RR lot:* 77.1% inside, 84.3% within 50 ft, median 0 ft. Yards 58.8% inside (CMAP codes many yards as industrial or transport), industry spurs 70.3%.
- *CTA vs NARN:* 2.4% within 25 ft: they don't overlap (different railways), so neither checks the other's position.

**Lots** (590,174 base lots, 589,574 with an outline; a line "on the lot" = 25 ft or more of it inside the outline; CMAP = rail right-of-way over half the lot):

| Sources on the lot (not RR class) | Lots | Shown in Empty land today | Shown with room to build today | Built (both building sources) |
|---|---|---|---|---|
| CMAP + CTA line | 648 | 570 | 6 | 19 |
| CMAP only | 520 | 371 | 42 | 5 |
| CMAP + NARN (+ CTA 16) | 327 | 278 | 17 | 10 |
| CTA line only | 769 | 85 | 96 | 55 |
| NARN only | 333 | 142 | 75 | 102 |

- RR-class lots: 2,791, all hidden already (Item 60).
- **CTA line only:** 579 of the 769 are CMAP *road* right-of-way on exempt land, so Item 112 already hides them as road land. The rest are mostly lots beside the L that the approximate line clips (homes and shops: 26 residential, 21 commercial).
- **NARN only:** noisy: 102 built, 115 taxed commercial (industrial yards and plants beside the tracks).
- **The Brown Line's own lots** (example, the 14-18-500 and 14-19-500 blocks along Ravenswood): tax-exempt, nothing built, CMAP rail 84-100% and the CTA line through every one; today they are Empty land and shown. That is the owner's report.
- **Structure "disagree" on rail land** (78 exempt lots with CMAP rail): one building source sees a structure the other doesn't; on rail land that is likely the elevated structure itself in the LiDAR. The panel checks it.
- **Not marked, counted:** 61 lots over the CTA subway (10 built; you can build over a subway) and 26 lots crossed only by an industry spur (6 built).
- **Possible misses:** 3,546 shown Empty-land lots lie within 60 ft of a CTA elevated or NARN line with no source on them (lots beside the tracks).
- Shown Empty land today: 67,108. The CMAP rule alone would take 1,219 of them out.

**The blind owner check (drawn, seeded 121, not yet labeled).**
- 70 lots, none on an earlier panel (Items 109, 110, 112). The page is Item 112's: outline, neighbors' own addresses, street names, the City's footprints around the lot, Street View, the lot from above. Never the rail lines, the sources' answers or the stratum (test-checked).
- Answers: rail (tracks, structure or embankment on or over the lot; parking or storage under the tracks counts), rail yard or station grounds, empty land beside the tracks, parking lot not under the tracks, a building, street/alley/expressway land, park/garden/trail, can't tell.

| Stratum | Lots | Pool | Measures |
|---|---|---|---|
| CMAP + CTA, Empty land | 10 | 570 | the main rule, L right-of-way |
| CMAP + NARN, Empty land | 8 | 278 | the main rule, railroads |
| CMAP only, Empty land | 10 | 371 | CMAP alone |
| CMAP, not Empty land (a building source sees something) | 6 | 132 | whether rail land with a "structure" is the L itself |
| CTA line only, Empty land | 8 | 85 | the CTA line as a source on its own |
| CTA line only, other (mostly built) | 5 | 104 | what the approximate line clips |
| NARN only, Empty land | 6 | 142 | NARN on its own |
| NARN only, other | 5 | 177 | same |
| CMAP road land with a CTA line (hidden today) | 6 | 579 | rail or road: which words the Profile uses |
| Empty land within 60 ft of a line, no source | 6 | 3,546 | what the sources miss |

Run: `PYTHONPATH=. python -m eval.rail_land_label serve` (localhost:8035), then `... score --out eval/results/2026-11-13-rail-land/precision.json`.

**The plan (for the owner's go after the labels; not built).**
1. **Rail on every new-UI map.** A `rail` layer in our base tiles (`base_tiles.py`), from NARN (kept kinds, with `kind` freight / commuter / amtrak / yard from its owner and passenger fields) and the CTA lines (`kind` cta, `name` = the lines, subway left out of the drawing). Drawn in the Cities: Skylines manner as thin rail lines (a quiet casing with short ties, no satellite, Item 80) above the lot fills; the CTA L slightly heavier where elevated, with its line names from zoom 15 like street names; yards and spurs from zoom 14. It joins the Streets group in the key ("Streets and rail"), so every map that has the base gets it (Profile, Discovery, chat panel). Base tiles grow by a few hundred KB.
2. **Rail land on the lot** (index fields, a `data_version` bump through the backfill): `infrastructure: "rail"`, `infrastructure_source: "cmap_2023"` (plus `"cta"` / `"narn"` when a line confirms), on the rule the panel supports. The working proposal: **CMAP rail right-of-way over half the lot, on vacant, City-owned, parking or exempt land with no building** (1,361 lots, 1,219 shown today), widened to the "structure" lots and to CTA- or NARN-only lots only if their strata reach 90%. `lot_sources --land-use-only` adds the per-lot rail table (`rail_on_lot`: CMAP 1511 share, CTA and NARN feet).
3. **Hidden by default with a visible count**, like road land: `unusual_rule` adds rail; the "N unusual lots hidden · Show" line names rail land (en + es-MX).
4. **Never room to build:** rail and road land get no `room_sqft`; their room reads "rail or road land, not a building site" (a new `room_scope: "right_of_way"`, tile band `r` drawn like transportation zones), even when Show brings them back.
5. **Profile Overview line:** "Rail right-of-way" (es "Derecho de vía ferroviario") under the answer sentence, with how we know (CMAP 2023, the CTA or federal rail line, the owner's check) behind the Info tool, from the Discovery row as Item 112's line does (exact match only).
6. **Road land crossed by the L:** relabeled rail only if the panel's six say so; otherwise it stays road land (both hidden either way).

**Open for the owner:**
1. Label the 70 lots (about 15 minutes; Street View and the overhead view).
2. The CTA L on the map: one neutral rail style for all rail (proposed: color by role, Item 74), or each L line in its CTA color?
3. Road land too: drop its room to build along with rail land (proposed, so both read the same), or rail only?

**Production steps** (after merge; the owner runs them with sudo): fetch the rail lines (`python -m eval.rail_land fetch`, or the build step's own fetch; the City portal and BTS's ArcGIS answer the server unless proven otherwise, else copy from the Mac), `lot_sources --land-use-only`, `index_backfill`, `parcel_tiles`, `base_tiles`, restart. Written out in full with the build.
