# Known Issues — UrbanLayer

## Open Bugs

**Cook County GIS parcel lookup is intermittently down**: The ArcGIS endpoint (`gis.cookcountyil.gov/.../MapServer/44/query`) has a broken spatial/attribute index — filtered queries (spatial or by PIN) can timeout at 60s+. **Mitigation**: `parcels.py` now falls back to the Cook County Socrata Parcel Universe dataset (`pabr-t5kh`) via bounding-box query on lat/lon columns. The fallback returns a PIN plus enrichment fields (`zip_code`, `township_name`, `nbhd_code`, `tax_code`) to unblock the full property pipeline. Building/land sqft are filled in downstream by CCAO Characteristics. **Still missing on fallback**: parcel polygon geometry (map display only) and address — though for pin-keyed scorecard/report requests the *display* address is now backfilled independently via `pin_to_address()` (Address Points `78yw-iddh` reverse lookup, 2026-06-12; display-only, never used for coordinates). When GIS is up, it's used preferentially. A diagnostic integration test (`test_parcel_gis_diagnostic`) fails loudly when GIS is down. UX note: the Scorecard's parcel-confidence badge copy now explains the degraded state ("Area data — exact parcel not confirmed") instead of a bare warning.

**Reranker (`bge-reranker-v2-m3`) hangs `semantic_search` → DISABLED in prod** (found 2026-06-16): a single reranked `semantic_search` takes **>40–60s** on the prod box (CPX32, 4 vCPU), so the report's `extract_zoning_standards` — which fires **5 reranked searches in parallel** — hangs `_fetch_report_data` past the nginx 180s ceiling → **`/api/report` 504**. Report-only path, so scorecard/chat stayed up; this was the *actual* root cause of the "report never generates" incident (NOT the OOM). **Mitigation: `RERANKER_ENABLED=false` in `docker-compose.prod.yml`** — with it off, `semantic_search` is 0.2–1.4s and reports render in ~10s. **The "torch thread oversubscription" hypothesis was DISPROVEN** (capping `torch.set_num_threads(1)` made it *worse*; re-enable attempt `c3410ba` reverted in `a465014`). The reranker itself is fine — `predict(4 pairs)`=0.3s — so the cost is in the rerank-over-`reranker_candidate_count` path or its `run_in_executor` interaction. **Needs profiling (candidate-count size, per-call overhead, batching) before re-enabling.** While off, chat loses the 20% rerank blend and zoning extraction sees weaker context (more `low`-confidence → more table fallback). Full record: `archive/2026-06-16_report-oom-reranker.md`.

## Known Limitations

**Report parent-process RSS creeps ~20 MB/render (benign)** (measured 2026-06-16): the `/api/report` handler's per-request work that stays in the parent (matplotlib map generation + Jinja HTML assembly; the WeasyPrint render itself is isolated in a child) leaves ~20 MB/render of un-returned RSS. **Neither `MALLOC_ARENA_MAX=2` nor a per-report `malloc_trim(0)` flattened it** — it's evidently live caches (matplotlib/fonts) or fragmentation, not reclaimable free space. Benign: ~2.4 GB parent after 8 renders, 4.5 GB free + 8 GB swap, decelerating, worker restarts each deploy. Both mitigations kept as cheap/harmless. Watch over days; revisit only if RSS fails to plateau.

**Report envelope map depends on parcel geometry**: The V5 development envelope visualization (`_generate_envelope_map()`) requires parcel polygon geometry from Cook County GIS. When GIS is down and the Socrata fallback is used, no geometry is available — the envelope map section silently omits. Edge classification assumes roughly rectangular lots; irregular parcels (5+ distinct edges, L-shapes) fall back to uniform minimum setback.

**Report envelope map skipped for zero-setback zones**: Some commercial zones (C1, B3, etc.) have front_setback_ft=0 and side_setback_ft=0 with only a rear setback. When all three setbacks are 0, the envelope map won't render. When only rear is non-zero, the visualization is technically correct but less visually informative.

**Condo stacks remain pin10-ambiguous**: A street address in a condo building maps to the 10-digit parcel stem, not a specific 14-digit unit PIN. Address Points returns one pin14 for the stack, so an address search for a condo can land on an arbitrary unit. SelectedParcel (2026-06) guarantees the pin the user *sees* is the pin that's queried, purchased, and reported on — it does not disambiguate units. Entering by explicit `?pin=` is the workaround.

**Chat never writes the selected parcel — by design (it may READ it via handoff, 2026-06-12)**: Chat's per-message `pin14` is conversation history, not the current selection; promoting it would create a second identity write path (SelectedParcel truth-model §3: `SelectedParcelContext.select()` is the only write site). Don't "fix" this by syncing chat answers into the selection. **Amendment (2026-06-12)**: the read direction now exists — Scorecard investigate buttons pass `?pin=` → `ChatRequest.parcel_pin` → `_apply_parcel_hint()` overrides the router's text-geocoded location with the authoritative parcel point (only for address-typed plans; any failure keeps the router location; `Location.pin` keys the property domain per INV-2). This is one-directional: selection → chat, never chat → selection.

**Demographics median values are estimated**: The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is interpolated from the bracket containing the 50th percentile. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Census tract-level demographics (via Census Reporter API) provide housing fields: median home value, median gross rent, owner-occupied %, vacancy rate, and bachelor's degree %.

**Violation categories are homegrown**: Chicago's violations dataset has no standard category field — only free-text `violation_description`. `_categorize_violation()` does first-match keyword bucketing into 18 custom categories, supplemented by code-prefix mapping (EV→Elevator, BR→Boiler) using the `violation_code` field.

**FEMA endpoint flakiness**: The FEMA NFHL MapServer occasionally returns 500 errors or empty results. Graceful degradation handles this (flood zone shows as "Unknown" rather than failing the whole request).

**CCAO assessment 400 errors**: Some PINs return HTTP 400 from the Cook County Assessor API. `socrata_get()` now fails fast on 4xx errors (no retries), and negative results are cached for 24 hours to prevent repeat queries. Graceful degradation shows assessments as unavailable. **Impact on Report**: When assessments fail, `estimated_annual_tax` and `total_assessed_value` are null → effective tax rate cannot be derived.

**Report address-specific data gaps**: The permits dataset (`ydr8-5enu`) stores addresses as separate fields (`street_number`, `street_direction`, `street_name`). Some properties have permits filed under variant address formats. When no exact-match permits are found, the section renders "No permits found" rather than showing community-area-level data.

**iPhone 12 Pro black space on right side**: Black strip on right edge on iPhone 12 Pro (390x844). Added `viewport-fit=cover` as precaution. May be DevTools emulation artifact — needs real-device testing.

**Cloudflare Insights beacon CORS**: Cloudflare-injected beacon intermittently fails with CORS and subresource integrity hash mismatches. Harmless console noise, not fixable by us.

**UpgradePrompt / ReportPurchasePrompt copy is hardcoded English**: Both paywall modals (`UpgradePrompt.tsx`, `ReportPurchasePrompt.tsx`) have no i18n keys — Spanish users see English. Pre-existing; surfaced during coherence-audit step 2 (2026-06-12), which fixed the related untranslated `es/pages.json` `scorecard.reportCTA` block but left the modals as-is (north-star says don't expand Spanish by default; fix if/when pricing copy changes again).

**TOD radii don't exist as a map layer**: Coherence audit §6 calls for "transit stations + TOD radii" in the default map; only stations render (`MapView.tsx` transit layer). Radii around CTA stations (the literal zoning-bonus determinant distance) would be new feature work.

**Census data vintage**: ACS 5-year estimates have a ~2-year lag (2023 data = 2019-2023 period). Labeled as estimates in the UI.

**Assessment lag**: CCAO assessments are triennial by township. Recent years may show $0 or stale values. UI shows the most recent non-zero assessment year.

**Discovery index — FULL CITYWIDE COVERAGE LIVE (2026-06-15, all 77 CAs / 949k parcels)**: the build OOM is resolved and full city now fits comfortably. The builder is memory-bounded by construction (per-CA `upsert_parcels` ingest + a streaming `finalize_index` that recomputes value_percentile/populated_fields/recipe_counts over the SQLite index in chunks) and runs **off the live backend** via `docker compose run --rm --no-deps backend …` (own cgroup, shared `backend_data` volume). A coupled bug was fixed too: the old `write_index` **clobbered** the `meta` row to the last batch; `finalize_index` now recomputes meta cumulatively (CAs unioned), so `--community-areas <batch>` correctly *adds*. **Runtime cost measured at ~2.37 KB/parcel** (the backend loads the whole index into RAM at startup): 25 CA=1.86 GB → 37=2.20 → 57=2.49 → **77=2.98 GB RSS (39% of the 8 GB box)**. ⚠️ **The earlier "~1.8M parcels / won't fit" estimate was a unit error — that's Cook County WITH suburbs; Chicago's 77 community areas = ~949k parcels.** No box bump needed; registry reports `coverage: "all"`. Index persists on `backend/data` (`settings.discovery_index_path`); monthly `--refresh` timer (now `run --rm`) auto-follows all 77 CAs. Expand/rebuild + measurement procedure in `deploy/README.md`.

**Discovery `value_percentile` / `undervalued_mf` is structurally thin** (2026-06-14): the metric needs a recent (≤36mo) arm's-length sale, and multifamily trades slowly (~1.2% of multifamily sold in 3 years), so `undervalued_mf` returns only ~30 across 25 CAs. Not a bug — the recipe correctly refuses to invent a $/sqft percentile without a comp. Only lever is the 36-month window (staler comps). `upside_score` is a documented v1 heuristic (0.6/0.4), validated only weakly/confoundedly by the PR-VAL permit cross-check — **don't oversell it in copy**.

## Fragile Heuristics

- **Sub-header detection inside tables** — length cap (<80 chars) and min-chars threshold (400 chars before splitting)
- **Multi-row header count** — inferred from consecutive row patterns
- **Cross-references** — filtered to section IDs only
- **Keyword boost weight (0.20)** — hand-tuned; higher drowns out semantic similarity, lower misses exact-match terms
- **Reranker weight (0.2)** — hand-tuned; higher values (0.3-0.5) regress `minimum_lot_size` and `setback_single_family` queries
- **Section dedup score threshold (0.05)** — keyword-aware dedup only activates when two chunks from the same section are within 0.05 blended score; wider thresholds cause regressions (e.g. m1_setbacks)

## Gotchas

**LLM JSON comes back markdown-fenced** (found 2026-06-16): Haiku wraps its JSON in ```` ```json … ``` ```` fences, so a bare `json.loads(text)` fails at char 0 (`Expecting value: line 1 column 1`). This silently broke `extract_zoning_standards` for ages — every report fell back to the deterministic Title-17 table instead of using AI-extracted zoning. Fixed via `_json_from_model_text()` (strips fences, unwraps a single `{…}` from prose) in `zoning_extract.py` + `test_zoning_extract.py`. **Apply the same strip anywhere you `json.loads` raw LLM output.** (Failure is silent because the parse error is caught and returns `None` → fallback.)

**The PDF report renders in an isolated child process** (2026-06-16): `/api/report`'s WeasyPrint `write_pdf()` runs via `backend/report_render.py` (`render_pdf()` spawns `python -m backend.report_render` with the HTML in a temp file, PDF out). Measured ~118 MB peak per render; the child imports **only** weasyprint (not the FastAPI app or the ~3 GB discovery index), sets `oom_score_adj=1000`, has a generous `RLIMIT_AS` backstop, and is killed by a parent wall-clock timeout (`report_render_timeout_s=150s`) → clean 503, worker survives. Don't move the Jinja render or map generation into the child — they stay in the parent; only `write_pdf` is isolated. The OOM this guards against was real but was **not** triggered by report renders (reports were hanging upstream on the reranker); it's defense-in-depth.

**CCAO latest assessment year is VALUELESS until mailed** (found 2026-06-14 building the Discovery index): the CCAO Assessed Values dataset (`uzyt-m557`) carries an in-progress year (e.g. `2026`) whose value columns (`mailed_tot`/`certified_tot`/`board_tot`/`*_bldg`/`*_land`) are still NULL — and **Socrata omits NULL fields from JSON**, so the row comes back with no value columns at all. Any join that orders `year DESC` and takes the first row resolves every parcel to a valueless row (in the Discovery builder this made `total_assessed_value` 0% populated). **Fix pattern: AND `(mailed_tot IS NOT NULL OR certified_tot IS NOT NULL OR board_tot IS NOT NULL)`** so "latest" means the latest year that actually carries values. ✅ **The scorecard/report assessment path was VERIFIED SAFE (2026-06-14)** — `_build_summary` (`retrieval/property/__init__.py`) iterates `year DESC` and takes the first row with a non-null total (it does NOT grab the raw first row like the index builder did), so the headline value, trend, and tax derivation all skip the valueless in-progress year. Locked with `test_build_summary_skips_valueless_latest_year` + a guard dropping the phantom valueless current-year record from `assessment_history`.

**Permits carry 10-digit parcel PINs, the index has 14-digit unit-PINs**: Chicago building permits (`ydr8-5enu`) `pin_list` holds 10-digit parcel ids; CCAO/Discovery use 14-digit (parcel + 4-digit unit suffix). Match on the shared **10-digit prefix**, never zero-pad the 10-digit to 14 (left-padding gives `00001708320016`, which matches nothing). Same condo-prefix idea as the Discovery address fallback.

**Legacy `user_id IS NULL` conversations**: Conversations created before auth have `user_id = NULL`. Ownership checks must use `WHERE user_id = ? OR user_id IS NULL`. Applies to share creation/revocation, conversation loading, and any user-scoped operations. **Since 2026-06-12 (audit step 3)** all `/api/conversations/*` endpoints `require_auth`, so anonymous HTTP callers can no longer reach the NULL fallback — it exists only so signed-in/dev users keep seeing legacy rows. The one-time prod cleanup (`DELETE FROM conversations WHERE user_id IS NULL`, children first — SQLite FK cascade is off) **was run 2026-06-12**: prod has 0 NULL rows (backup at `/app/backend/data/chicago.backup-2026-06-12-prenullclean.db`). Local dev DBs may still hold NULL rows. NOTE: anonymous chat is intentionally NOT persisted — never "fix" anon chat by re-opening these endpoints. Operational gotcha: the live backend's aiosqlite connection holds a persistent SQLite write lock — ad-hoc writes from a second connection need a fresh backend restart (busy_timeout alone won't get you in).

**`GET /api/uploads/{upload_id}/file` is unauthenticated**: Upload downloads are keyed only by UUID (needed for shared-transcript rendering). Enumeration is impractical, but there's no ownership check. Flagged during audit step 3; tighten if uploads ever carry sensitive content.

**Display PINs are dash-formatted; `_resolve_location` rejects them**: PIN-display helpers (`format_pin` in `retrieval/utils.py`, used by the Discovery index builder) emit `14-28-115-084-0000`, but `_resolve_location` rejects dashed pins with 422. Strip to 14 digits (`pin.replace(/\D/g, "")`) before using as a `?pin=` query key. (Was originally an `/api/explore` gotcha; `/explore` was retired 2026-06-14 but the dash-format-vs-resolver mismatch still applies to any display pin → Scorecard handoff.)

**Port must be 8001**: Frontend proxy config and API URLs assume backend on 8001. Changing it requires updating `vite.config.ts` proxy + frontend API base URL.

**Tailwind color-name collisions**: Custom tokens (`bg-dark-bg`, `text-accent`) must not collide with Tailwind built-ins. Always use the full prefixed name.

**WebGL context loss**: The map can lose its WebGL context if the browser reclaims GPU memory. deck.gl handles this gracefully but the map may need a re-render.

**Municipal Code is gitignored**: `chicago-il-codes.html` (~100MB) is not in version control. Anyone cloning needs to obtain it from American Legal Publishing.

**PTAXSIM database is large**: 8.8GB uncompressed. Download script at `scripts/download_ptaxsim.py`. Optional — tax estimation is skipped if the DB doesn't exist. **Test gotcha**: tests that stub `property_domain` must also patch `estimate_tax`, or the test opens the 8.8GB DB (see `test_property_domain_pin.py`).

**Local dev DB schema_version can run ahead of the actual schema**: Found 2026-06-11 — the local `backend/data/chicago.db` claimed v10/v11 while entirely missing the v9 `report_purchases` and v10 `events` tables (so local analytics ingestion had been silently writing to a missing table). Cause class: `executescript` implicitly commits, so a crashed init can leave the version row committed without the later migrations' tables. `init_db` trusts the version row and won't self-heal; `_migrate_v11` (and any future ALTER-based migration) will crash on such a DB. **Repair**: re-run the relevant idempotent `_migrate_vN` functions manually against the file. Production was verified unaffected.

**Local `chicago-backend-1` docker container crash-loops on `ModuleNotFoundError: jwt`**: The local dev image predates the PyJWT dependency; `docker compose build backend` fixes it. Found 2026-06-12 during step-3 verification (harmless — local dev uses native uvicorn on 8001, not the container).

**Dev mode rate-limits the dev user as anonymous**: `_get_tier()` treats `id == "dev"` as anonymous (3/day by IP). Useful for testing the 429 path (`RATE_LIMIT_ANON_DAY=1`), surprising if local chat suddenly 429s — bump `RATE_LIMIT_ANON_DAY` when doing chat-heavy local work (the eval README already does this).

**Dev-mode Stripe checkout needs two local fixtures**: (1) `_DEV_USER`'s email must be Stripe-valid — `dev@localhost` was rejected by Stripe's `customer_email` validation, 500ing every dev checkout until it was changed to `dev@example.com` (fixed in `auth.py`, 2026-06-11). (2) The synthetic dev user has no `users` row, and `report_purchases.user_id` has a FK on it — insert an `id='dev'` row into the local DB before exercising checkout in dev mode (done on this machine during Phase 2 QA).

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

- **Test baseline (2026-06-12, post-audit-step-3)** — `python -m pytest backend/tests/ -q -m "not integration"` → **599 passed, 56 deselected**; `npx tsc --noEmit` clean. If a fresh checkout shows fewer passing, something regressed — integration tests (56) are excluded because they hit real external APIs and fail on network/GIS flakiness, not code. (2026-06-16 added `test_report_render.py` (11) + `test_zoning_extract.py` (5); local non-integration count ~821 incl. discovery.)
- **Reranker is OFF in prod** (`RERANKER_ENABLED=false`, 2026-06-16) — it hangs `semantic_search` (see Open Bugs). Re-enable only after profiling the rerank path.
- **Host swap = 8 GB** (`/swapfile`, swappiness=10; grown from 2 GB 2026-06-16) — cushions transient render/index spikes on the 8 GB CPX32. `MALLOC_ARENA_MAX=2` set on the backend (does not flatten the report RSS creep; see Known Limitations).
- **`/api/report` has a dedicated nginx 180s timeout** (`location = /api/report`, `frontend/nginx.prod.conf`); the rest of `/api/` stays at the 60s default. Backend render budget `report_render_timeout_s=150s` < 180s so the app 503s before nginx 504s.
- **Deploy verification** — verify against the live API, not just server git HEAD. To exercise auth'd endpoints, mint a short-lived admin token server-side (`docker exec … python -c "from backend.auth import create_access_token; …"`) and `curl -k --resolve urbanlayerchicago.com:443:127.0.0.1 …` to hit origin nginx directly (bypasses Cloudflare; origin cert needs `-k`). Watch a render child's own RSS via `/proc` filtered on `comm=python` + cmdline `backend.report_render` (a naive `grep backend.report_render` matches the sampler itself).
- **Sentry** — Active on production (EU region, `ingest.de.sentry.io`). Backend (FastAPI) and frontend (React) both reporting.
- **UptimeRobot** — Configured for `/health` checks.
- **CI/CD** — Tests + type check + auto-deploy on push to main. Claude Code review on PR open/synchronize.
- **Vacant buildings dataset** — Sparsely updated (only 8 records in 2025). Query returns all historical cases.
- **Grant programs datasets** — SBIF (`etqr-sz5x`, 2,152 records) historical/complete. NOF large (6 records) and small (126 records).
- **ARO housing dataset** — `s6ha-ppgi` (598 records). Relatively stable.
