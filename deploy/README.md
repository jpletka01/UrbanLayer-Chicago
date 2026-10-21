# Deploy units

## Data-health check — daily (WS6 M2)

`backend.data_health.check --write --alert` probes every registered data source (HTTP reads and
local files; **no model calls**), stores the result in `backend/data/data_health.db` (persistent
volume) and tells Sentry about sources that turned red. It also checks the age of the newest DB backup
(`backup_status.json`, written by `scripts/backup_db.sh`). `/health` reads the store and shows
`data_health.checker` (`ok`, or `late` after 36 h without a finished run). Design and alarm rules:
`claude-context/guides/data-health.md`.

### Install on the prod host (`ssh urbanlayer-prod`; needs sudo)

```bash
cd /opt/urbanlayer                                          # the unit files arrive with the deploy
sudo /opt/urbanlayer/scripts/backup_db.sh                   # once now, so backup_status.json exists before the first check
sudo cp deploy/data-health-check.service deploy/data-health-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now data-health-check.timer
sudo systemctl start data-health-check.service              # first run now, don't wait for 05:37 UTC
systemctl status data-health-check.service --no-pager       # "status=0/SUCCESS"
systemctl list-timers data-health-check.timer               # next run 05:37 UTC
```

### Check it

```bash
journalctl -u data-health-check.service -n 120 --no-pager   # the table, worst first, then "Sentry: N event(s)"
curl -s https://urbanlayerchicago.com/health                # "data_health":{"checker":"ok","last_run_age_h":0.0,...}
```

Exit `1` = the checker itself crashed (a Sentry Cron `error` check-in; the unit retries once after
30 min). A red *source* is not a failed unit: it is a Sentry issue. The alarm drill is in the guide.

The GitHub workflows `data-health-deadman.yml` (daily, fails if `/health` shows the checker late) and
`code-export-reminder.yml` (monthly, fails while the code text was ingested over 35 days ago) email a
failure to whoever last edited their schedule.

## Legislation sync — daily (WS1 M2)

`backend.legislation.sync` asks the City Clerk's API what Municipal Code amendments passed
after the code text's vintage and writes `backend/data/legislation_snapshot.json` (persistent
volume). The app only reads that file (no Clerk call on the request path) and reloads it when it
changes. Without a check in the last 72 h the Profile, chat and report stop giving a count; after
14 days they say "we couldn't check" (the committed `backend/code_amendments.json` still lists the
reviewed ones).

### Install on the prod host (`ssh urbanlayer-prod`; needs sudo)

```bash
cd /opt/urbanlayer                                          # the unit files arrive with the deploy
sudo cp deploy/legislation-sync.service deploy/legislation-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now legislation-sync.timer
sudo systemctl start legislation-sync.service               # first run now, don't wait for 06:00
systemctl status legislation-sync.service --no-pager        # "status=0/SUCCESS"
systemctl list-timers legislation-sync.timer                # next run 06:00 Chicago
```

### Check it

```bash
journalctl -u legislation-sync.service -n 20 --no-pager     # status=ok ... title17=16 ...
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  python -c "from backend.legislation.currency import code_currency_status as s; print(s())"
```

Exit codes: `1` = the Clerk was unreachable (the last good rows and `checked_at` are kept, so the
product ages out gracefully); `2` = contract drift (a final `subStatus` never seen before, or a
previously passed record vanished), snapshot marked `suspect` and treated as unchecked. Both
report to Sentry. Admins see the same data at `GET /api/admin/code-currency`.


## Property Discovery — monthly index rebuild

The prospecting index (`backend/data/discovery_index.db`, persistent volume) goes stale as CCAO
assessments/sales/characteristics update. These systemd units rebuild it monthly with `--refresh`
(which rebuilds exactly the community areas already in the index — so expanding coverage with a
one-off `--community-areas …`/`--all` run automatically carries forward).

### Install on the prod host (`ssh urbanlayer-prod`)

```bash
cd /opt/urbanlayer && git pull               # get the unit files (this deploy/ dir)
sudo cp deploy/discovery-index-rebuild.service deploy/discovery-index-rebuild.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now discovery-index-rebuild.timer
systemctl list-timers discovery-index-rebuild.timer        # confirm next run
```

### Run a rebuild on demand

```bash
sudo systemctl start discovery-index-rebuild.service       # same as the monthly run
journalctl -u discovery-index-rebuild.service -f           # watch it
```

### Expand coverage (one-off), then let the timer follow

The builder is **memory-bounded by construction** (per-CA ingest + streaming finalize), and runs
**off the live backend** in an ephemeral `run --rm` container, so a build never OOMs the serving
process. `--community-areas` *adds* to the existing index (parcels upsert; meta is recomputed over
the whole accumulated index — `community_areas` / `populated_fields` / `recipe_counts` are correct
cumulatively, not just the last batch). `--refresh` afterwards rebuilds exactly the current set.

```bash
# off-box build (own cgroup, shares the backend_data volume, skips qdrant); then reload
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backend \
  python -m backend.discovery.index_build --community-areas <new batch>
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

#### Expansion is RUNTIME-bounded, not build-bounded (8 GB box, hard cap)

The build is safe at any size, but the backend loads the **entire** index into RAM at startup
(~2 KB/parcel). On the 8 GB box that is the real ceiling. Expand in batches and let measurement
decide how far to go:

```bash
# after each batch + restart, measure the serving backend's resident memory
docker stats --no-stream $(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q backend)
free -m
```

**Stop rule:** keep backend RSS **≤ ~5.5 GB** (leaves ~2 GB for qdrant/frontend/OS/page-cache +
request spikes). When the measured curve says the next batch would breach that, **stop** and record
the final supported CA set. Do **not** run `--all` blindly — full city (~1.8M ≈ ~3.7 GB of snapshot
alone) is not expected to fit under the cap, and that is an accepted limit (no box bump).
