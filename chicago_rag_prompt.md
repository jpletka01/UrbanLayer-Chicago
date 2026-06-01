# UrbanLayer — Chicago: Architecture & Design

## Project Overview

A **RAG-powered chat interface** (branded as **UrbanLayer — Chicago**) for natural-language questions about the city of Chicago. The system combines live data from the Chicago Data Portal (via Socrata API) with semantic search over the embedded Chicago Municipal Code to answer questions about public safety, neighborhood conditions, building activity, 311 complaints, business licensing, and local regulations.

The killer use case is a unified address query: a user types _"What's going on near 2400 N Milwaukee Ave?"_ and receives a synthesized response covering recent crime patterns, open 311 service requests, active building permits, business licenses, and applicable zoning — all from a single prompt, with an interactive map, analytics charts, and clickable source citations.

---

## Tech Stack

### Backend
- **Language:** Python 3.11
- **Framework:** FastAPI (async-first, SSE streaming)
- **LLM:** Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) for router + synthesizer; Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for conversation synthesis
- **Vector DB:** Qdrant v1.9.0 (Docker, self-hosted) — accessed via raw HTTP API (`httpx`), not `qdrant-client` (due to client/server version incompatibility)
- **Embeddings:** `BAAI/bge-base-en-v1.5` (768-dim, 512-token context) via `sentence-transformers`, running locally — no OpenAI key needed. Query prefix enabled for asymmetric retrieval
- **Async HTTP:** `httpx` for Socrata API calls with retry/backoff and shared `X-App-Token`
- **Persistence:** SQLite via `aiosqlite` (WAL mode) for conversation storage — `backend/data/chicago.db`
- **Geocoding:** Census Geocoder (free, no API key) + `shapely` point-in-polygon against cached community-area polygons

### Frontend
- **Framework:** React + TypeScript + Vite
- **Styling:** Tailwind CSS v3 (dark theme throughout, custom color tokens)
- **Chat UI:** Custom components with typewriter effect, inline citation pills, data pills
- **Map:** Mapbox GL JS (`dark-v11` basemap) + deck.gl (`ScatterplotLayer`, `GeoJsonLayer`) via `@deck.gl/mapbox` MapboxOverlay
- **Streaming:** SSE consumption with per-message context binding
- **State:** React hooks (`useChat`, `useTypewriter`, `useCopyButton`), no external state library

### Infrastructure
- **Docker Compose:** Qdrant service (pinned to v1.9.0)
- **Document pipeline:** Standalone Python scripts (`ingestion/`) for parsing, chunking, embedding, and storing municipal code sections
- **Env vars:** `.env` (backend: `ANTHROPIC_API_KEY`, `SOCRATA_APP_TOKEN`), `frontend/.env` (`VITE_MAPBOX_TOKEN`)

---

## Architecture: Three-Layer RAG Pipeline

```
User Message
  │
  ├─ Conversation Synthesis (Haiku) ─── expands follow-ups into self-contained queries
  │
  ├─ LLM Router (Sonnet) ─── produces RetrievalPlan JSON
  │
  ├─ Parallel Retrieval (asyncio.gather)
  │   ├─ Socrata APIs ─── crime, 311, permits, violations, business
  │   ├─ Vector Search ─── Qdrant semantic search + cross-ref expansion
  │   ├─ ArcGIS Zoning ─── point lookup (zone class) + polygon fetch (map overlay)
  │   └─ Map Data ─── raw geo-located rows for map + analytics
  │
  ├─ Context Assembly ─── merges results into ContextObject
  │
  ├─ Analytics Computation ─── month-over-month trends from map rows
  │
  └─ LLM Synthesis (Sonnet, streaming) ─── generates response with inline citations + trend data
```

### Layer 1 — Live Structured Data (Socrata API)
Real-time queries to the Chicago Data Portal using SoQL. Results are fetched at query time and injected into the LLM context as structured summaries. Each query carries a `$limit` guard and the assembler detects when results hit the cap (`capped: true`), instructing the LLM to say "at least N" instead of exact counts.

### Layer 2 — Static Document Embeddings (Qdrant Vector Search)
The full Chicago Municipal Code (Titles 1–18, 14,535 chunks from 8,615 sections) is chunked at the subsection level, embedded with `bge-base-en-v1.5`, and stored in Qdrant. Retrieved via semantic similarity with keyword boost scoring and per-section deduplication.

### Layer 3 — LLM Router + Synthesizer (Claude)
A Claude-based router parses the user message, produces a `RetrievalPlan` (sources, location, intent, time range, search query), and dispatches parallel queries to Layers 1 and 2. A second Claude call synthesizes all retrieved context — including analytics trends — into a streaming response with inline citation markers.

### Layer 4 — Conversation Persistence (SQLite)
Conversations, messages, and per-message state (context, plan, map data) are persisted in SQLite. Each assistant message stores the full context snapshot that was used to generate it, enabling per-question state toggling in the UI. A 10-message limit per conversation controls token costs.

---

## Data Sources

### Socrata Datasets (Chicago Data Portal)

All datasets accessed via `https://data.cityofchicago.org/resource/{dataset_id}.json` with SoQL query parameters and `X-App-Token` header.

| Dataset | ID | Key Fields | Use |
|---|---|---|---|
| Crimes 2001–Present | `ijzp-q8t2` | `date`, `primary_type`, `description`, `arrest`, `community_area`, `latitude`, `longitude` | Crime trends, safety assessments. 7-day data lag always surfaced |
| 311 Service Requests | `v6vf-nfxy` | `sr_type`, `status`, `owner_department`, `created_date`, `community_area`, `latitude`, `longitude` | Quality-of-life queries. `Open - Dup` filtered before aggregating |
| Building Permits | `ydr8-5enu` | `permit_type`, `work_description`, `issue_date`, `reported_cost`, `community_area`, `latitude`, `longitude` | Development activity, construction queries |
| Building Violations | `22u3-xenr` | `violation_date`, `violation_description`, `violation_status`, `community_area`, `latitude`, `longitude` | Property condition, landlord accountability |
| Business Licenses | `uupf-x98q` | `doing_business_as_name`, `license_description`, `business_activity`, `community_area`, `latitude`, `longitude` | Neighborhood character, business verification |
| Community Areas | `igwz-8jzy` | Boundaries GeoJSON | Address → community area resolution (shapely point-in-polygon) |
| IUCR Codes | `c7ck-438e` | Crime code lookup | Human-readable crime type translation |
| Zoning Districts | ArcGIS MapServer | `ZONE_CLASS`, `ZONE_TYPE`, `ORDINANCE_NUM` | Zoning point lookup + polygon overlay. Uses `gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer/1/query` (no API key). Socrata `p8va-airx` is non-queryable |

### Municipal Code (Vector Search)

- **Source:** Local HTML export from American Legal Publishing (`chicago-il-codes.html`, ~100MB, gitignored)
- **Scope:** Full Chicago Municipal Code, Titles 1–18, including the republished Zoning & Land Use Ordinance (Titles 16/17)
- **Pipeline:** `parse_chicago_code.py` → `chunk.py` → `embed_and_store.py`
- **Stats:** 8,615 sections → 14,535 chunks in Qdrant
- **Embedding model:** `BAAI/bge-base-en-v1.5` (768-dim, 110M params) with BGE query prefix for asymmetric retrieval

---

## The Router

The router is a Claude Sonnet call that runs before any retrieval. It receives the synthesized query (after multi-turn expansion) and returns a structured `RetrievalPlan`.

### Router Output Schema
```json
{
  "sources": ["crime_api", "311_api", "permits_api", "violations_api", "business_api", "vector_search"],
  "location": {
    "raw": "Wicker Park",
    "type": "intersection | address | neighborhood | community_area | none",
    "resolved_community_area": 24,
    "resolved_community_area_name": "West Town",
    "resolved_address": "2400 N Milwaukee Ave",
    "resolved_lat": 41.9270,
    "resolved_lon": -87.6984
  },
  "intent": "neighborhood_overview | incident_lookup | legal_question | event_query | trend_analysis | clarification_needed",
  "time_range_days": 90,
  "requires_disclaimer": true,
  "search_query": "accessory structures fence height residential",
  "clarification": null
}
```

### Router System Prompt Features
- Embeds all 77 community area names + 30+ neighborhood aliases (Wicker Park → West Town, etc.)
- **Search query guidance** for both zoning and non-zoning topics: home occupations ("search home occupation rules, not bakery"), accessory structures, licensing, building code, etc.
- Location resolution: maps neighborhood names to `community_area` integers
- If no location and query requires one: `intent = "clarification_needed"`, emits clarification text

---

## Context Assembly & Analytics

### Context Assembler (`assembler.py`)
Merges raw API results into a `ContextObject` with configurable caps:

```json
{
  "community_area": 24,
  "community_area_name": "West Town",
  "data_lag_note": "Crime data may lag by up to 7 days.",
  "crime_last_90d": {
    "total": 1756,
    "arrest_rate": 0.18,
    "by_type": {"THEFT": 412, "BATTERY": 287, ...},
    "capped": false
  },
  "open_311_requests": { ... },
  "permits": { ... },
  "violations": { ... },
  "businesses": { ... },
  "code_chunks": [ ... ],
  "parcel_zoning": {
    "zone_class": "RM-6",
    "zone_type": 4,
    "ordinance_num": null,
    "zoning_map_url": "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning"
  },
  "analytics": {
    "crime_trends": [
      {"category": "BATTERY", "current_count": 245, "prior_count": 199, "change_pct": 23},
      {"category": "THEFT", "current_count": 189, "prior_count": 222, "change_pct": -15}
    ],
    "trend_period": "Apr '26 vs Mar '26"
  }
}
```

### Server-Side Analytics (`analytics.py`)
Month-over-month trends computed from raw map data rows (up to 2500 crime, 1000 311, 500 permits):
- Groups records by year-month + category
- Skips the current partial calendar month
- Compares the two most recent complete months
- Returns top 8 categories per source, sorted by current count
- Results formatted as human-readable text in the synthesis prompt (not JSON) to save tokens

---

## Vector Search Pipeline

### Search Flow
```
query
  → prepend BGE query prefix ("Represent this sentence for searching relevant passages: ")
  → encode with bge-base-en-v1.5 (768-dim)
  → Qdrant dense search (limit = top_k × 5, overfetch for dedup)
  → filter legend-only table chunks
  → keyword boost: combined = 0.85 × dense + 0.15 × keyword_overlap
  → sort by combined score
  → per-section dedup (keep best chunk per section)
  → return top_k CodeChunks
```

### Key Features
- **Per-section deduplication** prevents long sections (e.g., 27 chunks) from dominating results
- **Keyword boost** (0.15 weight) helps when embedding similarity misses exact-term relevance
- **Cross-reference expansion** fetches related sections by ID from Qdrant payload
- **Cross-reference filtering** against a cached section index (scrolled once per process lifetime)
- **Reranker infrastructure** wired but disabled — MS MARCO model hurts on legal text; ready for a legal-domain reranker

### Chunking Strategy
- Chunk at the **subsection level**, never splitting across subsections
- Hierarchical header re-duplication in each chunk
- Table-aware: colspan/rowspan handling, composite multi-row headers, `[TABLE]` / `Row N: header=value` format
- Sub-section splits at category boundaries within tables (min 400 chars before splitting)
- Small table pieces merged when consecutive fragments fit within chunk budget

---

## LLM Synthesis

### SSE Event Stream
The `/chat` endpoint streams Server-Sent Events:

```
{"type": "plan",     "plan": RetrievalPlan,     "t_ms": 2400}
{"type": "context",  "context": ContextObject,  "t_ms": 6200}
{"type": "map_data", "map_data": MapDataResponse, "t_ms": 6500}
{"type": "token",    "text": "Based on...",     "t_ms": 7100}  ← first token
{"type": "token",    "text": " crime data"}
...
{"type": "done",     "t_ms": 13600}
```

### Synthesis Prompt Structure

**System prompt** instructs Claude to:
1. Use `[N]` citation markers that render as `§ <section>` pills in the frontend
2. Use `[data:crime]` / `[data:311]` / etc. data markers for API statistics
3. Surface data freshness (7-day crime lag)
4. Say "at least N" when data is capped
5. Add legal disclaimer when `requires_disclaimer: true`
6. Be concise — lead with direct answer
7. Place citations immediately after relevant statements
8. Weave notable month-over-month trends into answers naturally
9. When `parcel_zoning` is present, state the zoning classification as a definitive fact and link to `https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning` — never invent other URLs

**User prompt** includes:
- Full `ContextObject` as indented JSON (excluding analytics)
- Analytics formatted as readable text: `"Crime: BATTERY: 245 (up 23%)"`
- The user's question
- Instruction to answer from context only

---

## Conversation Persistence

### SQLite Schema (`backend/db.py`)

```sql
conversations (id TEXT PK, title, created_at, updated_at)
messages (id INTEGER PK, conversation_id FK, role, content,
          context_json, plan_json, map_data_json, map_fetched_at, position, created_at)
uploads (id TEXT PK, conversation_id FK, filename, mime_type, size_bytes, storage_path, created_at)
llm_calls (id INTEGER PK, request_group, conversation_id, phase, model,
           input_tokens, output_tokens, cache_read_tokens, cache_create_tokens,
           duration_ms, status, error_message, created_at)
request_logs (id INTEGER PK, request_group UNIQUE, conversation_id, user_message,
              intent, community_area, community_area_name, sources,
              total_duration_ms, status, error_message, created_at)
schema_version (version INTEGER PK)
```

- WAL mode, foreign keys enabled, singleton `aiosqlite` connection
- JSON blob columns for context/plan/mapData (written once, read whole)
- `llm_calls` logs every Anthropic API call (router, synthesizer, conversation synthesis) with token counts and wall-clock timing
- `request_logs` stores one summary row per `/chat` request (intent, location, sources, total duration)
- 10-message limit enforced via `count_user_messages()` check before routing

### Conversation API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/conversations` | List all with message counts |
| `POST` | `/api/conversations` | Create new conversation |
| `GET` | `/api/conversations/{id}` | Full conversation with all messages + context/plan/mapData |
| `DELETE` | `/api/conversations/{id}` | Delete (CASCADE to messages) |
| `PUT` | `/api/conversations/{id}/messages` | Append message pair |
| `PATCH` | `/api/conversations/{id}/messages/{position}` | Update map data (staleness refresh) |
| `POST` | `/api/conversations/import` | Bulk import from localStorage migration |

### Admin API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/admin/overview?period=30d` | Summary: total requests, tokens, cost, errors, by-model/by-phase |
| `GET` | `/api/admin/timeseries?period=30d&bucket=day` | Time-bucketed arrays for charts |
| `GET` | `/api/admin/latency?period=30d` | p50/p90/p99 by phase |
| `GET` | `/api/admin/conversations` | Conversation stats |
| `GET` | `/api/admin/requests?limit=50&offset=0` | Paginated request log |
| `GET` | `/api/admin/benchmark` | Retrieval benchmark results from `eval/benchmark_results.json` |

### LLM Call Tracking

Every Anthropic API call is logged via `tracked_create()` (non-streaming) or `tracked_stream()` (streaming) wrappers in `llm.py`. Each chat request generates a UUID `request_group` that links the 1-3 LLM calls from a single turn. Token usage is captured from `response.usage` (non-streaming) or `await stream.get_final_message()` (streaming). Cost estimation uses per-model pricing tables. Logging is non-fatal — db errors are caught and logged without disrupting the chat flow.

### Migration
On first frontend load, `migrateLocalStorageToSQLite()` reads the old `chicago.conversations.v1` localStorage key, POSTs all conversations to the import endpoint, then removes the localStorage keys.

---

## Frontend Architecture

### Routing & State Machine

URL-based conversation routing via `react-router-dom`:
- `/` — splash page (hero slideshow, chat input, suggestion chips, animated stats)
- `/c/:id` — conversation view (workspace with chat, sidebar, map)
- `/admin` — admin dashboard (usage metrics, latency, cost, benchmark results)

Conversations are bookmarkable and work with browser back/forward. Direct URL access loads from SQLite; invalid IDs redirect to `/`.

```
Splash (/) — hero slideshow + chat pill + suggestions + stats
  → [first message] → create conversation → navigate to /c/:id
Workspace (/c/:id) — split-screen: chat + sidebar
Admin (/admin) — observability dashboard (independent of chat state)
```

### Per-Message Context
Each assistant message stores its own `context`, `plan`, `mapData`, and `mapFetchedAt`. This enables:
- **Citations that survive multi-turn** — `[1]` in an old message still points to the right code chunk
- **Per-question state toggling** — clicking a past user message loads that turn's data into the sidebar
- **Map data staleness** — re-fetch if `mapFetchedAt` > 24 hours ago

### Sidebar
Two tabs: **Data** (map + analytics) and **Sources** (code chunks with citations).

**Data tab layout:**
- Mapbox + deck.gl map (~75% height) with ScatterplotLayers for crime/311/permits + GeoJsonLayer for zoning polygons
- Zoning/Points toggles (top-left) — Points off hides all scatter dots and shows zoning category legend
- Context-aware filter toggles (crime types, 311 request types, permit types, or source-level)
- Arrest filter (All / Arrested / No Arrest) for crime mode
- Dual-handle date range slider
- Data lag note (when applicable)
- Zoning codes table (collapsible, when zoning data present)
- Analytics section: SVG donut chart with hover expansion + thin-slice ring, MoM trend table with sortable columns

**Sources tab:**
- Ranked code chunks with `§ section` pills, relevance scores, expandable full text
- Clickable cross-reference pills with hover preview
- Full-section viewer drawer for cross-referenced sections

### Key Components
- `ChatInterface` — message list + input, per-question click handling, message limit UI
- `MessageBubble` — markdown rendering, citation/data pill injection, typewriter effect, click-to-select for user messages
- `SidebarPanel` — drag-to-resize, collapsible rail, Data/Sources tabs
- `MapView` — Mapbox + deck.gl with click-to-detail popups (Google Street View links), flyTo animation, zoning polygon overlay with per-district colors
- `AnalyticsSection` — pie chart + trend table, computed from map data
- `useChat` — SSE consumption hook, message limit enforcement, plan/context/mapData attachment

---

## Project File Structure

```
chicago/
├── backend/
│   ├── main.py                     # FastAPI: /chat SSE, /api/conversations/*, /api/admin/*, /api/map-data, /section/*
│   ├── router.py                   # Claude router → RetrievalPlan
│   ├── synthesizer.py              # Claude streaming synthesis with analytics formatting
│   ├── conversation.py             # Multi-turn query expansion (Haiku)
│   ├── assembler.py                # Context assembly with caps + capped detection
│   ├── analytics.py                # Server-side MoM trend computation
│   ├── db.py                       # SQLite persistence (aiosqlite, WAL, schema v2: +llm_calls, +request_logs)
│   ├── models.py                   # Pydantic models for all types
│   ├── config.py                   # Settings via pydantic-settings
│   ├── prompts.py                  # System prompts (router, synthesizer, conversation)
│   ├── llm.py                      # Shared client + tracked_create/tracked_stream + cost estimation
│   ├── data/                       # SQLite database (gitignored)
│   ├── retrieval/
│   │   ├── socrata.py              # Shared async client with retry/backoff
│   │   ├── crime.py                # Crime API (aggregated + block-level)
│   │   ├── three11.py              # 311 API (open requests + response times)
│   │   ├── buildings.py            # Permits + violations
│   │   ├── business.py             # Business licenses
│   │   ├── map_data.py             # Raw geo-located rows for map
│   │   ├── vector_search.py        # Qdrant search + keyword boost + dedup
│   │   ├── zoning.py               # ArcGIS zoning point lookup + polygon fetch
│   │   ├── geo.py                  # Geocoding + community area resolution
│   │   └── utils.py                # Shared helpers (cutoff_iso)
│   └── tests/                      # 192 tests (unit + integration)
│
├── ingestion/
│   ├── parse_chicago_code.py       # HTML → sections JSON (split-at-republication strategy)
│   ├── chunk.py                    # Section-aware chunking with table consolidation
│   ├── embed_and_store.py          # sentence-transformers → Qdrant (--recreate flag)
│   ├── load_community_areas.py     # Community area polygons → GeoJSON
│   └── data/                       # Generated: sections/, chunks.jsonl, community_areas.geojson
│
├── eval/
│   ├── queries.json                # 26 test queries (all passing)
│   ├── run_eval.py                 # Router-only and full pipeline eval
│   ├── retrieval_benchmark.py      # 18-query retrieval quality benchmark (--json-out for admin)
│   └── benchmark_results.json      # Machine-readable benchmark output (generated)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # State machine, async conversation lifecycle, per-question toggling
│   │   ├── components/
│   │   │   ├── AdminDashboard.tsx  # /admin page: metrics, charts, benchmark, request log
│   │   │   ├── ChatInterface.tsx   # Message list, input, message limit UI
│   │   │   ├── ChatInput.tsx       # Glassmorphism input with address autocomplete
│   │   │   ├── MessageBubble.tsx   # Markdown + citations + typewriter + click-to-select
│   │   │   ├── CitationPill.tsx    # [N] → § section pill with hover tooltip
│   │   │   ├── DataPill.tsx        # [data:*] → colored data source pill
│   │   │   ├── CrossRefPill.tsx    # Clickable cross-reference with hover preview
│   │   │   ├── SourceCitation.tsx  # Source card with rank, score, expandable text
│   │   │   ├── SourceDetailDrawer.tsx  # Full-section viewer for cross-refs
│   │   │   ├── Tooltip.tsx         # Shared hover tooltip (position: fixed, viewport clamping)
│   │   │   ├── ChunkText.tsx       # Chunk text renderer (delegates tables to ChunkTable)
│   │   │   ├── ChunkTable.tsx      # Formatted HTML table for table-bearing chunks
│   │   │   ├── DisclaimerBanner.tsx # Legal disclaimer banner
│   │   │   ├── PromptSuggestionChip.tsx # Splash page suggestion chips
│   │   │   ├── SidebarPanel.tsx    # Drag-to-resize, collapsed rail, Data/Sources tabs
│   │   │   ├── HistorySidebar.tsx  # Conversation history list
│   │   │   ├── HeroSlideshow.tsx   # Landing page photo carousel
│   │   │   ├── CountUp.tsx         # Animated stat counter
│   │   │   ├── admin/
│   │   │   │   ├── StatCard.tsx        # Animated metric card (wraps CountUp)
│   │   │   │   ├── TimeSeriesChart.tsx # SVG area/line chart with hover crosshair
│   │   │   │   ├── BarChart.tsx        # Horizontal bar chart (benchmark grades)
│   │   │   │   ├── LatencyTable.tsx    # p50/p90/p99 table with color thresholds
│   │   │   │   ├── RequestsTable.tsx   # Paginated request log with expandable rows
│   │   │   │   └── BenchmarkSection.tsx # Score cards + grade bars + pie + per-query table
│   │   │   └── sidebar/
│   │   │       ├── MapView.tsx     # Mapbox + deck.gl with click popups, zoning overlay
│   │   │       ├── MapLayerToggles.tsx
│   │   │       ├── MapLegend.tsx
│   │   │       ├── ArrestFilter.tsx
│   │   │       ├── StatusFilter.tsx   # Open/Closed status filter (311 mode)
│   │   │       ├── CostFilter.tsx     # Cost bucket filter (permits mode)
│   │   │       ├── DateRangeSlider.tsx
│   │   │       ├── DataView.tsx    # Data lag note + analytics (data cards removed)
│   │   │       ├── AnalyticsSection.tsx
│   │   │       ├── PieChart.tsx    # SVG donut with thin-slice ring
│   │   │       ├── TrendTable.tsx  # MoM trend rows with arrows
│   │   │       └── SourcesView.tsx
│   │   └── lib/
│   │       ├── api.ts              # SSE streaming, conversation CRUD, map data, admin endpoints
│   │       ├── useChat.ts          # Chat state hook with message limit
│   │       ├── history.ts          # Async API-backed persistence + migration
│   │       ├── types.ts            # TypeScript types matching backend Pydantic
│   │       ├── analytics.ts        # Client-side trend/pie computation
│   │       ├── mapColors.ts        # Shared color constants for map + charts
│   │       ├── sse.ts              # SSE parser
│   │       ├── useTypewriter.ts    # Character reveal animation
│   │       ├── useCopyButton.ts    # Copy-to-clipboard hook
│   │       ├── useConversationRouter.ts # URL ↔ conversationId sync
│   │       ├── constants.ts        # Suggestions, splash stats
│   │       ├── codeRefs.ts         # Section ID helpers
│   │       ├── clipboard.ts        # Copy utility
│   │       └── parseTable.ts       # Table markup parser
│   └── ...
│
├── docker-compose.yml              # Qdrant (pinned to v1.9.0)
├── .env.example
├── HANDOFF.md                      # Detailed session logs and decisions
├── README.md                       # User-facing setup guide
└── chicago_rag_prompt.md           # This file
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM | Claude Sonnet 4.6 (router + synth), Haiku 4.5 (conversation) | Best tool-use and structured output reliability; Haiku for cheap pre-routing |
| Vector DB | Qdrant v1.9.0 (Docker) | Free, fast, metadata filtering, payload search for cross-refs |
| Embeddings | `bge-base-en-v1.5` (768-dim, local) | Better semantic discrimination than bge-small on legal text; no external API |
| Streaming | SSE (`text/event-stream`) | Synthesis is slow (3–8s); streaming TTFT is critical UX |
| Persistence | SQLite via `aiosqlite` | Single user, single writer — simplest correct solution |
| Map | Mapbox + deck.gl | WebGL handles thousands of points; deck.gl's declarative layers make filter toggling trivial |
| Chunking | Section-aware (subsection level) | Legal cross-references break naive character chunking |
| Search scoring | 0.85 dense + 0.15 keyword | Keyword boost catches exact-term relevance that embeddings miss |
| Section dedup | Keep best chunk per section | Prevents long sections from monopolizing result slots |
| Analytics in synthesis | Text format, not JSON | Saves ~40% tokens vs JSON encoding of trend data |
| Map data in SSE | Emitted inline with stream | Eliminates separate /api/map-data round-trip for current turn |
| Map data staleness | 24h threshold | Fresh enough for recent conversations, current enough for revisits |
| Message limit | 10 user messages per conversation | Controls token costs; enforced both backend and frontend |
| LLM logging | Per-call rows, not per-request | Maps cleanly to cost calculation (different model pricing); avoids NULLs when phases are skipped |
| Admin charts | Custom SVG, no chart library | Existing PieChart is custom SVG; adding recharts (300KB) would be a dependency mismatch |
| Admin logging | Non-fatal wrappers | DB save errors are caught — logging never degrades the chat experience |

---

## Quick Reference — Commands

```bash
# Backend + frontend dev
docker compose up -d qdrant
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                              # :5173

# Tests
python -m pytest backend/tests/ -q                      # 192 tests
cd frontend && npx tsc --noEmit                         # type check

# Eval
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --out eval/last.md
python -m eval.retrieval_benchmark --out eval/retrieval_quality.md

# Full ingestion pipeline (only if Qdrant data is lost)
python -m ingestion.load_community_areas
python -m ingestion.parse_chicago_code
python -m ingestion.chunk
python -m ingestion.embed_and_store --recreate
```
