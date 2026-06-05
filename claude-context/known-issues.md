# Known Issues — UrbanLayer

## Open Bugs

~~**Conversation history click-to-load is broken**~~: **Fixed** — Schema v5 migration adds `user_id` to `conversations` table. All conversation CRUD endpoints now use `Depends(get_current_user)` for per-user scoping. Legacy conversations (null user_id) are visible to all users. Frontend `getConversation`/`listConversations` now log errors on failure, and `loadConv` shows an error banner when a conversation can't be loaded.

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+ while unfiltered queries return data fine. The 2026-06-02 benchmark showed 0/7 successful lookups. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN to unblock the full property pipeline (characteristics, assessments, sales, tax) but provides **no parcel polygon geometry** (only centroids) and no address — both are filled in downstream by CCAO Characteristics. When GIS is up, it's used preferentially (includes polygon + address). A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down rather than skipping.

## Known Limitations

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Census tract-level demographics (via Census Reporter API) now provide all housing fields: median home value (B25077), median gross rent (B25064), owner-occupied % (B25003), vacancy rate (B25002), and bachelor's degree % (B15003).

**Violation categories are homegrown**: Chicago's violations dataset has no standard category field — only free-text `violation_description`. Our `_categorize_violation()` does first-match keyword bucketing into 18 custom categories, supplemented by code-prefix mapping (EV→Elevator, BR→Boiler) using the `violation_code` field. The code prefixes are heterogeneous alphanumeric strings, so full code-to-category mapping isn't practical — keyword matching remains the primary strategy.

**FEMA endpoint flakiness**: The FEMA NFHL MapServer occasionally returns 500 errors or empty results. Graceful degradation handles this (flood zone shows as "Unknown" rather than failing the whole request).

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

**Port must be 8001**: Frontend proxy config and API URLs assume backend on 8001. Changing it requires updating `vite.config.ts` proxy + frontend API base URL.

**Tailwind color-name collisions**: Custom tokens (`bg-dark-bg`, `text-accent`) must not collide with Tailwind built-ins. An earlier incident used `bg-dark` which is a valid Tailwind class with a different meaning. Always use the full prefixed name.

**WebGL context loss**: The map can lose its WebGL context if the browser reclaims GPU memory. deck.gl handles this gracefully but the map may need a re-render.

**Municipal Code is gitignored**: `chicago-il-codes.html` (~100MB) is not in version control. Anyone cloning needs to obtain it separately from American Legal Publishing. Qdrant data persists in Docker volume.

**PTAXSIM database is large**: 8.8GB uncompressed. Download script at `scripts/download_ptaxsim.py`. Optional — tax estimation is skipped if the DB doesn't exist.

## Source Coverage Benchmark Results (2026-06-05, run 2)

The `eval/source_coverage.py` benchmark tests 29 data sub-sources across 29 targeted queries (including Tier 3: grant programs, ARO housing, tax incentive classes). **34/40 sub-source checks covered** (85%). Property tax is NOT_TESTED (PTAXSIM optional, DB not present).

| Category | Sources | Result |
|----------|---------|--------|
| Socrata APIs | crime, 311, permits, violations, business, vacant buildings, food inspections | All COVERED |
| Property domain | PIN, sales | COVERED. Characteristics/assessments show RETRIEVAL_GAP (Cook County GIS intermittent — data not available). Tax NOT_TESTED (PTAXSIM optional) |
| Regulatory domain | flood, overlays, TOD, historic, brownfields | All COVERED |
| Incentives domain | TIF, OZ, grant programs | All COVERED. Enterprise Zone shows SYNTHESIS_GAP (model omits negative EZ when TIF/OZ positive — marked optional). Tax class shows HALLUCINATION (requires property class from Cook County — not retrieved when GIS is down) |
| Neighborhood domain | demographics, census tract, transit, Walk Score | All COVERED |
| ARO Housing | affordable housing projects | HALLUCINATION — ARO data not in context but model mentions it. Likely routing issue: ARO query may not be dispatched for this query type |
| Vector search | municipal code chunks | RETRIEVAL_GAP — RT-4 daycare query did not return code chunks |

**Remaining real issues:**
- **ARO housing HALLUCINATION** — Model fabricates ARO data when the retrieval doesn't include it. Root cause: ARO runs only when `regulatory_domain` is active, but the ARO-specific query may not trigger regulatory routing.
- **Tax incentive class HALLUCINATION** — Requires property class code from Cook County parcel data; when GIS is down, no class code is available for the assembler to interpret.
- **Vector search gap** — Qdrant returned no chunks for the RT-4 daycare query. May be a query formulation issue or Qdrant index state.
- **Property characteristics/assessments** — Cook County GIS intermittent (known, fallback provides PIN but not building details).

**Cap report**: No capped sources detected across all 29 queries.

Run with: start backend with `RATE_LIMIT_ANON_DAY=200 RATE_LIMIT_ANON_HOUR=200`, then `python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- ~~**Automated code review**~~ — **Done** — `.github/workflows/code-review.yml` uses `anthropics/claude-code-action@v1` to review PRs on open/synchronize. Requires `ANTHROPIC_API_KEY` + Claude Code GitHub App installed on repo.
- **GPU acceleration** — Embedding and reranker models run on CPU. MPS (Apple Silicon) acceleration available but not configured for production server (x86, no GPU).
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset exists.
- **Context management improvements** — Beyond existing TurnSummary + sliding window. Designed but not implemented.
- **Latency reduction** — Synthesis currently takes 3-8s. Optimization opportunities identified but not implemented.
- **Shareable links** — PDF export exists (`ExportReport.tsx`). Link sharing not yet built.

## Outstanding Work

- ~~**CI/CD deploy key**~~ — **Done** (2026-06-05).
- ~~**Re-run source coverage benchmark**~~ — **Done** (2026-06-05). 34/40 covered (85%). Remaining gaps are external data availability.
- ~~**Database backup cron on server**~~ — **Done** (2026-06-05). Cron runs daily at 3am UTC, 7 rolling backups at `/opt/urbanlayer/backups/`. DB path: `/var/lib/docker/volumes/urbanlayer_backend_data/_data/chicago.db`.
- **Synthesis latency reduction** — 3-8s first-hit synthesis. Optimization opportunities: model routing for simple queries, prompt trimming, partial streaming.
- **Mobile experience** — Sidebar/map hidden on mobile (`hidden md:flex`). Needs bottom sheet or swipe-to-reveal for map access.
- **Shareable conversation links** — PDF export exists, but no way to share a conversation via URL.
- **Advanced context management** — Beyond existing TurnSummary + sliding window.
- **ARO housing routing gap** — Benchmark shows HALLUCINATION; ARO query not dispatched for ARO-specific questions that don't trigger `regulatory_domain` routing.
- **Vector search gap** — RT-4 daycare query returned no code chunks. Investigate query formulation or Qdrant index state.

## Operational Status

- **Sentry** — Active on production (EU region, `ingest.de.sentry.io`). Backend (FastAPI) and frontend (React) both reporting.
- **UptimeRobot** — Configured for `/health` checks.
- **CI/CD** — Tests + type check + auto-deploy on push to main. Claude Code review on PR open/synchronize.
- **Vacant buildings dataset** — Chicago Data Portal dataset `kc9i-wq85` is sparsely updated (only 8 records in 2025). Query has no date filter — returns all historical cases for the community area.
- **Grant programs datasets** — SBIF (`etqr-sz5x`, 2,152 records) is historical and complete. NOF large (`j7ew-b73u`, 6 records) and small (`rym7-49n8`, 126 records) are small but meaningful.
- **ARO housing dataset** — `s6ha-ppgi` (598 records). Relatively stable, not frequently updated.

## Deployment Status (2026-06-05)

Production server provisioned and hardened (Hetzner CX22, `178.105.184.66`, Nuremberg). **App is live on HTTPS at `https://urbanlayerchicago.com`** — all 3 Docker services running (Qdrant, backend, frontend) via production compose overlay. Cloudflare Full (Strict) + Origin Certificate. GitHub repo is public (`jpletka01/UrbanLayer-Chicago`). Google OAuth active. Qdrant has 14,535 vectors (municipal code search operational). CI/CD pipeline deployed (tests + type check pass, auto-deploy key pending verification). UptimeRobot + Sentry monitoring active. Claude Code GitHub App installed for AI code review on PRs. Full status tracked in `claude-context/deployment-plan.md`.

**Tier 3 integrations deployed to production** (2026-06-05): Grant programs, ARO housing, tax incentive classes merged via PR #1 and deployed.

**Server deploy command** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
