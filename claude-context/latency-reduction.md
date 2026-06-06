# Latency Reduction — UrbanLayer

## Completed (2026-06-06)

### Prompt Caching
All LLM calls (router, synthesizer, conversation) now use Anthropic prompt caching via `_enable_prompt_caching()` in `backend/llm.py`. Static system prompts (~8KB router, ~12KB synthesizer) are sent as structured content blocks with `cache_control: {"type": "ephemeral"}`. Anthropic caches these server-side with a 5-minute TTL, giving ~80% latency reduction on cached input tokens. Cache hit/miss is tracked in the `llm_calls` table (`cache_read_tokens`, `cache_create_tokens`).

### Server Upgrade + Reranker Re-enable
Server upgraded from CX22 (4GB) to CX32 (8GB, $16.90/mo). `RERANKER_ENABLED=true` in `docker-compose.prod.yml`. Retrieval semaphore increased from `Semaphore(4)` to `Semaphore(8)` in `main.py`.

### Pipeline Timing Instrumentation
Phase-level timing added to `_event_stream()` in `main.py`. The `done` SSE event now includes a `timings` dict with `conv_synth`, `router`, `retrieval`, `first_token`, and `total` (all in ms). Frontend logs these to console via `[perf] pipeline timings (ms):`.

---

## Ready to Implement

### 1. Cache Zoning Polygons (saves 1-2s per query, ~5 min)

**File:** `backend/retrieval/zoning.py`

`zoning_polygons_for_map()` (line 88) fetches all zoning district polygons for a community area from ArcGIS with **no caching**. Each call returns ~1MB of GeoJSON (200-600 features). Zoning boundaries change rarely (ordinance amendments only).

**Fix:** Add a TTLCache (1-hour TTL, 77 entries — one per community area):
```python
_polygon_cache = TTLCache(ttl_seconds=3600, maxsize=77, name="zoning_polygons")
```
Cache key: `f"zoning_poly:{community_area}"`. Check/set around the HTTP call inside `zoning_polygons_for_map()`.

---

### 2. Cache Overlay Geometry Fetches (saves 1-3s per query, ~10 min)

**File:** `backend/retrieval/regulatory/overlays.py`

`query_overlay_with_geometry()` (line 83) queries a single ArcGIS overlay layer at a point with `returnGeometry=true`. Called up to 13 times per request (one per overlay layer) via `overlay_geojson_features()` (line 121). **Zero caching** on either function.

Meanwhile, the attribute-only `query_all_overlays()` (line 163) IS cached with 1-hour TTL.

**Fix:** Add a TTLCache to the assembled `overlay_geojson_features()` result:
```python
_geojson_cache = TTLCache(ttl_seconds=3600, maxsize=512, name="overlay_geojson")
```
Cache key: `f"overlay_geo:{round(lat,5)}:{round(lon,5)}"`. This single cache eliminates all 13 per-layer geometry fetches on cache hit.

---

### 3. Cache Geocoding Results (saves 0.5-3s on repeat addresses, ~5 min)

**File:** `backend/retrieval/geo.py`

`geocode_address()` (line 126) calls the Census Geocoder API with **no caching**. Multi-turn conversations about the same address pay the full geocoding latency each time.

**Fix:** Add a TTLCache:
```python
_geocode_cache = TTLCache(ttl_seconds=3600, maxsize=256, name="geocoded_addresses")
```
Cache key: the normalized address string. Wrap the HTTP call in cache check/set.

---

### 4. Shared HTTP Clients for ArcGIS and Qdrant (saves 20-50ms per query, ~20 min)

Multiple modules create a new `httpx.AsyncClient()` per function call, paying TCP+TLS overhead every time. The Socrata layer already has a shared client pattern (`socrata.py:get_shared_client()`) with connection pooling and HTTP/2.

**Modules creating per-call clients:**
- `backend/retrieval/vector_search.py` — 5 locations (Qdrant HTTP calls)
- `backend/retrieval/zoning.py` — 2 locations (ArcGIS point lookup + polygon fetch)
- `backend/retrieval/regulatory/overlays.py` — 4 locations (ArcGIS overlay queries)
- `backend/retrieval/regulatory/flood.py` — 1 location (FEMA API)
- `backend/retrieval/regulatory/environmental.py` — 1 location (EPA API)
- `backend/retrieval/geo.py` — 3 locations (Census Geocoder)

**Fix:** Create shared clients:

**Qdrant client** — add to `vector_search.py`:
```python
_qdrant_client: httpx.AsyncClient | None = None

def _get_qdrant_client() -> httpx.AsyncClient:
    global _qdrant_client
    if _qdrant_client is None or _qdrant_client.is_closed:
        _qdrant_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _qdrant_client
```
Replace all `async with httpx.AsyncClient(...) as client:` with `client = _get_qdrant_client()`.

**ArcGIS client** — add to a shared location or inline in each module. All ArcGIS calls target `gisapps.chicago.gov` so connection reuse helps. Each module already accepts an optional `client` parameter — the shared client becomes the default.

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
  │    └─ Geocoding (Census API)         ~200-500ms (embedded in router, not cached)
  │
  ├─ Parallel Retrieval (Semaphore 8)    ~300-800ms
  │    ├─ Socrata APIs (cached)          ~50-200ms per source
  │    ├─ ArcGIS Zoning polygons         ~500-2000ms (NOT cached)
  │    ├─ ArcGIS Overlay geometry         ~1000-3000ms (13 layers, NOT cached)
  │    ├─ Qdrant vector search           ~50-200ms
  │    └─ Domain orchestrators           ~200-500ms (TIF/EZ preloaded, property varies)
  │
  ├─ Context Assembly                    ~5-50ms (pure Python)
  │
  └─ Streaming Synthesis (Sonnet)        ~1-2s TTFT + ~2-3s streaming
       └─ System prompt cached           (5-min TTL via Anthropic prompt caching)
```

**Total typical latency:** 3-8s (first query), 2-5s (subsequent queries with warm caches).

Items 1-4 above would reduce the retrieval phase from ~1-3s to ~50-200ms on cache hit, cutting total latency by 1-3s for repeat areas.
