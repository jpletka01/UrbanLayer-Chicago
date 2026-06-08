# Backend Guide — UrbanLayer

## Router (`router.py`)

Produces a `RetrievalPlan` JSON with: `sources` (list of SourceTags), `location` (raw + resolved lat/lon/community_area), `intent`, `time_range_days`, `requires_disclaimer`, `search_query`, `workflow_hint`, `clarification`.

Router system prompt embeds all 77 community area names + 30+ neighborhood aliases. Includes search query guidance for zoning-specific terminology (e.g., "search home occupation rules, not bakery") and non-zoning topics.

If no location and query requires one: `intent = "clarification_needed"`, emits clarification text.

**Source tags**: `crime_api`, `311_api`, `permits_api`, `violations_api`, `business_api`, `vector_search`, `property_domain`, `regulatory_domain`, `incentives_domain`, `neighborhood_domain`.

**Incentives routing**: `incentives_domain` works at two levels — address queries (lat/lon → point-in-polygon TIF check + EZ + OZ) and neighborhood queries (community area → list all TIF districts via `comm_area` field matching).

## Context Assembly (`assembler.py`)

Merges raw API results into a `ContextObject` with configurable caps (from `config.py`): `top_crime_types`, `top_311_types`, `top_chunks`, etc.

Key behaviors:
- `Open - Dup` dedup on 311 data before aggregating.
- Auto data-lag note for crime (7-day lag).
- Permits, violations, and business use grouped aggregation data (never capped). Crime and 311 use grouped counts with capped detection as a safety net.
- `partial_failures` field tracks which domain orchestrators returned errors (graceful degradation).

## Synthesis (`synthesizer.py`)

Streaming Claude call with structured system prompt rules (26 rules total):
- `[N]` citation markers render as `§ section` pills in frontend.
- `[data:crime]`, `[data:311]`, etc. render as colored data pills.
- Surface data freshness (7-day crime lag).
- Pre-scan instruction + rule 4a: check each summary's `capped` field, say "at least N" when capped.
- Legal disclaimer when `requires_disclaimer: true`.
- Weave MoM trends naturally (analytics formatted as text, not JSON).
- State zoning classification as definitive fact. Link to official Zoning Map Web.
- Explicit "When X data is present" rules for all data sources.
- Use `.total` fields for authoritative counts, not trend data sums.

**i18n**: When `language != "en"`, `LANGUAGE_INSTRUCTION` is appended to the system prompt, directing synthesis in the target language while preserving citation markers, data markers, proper nouns, and official program names.

## Conversation (`conversation.py`)

Multi-turn context synthesis using Haiku. Improves follow-up detection for context references ("their", "it", "what about"), clarification answers.

**Deterministic neighborhood switching**: regex-based pre-check for "what about X?" / "compare to Y" patterns. If detected, substitutes the new neighborhood into the original question structure without LLM synthesis. Falls back to Haiku for ambiguous cases.

**Non-English**: Forced synthesis for all non-English follow-ups (English heuristics don't match other languages).

## Rate Limiting (`rate_limit.py`)

In-memory sliding window counters keyed by user_id (or IP for anonymous). Applied to `/chat` endpoint only.

**Tier limits**: anonymous 3/day + 3/hour, free 25/day + 10/hour, premium 100/day + 30/hour, admin unlimited.

**Daily budget cap**: sums today's `llm_calls` via `estimate_cost()`, rejects if over `DAILY_API_BUDGET_USD` env var (default $5).

## Persistence (`db.py`)

SQLite via aiosqlite, WAL mode, singleton connection, schema versioning.

**Conversation API** (7 CRUD endpoints): list, create, get (full with messages), delete (CASCADE), append messages, update map data, bulk import.

**Admin API** (8 endpoints, all protected by `require_admin`): cache stats, overview, timeseries, latency, conversations, paginated request log, benchmark results, judge results.

**LLM tracking**: `tracked_create()` / `tracked_stream()` wrappers capture token usage. Each chat turn gets a UUID `request_group` linking its 1-3 LLM calls. Cost estimation uses per-model pricing. Logging is non-fatal.

## Caching (`retrieval/cache.py`)

`TTLCache` utility used by all external query modules. 25 caches across the codebase.

Cache key patterns:
- Spatial: `f"{source}:{round(lat,5)}:{round(lon,5)}"`
- PIN-based: `f"{source}:{pin14}"`
- Tract-based: `f"{source}:{tract_fips}"`

Startup preloading: TIF boundaries, Enterprise Zone boundaries, OZ tract list, GTFS stations, ACS demographics, community area polygons, ML embedding model (blocking).

Cache hit/miss stats available via `/api/admin/cache-stats`.

**Prompt caching**: All LLM calls use Anthropic server-side prompt caching via `_enable_prompt_caching()` in `llm.py`. Static system prompts auto-converted to content blocks with `cache_control: {"type": "ephemeral"}` (5-minute TTL).

## HTTP Client Patterns

Every retrieval module uses a process-lifetime `httpx.AsyncClient` with connection pooling. Pattern: `_get_X_client()` lazily creates the singleton, checks `is_closed`. All functions accept an optional `client` parameter for testing.

## Concurrency & Memory Management

**Retrieval semaphore**: `_RETRIEVAL_SEM = asyncio.Semaphore(8)` in `main.py` wraps all retrieval tasks. Prevents 10+ concurrent external API calls from spiking memory.

**ML model lifecycle**: Embedding model (~500MB) and optional reranker (~1.3GB) loaded via `@lru_cache` in `vector_search.py`. At startup, the `lifespan` handler preloads models via `run_in_executor` — **blocking** so health checks don't pass before models are ready.

**SSE error handling**: `_event_stream()` wraps async calls in two tiers of try-except: (1) fatal calls — yield error event and return, (2) non-fatal calls — log warning, continue with partial response.

## Testing

~444 unit + integration tests. Mock external APIs in unit tests. Real-API tests marked `@pytest.mark.integration`.

Key test patterns:
- `conftest.py` has autouse fixture that clears all TTLCaches between tests + rate limit counters.
- Domain orchestrator tests: mock individual sub-modules, verify parallel execution + graceful degradation.
- Walk Score tests: autouse `_mock_api_key` fixture provides fake key via `monkeypatch`.
- **CI note**: `anthropic_api_key` defaults to `""` in `config.py` so tests run without the secret.

## Evaluation & Benchmarks

| Tool | Command | What it tests |
|------|---------|---------------|
| Router eval | `python -m eval.run_eval` | Source tag routing, intent, location resolution (39 queries) |
| Full eval + judge | `python -m eval.run_eval --full URL --judge` | End-to-end retrieval + LLM-as-judge synthesis grading |
| Source coverage | `python -m eval.source_coverage --full URL` | Per-sub-source data presence (29 queries, 41 checks) |
