# Backend Guide — UrbanLayer

## Router (`router.py`)

Produces a `RetrievalPlan` JSON with: `sources` (list of SourceTags), `location` (raw + resolved lat/lon/community_area), `intent`, `time_range_days`, `requires_disclaimer`, `search_query`, `workflow_hint`, `clarification`.

Router system prompt embeds all 77 community area names + 30+ neighborhood aliases. Includes search query guidance for zoning-specific terminology (e.g., "search home occupation rules, not bakery") and non-zoning topics.

If no location and query requires one: `intent = "clarification_needed"`, emits clarification text.

**Source tags**: `crime_api`, `311_api`, `permits_api`, `violations_api`, `business_api`, `vector_search`, `property_domain`, `regulatory_domain`, `incentives_domain`, `neighborhood_domain`.

## Context Assembly (`assembler.py`)

Merges raw API results into a `ContextObject` with configurable caps (from `config.py`): `top_crime_types`, `top_311_types`, `top_chunks`, etc.

Key behaviors:
- `Open - Dup` dedup on 311 data before aggregating.
- Auto data-lag note for crime (7-day lag).
- Capped-result detection: sets `capped=True` when row count hits the `$limit` guard, so synthesis says "at least N".
- `partial_failures` field tracks which domain orchestrators returned errors (graceful degradation).

## Synthesis (`synthesizer.py`)

Streaming Claude call with structured system prompt rules:
1. `[N]` citation markers render as `§ section` pills in frontend.
2. `[data:crime]`, `[data:311]`, etc. render as colored data pills.
3. Surface data freshness (7-day crime lag).
4. Say "at least N" when data is capped.
5. Legal disclaimer when `requires_disclaimer: true`.
6. Weave MoM trends naturally (analytics formatted as text, not JSON).
7. State zoning classification as definitive fact. Link to official Zoning Map Web.
8. When property data present: lead with address, PIN, zoning, lot size, building characteristics.
9. When overlays present: list each with practical implications.
10. When incentives present: state eligibility with implications.

## Conversation (`conversation.py`)

Multi-turn context synthesis using Haiku. Improves follow-up detection for context references ("their", "it", "what about"), clarification answers.

**Deterministic neighborhood switching**: regex-based pre-check for "what about X?" / "compare to Y" patterns. If detected, substitutes the new neighborhood into the original question structure without LLM synthesis. Falls back to Haiku for ambiguous cases.

## Persistence (`db.py`)

SQLite via aiosqlite, WAL mode, singleton connection, schema versioning.

**Tables:**
- `conversations` — id, title, created_at, updated_at
- `messages` — with `context_json`, `plan_json`, `map_data_json` blob columns (written once, read whole)
- `uploads` — file metadata for Claude Vision
- `llm_calls` — per-call token/cost/latency logging (router, synthesizer, conversation phases)
- `request_logs` — per-chat-turn summary (intent, location, sources, duration)
- `schema_version` — migration tracking

**Conversation API** (7 CRUD endpoints): list, create, get (full with messages), delete (CASCADE), append messages, update map data, bulk import.

**Admin API** (6 endpoints): overview (tokens/cost/errors by model/phase), timeseries (bucketed for charts), latency (p50/p90/p99), conversations, paginated request log, benchmark results.

**LLM tracking**: `tracked_create()` / `tracked_stream()` wrappers capture token usage from `response.usage` or `stream.get_final_message()`. Each chat turn gets a UUID `request_group` linking its 1-3 LLM calls. Cost estimation uses per-model pricing. Logging is non-fatal.

## Caching (`retrieval/cache.py`)

`TTLCache` utility used by all external query modules. 17 caches across the codebase.

Cache key patterns:
- Spatial: `f"{source}:{round(lat,5)}:{round(lon,5)}"`
- PIN-based: `f"{source}:{pin14}"`
- Tract-based: `f"{source}:{tract_fips}"`

Startup preloading: TIF boundaries, Enterprise Zone boundaries, OZ tract list, GTFS stations, ACS demographics, community area polygons.

Cache hit/miss stats available via `/api/admin/cache-stats` (if implemented).

## Testing

~340 unit + integration tests. Mock external APIs in unit tests. Real-API tests marked `@pytest.mark.integration`.

Key test patterns:
- `conftest.py` has autouse fixture that clears all TTLCaches between tests.
- Socrata mocks: `httpx` response fixtures.
- ArcGIS mocks: JSON response fixtures matching real API shape.
- Domain orchestrator tests: mock individual sub-modules, verify parallel execution + graceful degradation.

## Evaluation & Benchmarks

Three eval tools in `eval/`:

| Tool | Command | What it tests |
|------|---------|---------------|
| Router eval | `python -m eval.run_eval` | Source tag routing, intent, location resolution (39 queries) |
| Full eval + judge | `python -m eval.run_eval --full URL --judge` | End-to-end retrieval + LLM-as-judge synthesis grading (4 dimensions) |
| **Source coverage** | `python -m eval.source_coverage --full URL` | Per-sub-source data presence in context AND synthesis (24 queries, 36 checks across 24 sub-sources) |

Source coverage benchmark produces a coverage matrix with four statuses per sub-source: COVERED, SYNTHESIS_GAP (data in context but not mentioned), RETRIEVAL_GAP (data not fetched), HALLUCINATION (mentioned but not in context). Also tracks API cap hits and whether the synthesis correctly hedges with "at least" phrasing. Results written to `eval/coverage_results.json` and optionally `--out coverage_report.md`.
