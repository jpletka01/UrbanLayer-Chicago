# Build queue 2026-10: engineering decisions

The confidence standard (WS0), code refresh (WS1) and data health (WS6) workstreams ship as one serial merge queue, one PR per item. This file records the decisions made inside each item. Format: see `README.md` in this folder.

Standing constraints that shaped many of these:
- **No production model tokens for build work.** Verification uses fixtures, mocks, recorded replays and direct reads of government APIs. It never runs a live chat or a model script.
- **Free tiers only, no new sign-ups.**
- **Pushing to `main` deploys.** So a deploy is verified by what the live API and bundle serve, not by git HEAD.

---

## Item 0: nightly backups and an off-box copy (#58, 2026-10-20)
*Reconstructed from the earlier session's notes; that session holds the full reasoning.*

- **Diagnosis before the fix.** The last on-box backup was a manual run on Sept 28, and no backup log existed. The guess was "cron entry lost in the Sept 28 hardening", and reading root's crontab confirmed it was empty. Restored with output redirected to a log, so a silent stop is visible next time.
- **Off-box copy = pull, not push.** The owner's Mac pulls over SSH every 4 h (launchd + rsync). The server holds no credentials for anything else, so a compromised server can't reach or delete the copies. The Mac's key is restricted server-side to read-only `rrsync` on the backups directory. That's why it can be passphrase-less without being a general login key. *Alternative:* encrypted push to existing cloud storage. Rejected for now because it adds a tool and a credential on the server.
- **Plain copies, owner's call.** No encryption at rest on the Mac. Recorded as an open risk (disk encryption is off).
- **Tooling quirks (keep):** macOS `openrsync` sends `--dirs` for `-r` with include/exclude, which `rrsync` rejects, so use a remote glob. macOS `sqlite3 -readonly` fails on the copies, so open them with `file:…?immutable=1`.
- **Revisit if:** the Mac stops being on regularly (copies go stale silently until WS6 M2's backup-age alarm lands), or more irreplaceable stores appear (WS6 M8's report PDFs and `data_health.db` must join the same job).

**Numbers** *(from the earlier session's notes)*
- **Backup gap:** last good copy 2026-09-28 → nightly restored 2026-10-20, so 22 days with no backups.
- **Off-box copy:** pulled every 4 h, keeping 60 copies (about 10 days at one per 4 h; fewer distinct days if the Mac is off).
- **Restore test:** passed; no timing recorded.
- **Not measured:** backup size and duration, transfer time, and how often the Mac is actually on (the real recovery-point objective).

## Item 1: overlay tri-state (#59, 2026-10-20)
*Reconstructed from the earlier session's notes.*

- **"Couldn't check" is a third answer, not "no".** An overlay layer the City map failed to answer used to read as "not in this overlay", which is a confident false negative on a landmark/PD/flood question. It now reads as unknown, everywhere it surfaces (Profile, chat, report).
- **Spanish debt made visible:** introduced `frontend/src/locales/es/_untranslated.json` plus a vitest guard. A new `es` string carries the English text, and its key is listed. The guard fails if a listed key is missing or has been translated without being delisted. Every later PR reuses it.

**Numbers** *(from the earlier session's notes)*
- **Not measured:** how often a layer fails to answer in practice (the rate of "couldn't check"). WS6 M2's daily checks should produce it; until then the tri-state's user impact is unknown.

## Item 2: the source confidence standard (#60, 2026-10-20)

**The guide holds rules, not the work queue.**
- **Decision:** `claude-context/guides/source-confidence.md` carries the tiers, the five fields, thresholds, display rules, source-id scheme, ownership and an "adding a figure" checklist. The per-figure inventory and the fix list stay in the local plan.
- **Alternatives:** commit the whole plan.
- **Why:** the guide is what every later PR cites and must stay true. The inventory goes stale as items ship. The plan files are local-only, so the guide can name them but not link them.
- **Revisit if:** the inventory becomes something reviewers need in-repo. Then it belongs in the audit script WS0 M3 adds, generated, not hand-kept.

**Source ids before the registry exists.**
- **Decision:** the guide adopts the data-health workstream's planned slugs (`chi.zoning.districts`, `census.reporter.acs`, …) as the contract now, and says the registry file becomes canonical when it lands, enforced by a parity test.
- **Alternatives:** wait for the registry (blocks WS0 M2), or keep a second source table in `provenance.py`.
- **Why:** two tables of the same facts drift. One canonical direction (a fact names its source) and one test keep them honest.

**Names the plan left open.**
- **Decision:** the guide names `HIDE_CV_ABOVE = 0.50` and a reason-code vocabulary (`low_coverage`, `small_sample`, `high_cv`, `bracket_median`, `ai_unverified`, `old_source`, `stale`).
- **Why:** the schema PR needs fixed names. Choosing them in the docs PR makes the first code PR a review of an implementation, not of a vocabulary. These are flagged for WS0 M2 to confirm or change.

**Merge commits, not squash.**
- Matches the repo's history (#58, #59 were merge commits). One convention keeps `git log --first-parent main` readable as the queue.

**Numbers**
- **Thresholds are defaults, not measurements:** withhold if coverage < 10%, n < 30 or CV > 50%; fade if coverage < 25% or CV > 30%; comps fade under 5 sales and are withheld under 3. How many figures each rule would withhold is unmeasured until WS0 M3's audit script runs. Re-tune them against that count, not by feel.
- **Baseline coverage** *(measured by the planning session on 2026-10-20, not this one)*: 1601 N Milwaukee had 14 provenance entries across 9 kinds of fact, with about 55 other displayed figures uncovered. That is WS0's starting point.
- **CI:** test job 2 m 54 s; deploy correctly skipped as docs-only.
- **Reproduce:** `curl -s "https://urbanlayerchicago.com/api/scorecard?address=1601%20N%20Milwaukee%20Ave" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["provenance"]))'`

## Item 3: stale and empty cleanup (#61, 2026-10-20)

**Check the dataset's columns before trusting the plan's field list.**
- **Decision:** before removing fields, read the City dataset's metadata (`/api/views/t68z-cikk.json`). It has 30 columns: population, 5 income brackets, age/sex, race, and nothing else. So once the 2008–2012 set (`kn9c-c2s2`) was dropped, community-area poverty and unemployment would *also* always be empty. Removed **eight** fields, not the plan's five, plus the median-age "bracket midpoint", which isn't a median.
- **Alternatives:** remove exactly the plan's five and leave fields that can only ever be `None`.
- **Why:** an always-empty field on the model implies we hold the figure. The standard says nothing should imply that.
- **Revisit if:** community-area figures return via tract aggregation (the rents/market workstream). They come back as new, sourced fields with margins of error, not by reviving these.

**Keep the bracket-median income, but say what it is.**
- **Decision:** the community-area median household income stays, with a caption: "ACS 2019–2023 · income estimated from 5 brackets, no margin of error".
- **Alternatives:** remove it too.
- **Why:** it's the only community-area income figure, and the approved standard treats bracket medians as `low`, shown and labeled, not hidden. The caption also separates it from the tract block below it (ACS 2020–2024), so two vintages never sit side by side unlabeled.

**Delete the unreachable report block, not just its bug.**
- **Decision:** the report template's demographics block was unreachable. The report uses the Profile's fetch, which skips demographics (`workflow="property_intelligence"`), and the mock overrides don't set it. Removed the whole block and its catalog keys, not only the ×100 on values that were already percentages.
- **Alternatives:** fix the ×100 and keep the block.
- **Why:** dead template code is a trap. If the skip ever changes, it would silently print unlabeled bracket estimates in a paid report. Removing it means a future change has to add the block back deliberately, under the standard.

**Backward compatibility without a migration.**
- **Decision:** rely on pydantic ignoring unknown keys and on optional TypeScript fields. Stored conversations from before the change still load. Tests feed an old-shaped stored context through `ContextObject` and through the sidebar card, and assert the retired 2008–2012 numbers don't render.
- **Alternatives:** a migration that rewrites `messages.context_json`.
- **Why:** rewriting users' stored answers would also erase what they were shown. The display layer simply stops reading the retired keys.

**Unemployment from the right denominator, the period from the response.**
- **Decision:** tract unemployment = B23025005 ÷ B23025003 (unemployed ÷ *civilian* labor force), the Census definition. The column meanings were read from the live API's table metadata, not from memory. The ACS period comes from the response's `release.years`, not a hardcoded "2020–2024".
- **Why:** the label updates itself when Census Reporter's "latest" release moves. A hardcoded year would turn into the same unlabeled-vintage bug this item fixes.

**Fix the same defect class where it turned up.**
- **Decision:** while removing the ×100 bugs, found the opposite one. `arrest_rate` is a fraction (0.123), but it was printed unscaled in the transcript export (≈0.1%) and in the turn summary that later chat turns read ("0% arrest rate"). Fixed both, with a test.
- **Why:** the same class of defect, found by reading every consumer of a rate field, small and in scope. The turn-summary one fed a wrong number to the model on follow-up turns.

**Spanish: what counts as "new".**
- **Decision:** genuinely new strings (the two caption keys) carry English and are listed in `_untranslated.json`. *Existing* strings whose meaning changed ("Checked", the footprint label, the report's methodology text) were translated in-session.
- **Alternatives:** revert changed strings to English too.
- **Why:** leaving the old Spanish would keep a now-false claim (e.g. "ACS 2019–2023 demographics") in front of Spanish readers. Switching them to English would regress a working translation.

**Test design: assert on what the data adds, not on the whole page.**
- **Decision:** "no percentage over 100" compares a render with area figures against an empty render and checks only the percentages the figures add.
- **Alternatives:** a whitelist of known static percentages.
- **Why:** the first version failed on static glossary text (the LIHTC "basis boost of up to 130%"). The diff ignores static copy without a list that would need maintaining.
- **Related lesson:** a hand-computed expected value in the demographics test was wrong (106,666 vs the correct 111,111). The test caught it on the first run. Expected values for interpolations are now written with their derivation in a comment.

**Verification that can't be fooled.**
- **Before the mobile audit:** checked its route list for anything that sends a chat message (the no-tokens rule). `/?ask=1` only opens an empty workspace.
- **A suspicious result gets the raw data.** Locally, Brighton Park's tract showed poverty and unemployment both at 9.1%, which could mean a copy-paste bug. The raw Census counts (423/4,670 and 245/2,681) showed a coincidence.
- **The deploy check reads fields only the new code produces.** Tract `unemployment_rate` and `acs_period` appeared in the live `/api/scorecard` response. The bundle hash changed, and the new strings were present while the old ones were absent. That proves the running image, not just the server's git tree.

**Numbers** (measured 2026-10-20/21)

| Measure | Before | After | How measured |
|---|---|---|---|
| `DemographicsSummary` fields | 12 | 5 (incl. new `acs_period`) | the model |
| Socrata datasets loaded at demographics preload | 2 (`t68z-cikk`, `kn9c-c2s2`) | 1 | the code; `test_reads_only_the_acs_extract_never_kn9c` |
| Community-area figures from 2008–2012 in chat context/sidebar/export | 2 per area × 77 areas | 0 | the code; the sidebar old-context test |
| Census Reporter tables per tract request | 14 | 15 (+B23025) | `TABLE_IDS` |
| Live `/api/scorecard` provenance entries, 1601 N Milwaukee | 14 | 14 (unchanged, as intended) | live API, after deploy |
| Served bundle | `index-CSCu4C2y.js` | `index-bcwa5WYG.js` | live homepage |

Reference values (live, government sources):
- **Tract 8310** (1601 N Milwaukee), ACS 2020–2024: poverty 4.6%, unemployment 5.5% (96 / 1,736), median gross rent $2,435 ± $220 (CV 5.5%).
- **Brighton Park** (community area 58), ACS 2019–2023: population 42,360; bracket-estimated median income $58,661.
- **Tract 5805.01** (Brighton Park), ACS 2020–2024: poverty 9.1% (423 / 4,670), unemployment 9.1% (245 / 2,681).
- **`t68z-cikk` metadata:** 77 rows, 30 columns, one ACS year (2023), rows updated 2025-01-23.

Checks (after; the "before" counts weren't taken): `make test`: 1,462 backend + 88 eval + 290 vitest tests passed; `npm run test:mobile` 40/40 in 1.8 min; CI test job 2 m 15 s; diff 24 files, +339 / −286.

**Reproduce** (no model tokens):
- Dataset columns: `curl -s https://data.cityofchicago.org/api/views/t68z-cikk.json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d["columns"]),[c["fieldName"] for c in d["columns"]])'`
- Tract figures: `curl -s "https://api.censusreporter.org/1.0/data/show/latest?table_ids=B17001,B23025,B25064&geo_ids=14000US17031831000"`. Poverty = B17001002 / B17001001; unemployment = B23025005 / B23025003.
- Live: the scorecard `curl` in item 2, reading `context.neighborhood.census_tract`.

**Not measured:**
- Latency cost of adding B23025 to the tract request (one more table in the same call; expected to be small, unverified).
- Chat answer quality after removing the community-area fields (a `make kit` chat run would spend production tokens; the monthly production kit run will show it).
- `eval.lot_coverage` (unaffected in principle: no parcel fields changed).
