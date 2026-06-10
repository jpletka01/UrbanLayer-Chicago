# Known Issues — UrbanLayer

## Open Bugs

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN plus enrichment fields (`zip_code`, `township_name`, `nbhd_code`, `tax_code`) to unblock the full property pipeline. Building/land sqft are filled in downstream by CCAO Characteristics. **Still missing on fallback**: parcel polygon geometry (map display only) and address. When GIS is up, it's used preferentially. A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down.

## Known Limitations

**Report envelope map depends on parcel geometry**: The V5 development envelope visualization (`_generate_envelope_map()`) requires parcel polygon geometry from Cook County GIS. When GIS is down and the Socrata fallback is used, no geometry is available — the envelope map section silently omits. Edge classification assumes roughly rectangular lots; irregular parcels (5+ distinct edges, L-shapes) fall back to uniform minimum setback.

**Report envelope map skipped for zero-setback zones**: Some commercial zones (C1, B3, etc.) have front_setback_ft=0 and side_setback_ft=0 with only a rear setback. When all three setbacks are 0, the envelope map won't render. When only rear is non-zero, the visualization is technically correct but less visually informative.

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Census tract-level demographics (via Census Reporter API) provide housing fields: median home value, median gross rent, owner-occupied %, vacancy rate, and bachelor's degree %.

**Violation categories are homegrown**: Chicago's violations dataset has no standard category field — only free-text `violation_description`. `_categorize_violation()` does first-match keyword bucketing into 18 custom categories, supplemented by code-prefix mapping (EV→Elevator, BR→Boiler) using the `violation_code` field.

**FEMA endpoint flakiness**: The FEMA NFHL MapServer occasionally returns 500 errors or empty results. Graceful degradation handles this (flood zone shows as "Unknown" rather than failing the whole request).

**CCAO assessment 400 errors**: Some PINs return HTTP 400 from the Cook County Assessor API. `socrata_get()` now fails fast on 4xx errors (no retries), and negative results are cached for 24 hours to prevent repeat queries. Graceful degradation shows assessments as unavailable. **Impact on Report**: When assessments fail, `estimated_annual_tax` and `total_assessed_value` are null → effective tax rate cannot be derived.

**Report address-specific data gaps**: The permits dataset (`ydr8-5enu`) stores addresses as separate fields (`street_number`, `street_direction`, `street_name`). Some properties have permits filed under variant address formats. When no exact-match permits are found, the section renders "No permits found" rather than showing community-area-level data.

**iPhone 12 Pro black space on right side**: Black strip on right edge on iPhone 12 Pro (390x844). Added `viewport-fit=cover` as precaution. May be DevTools emulation artifact — needs real-device testing.

**Cloudflare Insights beacon CORS**: Cloudflare-injected beacon intermittently fails with CORS and subresource integrity hash mismatches. Harmless console noise, not fixable by us.

**Census data vintage**: ACS 5-year estimates have a ~2-year lag (2023 data = 2019-2023 period). Labeled as estimates in the UI.

**Assessment lag**: CCAO assessments are triennial by township. Recent years may show $0 or stale values. UI shows the most recent non-zero assessment year.

## Fragile Heuristics

- **Sub-header detection inside tables** — length cap (<80 chars) and min-chars threshold (400 chars before splitting)
- **Multi-row header count** — inferred from consecutive row patterns
- **Cross-references** — filtered to section IDs only
- **Keyword boost weight (0.20)** — hand-tuned; higher drowns out semantic similarity, lower misses exact-match terms
- **Reranker weight (0.2)** — hand-tuned; higher values (0.3-0.5) regress `minimum_lot_size` and `setback_single_family` queries
- **Section dedup score threshold (0.05)** — keyword-aware dedup only activates when two chunks from the same section are within 0.05 blended score; wider thresholds cause regressions (e.g. m1_setbacks)

## Gotchas

**Legacy `user_id IS NULL` conversations**: Conversations created before auth have `user_id = NULL`. Ownership checks must use `WHERE user_id = ? OR user_id IS NULL`. Applies to share creation/revocation, conversation loading, and any user-scoped operations.

**Port must be 8001**: Frontend proxy config and API URLs assume backend on 8001. Changing it requires updating `vite.config.ts` proxy + frontend API base URL.

**Tailwind color-name collisions**: Custom tokens (`bg-dark-bg`, `text-accent`) must not collide with Tailwind built-ins. Always use the full prefixed name.

**WebGL context loss**: The map can lose its WebGL context if the browser reclaims GPU memory. deck.gl handles this gracefully but the map may need a re-render.

**Municipal Code is gitignored**: `chicago-il-codes.html` (~100MB) is not in version control. Anyone cloning needs to obtain it from American Legal Publishing.

**PTAXSIM database is large**: 8.8GB uncompressed. Download script at `scripts/download_ptaxsim.py`. Optional — tax estimation is skipped if the DB doesn't exist.

## Source Coverage Benchmark (2026-06-06, run 3)

38/41 sub-source checks covered (93%). Property tax is NOT_TESTED (PTAXSIM optional).

**Failing checks (3/41, external-data-dependent):**
- `property_characteristics` — RETRIEVAL_GAP — Cook County GIS intermittent, Socrata fallback lacks `bldg_sqft`/`land_sqft`/`stories`
- `property_assessments` — HALLUCINATION (intermittent) — CCAO API returns 400 for some PINs
- `property_tax` — HALLUCINATION (intermittent) — PTAXSIM not installed locally

Run with: `RATE_LIMIT_ANON_DAY=200 RATE_LIMIT_ANON_HOUR=200`, then `python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- **GPU acceleration** — Embedding and reranker models run on CPU. MPS acceleration available but not configured for production (x86, no GPU).
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset.
- **Advanced context management** — Beyond existing TurnSummary + sliding window. Designed but not implemented.
- **Title 14A re-ingestion** — Parser regex fixed to handle Title 14A (building code) sections, but re-ingestion not yet run. Will add ~500+ building code sections to the index. Requires downloading fresh `chicago-il-codes.html` and running `python -m ingestion.update`.

## Operational Status

- **Sentry** — Active on production (EU region, `ingest.de.sentry.io`). Backend (FastAPI) and frontend (React) both reporting.
- **UptimeRobot** — Configured for `/health` checks.
- **CI/CD** — Tests + type check + auto-deploy on push to main. Claude Code review on PR open/synchronize.
- **Vacant buildings dataset** — Sparsely updated (only 8 records in 2025). Query returns all historical cases.
- **Grant programs datasets** — SBIF (`etqr-sz5x`, 2,152 records) historical/complete. NOF large (6 records) and small (126 records).
- **ARO housing dataset** — `s6ha-ppgi` (598 records). Relatively stable.
