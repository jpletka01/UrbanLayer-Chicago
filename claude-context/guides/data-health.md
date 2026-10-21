# Data health: the source registry and the checker

**Status (2026-10-21): registry, probes and dry run (WS6 M1); status store, daily timer, Sentry alarms and the dead-man check (M2).** The admin panel (M3, 2026-10-21) is the "Data Health" row on `/admin`; contracts and sentinels arrive in M4.

**Owner:** WS6. The registry's `id`s are the join key WS0 puts on provenance entries (`source_id`); WS1's code-vintage alarm and WS2's poller register here too. There is one registry and one alarm path.

## What it is

`backend/data_health/` has these parts:

| File | Job |
|---|---|
| `registry.py` | `SOURCES`: a tuple of `SourceSpec`, one per data source the product shows (81 on 2026-10-21). Who publishes it, its tier, which module reads it, how to read its date, how stale is too stale. |
| `probes.py` | Reads each source's latest data date (and the cheap contract facts) over HTTP, or from a local file. Parsers are pure and tested on recorded responses. |
| `evaluate.py` | Pure rules: probe result + spec + today → a status (`ok`, `warn`, `alarm`, `error`, `unknown`, `frozen_ok`, `acked`). |
| `check.py` | The CLI and `check()`, one run: probe, evaluate, store, alert. `--dry-run` prints every source and writes nothing. |
| `store.py` | `data_health.db` (SQLite on the `backend_data` volume; the checker is the only writer, the app reads it read-only for `/health`). |
| `alerting.py` | Sentry alarms on transitions and the Cron check-in, behind a `Sink` so tests inject a fake. |

The checker is cheap and dumb: HTTP reads and local files only, **no model calls** (it never spends the production Anthropic key), about 100 requests and 3 seconds for the whole registry. It imports no torch, no Discovery and not `backend.main` (a test asserts this), so it can run in its own short-lived container.

```bash
python -m backend.data_health.check --dry-run                       # every source, worst first
python -m backend.data_health.check --dry-run --only chi.crime,cook.   # a family: a trailing '.' is a prefix
python -m backend.data_health.check --dry-run --json
python -m backend.data_health.check --dry-run --today 2026-12-01    # judge ages as of another day
python -m backend.data_health.check --write --alert                 # what the daily timer runs
python -m backend.data_health.check --clear drill.synthetic         # delete a drill row
```

## How a date is read

Judge freshness on **content** where it can be read; the publisher touching a dataset is not the data being current.

| Kind | Published date | Content date |
|---|---|---|
| Socrata (city and Cook portals) | `GET /api/views/{id}.json` → `rowsUpdatedAt` (also gives the column list) | `$select=max(<col>)`; a *year* column counts as Dec 31 of that year |
| ArcGIS layer | `editingInfo.dataLastEditDate` when the service reports one | `query?orderByFields=<col> DESC&resultRecordCount=1`. **Never `outStatistics max`**: it returns a wrong value on the City server. Always look for an `error` key in a 200 body. |
| Census Reporter | | the newest release's end year |
| GTFS | `HEAD` → `Last-Modified` (the 68 MB zip is never downloaded) | |
| Clerk eLMS | | newest `recordCreateDate` (never `introductionDate`, which can be future-dated) |
| ptaxsim | the database's `created_at` | the last tax year in `metadata`, plus a `HEAD` for a newer upstream release |
| Code text | | `current_through` via `legislation.currency.code_currency_status()` (WS1's thresholds: warn 60, alarm 90) |

Sources with no date to read are judged on **findings**: reachability, a layer name, a known answer (121 N LaSalle geocodes within 50 m), or coherence (the Qdrant alias points at the vintage's collection with its chunk count; the zoning cache's vintage equals the code's; `zoning_definitions.VERIFIED_AGAINST` equals the code's).

## Statuses

- **ok**: inside its tolerances. **warn**: past `warn_days`. **alarm**: past `alarm_days`, or a frozen source changed.
- **error**: a service answered with an error body, or the structural contract broke (layer renamed, required field missing).
- **unknown**: no date signal. The 13 overlay layers have no edit-date field, so they are `unknown` with their name and count band checked. Unknown is amber, not red.
- **frozen_ok**: a frozen source (the 2015 footprints, the 1996 CHRS survey, the 2023 wards) whose publisher date has not moved. These alarm on **change**, not age: if one starts updating, our "frozen" label is wrong.
- **acked**: a known-stale source with an unexpired `ack`. Amber; does not alarm. An ack past its `until` becomes `alarm`.
- A transient probe failure (timeout, 5xx) is `warn` on one run and `alarm` on two in a row, so a network blip doesn't page. `previous_error` carries the last run's failure; the store keeps it (`source_status.probe_error`).
- A source with a working fallback (`warns_only_while_ok`: Cook GIS layer 44, with Parcel Universe behind it) can only warn.

## Adding a source

1. **Add a `SourceSpec`** to `registry.py`. Use `_socrata(...)` or `_layer(...)` for the common kinds. Give it a stable `id` (`chi.*`, `cook.*`, `fed.*`, `census.*`, `code.*`, `artifact.*`, `internal.*`), its tier (see `source-confidence.md`), the module that reads it, and tolerances. A frozen source takes `frozen=Frozen(as_of, label)` and **no** tolerances.
2. **Pick tolerances from the publisher's cadence**, on the content date when the dataset has one. Say why in `note` when it is not obvious.
3. **A completeness test fails CI** if a Socrata dataset id (in `config.py`, `main.py`, `retrieval/**` or `discovery/**`), an ArcGIS service URL, an `OVERLAY_LAYERS` id or a committed file in `ingestion/data/` has no entry. That is the point: a new source can't ship without a freshness rule.
4. **Run the dry run** and check the new row reads what you expect.

An overlay layer needs `chi.zoning.overlay.<type>` where `<type>` is its `OVERLAY_LAYERS` type. **Layer 7 stays out** (it is the Historic Resources Survey, not designations; F8, 2026-10-02) and a test asserts that.

## Acks

An ack is a code change, so each one is reviewed in a PR. It names a reason (what is stale and what covers for it), an owner and an `until` date. On 2026-10-21 three exist:

- `cook.address_points`: rows last updated 2024-04-08; Parcel Addresses `3723-97qp` is the second authoritative source.
- `chi.vacant_buildings`: the feed stopped on 2025-10-08.
- `chi.nof_large`: stale since 2023-09-19; only a project list in chat.

All three run until 2027-01-31. A fourth, `code.municipal_text`, runs until 2026-12-15 (see below). When one expires and the source is still bad it becomes an alarm, which forces the question.

## Gotchas

- **The City GIS server answers 403 to a User-Agent that contains a URL or parentheses** (`name/1 (+https://site)`), and 200 to `name/1`. The checker sends `urbanlayer-data-health/1`.
- **Error text must not carry a query string**: Walk Score's key travels in one, and an httpx error message quotes the URL. `probes._clean` strips them.
- **A probe that cannot run here** (no ptaxsim.db, no Discovery index, no Walk Score key) reports `unknown: not probed here`, never `ok`. A dev checkout therefore shows a few unknowns that production does not.
- **The local Discovery index is old** (built 2026-07-07), so the dry run on a dev machine alarms `internal.discovery_index`. Production rebuilds it monthly.

## Alarms (M2)

**Daily run.** `deploy/data-health-check.timer` starts `data-health-check.service` at 05:37 UTC: `docker compose run --rm --no-deps backend python -m backend.data_health.check --write --alert`. Its own container, so it never stacks memory on the serving process. Install and drill steps: `deploy/README.md`.

**What reaches Sentry** (`alerting.py`; one issue per source and state, so Sentry's new-issue email is the page):

| Event | Sentry |
|---|---|
| source enters `alarm` or `error` | one `error` event, fingerprint `["data-health", id, state]`, tags `source_id`, `severity`, `kind` (`stale` or `broken`), `source_kind` |
| still red on a later day | one more event a day, same fingerprint (bumps the count, no new email) |
| back to anything but red | an `info` "recovered" event |
| `warn`, `acked`, `unknown` | nothing (admin panel only) |

What we last notified about is stored per source (`alerted_state`), not inferred from the previous run. **For the first 14 days after the checker's first run only `critical` sources alert**; the rest are held back and alert as a new transition when the period ends.

**Dead-man, three layers.**
1. A **Sentry Cron monitor** (`data-health-check`, crontab `37 5 * * *`, 90 min margin) gets an `in_progress` then `ok` or `error` check-in per run. The monitor is created from the first check-in's config; nothing to set up in the Sentry UI.
2. **`/health`** carries `"data_health": {"checker": "ok"|"late", "last_run_age_h": 3.1, "alarms": 2}`. `late` = no finished run in 36 h (or none yet). It never changes the HTTP status.
3. **`.github/workflows/data-health-deadman.yml`** (daily): fails, and GitHub emails, when the site doesn't answer, `/health` has no `data_health` block, or `checker` isn't `ok`. A red source only adds a warning annotation (Sentry owns those).

**Backup age** (`internal.backups`, critical). `scripts/backup_db.sh` writes `backup_status.json` beside `chicago.db` (on the `backend_data` volume) after each successful backup; the checker container cannot see `/opt/urbanlayer/backups`, so it reads the status file instead of a mount. Warn after 30 h, alarm after 36 h (a missed night). With `BACKUP_STATUS_REQUIRED=true` (set in `docker-compose.prod.yml`) a missing file is an alarm; in dev it reads "not probed here". It sees the on-box copy only, not the off-box pull to the Mac.

**Code vintage** (`code.municipal_text`, critical, WS1's thresholds 60/90 days). American Legal publishes about four months behind Council, so the newest export is already past the 90-day alarm the day it is ingested; the source is acked until 2026-12-15, and the nudge is `.github/workflows/code-export-reminder.yml`: on the 1st of each month it fails (and emails) while `backend/code_vintage.json:ingested_at` is more than 35 days old. When the ack expires, re-decide the thresholds against the publisher's real lag rather than extending it blindly. `code.hand_table.zoning_definitions` alarms when `VERIFIED_AGAINST` differs from the vintage.

**The alarm drill** (production, after install, then quarterly):

```bash
cd /opt/urbanlayer
sudo systemctl start data-health-check.service                      # a normal run: rows written, Cron check-in
# stale source: expect a Sentry email "Data source stale: drill.synthetic"
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backend \
  python -m backend.data_health.check --write --alert --inject-fault stale:drill.synthetic
# broken source: expect "Data source broken: drill.synthetic"
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backend \
  python -m backend.data_health.check --write --alert --inject-fault broken:drill.synthetic
# clear: the next normal run drops the row and sends "recovered"; or delete it now
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backend \
  python -m backend.data_health.check --clear drill.synthetic
curl -s https://urbanlayerchicago.com/health                         # data_health.last_run_age_h under 26
```

Then resolve the two drill issues in Sentry by hand.

## The admin panel (M3)

`GET /api/admin/data-health` (admin only; no network) → `backend/data_health/panel.py`: the registry joined with `source_status`, read through the same read-only handle as `/health`. Response: `checker` (state ok|late at 36 h, last run, next run 05:37 UTC, last error, the last 10 runs), `counts` by state, `sources` sorted alarm, error, warn, unknown, acked, ok, frozen (critical first within a state). `?source=<id>` returns that source's 90-day history. A stored row with no registry entry (a fault drill's `drill.*`) is shown, never hidden. `frontend/src/components/admin/DataHealthSection.tsx` renders it; a row click shows the reason, publisher link and the history strip.

## Not here yet

| Milestone | Adds |
|---|---|
| M4 | value-set contracts, daily known-answer sentinels (FEMA and EPA known answers live here) |
| M5 | metadata sidecars for committed artifacts (`transit_stations.json` is `unknown` until then), the weekly kit, CI artifact-age warnings |
