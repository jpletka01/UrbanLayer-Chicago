# Backend — UrbanLayer

## Core Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app: `/chat` SSE, `/api/scorecard`, `/api/report` (PDF V5 feasibility report with synthesis intelligence, envelope visualization, approval pathway), `/api/report/access`, `/api/checkout` (subscription), `/api/checkout/report` (one-time $25 report purchase), `/api/webhook/stripe`, `/api/subscription`, `/api/billing/portal`, `/api/conversations/*`, `/api/admin/*` (includes `/api/admin/engagement`), `/api/events` (CSRF-exempt, fire-and-forget analytics ingestion), `/api/map-data`, `/api/transit-stations`. Report V5 functions: `_synthesize_opportunities_constraints()`, `_compute_land_value_range()`, `_compute_approval_pathway()`, `_compute_development_trend()`, `_build_incentive_stacking_narrative()`, `_build_envelope_summary()`, `_generate_envelope_map()` (all deterministic, no LLM calls) |
| `router.py` | Claude router → `RetrievalPlan` JSON (sources, location, intent, workflow_hint, search_query) |
| — parcel hint | `ChatRequest.parcel_pin` (Scorecard→chat handoff): `_apply_parcel_hint()` in `main.py` overrides address-typed plans with the authoritative parcel point (`Location.pin` → property domain keyed by PIN, INV-2). **Pivot guard (2026-06-30):** the sticky pin now rides EVERY turn, so a turn that geocoded >`_PARCEL_HINT_PIVOT_MI` (0.1mi) from the held parcel keeps the router's location (the user pivoted) and the grounding gate then drops the stale context via pin-mismatch. Tests: `test_chat_parcel_hint.py` |
| — scorecard grounding | `ChatRequest.scorecard_context` (`ScorecardContext`, paired with `parcel_pin`): pre-resolved parcel facts from the Scorecard. `_scorecard_grounding_applies()` gates on pin-match + property-scoped; `_retrieve()` then **skips** the property/regulatory/incentives/zoning/aro fetches (bypass) and **post-hoc overwrites** those sub-objects + comparables/zone_definition onto the assembled `ContextObject`. Synthesizer unchanged (it serializes ContextObject). vector_search/neighborhood/activity feeds still run (augment). Selective shape (no crime/311/permits/code_chunks). **2026-06-30 (LIVE):** also grafts `ContextObject.verdict` (distilled Scorecard verdict + caveats) and `ContextObject.address_violations` (`AddressViolations {status: present\|confirmed_zero\|unconfirmed, summary}` — ADDRESS-scoped, distinct from the area-level `violations`; never merged). **2026-07-03 (LIVE):** `ScorecardContext.traffic` (nearest counted street, Scorecard Tier-2) grafts into `ctx.neighborhood.traffic` — creates the `NeighborhoodSummary` shell when the turn skipped the neighborhood orchestrator, never overwrites a fresher fetched row. **Prompt rules** (`prompts.py`): rule 27 = SCOPE DISCIPLINE (THIS-PARCEL vs SURROUNDING-AREA field lists — now explicitly names `property.flags` (CHRS) + `property.energy` as THIS-PARCEL, and defines a NEAREST-STREET scope for `neighborhood.traffic` ("about N vehicles/day on <road>", never the parcel/area); bans "this property has N violations"); rule 28 = verdict (state category/binding_constraint, MUST hedge when caveated); rule 29 = `address_violations` (confirmed_zero ⇒ AFFIRM "none on record at this address"; unconfirmed ⇒ never say zero / never substitute the area count — opposites). Tests: `test_chat_scorecard_grounding.py`. Full design + lessons: `claude-context/archive/2026-06-21_scorecard-chat-grounding.md` + `2026-06-30_verdict-grounding-ux.md` + `2026-07-03_chat-usability.md` |
| `synthesizer.py` | Claude streaming synthesis with `[N]` citation markers + `[data:*]` data markers + analytics. `LANGUAGE_NAMES` dict + `LANGUAGE_INSTRUCTION` for i18n — appends language instruction to system prompt when `language != "en"` |
| `conversation.py` | Multi-turn query expansion (Haiku). Deterministic neighborhood switch detection. Forces synthesis for non-English follow-ups |
| `context_manager.py` | TurnSummary generation for sliding-window context management |
| `assembler.py` | Context assembly with configurable caps + capped-result detection + partial_failures + tax class interpretation + negative signals for missing data |
| `analytics.py` | Server-side MoM trend computation from raw Socrata rows |
| `auth.py` | Google OAuth2 + JWT sessions. Dev-mode bypass when `GOOGLE_CLIENT_ID` empty. Dependencies: `get_current_user`, `require_auth`, `require_admin`, `require_tier(minimum)`. All `/api/conversations/*` endpoints use `require_auth` (anon chat is in-memory only — the `user_id IS NULL` db fallback must never be reachable by anonymous HTTP callers) |
| `payments.py` | Stripe integration: subscription checkout + a la carte report checkout (`mode=payment`; PIN carried in session metadata, purchase row, and `?pin=` success/cancel URLs when known), webhook handler dispatches on session mode (subscription vs one-time) and matches purchases by `stripe_session_id`, billing portal, subscription status |
| `rate_limit.py` | Per-user sliding window rate limiting + daily API budget cap. Applied to `/chat` only |
| `db.py` | SQLite persistence (aiosqlite, WAL, schema v11). Tables: conversations (user-scoped), messages, uploads, llm_calls, request_logs, users (with stripe_customer_id, stripe_subscription_id), refresh_tokens, conversation_shares, report_purchases (a la carte $25 reports, entitlement keyed on parcel PIN when known; legacy pin-less rows matched by lat/lon rounded to 4 decimals), events (usage analytics: page_view, investigate_click, report_cta_click, chat_message_sent, scorecard_bridge_click, hero_address_submit, hero_librarian_click, sample_report_click — only the first 4 charted on admin dashboard) |
| `llm.py` | Shared Anthropic client + `tracked_create()`/`tracked_stream()` wrappers (token/cost/latency logging) + automatic prompt caching via `_enable_prompt_caching()` |
| `prompts.py` | System prompts: ROUTER_SYSTEM_TEMPLATE, SYNTHESIZER_SYSTEM, CONVERSATION_SYNTHESIS |
| `models.py` | All Pydantic types: RetrievalPlan, ContextObject, domain summaries, SSE event types, Report v2 models (ZoningStandards, DevelopmentPotential, ComparableSale, ComparablesSummary, NearbyDevelopment, ReportData with comps_chart_b64, zoning_map_b64, zone_definitions), EventPayload/EventBatch (usage analytics) |
| `zoning_extract.py` | Haiku-powered structured zoning standard extraction from Municipal Code vectors. 5 parallel semantic searches (`ZONING_QUERY_TEMPLATES`, templated on `zone_class`) → Haiku JSON extraction with confidence self-assessment. `_json_from_model_text()` strips ```` ```json ```` fences before parsing (Haiku fences its output; without this every extraction silently fell back to the table — fixed 2026-06-16). `extract_zoning_standards_from_sections()` (deterministic full-section fetch via `BULK_SECTION_BY_PREFIX`, returns standards + provenance) is what the cache builder uses; `extract_zoning_standards[_with_provenance]()` is the legacy semantic-search path (tests only). `calculate_development_potential()` pure math. **The live report path no longer calls any of these** — it reads the precomputed cache (`zoning_cache.py`) |
| `zoning_cache.py` / `zoning_cache_build.py` | **Precomputed zoning extraction** (2026-06-18). Live zoning extraction couldn't run the reranker (504s), and even reranked the partial-chunk searches mostly returned `low`/null (the FAR/height tables are large, so semantic search fetched a ~1,800-char slice of a ~30K-char table, missing the zone's row). Replaced with an **offline deterministic build** (`python -m backend.zoning_cache_build`, dev box): per zone it `get_full_section()`s the **complete** Title-17 "Bulk and density standards" section for the district chapter (`BULK_SECTION_BY_PREFIX`: residential `17-2-0300`, business `17-3-0400`, downtown `17-4-0400`, mfg `17-5-0400`) → Haiku → **hybrid merge**: the deterministic Title-17 table (`standards_from_definitions`) is authoritative for FAR/height/coverage (AI mis-rowed ~7/59 zones, e.g. B3-1 3.0 vs true 1.2), AI keeps the fields the table lacks (setbacks, min-lot, special conditions). Result: 57/59 high-confidence, 0 FAR errors. Committed to `ingestion/data/zoning_cache.json`; report reads via `get_cached_zoning_standards()`; miss/stale (config_version mismatch) → existing R1 table fallback. `config_version` (section map + extraction prompt/model) guards content; `corpus_fingerprint` (Title-17 hashes) flags code changes (`ingestion.update` + `--check`). **No reranker anywhere** — retires the 504 *and* the quality gap. See `archive/2026-06-16_report-oom-reranker.md` |
| `report_i18n.py` | **Deterministic report localization** (2026-06-20, no LLM). `make_translator(lang)`→`t(key,**kw)` + `make_plural(lang)`→`tn(key,count,**kw)` (`__one`/`__other` variants) + `format_report_date`. `MESSAGES` is a flat en/es catalog covering every string in `zoning_report.html` (registered as Jinja globals `t`/`tn`) **and** the deterministic narrative builders in `main.py` (opportunities/constraints, incentive-stacking, approval pathway, decision box, dev-trend, envelope). `/api/report?language=` → `_fetch_report_data(language=)` sets `ReportData.language` before synthesis; English values are byte-identical to the originals so the en report is unchanged. Guard: `test_report_i18n.py` (en/es parity + fallback). |
| `report_render.py` | **Isolated PDF render worker** (2026-06-16). `render_pdf(html)` spawns `python -m backend.report_render` (HTML in temp file → PDF out) so WeasyPrint runs in a short-lived child (~118 MB, fresh address space, imports only weasyprint — not the app/discovery index). Child sets `oom_score_adj=1000` + generous `RLIMIT_AS`; parent enforces `report_render_timeout_s` wall-clock → `PdfRenderError` → clean 503. The `/api/report` handler calls it inside `_REPORT_SEM`. See `archive/2026-06-16_report-oom-reranker.md` |
| `config.py` | Settings via pydantic-settings: API keys, model IDs, query limits, assembler caps |
| `vision.py` | Image/PDF processing for Claude Vision uploads |

## Retrieval Layer

```
retrieval/
├── socrata.py              # Shared async client: socrata_get(), grouped_count(), socrata_aggregate() with retry/backoff
├── cache.py                # TTLCache utility (25 caches across all modules)
├── crime.py                # Crime API (aggregated + block-level, parallel arrest counts)
├── three11.py              # 311 API (open requests + response times, Open-Dup filtered, 200 grouped limit)
├── buildings.py            # Permits (grouped by type + detail sample) + violations (status counts + detail sample) + address-specific permits/violations (permits include permit_ ID for deep linking) + nearby new construction + parse_chicago_address()
├── business.py             # Business licenses (grouped by license_description + detail sample for activities)
├── vacant.py               # Vacant buildings (bounding-box filter, grouped by department + detail sample)
├── food_inspections.py     # Food inspections (bounding-box filter, grouped by result/risk + detail sample)
├── map_data.py             # Raw geo-located rows for map (2500/1000/500 row limits)
├── vector_search.py        # Async Qdrant search + synonym expansion + keyword boost + bge-reranker + keyword-aware per-section dedup
├── zoning.py               # ArcGIS zoning point lookup + polygon fetch + adjacent_parcel_zoning()
├── zoning_definitions.py   # Deterministic zone class lookup table (~50 entries). FAR, height, uses, code sections from Title 17. Used by PDF report for inline descriptions + definitions section AND serialized as `zone_definition` in /api/scorecard (frontend ZoningCard; contract test test_zone_definition_contract.py). Fallback chain: exact → prefix → PD/PMD → unknown
├── geo.py                  # Census Geocoder + community area resolution (77 areas + 30+ aliases) + census tract FIPS resolution (FCC API)
├── utils.py                # Shared helpers (cutoff_iso, format_pin)
├── property/               # Orchestrator: parcels (GIS primary, Socrata fallback) → PIN → [characteristics, assessments, sales, tax, parcel_geometry] parallel + a CONDITIONAL phase-2 (building_facts fallbacks, only when x54s left gaps; skipped for vacant 1xx). sales.py also has nearby_comparable_sales() (3-hop: Parcel Universe → Sales → Characteristics)
│   ├── parcel_geometry.py  # Land area + parcel outline computed ON-DEMAND from ptaxsim pin_geometry_raw (indexed (pin10,start_year) PK, ~ms) — the only all-class land source; cos-lat planar area (no pyproj). Fills land_sqft (source="geometry") + parcel_geometry when GIS absent
│   ├── building_facts.py   # Non-residential building facts: condo unit chars (3r7i-mrz4), Commercial Valuation bldgsf (csik-bsws; SUM latest-year rows — one row PER BUILDING per keypin), Building Footprints stories/year_built (syp8-uezg; col is bldg_statu, bldg_sq_fo mostly 0). Fill-only merge, assessor wins; per-field provenance in PropertySummary.*_source
│   ├── energy.py           # Chicago Energy Benchmarking (xq83-jr8c, ≥50k-sqft buildings): 0–4 rating + ENERGY STAR + owner-reported GFA (fills bldg_sqft, source "energy_benchmark"). Spatial match on `location` (no PIN). Status is "Submitted" OR "Submitted Data". year_built deliberately NOT merged (owner-typed — live probe returned 2000 for the 1894 Old Colony); rides PropertySummary.energy
│   └── chrs.py             # CHRS orange/red (1996, frozen; API asset 403s but /download/ works) from committed artifact ingestion/data/chrs_orange_red.json.gz (build: ingestion.build_chrs_artifact; COLOR_ID 1=orange 2=red, verified vs known red landmarks). Lazy shapely STRtree PIP → ParcelFlags.chrs_rating ("90-day demolition hold"). A committed data artifact needs THREE allowlist lines: .gitignore, .dockerignore, AND a per-file COPY in backend/Dockerfile (all three bit on this artifact)
├── regulatory/             # Orchestrator: [overlays (layers 2-24), flood, environmental] all parallel + aro_housing.py (ARO affordable housing projects by CA, triggered by any domain not just regulatory)
├── incentives/             # Orchestrator: point-based [TIF, EZ, grants] parallel → conditional [financials, OZ]; OR community-area-based TIF + grants. grant_programs.py queries SBIF + NOF
└── neighborhood/           # Orchestrator: [demographics, census_tract, transit, walkscore, traffic] parallel + ward_by_point (wards.py: 50 ward polygons + alderman contacts preloaded at startup; NOTE Socrata URL columns are {"url":...} objects — normalize before pydantic). traffic.py = live daily counts gc7y-n4xa → NeighborhoodSummary.traffic (nearest road, directions summed, 7-day avg); ⚠️ that dataset's point columns are [lat, lon] (swapped) so within_circle matches NOTHING — query numeric bbox on midpointlat/midpointlon
```

## Patterns

- **New Socrata module**: copy `business.py` — same `socrata_get()` pattern with `community_area` filter.
- **New ArcGIS module**: copy `zoning.py` — same spatial query pattern, change endpoint + layer ID.
- **Domain orchestrator**: `asyncio.gather(return_exceptions=True)` → build summary → graceful degradation on failures.
- **External queries**: always use TTLCache, `httpx.AsyncClient`, return `None` on failure. All modules use shared HTTP clients (module-level `_get_X_client()` pattern, same as `socrata.py:get_shared_client()`). Functions accept optional `client` parameter for testing.
- **Tests**: mock external APIs in unit tests, `@pytest.mark.integration` for real-API tests. Cache-clearing autouse fixture in `conftest.py`.

## Property Discovery (`discovery/`)

Deterministic parcel **filter + single-key sort** engine (no scoring) → a goal-first, map-backed
prospecting **workbench**. **LIVE on prod — full citywide (all 77 CAs / ~949k parcels), nav-linked,
premium-gated full experience + free top-10 teaser.** Spec + decisions:
`claude-context/property-discovery/` — **read `10-implementation-status.md` first**, esp. the
"result.rows workbench (PR1–PR10)" section.

- **Invariant core:** `registry.py` (+`registry.json`, **32 filters** + `RangeMeta`/`requires`/
  `label`/`help`/`enumLabels` + 6 `topics` + `Coverage`) → `cqs.py` → `predicates.py` →
  `evaluator.py` (`evaluate(cqs, data_version)` — the ONLY result producer, INV-1, pure leaf;
  unchanged by Wave 2 except it reads the sort-only `total_assessed_value_sortkey` field).
- **Diagnostics** `diagnostics.py` (advisory; `mostRestrictive` calls evaluate as a black box).
- **Compilers** `compile_text.py` (rule-based, never the LLM) + `compile_merge.py` (only writer
  of canonical CQS; precedence user>text>default; `topicId` is telemetry-only, never re-expanded).
- **Data** `parcel_index.py` (`IndexedParcel` + SQLite; `IndexMeta`/`read_meta`;
  `derive_sort_fields` = the 0/exempt sort-only key, real value kept) + `index_build.py` (offline
  builder CLI) → `discovery_index.db` under `backend/data/` (the PERSISTENT volume, via
  `settings.discovery_index_path` — survives redeploys, unlike `ingestion/data/`).
  `parcel_source.ensure_loaded()` loads it + `read_meta`; `current_meta()` feeds
  coverage/populatedFields; empty fallback until built.
- **API** `api.py` — **one shared `_resolve(req)`** (parse→merge→evaluate) behind every endpoint:
  - `GET /api/discovery/registry` — static artifact + **coverage + populatedFields injected from
    index `meta`** (safe default: no meta → coverage "none", empty populatedFields).
  - `POST /api/discovery/search` — `{rows,total,nextOffset,gated}`. Rows hydrated from the snapshot;
    `limit/offset` paging. **Free tier (Depends(get_current_user), `FREE_ROW_CAP=10`) is
    server-capped** to the top 10 + `gated=true` + true total + `nextOffset=null`.
  - `POST /api/discovery/search/pins` — FULL ordered coord set (pin+lat/lon+upside+landUse),
    capped `MAX_MAP_POINTS=5000` + `truncated`. NOT tier-capped (free sees all dots; FE colors
    by land-use + view-only).
  - `POST /api/discovery/search/export` — streams ALL `result.total` rows as CSV,
    **`require_tier("premium")`** (free 403), human headers from registry labels.
  - `meta.recipe_counts` (built per-recipe) → `registry.recipeCounts` → shelf "Live · N" / "No
    matches yet" badges. `parcel_source.pin_lookup` is **memoized per dataVersion** (was O(N)/req).
- **Builder** `index_build.py` computes the derived fields (`is_teardown_candidate`, `upside_score`
  = 0.6·FAR-headroom + 0.4·land-share, `cta_rail_distance_mi`, cross-parcel `value_percentile`),
  3-tier addresses (`_address_for`: own → building base-PIN → nearest-approx `~` via shapely STRtree),
  `populated_fields` + `recipe_counts` manifest. **`--refresh`** rebuilds the current `meta.community_areas`
  (monthly timer). **Assessment join filters for a present value** (latest CCAO year is valueless — see
  known-issues). `index_validate.py` = non-blocking validation CLI.
  **Memory-bounded by construction (2026-06-14):** per-CA `_assemble_ca`→`upsert_parcels` ingest
  (peak = one CA) then a streaming `finalize_index` that recomputes the cross-parcel fields + meta
  over the SQLite index in chunks (value_percentile float-maps, chunked `evaluate()` recipe counts,
  stream-union populated_fields). `write_index` is now a thin `upsert_parcels`+`write_meta` wrapper.
  Meta is recomputed **cumulatively** (CAs unioned), so `--community-areas <batch>` correctly *adds*
  instead of clobbering coverage to the last batch. Run **off-box** via `docker compose run --rm`.
- **Tests:** `backend/tests/test_discovery_*.py` (**193**). Mock Socrata + polygon layers;
  premium/free gating via FastAPI `dependency_overrides` (the `Depends` callable is captured at
  decoration, so monkeypatching the module attr does NOT work — override the dependency).
- **LIVE ON PROD — FULL CITYWIDE (2026-06-15) — coverage `all`, ALL 77 CAs / ~949k parcels**,
  nav-linked. Reached via measured off-box batches (25→37→57→77); runtime **2.98 GB RSS (39% of the
  8 GB box)** at ~2.37 KB/parcel — the "~1.8M won't fit" worry was a unit error (that's Cook County +
  suburbs; Chicago = ~949k). Index persists on `backend/data` volume; monthly `--refresh` timer
  (`deploy/`, `run --rm`, off-box) auto-follows all 77. **Remaining:** deferred index fields (each a
  `data_version` bump, no evaluator change — OZ/ward/overlay/adu/aro/flood/brownfield/rollups + a real
  `units` source). `/explore` **retired 2026-06-14** (Discovery is a strict superset; redirects to
  `/discovery`). Full record: `claude-context/property-discovery/10-implementation-status.md`.

## Production Configuration

- **Retrieval concurrency**: `_RETRIEVAL_SEM = asyncio.Semaphore(8)` in `main.py` limits concurrent retrieval tasks in `_retrieve()` and `_fetch_map_rows()`. Increased from 4→8 after server upgrade to 8GB RAM (2026-06-06).
- **ML model preloading**: Embedding model (`bge-base-en-v1.5`, ~500MB) is preloaded at startup via `run_in_executor` in the `lifespan` handler. Startup is **blocking** (not `create_task`) so health checks don't pass before models are loaded.
- **Reranker**: **DISABLED in production** (`RERANKER_ENABLED=false` in `docker-compose.prod.yml`, since 2026-06-16) — it hung `/api/report` → 504. Root cause (profiled 2026-06-18): unbounded rerank concurrency (the report fires 5 parallel `semantic_search` → 5 torch `predict()` thrashing the 4-vCPU box) compounded by a 3× oversized batch (60 pairs reranked to return 3). The concurrency/batch fix (top-20 batch, single-worker `_get_rerank_executor()` in `vector_search.py`, configurable `reranker_torch_threads`; commit `e59990b`) landed and is core-independent (native 5-way 35.7s→12.4s) **but was VERIFIED-TOO-SLOW on the real prod box 2026-06-18** — a single 20-pair `predict()` is still ~40s on these vCPUs, so the report path stayed ≫180s. **Resolved instead by removing the reranker from the report path entirely** via the precomputed zoning cache (`zoning_cache.py`, deployed & verified live 2026-06-18, `main` @ `69d8481`). The flag stays `false`; re-enabling for chat would need a faster/ONNX-quantized cross-encoder. Full record: `claude-context/archive/2026-06-16_report-oom-reranker.md`.
- **SSE error handling**: `_event_stream()` wraps fatal calls (`db.count_user_messages()`, `synthesize_query()`) and non-fatal calls (`compute_analytics()`, `_build_map_response()`) in separate try-except blocks to prevent generator crashes before any SSE chunk is yielded.

## Ingestion Pipeline

```
ingestion/
├── parse_chicago_code.py   # HTML → section JSON files (8615+ sections). Handles Title 14A (alphanumeric IDs)
├── chunk.py                # Section JSON → chunks.jsonl (MAX_CHARS=1800, table flattening, no overlap)
├── embed_and_store.py      # chunks.jsonl → Qdrant (bge-base-en-v1.5, two collections). Supports --recreate and --incremental
├── manifest.py             # Section content hash tracking for incremental updates (SHA-256 of body + tables)
├── update.py               # Unified CLI: parse → chunk → diff → embed. Supports --dry-run, --full, --manifest
├── source_check.py         # Detect whether source HTML changed since last ingestion
├── build_transit_stations.py
└── load_community_areas.py
```

```bash
python -m ingestion.update                # incremental update (diff against manifest)
python -m ingestion.update --dry-run      # show changes without modifying Qdrant
python -m ingestion.update --full         # full rebuild
python -m ingestion.update --manifest     # just save manifest from current sections
python -m ingestion.source_check          # check if source HTML changed
```

## Testing

```bash
python -m pytest backend/tests/ -q                           # all tests
python -m pytest backend/tests/ -m integration -v            # real API tests only
python -m pytest backend/tests/test_assembler.py -v          # specific module
python -m pytest backend/tests/ -k "property" -v             # keyword filter

# PDF Report v2 visual QA (mock=true forces all sections populated)
curl -o /tmp/report_mock.pdf "http://localhost:8001/api/report?address=1601+N+Milwaukee+Ave&mock=true" -H "Cookie: session=dev"
```
