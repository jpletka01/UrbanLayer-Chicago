# Latency Reduction — UrbanLayer

## Property Profile (`/api/scorecard`), measured 2026-11-07 (decision Item 81)

The Profile is deterministic (no model) and waits for every source before it answers. Measured locally, in-process, 7 parcels × 5 rounds (n 35 cold, 35 warm): **cold p50 26.8 s, p95 46.0 s; warm p50 41 ms.** Full table, method and the Phase 4 contract sketch: `decisions/2026-11_frontend-rewrite.md` Item 81.

- **Where the time goes:** ~36 Socrata requests per cold Profile plus ArcGIS/FEMA/EPA/Census/FCC/Walk Score; the last to finish varies (property, 311, crime YoY, incentives). The City portal (`data.cityofchicago.org`) is the tail: a one-row query took 1.7–9.6 s during the run, and ~35 parallel requests roughly double its medians. Crime (`ijzp-q8t2`) is the largest single cost.
- **Known suspect:** the Cook County GIS point lookup, 10–11 s, on approximately resolved addresses only.
- **Hidden ordering:** the property domain's building-facts fallback waits for parcel flags (6.5 s p50).
- **Fixed:** TIF financial reports had no cache (warm 1.5–12 s on TIF parcels) → 24 h per district (warm p95 0.5 s).
- **Fixed:** crime's cache 15 min → 6 h (Item 83; the source is daily).
- **Built:** the new UI's first screen, `GET /api/scorecard/first` (Item 82): lot, district and what it allows in about 1–3 s locally, by the full response's own rules; then one swap.
- **Production, 2026-11-07 (Item 83, whole requests from outside, n=10 fresh addresses, before this branch deployed):** first visit p50 24.7 s / p95 44.1 s (matches local); **repeat visit p50 4.0 s / p95 14.4 s** (local: 41 ms). FEMA's flood map failed on every production request while answering locally in 1.5 s; failures are never cached, so each visit re-asks it (~4 s). The slowest repeats look like the uncached TIF reports fixed on this branch. Re-measure after deploy with the `scorecard timings` log lines.
- **Open:** FEMA from the production server; the Phase 4 split (Item 81).

**Measure:** `PYTHONPATH=. python -m eval.profile_latency --label <label> --rounds 5` (no model, public APIs, ~25 min); `--isolate` runs each slow lookup alone; `--base URL` times a running server. A running server logs one `scorecard timings` line per Profile; `PROFILE_TIMINGS=true` (dev only) adds the breakdown to the response as `_timings`. Instrumentation: `backend/timing.py`.

The sections below are the 2026-06 chat pipeline work.

## Completed (2026-06-06)

### Prompt Caching
All LLM calls (router, synthesizer, conversation) now use Anthropic prompt caching via `_enable_prompt_caching()` in `backend/llm.py`. Static system prompts (~8KB router, ~12KB synthesizer) are sent as structured content blocks with `cache_control: {"type": "ephemeral"}`. Anthropic caches these server-side with a 5-minute TTL, giving ~80% latency reduction on cached input tokens. Cache hit/miss is tracked in the `llm_calls` table (`cache_read_tokens`, `cache_create_tokens`).

### Server Upgrade + Reranker Re-enable
Server upgraded from CX22 (4GB) to CX32 (8GB, $16.90/mo). `RERANKER_ENABLED=true` in `docker-compose.prod.yml`. Retrieval semaphore increased from `Semaphore(4)` to `Semaphore(8)` in `main.py`.

### Pipeline Timing Instrumentation
Phase-level timing added to `_event_stream()` in `main.py`. The `done` SSE event now includes a `timings` dict with `conv_synth`, `router`, `retrieval`, `first_token`, and `total` (all in ms). Frontend logs these to console via `[perf] pipeline timings (ms):`.

### Cache Zoning Polygons (saves 1-2s per query)
`_polygon_cache = TTLCache(ttl_seconds=3600, maxsize=77, name="zoning_polygons")` in `zoning.py`. Cache key: `f"zoning_poly:{community_area}"`. Eliminates ArcGIS polygon fetch (~1MB GeoJSON) on cache hit.

### Cache Overlay Geometry (saves 1-3s per query)
`_geojson_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="overlay_geojson")` in `overlays.py`. Cache key: `f"overlay_geo:{round(lat,5)}:{round(lon,5)}"`. Eliminates all 13 per-layer ArcGIS geometry fetches on cache hit.

### Cache Geocoding Results (saves 0.5-3s on repeat addresses)
`_geocode_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="geocoded_addresses")` in `geo.py`. Cache key: normalized address string. Multi-turn conversations about the same address hit cache instead of Census Geocoder API.

### Shared HTTP Clients (saves 20-50ms per query)
Replaced per-call `httpx.AsyncClient()` with module-level shared clients across all non-Socrata modules:
- `vector_search.py` — `_get_qdrant_client()` (10 connections, 5 keepalive) — 5 call sites
- `zoning.py` — `_get_arcgis_client()` (10 connections, 5 keepalive) — 2 call sites
- `overlays.py` — `_get_arcgis_client()` (15 connections, 10 keepalive) — 4 call sites
- `flood.py` — `_get_fema_client()` (5 connections, 3 keepalive) — 1 call site
- `environmental.py` — `_get_epa_client()` (5 connections, 3 keepalive) — 1 call site
- `geo.py` — `_get_geocoder_client()` (5 connections, 3 keepalive) — 3 call sites

All follow the same pattern as `socrata.py:get_shared_client()`. Each function still accepts an optional `client` parameter for testing.

---

## Completed (2026-06-07)

### 5. Client-Side Map Data Caching

`ChatRequest.cached_community_area` tells the backend which community area's polygons the client already has. When it matches the resolved community area, `_fetch_map_rows()` skips zoning polygon, overlay geometry, and incentive zone polygon fetches. Frontend (`useChat.ts`) tracks `cachedMapRef` — a ref holding `{ communityArea, mapData }` — and merges cached zoning/overlay/incentive polygons into new map data when the backend returns null for those fields. Cache is in-memory (React ref), cleared on page refresh.

### 6. Geometry Simplification

`_simplify_geojson()` in `main.py` applies `shapely.simplify(tolerance=0.0001, preserve_topology=True)` to all Polygon/MultiPolygon features in the zoning, overlay_districts, and incentive_zones FeatureCollections before sending them in the `map_data` SSE event. Tolerance of 0.0001° ≈ 10m, no visible quality loss at UI zoom levels. Reduces polygon payloads 50-80%.

---

## Forward-Thinking Opportunities

### Vector Tiles (significant effort, best for scaling)

Replace per-query GeoJSON FeatureCollections with pre-rendered vector tiles served via a tile server (Martin, tippecanoe, or Mapbox-hosted). The frontend would load tiles on demand based on viewport, eliminating per-query polygon fetches entirely.

**When to consider:** If polygon data grows 10x+, if map responsiveness becomes a core feature, or if zoning polygons are shown by default (not query-gated).

---

### Model Routing for Simple Queries (saves ~500ms, quality risk)

Use Haiku instead of Sonnet for synthesis on simple lookups (e.g., "What zone is 123 Main St?"). The router already classifies intent — simple intents could be routed to Haiku.

**Risk:** Quality regression on edge cases. Would need A/B testing or a judge evaluation.

**Prerequisite:** Pipeline timing data (now available via the `timings` dict) to validate that synthesis is the bottleneck for these query types.

---

## Current Pipeline Timing Reference

```
User Message
  │
  ├─ Conversation Synthesis (Haiku)     ~0-300ms (skipped if first message or long input)
  │
  ├─ LLM Router (Sonnet)                ~500-1500ms (includes geocoding if address query)
  │    └─ Geocoding (Census API)         ~0-5ms cached / ~200-500ms cold
  │
  ├─ Parallel Retrieval (Semaphore 8)    ~50-200ms cached / ~300-800ms cold
  │    ├─ Socrata APIs (cached)          ~50-200ms per source
  │    ├─ ArcGIS Zoning polygons         ~0-5ms cached / ~500-2000ms cold
  │    ├─ ArcGIS Overlay geometry         ~0-5ms cached / ~1000-3000ms cold
  │    ├─ Qdrant vector search           ~50-200ms (shared client, connection reuse)
  │    └─ Domain orchestrators           ~200-500ms (TIF/EZ preloaded, property varies)
  │
  ├─ Context Assembly                    ~5-50ms (pure Python)
  │
  └─ Streaming Synthesis (Sonnet)        ~1-2s TTFT + ~2-3s streaming
       └─ System prompt cached           (5-min TTL via Anthropic prompt caching)
```

**Total typical latency:** 3-8s (first query), 2-4s (subsequent queries with warm caches — 1-3s faster than before caching/shared clients).
