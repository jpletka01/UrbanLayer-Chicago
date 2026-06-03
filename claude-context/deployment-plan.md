# Production Deployment Plan: urbanlayerchicago.com

## Context

UrbanLayer is a Docker Compose app (backend + Qdrant + nginx/frontend) being deployed as a live public website at `urbanlayerchicago.com`. The backend is resource-heavy (~2-3GB RAM for PyTorch embedding + reranker models). The primary recurring cost is the Anthropic API (~$0.03-0.10 per query), making rate limiting and auth essential.

**Decisions**: Hetzner CX22 (~$10/mo), Google OAuth + self-rolled JWT sessions, public GitHub repo.

**Server**: `178.105.184.66` — Hetzner CX22, Nuremberg datacenter, Ubuntu 22.04, provisioned 2026-06-03.

---

## Completed Phases

### Phase 1: Hosting & Infrastructure — DONE (2026-06-03)

**Specs**: 2 vCPU (x86), 4GB RAM, 40GB SSD, 20TB egress — ~$10/month

- Provisioned CX22 (Ubuntu 22.04), Nuremberg datacenter
- Hardened: SSH key-only login, disabled password auth, `ufw allow 22,80,443`
- Docker 29.5.2, Compose 5.1.4 installed
- 2GB swap created, persisted in `/etc/fstab`
- App not yet deployed to server (repo not cloned, `.env` not created)

### Phase 3: Production Nginx — DONE (2026-06-03)

- `frontend/nginx.prod.conf` — HTTPS redirect, SSL termination (Cloudflare Origin Cert), security headers (HSTS, CSP for Mapbox, X-Frame-Options DENY, X-Content-Type-Options), gzip compression
- `docker-compose.prod.yml` — production compose override (port 443, SSL volume mount, `NGINX_CONF` build arg)
- `frontend/Dockerfile` — `NGINX_CONF` build arg (defaults to `nginx.conf` for dev), exposes port 443

### Phase 5: Authentication — DONE (2026-06-03)

Google OAuth2 Authorization Code flow + self-rolled JWT sessions. Auth is opt-in — when `GOOGLE_CLIENT_ID` is not set in `.env`, the entire auth system is disabled and all requests are treated as admin user. This means local dev works with zero auth config.

**Backend (`backend/auth.py`)**:
- Google OAuth2 flow (3 HTTP calls: redirect → token exchange → userinfo)
- JWT access tokens (HS256, 15min TTL) in httpOnly cookie
- Opaque refresh tokens (hashed SHA-256) stored in SQLite, path-scoped to `/api/auth`, 7-day TTL, rotation on each refresh
- CSRF protection: double-submit cookie pattern (JS-readable `csrf_token` cookie + `X-CSRF-Token` header)
- FastAPI dependencies: `get_current_user()`, `require_auth()`, `require_admin()`, `verify_csrf()`
- 5 endpoints: `GET /api/auth/google`, `GET /api/auth/google/callback`, `POST /api/auth/refresh`, `GET /api/auth/me`, `POST /api/auth/logout`

**Database (schema v4)**:
- `users` table: id (UUID), email (unique), name, picture_url, google_id (unique), tier (free/premium/admin), created_at, updated_at
- `refresh_tokens` table: id, user_id (FK), token_hash (unique), expires_at, revoked, created_at
- Added nullable `user_id` column to `request_logs` and `llm_calls`

**Frontend**:
- `useAuth.ts` hook — manages auth state, auto-checks `/api/auth/me` on mount, auto-attempts token refresh
- `AuthContext.tsx` — React context provider wrapping useAuth, available app-wide
- `AuthModal.tsx` — "Sign in with Google" modal with Google branding, shown when unauth user submits a message
- `UserMenu.tsx` — Google avatar dropdown in workspace header (shows name, email, sign-out)
- `ProtectedRoute.tsx` — Route guard for tier-based access (used for `/admin`)
- `api.ts` — all 23 fetch calls converted to `authFetch()` wrapper with `credentials: 'include'` + CSRF headers on mutations. Auth API functions added.
- `App.tsx` — auth gate on `sendMessage`, UserMenu in header, admin link only shown for admin tier
- `main.tsx` — wrapped in `<AuthProvider>`, `/admin` route protected by `<ProtectedRoute tier="admin">`

**Config settings added** (`backend/config.py`):
- `google_client_id`, `google_client_secret`, `jwt_secret` (all empty by default = auth disabled)
- `jwt_access_token_ttl` (900s), `jwt_refresh_token_ttl` (604800s)
- `auth_cookie_secure` (False for dev, True in production)
- `frontend_url` (for OAuth redirect after callback)

**Tests**: 29 tests in `backend/tests/test_auth.py` covering JWT utils, refresh tokens, user CRUD, dev mode bypass, CSRF, `/me` endpoint.

### Phase 6: Rate Limiting & Cost Control — DONE (2026-06-03)

**Backend (`backend/rate_limit.py`)**:
- In-memory sliding window counters keyed by `user_id` (or IP for anonymous)
- Tier limits: anonymous 3/day + 3/hr, free 25/day + 10/hr, premium 100/day + 30/hr, admin unlimited
- Daily API budget cap: sums today's `llm_calls` via `estimate_cost()`, rejects with 503 if over `DAILY_API_BUDGET_USD` env var (default $5)
- Applied to `/chat` endpoint only (in `main.py`)
- `clear_rate_limits()` function for tests; autouse fixture in `conftest.py`

### Phase 7: Security Hardening — DONE (2026-06-03)

- CORS: `allow_credentials=True` (required for cookies). Production origins set via `cors_origins` in `.env`.
- Input validation: `max_length=2000` on `ChatRequest.message`, `max_length=20` on `ChatRequest.history`
- Admin endpoints: all 8 `/api/admin/*` endpoints protected with `Depends(require_admin)`
- Frontend: `/admin` route wrapped in `<ProtectedRoute tier="admin">`

---

## Remaining Phases

### Phase 2: Domain & TLS — IN PROGRESS

**Status**: Cloudflare site added, but Universal SSL certificate still propagating (error: "This hostname is not covered by a certificate"). Namecheap nameservers may need to be pointed to Cloudflare.

**Remaining steps**:
1. Verify Namecheap nameservers are set to Cloudflare's assigned NS (not Namecheap BasicDNS)
2. Wait for Cloudflare Universal SSL to provision (can take up to 24h)
3. In Cloudflare, add DNS records:
   ```
   A     urbanlayerchicago.com    → 178.105.184.66         (Proxied)
   CNAME www                      → urbanlayerchicago.com  (Proxied)
   ```
4. Set SSL/TLS mode to "Full (Strict)" in Cloudflare
5. Generate Origin Certificate from Cloudflare dashboard (SSL/TLS → Origin Server → Create Certificate). Save as `origin.pem` + `origin-key.pem`
6. On server: `mkdir -p /etc/ssl/cloudflare && scp origin.pem origin-key.pem root@178.105.184.66:/etc/ssl/cloudflare/`

### Phase 1 (remaining): Deploy App to Server — DONE (2026-06-03)

- Repo cloned to `/opt/urbanlayer` on server (public GitHub repo: `jpletka01/UrbanLayer-Chicago`)
- `.env` created with Anthropic, Socrata, Mapbox, WalkScore, Census keys + `DAILY_API_BUDGET_USD=5.00`
- Auth keys left out (auth disabled = admin mode for all users)
- All 3 services running on HTTP (port 80): Qdrant (healthy), backend (healthy), frontend (nginx)
- Health check: `curl http://178.105.184.66/health` → `{"ok":true,"qdrant":true,"db":true}`
- Frontend accessible at `http://178.105.184.66`

**Issues resolved during deploy**:
- `community_areas.geojson` was gitignored — un-gitignored and committed (needed by Dockerfile for `geo.py`)
- `PyJWT` missing from `requirements.prod.txt` — added (backend crash-looped without it)
- 3 TypeScript errors in frontend — `BarChart.tsx` was untracked (committed), `InfoTooltip.tsx` useRef init fix, `SidebarPanel.tsx` unused variable fix

**To switch to HTTPS later**:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Phase 4: Qdrant Data Transfer — NOT STARTED

Transfer municipal code embeddings from local machine to server. One-time operation. **Without this, vector search (municipal code queries) returns no results.** All other data sources (Socrata APIs, ArcGIS, property domain, etc.) work without Qdrant data.

**Prerequisite**: Local Qdrant must be running (`docker compose up -d qdrant`).

```bash
# On local machine
curl -X POST http://localhost:6333/collections/chicago_municipal_code/snapshots
# Note the snapshot filename from the response

# Download snapshot
curl -o qdrant-snapshot.tar http://localhost:6333/collections/chicago_municipal_code/snapshots/<name>

# Upload to server
scp qdrant-snapshot.tar root@178.105.184.66:/tmp/

# On server — restore into Qdrant
docker cp /tmp/qdrant-snapshot.tar $(docker compose ps -q qdrant):/qdrant/snapshots/
curl -X PUT http://localhost:6333/collections/chicago_municipal_code/snapshots/recover \
  -H 'Content-Type: application/json' \
  -d '{"location": "file:///qdrant/snapshots/qdrant-snapshot.tar"}'
```

### Phase 8: CI/CD Pipeline — NOT STARTED

`.github/workflows/deploy.yml`:
- On every push/PR: `pytest backend/tests/ -q` + `cd frontend && npx tsc --noEmit`
- On push to `main`: build Docker images (linux/amd64), push to GHCR, SSH deploy to Hetzner, health check
- Docker layer caching for HuggingFace model layer (~1.5GB, rarely changes)

### Phase 9: Monitoring — NOT STARTED

- **Sentry** (free, 5K errors/mo): `sentry-sdk[fastapi]` backend + `@sentry/react` frontend
- **UptimeRobot** (free): HTTP check on `/health` every 5 minutes, email alerts

### Google Cloud OAuth Setup — NOT STARTED

Required before auth works in production:
1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Authorized redirect URI: `https://urbanlayerchicago.com/api/auth/google/callback`
4. For local testing, also add: `http://localhost:8001/api/auth/google/callback`
5. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to server `.env`
6. Generate JWT_SECRET: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

---

## Production .env Template

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
VITE_MAPBOX_TOKEN=pk.eyJ1...

# Optional data sources
SOCRATA_APP_TOKEN=...
WALKSCORE_API_KEY=...

# Auth (leave empty to disable auth — all users treated as admin)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
JWT_SECRET=
AUTH_COOKIE_SECURE=true
FRONTEND_URL=https://urbanlayerchicago.com

# Production CORS (JSON array string)
CORS_ORIGINS=["https://urbanlayerchicago.com","https://www.urbanlayerchicago.com"]

# Cost control
DAILY_API_BUDGET_USD=5.00
```

---

## Execution Summary

| Step | What | Status |
|------|------|--------|
| 1 | Provision Hetzner, Docker, harden | **Done** |
| 1b | Deploy app to server (HTTP) | **Done** — all 3 services running at `http://178.105.184.66` |
| 2 | DNS + TLS (Cloudflare) | **Not started** — Namecheap NS not yet pointed to Cloudflare |
| 3 | Production nginx.conf | **Done** |
| 4 | Transfer Qdrant snapshots | **Not started** — required for municipal code vector search |
| 5 | Google OAuth + JWT auth | **Done** — code complete, needs Google Cloud OAuth client + `.env` update on server |
| 6 | Rate limiting + budget cap | **Done** |
| 7 | Security hardening | **Done** |
| 8 | CI/CD pipeline | **Not started** |
| 9 | Monitoring (Sentry + UptimeRobot) | **Not started** |

## Verification Checklist (post-deploy)

1. `curl -I https://urbanlayerchicago.com` → 200 with HSTS + security headers
2. Chat without auth → 3 queries work, 4th returns 429
3. Google sign-in → chat works → UserMenu shows avatar → tokens refresh
4. Non-admin user → `/admin` redirects, `/api/admin/*` returns 403
5. Set `DAILY_API_BUDGET_USD=0.01` → budget cap after 1 query
6. Full chat query streams tokens correctly through Cloudflare → nginx → backend SSE
7. Vector search returns municipal code results (after Qdrant snapshot transfer)
8. Dev mode (no `GOOGLE_CLIENT_ID`): no auth UI, everything works as before
