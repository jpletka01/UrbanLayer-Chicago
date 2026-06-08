# Known Issues — UrbanLayer

## Open Bugs

~~**Conversation history click-to-load is broken**~~: **Fixed** — Schema v5 migration adds `user_id` to `conversations` table. All conversation CRUD endpoints now use `Depends(get_current_user)` for per-user scoping. Legacy conversations (null user_id) are visible to all users. Frontend `getConversation`/`listConversations` now log errors on failure, and `loadConv` shows an error banner when a conversation can't be loaded.

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+ while unfiltered queries return data fine. The 2026-06-02 benchmark showed 0/7 successful lookups. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN to unblock the full property pipeline (characteristics, assessments, sales, tax) but provides **no parcel polygon geometry** (only centroids) and no address — both are filled in downstream by CCAO Characteristics. When GIS is up, it's used preferentially (includes polygon + address). A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down rather than skipping.

## Known Limitations

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Census tract-level demographics (via Census Reporter API) now provide all housing fields: median home value (B25077), median gross rent (B25064), owner-occupied % (B25003), vacancy rate (B25002), and bachelor's degree % (B15003).

**Violation categories are homegrown**: Chicago's violations dataset has no standard category field — only free-text `violation_description`. Our `_categorize_violation()` does first-match keyword bucketing into 18 custom categories, supplemented by code-prefix mapping (EV→Elevator, BR→Boiler) using the `violation_code` field. The code prefixes are heterogeneous alphanumeric strings, so full code-to-category mapping isn't practical — keyword matching remains the primary strategy.

~~**Reranker disabled in production**~~: **Re-enabled** (2026-06-06) — Server upgraded from CX22 (4GB) to CX32 (8GB). `RERANKER_ENABLED=true` in `docker-compose.prod.yml`. Full vector search pipeline with cross-encoder reranking now active in production.

**FEMA endpoint flakiness**: The FEMA NFHL MapServer occasionally returns 500 errors or empty results. Graceful degradation handles this (flood zone shows as "Unknown" rather than failing the whole request). Observed intermittently during production testing (2026-06-05).

**CCAO assessment 400 errors**: Some PINs return HTTP 400 from the Cook County Assessor API. Graceful degradation shows assessments as unavailable. Root cause unknown — may be invalid PIN format or stale PIN data from the Socrata parcel fallback. **Impact on Report v2**: When assessments fail, `estimated_annual_tax` and `total_assessed_value` are null → effective tax rate cannot be derived → tax rate field omitted from PDF. Similarly, the Cook County Parcel Universe (`pabr-t5kh`) sometimes returns 400 on bounding-box queries → comparable sales 3-hop pipeline fails at step 1 → comps section shows "No comparable sales found."

**Report v2 address-specific data gaps**: The permits dataset (`ydr8-5enu`) stores street addresses as three separate fields (`street_number`, `street_direction`, `street_name`). Some properties have permits filed under variant address formats (e.g., "MILWAUKEEAV" vs "MILWAUKEE") or under a different street number if the lot spans multiple addresses. When no exact-match permits are found, the section renders "No permits found" rather than showing the community-area-level permit data. This is correct behavior (specificity > noise) but means some properties with genuine permit history may show empty. A fuzzy-match fallback (LIKE queries) would increase false positives.

**iPhone 12 Pro black space on right side**: Reported during mobile UX testing (2026-06-06) — a black strip appears on the right edge of the screen on iPhone 12 Pro (390x844 logical). Not reproducible on iPhone 14+ or Samsung. Added `viewport-fit=cover` to `index.html` viewport meta as a precaution. Root cause unclear — may be a DevTools emulation artifact (iPhone 12 Pro and 14 have the same 390px logical width). Needs real-device testing on production.

**Cloudflare Insights beacon CORS**: Cloudflare injects a beacon script (`static.cloudflareinsights.com`) that intermittently fails with CORS and subresource integrity hash mismatches. Cloudflare-side issue, not fixable by us. Harmless console noise.

**Census data vintage**: ACS 5-year estimates have a ~2-year lag (2023 data = 2019-2023 period). Labeled as estimates in the UI.

**Assessment lag**: CCAO assessments are triennial by township. Recent years may show $0 or stale values. UI shows the most recent non-zero assessment year.

## Fragile Heuristics

These work well enough but could break on edge cases:
- **Sub-header detection inside tables** — length cap (<80 chars) and min-chars threshold (400 chars before splitting)
- **Multi-row header count** — inferred from consecutive row patterns
- **Cross-references** — filtered to section IDs only
- **Keyword boost weight (0.15)** — hand-tuned; too high drowns out semantic similarity, too low has no effect
- **Reranker weight (0.2)** — hand-tuned; higher values (0.3-0.5) regress `minimum_lot_size` and `setback_single_family` queries

## Gotchas

**Legacy `user_id IS NULL` conversations**: Conversations created before auth was added (schema v5) have `user_id = NULL`. Any ownership check must use `WHERE user_id = ? OR user_id IS NULL` — not just `WHERE user_id = ?`. This applies to share creation/revocation, conversation loading, and any future user-scoped operations. In dev mode (no GOOGLE_CLIENT_ID), the auth bypass creates a user with `id: "dev"`, but pre-auth conversations still have NULL.

**Port must be 8001**: Frontend proxy config and API URLs assume backend on 8001. Changing it requires updating `vite.config.ts` proxy + frontend API base URL.

**Tailwind color-name collisions**: Custom tokens (`bg-dark-bg`, `text-accent`) must not collide with Tailwind built-ins. An earlier incident used `bg-dark` which is a valid Tailwind class with a different meaning. Always use the full prefixed name.

**WebGL context loss**: The map can lose its WebGL context if the browser reclaims GPU memory. deck.gl handles this gracefully but the map may need a re-render.

**Municipal Code is gitignored**: `chicago-il-codes.html` (~100MB) is not in version control. Anyone cloning needs to obtain it separately from American Legal Publishing. Qdrant data persists in Docker volume.

**PTAXSIM database is large**: 8.8GB uncompressed. Download script at `scripts/download_ptaxsim.py`. Optional — tax estimation is skipped if the DB doesn't exist.

## Source Coverage Benchmark Results (2026-06-06, run 3)

The `eval/source_coverage.py` benchmark tests 28 data sub-sources across 29 targeted queries (including Tier 3: grant programs, ARO housing, tax incentive classes). **38/41 sub-source checks covered** (93%, up from 85% on run 2). Property tax is NOT_TESTED (PTAXSIM optional, DB not present).

| Category | Sources | Result |
|----------|---------|--------|
| Socrata APIs | crime, 311, permits, violations, business, vacant buildings, food inspections | All COVERED |
| Property domain | PIN, sales | COVERED. Characteristics show RETRIEVAL_GAP (Cook County GIS intermittent). Assessments show intermittent HALLUCINATION (model fabricates when CCAO returns 400). Tax shows intermittent HALLUCINATION (PTAXSIM not present) |
| Regulatory domain | flood, overlays, TOD, historic, brownfields | All COVERED |
| Incentives domain | TIF, OZ, EZ, grant programs, tax class | All COVERED (tax class fixed 2026-06-06) |
| Neighborhood domain | demographics, census tract, transit, Walk Score | All COVERED |
| ARO Housing | affordable housing projects | COVERED (fixed 2026-06-06) |
| Vector search | municipal code chunks | COVERED (fixed 2026-06-06) |

**Failing checks (3/41, all external-data-dependent):**

| Query ID | Sub-source check | Status | Root cause |
|----------|-----------------|--------|------------|
| `property_pin_characteristics` | `property_characteristics` | RETRIEVAL_GAP | Cook County GIS intermittent — Socrata fallback returns PIN but no `bldg_sqft`, `land_sqft`, or `stories`. Context missing, synthesis correctly omits. Not fixable on our side. |
| `property_assessments_sales` | `property_assessments` | HALLUCINATION (intermittent) | CCAO Assessor API returns HTTP 400 for some PINs → `total_assessed_value` and `assessment_history` are null. Model fabricates values despite prompt rule 4. Prompt strengthened (2026-06-06) but still intermittent. Deeper fix: property domain should report assessment failure via `partial_failures`. |
| `property_tax_estimate` | `property_tax` | HALLUCINATION (intermittent) | PTAXSIM database not installed locally (8.8GB, optional). `estimated_annual_tax` is null. Model fabricates a tax number. Same prompt fix applied. Will not recur once PTAXSIM is installed, or if benchmark marks it NOT_TESTED when null. |

**Intermittent (passes on some runs, fails on others):**

| Query ID | Sub-source check | Status | Root cause |
|----------|-----------------|--------|------------|
| `due_diligence_full` | `parcel_zoning` | HALLUCINATION (intermittent) | Zoning lookup for 5600 W Chicago Ave occasionally returns no `zone_class` (geocoding or ArcGIS flaky). Model then fabricates zoning. Passes on retry — appeared in run 2 but not run 3. |

**Cap report**: No capped sources detected across all 29 queries.

Run with: start backend with `RATE_LIMIT_ANON_DAY=200 RATE_LIMIT_ANON_HOUR=200`, then `python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- ~~**Automated code review**~~ — **Done** — `.github/workflows/code-review.yml` uses `anthropics/claude-code-action@v1` to review PRs on open/synchronize. Requires `ANTHROPIC_API_KEY` + Claude Code GitHub App installed on repo.
- **GPU acceleration** — Embedding and reranker models run on CPU. MPS (Apple Silicon) acceleration available but not configured for production server (x86, no GPU).
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset exists.
- **Context management improvements** — Beyond existing TurnSummary + sliding window. Designed but not implemented.
- **Latency reduction** — Prompt caching implemented (2026-06-06). Phase timing instrumentation added. Full plan in `claude-context/latency-reduction.md`.
- ~~**Shareable links**~~ — **Done** — `/s/:token` share routes with `conversation_shares` table (schema v6). ShareModal UI for create/copy/revoke.
- **Property Scorecard** — **Done** (2026-06-07). Non-AI instant-load property dashboard at `/api/scorecard?address=...`. Zero LLM cost. Frontend at `/scorecard`. Includes 3 data upgrades: crime YoY comparison, permit contractor names, address-level 311 complaints with high-risk flagging. **Investigate buttons** (2026-06-08): contextual links below each data card navigate to chat with pre-populated questions via `/?q=...` → `App.tsx` auto-send.
- **PDF Report v3 — Premium Development Feasibility & Site Intelligence** — **Done** (2026-06-08). Upgraded from v2 functional layout to premium pitch-deck quality. v2 base (2026-06-07): 9-section feasibility analysis, Haiku zoning extraction, 3-hop comparable sales, address-specific permits/violations, development potential math, effective tax rate, traffic-light risk indicators, adjacent zoning, nearby construction. v3 additions: **Inter font** (Google Fonts import with system fallback), **traffic-light pill badges** (colored rounded pills replacing text prefixes), **comparable sales scatter chart** (matplotlib, sale date vs price with median reference line, base64-embedded PNG via `_generate_comps_chart()` + `run_in_executor`), **external deep links** (PIN → Cook County Assessor, zone class → Title 17 Municipal Code, violation inspection numbers → Chicago Data Portal, permit numbers → Chicago Data Portal), **professional table styling** (zebra striping, right-aligned numeric columns via `.num` class, summary row borders), **increased whitespace** throughout. Permit query now includes `permit_` ID field from Socrata. **Gated behind Pro tier**. Test with `?mock=true` param for visual QA.
- **Stripe Payment System** — **Done** (2026-06-07). `backend/payments.py` handles Stripe Checkout sessions, webhook events (checkout.session.completed, subscription.updated/deleted), and billing portal. Schema v7 adds `stripe_customer_id` + `stripe_subscription_id` to users table. `require_tier("premium")` dependency gates premium endpoints. Frontend: `/pricing` page (Free vs Pro $99/mo), `UpgradePrompt` modal on gated features, tier badge in `UserMenu`.
- **Site Explorer / Property Finder** — **Done** (2026-06-07). `backend/retrieval/explore.py` queries Cook County Parcel Universe (`pabr-t5kh`) by community area bounding box + property class prefix. `GET /api/explore` (paginated table) + `GET /api/explore/map` (up to 5000 parcels for map). Frontend at `/explore` with split-screen layout: filter panel (CA dropdown + class segmented control + paginated table) + Mapbox/deck.gl map with class-colored dots and legend. Click parcel → Scorecard via lat/lon. Premium-gated via `require_tier("premium")`. Scorecard also updated to support `?lat=...&lon=...` URL params with property-domain address fallback.

## Outstanding Work

- ~~**CI/CD deploy key**~~ — **Done** (2026-06-05).
- ~~**Re-run source coverage benchmark**~~ — **Done** (2026-06-05). 34/40 covered (85%). Remaining gaps are external data availability.
- ~~**Database backup cron on server**~~ — **Done** (2026-06-05). Cron runs daily at 3am UTC, 7 rolling backups at `/opt/urbanlayer/backups/`. DB path: `/var/lib/docker/volumes/urbanlayer_backend_data/_data/chicago.db`.
- ~~**Conversation persistence fix**~~ — **Done** (2026-06-05). 401-interceptor, auth race condition fix, error handling on write functions, CSP fixes, SSE resilience, nginx body size, OOM mitigation. See `claude-context/conversations.md`.
- ~~**Re-enable reranker**~~ — **Done** (2026-06-06). Server upgraded to CX32 (8GB). `RERANKER_ENABLED=true`, retrieval semaphore increased from 4→8.
- **Synthesis latency reduction** — Prompt caching (2026-06-06), retrieval caching + shared HTTP clients (2026-06-06) all implemented. Zoning polygon cache, overlay geometry cache, geocoding cache, and shared HTTP clients across all modules are live. Retrieval phase drops from ~1-3s to ~50-200ms on warm cache. Geometry simplification (2026-06-07) via `shapely.simplify(tolerance=0.0001)` on all GeoJSON FeatureCollections reduces polygon payloads 50-80%. Client-side map caching (2026-06-07) via `cached_community_area` on ChatRequest skips polygon re-fetch for same community area; frontend merges cached zoning/overlay/incentive polygons into new map data. **2 forward-thinking items remain in `claude-context/latency-reduction.md`** — vector tiles, model routing.
- ~~**Shareable conversation links**~~ — **Done** — Share button in workspace header creates a public read-only link (`/s/:token`). ShareModal shows URL with copy/revoke. Schema v6 `conversation_shares` table with CASCADE delete.
- ~~**Investigate buttons on Scorecard**~~ — **Done** (2026-06-08). `InvestigateButton` shared component (`frontend/src/components/InvestigateButton.tsx`). 8 contextual buttons below data cards + 2 in header. `App.tsx` reads `?q=` query param on splash and auto-sends via `sendMessage()`. i18n keys in `pages` namespace (en/es). **Known trade-off**: questions are always English (backend RAG is English-only); in Spanish mode the user's chat bubble shows the English question text.
- **Advanced context management** — Beyond existing TurnSummary + sliding window.
- ~~**ARO housing routing gap**~~ — **Fixed** (2026-06-06). ARO now triggers on any domain (regulatory, property, neighborhood, incentives) when community area is resolved, not just regulatory_domain. Router prompt expanded with explicit affordable housing triggers. Assembler creates RegulatorySummary if needed to hold ARO data. Verified COVERED in benchmark run 3.
- ~~**Vector search gap**~~ — **Fixed** (2026-06-06). Router prompt search guidance strengthened with concrete examples for zoning use queries (e.g., "RT-4 use table allowed uses"). CRITICAL instruction to never include specific use names in zoning search queries. Verified COVERED in benchmark run 3.
- ~~**Tax incentive class hallucination**~~ — **Fixed** (2026-06-06). Assembler now emits "standard" (class exists but not an incentive) or "unavailable" (class missing) signals. Synthesizer prompt updated to handle both. Verified COVERED in benchmark run 3.
- ~~**Property assessment/tax hallucination (intermittent)**~~ — **Fixed** (2026-06-07). Property domain orchestrator now tracks `data_gaps` (list of failed sub-sources: "property characteristics", "property assessments", "property tax estimate"). `data_gaps` is a field on `PropertySummary` and flows through to `partial_failures` in `main.py`. Synthesizer prompt Rule 16 updated to explicitly check `partial_failures` for property-specific gaps and refuse to fabricate values.
- ~~**Mobile UX overhaul**~~ — **Done** (2026-06-06). `MobileSidebarSheet` rewritten with adjustable snap heights (20/70/90vh), 3-tab layout (Map/Data/Sources), MapView GL context preservation, smart default tab, compact mobile map controls with filter popover. Desktop behavior untouched.

## Operational Status

- **Sentry** — Active on production (EU region, `ingest.de.sentry.io`). Backend (FastAPI) and frontend (React) both reporting.
- **UptimeRobot** — Configured for `/health` checks.
- **CI/CD** — Tests + type check + auto-deploy on push to main. Claude Code review on PR open/synchronize.
- **Vacant buildings dataset** — Chicago Data Portal dataset `kc9i-wq85` is sparsely updated (only 8 records in 2025). Query has no date filter — returns all historical cases for the community area.
- **Grant programs datasets** — SBIF (`etqr-sz5x`, 2,152 records) is historical and complete. NOF large (`j7ew-b73u`, 6 records) and small (`rym7-49n8`, 126 records) are small but meaningful.
- **ARO housing dataset** — `s6ha-ppgi` (598 records). Relatively stable, not frequently updated.

## Deployment Status (2026-06-05)

Production server provisioned and hardened (Hetzner CX32 8GB, `178.105.184.66`, Nuremberg — upgraded from CX22 4GB on 2026-06-06). **App is live on HTTPS at `https://urbanlayerchicago.com`** — all 3 Docker services running (Qdrant, backend, frontend) via production compose overlay. Cloudflare Full (Strict) + Origin Certificate. GitHub repo is public (`jpletka01/UrbanLayer-Chicago`). Google OAuth active. Qdrant has 14,535 vectors (municipal code search operational). CI/CD pipeline deployed. UptimeRobot + Sentry monitoring active. Claude Code GitHub App installed for AI code review on PRs. Reranker re-enabled, retrieval concurrency increased to 8. Prompt caching active on all LLM calls.

**Tier 3 integrations deployed to production** (2026-06-05): Grant programs, ARO housing, tax incentive classes merged via PR #1 and deployed.

**Server deploy command** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
