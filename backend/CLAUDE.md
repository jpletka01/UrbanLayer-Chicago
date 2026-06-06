# Backend — UrbanLayer

## Core Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app: `/chat` SSE, `/api/conversations/*`, `/api/admin/*`, `/api/map-data`, `/api/transit-stations` |
| `router.py` | Claude router → `RetrievalPlan` JSON (sources, location, intent, workflow_hint, search_query) |
| `synthesizer.py` | Claude streaming synthesis with `[N]` citation markers + `[data:*]` data markers + analytics |
| `conversation.py` | Multi-turn query expansion (Haiku). Deterministic neighborhood switch detection |
| `context_manager.py` | TurnSummary generation for sliding-window context management |
| `assembler.py` | Context assembly with configurable caps + capped-result detection + partial_failures + tax class interpretation + negative signals for missing data |
| `analytics.py` | Server-side MoM trend computation from raw Socrata rows |
| `auth.py` | Google OAuth2 + JWT sessions. Dev-mode bypass when `GOOGLE_CLIENT_ID` empty. Dependencies: `get_current_user`, `require_admin` |
| `rate_limit.py` | Per-user sliding window rate limiting + daily API budget cap. Applied to `/chat` only |
| `db.py` | SQLite persistence (aiosqlite, WAL, schema v6). Tables: conversations (user-scoped), messages, uploads, llm_calls, request_logs, users, refresh_tokens, conversation_shares |
| `llm.py` | Shared Anthropic client + `tracked_create()`/`tracked_stream()` wrappers (token/cost/latency logging) + automatic prompt caching via `_enable_prompt_caching()` |
| `prompts.py` | System prompts: ROUTER_SYSTEM_TEMPLATE, SYNTHESIZER_SYSTEM, CONVERSATION_SYNTHESIS |
| `models.py` | All Pydantic types: RetrievalPlan, ContextObject, domain summaries, SSE event types |
| `config.py` | Settings via pydantic-settings: API keys, model IDs, query limits, assembler caps |
| `vision.py` | Image/PDF processing for Claude Vision uploads |

## Retrieval Layer

```
retrieval/
├── socrata.py              # Shared async client: socrata_get(), grouped_count(), socrata_aggregate() with retry/backoff
├── cache.py                # TTLCache utility (25 caches across all modules)
├── crime.py                # Crime API (aggregated + block-level, parallel arrest counts)
├── three11.py              # 311 API (open requests + response times, Open-Dup filtered, 200 grouped limit)
├── buildings.py            # Permits (grouped by type + detail sample) + violations (status counts + detail sample)
├── business.py             # Business licenses (grouped by license_description + detail sample for activities)
├── vacant.py               # Vacant buildings (bounding-box filter, grouped by department + detail sample)
├── food_inspections.py     # Food inspections (bounding-box filter, grouped by result/risk + detail sample)
├── map_data.py             # Raw geo-located rows for map (2500/1000/500 row limits)
├── vector_search.py        # Async Qdrant search + keyword boost + bge-reranker + per-section dedup
├── zoning.py               # ArcGIS zoning point lookup + polygon fetch
├── geo.py                  # Census Geocoder + community area resolution (77 areas + 30+ aliases) + census tract FIPS resolution (FCC API)
├── utils.py                # Shared helpers (cutoff_iso)
├── property/               # Orchestrator: parcels (GIS primary, Socrata fallback) → PIN → [characteristics, assessments, sales, tax] parallel
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

## Production Configuration

- **Retrieval concurrency**: `_RETRIEVAL_SEM = asyncio.Semaphore(8)` in `main.py` limits concurrent retrieval tasks in `_retrieve()` and `_fetch_map_rows()`. Increased from 4→8 after server upgrade to 8GB RAM (2026-06-06).
- **ML model preloading**: Embedding model (`bge-base-en-v1.5`, ~500MB) is preloaded at startup via `run_in_executor` in the `lifespan` handler. Startup is **blocking** (not `create_task`) so health checks don't pass before models are loaded.
- **Reranker**: Enabled in production via `RERANKER_ENABLED=true` (set in `docker-compose.prod.yml`). Re-enabled after server upgrade to 8GB RAM (2026-06-06). Full vector search pipeline with cross-encoder reranking active.
- **SSE error handling**: `_event_stream()` wraps fatal calls (`db.count_user_messages()`, `synthesize_query()`) and non-fatal calls (`compute_analytics()`, `_build_map_response()`) in separate try-except blocks to prevent generator crashes before any SSE chunk is yielded.

## Testing

```bash
python -m pytest backend/tests/ -q                           # all tests
python -m pytest backend/tests/ -m integration -v            # real API tests only
python -m pytest backend/tests/test_assembler.py -v          # specific module
python -m pytest backend/tests/ -k "property" -v             # keyword filter
```
