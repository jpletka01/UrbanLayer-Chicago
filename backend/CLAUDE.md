# Backend — UrbanLayer

## Core Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app: `/chat` SSE, `/api/conversations/*`, `/api/admin/*`, `/api/map-data`, `/api/transit-stations` |
| `router.py` | Claude router → `RetrievalPlan` JSON (sources, location, intent, workflow_hint, search_query) |
| `synthesizer.py` | Claude streaming synthesis with `[N]` citation markers + `[data:*]` data markers + analytics |
| `conversation.py` | Multi-turn query expansion (Haiku). Deterministic neighborhood switch detection |
| `context_manager.py` | TurnSummary generation for sliding-window context management |
| `assembler.py` | Context assembly with configurable caps + capped-result detection + partial_failures |
| `analytics.py` | Server-side MoM trend computation from raw Socrata rows |
| `db.py` | SQLite persistence (aiosqlite, WAL, schema v3). Tables: conversations, messages, uploads, llm_calls, request_logs |
| `llm.py` | Shared Anthropic client + `tracked_create()`/`tracked_stream()` wrappers (token/cost/latency logging) |
| `prompts.py` | System prompts: ROUTER_SYSTEM_TEMPLATE, SYNTHESIZER_SYSTEM, CONVERSATION_SYNTHESIS |
| `models.py` | All Pydantic types: RetrievalPlan, ContextObject, domain summaries, SSE event types |
| `config.py` | Settings via pydantic-settings: API keys, model IDs, query limits, assembler caps |
| `vision.py` | Image/PDF processing for Claude Vision uploads |

## Retrieval Layer

```
retrieval/
├── socrata.py              # Shared async client: socrata_get() with retry/backoff, X-App-Token
├── cache.py                # TTLCache utility (17 caches across all modules)
├── crime.py                # Crime API (aggregated + block-level, parallel arrest counts)
├── three11.py              # 311 API (open requests + response times, Open-Dup filtered)
├── buildings.py            # Permits (reported_cost) + violations (open-first ordering, 200 limit)
├── business.py             # Business licenses (active-only via license_status='AAI', 500 limit)
├── map_data.py             # Raw geo-located rows for map (2500/1000/500 row limits)
├── vector_search.py        # Async Qdrant search + keyword boost + bge-reranker + per-section dedup
├── zoning.py               # ArcGIS zoning point lookup + polygon fetch
├── geo.py                  # Census Geocoder + community area resolution (77 areas + 30+ aliases)
├── utils.py                # Shared helpers (cutoff_iso)
├── property/               # Orchestrator: parcels → PIN → [characteristics, assessments, sales, tax] parallel
├── regulatory/             # Orchestrator: [overlays (layers 2-24), flood, environmental] all parallel
├── incentives/             # Orchestrator: [TIF, enterprise_zones] parallel → conditional [financials, OZ]
└── neighborhood/           # Orchestrator: [demographics, transit, walkscore] parallel
```

## Patterns

- **New Socrata module**: copy `business.py` — same `socrata_get()` pattern with `community_area` filter.
- **New ArcGIS module**: copy `zoning.py` — same spatial query pattern, change endpoint + layer ID.
- **Domain orchestrator**: `asyncio.gather(return_exceptions=True)` → build summary → graceful degradation on failures.
- **External queries**: always use TTLCache, `httpx.AsyncClient`, return `None` on failure.
- **Tests**: mock external APIs in unit tests, `@pytest.mark.integration` for real-API tests. Cache-clearing autouse fixture in `conftest.py`.

## Testing

```bash
python -m pytest backend/tests/ -q                           # all tests
python -m pytest backend/tests/ -m integration -v            # real API tests only
python -m pytest backend/tests/test_assembler.py -v          # specific module
python -m pytest backend/tests/ -k "property" -v             # keyword filter
```
