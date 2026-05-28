# Project Handoff — Chicago City Intelligence

A snapshot of what's been built, the decisions behind it, and what should come next. Companion to `README.md` (user-facing setup) and `~/.claude/plans/velvet-gliding-salamander.md` (the original implementation plan).

---

## TL;DR

A RAG-powered chat interface for natural-language questions about Chicago. Combines live Chicago Data Portal (Socrata) data with semantic search over the entire Chicago Municipal Code. Single killer query: *"What's going on near 2400 N Milwaukee Ave?"* → a unified response covering crime, 311, building activity, business licenses, and applicable zoning, all from one prompt.

**Current status (2026-05-28):** Full pipeline operational. Ingestion complete (14,628 chunks in Qdrant). Eval suite passes 26/26 queries (100%). Multi-turn conversation synthesis added. Ready for UI testing and production hardening.

---

## Stack (Locked)

| Layer | Choice | Reasoning |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-first, OpenAPI for free, easy SSE |
| LLM | Anthropic Claude **Sonnet 4.6** (`claude-sonnet-4-6`) for both router and synthesizer | Latest non-Opus model, better tool-use, structured output reliability |
| Vector DB | **Qdrant v1.9.0** (Docker, self-hosted) | Free, fast, good metadata filtering, payload search supports cross-ref lookup |
| Embeddings | **`BAAI/bge-small-en-v1.5`** via sentence-transformers (local, 384-dim, 512-token context) | Originally chose MiniLM-L6 (256-token context, too small for legal sections); upgraded during Title-17 work. Same dim → Qdrant config unchanged |
| Streaming | **SSE** (`text/event-stream`) | Synthesizer is the slow part (~3–8s); streaming TTFT is much better UX |
| Chat memory | **Multi-turn from day one**, history in client `localStorage`, server is stateless | Simplest persistence model, scales |
| Geocoding | **Census Geocoder** (free, no key) + shapely point-in-polygon against cached community-area polygons | No rate limit, no API key, deterministic |
| Frontend | **React + TypeScript + Vite + Tailwind v3** | Type-safe contract with FastAPI Pydantic via OpenAPI |
| Doc ingest | **Parse local `chicago-il-codes.html`** (American Legal Publishing export, ~100MB) | Originally tried scraping Municode (deleted); the local HTML export is much more reliable |

Decisions that came up later and were resolved:
- The HTML file has a malformed div somewhere in Title 18 that causes lxml/html.parser to silently nest the trailing ~8MB (the republished Titles 16/17 "Zoning + Land Use Ordinance" volume) inside an earlier element. Worked around by splitting the file at the republication banner string and parsing each half separately. Without this, 250 republished sections and 1 net-new section were missing.
- Sentence-transformers import is lazy inside `vector_search._model()` so FastAPI can boot without the heavy torch dependency installed.
- Qdrant pinned to v1.9.0 because Docker Hub had issues with `:latest` tag and to ensure reproducible builds.
- Vector search uses raw HTTP API (httpx) instead of qdrant-client Python library due to client v1.18.x incompatibility with server v1.9.0.

---

## What's Done

Everything below is in the repo, tested and verified.

### Backend (`backend/`)
- `main.py` — FastAPI app, `/chat` SSE endpoint with phase timing events
- `router.py` — Claude-based router producing strict `RetrievalPlan` JSON; system prompt embeds the 77 community-area names + 30+ neighborhood aliases + **search query guidance for zoning-specific terminology**
- `synthesizer.py` — streaming Claude synthesis call
- `assembler.py` — pure context-merging function with caps (top-5 crime types, top-15 311 types, top-5 chunks), `Open - Dup` dedup, auto data-lag note
- `models.py` — Pydantic types: `RetrievalPlan`, `ContextObject`, `ChatChunk` (with `t_ms` timing), `Message`, `ChatRequest`
- `config.py` — env via pydantic-settings (Anthropic key, Socrata token, Qdrant URL, model/dataset IDs)
- `retrieval/`:
  - `socrata.py` — shared async client with retry/backoff, `X-App-Token`, `$limit` guard
  - `crime.py` — `ijzp-q8t2` (neighborhood-aggregated + block-level), uses two parallel queries for crime counts + arrest counts (SoQL `case()` doesn't exist)
  - `three11.py` — `v6vf-nfxy` (open requests + response times, `Open - Dup` filtered)
  - `buildings.py` — `ydr8-5enu` permits (uses `reported_cost` field) + `22u3-xenr` violations
  - `business.py` — `uupf-x98q` active licenses
  - `vector_search.py` — Qdrant semantic search via raw HTTP API + payload-filter cross-ref expansion, lazy embedder
  - `geo.py` — 77 community areas + alias table + Census Geocoder + shapely
- `tests/` — **113 tests total** (100 unit + 13 integration), all passing:
  - `test_api.py` — API endpoint tests (SSE streaming, error handling, timing)
  - `test_assembler.py` — context assembly, caps, dedup
  - `test_geo.py` — community area resolution, aliases
  - `test_models.py` — Pydantic model validation
  - `test_retrieval.py` — Socrata query structure
  - `test_router.py` — router prompt, LLM response parsing
  - `test_socrata.py` — retry logic, error handling
  - `test_synthesizer.py` — prompt construction
  - `test_vector_search.py` — cross-reference expansion
  - `test_integration.py` — **real API tests** against Socrata, Census Geocoder, Anthropic, Qdrant

### Ingestion (`ingestion/`)
- `parse_chicago_code.py` — HTML parser with split-at-republication strategy, state machine for Title→Chapter→Article→Subarticle→Part, colspan/rowspan-aware table extraction with composite multi-row headers
- `chunk.py` — section-aware chunking with hierarchical header re-duplication, table flattening to `Row N: header=value`, sub-section splits inside tables at category boundaries (`A. Household Living`, `PUBLIC AND CIVIC`)
- `embed_and_store.py` — sentence-transformers + Qdrant upsert to two collections (`chicago_municipal_code`, `chicago_zoning` for Title 17 filter-free)
- `load_community_areas.py` — fetches and caches community-area polygons from Socrata `igwz-8jzy` as GeoJSON
- **Pipeline fully run**: 8,615 sections → 14,628 chunks → Qdrant (took ~3 minutes with MPS acceleration)

### Frontend (`frontend/`)
- Vite + React + TypeScript + Tailwind v3 scaffold
- State machine in `App.tsx`: splash (hero slideshow + chat pill + suggestion chips + ingestion stats grid) → split-screen workspace
- Components per the style guide:
  - `HeroSlideshow` (5 Unsplash photos, cross-fade)
  - `ChatInput` (glassmorphism pill, hero + compact variants)
  - `MessageBubble` (react-markdown, inline citation styling)
  - `DisclaimerBanner` (amber, legal disclaimer)
  - `SidebarPanel` (sources, latency, crime breakdown, 311, code-chunk citations, skeletons during loading)
  - `SourceCitation`, `PromptSuggestionChip`
- `lib/api.ts` (SSE fetch streaming), `lib/history.ts` (localStorage), `lib/types.ts` (matches backend Pydantic)
- **Builds cleanly** (~322KB JS, 16KB CSS)

### Benchmarks & Eval (`eval/`)
- **Parser stats** — `python -m ingestion.parse_chicago_code --stats` prints per-title section/table/xref/definition/legislative-history counts, plus dedup-skipped count. Currently: **8,615 sections** across all titles (17 active titles; 12 is reserved; 250 dedupes from the republished Titles 16/17 at file tail). Title 17 has 147 sections, 89 tables, 144 with legislative history.
- **Per-phase latency** — every SSE event carries `t_ms` (wall-clock ms since `/chat` request received). Sidebar renders Router / Retrieval / Synthesis-TTFT / Total live. Eval runner aggregates p50/p95.
- **Query test set** — `eval/queries.json` has **26 representative queries** spanning neighborhood overviews, address lookups, crime trends, 311, zoning legal questions, dimensional standards, parking ratios, sign regs, definitions, alias resolution, clarification handling, compound queries.
- **Eval runner** — `eval/run_eval.py` with two modes: `--router-only` (router only, ~30s, ~$0.05) and `--full <URL>` (full backend, captures retrieval + timings). Both emit stdout + optional markdown report.
- **Baseline established**: 26/26 passing (100%), latency p50: router 2.4s, retrieval 3.8s, total 13.6s

---

## What's NOT Done

### 1. ~~Violations API retrieval~~ ✅ DONE
Fixed in this session. The violations dataset now queries by bounding box derived from community area polygons (`geo.community_area_bounds()`), since the dataset has lat/lon but no community_area field.

### 2. The Municipal Code is gitignored
- `chicago-il-codes.html` (~100MB) is not in version control (`.gitignore` line 17).
- Anyone cloning the repo needs to obtain it separately (presumably from American Legal Publishing or a similar source — the user provided it once).

### 3. Stretch goals (Phase I)
- **Leaflet map view** showing crime pins, 311 markers, zoning overlay for a queried neighborhood. Right side of the split-screen has space reserved for this. *Not started.*
- **Address autocomplete** — ✅ **DONE.** Added `/autocomplete` endpoint using Census Geocoder + frontend dropdown in `ChatInput.tsx` with debounced suggestions, keyboard navigation, and click-to-select.
- **Multi-turn follow-up resolution** — ✅ **DONE.** Added `backend/conversation.py` with a pre-router synthesis layer that merges conversation context into self-contained queries. Uses Haiku for fast/cheap synthesis when needed (heuristic gate avoids unnecessary LLM calls).

### 4. Deferred but probably worth doing
- **LLM-as-judge eval** — grade synthesis answers for citation accuracy + factuality + directness. ~$0.05 × 30 questions per run. Mentioned in benchmarks plan as Tier 4 (deferred).
- **Cost/token logging** — wrap the Anthropic client to record input/output tokens per request. Low effort, easy ongoing visibility. Mentioned as Tier 5.
- **Deployment** — currently local-only via `docker-compose up qdrant` + `uvicorn` + `npm run dev`. No production deployment story.
- **Postgres / server-side history** — currently the API is stateless and history lives in localStorage. Fine for a demo. Would need Postgres for multi-device sync.
- **Latency optimization** — Router p50 is 2.4s (could try Haiku), total p50 is 13.6s.

### 5. Known fragile heuristics
- **Sub-header detection inside tables** uses a length cap (<80 chars) and same-value-across-most-of-row heuristic. Works for the residential use table (`"A. Household Living"`) but could miss tables with unusual sub-section conventions.
- **Multi-row header count** is inferred from how many consecutive rows in row 0 share the same value (proxy for rowspan carry-down). Works for the use table (3 header rows) but caps at 4 rows.
- **Cross-references** include Title-shaped (`"Title17"`) and Chapter-shaped (`"Ch.17-2"`) anchors as well as section IDs. `expand_cross_references` filters to section IDs only; future code could handle the chapter/title anchors differently.

### 6. Title 18 empty-body sections (Investigated — not a bug)
334 sections in Title 18 (Building Code) have no body text. Investigation showed these are legitimate structural placeholders in the Building Code format — section headers like "18-14-101 General" that contain no prose, with content in subsections like "18-14-101.1 Title". These won't hurt retrieval; they simply won't match queries (which is correct).

---

## Session Log (2026-05-28)

Work completed in this session:

1. **Comprehensive test suite** — Added 100+ tests covering all backend modules with both unit tests (mocked) and integration tests (real APIs). Found and fixed several bugs through testing.

2. **Socrata API bug fixes**:
   - Crime query used `case()` function which doesn't exist in SoQL — rewrote to use two parallel queries
   - Permits dataset uses `reported_cost` not `estimated_cost` — fixed field name
   - Updated Socrata app token in `.env`

3. **Qdrant compatibility fix** — Python client v1.18.x uses `query_points` API not available in server v1.9.0. Switched to raw HTTP API via httpx.

4. **Full ingestion pipeline run**:
   - Parsed 8,615 sections (~12s)
   - Chunked to 14,628 chunks (~1s)
   - Embedded and stored in Qdrant (~3 min with MPS)

5. **Router prompt improvements** — Added detailed guidance for constructing zoning-specific search queries. Key insight: queries mentioning specific use names (daycare, restaurant) match business licensing code (Title 4) instead of zoning code (Title 17). Solution: emphasize "allowed uses", "use table", district types.

6. **Eval baseline established** — 26/26 queries passing (100%). Latency: router p50=2.4s, retrieval p50=3.8s, total p50=13.6s.

7. **Title 18 investigation** — Confirmed empty-body sections are legitimate placeholders, not a parser bug.

8. **Multi-turn conversation synthesis** — Added `backend/conversation.py` to handle multi-turn context. When a user provides a short answer to a clarification (e.g., "lincoln park" after being asked for a location), the system now synthesizes the full query ("Is it legal to add a balcony to a townhouse in Lincoln Park?") before routing. Uses Haiku for speed/cost, with a heuristic gate to avoid unnecessary LLM calls on single-turn queries.

9. **Violations API fix** — Rewrote `violations_by_community_area()` to query by bounding box (lat/lon) since the dataset lacks a `community_area` field. Added `geo.community_area_bounds()` helper.

10. **Address autocomplete** — Added `/autocomplete` endpoint + `geocode_address_suggestions()` in geo.py. Frontend `ChatInput.tsx` now has a debounced dropdown with keyboard navigation.

---

## Recommended Next Steps (Prioritized)

### Step 1 — Test the UI end-to-end
```bash
docker compose up -d qdrant
.venv/bin/uvicorn backend.main:app --reload &
cd frontend && npm run dev
```
Open http://localhost:5173 and try the killer query: "What's going on near 2400 N Milwaukee Ave?"

### Step 2 — Fix violations retrieval
The violations dataset needs geo-based querying. Options:
1. Pre-compute community area for each violation using lat/lon
2. Query by bounding box and filter in Python
3. Use Socrata's `within_polygon` function if available

### Step 3 — Add more eval queries
Current 26 queries cover the happy path well. Add edge cases:
- Misspelled neighborhood names
- Questions mixing English/Spanish neighborhood names
- Very long compound queries
- Queries that should return "I don't know"

### Step 4 — Stretch goal: address autocomplete
Easiest of Phase I. Use the Census Geocoder we already have. Debounce input by 300ms, render suggestions as a dropdown under the chat pill.

### Step 5 — Stretch goal: Leaflet map
Right side of split-screen has a placeholder. Need to surface lat/lon from crime data (currently aggregated).

---

## How to Get Productive Quickly

If you're a fresh agent picking this up:

1. **Read in this order**: `README.md` (user setup) → `HANDOFF.md` (this file) → `~/.claude/plans/velvet-gliding-salamander.md` (original architectural rationale)
2. **Check current state**: 
   ```bash
   .venv/bin/python -m pytest backend/tests/ -q  # Should be 113 passed
   cd frontend && npm run build                   # Should succeed
   ```
3. **Verify env**: `.env` should have `ANTHROPIC_API_KEY` and `SOCRATA_APP_TOKEN` set
4. **Files most likely to need edits**:
   - `backend/router.py` — router prompt iteration
   - `backend/synthesizer.py` system prompt — answer quality tuning
   - `ingestion/chunk.py` — heuristic refinements
   - `eval/queries.json` — add new test cases as you discover them

## Repo Layout

```
chicago/
├── README.md                       # User-facing setup
├── HANDOFF.md                      # This file
├── chicago_rag_prompt.md           # Original product spec
├── style_guide.md                  # Original UI spec
├── chicago-il-codes.html           # Source HTML — GITIGNORED, get separately
├── docker-compose.yml              # Qdrant (pinned to v1.9.0)
├── requirements.txt
├── pytest.ini                      # Test configuration
├── .env.example
├── backend/
│   ├── main.py                     # FastAPI /chat (SSE w/ t_ms timing)
│   ├── router.py                   # Claude router (with search query guidance)
│   ├── synthesizer.py              # Claude streaming synth
│   ├── conversation.py             # Multi-turn context synthesis (Haiku)
│   ├── assembler.py                # Pure (pytest-covered)
│   ├── models.py
│   ├── config.py
│   ├── retrieval/                  # socrata.py + per-dataset wrappers + geo.py + vector_search.py
│   └── tests/                      # 130+ tests (unit + integration)
├── ingestion/
│   ├── data/                       # Generated: sections/, chunks.jsonl, community_areas.geojson
│   ├── parse_chicago_code.py       # HTML → sections JSON, --stats flag
│   ├── chunk.py                    # sections → chunks.jsonl
│   ├── embed_and_store.py          # chunks → Qdrant
│   └── load_community_areas.py     # CA polygons → GeoJSON
├── eval/
│   ├── queries.json                # 26 test queries
│   ├── run_eval.py                 # --router-only | --full <URL>
│   ├── baseline_router.md          # Router-only results
│   └── baseline_full_v2.md         # Full pipeline results (26/26 passing)
└── frontend/
    ├── src/components/             # Hero, ChatInput, MessageBubble, Sidebar, etc.
    ├── src/lib/                    # api (SSE), history (localStorage), types
    └── src/App.tsx                 # State machine
```

## Quick Reference — Useful Commands

```bash
# Tests + builds
.venv/bin/python -m pytest backend/tests/ -q           # 113 tests
.venv/bin/python -m pytest backend/tests/test_integration.py -v  # Real API tests
cd frontend && npm run build

# Parser sanity check (no JSON output)
.venv/bin/python -m ingestion.parse_chicago_code --stats

# Full ingestion pipeline (only needed if Qdrant data is lost)
docker compose up -d qdrant
.venv/bin/python -m ingestion.load_community_areas
.venv/bin/python -m ingestion.parse_chicago_code
.venv/bin/python -m ingestion.chunk
.venv/bin/python -m ingestion.embed_and_store

# Eval
PYTHONPATH=. .venv/bin/python -m eval.run_eval --filter zoning
PYTHONPATH=. .venv/bin/python -m eval.run_eval --full http://localhost:8001 --out eval/last.md

# Backend + frontend dev
docker compose up -d qdrant
.venv/bin/uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                              # :5173

# Smoke-test /chat
curl -N -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```
