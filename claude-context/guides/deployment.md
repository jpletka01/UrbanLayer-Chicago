# Deployment — UrbanLayer

## Production Server

Hetzner CX32 at `178.105.184.66` (Nuremberg datacenter). Ubuntu 22.04, 2 vCPU, 8GB RAM, 80GB SSD. Live at `https://urbanlayerchicago.com`.

**SSH access**: `ssh -i ~/.ssh/id_ed25519 root@178.105.184.66` (key has passphrase — run `ssh-add ~/.ssh/id_ed25519` first).

**Deploy** (from server `/opt/urbanlayer`):
```bash
git fetch origin && git merge origin/main && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**Server maintenance**:
```bash
docker compose logs -f backend                    # backend logs
docker compose logs -f frontend                   # nginx logs
docker compose restart backend                    # restart single service
docker stats --no-stream                          # resource usage
free -h
dmesg | grep -i -E 'oom|kill|memory'             # check OOM kills (exit code 137)
```

## DNS & TLS

Cloudflare Free — Full (Strict) mode + Origin Certificate (RSA 2048, expires 2041). Origin cert at `/etc/ssl/cloudflare/` on server. DDoS protection, static asset caching. Cloudflare error codes: 521 = Web Server Down, 525 = SSL Handshake Failed (both mean backend container is down).

## Docker

Multi-stage `backend/Dockerfile`: builder installs CPU-only PyTorch + deps + pre-downloads HF models; runtime copies packages, models, backend code, `community_areas.geojson`, `transit_stations.json`. Non-root `app` user.

`docker-compose.yml`: Qdrant (health-checked), backend (health-checked, 30s start period), frontend (nginx, waits for healthy backend). `backend_data` named volume persists SQLite + uploads.

`docker-compose.override.yml` (dev): mounts local `./backend` + `./ingestion/data` for hot-reload, exposes 8001.

## Seeding / updating the production code corpus (Qdrant)

There was no runbook for this until 2026-09-08; it is not obvious, because **the prod
image cannot run the ingestion pipeline at all**. `backend/Dockerfile` copies `backend/`
plus four `ingestion/data` artifacts — it does NOT copy `ingestion/*.py`, `chunks.jsonl`,
`sections/`, or the 101 MB source HTML. So `python -m ingestion.update` inside the prod
container is impossible. Qdrant is also a **persisted named volume** (`qdrant_storage`),
so a code deploy never touches the corpus: a parser fix ships without changing what prod
serves.

The corpus is updated by embedding LOCALLY and writing to prod over an SSH tunnel — this
keeps all model work off the 8 GB box:

```bash
# Qdrant publishes NO host port in prod (see the security note in docker-compose.yml),
# so tunnel to the CONTAINER on the docker bridge, not to 127.0.0.1.
IP=$(ssh root@178.105.184.66 'docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" $(docker ps -qf name=qdrant)')
ssh -f -N -L 6335:$IP:6333 root@178.105.184.66
curl -s localhost:6335/collections/chicago_municipal_code | jq .result.points_count
```

Then embed locally and upsert to `localhost:6335`. **Delete the target sections' points
first** — `embed_and_store` assigns `uuid.uuid4()` per point, so a re-run without a delete
DUPLICATES rows rather than replacing them. Verify by comparing per-section point counts
against local, not just the total.

Only `title_number == 17` chunks belong in the `chicago_zoning` collection; everything else
is code-collection only. Prod currently has just `chicago_municipal_code` — the precomputed
zoning cache made the second collection unnecessary there.

**Done 2026-09-08:** Title 14 (the building code) pushed this way — prod 14,535 → 16,576
points, matching local exactly, per-section counts verified, `/section/14A-1-101` now 200.

`docker-compose.prod.yml`: builds frontend with `nginx.prod.conf` (HTTPS, security headers, gzip), exposes 80+443, mounts Cloudflare Origin Certificate. Sets `RERANKER_ENABLED=true`.

```bash
docker compose up -d                              # dev (hot-reload)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d  # production with HTTPS
docker compose build backend                      # rebuild after dep changes
```

## Production .env Template

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
VITE_MAPBOX_TOKEN=pk.eyJ1...

# Optional data sources
SOCRATA_APP_TOKEN=...
WALKSCORE_API_KEY=...

# Auth (leave empty to disable — all users treated as admin)
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

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```

## CI/CD

`.github/workflows/ci.yml`: pytest + tsc on PRs, SSH deploy on merge to main. Secrets: `SERVER_SSH_KEY`, `SERVER_HOST`, `ANTHROPIC_API_KEY`.

`.github/workflows/codeql.yml`: GitHub CodeQL (python + javascript-typescript) on PRs/pushes to main + weekly. Replaced the Claude review action 2026-09-09 — that one never ran (no API key configured). CodeQL is security analysis only; there is no general automated code reviewer now. `.github/dependabot.yml` batches monthly minor/patch updates.

## Monitoring

- **UptimeRobot**: `/health` checks
- **Sentry**: Backend (`sentry-sdk[fastapi]`) + frontend (`@sentry/react`), EU region

## Database Backups

SQLite backup script at `scripts/backup_db.sh` — `sqlite3 .backup` for WAL-safe copies, retains 7 days. DB path on server: `/var/lib/docker/volumes/urbanlayer_backend_data/_data/chicago.db`.

Cron (server): `0 3 * * * /opt/urbanlayer/scripts/backup_db.sh /opt/urbanlayer/backend/data/urbanlayer.db /opt/urbanlayer/backups 7`

## Memory Budget (8GB CX32)

~500MB embedding model + ~1.3GB reranker + ~500MB Python/PyTorch + Qdrant + nginx ≈ 4GB, leaving ~4GB headroom for request processing.

## Verification Checklist

1. `curl -I https://urbanlayerchicago.com` → 200 with HSTS + security headers
2. Chat without auth → 3 queries work, 4th returns 429
3. Google sign-in → chat → UserMenu → token refresh
4. Non-admin → `/admin` redirects, `/api/admin/*` returns 403
5. Full SSE streaming through Cloudflare → nginx → backend
6. Vector search returns municipal code results
