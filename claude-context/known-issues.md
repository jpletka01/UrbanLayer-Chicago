# Known Issues — UrbanLayer

## Open Bugs

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+ while unfiltered queries return data fine. The 2026-06-02 benchmark showed 0/7 successful lookups. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN to unblock the full property pipeline (characteristics, assessments, sales, tax) but provides **no parcel polygon geometry** (only centroids) and no address — both are filled in downstream by CCAO Characteristics. When GIS is up, it's used preferentially (includes polygon + address). A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down rather than skipping.

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

**Cap report**: Permits, violations, and business now use grouped aggregation queries that never cap. 311 grouped limit increased 50→200. Crime (35 grouped rows) never caps. Re-run benchmark to verify updated cap rates.

Run with: `python -m eval.source_coverage --full http://localhost:8001`

## Not Yet Built

- **DNS + TLS** — Domain (`urbanlayerchicago.com`) purchased via Namecheap. Cloudflare DNS setup not started — Namecheap nameservers need to be pointed to Cloudflare. Server is live on HTTP at `178.105.184.66` but not reachable by domain name.
- **Qdrant data on server** — Server Qdrant is running but has no data. Municipal code vector search won't return results until local embeddings are snapshot-transferred. All other data sources work.
- **CI/CD** — No GitHub Actions pipeline. Manual deploy via SSH + `git pull && docker compose up -d --build`. Pipeline planned (Phase 8).
- **Monitoring** — No Sentry or uptime monitoring. Planned for Phase 9.
- **GPU acceleration** — Embedding and reranker models run on CPU. MPS (Apple Silicon) acceleration available but not configured for production.
- **Plan Commission PDFs** — Planned development applications are PDF-only; no structured dataset exists.
- **Google Cloud OAuth app** — OAuth client ID needs to be created in Google Cloud Console with `https://urbanlayerchicago.com/api/auth/google/callback` as authorized redirect URI. Until created, auth is disabled on the server (all users treated as admin).

## Deployment Status (2026-06-03)

Production server provisioned and hardened (Hetzner CX22, `178.105.184.66`, Nuremberg). **App is live on HTTP** — all 3 Docker services running (Qdrant, backend, frontend). GitHub repo is public (`jpletka01/UrbanLayer-Chicago`). Auth disabled on server (no Google OAuth client yet — all users admin). Qdrant is empty (vector search won't work until snapshot transfer). DNS/HTTPS not configured yet. Full status tracked in `claude-context/deployment-plan.md`.

**Server deploy command** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose up -d --build
```
