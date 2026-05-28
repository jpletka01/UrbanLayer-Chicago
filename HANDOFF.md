# Project Handoff — Chicago City Intelligence

A snapshot of what's been built, the decisions behind it, and what should come next. Companion to `README.md` (user-facing setup) and `~/.claude/plans/velvet-gliding-salamander.md` (the original implementation plan).

---

## TL;DR

A RAG-powered chat interface for natural-language questions about Chicago. Combines live Chicago Data Portal (Socrata) data with semantic search over the entire Chicago Municipal Code. Single killer query: *"What's going on near 2400 N Milwaukee Ave?"* → a unified response covering crime, 311, building activity, business licenses, and applicable zoning, all from one prompt.

The entire vertical slice exists and compiles. The Municipal Code ingestion has been verified through a Title-17 dry-run, but the full embedding step (~10–20 min) hasn't been run end-to-end yet. The eval runner exists but hasn't been run against a real Anthropic key — no baseline numbers yet.

---

## Stack (Locked)

| Layer | Choice | Reasoning |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-first, OpenAPI for free, easy SSE |
| LLM | Anthropic Claude **Sonnet 4.6** (`claude-sonnet-4-6`) for both router and synthesizer | Latest non-Opus model, better tool-use, structured output reliability |
| Vector DB | **Qdrant** (Docker, self-hosted) | Free, fast, good metadata filtering, payload search supports cross-ref lookup |
| Embeddings | **`BAAI/bge-small-en-v1.5`** via sentence-transformers (local, 384-dim, 512-token context) | Originally chose MiniLM-L6 (256-token context, too small for legal sections); upgraded during Title-17 work. Same dim → Qdrant config unchanged |
| Streaming | **SSE** (`text/event-stream`) | Synthesizer is the slow part (~3–8s); streaming TTFT is much better UX |
| Chat memory | **Multi-turn from day one**, history in client `localStorage`, server is stateless | Simplest persistence model, scales |
| Geocoding | **Census Geocoder** (free, no key) + shapely point-in-polygon against cached community-area polygons | No rate limit, no API key, deterministic |
| Frontend | **React + TypeScript + Vite + Tailwind v3** | Type-safe contract with FastAPI Pydantic via OpenAPI |
| Doc ingest | **Parse local `chicago-il-codes.html`** (American Legal Publishing export, ~100MB) | Originally tried scraping Municode (deleted); the local HTML export is much more reliable |

Decisions that came up later and were resolved:
- The HTML file has a malformed div somewhere in Title 18 that causes lxml/html.parser to silently nest the trailing ~8MB (the republished Titles 16/17 "Zoning + Land Use Ordinance" volume) inside an earlier element. Worked around by splitting the file at the republication banner string and parsing each half separately. Without this, 250 republished sections and 1 net-new section were missing.
- Sentence-transformers import is lazy inside `vector_search._model()` so FastAPI can boot without the heavy torch dependency installed.

---

## What's Done

Everything below is in the repo, tested locally to the level noted.

### Backend (`backend/`)
- `main.py` — FastAPI app, `/chat` SSE endpoint with phase timing events
- `router.py` — Claude-based router producing strict `RetrievalPlan` JSON; system prompt embeds the 77 community-area names + 30+ neighborhood aliases
- `synthesizer.py` — streaming Claude synthesis call
- `assembler.py` — pure context-merging function with caps (top-5 crime types, top-15 311 types, top-5 chunks), `Open - Dup` dedup, auto data-lag note
- `models.py` — Pydantic types: `RetrievalPlan`, `ContextObject`, `ChatChunk` (with `t_ms` timing), `Message`, `ChatRequest`
- `config.py` — env via pydantic-settings (Anthropic key, Socrata token, Qdrant URL, model/dataset IDs)
- `retrieval/`:
  - `socrata.py` — shared async client with retry/backoff, `X-App-Token`, `$limit` guard
  - `crime.py` — `ijzp-q8t2` (neighborhood-aggregated + block-level)
  - `three11.py` — `v6vf-nfxy` (open requests + response times, `Open - Dup` filtered)
  - `buildings.py` — `ydr8-5enu` permits + `22u3-xenr` violations
  - `business.py` — `uupf-x98q` active licenses
  - `vector_search.py` — Qdrant semantic + payload-filter cross-ref expansion, lazy embedder
  - `geo.py` — 77 community areas + alias table + Census Geocoder + shapely
- `tests/test_assembler.py` — **10 unit tests, all passing**, covering caps/dedup/disclaimer/data-lag-note

### Ingestion (`ingestion/`)
- `parse_chicago_code.py` — HTML parser with split-at-republication strategy, state machine for Title→Chapter→Article→Subarticle→Part, colspan/rowspan-aware table extraction with composite multi-row headers
- `chunk.py` — section-aware chunking with hierarchical header re-duplication, table flattening to `Row N: header=value`, sub-section splits inside tables at category boundaries (`A. Household Living`, `PUBLIC AND CIVIC`)
- `embed_and_store.py` — sentence-transformers + Qdrant upsert to two collections (`chicago_municipal_code`, `chicago_zoning` for Title 17 filter-free)
- `load_community_areas.py` — fetches and caches community-area polygons from Socrata `igwz-8jzy` as GeoJSON

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

### Benchmarks (`eval/` + parser flag + SSE timing)
- **Parser stats** — `python -m ingestion.parse_chicago_code --stats` prints per-title section/table/xref/definition/legislative-history counts, plus dedup-skipped count. Currently: **8,615 sections** across all titles (17 active titles; 12 is reserved; 250 dedupes from the republished Titles 16/17 at file tail). Title 17 has 147 sections, 89 tables, 144 with legislative history.
- **Per-phase latency** — every SSE event carries `t_ms` (wall-clock ms since `/chat` request received). Sidebar renders Router / Retrieval / Synthesis-TTFT / Total live. Eval runner aggregates p50/p95.
- **Query test set** — `eval/queries.json` has **26 representative queries** spanning neighborhood overviews, address lookups, crime trends, 311, zoning legal questions, dimensional standards, parking ratios, sign regs, definitions, alias resolution, clarification handling, compound queries.
- **Eval runner** — `eval/run_eval.py` with two modes: `--router-only` (router only, ~30s, ~$0.05) and `--full <URL>` (full backend, captures retrieval + timings). Both emit stdout + optional markdown report.

---

## What's NOT Done

Honest gap list. Roughly in order of risk-to-the-project.

### 1. The pipeline hasn't been run end-to-end with real data
- Full parse of `chicago-il-codes.html`: takes ~60s, verified
- Full chunk: ~30s for all 8,615 sections, verified for Title 17 (146 sections → 968 chunks)
- **Full embed: NOT YET RUN.** With 8,615 sections × ~6 chunks/section ≈ 50,000 chunks at ~25ms/chunk on CPU ≈ **20 minutes**. First run also downloads ~150MB BGE model
- **No Qdrant collection populated yet.** Vector search returns empty. The synthesizer will work but with no code citations.
- **No eval baseline.** The `--router-only` and `--full` modes have never been run with a real Anthropic key.

### 2. Router prompt accuracy is unverified
- Router uses Sonnet 4.6 with a system prompt embedding the 77 community areas + 30 aliases. Logic looks reasonable but no real-world testing yet.
- Edge cases not yet probed: ambiguous locations (Lincoln Park = park or community area?), compound queries, multi-turn follow-ups, time-range parsing.
- Eval set targets all of these but hasn't been run.

### 3. Title 18 has 334 empty-body sections (out of 1,470)
- Almost certainly the Building Code chapters with table-only content (no prose). Worth investigating — the parser may need to treat tables-only sections specially, or the chunker may be producing chunks that are mostly header with no body, which would hurt retrieval quality.
- Visible in `parse_chicago_code --stats` output.

### 4. The Municipal Code is gitignored
- `chicago-il-codes.html` (~100MB) is not in version control (`.gitignore` line 17).
- Anyone cloning the repo needs to obtain it separately (presumably from American Legal Publishing or a similar source — the user provided it once).

### 5. Stretch goals never started (Phase I)
- **Leaflet map view** showing crime pins, 311 markers, zoning overlay for a queried neighborhood. Right side of the split-screen has space reserved for this.
- **Address autocomplete** (Census Geocoder debounced) for the chat input.
- **Multi-turn follow-up resolution** — the API supports `history` and frontend persists it, but the router prompt doesn't yet handle context-aware location like *"what about the next neighborhood over?"*

### 6. Deferred but probably worth doing
- **LLM-as-judge eval** — grade synthesis answers for citation accuracy + factuality + directness. ~$0.05 × 30 questions per run. Mentioned in benchmarks plan as Tier 4 (deferred).
- **Cost/token logging** — wrap the Anthropic client to record input/output tokens per request. Low effort, easy ongoing visibility. Mentioned as Tier 5.
- **Deployment** — currently local-only via `docker-compose up qdrant` + `uvicorn` + `npm run dev`. No production deployment story.
- **Postgres / server-side history** — currently the API is stateless and history lives in localStorage. Fine for a demo. Would need Postgres for multi-device sync.

### 7. Known fragile heuristics
- **Sub-header detection inside tables** uses a length cap (<80 chars) and same-value-across-most-of-row heuristic. Works for the residential use table (`"A. Household Living"`) but could miss tables with unusual sub-section conventions.
- **Multi-row header count** is inferred from how many consecutive rows in row 0 share the same value (proxy for rowspan carry-down). Works for the use table (3 header rows) but caps at 4 rows.
- **Cross-references** include Title-shaped (`"Title17"`) and Chapter-shaped (`"Ch.17-2"`) anchors as well as section IDs. `expand_cross_references` filters to section IDs only; future code could handle the chapter/title anchors differently.
- **The Anthropic key the user pasted in chat history was sensitive.** They were warned to rotate it. Confirm with them whether it's been rotated before any production use.

---

## Recommended Next Steps (Prioritized)

The order assumes you want the system actually working end-to-end before iterating on quality.

### Step 1 — Run the ingestion pipeline (1 hour, mostly waiting)
```bash
docker compose up -d qdrant
.venv/bin/python -m ingestion.load_community_areas      # ~5s
.venv/bin/python -m ingestion.parse_chicago_code        # ~60s, 8,615 sections to disk
.venv/bin/python -m ingestion.chunk                     # ~30s, chunks.jsonl
.venv/bin/python -m ingestion.embed_and_store           # ~20min, downloads BGE first run
```
Watch for: BGE download speed, Qdrant memory usage, any sections with parse errors. After this, `vector_search.semantic_search("coach house in RS-3")` should return real chunks.

### Step 2 — Establish a router baseline (5 min, ~$1)
```bash
PYTHONPATH=. .venv/bin/python -m eval.run_eval --out eval/baseline_router.md
```
Expect failures. The router prompt was written without ever being tested. Look for:
- Wrong community area resolution (aliases not matching)
- Missing `requires_disclaimer: true` on legal questions
- Wrong `intent` classification
- Missing sources (e.g. asking about businesses but not including `business_api`)

Iterate on `backend/router.py`'s system prompt until > 80% pass. Then commit the baseline.

### Step 3 — Run the full backend eval (15 min, ~$3)
```bash
.venv/bin/uvicorn backend.main:app &
PYTHONPATH=. .venv/bin/python -m eval.run_eval --full http://localhost:8000 --out eval/baseline_full.md
```
Verifies retrieval (do the right sections come back from Qdrant?) and records p50/p95 latency. The first time, expect to see Synthesis-TTFT dominate (~2–4s). If Router latency is > 1s, consider moving the router to Haiku 4.5 (`claude-haiku-4-5-20251001`).

### Step 4 — Investigate Title 18 empty-body sections
334 sections have no body text but no tables either. Either:
- The parser is dropping their content (bug)
- They're genuinely empty placeholders / "Reserved" markers (fine, but should be flagged in chunking and skipped)
- They're tables that the colspan-expansion logic over-classified as headers and ate all rows

Quick check: `cat ingestion/data/sections/18-*.json | jq 'select(.body_paragraphs|length==0 and (.tables|length)==0)' | head`.

### Step 5 — Stretch goal: address autocomplete
Easiest of Phase I. Use the Census Geocoder we already have. Debounce input by 300ms, render suggestions as a dropdown under the chat pill. Pre-fills the location so the router doesn't have to resolve it.

### Step 6 — Stretch goal: Leaflet map
Bigger lift. Right side of split-screen has a placeholder for it. Crime markers from `ContextObject.crime_last_90d` need backend support to surface lat/lon (currently aggregated, not per-incident). Worth deciding whether map should be its own retrieval path or just display already-fetched data.

### Step 7 — Stretch goal: multi-turn follow-up resolution
The API and storage are ready. What's missing: the router prompt needs to look at `history` and resolve referential locations ("the next neighborhood over"). Probably one-shot examples in the router system prompt + always passing the last user/assistant turn as additional context.

---

## How to Get Productive Quickly

If you're a fresh agent picking this up:

1. **Read in this order**: `README.md` (user setup) → `HANDOFF.md` (this file) → `~/.claude/plans/velvet-gliding-salamander.md` (original architectural rationale)
2. **Check current state**: `.venv/bin/python -m pytest backend/tests/ -q` (assembler tests should be 10/10), `cd frontend && npm run build` (should succeed), `python -m ingestion.parse_chicago_code --stats` (should print 8,615 total sections)
3. **Verify env**: `.env` should have `ANTHROPIC_API_KEY` set (rotated from the values posted in earlier chat history)
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
├── docker-compose.yml              # Qdrant
├── requirements.txt
├── .env.example
├── backend/
│   ├── main.py                     # FastAPI /chat (SSE w/ t_ms timing)
│   ├── router.py                   # Claude router
│   ├── synthesizer.py              # Claude streaming synth
│   ├── assembler.py                # Pure (pytest-covered)
│   ├── models.py
│   ├── config.py
│   ├── retrieval/                  # socrata.py + per-dataset wrappers + geo.py + vector_search.py
│   └── tests/test_assembler.py     # 10 tests
├── ingestion/
│   ├── parse_chicago_code.py       # HTML → sections JSON, --stats flag
│   ├── chunk.py                    # sections → chunks.jsonl
│   ├── embed_and_store.py          # chunks → Qdrant
│   └── load_community_areas.py     # CA polygons → GeoJSON
├── eval/
│   ├── queries.json                # 26 test queries
│   └── run_eval.py                 # --router-only | --full <URL>
└── frontend/
    ├── src/components/             # Hero, ChatInput, MessageBubble, Sidebar, etc.
    ├── src/lib/                    # api (SSE), history (localStorage), types
    └── src/App.tsx                 # State machine
```

## Quick Reference — Useful Commands

```bash
# Tests + builds
.venv/bin/python -m pytest backend/tests/ -q
cd frontend && npm run build

# Parser sanity check (no JSON output)
.venv/bin/python -m ingestion.parse_chicago_code --stats

# Full ingestion pipeline
.venv/bin/python -m ingestion.parse_chicago_code
.venv/bin/python -m ingestion.chunk
.venv/bin/python -m ingestion.embed_and_store

# Eval
PYTHONPATH=. .venv/bin/python -m eval.run_eval --filter zoning
PYTHONPATH=. .venv/bin/python -m eval.run_eval --full http://localhost:8000 --out eval/last.md

# Backend + frontend dev
.venv/bin/uvicorn backend.main:app --reload     # :8000
cd frontend && npm run dev                       # :5173

# Smoke-test /chat
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```
