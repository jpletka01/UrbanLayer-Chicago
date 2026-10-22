# Deployment — UrbanLayer

## Production Server

Hetzner CX32 (Nuremberg datacenter; ssh alias `urbanlayer-prod`). Ubuntu 22.04, 2 vCPU, 8GB RAM, 80GB SSD. Live at `https://urbanlayerchicago.com`.

**SSH access**: `ssh urbanlayer-prod` (key has passphrase — run `ssh-add ~/.ssh/id_ed25519` first).
The address isn't written in this public repo; define the alias in `~/.ssh/config`:

```
Host urbanlayer-prod
  HostName <server IP from the Hetzner console>
  User jack            # root login is disabled after deploy/hardening-runbook.md step 4
  IdentityFile ~/.ssh/id_ed25519
```

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

This section is the mechanics of the push. The whole refresh (the monthly review, the dry run and gates, the
codification check, what to re-verify, when to drop old collections) is `guides/code-refresh.md`.

There was no runbook for this until 2026-09-08; it is not obvious, because **the prod
image cannot run the ingestion pipeline at all**. `backend/Dockerfile` copies `backend/`
plus four `ingestion/data` artifacts — it does NOT copy `ingestion/*.py`, `chunks.jsonl`,
`sections/`, or the 101 MB source HTML. So `python -m ingestion.update` inside the prod
container is impossible. Qdrant is also a **persisted named volume** (`qdrant_storage`),
so a code deploy never touches the corpus: a parser fix ships without changing what prod
serves.

The corpus is updated by embedding LOCALLY and copying the result to prod over an SSH
tunnel. That keeps all model work off the 8 GB box.

**One collection per code vintage, behind an alias** (WS1 M0, 2026-10-21). The app reads
the alias `municipal_code` (`settings.qdrant_code_collection`). Each export lives in its
own collection, `municipal_code_<current_through>` (e.g. `municipal_code_2026-03-18`), and
`backend/code_vintage.json:collection` names the one the code was ingested into. A refresh
never edits the collection being served:

1. `python -m ingestion.update --dry-run --source <export>` parses into
   `ingestion/data/sections.new/` and writes `ingestion/data/diff/<vintage>/report.md`.
   Nothing else is touched. Review the report and its abort gates.
2. `python -m ingestion.update --source <export>` (add `--force` once a tripped gate is
   explained) embeds into the new local collection. Only after the point count matches
   does it promote the staged files, keep the old ones in
   `ingestion/data/snapshots/<old vintage>/`, flip the local alias, and write
   `code_vintage.json` + `code_changes.json`.
3. Push to prod with `ingestion.push_index` (below), then merge the PR carrying
   `code_vintage.json`. **Alias first, then the code deploy**: in between, the product
   understates how current the text is, never overstates it.

```bash
# Qdrant publishes NO host port in prod (see the security note in docker-compose.yml), so
# tunnel to the CONTAINER on the docker bridge. `jack` isn't in the docker group, so the
# IP lookup needs sudo (Jack types the password); the IP only changes if the container is recreated.
ssh -t urbanlayer-prod 'sudo docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" $(sudo docker ps -qf name=qdrant)'
ssh -f -N -L 6335:<that IP>:6333 urbanlayer-prod

python -m ingestion.push_index --target http://localhost:6335 --status   # collections, counts, alias
python -m ingestion.push_index --target http://localhost:6335 --upload   # local alias target -> prod, same ids/vectors
python -m ingestion.push_index --target http://localhost:6335 --verify   # per-section chunk-text hashes; must be 0 differences
python -m ingestion.push_index --target http://localhost:6335 --switch   # re-verifies, then flips the alias atomically
# rollback: --switch --to municipal_code_<previous vintage>   (kept until the next refresh)
# cleanup, one refresh later: --drop municipal_code_<older vintage>   (refuses the served one)
```

`--upload` copies points with their ids and vectors, so nothing is re-embedded on prod and
a re-run can't duplicate rows (the old hand-push used `uuid4` ids and needed a delete
first). `--snapshot-copy FROM --collection NEW` copies a collection to a new name on the
same server (snapshot, then recover from it), with no transfer.

**Migration done 2026-10-21:** prod's `chicago_municipal_code` (16,576 points) was verified
equal to local section by section, copied server-side to `municipal_code_2026-03-18`, and
put behind the `municipal_code` alias before the config change deployed.

**Done 2026-09-08:** Title 14 (the building code) pushed by hand: prod 14,535 → 16,576
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

Cron (root, server): `0 3 * * * /opt/urbanlayer/scripts/backup_db.sh >> /var/log/urbanlayer-backup.log 2>&1` (UTC; defaults to the volume path above, `/opt/urbanlayer/backups`, 7 copies). The folder is `root:jack` 2750 and copies are 640 (they hold user data). **The entry was lost in the 2026-09-28 hardening; no backups ran from Sept 28 to Oct 20, when it was restored.**

Off-box: Jack's Mac pulls the copies (`scripts/pull_backups.sh`, launchd job `deploy/launchd/com.urbanlayer.backup-pull.plist`, every 4 h) into `~/Backups/urbanlayer`, keeping 60. It uses a no-passphrase key the server accepts only for read-only `rrsync` of the backups folder, and shows a macOS notification if the pull fails or the newest copy is over 36 h old. The Mac copies aren't encrypted. Setup, the restore test (last passed 2026-10-20) and the prod restore steps are in `deploy/hardening-runbook.md` §8c. A server-side backup-age alarm comes with WS6 M2.

## Memory Budget (8GB CX32)

~500MB embedding model + ~1.3GB reranker + ~500MB Python/PyTorch + Qdrant + nginx ≈ 4GB, leaving ~4GB headroom for request processing.

## Verification Checklist

1. `curl -I https://urbanlayerchicago.com` → 200 with HSTS + security headers
2. Chat without auth → 3 queries work, 4th returns 429
3. Google sign-in → chat → UserMenu → token refresh
4. Non-admin → `/admin` redirects, `/api/admin/*` returns 403
5. Full SSE streaming through Cloudflare → nginx → backend
6. Vector search returns municipal code results
