# Cleanup inventory: post-rewrite code-debt pass (Phase 1)

2026-11-25 · PRD: `claude-context/plans/2026-11-25_post-rewrite-cleanup-prd.md` · decision **Item 137** (`decisions/2026-11_post-rewrite-cleanup.md`)

> **Outcome (2026-11-25, branch `chore/post-rewrite-cleanup`).** The owner took every recommendation ("go with your picks").
> - **Done:** A, B1, B3 (the dead parts), D (1,467 keys in all), F1–F7 (minus the oracle helpers kept, see Item 137), G1–G3, knip in CI, lint cap 35.
> - **Not done:**
>   - **C file renames and B2 moves.** Item 126 had already kept those names at the owner's call; the inventory hadn't read it.
>   - **E (the PDF report).** Waits for the owner's zero-purchases check, then gets its own PR.
>   - **G6/G7.** Local files, left as they are.
>
> The numbers before and after are in Item 137.

How it was found: `knip` 5.88 run in normal and `--production` mode, then each item re-checked by searching for its name as text across `frontend/src`, `e2e`, `backend`, `scripts`, `deploy`, `eval`, `ingestion`, `.github`, nginx and compose files. Backend: a reference count over top-level functions and classes (a stand-in for `vulture`), a route→caller map, and an import count per dependency. Every verdict below names its evidence. **Gate 1: nothing here is acted on until Jack reviews it.**

## Summary

| Area | What was found | Size | Confidence |
|------|----------------|------|------------|
| Frontend whole files | 1 file unreachable (`lib/parcelMap.ts`), 2 components dead in practice (`ChatInput`, `discovery/Chips` + `ui/Chip`) | ~600 lines + tests | High |
| Frontend inside live files | `lib/mapColors.ts` 624 lines, only `capLabel` used; `lib/analytics.ts` 148 lines, only a type used; 52 exports nothing uses; 17 that only tests use | ~1,100 lines | High |
| Old chat chain | Ask drawer still renders through the old `MessageBubble` + 6 helpers | ~650 lines | Needs Jack (visible) |
| Translations | ~1,400 of 4,353 English keys have no reference; the same keys again in Spanish. All 8 namespaces load into the main bundle | ~3,000 JSON lines across both languages | High for 3 groups; the rest checked key by key |
| Rewrite-era names | 18 `*NextPage` files, `NextMap`, `AuthOverlaysNext`, `NextUi*` types | mechanical | High |
| Retired $25 report (backend) | `/api/report` PDF path, Jinja template, weasyprint + matplotlib; only reachable from Settings' past-purchase rows | ~3,500 lines + 3 prod deps | **Needs Jack** |
| Backend functions | 3 dead, 31 only tests call (pre-Item 121 user lookups, old map label helpers) | ~400 lines | High (minus test resets) |
| Backend routes | 2 routes nobody calls, 1 only dead code calls (`/section/{id}`) | small | Needs Jack |
| Docs | `AGENTS.md` describes July (unmerged branch, $25 report); skills disagree on `page-design.md`; 5 guides are history | — | High |
| CSS | Clean (custom classes all used; Tailwind purges the rest) | — | — |

## Phase 0 baseline (before)

| Measure | Value |
|---------|-------|
| Frontend non-test source | 199 `.ts/.tsx` files, 37,094 lines (incl. CSS) · tests 9,021 lines |
| Backend non-test source | 178 `.py` files, 53,556 lines · tests 40,788 lines |
| Locale JSON | 11,577 lines (en + es), 263 KB English alone |
| Build | 57 chunks, 4,244 KB raw / 1,273 KB gzip. Main `index` chunk 864 KB / 280 KB gzip (locales are bundled into it); `jspdf` 400 KB and `html2canvas` 199 KB raw, lazy |
| ESLint | 45 warnings (cap 65): 21 `set-state-in-effect`, 15 `only-export-components`, 6 `refs` |
| vitest | 809 passed |
| pytest (`-m "not integration"`) | 3,341 passed, 62 deselected. The integration run fails `test_311_api_returns_data` (live Socrata; network, not code) |

---

## A. Frontend: delete (high confidence)

| # | Path | What / evidence | Verdict |
|---|------|-----------------|---------|
| A1 | `src/lib/parcelMap.ts` (76) + its test | Unreachable from `main.tsx`; only its own test imports it | **Delete** |
| A2 | `src/components/ChatInput.tsx` (332) | The component itself has no importer. `Composer.tsx` and `useChatSession.ts` import only the `PendingAttachment` **type** from it | **Delete**; move the type into `app/chat/` |
| A3 | `src/discovery/chips.tsx` → `Chips` component, and `src/components/ui/Chip.tsx` (121) | `Chips` is used only by `chips.test.tsx`; `Chip` is imported only by `Chips`. `chipLabel` in the same file **is** used (DiscoveryNextPage) | **Delete** `Chips` + `Chip.tsx` + their tests; keep `chipLabel` |
| A4 | `src/lib/mapColors.ts` (624) + `mapColors.test.ts` | The old deck.gl map's colour/label system. The only production import is `capLabel` (admin `PieChart`). 26 exports used nowhere, 3 only by the test | **Delete the file**; move `capLabel` (~10 lines) next to `PieChart` |
| A5 | `src/lib/analytics.ts` (148) | Only the `PieSlice` type is imported (4 admin charts). `computeTrends`, `computePieSlices`, `getTrendMonthLabels` unused | **Delete**; move `PieSlice` to `app/admin/` |
| A6 | Dead exports (no reference anywhere outside their definition) | `chatModel.PreviewKind`; `discoveryModel.TRANSIT_WALKS`; `filterGroups.FLAG_YES`; `communityAreas.SORTED_CAS`; `coverage.liveAreaNames`, `formatAsOf`; `searchClient.fetchOutlineRow`; `summary.seamPrompt`; `types.FilterTier`; `api.createReportCheckoutSession`, `CodeSubsection`, `TypicalLot`, `WhatIfResponse`; `codeRefs.isResolvableSection`; `confidence.marginText`, `SourceBullet`; `constants.SPLASH_STATS`, `SOURCE_FLASH_MS`; `csvExport.exportCSV`; `failedSources.FEMA_FLOOD_MAP_URL`, `ZONING_MAP_URL`; `format.translateFloodSubtype`, `localizeZoningValue`; `types.SidebarView`; `useChatSession.ChatSession` | **Delete** each |
| A7 | Code only tests exercise (exported, unused in its own file, called only by a test) | `evidenceModel.citingSentence`; `SuggestCorrection.resetCorrectionsSent`; `discoveryData.fetchLotShape`, `shapePath`; `mapStyle.LAYER_IDS`; `filterMenu.menuGroups`; `registryClient.isStale`; `rowFigures.rowFigures`; `api.checkReportAccess`, `api.fetchSection`; `failedSources.failedLabels` | **Delete** with their test cases. Keep the `_resetForTests` / `_resetCache` hooks; they are test seams |
| A8 | `frontend/vite.wave.config.ts` (untracked) | Local dev config for the 2026-11-03 wave (:5175 → :8003) | **Delete locally** (not in git) |

Not dead, for the record: `e2e/live-sweep.mjs`, `e2e/mobile-audit-report.mjs` (npm scripts) and `scripts/render-hero.mjs` (manual hero render, Item 133). knip flags them only because nothing imports them. **Keep.**

**209 exports are used only inside their own file.** Dropping the `export` keyword is cosmetic churn. **Keep** them, and set knip's `ignoreExportsUsedInFile: true` so the ratchet ignores them.

## B. Frontend: consolidate or move (Jack's call where visible)

| # | Item | Evidence | Verdict |
|---|------|----------|---------|
| B1 | **Ask drawer uses the old chat renderer.** `app/ask/AskDrawer.tsx` → `components/MessageBubble.tsx` (284), which alone keeps `ThinkingTrace` (36), `ActivityStatus` (116), `DisclaimerBanner` (13), `CitationPill` (66), `DataPill` (83), `Tooltip` (52) alive. The chat page uses `app/chat/ChatMessage.tsx` + `ThinkingSteps.tsx` | Each of those 6 has `MessageBubble` (or each other) as its only importer | **Ask Jack.** Recommend moving the drawer onto `ChatMessage`; ~650 lines go. The drawer will look like the chat page |
| B2 | Live components still in the pre-rewrite folders: `components/AddressInput`, `AnsweredOnNote`, `CountUp`, `ExportReport`, `ShareModal`, `ui/Modal`, `ui/Toggletip`, `ui/StatusLabel`, `ui/ConfidenceState`, `settings/PurchaseRow`, `auth/ProviderButtons`; `contexts/*` | All have importers in `app/` | **Move** into `app/` (`app/ui/`, `app/chat/`, …) after A/B1, so `src/components/` stops existing. Pure moves, no logic |
| B3 | `lib/scorecardVerdict.ts` (601) | Live (`computeVerdict` feeds Overview/Build and chat grounding), but 11 constants/functions are exported for nothing | **Keep the file**; un-export or delete the 11 during the pass; rename belongs to C |
| B4 | Chat transcript export: `ExportReport` (564) + `reportBuilder` + `pdfExport` → `jspdf` + `html2canvas` (~600 KB raw, lazy) | Live: the chat page's Export button | **Keep** (a feature). Flagged only because it's the largest frontend dependency |

## C. Rewrite-era names (rename only, high confidence)

- 18 files: `AboutNextPage`, `PrivacyNextPage`, `AdminNextPage`, `ChatNextPage`, `DiscoveryNextPage`, `HomeNextPage`, `RootNextPage`, `LandingNextPage`, `NotFoundNextPage`, `PricingNextPage`, `ProfileNextPage`, `SavedNextPage`, `SettingsNextPage` (+ 3 tests) → `*Page`. `NextMap` → `ParcelMap` (or `Map`). `AuthOverlaysNext` folded into `AuthOverlays` (the wrapper is 20 lines).
- `NextUiCrime`, `NextUiSchools`, `NextUiTract`, `NextUiArea311`, `NextUiConstruction`, `NextUiData`, … types in `lib/api.ts` → drop the `NextUi` prefix.
- **Recommend Keep:** the `.ui-next` root class (34 files), the `nx-*` token/Tailwind prefix, and the `next` i18n namespace (2,051 keys, 149 call sites). Renaming them touches thousands of lines for no reader benefit, and they are documented in `app/app.css`. **Ask Jack** if he wants them renamed anyway.

## D. Translations

All 8 namespaces (`common chat sidebar landing map data pages next`) are imported eagerly in `lib/i18n.ts`, so dead keys cost main-bundle bytes.

| # | Group | Evidence | Verdict |
|---|-------|----------|---------|
| D1 | `landing` namespace: 67 keys × 2 languages | No `useTranslation("landing")`, no `landing:` key anywhere; the current landing uses `next` | **Delete** the namespace (en + es + `i18n.ts` lines) |
| D2 | `sidebar` namespace: 35 keys | Only `sidebar:map` is used (ExportReport alt text); the rest belonged to the old sources sidebar | **Delete** the 31 with no reference, then check the 3 that only match a common word; move `map` to `common` |
| D3 | `pages.scorecard.*`: 521 keys unreferenced | The old Scorecard page's strings; `scorecardVerdict.ts` uses 53 others under the same prefix | **Delete** the unreferenced ones |
| D4 | Remaining ~780 unreferenced keys: `data.*` 477, `map.*` 135, `common.*` 60, `pages.settings/pricing/nav` 52, `next.*` 42, `chat.*` 13 | Literal-string search found no reference. Some may be built at runtime (`t(\`crimeLabels.${x}\`)`-style), so another ~1,400 keys were already set aside as "maybe dynamic" and are **not** in this count | **Delete per key in Phase 2**, guarded by: i18next `missingKeyHandler` logging in dev + vitest + `npm run test:mobile` + live-site-sweep on localhost |

## E. Backend: the retired $25 report (needs Jack)

The $25 purchase ended in Item 123 (`/api/checkout/report` already returns 410). What still exists so **past buyers can re-download** from Settings → Purchases:

- `GET /api/report` and `GET /api/report/access` (`main.py` ~2598–3000), `_record_report_render`
- `backend/report_render.py` (177) and `templates/zoning_report.html` (1,724)
- The PDF-only chart/map drawing inside `report_builder.py` (matplotlib, ~8 functions)
- Prod dependencies used only there: **weasyprint** (pinned <70, pulls system libraries into the image), **matplotlib**, **jinja2**
- Frontend: `PurchaseRow`, `fetchReport`, the Purchases section of Settings, nginx's 180 s `/api/report` timeout
- `db.save_report_purchase` (called only by tests) and the purchases table

If the prod database holds no report purchases, every line above can go. `report_builder.py` itself **stays**: `deep_analysis`, `chat_sources` and `provenance` use its assembly functions. The same applies to `report_i18n.py`.

**Ask Jack:** (1) confirm zero `report_purchases` rows in prod (Jack runs the query; I don't touch the server); (2) retire the PDF path. If yes, this is the single largest cut: roughly 3,000–3,500 lines, 3 dependencies and a smaller Docker image.

## F. Backend: functions and routes

| # | Item | Evidence | Verdict |
|---|------|----------|---------|
| F1 | `payments.create_report_checkout_session`, `deep_inputs.reset_new_construction`, `provenance_figures._money` | No reference anywhere | **Delete** |
| F2 | Pre-Item 121 user helpers in `db.py`: `upsert_user`, `get_user_by_email`, `get_user_by_google_id`, `get_user_by_stripe_customer`, `update_user_tier`, `update_user_stripe` (~65 lines) | Only tests call them. Item 121 made identity-only sign-in the rule and Item 123 made Stripe's state the tier source | **Delete** with their tests, after checking that no test fixture relies on them to seed users (if one does, move it into the test helpers) |
| F3 | `db.count_user_messages`, `db.update_message_map_data`, `map_geometry.prepare_parcel_zoning`, `zoning_label_points` (old deck.gl labels), `code_sections.extract_subsection`, `retrieval/area_stats.get_area_stats`, `overlays.query_all_overlays`, `provenance.entry_is_dated`, `provenance_figures.area_benchmark_entry`, `typical_lot_entry`, `discovery/index_build._compute_value_percentile`, `_populated_fields`, `_recipe_counts`, `discovery/parcel.DictParcel`, `cqs.cqs_equal`, `capacity_map.normalize_pin`, `data_health.in_module`, `layer_id_of`, `inflight.in_flight` | Only tests call them | **Delete** each with its tests, except where the function is a deliberate test oracle (`cqs_equal`, `DictParcel` look like this: **Keep**, add a one-line reason) |
| F4 | Test resets: `clear_rate_limits`, `clear_state`, `reset_artifact`, `reset_for_tests`, `_reset_cache_for_tests` | Test seams | **Keep** |
| F5 | `GET /section/{section_id}` + nginx `location /section/` | The only frontend caller is `fetchSection`, which only a test uses (A7). The old sources sidebar opened full sections; the new evidence panel shows the cited chunk | **Ask Jack**: was dropping "read the full section" deliberate? If yes, delete the route, the nginx block and `fetchSection` |
| F6 | `GET /api/community-area` | No caller in the frontend, scripts, deploy, eval or tests | **Delete** (Ask if it was meant for outside use) |
| F7 | `POST /api/newsletter` + `db` subscriber insert + rate-limit entry | The newsletter form was on the old landing (its keys are in the dead `landing` namespace). Nothing posts to it now | **Ask Jack**: is email capture coming back on the new landing? If not, delete the route and keep the table (data) |
| F8 | `/api/auth/apple/callback`, `/api/auth/dev/authorize`, `/api/admin/cache` | Called by Apple, the localhost test sign-in and ops (`backend-guide.md`) respectively | **Keep** |
| F9 | Python deps | Every prod requirement is imported except `uvicorn` / `python-multipart` / `lxml` (runtime or parser backends; keep). weasyprint, matplotlib and jinja2 depend on E | Follows E |

## G. Docs and repo

| # | Item | Evidence | Verdict |
|---|------|----------|---------|
| G1 | `AGENTS.md` (89 lines, last touched July) | Says Property Profile is "unmerged" and sells the $25 report; memory notes it is stale | **Replace** with a 3-line pointer to `CLAUDE.md` (other agents read `AGENTS.md`) |
| G2 | `page-design-rules` skill points at `guides/page-design.md`; `load-urbanlayer-context` says **never** read `page-design.md`; CLAUDE.md calls it history | Contradiction an agent will trip on | **Fix the skill**: point it at the current rules (`frontend-redesign-vision.md` + decisions Items 73+), or fold `page-design.md`'s still-true rules into the skill |
| G3 | History guides: `bento-pro-redesign.md`, `bento-pro-phase3-app-surfaces.md`, `design-system.md`, `light-dark-theming.md` (mechanism still true), `page-design.md`, `scorecard-dashboard-model.md` | Marked historical in CLAUDE.md / README | **Archive** to `claude-context/archive/` per README rules; carry the still-true theming mechanism into `frontend-guide.md` |
| G4 | `guides/report.md` | Describes the PDF report | Follows E |
| G5 | `core/architecture.md` (June), `guides/backend-guide.md` (June), `guides/frontend-guide.md` (2 old-UI mentions) | Older than the rewrite | **Review** in Phase 2 for statements about the old UI; edit in place |
| G6 | Root: `chicago-il-1-june.html`, `chicago-il-codes.html` (97 MB each), `vibecoded-design-tells-main.zip` (30 MB), `test-results/` | All git-ignored, local only | **Ask Jack** (local disk only, does not affect the repo) |
| G7 | `plans/` (~50 local, untracked prompt files) | Shipped phases' prompts | **Ask Jack** (PRD question 4) |

---

## Decisions Jack needs to make (Gate 1)

1. **B1**: move the Ask drawer onto the new chat renderer (visible change)?
2. **E**: confirm zero report purchases in prod, then retire the PDF report path and its 3 dependencies?
3. **F5**: delete `/section/{id}` ("read the full section"), or bring the feature back in the evidence panel?
4. **F7**: delete `/api/newsletter`, or will email capture return?
5. **C**: keep `.ui-next` / `nx-*` / the `next` namespace as they are (recommended)?
6. **G6/G7**: tidy the local root files and `plans/`?
7. Can `knip` be added as a devDependency with a CI check (§7 of the PRD)? It already runs from the local npx cache, so the inventory didn't need it.

Everything not on this list is marked Delete, Move, Rename or Keep with evidence, and runs in Phase 2 in the PRD's order.

## Proposed Phase 2 commit order (one branch, one PR)

1. A1–A7 dead code + tests → 2. D1–D3 translations → 3. C renames → 4. B2 moves → 5. B1 (if approved) → 6. F1–F3, F6 backend → 7. E (if approved) → 8. G docs → 9. Ratchets: ESLint cap to the new count, knip config + CI step.

Preconditions (PRD): #278 and #271 merged or closed; #270 (Tailwind 4) not combined with this pass; branch from a fresh `main`.
