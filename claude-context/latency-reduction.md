# Latency Reduction — UrbanLayer

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

## Forward-Thinking Opportunities

### 5. Client-Side Map Data Caching (~30 min)

Currently, every new query re-fetches all polygon data from the backend, even if the user is asking about the same area. The frontend could cache polygon data by community area.

**Approach:** In `frontend/src/lib/useChat.ts` or a new `mapCache.ts`:
- After receiving a `map_data` SSE event, cache the zoning FeatureCollection keyed by community area
- On subsequent queries in the same community area, skip the zoning polygon fetch
- A `skipZoningPolygons` flag on the ChatRequest could tell the backend to skip the expensive fetch

**Options:**
- **Simple:** In-memory `Map` in a React ref. Cleared on page refresh. Minimal code.
- **Durable:** IndexedDB cache with TTL. Survives refresh but more complex.

Start with the simple approach.

---

### 6. Geometry Simplification (~1 hour, reduces payload 50-80%)

Zoning polygons often have excessive vertex counts for the zoom levels used in the sidebar map. Douglas-Peucker simplification with tolerance ~0.0001 degrees (~10m) would reduce vertex counts dramatically without visible quality loss.

**Options:**
- **Server-side (recommended):** Use `shapely.simplify()` on GeoJSON features in `_build_map_response()` in `main.py`. Shapely is already a dependency.
- **Client-side:** Use `@turf/simplify`. Adds a dependency but keeps server unchanged.

Server-side is better since it reduces both SSE payload size AND rendering time.

---

### 7. Vector Tiles (significant effort, best for scaling)

Replace per-query GeoJSON FeatureCollections with pre-rendered vector tiles served via a tile server (Martin, tippecanoe, or Mapbox-hosted). The frontend would load tiles on demand based on viewport, eliminating per-query polygon fetches entirely.

**When to consider:** If polygon data grows 10x+, if map responsiveness becomes a core feature, or if zoning polygons are shown by default (not query-gated).

---

### 8. Model Routing for Simple Queries (saves ~500ms, quality risk)

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
