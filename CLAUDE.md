# UrbanLayer — Chicago

Parcel feasibility engine for Chicago real-estate professionals, built on RAG over the municipal code plus 25+ city/county/federal data sources. Killer query: type "2400 N Milwaukee Ave" → the parcel's full Scorecard (zoning, overlays, incentives, tax projection, comps) in ~2 seconds, free and anonymous — then interrogate it via chat with cited municipal code, and buy the $25 Development Feasibility Report. Chat also answers parcel-less code-research and neighborhood questions (crime, 311, permits, demographics, transit) with interactive maps and clickable source citations.

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

python -m pytest backend/tests/ -q                # ~633 tests (577 unit + 56 integration)
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

## Workflow Rules

- **⚠️ Pushing to `main` IS deploying.** The production server (`178.105.184.66` / `/opt/urbanlayer`) **auto-pulls and rebuilds on every push to `main`** — a push goes live within minutes with no manual `docker compose up`. (Verified 2026-06-11: R7 commit `a9b7e6b` auto-shipped ~12 min after push.)
- **Deploy requires confirmation → so `git push` to `main` requires confirmation.** Because push = deploy, always ask before pushing production code to `main`, the same way you'd ask before a manual deploy. Commit freely on a branch; **get approval before pushing to `main`.** Docs-only/non-code changes can be pushed freely. The manual deploy command (below) is now a fallback; normally the push does it.
- **Commit freely; use clear, conventional commit messages.** Branch for code work that isn't ready to ship.
- **Verify a deploy via the live API**, not just the server's git HEAD — confirm the running image actually serves the change (e.g. `curl https://urbanlayerchicago.com/api/scorecard?address=...` and check the response). The server's git tree can advance ahead of (or independently of) what the running container serves.
- **Archive completed work** — when a feature ships, follow the archivation rules in `claude-context/README.md`. Strip completed items from active docs, create archive entry, keep active files lean.

## Context Docs

Deep context lives in `claude-context/`. Read `claude-context/README.md` for a manifest
of available docs — load only what's relevant to the current task. Don't read everything.
