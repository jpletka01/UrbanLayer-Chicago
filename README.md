# UrbanLayer — Chicago

Parcel feasibility engine for Chicago real-estate professionals. Type an address, get the
parcel's full **Property Profile** in ~2 seconds — free and anonymous — then interrogate it in
chat with cited municipal code.

**Live:** [urbanlayerchicago.com](https://urbanlayerchicago.com)

```
1601 N Milwaukee Ave  →  zoning (B3-2, FAR 2.2, 45–50 ft) · 7 overlays · TIF/Opportunity-Zone
                         status · tax history + class-aware effective rate · comparable sales ·
                         violations · environment · three scoped parcel maps
```

## What it does

- **Property Profile** (`/scorecard`) — the parcel dossier: zoning and bulk standards, overlays,
  incentives, taxes, comps, and a verdict band with one recommended next step. Free, no account.
- **Chat** — grounded follow-up questions about the parcel, plus parcel-less code research and
  neighborhood questions (crime, 311, permits, demographics, transit) with interactive maps and
  clickable source citations.
- **Development Feasibility Report** ($25) — a rendered PDF dossier for a single parcel.
- **Property Discovery** (`/discovery`) — a filter/search workbench over all 77 community areas
  (~949k parcels), with recipes, ranked results, map, and CSV export.

Answers are assembled from 25+ city/county/federal data sources plus RAG over the Chicago
Municipal Code. See [`claude-context/core/data-sources.md`](claude-context/core/data-sources.md)
for the full dataset reference.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11 + FastAPI, async-first |
| LLM | Claude Sonnet 4.6 (router + synthesizer), Haiku 4.5 (conversation synthesis, zoning extraction) |
| Vector DB | Qdrant v1.9.0 (Docker) |
| Embeddings | `BAAI/bge-base-en-v1.5` — 768-dim, local, no API key |
| Reranker | `BAAI/bge-reranker-v2-m3`, **off by default** (see Known Issues) |
| Frontend | React + TypeScript + Vite + Tailwind v3 |
| Map | Mapbox GL JS (dark-v11) + deck.gl |
| Persistence | SQLite via aiosqlite (WAL mode) |
| Streaming | SSE (`text/event-stream`) |
| Geocoding | Census Geocoder (free) + shapely point-in-polygon |

## Setup

```bash
# 1. Python env
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Frontend deps
cd frontend && npm install && cd ..

# 3. Env vars
cp .env.example .env                  # ANTHROPIC_API_KEY required; others optional
cp frontend/.env.example frontend/.env  # VITE_MAPBOX_TOKEN for maps

# 4. Start Qdrant
docker compose up -d qdrant
```

`SOCRATA_APP_TOKEN` is optional but recommended (higher rate limits).
`WALKSCORE_API_KEY` and the Google OAuth / Stripe keys are only needed for the features that
use them; the app degrades gracefully without them.

## Ingest the Municipal Code

The code is parsed from a local HTML export — drop `chicago-il-codes.html` (American Legal
Publishing format) in the project root first. It is not committed.

```bash
# One-time: cache community-area polygons (~5s)
.venv/bin/python -m ingestion.load_community_areas

# Parse → chunk → diff → embed only what changed
.venv/bin/python -m ingestion.update

.venv/bin/python -m ingestion.update --dry-run   # show the diff, change nothing
.venv/bin/python -m ingestion.update --full      # full rebuild (recreates the collection)
.venv/bin/python -m ingestion.source_check       # has the source HTML changed since last ingest?
```

Current corpus: **9,487 sections → 16,576 chunks**, spanning Titles 1–18 including Title 14
(the Chicago Construction Codes, eleven lettered volumes: 14A/14B/14C/14E/14F/14G/14M/14N/14P/
14R/14X).

### How the chunker works

- **One chunk per section** when it fits in ~1,800 chars; longer sections split at paragraph
  boundaries.
- **The hierarchical header is duplicated** at the top of every chunk so it stands alone:
  ```
  CHICAGO MUNICIPAL CODE
  Title 17 — Chicago Zoning Ordinance
  Chapter 17-2 — Residential Districts
  § 17-2-0200 — Allowed uses
  ```
- **Tables get colspan/rowspan-aware extraction with composite headers**, so every
  use × district intersection is individually retrievable — "Can I put a coach house in RM-4.5?"
  returns the row directly.
- **Cross-references, prev/next adjacency, legislative history, effective dates, and
  definitions** are extracted into payload metadata.
- **Title 16/17 deduplication** — the source republishes those titles as a separate volume at
  the tail; the parser dedups by section ID (~250 skipped).

## Run

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8001   # backend
cd frontend && npm run dev                                # frontend :5173
```

## Tests

```bash
.venv/bin/python -m pytest backend/tests/ -q -m "not integration"   # 1,103 tests
.venv/bin/python -m pytest backend/tests/ -q                        # + 61 integration (hits live APIs)

cd frontend && npm run test         # vitest — 171 tests
cd frontend && npm run build        # ⚠️ the CI-parity gate: tsc -b + vite build
cd frontend && npm run test:mobile  # Playwright overflow audit, 8 routes × 5 phone profiles
```

`npm run build` is the gate CI enforces, not `tsc --noEmit` — `tsc -b` catches errors
(`noUnusedLocals`, etc.) that `--noEmit` misses.

## Evals & benchmarks

```bash
# Parser coverage — verifies the HTML → section parse hasn't regressed
.venv/bin/python -m ingestion.parse_chicago_code --stats

# Query test set (44 queries with expected router/retrieval behavior)
PYTHONPATH=. .venv/bin/python -m eval.run_eval --full http://localhost:8001 --judge

# Data-source coverage, and lot-field completeness across a fixed 100-address panel
.venv/bin/python -m eval.source_coverage --full http://localhost:8001
PYTHONPATH=. .venv/bin/python -m eval.lot_coverage --full http://localhost:8001
```

Every SSE event carries `t_ms` (ms since the request was received), so per-phase latency
(router / retrieval / synthesis-TTFT / total) is measurable live and recorded by the eval runner.

## How a request flows

**Property Profile** — `GET /api/scorecard?address=…`
1. Resolve address → PIN. Layered: Address Points, then Assessor Parcel Addresses, then a
   distance-ordered Parcel Universe fallback. A PIN from the fallback is only promoted to
   authoritative identity if it survives a reverse address round-trip; otherwise the response is
   marked `approximate` and the UI caveats the parcel data.
2. Domain orchestrators (`property/`, `regulatory/`, `incentives/`, `neighborhood/`) fan out via
   `asyncio.gather` with graceful degradation — one dead source never fails the page.
3. Zoning standards come from a precomputed cache with serve-time table authority applied.

**Chat** — `POST /chat` (SSE)
1. **Router** (Claude) parses the message into a `RetrievalPlan` — sources, location, intent,
   time range, disclaimer flag — streamed first so the client can render skeletons.
2. **Parallel retrieval** fires Socrata + Qdrant queries via `asyncio.gather`.
3. **Assembler** merges results into a capped, deduped `ContextObject`, streamed to the client.
4. **Synthesizer** (Claude, streaming) produces the answer with citations.

## Project layout

```
backend/
├── main.py               # FastAPI app + endpoints (chat SSE, scorecard, report, auth, payments)
├── router.py             # Claude router → retrieval plan
├── synthesizer.py        # Claude streaming synthesis
├── assembler.py          # Pure context-merging (pytest-covered)
├── report_builder.py     # $25 feasibility report pipeline
├── report_render.py      # PDF render, run in an isolated subprocess
├── zoning_cache.py       # Precomputed zoning extraction (keeps the reranker out of the report path)
├── auth.py · payments.py · conversation.py · db.py · analytics.py
├── discovery/            # Property Discovery index + query engine
└── retrieval/
    ├── socrata.py        # Shared async client with retry/backoff
    ├── vector_search.py  # Qdrant hybrid search
    ├── property/ · regulatory/ · incentives/ · neighborhood/   # domain orchestrators
    └── crime.py · three11.py · buildings.py · zoning.py · …
ingestion/
├── update.py             # Unified CLI: parse → chunk → diff → incremental embed
├── parse_chicago_code.py # HTML → per-section JSON
├── chunk.py · embed_and_store.py · manifest.py · source_check.py
frontend/src/
├── App.tsx               # State machine
├── components/ · discovery/ · contexts/ · lib/ · locales/       # (EN/ES)
eval/                     # run_eval, source_coverage, lot_coverage, retrieval_benchmark
```

## Deployment

Pushing to `main` **is** deploying — CI (`ci.yml`) runs the test job, then SSHes to the
production box and rebuilds. A failing test job silently skips the deploy, so prod keeps serving
the old image; verify a deploy against the live API and the served asset hash, not the server's
git HEAD.

Note that Qdrant lives in a persisted named volume: a code deploy does **not** re-ingest the
municipal code.

## Docs

Deep context lives in [`claude-context/`](claude-context/) — start with its `README.md`, which is
a file-by-file manifest. [`core/known-issues.md`](claude-context/core/known-issues.md) is the
first thing to read before debugging anything.
