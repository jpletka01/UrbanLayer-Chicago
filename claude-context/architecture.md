# Architecture — UrbanLayer

## RAG Pipeline Overview

```
User Message
  │
  ├─ Conversation Synthesis (Haiku) ─── expands follow-ups into self-contained queries
  │
  ├─ LLM Router (Sonnet) ─── produces RetrievalPlan JSON
  │
  ├─ Parallel Retrieval (asyncio.gather)
  │   ├─ Socrata APIs ─── crime, 311, permits, violations, business, vacant, food inspections
  │   ├─ Vector Search ─── Qdrant semantic search + cross-ref expansion
  │   ├─ ArcGIS Zoning ─── point lookup (zone class) + polygon fetch (map overlay)
  │   ├─ Domain Orchestrators ─── property, regulatory (+ARO housing), incentives (+grants), neighborhood
  │   └─ Map Data ─── raw geo-located rows for map + analytics
  │
  ├─ Context Assembly ─── merges results into ContextObject
  │
  ├─ Analytics Computation ─── month-over-month trends from map rows
  │
  └─ LLM Synthesis (Sonnet, streaming) ─── generates response with citations + trends
```

## Stack Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM | Claude Sonnet 4.6 (router + synth), Haiku 4.5 (conversation) | Best tool-use/structured output; Haiku for cheap pre-routing |
| Vector DB | Qdrant v1.9.0 via raw HTTP API (httpx) | Free, fast, metadata filtering. qdrant-client v1.18 incompatible with server v1.9 |
| Embeddings | bge-base-en-v1.5 (768-dim, local) | Better semantic discrimination than bge-small on legal text; no external API |
| Reranker | bge-reranker-v2-m3, 20% weight | MS MARCO over-indexed on keyword overlap, hurt legal text (A=9 D=2 F=2). bge-reranker at 0.2 weight was the sweet spot (higher values regress lot_size and setback queries) |
| Streaming | SSE (text/event-stream) | Synthesis is slow (3-8s); streaming TTFT is critical UX |
| Persistence | SQLite via aiosqlite (WAL), schema v6 | Single user, single writer — simplest correct solution |
| Sharing | Live links via unique token (`/s/:token`) | No snapshot duplication; CASCADE delete auto-revokes |
| Map | Mapbox GL JS + deck.gl | WebGL handles thousands of points; deck.gl declarative layers |
| Geocoding | Census Geocoder + shapely | Free, no API key, deterministic. 77 community areas + 30+ aliases |
| Containers | Docker Compose (Qdrant + backend + nginx/frontend) | Multi-stage build, CPU-only PyTorch, baked HF models, non-root user |
| Hosting | Hetzner CX32 (Nuremberg) — 2 vCPU, 8GB RAM. Live at `https://urbanlayerchicago.com` | Upgraded from CX22 (4GB) on 2026-06-06; reranker re-enabled |
| DNS/CDN | Cloudflare Free | Origin IP hiding, DDoS protection, static asset caching |
| TLS | Cloudflare Full (Strict) + Origin Certificate (expires 2041) | Zero-maintenance vs Let's Encrypt — no certbot/renewal cron |
| Auth | Google OAuth2 + self-rolled JWT (PyJWT) | One-click sign-in, no password storage, httpOnly cookies + CSRF double-submit |
| Rate Limiting | In-memory sliding window + daily budget cap | Tier-based (anon 3/day, free 25/day, admin unlimited) + API cost guard |
| Domain | `urbanlayerchicago.com` via Namecheap | Registered, NS migration to Cloudflare pending |

## Domain Architecture

Four domain orchestrators handle complex multi-source retrievals. Each runs as a single `asyncio.gather` task alongside existing flat sources.

**Property** (keyed on PIN, sequential → parallel):
```
Address → lat/lon → Cook County GIS Parcel (primary) or Socrata Parcel Universe (fallback) → PIN14
  → [Characteristics, Assessments, Sales, Tax Estimate] in parallel
```

**Regulatory** (keyed on lat/lon, fully parallel + ARO enrichment):
```
lat/lon → [Zoning Layers 1-24, FEMA Flood, EPA Brownfields] all in parallel
community_area → ARO Housing projects (parallel with overlays, enriches RegulatorySummary)
```

**Incentives** (keyed on lat/lon or community area, two-phase + grants):
```
lat/lon → [TIF boundary, Enterprise Zone, Grant Programs (SBIF+NOF)] in parallel
  → conditional: TIF fund analysis + project financials (if TIF hit), Opportunity Zone (needs tract)
community_area → [all active TIF districts via comm_area matching, Grant Programs]
  → fund analysis for each district in parallel
Post-retrieval: assembler checks property class code for tax incentive classification (6b/7a/7b/8)
```

**Neighborhood** (keyed on community area + lat/lon):
```
community_area → Demographics
lat/lon → [Transit proximity, Walk Score] in parallel
```

### Workflow Hints

The router emits a `workflow_hint` that tells domain orchestrators how deep to go:
- `site_due_diligence` — fetch everything (property, regulatory, incentives, neighborhood)
- `development_feasibility` — lot dimensions + zoning + overlays + code search
- `business_launch` — zoning + code search + business licenses + incentives
- `property_intelligence` — deep property focus (full assessment/sales/tax history)
- `neighborhood_overview` — standard sources + demographics + transit
- `general` — standard behavior, no domain expansion

## Vector Search Pipeline (v4)

```
query
  → prepend BGE query prefix (asymmetric retrieval)
  → encode with bge-base-en-v1.5 (768-dim) [thread pool]
  → Qdrant async dense search (limit = top_k × 5, overfetch for dedup)
  → filter legend-only table chunks
  → keyword boost: combined = 0.85 × dense + 0.15 × keyword_overlap
  → cross-encoder rerank ALL candidates [thread pool]
  → blend: final = 0.80 × norm_dense + 0.20 × norm_reranker
  → sort by blended score
  → per-section dedup (keep best chunk per section)
  → return top_k CodeChunks
```

Key design: rerank BEFORE per-section dedup. The v3 pipeline deduped first, then reranked — the reranker was stuck with whatever chunk the dense embedding liked most. v4 reranks all ~60 candidates first, so dedup picks the best-scoring chunk per section after blending. This fixed lot_size and liquor_school_distance queries (C→A).

**Note**: Reranker is enabled in production (`RERANKER_ENABLED=true`) after server upgrade to 8GB RAM (2026-06-06). Full pipeline with cross-encoder reranking and blended scoring is active.

## Context Management

- **TurnSummary**: pure function generates a compressed summary of each turn's question + answer. Stored in conversation history to reduce token count.
- **Sliding window**: recent turns get full context; older turns get TurnSummary only.
- **Location-aware isolation**: neighborhood switch detection is deterministic (regex + alias matching) before falling back to LLM synthesis.
- **Message limit**: 10 user messages per conversation, enforced backend + frontend.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chunking | Section-aware (subsection level) | Legal cross-references break naive character chunking |
| Search scoring | 0.85 dense + 0.15 keyword | Keyword boost catches exact-term relevance embeddings miss |
| Section dedup | Keep best chunk per section | Prevents long sections from monopolizing results |
| Analytics format | Text in synthesis prompt, not JSON | Saves ~40% tokens vs JSON encoding of trend data |
| Map data delivery | Inline SSE events, not separate endpoint | Eliminates round-trip for current turn's map data |
| Map data staleness | 24h threshold for re-fetch | Fresh enough for recent conversations, current for revisits |
| LLM logging | Per-call rows, not per-request | Maps cleanly to cost calculation (different model pricing) |
| Admin charts | Custom SVG, no chart library | Existing PieChart is custom SVG; recharts (300KB) would be a dependency mismatch |
| Domain routing | Hybrid (coarse domain tags + workflow hints) | Flat expansion (20+ tags) overwhelms router; pure workflow is too rigid for single-domain queries |
| Overlay caching | Startup-loaded GeoJSON + shapely point-in-polygon | Same pattern as community areas in geo.py. Avoids API calls for boundary checks |
| HTML parsing | Split-at-republication strategy | Malformed div in Title 18 causes lxml to silently nest ~8MB of content. Split file at republication banner, parse halves separately |
