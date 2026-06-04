# Known Issues — UrbanLayer

## Open Bugs

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+ while unfiltered queries return data fine. The 2026-06-02 benchmark showed 0/7 successful lookups. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN to unblock the full property pipeline (characteristics, assessments, sales, tax) but provides **no parcel polygon geometry** (only centroids) and no address — both are filled in downstream by CCAO Characteristics. When GIS is up, it's used preferentially (includes polygon + address). A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down rather than skipping.

## Known Limitations

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Census tract-level demographics (via Census Reporter API) now provide all housing fields: median home value (B25077), median gross rent (B25064), owner-occupied % (B25003), vacancy rate (B25002), and bachelor's degree % (B15003).

**Violation categories are homegrown**: Chicago's violations dataset has no standard category field — only free-text `violation_description`. Our `_categorize_violation()` does first-match keyword bucketing into 16 custom categories. The dataset also has a `violation_code` numeric field we're not using, which might give more reliable groupings.

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

## Source Coverage Benchmark Results (2026-06-04)

The `eval/source_coverage.py` benchmark tests 26 data sub-sources across 26 targeted queries. **27/37 sub-source checks covered** (73%).

| Category | Sources | Result |
|----------|---------|--------|
| Socrata APIs | crime, 311, permits, violations, business, vacant buildings, food inspections | All COVERED |
| Property domain | PIN, sales | COVERED. Characteristics/assessments show HALLUCINATION (synthesis mentions data not in context) |
| Regulatory domain | flood | COVERED. Overlays, TOD, historic, brownfields: RETRIEVAL_GAP on specific test addresses |
| Incentives domain | TIF, OZ, Enterprise Zone | All COVERED |
| Neighborhood domain | demographics, census tract, transit | COVERED (transit has 1 gap on specific address) |
| WalkScore | walk/transit/bike scores | SYNTHESIS_GAP (data retrieved but synthesis doesn't mention "score" format) |
| Vector search | municipal code chunks | RETRIEVAL_GAP (Qdrant returned empty for test query) |

**Cap report**: No capped sources detected across all 26 queries. Grouped aggregation queries never cap.

Run with: `RATE_LIMIT_ANON_DAY=200 RATE_LIMIT_ANON_HOUR=200 python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- **Sentry** — Active on production (EU region, `ingest.de.sentry.io`). Backend (FastAPI) and frontend (React) both reporting.
- **CI/CD deploy secrets** — Pipeline runs tests on PRs but deploy job needs `SERVER_SSH_KEY` + `SERVER_HOST` GitHub repo secrets.
- **GPU acceleration** — Embedding and reranker models run on CPU. MPS (Apple Silicon) acceleration available but not configured for production server (x86, no GPU).
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset exists.

## Deployment Status (2026-06-03)

Production server provisioned and hardened (Hetzner CX22, `178.105.184.66`, Nuremberg). **App is live on HTTPS at `https://urbanlayerchicago.com`** — all 3 Docker services running (Qdrant, backend, frontend) via production compose overlay. Cloudflare Full (Strict) + Origin Certificate. GitHub repo is public (`jpletka01/UrbanLayer-Chicago`). Google OAuth active. Qdrant has 14,535 vectors (municipal code search operational). CI/CD pipeline deployed. UptimeRobot monitoring active. Full status tracked in `claude-context/deployment-plan.md`.

**Server deploy command** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
