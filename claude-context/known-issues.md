# Known Issues — UrbanLayer

## Open Bugs

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+ while unfiltered queries return data fine. The 2026-06-02 benchmark showed 0/7 successful lookups. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN to unblock the full property pipeline (characteristics, assessments, sales, tax) but provides **no parcel polygon geometry** (only centroids) and no address — both are filled in downstream by CCAO Characteristics. When GIS is up, it's used preferentially (includes polygon + address). A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down rather than skipping.

**Capped-source phrasing inconsistency**: When Socrata API results hit the `$limit` guard (`capped: true`), the synthesis should say "at least N" instead of stating N as an exact count. The 2026-06-02 benchmark found the synthesizer only hedges with "at least" **~60% of the time** — 40% of capped results are presented as exact numbers, which is misleading. Affected sources: 311 (limit 50), permits (limit 500), violations (limit 200), business licenses (limit 500). Crime (limit 35) was the only source that never hit its cap.

**Socrata API limits too low for busy community areas**: Four of five Socrata sources hit their row caps in **100% of benchmark queries**: 311 (50 rows), permits (500), violations (200), business licenses (500). Only crime (35 rows) avoided capping. The 311 limit of 50 is especially low — Englewood alone has far more open requests. These caps mean users see truncated data for every query in every neighborhood.

**Building violations synthesis inconsistency**: The `violations_api` source is fetched and `ViolationSummary` is assembled into the `ContextObject`, but the synthesizer inconsistently mentions it in the response. The data IS present in context and the sidebar `ViolationsCard` renders correctly. Likely fix: add violations to the explicit "must-cover" list in the synthesizer prompt for `site_due_diligence` workflows. Note: the 2026-06-02 benchmark did NOT reproduce this bug (3/3 violations queries were covered), so it may be intermittent or partially fixed.

## Known Limitations

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Median home value, rent, owner-occupied %, bachelor's degree %, and vacancy rate remain null.

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

## Source Coverage Benchmark Results (2026-06-02)

The `eval/source_coverage.py` benchmark tests all 24 data sub-sources across 24 targeted queries. Results from the initial run:

| Category | Sources | Result |
|----------|---------|--------|
| Socrata APIs | crime, 311, permits, violations, business | All COVERED (data in context + mentioned in synthesis) |
| Property domain | PIN, characteristics, assessments, sales, tax | PIN FAILED via GIS (0/7) — now mitigated by Socrata Parcel Universe fallback. Re-run benchmark to verify. |
| Regulatory domain | zoning, overlays, flood, brownfields | All COVERED |
| Incentives domain | TIF, OZ, Enterprise Zone | All COVERED (including negative results) |
| Neighborhood domain | demographics, census tract, transit | All COVERED |
| WalkScore | walk/transit/bike scores | NOT_TESTED (API key not configured) |
| Vector search | municipal code chunks | COVERED |

**Cap report**: 311 capped 100%, permits 100%, violations 100%, business 100%, crime 0%. "at least" hedge used only ~60% of the time.

Run with: `python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- **Deployment** — No Dockerfile for FastAPI backend, no CI/CD, no production config. Vite SPA needs static file server with SPA-fallback.
- **GPU acceleration** — Embedding and reranker models run on CPU. MPS (Apple Silicon) acceleration available but not configured for production.
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset exists.
