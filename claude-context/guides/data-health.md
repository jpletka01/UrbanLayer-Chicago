# Data health: the source registry and the checker

**Status (2026-10-21): registry, probes and dry run (WS6 M1); status store, daily timer, Sentry alarms and the dead-man check (M2).** The admin panel (M3, 2026-10-21) is the "Data Health" row on `/admin`; contracts and sentinels arrive in M4.

**Owner:** WS6. The registry's `id`s are the join key WS0 puts on provenance entries (`source_id`); WS1's code-vintage alarm and WS2's poller register here too. There is one registry and one alarm path.

## What it is

`backend/data_health/` has these parts:

| File | Job |
|---|---|
| `registry.py` | `SOURCES`: a tuple of `SourceSpec`, one per data source the product shows (83 after WS2 PR 1). Who publishes it, its tier, which module reads it, how to read its date, how stale is too stale. |
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
| Pending legislation snapshot | | last successful atomic refresh in `pending_legislation.db`; the latest failed/suspect attempt is a separate finding and never erases the date/counts |
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

**Amendment review** (`internal.amendment_review`, WS1 M7). Is the monthly review of what Council passed being done? `probe_amendment_review` reads the Clerk snapshot and `backend/code_amendments.json` (offline, via `currency.review_backlog`) and judges how long each unreviewed amendment has waited since Council passed it: a Title 17 amendment warns after 14 days and **alarms after 45** (the only one that emails); any other passed amendment warns after 45 and never alarms. It is its own source because `code.municipal_text` is acked until 2026-12-15, and an ack turns every alarm on that source into `acked`. Without a fresh Clerk check (older than 14 days, or `suspect`) it judges nothing and says why; `chi.clerk.legislation` reports that. The routine it asks for is `guides/code-refresh.md`.

**Pending legislation snapshot** (`internal.pending_legislation`, WS2 PRs 1–2). The existing daily legislation sync writes `backend/data/pending_legislation.db`; the checker and Profile reader open it read-only. Freshness is the last successful atomic refresh (warn after 3 days, alarm after 14). A failed latest attempt is a warning while last-good rows/counts remain; lifecycle/status contract drift is an immediate error. The row reports candidate/detail/current counts, zoning and Title-17 subsets, parse-ready titles, actual placed/unplaced zoning matters and stored locations, lifecycle collapses, and excluded attachment metadata. The City Clerk API remains the official record source; Cook County Address Points plus UrbanLayer's deterministic range/distance calculation supply placement. The Profile treats >3 days or a failed latest attempt as stale and >14 days as unavailable, never as an empty result.

**Pending-amendment review** (`internal.pending_impact_review`, WS2 PR3). Is every pending Title 17 text proposal read and mapped (`backend/pending_impacts.json`)? `probe_pending_impact_review` reads the pending snapshot and the review file only and judges days since Council introduced each unreviewed or outdated matter (a review of an older record than the live substitute counts as outdated): warn after 14 days, **alarm after 45**; an invalid review entry (a title-only review carrying an impact, an unknown fact id, a missing field) alarms immediately and the entry is ignored, so its matter reads unreviewed. Like `internal.amendment_review` it judges nothing without a fresh snapshot (older than 14 days or never run) and says why. The Profile shows the same state to users: any unreviewed or outdated matter makes its review `incomplete`, which never reads as "none relevant". The routine it asks for is in `guides/code-refresh.md`.

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

## Contracts and sentinels (M4)

Freshness says a source is current; contracts and sentinels say it still *means* what we think. Both run in the daily check and feed the same states and alarms.

**Contracts** (`backend/data_health/contracts.py`, evaluated in `evaluate.contract_findings`):
- **Fields we read.** `fields_read.json` lists, per Socrata source, the columns its owning module mentions (38 sources). The registry merges it into each `Contract.required_fields`; a column the publisher renames or drops is an `error` on the next run. Regenerate after changing a module's reads: `python -m backend.data_health.contracts --scan --write` (reads the committed modules and the public `/api/views` schemas; no model). A test fails if a listed column is no longer mentioned by its module, and if a new Socrata source with named columns has no entry. This is the check that would have flagged `t68z-cikk`.
- **Value sets** (`ValueSpec`): layer 1 `ZONE_CLASS` must start with a known family (`ZONE_FAMILIES`; the layer has 1,526 distinct values, mostly `PD n`, and a few typos like `RM4-.5` that still start with a family), layer 6 `LANDMARK` is Y or N, Address Points `st_predir` is a compass word (Chicago rows). A value outside the set is an `alarm` naming it.
- **Count bands**: wards 50, community areas 77 (exact), ward offices 45–55, plus the layer bands from M1. Socrata counts use `$select=count(*)`.

**Sentinels** (`backend/data_health/sentinels.py`, source `internal.sentinels`, critical): each day the checker runs production's `lookup_zoning` and `query_overlays_checked` at the 12 kit parcels plus one positive control (5749 W Race Ave, a designated individual landmark; official list `tdab-kixi`, layer 5 covers it) and compares the district and the overlay set with `eval/kit/parcels.json`. Any difference is an `alarm` that names the field; a parcel the lookups could not answer (or with an overlay layer down) is a `warn`, never "overlay absent".
- `sentinels.json` is generated from the kit (`python -m backend.data_health.sentinels --from-kit eval/kit/parcels.json --control "5749 W Race Ave" --write`) because `eval/` is not in the image; a test keeps it in sync with the key. Coordinates are the point the Profile resolves the address to (Address Points), or the Assessor centroid for a vacant lot (P2).
- `UNCURATED_EXTRA` (`adu_area`, `tod_metra`): the key does not list these, so finding one is not a mismatch; a key-listed overlay still must be found.
- **Never re-baselined automatically.** An alarm is either a City data change (review, re-key the kit, regenerate) or our code reading it wrongly (fix the code). Run one by hand: `python -m backend.data_health.sentinels --check`.
- The F8 replay (`test_data_health_sentinels.py`): the pre-fix mapping (layer 7 as "landmark building") applied to a recorded layer-7 hit at P11 derives a landmark the key says is not there, and alarms.

## Artifact ages and the weekly kit (M5)

**CI artifact ages** (`backend/data_health/artifacts.py`): `python -m backend.data_health.artifacts --ci` is a step in `ci.yml`'s `test` job, `continue-on-error: true`. It prints a `::warning` annotation per artifact past its tolerance and a table in the job summary; it never fails the build (a stale artifact must not block a hotfix deploy; the daily checker is the real alarm). It reads only repo files: the code text's "current through" date (60/90 days; the registry's ack for it is named in the message), `zoning_cache.json` (its build date and that `_meta.code_vintage` equals the code text's), `transit_stations.meta.json` (180/365), the answer key's version date (180), `docs/benchmark/results.json` (45) and the hand table's `VERIFIED_AGAINST`. Run it by hand without `--ci` to get a nonzero exit on a red artifact.
- **Sidecars:** a committed artifact with no date of its own gets `<name>.meta.json` beside it, written by its build script. `transit_stations.meta.json` is the first. A sidecar must be in `.gitignore`, the `.dockerignore` allowlist and a Dockerfile `COPY`, or the daily checker can't read it on the box.
- `zoning_cache_build` writes `_meta.code_vintage`; the committed cache records `2026-06-17` (the reviewed rebase of 2026-10-21).

**Weekly kit** (`.github/workflows/kit-weekly.yml`, Mondays 10:00 UTC + manual dispatch): runs `python -m eval.parcel_kit --full https://urbanlayerchicago.com --surfaces profile` (the free `/api/scorecard`: no model, no secret) and judges it with `python -m eval.kit_gate` against `eval/kit/accepted_profile.json`. It fails if any parcel's district (field A) is not 2, on any confident-wrong claim, or if any cell falls below the accepted run. The run is kept 90 days as an artifact. A failed run emails whoever last edited the schedule; with a `SENTRY_DSN` repo secret it also sends one Sentry event.
- **Drill:** Actions > Weekly parcel kit > Run workflow with `inject_mismatch` ticked. The scored copy has P1's district corrupted; the run must go red. Never edit the accepted file to make a run pass: after a person reviews an improvement, `python -m eval.kit_gate <parcel_kit.json> --update-accepted`.
- **Registry:** `eval.kit_weekly` reads the workflow's runs through the public Actions API (warn 9 days, alarm 16 days or a failed latest run; unknown before the first run). `artifact.transit_stations` is dated by its sidecar, with the CTA feed's Last-Modified as context.
- The chat surface (about $1.20 a run, production credits) is a separate monthly production check, not run here.

## Data dates on every surface (M6)

`vintages.py` (`vintages_for(provenance, code_currency=None)`) is the one builder of "how current is what you are reading". It takes the provenance map (so source-level dates already came through `status.latest()` and the registry) and returns up to 14 `DatedSource`s in reading order: zoning map record edited, code text current (+ amendments since, from `code_currency`), Assessor values year, tax year, sales through, ACS tract / community area, then the area feeds (crime, 311, permits, violations, business, vacant, food). Each has a `kind`: `record` (a record's own edit date), `through` (a source's data runs through), `period` (a survey or tax year is the date), or `checked` (the source gave no date, so the day we asked; a date we don't have is never invented). The code text appears only when the answer rests on it, and the amendments count follows `code_currency`'s check state (fresh gives a count, aging a count "as of", unknown "couldn't check recently").
- **Chat:** a `- **Data dates:** …` line in the sources footer, persisted in the message text like the rest of it (a shared link carries it). The code date is left out of it when cited code already prints the currency line. The area source lines carry the area, the window ("last 90 days") and the margin level, not dates.
- **Report:** the cover's "Report Date" is "Generated on <date>" plus a "Data as of" box from `helpers()["data_dates"]`, and "Not checked in this report:" lists `partial_failures` (M7 makes those honest). The sources table was already generated from the registry (WS0 M5).
- **Profile:** `/api/scorecard` carries `data_dates`; the page footer words them (`lib/dataDates.ts`, `dataDates.*` in `common`) beside "Checked <day>".
- **Wording** lives in three catalogs that a test keeps equal: `dates.*` in `report_i18n.py` (chat and PDF), `dataDates.*` in the frontend locales. A lint forbids a typed year range (`2019–2023`) in the catalogs, the template, the footer and the prompts.
- To date a new feed: give its fact an entry (WS0 guide §8), then add it to `_AREA_FEEDS` (or a headline in `vintages_for`), a noun in both catalogs, and the key in the frontend/backend parity test.

## Partial failures, shown honestly (M7)

A source that didn't answer must read as "couldn't check", never as "none". Four parts:
- **One table** (`failures.py`): `LABELS` (the plain words that go in `partial_failures`), `MODULES` (which Profile module, and so which report section, each failure belongs to), `failed_detail(partial_failures)` → `[{key, labels}]`. Chat, scorecard and report build their failure labels from it; `/api/scorecard` carries `failed_sources`.
- **A failed call raises and is never cached.** The Assessor assessments, sales, characteristics and the comparable-sales query used to swallow an error and return "none" (and the first two cached it for a day, comps for an hour). They raise now; the property domain turns that into `data_gaps` and, only for a call that failed (not a record the source lacks, as for an exempt parcel), into `PropertySummary.failed_calls`, which the scorecard adds to `partial_failures`. Overlay layers were fixed in M7a. **Flood (2026-10-22):** `query_flood_zone` raises `FloodLookupError` (a 200 with an `error` body or no `features` counts as a failure; `None` is still FEMA's genuine "no mapped zone" and is cached); `RegulatorySummary.flood_unchecked` is true and `in_special_flood_hazard` is `None` (unknown, not false); the label is `failures.label("flood")` ("FEMA flood zone", module `record`: the Environment card). The Profile's Environment card shows its own `UncheckedRow` (with a FEMA flood map link) and the verdict hedges (it does not change category: unknown is not "constrained"); chat's footer carries it, prompt rule 16 forbids "not in a flood zone", and a Profile handoff adds the label even though the turn skipped the fetch; the report has a notice at the head of Regulatory & Environmental, an in-place line, a NOT CHECKED summary pill and a re-check item instead of a "completed" tick. FEMA resets many fresh connections, so the lookup retries resets (4 attempts, 0.3 s apart; timeouts and HTTP errors are not retried).
- **Surfaces.** Profile: each of the five modules shows an `UncheckedRow` ("Couldn't check <thing> today ... isn't a \"no\"") when its source failed, even if the module would otherwise have vanished; the verdict says so in its own words when the district itself failed. Chat: a deterministic `**Couldn't check today:**` line after the sources block (alone when there are no sources), whatever the model does. Report: the cover's "Not checked" line plus a notice at the head of each section that left a source out.
- **Live failure rate.** `live.py`: the app counts, per registry source, each call's outcome (once per call, not per retry) in `socrata_get`, the overlay layers, the zoning layer, the census tract call and FEMA's flood lookup (`fed.fema.nfhl`), flushes hourly to `backend/data/data_health_live.db` (the app is its only writer; the checker never writes it), and the checker reads the last 24 h: over 20% of at least 10 calls is `warn`, over 50% `alarm`. Not yet counted: the other ArcGIS layers (parcels, EPA, HUD), Walk Score, the Clerk.
- **Fault flag** (dev only; ignored when `environment=production`, loud at startup): `DATA_HEALTH_FAULT=overlay:5`, `socrata:<dataset id>`, `source:<registry id>` (`source:fed.fema.nfhl` fails the flood lookup), several joined by `;`. Start the backend with it and every surface should say "couldn't check" and none say "no". Example: `DATA_HEALTH_FAULT="overlay:5;source:chi.zoning.districts;source:cook.assessor.sales" uvicorn backend.main:app --port 8001`.

## Fact snapshots and report originals (M8)

`facts.py` `snapshot(context, ...)` is the small record (1 to 4 KB) of what an answer or a report rested on: the district and its ordinance, overlays (sorted, names normalized), the verdict flags, standards, the code vintage and cited sections, headline records, each source's date, the passed ordinances that list the parcel, what could not be checked. It is built **on the server from a validated `ContextObject`** and never read from a client payload. A parcel answer stored through `db.save_messages` gets `messages.facts_json` (none for an area or code answer); every report render gets a `report_renders` row (facts + `vintages_json`).
- **Originals.** A purchase keeps the first report it renders: the PDF under `backend/data/reports/<purchase_id>/<ms>.pdf` (SHA-256 recorded, checked on every serve; a missing or altered file is a 410, never served as the original), unique per purchase by a partial index. `GET /api/report?copy=original` serves it; any other download is a live render, and once an original exists its cover says "Updated copy of the report first generated on <date>". Updated copies, subscriber and admin renders keep a row but no PDF. A purchase made before this shipped gets its original from its next download.
- **Backups.** `scripts/backup_db.sh` mirrors `reports/` beside the nightly database copy, append-only (`rsync --ignore-existing`, no `--delete`). The off-box pull (`scripts/pull_backups.sh`, on Jack's Mac) does not fetch it yet.
- Account deletion removes the user's PDFs and render rows, never the purchase ledger.
## "Since then" (M9)

`diff.py` `compare(old, current)` (pure) lists the material changes between a stored snapshot and today's facts; `changes_for(old)` fetches today's facts (`current_facts`: the Profile's `lookup_zoning` + `regulatory_domain` at the stored point, no model), keeps them per (parcel, UTC day) in `fact_checks` (schema v16) and compares. Kinds: district, overlay (13 rule-carrying layers), standards (same district), amendment (before or after the answer), map_amendment, designation, text_refresh, correction (`corrections.json`, each checked against git). **A lookup that fails makes no claim** (`partial` / `unavailable`, never `none`), and an incomplete check is not cached. Old messages are rebuilt from `context_json`/`plan_json` (`reconstructed`; the code vintage is the text before the first refresh, since `ContextObject.code_vintage` is computed from today's files). Surfaces: `/api/conversations/{id}/changes`, `/api/share/{token}/changes` (public, per-IP limited, cached), `changes` on `/api/me/purchases`, `AnsweredOnNote` and the Settings `PurchaseRow` line. At most 3 parcels per conversation; answers under 24 h skipped. Adding a correction: append to `corrections.json` with its commit and a predicate on snapshot paths (`test_corrections_file_is_well_formed`); a fix whose cause the snapshot doesn't store needs the field added to `facts.snapshot` first.

## Not here yet

Phase 2 is complete. "Newer data available" (a new tax year or ACS release) is not built. The retrieval layer has about 70 `except Exception` blocks; the three that cached a failure are fixed, but each of the others that swallows an error and returns an empty result is a place a failure can still read as "none" (incentive layers, Walk Score and the parcel lookups are the next to audit; flood is done). The `displayed_label` field on a source (what we tell users, e.g. "ACS 2020–2024") is read only by the sources table; the probe-versus-label alarm the plan describes is not built, because no wording carries a typed vintage any more (the lint above guards that instead).
