# Production Deployment Plan: urbanlayerchicago.com

## Context

UrbanLayer is currently a local-only Docker Compose app (backend + Qdrant + nginx/frontend). There's no CI/CD, no authentication, no HTTPS, and no cloud hosting. The goal is to deploy it as a live public website at `urbanlayerchicago.com` that serves as an interview portfolio piece — demonstrating not just the RAG pipeline but also production operations skills.

The backend is resource-heavy (~2-3GB RAM for PyTorch embedding + reranker models), which eliminates most free tiers. The primary recurring cost is the Anthropic API (~$0.03-0.10 per query), making rate limiting and auth essential before going public.

**Decisions**: Hetzner CX22 ($4.15/mo), Google OAuth + self-rolled JWT sessions, public GitHub repo.

---

## Phase 1: Hosting & Infrastructure (Hetzner CX22)

**Specs**: 2 vCPU (x86), 4GB RAM, 40GB SSD, 20TB egress — ~$4.15/month

RAM budget: backend ~2.5GB (PyTorch models + FastAPI) + Qdrant ~500MB + nginx ~50MB = ~3GB, leaving ~1GB for OS. Add 2GB swap as insurance.

### Setup

1. Provision CX22 (Ubuntu 22.04) in Hetzner Cloud console
2. Harden: SSH key-only login, disable password auth, `ufw allow 22,80,443`
3. Install Docker Engine + Compose plugin
4. Create 2GB swap: `fallocate -l 2G /swapfile && mkswap /swapfile && swapon /swapfile`
5. Clone repo, create `.env` with API keys, `docker compose -f docker-compose.yml up -d`
6. No Dockerfile changes needed — x86 architecture matches existing setup exactly

### docker-compose.yml changes for production

```yaml
frontend:
  ports:
    - "80:80"
    - "443:443"     # Add HTTPS port
  volumes:
    - /etc/ssl/cloudflare:/etc/nginx/ssl:ro  # Origin cert + key
```

---

## Phase 2: Domain & TLS

### Domain: Namecheap (already purchased)

`urbanlayerchicago.com` registered via Namecheap ($6.99/year, order #204276226). Domain privacy included.

### DNS: Cloudflare Free Tier

1. Add `urbanlayerchicago.com` as a site in Cloudflare (free plan)
2. Cloudflare will assign two nameservers (e.g., `asa.ns.cloudflare.com`, `vin.ns.cloudflare.com`)
3. In **Namecheap dashboard** → Domain List → `urbanlayerchicago.com` → Nameservers → switch from "Namecheap BasicDNS" to "Custom DNS" → paste the two Cloudflare nameservers
4. Wait for propagation (usually 15-30 min, up to 24h)
5. In Cloudflare, add DNS records:

```
A     urbanlayerchicago.com    → <hetzner-server-ip>   (Proxied)
CNAME www                      → urbanlayerchicago.com  (Proxied)
```

Free CDN for static assets, DDoS protection, analytics, origin IP hiding.

### TLS: Cloudflare Full (Strict) + Origin Certificate

- **Browser → Cloudflare**: Universal SSL (automatic, free)
- **Cloudflare → Origin**: Generate free Origin Certificate (valid 15 years) from Cloudflare dashboard. Install on server at `/etc/ssl/cloudflare/`. Mount into nginx container.

Zero maintenance vs Let's Encrypt (no certbot, no renewal cron).

### Production nginx.conf

Create `frontend/nginx.prod.conf` alongside existing `nginx.conf` (dev). Key additions:

- **Port 80**: `return 301 https://$host$request_uri`
- **Port 443**: SSL termination with Origin Certificate
- **Security headers**: HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, CSP (tuned for Mapbox GL JS blob workers + tile URLs)
- **Gzip**: `gzip on` for text/css/json/javascript, min 1000 bytes
- **Rate limiting zones**: `limit_req_zone $binary_remote_addr zone=chat:10m rate=2r/s` and `zone=api:10m rate=10r/s`
- **SSE**: existing `proxy_buffering off` is correct; keep `proxy_read_timeout 120s`
- `server_name urbanlayerchicago.com www.urbanlayerchicago.com`

Frontend Dockerfile gets a build arg to select dev vs prod nginx config.

---

## Phase 3: Authentication (Google OAuth + Self-Rolled JWT Sessions)

Google OAuth as the sole sign-in method. No password storage at all — Google handles identity, we handle sessions with self-rolled JWTs. This is interview-impressive ("I implemented the full OAuth2 authorization code flow with custom JWT session management") and better for users (one-click sign-in, no passwords to remember, harder to create throwaway accounts).

### Backend: New `backend/auth.py`

**Dependencies**: `PyJWT`, `httpx` (already present) — no heavy OAuth library needed, the Google flow is 3 HTTP calls

**Google OAuth2 flow** (Authorization Code):
1. `GET /api/auth/google` — redirect user to `accounts.google.com/o/oauth2/v2/auth` with `client_id`, `redirect_uri`, `scope=openid email profile`, `state` (CSRF)
2. Google authenticates user, redirects to `GET /api/auth/google/callback?code=...&state=...`
3. Backend exchanges `code` for tokens via `POST https://oauth2.googleapis.com/token`
4. Backend verifies the `id_token` (Google's JWT containing email, name, picture)
5. Upsert user in SQLite `users` table, issue our own JWT pair

**Google Cloud setup** (free): Create OAuth 2.0 Client ID in Google Cloud Console. Authorized redirect URI: `https://urbanlayerchicago.com/api/auth/google/callback`. Env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

**New SQLite tables**:
- `users`: `id`, `email`, `name`, `picture_url`, `google_id`, `created_at`, `tier` (free/premium/admin)
- `refresh_tokens`: `id`, `user_id`, `token_hash`, `expires_at`, `revoked`

**Token strategy**:
- Access token: JWT with `user_id`, `email`, `tier`, `exp` (15 min). Sent as `httpOnly`, `Secure`, `SameSite=Lax` cookie
- Refresh token: opaque token stored hashed in SQLite with expiry + rotation. Also `httpOnly` cookie
- CSRF protection: Double-submit cookie — readable CSRF cookie + `X-CSRF-Token` header, backend verifies match

**Endpoints**:
- `GET /api/auth/google` — initiate OAuth flow (redirect to Google)
- `GET /api/auth/google/callback` — handle callback, issue JWT pair, redirect to app
- `POST /api/auth/refresh` — rotate refresh token
- `GET /api/auth/me` — current user from token
- `POST /api/auth/logout` — clear cookies, revoke refresh token

**FastAPI dependency**: `get_current_user()` extracts + verifies JWT from cookie, injects `User`. Optional `get_optional_user()` for endpoints that work with or without auth.

**Schema v4 migration**: Add `users`, `refresh_tokens` tables. Add `user_id` column to `request_logs` and `llm_calls`.

### Frontend: Auth UI

**New components**:
- `AuthModal` — "Sign in with Google" button (modal overlay, not a separate page). Shows when unauthenticated user tries to chat. Clean, minimal — one button, maybe a brief explanation of why sign-in is needed.
- `UserMenu` — Google profile picture + name dropdown in workspace header, with sign-out option

**State**: `useAuth` hook managing `user` (with Google profile pic/name), `isAuthenticated`, `signIn()` (redirects to `/api/auth/google`), `signOut()`, `refreshToken()`. Cookie-based — httpOnly cookies sent automatically by `fetch` with `credentials: 'include'`.

**Flow**:
- Landing page is public (splash screen, suggestion chips)
- First message submission checks auth → if not authenticated, show `AuthModal` with Google sign-in
- After Google auth, redirect back to the app with cookies set
- Workspace header shows `UserMenu` with Google avatar when authenticated
- `/about` page stays fully public
- `/admin` requires admin tier

**fetch changes**: Add `credentials: 'include'` to all API calls in `api.ts`. Add `X-CSRF-Token` header to mutating requests.

### User Tiers (future-ready)

| Tier | Access | How to get |
|---|---|---|
| free | 25 queries/day, standard features | Sign in with Google |
| premium | Higher limits + site exploration (future) | Stripe payment (future) |
| admin | Unlimited + `/admin` dashboard | Manual DB flag |

The `tier` column on the `users` table is the extensibility hook for paid features. No Stripe integration in this phase — just the data model.

---

## Phase 4: Rate Limiting & Cost Control

### Per-User Limits

| Tier | Queries/day | Queries/hour | Msg limit/conv |
|---|---|---|---|
| Anonymous | 3 | 3 | 3 |
| Free (registered) | 25 | 10 | 10 (existing) |
| Admin | Unlimited | Unlimited | 10 |

### New file: `backend/rate_limit.py`

- FastAPI middleware with in-memory sliding window counters keyed by `user_id` (or IP for anon)
- Persist daily aggregates to new `usage_limits` SQLite table
- Return `429 Too Many Requests` with `Retry-After` header
- Apply only to `/chat` endpoint

### Daily API budget cap

- Env var `DAILY_API_BUDGET_USD=5.00`
- Wire existing `estimate_cost()` from `llm.py` + `llm_calls` table sum into a pre-request check
- Return friendly error when cap hit

### Nginx rate limiting (defense in depth)

```nginx
limit_req_zone $binary_remote_addr zone=chat:10m rate=2r/s;
limit_req zone=chat burst=5 nodelay;  # on /chat location
```

---

## Phase 5: Security Hardening

### CORS
```python
# config.py — set via CORS_ORIGINS env var in production
cors_origins = ["https://urbanlayerchicago.com", "https://www.urbanlayerchicago.com"]
```

### Input validation
- `max_length=2000` on `ChatRequest.message` in `models.py`
- Cap `ChatRequest.history` at 20 items

### Admin access
- Gate `/admin` frontend route behind admin-tier auth check
- Gate `/api/admin/*` endpoints behind `get_current_admin()` dependency

### Secrets
- `.env` on server with `chmod 600` (already gitignored)
- GitHub Actions encrypted secrets for CI/CD
- `JWT_SECRET` generated as a strong random key, stored in `.env`

---

## Phase 6: CI/CD Pipeline

### `.github/workflows/deploy.yml`

**On every push/PR — Test**:
```yaml
- python -m pytest backend/tests/ -q  # ~380 tests, mocked APIs
- cd frontend && npx tsc --noEmit     # type check
```

**On push to `main` — Build + Deploy**:
```yaml
- Build backend + frontend Docker images (linux/amd64)
- Push to GHCR (free for public repos)
- SSH into Hetzner server
- docker compose pull && docker compose -f docker-compose.yml up -d --remove-orphans
- curl -f https://urbanlayerchicago.com/health || exit 1
```

Tag images as `ghcr.io/<username>/urbanlayer-backend:latest` + `:sha-<short>`. Use GitHub Actions cache for Docker layer caching (the HuggingFace model layer is ~1.5GB, rarely changes).

---

## Phase 7: Qdrant Data Transfer

### Snapshot/Restore (one-time)

On local machine with Qdrant running and data loaded:
```bash
curl -X POST http://localhost:6333/collections/chicago_municipal_code/snapshots
# Download snapshot, scp to server
curl -X PUT http://<server>:6333/collections/chicago_municipal_code/snapshots/recover \
  -d '{"location": "file:///qdrant/snapshots/<file>"}'
```

Avoids recomputing 14,535 embeddings. Qdrant Docker volume persists across restarts. Set up weekly snapshot cron for backups.

---

## Phase 8: Monitoring

- **Sentry** (free, 5K errors/mo): `sentry-sdk[fastapi]` backend + `@sentry/react` frontend
- **UptimeRobot** (free): HTTP check on `/health` every 5 minutes, email alerts
- **Cost monitoring**: Already built into `/admin` dashboard. Add daily budget alert script.

---

## Database Scaling Path (future)

SQLite is not a bottleneck for <100 concurrent users. The Anthropic API latency (3-8s/query) is the real constraint.

**When to migrate**: Multiple backend processes, >50 writes/sec sustained, or >10GB database size.

**How to migrate**: Swap `aiosqlite` for `asyncpg` in `db.py` only (~2-4 hours). Use Supabase or Neon free tier for hosted PostgreSQL.

---

## Future: Premium Tier & Site Exploration (not in scope, but architected for)

The auth system includes a `tier` column (`free`/`premium`/`admin`) specifically to support a paid tier later. The motivating feature:

**Site Exploration** — criteria-based search across the entire city (e.g., "show me all RS-3 lots near transit with no flood risk and low crime"). Returns a heatmap/overlay view, not a single-address response. This is essentially a second product mode requiring:
- City-wide spatial queries across multiple datasets
- Spatial indexing and results ranking
- Different UX (criteria builder → map overlay, not chat)
- Stripe integration for payments

This would justify charging ($10-20/mo?) and is the natural next evolution of the platform. The auth + tier infrastructure built in Phase 3 is the prerequisite. Tackle only after validating demand.

---

## Execution Order

| Step | What | Outcome |
|------|------|---------|
| 1 | Provision Hetzner, Docker, deploy existing stack | App running on server IP |
| 2 | Point Namecheap NS → Cloudflare, set up DNS + Origin Cert | `https://urbanlayerchicago.com` live |
| 3 | ~~Production nginx.conf (HTTPS, headers, gzip, rate limits)~~ | **Done** — `nginx.prod.conf`, Dockerfile build arg, `docker-compose.prod.yml` |
| 4 | Transfer Qdrant snapshots | Vector search working |
| 5 | Google OAuth + JWT auth (backend + frontend) | User sign-in via Google |
| 6 | Rate limiting + budget cap | Protected from cost abuse |
| 7 | Security hardening (CORS, input caps, admin gate) | Locked down |
| 8 | GitHub Actions CI/CD | Automated test + deploy |
| 9 | Sentry + UptimeRobot | Observable |

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| ~~`frontend/nginx.prod.conf`~~ | **Done** — HTTPS, security headers (HSTS, CSP for Mapbox, X-Frame-Options), gzip. Nginx-level rate limiting deferred to Phase 6 (needs `http`-context directives) |
| New: `backend/auth.py` | Google OAuth2 flow, JWT session management, refresh rotation, CSRF, FastAPI dependencies |
| New: `backend/rate_limit.py` | Per-user rate limiting middleware + budget cap |
| New: `.github/workflows/deploy.yml` | CI/CD pipeline |
| ~~`docker-compose.prod.yml`~~ | **Done** — production compose override (port 443, SSL volume, `NGINX_CONF` build arg). Base `docker-compose.yml` unchanged |
| `backend/config.py` | Auth settings (JWT_SECRET, GOOGLE_CLIENT_ID/SECRET, token TTLs), rate limit settings, budget cap, prod CORS |
| `backend/main.py` | Mount auth routes, add rate limit + auth middleware, Sentry init |
| `backend/models.py` | `max_length=2000` on message, cap history at 20 |
| `backend/db.py` | Schema v4: `users`, `refresh_tokens`, `usage_limits` tables; `user_id` on existing tables |
| `requirements.prod.txt` | Add `PyJWT`, `sentry-sdk[fastapi]` |
| ~~`frontend/Dockerfile`~~ | **Done** — `NGINX_CONF` build arg (defaults to `nginx.conf` for dev), exposes port 443 |
| `frontend/package.json` | Add `@sentry/react` |
| `frontend/src/lib/api.ts` | `credentials: 'include'` on all fetches, CSRF header |
| `frontend/src/lib/useAuth.ts` | New hook: user state, login/register/logout/refresh |
| `frontend/src/components/AuthModal.tsx` | Google sign-in modal |
| `frontend/src/components/UserMenu.tsx` | Header user dropdown with Google avatar |
| `frontend/src/App.tsx` | Auth gate on first message, UserMenu in header |
| `frontend/src/main.tsx` | Sentry init + ErrorBoundary |

## Verification

1. `curl -I https://urbanlayerchicago.com` → 200 with HSTS + security headers
2. Unauthenticated `/chat` request → 401
3. Google sign-in → chat works → tokens refresh correctly
4. 4th anonymous query → 429 with Retry-After
5. Set `DAILY_API_BUDGET_USD=0.01` → budget cap after 1 query
6. Push to main → GitHub Actions build → deploy → health check green
7. Full chat query streams tokens correctly through Cloudflare → nginx → backend SSE
8. Vector search returns municipal code results
9. Trigger error → appears in Sentry
