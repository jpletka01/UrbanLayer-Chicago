# UrbanLayer — Chicago

RAG-powered urban intelligence platform for Chicago. Natural-language questions about crime, 311, permits, zoning, property, regulatory overlays, incentives, demographics, transit. Killer query: "What's going on near 2400 N Milwaukee Ave?" — returns a unified response with interactive map, analytics, and clickable source citations.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11 + FastAPI, async-first |
| LLM | Claude Sonnet 4.6 (router + synthesizer), Haiku 4.5 (conversation synthesis) |
| Vector DB | Qdrant v1.9.0 (Docker), BAAI/bge-base-en-v1.5 embeddings (768-dim, local) |
| Reranker | bge-reranker-v2-m3, 20% weight blended with dense+keyword scores |
| Frontend | React + TypeScript + Vite + Tailwind v3 |
| Map | Mapbox GL JS (dark-v11) + deck.gl |
| Persistence | SQLite via aiosqlite (WAL mode) |
| Streaming | SSE (text/event-stream) |
| Geocoding | Census Geocoder (free) + shapely point-in-polygon |

## Common Commands

```bash
docker compose up -d qdrant
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                        # :5173

# Restart servers (kill existing, then start fresh)
kill $(lsof -ti:8001) 2>/dev/null; uvicorn backend.main:app --reload --port 8001
kill $(lsof -ti:5173) 2>/dev/null; cd frontend && npm run dev

python -m pytest backend/tests/ -q                # ~444 tests
cd frontend && npx tsc --noEmit                   # type check
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --judge
python -m eval.source_coverage --full http://localhost:8001  # data source coverage benchmark

# Docker (local)
docker compose up -d                              # dev (backend + qdrant, hot-reload)
docker compose -f docker-compose.yml up           # production (all 3 services)
docker compose build backend                      # rebuild after dep changes

# Production server (178.105.184.66) — live at https://urbanlayerchicago.com
ssh-add ~/.ssh/id_ed25519                         # load key (has passphrase)
ssh root@178.105.184.66                           # SSH into server
# On server: cd /opt/urbanlayer
git fetch origin && git merge origin/main         # pull latest code
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Key Conventions

- Backend port 8001, frontend dev port 5173.
- All Socrata modules (crime, 311, permits, violations, business, vacant, food_inspections, grant_programs, aro_housing) use shared `socrata_get()` with retry/backoff from `retrieval/socrata.py`.
- All ArcGIS modules follow the same spatial query pattern as `zoning.py`.
- Domain orchestrators (`property/`, `regulatory/`, `incentives/`, `neighborhood/`) run sub-queries in parallel via `asyncio.gather` with graceful degradation.
- TTLCache used for all external API queries. Clear caches between tests via autouse fixture in `conftest.py`.
- Frontend state: `useChat` hook owns SSE consumption. `App.tsx` is the state machine. Per-message context architecture (each assistant message stores its own context/plan/mapData).
- Tests: mock external APIs, mark real-API tests with `@pytest.mark.integration`.
- Env vars: `.env` (ANTHROPIC_API_KEY, SOCRATA_APP_TOKEN, WALKSCORE_API_KEY), `frontend/.env` (VITE_MAPBOX_TOKEN).

## Known Issues

- **Cook County GIS parcel lookup intermittent** — ArcGIS spatial index broken, queries can timeout 60s+. Socrata Parcel Universe (`pabr-t5kh`) auto-fallback implemented in `parcels.py` — resolves PIN via bounding-box query, no polygon geometry. Diagnostic test `test_parcel_gis_diagnostic` fails loudly when GIS is down.
- Demographics median values are estimated from bracket distributions, not pre-computed.
- Violation categories are homegrown keyword-based bucketing (16 custom categories from free-text descriptions).

## Keeping Docs Current

After completing work, update the relevant `claude-context/` files and subdirectory CLAUDE.md files to reflect what changed — new modules, modified schemas, changed patterns, new known issues, etc. If you added or renamed backend modules, update `backend/CLAUDE.md`. If you changed frontend components or design tokens, update `frontend/CLAUDE.md`. If you added data sources or API integrations, update `claude-context/data-sources.md`. Keep these docs accurate so the next conversation starts with a correct picture of the codebase.

## Context Docs

Read from `claude-context/` on demand when you need deeper information:

- `architecture.md` — RAG pipeline, retrieval flow, domain orchestrators, key design decisions
- `data-sources.md` — All datasets, APIs, GIS layers, endpoint reference
- `backend-guide.md` — Backend modules, router/synthesizer/assembler patterns, persistence, caching
- `frontend-guide.md` — Components, design tokens, state management, layout, map system
- `known-issues.md` — Bugs, fragile heuristics, synthesis gaps, gotchas, deferred work
- `expansion-roadmap.md` — Completed expansion phases + remaining Tier 3 opportunities
- `conversations.md` — Conversation persistence architecture, auth integration, known production issue + fix plan
