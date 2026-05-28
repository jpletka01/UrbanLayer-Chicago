# Chicago City Intelligence

RAG-powered chat interface for natural-language questions about Chicago. Combines live data from the Chicago Data Portal (Socrata API) with semantic search over the embedded Chicago Municipal Code.

## Stack

- **Backend:** Python 3.11, FastAPI, async Socrata + Anthropic + Qdrant clients, SSE streaming
- **Frontend:** React + TypeScript + Vite + Tailwind
- **Vector DB:** Qdrant (Docker)
- **Embeddings:** sentence-transformers `BAAI/bge-small-en-v1.5` (local, 384-dim, 512-token context, no API key)
- **LLM:** Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) for both router and synthesizer

## One-time setup

```bash
# 1. Python env
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Frontend deps
cd frontend && npm install && cd ..

# 3. Env vars
cp .env.example .env
# Edit .env:
#   ANTHROPIC_API_KEY  — required, https://console.anthropic.com
#   SOCRATA_APP_TOKEN  — recommended (higher rate limit), https://data.cityofchicago.org/profile/app_tokens
#   QDRANT_URL         — leave as default

# 4. Start Qdrant
docker compose up -d qdrant
```

## Ingest the Municipal Code

The Municipal Code is parsed from a local HTML export. Drop `chicago-il-codes.html` (American Legal Publishing format, current through March 18, 2026 or later) into the project root before running the pipeline.

```bash
# Cache community-area polygons (one-time, ~5s)
.venv/bin/python -m ingestion.load_community_areas

# Parse the HTML into per-section JSON files (~10k sections, ~60s)
.venv/bin/python -m ingestion.parse_chicago_code
# Or limit to a single Title for faster iteration:
.venv/bin/python -m ingestion.parse_chicago_code --title 17

# Chunk and embed
.venv/bin/python -m ingestion.chunk
.venv/bin/python -m ingestion.embed_and_store
```

### How the chunker works

- **One chunk per Section** when the section fits in ~1,800 chars; longer sections are split at paragraph boundaries
- **Hierarchical header is duplicated** at the top of every chunk so it's interpretable on its own:
  ```
  CHICAGO MUNICIPAL CODE
  Title 17 — Chicago Zoning Ordinance
  Chapter 17-2 — Residential Districts
  § 17-2-0200 — Allowed uses
  ```
- **Tables get colspan/rowspan-aware extraction with composite headers.** A 3-row header like `USE GROUP / Zoning Districts / Use Standard / Parking Standard` × `Use Category / RS-1 ... RM-6.5 / – / –` becomes one composite label per column (`"Zoning Districts - RS - 1"`, `"Use Standard"`, etc.). Rows then flatten to `Row N: header=value; header=value`. Sub-section header rows inside a table (e.g. `"A. Household Living"`, `"PUBLIC AND CIVIC"`) become natural chunk-split boundaries, so the residential use table becomes one chunk per use-category instead of one giant table chunk.
- **What this unlocks at query time**: every use × district intersection is individually retrievable. "Can I put a Coach House in RM-4.5?" → returns the row directly. "What's the max building height in RT-4?" → returns `Principal residential buildings: 38`. Same goes for bulk/density standards, parking ratios, signs, landscape buffers — every regulatory number from Title 17 is now a queryable fact.
- **Cross-references** (`<Link to="...#JD_17-2-0303-B">`) extracted into payload metadata and resolvable one hop at retrieval time
- **prev_section / next_section** adjacency stored in payload for "see also" expansion
- **Legislative history and effective dates** parsed from the standard `(Added Coun. J. 6-27-90)` footer
- **Definitions** (`"foo" means ...`) heuristically extracted into a separate metadata field
- **Has-table flag** lets the router prefer tabled sections for use-permitted queries
- **Title 16/17 deduplication**: the source file republishes Titles 16 and 17 as a separate "Chicago Zoning Ordinance and Land Use Ordinance" volume at the tail. The parser dedups by section ID — the Municipal Code copy wins.

## Run

```bash
# Backend (port 8000)
.venv/bin/uvicorn backend.main:app --reload

# Frontend (port 5173)
cd frontend && npm run dev
```

Open http://localhost:5173.

## Tests

```bash
.venv/bin/python -m pytest backend/tests/ -v
```

## Smoke test the API

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```

## How a request flows

1. Frontend POSTs `{message, history}` to `/chat`.
2. **Router** (Claude) parses the message into a `RetrievalPlan` with `sources`, `location`, `intent`, `time_range_days`, `requires_disclaimer`.
3. Plan is streamed to the client as the first SSE event so the sidebar can start rendering skeletons.
4. **Parallel retrieval** fires Socrata + Qdrant queries via `asyncio.gather`.
5. **Context assembler** merges results into a capped, deduped `ContextObject` (top-5 crime types, top-15 311 types, top-5 chunks, `Open - Dup` filtered).
6. Context is streamed to the client (sidebar updates).
7. **Synthesizer** (Claude streaming) produces the final answer; tokens are streamed to the client.
8. Disclaimer banner renders if `requires_disclaimer` was set by the router.

## Project layout

See the [implementation plan](~/.claude/plans/velvet-gliding-salamander.md) for the full architecture rationale and the decisions that shaped this build.

```
backend/
├── main.py              # FastAPI /chat SSE endpoint
├── router.py            # Claude router → retrieval plan
├── synthesizer.py       # Claude streaming synthesis
├── assembler.py         # Pure context-merging function (pytest-covered)
├── models.py            # Pydantic types
├── config.py            # Env + dataset/model IDs
├── retrieval/
│   ├── socrata.py       # Shared async client with retry/backoff
│   ├── crime.py         # ijzp-q8t2
│   ├── three11.py       # v6vf-nfxy
│   ├── buildings.py     # ydr8-5enu + 22u3-xenr
│   ├── business.py      # uupf-x98q
│   ├── vector_search.py # Qdrant semantic + payload-filter cross-ref
│   └── geo.py           # CA lookup + Census geocoder + shapely
└── tests/
ingestion/
├── scrape_municode.py   # Walk library.municode.com → section JSON
├── chunk.py             # Section-aware subsection-level chunker
├── embed_and_store.py   # sentence-transformers + Qdrant upsert
└── load_community_areas.py  # Cache CA polygons as GeoJSON
frontend/src/
├── App.tsx              # Splash → split-screen state machine
├── components/          # Hero, ChatInput, MessageBubble, Sidebar, etc.
└── lib/                 # api.ts (SSE), history.ts (localStorage), types.ts
```

## Known follow-ups (Phase I — stretch)

- Address autocomplete (Census Geocoder, debounced)
- Map view (Leaflet) for crime/311/zoning overlay
- Multi-turn follow-up resolution ("what about the next neighborhood over?")
- Full Municipal Code coverage beyond Title 17
