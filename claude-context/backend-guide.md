# Backend Guide — UrbanLayer

## Router (`router.py`)

Produces a `RetrievalPlan` JSON with: `sources` (list of SourceTags), `location` (raw + resolved lat/lon/community_area), `intent`, `time_range_days`, `requires_disclaimer`, `search_query`, `workflow_hint`, `clarification`.

Router system prompt embeds all 77 community area names + 30+ neighborhood aliases. Includes search query guidance for zoning-specific terminology (e.g., "search home occupation rules, not bakery") and non-zoning topics.

If no location and query requires one: `intent = "clarification_needed"`, emits clarification text.

**Source tags**: `crime_api`, `311_api`, `permits_api`, `violations_api`, `business_api`, `vector_search`, `property_domain`, `regulatory_domain`, `incentives_domain`, `neighborhood_domain`.

**Incentives routing**: `incentives_domain` works at two levels — address queries (lat/lon → point-in-polygon TIF check + EZ + OZ) and neighborhood queries (community area → list all TIF districts via `comm_area` field matching). The router prompt allows both. `main.py` dispatches to the appropriate path based on whether lat/lon or only CA is available.

## Context Assembly (`assembler.py`)

Merges raw API results into a `ContextObject` with configurable caps (from `config.py`): `top_crime_types`, `top_311_types`, `top_chunks`, etc.

Key behaviors:
- `Open - Dup` dedup on 311 data before aggregating.
- Auto data-lag note for crime (7-day lag).
- Permits, violations, and business use grouped aggregation data (never capped). Crime and 311 use grouped counts with capped detection as a safety net.
- `partial_failures` field tracks which domain orchestrators returned errors (graceful degradation).

## Synthesis (`synthesizer.py`)

Streaming Claude call with structured system prompt rules (26 rules total):
- `[N]` citation markers render as `§ section` pills in frontend.
- `[data:crime]`, `[data:311]`, etc. render as colored data pills.
- Surface data freshness (7-day crime lag).
- Pre-scan instruction + rule 4a: check each summary's `capped` field, say "at least N" when capped.
- Legal disclaimer when `requires_disclaimer: true`.
- Weave MoM trends naturally (analytics formatted as text, not JSON).
- State zoning classification as definitive fact. Link to official Zoning Map Web.
- Explicit "When X data is present" rules for all data sources: property (12), regulatory (10), incentives (13), demographics (14/14a), transit (15), tax (17), Walk Score (18), crime (19), 311 (20), permits (21), violations (22 — "always include"), business (23).
- Use `.total` fields for authoritative counts, not trend data sums.

## Conversation (`conversation.py`)

Multi-turn context synthesis using Haiku. Improves follow-up detection for context references ("their", "it", "what about"), clarification answers.

**Deterministic neighborhood switching**: regex-based pre-check for "what about X?" / "compare to Y" patterns. If detected, substitutes the new neighborhood into the original question structure without LLM synthesis. Falls back to Haiku for ambiguous cases.

## Authentication (`auth.py`)

Google OAuth2 Authorization Code flow + self-rolled JWT sessions. Auth is opt-in — when `GOOGLE_CLIENT_ID` is not set, all requests are treated as admin (local dev works without OAuth).

**Token strategy**: httpOnly `access_token` cookie (JWT, 15min TTL), httpOnly `refresh_token` cookie (opaque, 7d, path-scoped to `/api/auth`), JS-readable `csrf_token` cookie (double-submit CSRF pattern).

**Endpoints**: `GET /api/auth/google` (redirect to Google), `GET /api/auth/google/callback` (exchange code, set cookies, redirect), `POST /api/auth/refresh` (rotate tokens), `GET /api/auth/me` (current user status), `POST /api/auth/logout`.

**FastAPI dependencies**: `get_current_user()` (returns user dict or None), `require_auth()` (401 if not auth'd), `require_admin()` (403 if not admin tier). All admin endpoints use `Depends(require_admin)`.

**User tiers**: `free` (default on sign-up), `premium` (future), `admin` (manual DB flag).

**Config settings**: `google_client_id`, `google_client_secret`, `jwt_secret`, `jwt_access_token_ttl`, `jwt_refresh_token_ttl`, `auth_cookie_secure`, `frontend_url`.

## Rate Limiting (`rate_limit.py`)

In-memory sliding window counters keyed by user_id (or IP for anonymous). Applied to `/chat` endpoint only.

**Tier limits**: anonymous 3/day + 3/hour, free 25/day + 10/hour, premium 100/day + 30/hour, admin unlimited.

**Daily budget cap**: sums today's `llm_calls` via `estimate_cost()`, rejects if over `DAILY_API_BUDGET_USD` env var (default $5).

## Persistence (`db.py`)

SQLite via aiosqlite, WAL mode, singleton connection, schema versioning.

**Tables:**
- `conversations` — id, title, created_at, updated_at
- `messages` — with `context_json`, `plan_json`, `map_data_json` blob columns (written once, read whole)
- `uploads` — file metadata for Claude Vision
- `llm_calls` — per-call token/cost/latency logging (router, synthesizer, conversation phases). Has nullable `user_id` column.
- `request_logs` — per-chat-turn summary (intent, location, sources, duration). Has nullable `user_id` column.
- `users` — id, email, name, picture_url, google_id, tier. Google OAuth user records.
- `refresh_tokens` — user_id, token_hash, expires_at, revoked. Refresh token rotation tracking.
- `schema_version` — migration tracking (currently v4)

**Conversation API** (7 CRUD endpoints): list, create, get (full with messages), delete (CASCADE), append messages, update map data, bulk import.

**Admin API** (8 endpoints, all protected by `require_admin`): cache stats, overview (tokens/cost/errors by model/phase), timeseries (bucketed for charts), latency (p50/p90/p99), conversations, paginated request log, benchmark results, judge results.

**LLM tracking**: `tracked_create()` / `tracked_stream()` wrappers capture token usage from `response.usage` or `stream.get_final_message()`. Each chat turn gets a UUID `request_group` linking its 1-3 LLM calls. Cost estimation uses per-model pricing. Logging is non-fatal.

## Caching (`retrieval/cache.py`)

`TTLCache` utility used by all external query modules. 17 caches across the codebase.

Cache key patterns:
- Spatial: `f"{source}:{round(lat,5)}:{round(lon,5)}"`
- PIN-based: `f"{source}:{pin14}"`
- Tract-based: `f"{source}:{tract_fips}"`

Startup preloading: TIF boundaries, Enterprise Zone boundaries, OZ tract list, GTFS stations, ACS demographics, community area polygons.

Cache hit/miss stats available via `/api/admin/cache-stats` (if implemented).

## Docker

Multi-stage Dockerfile (`backend/Dockerfile`): builder installs CPU-only PyTorch + deps + pre-downloads HF models; runtime stage copies packages, models, backend code, and two ingestion data files (`community_areas.geojson`, `transit_stations.json`). Runs as non-root `app` user.

`docker-compose.yml` runs Qdrant (health-checked via `/dev/tcp`), backend (health-checked via `/health`, 30s start period for model loading), and frontend (nginx reverse proxy, waits for healthy backend). `backend_data` named volume persists SQLite DBs and uploads.

`docker-compose.override.yml` (auto-loaded in dev): mounts local `./backend` and `./ingestion/data` for hot-reload, exposes port 8001 directly.

`docker-compose.prod.yml`: production override — builds frontend with `nginx.prod.conf` (HTTPS, security headers, gzip), exposes ports 80+443, mounts Cloudflare Origin Certificate from `/etc/ssl/cloudflare`.

```bash
docker compose up -d                              # dev (hot-reload, no frontend)
docker compose -f docker-compose.yml up           # production (all 3 services, HTTP only)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d  # production with HTTPS
docker compose build backend                      # rebuild after dep changes
# Optional: seed ptaxsim for tax estimates (9.4GB)
docker compose cp ./backend/data/ptaxsim.db backend:/app/backend/data/
```

## Production Server

Hetzner CX22 at `178.105.184.66` (Nuremberg datacenter). Ubuntu 22.04, 2 vCPU, 4GB RAM, 40GB SSD, 2GB swap.

**SSH access**: `ssh -i ~/.ssh/id_ed25519 root@178.105.184.66` (key has passphrase — run `ssh-add ~/.ssh/id_ed25519` first).

**Server maintenance commands**:
```bash
# Deploy latest (from server)
cd /opt/urbanlayer && git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# View logs
docker compose logs -f backend                    # backend logs
docker compose logs -f frontend                   # nginx logs

# Restart a single service
docker compose restart backend

# Check resource usage
docker stats --no-stream
free -h

# Qdrant snapshot backup
curl -X POST http://localhost:6333/collections/chicago_municipal_code/snapshots
```

**Installed software**: Docker 29.5.2, Docker Compose 5.1.4. Firewall (ufw): ports 22, 80, 443 open. SSH password auth disabled.

## Testing

~340 unit + integration tests. Mock external APIs in unit tests. Real-API tests marked `@pytest.mark.integration`.

Key test patterns:
- `conftest.py` has autouse fixture that clears all TTLCaches between tests.
- Socrata mocks: `httpx` response fixtures.
- ArcGIS mocks: JSON response fixtures matching real API shape.
- Domain orchestrator tests: mock individual sub-modules, verify parallel execution + graceful degradation.

## Evaluation & Benchmarks

Three eval tools in `eval/`:

| Tool | Command | What it tests |
|------|---------|---------------|
| Router eval | `python -m eval.run_eval` | Source tag routing, intent, location resolution (39 queries) |
| Full eval + judge | `python -m eval.run_eval --full URL --judge` | End-to-end retrieval + LLM-as-judge synthesis grading (4 dimensions) |
| **Source coverage** | `python -m eval.source_coverage --full URL` | Per-sub-source data presence in context AND synthesis (24 queries, 36 checks across 24 sub-sources) |

Source coverage benchmark produces a coverage matrix with four statuses per sub-source: COVERED, SYNTHESIS_GAP (data in context but not mentioned), RETRIEVAL_GAP (data not fetched), HALLUCINATION (mentioned but not in context). Also tracks API cap hits and whether the synthesis correctly hedges with "at least" phrasing. Results written to `eval/coverage_results.json` and optionally `--out coverage_report.md`.
