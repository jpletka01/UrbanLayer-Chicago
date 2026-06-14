# Backend — UrbanLayer

## Core Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app: `/chat` SSE, `/api/scorecard`, `/api/explore` + `/api/explore/map` (premium-gated), `/api/report` (PDF V5 feasibility report with synthesis intelligence, envelope visualization, approval pathway), `/api/report/access`, `/api/checkout` (subscription), `/api/checkout/report` (one-time $25 report purchase), `/api/webhook/stripe`, `/api/subscription`, `/api/billing/portal`, `/api/conversations/*`, `/api/admin/*` (includes `/api/admin/engagement`), `/api/events` (CSRF-exempt, fire-and-forget analytics ingestion), `/api/map-data`, `/api/transit-stations`. Report V5 functions: `_synthesize_opportunities_constraints()`, `_compute_land_value_range()`, `_compute_approval_pathway()`, `_compute_development_trend()`, `_build_incentive_stacking_narrative()`, `_build_envelope_summary()`, `_generate_envelope_map()` (all deterministic, no LLM calls) |
| `router.py` | Claude router → `RetrievalPlan` JSON (sources, location, intent, workflow_hint, search_query) |
| — parcel hint | `ChatRequest.parcel_pin` (Scorecard→chat handoff): `_apply_parcel_hint()` in `main.py` overrides address-typed plans with the authoritative parcel point (`Location.pin` → property domain keyed by PIN, INV-2). Tests: `test_chat_parcel_hint.py` |
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
| `zoning_extract.py` | Haiku-powered structured zoning standard extraction from Municipal Code vectors. 5 parallel semantic searches → Haiku JSON extraction with confidence self-assessment. `calculate_development_potential()` pure math. For per-property interpretive analysis (setbacks, parking, special conditions) |
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
├── explore.py              # Site Explorer: bulk parcel query by community area + class prefix (Cook County Parcel Universe)
├── utils.py                # Shared helpers (cutoff_iso)
├── property/               # Orchestrator: parcels (GIS primary, Socrata fallback) → PIN → [characteristics, assessments, sales, tax] parallel. sales.py also has nearby_comparable_sales() (3-hop: Parcel Universe → Sales → Characteristics)
├── regulatory/             # Orchestrator: [overlays (layers 2-24), flood, environmental] all parallel + aro_housing.py (ARO affordable housing projects by CA, triggered by any domain not just regulatory)
├── incentives/             # Orchestrator: point-based [TIF, EZ, grants] parallel → conditional [financials, OZ]; OR community-area-based TIF + grants. grant_programs.py queries SBIF + NOF
└── neighborhood/           # Orchestrator: [demographics, census_tract, transit, walkscore] parallel
```

## Patterns

- **New Socrata module**: copy `business.py` — same `socrata_get()` pattern with `community_area` filter.
- **New ArcGIS module**: copy `zoning.py` — same spatial query pattern, change endpoint + layer ID.
- **Domain orchestrator**: `asyncio.gather(return_exceptions=True)` → build summary → graceful degradation on failures.
- **External queries**: always use TTLCache, `httpx.AsyncClient`, return `None` on failure. All modules use shared HTTP clients (module-level `_get_X_client()` pattern, same as `socrata.py:get_shared_client()`). Functions accept optional `client` parameter for testing.
- **Tests**: mock external APIs in unit tests, `@pytest.mark.integration` for real-API tests. Cache-clearing autouse fixture in `conftest.py`.

## Property Discovery (`discovery/`)

Deterministic parcel **filter + single-key sort** engine (no scoring). Built 2026-06-13 on
branch `feat/discovery-evaluator-core` (not deployed). Spec + decisions:
`claude-context/property-discovery/` (read `10-implementation-status.md` first).

- **Invariant core:** `registry.py` (+`registry.json`, 29 filters) → `cqs.py` (CQS/Predicate
  models, canonical equality) + `predicates.py` (`satisfies`/`within_scope`) → `evaluator.py`
  (`evaluate(cqs, data_version)` — the ONLY result producer, INV-1, pure leaf).
- **Diagnostics** `diagnostics.py` (advisory; `mostRestrictive` calls evaluate as a black box).
- **Compilers** `compile_text.py` (deterministic rule-based text→fragment, never the LLM) +
  `compile_merge.py` (the only writer of canonical CQS; precedence user>text>default).
- **Data** `parcel_index.py` (`IndexedParcel` + SQLite) + `index_build.py` (offline builder CLI:
  `python -m backend.discovery.index_build --community-areas 24 | --all`) → `discovery_index.db`
  under `ingestion/data/`. `parcel_source.ensure_loaded()` loads it (empty fallback until built).
- **API** `api.py`: `GET /api/discovery/registry`, `POST /api/discovery/search` (mounted in `main.py`,
  `ensure_loaded()` at startup). Wire: `parse → merge → evaluate → build`, echoes canonical CQS.
- **Tests:** `backend/tests/test_discovery_*.py` (131). Mock Socrata + polygon layers.
- **Remaining:** live index build (blocked by 2026-06-13 Socrata 503 outage); deferred index
  fields (OZ/ward/overlay/flood/transit/rollups) ship as a `data_version` bump, no code change.

## Production Configuration

- **Retrieval concurrency**: `_RETRIEVAL_SEM = asyncio.Semaphore(8)` in `main.py` limits concurrent retrieval tasks in `_retrieve()` and `_fetch_map_rows()`. Increased from 4→8 after server upgrade to 8GB RAM (2026-06-06).
- **ML model preloading**: Embedding model (`bge-base-en-v1.5`, ~500MB) is preloaded at startup via `run_in_executor` in the `lifespan` handler. Startup is **blocking** (not `create_task`) so health checks don't pass before models are loaded.
- **Reranker**: Enabled in production via `RERANKER_ENABLED=true` (set in `docker-compose.prod.yml`). Re-enabled after server upgrade to 8GB RAM (2026-06-06). Full vector search pipeline with cross-encoder reranking active.
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
curl -o /tmp/report_mock.pdf "http://localhost:8001/api/report?address=2400+N+Milwaukee+Ave&mock=true" -H "Cookie: session=dev"
```
