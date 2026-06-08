# Production Deployment

**Completed**: 2026-06-05
**Status**: Shipped to production

## What Was Built
Full production deployment — Hetzner server provisioning, Docker Compose deployment, Cloudflare DNS/TLS, Google OAuth, rate limiting, CI/CD pipeline, Sentry + UptimeRobot monitoring. Live at `https://urbanlayerchicago.com` on Hetzner CX32 (8GB RAM).

## Implementation Details

### Context

UrbanLayer is a Docker Compose app (backend + Qdrant + nginx/frontend) deployed as a live public website at `urbanlayerchicago.com`. The backend is resource-heavy (~2-3GB RAM for PyTorch embedding + reranker models). The primary recurring cost is the Anthropic API (~$0.03-0.10 per query), making rate limiting and auth essential.

### Phase 1: Hosting & Infrastructure (2026-06-03)

**Specs**: 2 vCPU (x86), 4GB RAM, 40GB SSD, 20TB egress — ~$10/month

- Provisioned CX22 (Ubuntu 22.04), Nuremberg datacenter
- Hardened: SSH key-only login, disabled password auth, `ufw allow 22,80,443`
- Docker 29.5.2, Compose 5.1.4 installed
- 2GB swap created, persisted in `/etc/fstab`

### Phase 1b: Deploy App to Server (2026-06-03)

- Repo cloned to `/opt/urbanlayer` on server (public GitHub repo: `jpletka01/UrbanLayer-Chicago`)
- `.env` created with Anthropic, Socrata, Mapbox, WalkScore, Census keys + `DAILY_API_BUDGET_USD=5.00`
- Auth keys left out (auth disabled = admin mode for all users)
- All 3 services now running on HTTPS (ports 80+443) via production compose overlay
- Health check: `curl https://urbanlayerchicago.com/health` → `{"ok":true,"qdrant":true,"db":true}`
- Frontend accessible at `https://urbanlayerchicago.com`

**Issues resolved during deploy**:
- `community_areas.geojson` was gitignored — un-gitignored and committed (needed by Dockerfile for `geo.py`)
- `PyJWT` missing from `requirements.prod.txt` — added (backend crash-looped without it)
- 3 TypeScript errors in frontend — `BarChart.tsx` was untracked (committed), `InfoTooltip.tsx` useRef init fix, `SidebarPanel.tsx` unused variable fix

**Server deploy command** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Phase 2: Domain & TLS (2026-06-03)

- Namecheap nameservers pointed to Cloudflare (`janet.ns.cloudflare.com`, `rajeev.ns.cloudflare.com`)
- Cloudflare DNS: A record `urbanlayerchicago.com` → `178.105.184.66` (Proxied), CNAME `www` → `urbanlayerchicago.com` (Proxied)
- SSL/TLS mode: Full (Strict)
- Origin Certificate (RSA 2048, expires 2041) installed at `/etc/ssl/cloudflare/` on server
- Production compose overlay deployed: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- Server `.env` updated: `CORS_ORIGINS`, `AUTH_COOKIE_SECURE=true`, `FRONTEND_URL=https://urbanlayerchicago.com`
- nginx `add_header` gotcha fixed: security headers repeated in child location blocks that override parent context
- SSE proxy directives added: `proxy_http_version 1.1` + `Connection ''` for Cloudflare streaming reliability

**Verified**:
- `curl -I https://urbanlayerchicago.com` → 200 with all 6 security headers (HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, CSP)
- `http://` → 301 redirect to `https://`
- `/health` → `{"ok":true,"qdrant":true,"db":true}`
- SSE streaming works through Cloudflare (full chat query with plan/context/tokens)

### Phase 3: Production Nginx (2026-06-03)

- `frontend/nginx.prod.conf` — HTTPS redirect, SSL termination (Cloudflare Origin Cert), security headers (HSTS, CSP for Mapbox, X-Frame-Options DENY, X-Content-Type-Options), gzip compression
- `docker-compose.prod.yml` — production compose override (port 443, SSL volume mount, `NGINX_CONF` build arg)
- `frontend/Dockerfile` — `NGINX_CONF` build arg (defaults to `nginx.conf` for dev), exposes port 443

### Phase 4: Qdrant Data Transfer (2026-06-03)

14,535 vectors snapshot-transferred from local to server. Municipal code vector search operational.

### Phase 5: Authentication (2026-06-03)

Google OAuth2 Authorization Code flow + self-rolled JWT sessions. Auth is opt-in — when `GOOGLE_CLIENT_ID` is not set in `.env`, the entire auth system is disabled and all requests are treated as admin user. Local dev works with zero auth config.

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

### Phase 6: Rate Limiting & Cost Control (2026-06-03)

**Backend (`backend/rate_limit.py`)**:
- In-memory sliding window counters keyed by `user_id` (or IP for anonymous)
- Tier limits: anonymous 3/day + 3/hr, free 25/day + 10/hr, premium 100/day + 30/hr, admin unlimited
- Daily API budget cap: sums today's `llm_calls` via `estimate_cost()`, rejects with 503 if over `DAILY_API_BUDGET_USD` env var (default $5)
- Applied to `/chat` endpoint only (in `main.py`)
- `clear_rate_limits()` function for tests; autouse fixture in `conftest.py`

### Phase 7: Security Hardening (2026-06-03)

- CORS: `allow_credentials=True` (required for cookies). Production origins set via `cors_origins` in `.env`.
- Input validation: `max_length=2000` on `ChatRequest.message`, `max_length=20` on `ChatRequest.history`
- Admin endpoints: all 8 `/api/admin/*` endpoints protected with `Depends(require_admin)`
- Frontend: `/admin` route wrapped in `<ProtectedRoute tier="admin">`

### Phase 8: CI/CD Pipeline (2026-06-03)

`.github/workflows/ci.yml`: pytest + tsc on PRs, SSH deploy on merge to main. Requires `SERVER_SSH_KEY` + `SERVER_HOST` GitHub repo secrets for deploy job.

### Phase 9: Monitoring (2026-06-03)

- **UptimeRobot**: Configured for `/health` checks
- **Sentry**: Active — backend (`sentry-sdk[fastapi]`) and frontend (`@sentry/react`) reporting to EU region (`ingest.de.sentry.io`). DSN values in server `.env`.

### Google Cloud OAuth Setup (2026-06-03)

OAuth client configured in Google Cloud Console. Credentials in server `.env`. Auth active — anonymous 3/day, free tier 25/day, admin unlimited.

### Execution Summary

| Step | What | Status |
|------|------|--------|
| 1 | Provision Hetzner, Docker, harden | **Done** |
| 1b | Deploy app to server | **Done** — all 3 services running at `https://urbanlayerchicago.com` |
| 2 | DNS + TLS (Cloudflare) | **Done** — Full (Strict) + Origin Certificate, security headers verified |
| 3 | Production nginx.conf | **Done** |
| 4 | Transfer Qdrant snapshots | **Done** — 14,535 vectors transferred and verified |
| 5 | Google OAuth + JWT auth | **Done** — Google Cloud OAuth client configured, credentials in server `.env`, HTTPS callback URL fix deployed |
| 6 | Rate limiting + budget cap | **Done** |
| 7 | Security hardening | **Done** |
| 8 | CI/CD pipeline | **Done** — `.github/workflows/ci.yml`: pytest + tsc on PR, SSH deploy on merge. Secrets: `SERVER_SSH_KEY` (passphrase-free deploy key, updated 2026-06-05), `SERVER_HOST`, `ANTHROPIC_API_KEY`. Deploy key pending verification on next push to main |
| 9 | Monitoring (Sentry + UptimeRobot) | **Done** — UptimeRobot configured, Sentry active (EU region, DSN values in server `.env`) |

### Production .env Template

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

# Sentry error tracking (EU region)
SENTRY_DSN=https://...@....ingest.de.sentry.io/...
VITE_SENTRY_DSN=https://...@....ingest.de.sentry.io/...

# Cost control
DAILY_API_BUDGET_USD=5.00
```

### Database Backups

SQLite backup script at `scripts/backup_db.sh` — uses `sqlite3 .backup` for WAL-safe copies, retains 7 days.

**Server cron setup** (run once on server):
```bash
crontab -e
# Add: 0 3 * * * /opt/urbanlayer/scripts/backup_db.sh /opt/urbanlayer/backend/data/urbanlayer.db /opt/urbanlayer/backups 7
```

### Verification Checklist (post-deploy)

1. `curl -I https://urbanlayerchicago.com` → 200 with HSTS + security headers
2. Chat without auth → 3 queries work, 4th returns 429
3. Google sign-in → chat works → UserMenu shows avatar → tokens refresh
4. Non-admin user → `/admin` redirects, `/api/admin/*` returns 403
5. Set `DAILY_API_BUDGET_USD=0.01` → budget cap after 1 query
6. Full chat query streams tokens correctly through Cloudflare → nginx → backend SSE
7. Vector search returns municipal code results (after Qdrant snapshot transfer)
8. Dev mode (no `GOOGLE_CLIENT_ID`): no auth UI, everything works as before

## Key Decisions

- **Hetzner CX22→CX32**: Started with CX22 (4GB RAM, ~$10/mo) but upgraded to CX32 (8GB RAM) because PyTorch embedding + reranker models consume ~2-3GB RAM alone.
- **Cloudflare Full Strict + Origin Cert (vs Let's Encrypt)**: Origin Certificate (RSA 2048, expires 2041) avoids certbot renewal complexity. Cloudflare handles edge TLS. Full (Strict) mode ensures end-to-end encryption.
- **Self-rolled JWT (vs Auth0)**: Auth0 adds latency, cost, and a vendor dependency. Google OAuth + HS256 JWT + opaque refresh tokens in SQLite is simpler and free. Auth is opt-in — disabled entirely when `GOOGLE_CLIENT_ID` is not set.
- **SQLite WAL (vs Postgres)**: Single-server deployment doesn't need Postgres complexity. WAL mode gives concurrent reads during writes. Backup via `sqlite3 .backup` is atomic and WAL-safe.

## Files Changed

- `docker-compose.prod.yml` — Production compose override (port 443, SSL volume, NGINX_CONF build arg)
- `frontend/nginx.prod.conf` — HTTPS redirect, SSL termination, security headers, gzip, CSP for Mapbox
- `frontend/Dockerfile` — NGINX_CONF build arg, port 443
- `backend/auth.py` — Google OAuth2 flow, JWT, refresh tokens, CSRF, FastAPI dependencies
- `backend/rate_limit.py` — Sliding window rate limiting, tier limits, daily API budget cap
- `backend/config.py` — Auth settings, cookie settings, frontend URL
- `backend/db.py` — Schema v4 migration (users, refresh_tokens tables)
- `backend/main.py` — Auth dependencies on endpoints, admin protection
- `.github/workflows/ci.yml` — pytest + tsc on PR, SSH deploy on merge to main
- `frontend/src/hooks/useAuth.ts` — Auth state management
- `frontend/src/components/AuthModal.tsx` — Google sign-in modal
- `frontend/src/components/UserMenu.tsx` — Avatar dropdown
- `frontend/src/components/ProtectedRoute.tsx` — Tier-based route guard
- `frontend/src/lib/api.ts` — authFetch wrapper, CSRF headers
- `scripts/backup_db.sh` — SQLite WAL-safe backup script
