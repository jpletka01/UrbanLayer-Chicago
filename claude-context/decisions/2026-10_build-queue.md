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

## Item 4: ingestion safety + prod push tool (WS1 M0, #63, 2026-10-21)

**A parse is not an ingest.**
- **Decision:** the parser no longer writes `backend/code_vintage.json`. `ingestion.update` writes it only after the embed finishes and the collection's point count equals the staged chunk count. The file now also records `ingested_at`, `chunk_count`, `collection` and `export_sha256`.
- **Alternatives:** keep writing the vintage at parse time, and tell people not to commit it after a dry run.
- **Why:** the old `--dry-run` ran the parser, which rewrote both `sections/` and the vintage file. Committing that would have claimed newer text than Qdrant served.
- **Revisit if:** the prod index can ever be written without going through `update` (it can't today; `push_index` copies a finished local collection).

**Bookkeeping fields stay out of the API and chat.**
- **Decision:** `get_code_vintage()` returns only `current_through`, `label` and `source`. The new fields come from `get_code_vintage_record()`.
- **Alternatives:** return the whole file.
- **Why:** the dict is serialized into the chat context and `/api/scorecard`. Collection names and hashes there cost tokens and help no user.

**Staged parse with a swap, rather than clearing `sections/` first.**
- **Decision:** a full parse writes `<dir>.tmp` and renames it over the target at the end, logging the ids that disappeared. A `--title` parse writes in place and deletes nothing.
- **Alternatives:** `rmtree(sections)` before parsing.
- **Why:** a crash or a bad export mid-parse would leave an empty or partial corpus. A one-title parse that cleared the directory would delete every other title.

**Retitles are caught by a separate `title_hash`, not a wider `content_hash`.**
- **Decision:** the manifest gets a second hash over every heading field a chunk header prints (section title plus the title, chapter, article, subarticle and part names). `diff_manifests` counts a change in either hash. A `None` title hash (manifests written before this item) never counts as a change.
- **Alternatives:** add `section_title` to `content_hash`.
- **Why:** that was tried and reverted on 2026-09-07. It changes every hash, forces a full re-embed, and trips the zoning-cache fingerprint (keyed on `content_hash`) for 147 unchanged Title 17 sections.
- **Note:** the local manifest was rebuilt with `update --manifest` after a fresh parse matched it exactly, so the next refresh compares titles too.

**Per-vintage collections behind an alias; the prod copy keeps ids and vectors.**
- **Decision:** a new vintage is embedded in full into `municipal_code_<vintage>`, and the app reads the alias `municipal_code`. `push_index --upload` copies points with their ids and vectors, `--verify` compares per-section multisets of chunk-text hashes, and `--switch` re-verifies before the atomic alias flip.
- **Alternatives:**
  - keep one collection and patch it incrementally over the tunnel (the old way);
  - copy unchanged points forward into the new collection and embed only the changed ones.
- **Why:**
  - the old way used `uuid4` ids, so a missed delete duplicated rows, and nothing checked the result;
  - copy-forward is faster, but it silently reuses stale vectors if the chunker changes between vintages. A full local embed of about 16.6k chunks is cheap, and this is a monthly-at-most job.
- **Same vintage (a parser fix) is updated in place** in the served collection: removed and modified sections deleted, added and modified ones embedded. `--full` on the served vintage is refused, because rebuilding the collection being served takes it offline.
- **Revisit if:** refreshes become frequent enough that the full embed time matters.

**Abort gates follow the plan, plus two exceptions found while testing.**
- **Decision:**
  - same-vintage re-ingests don't trip the "vintage ≤ old" gate (a parser fix is legitimate); only a vintage going backwards does;
  - a first-ever ingest skips the title-shape gates;
  - a brand-new title trips a gate, so a person looks at it.
- **Evidence (the June 17 export, dry run only, nothing applied):**
  - 37 added, 149 modified, 71 deleted; 7 Title 17 sections changed;
  - the Title 13 gate tripped: all 71 sections of chapter 13-208 are gone;
  - the export's editor's note confirms a real repeal (Coun. J. 6-17-26, temporary overnight shelters). M4 will apply it with `--force` after review. The gate did its job.

**Plan defect (d) was already fixed; no fixtures directory added.**
- **Decision:** dropped the planned `backend/tests/fixtures/code_sections/`.
- **Alternatives:** build it anyway.
- **Why:**
  - the 14 pinned sections have been committed in place under `ingestion/data/sections/` (via `.gitignore` exceptions) since `5072fbb`;
  - CI already runs those tests: the last `main` run had 1,461 passed and 1 skipped (the export-header test);
  - a second copy would need its own sync check. The in-place copies refresh automatically when M4 re-parses, and the git diff shows the change.

**Found along the way: two section files missing locally.**
- `ingestion/data/sections/` held 9,485 files against a 9,487-entry manifest. `17-4-0200` and `17-5-0200` were missing, though their chunks were in `chunks.jsonl` and Qdrant.
- A fresh parse of the same export produced both, identical to the manifest, so they were restored.
- The cause is unknown: the directory was modified 2026-10-09, and nothing in the repo deletes section files. This was the "9,485 vs 9,487" the plan read as stale leftovers.

**The answer key carries its own code vintage.**
- **Decision:** `eval/kit/parcels.json` gains `code_current_through`. The benchmark and the review packet read it.
  - `eval/tests/test_code_vintage_sync.py` fails when it differs from `backend/code_vintage.json`, or when EVALS.md quotes another date.
  - The About page row reads `lib/kitVintage.ts`, which a vitest pins to the key.
- **Alternatives:** read `backend/code_vintage.json` directly.
- **Why:** the key was built against specific text. After a refresh, the live vintage would claim the key covers newer law before anyone re-checked it. The failing test makes M4 re-check the key.

**Numbers** (measured 2026-10-21, local)

| Measure | Before | After | How measured |
|---|---|---|---|
| Files changed under `sections/` and in the vintage file by `update --dry-run` | every section file rewritten, plus the vintage file | 0 (byte-identical) | `shasum` of every file before/after the dry run |
| Dry-run changes on the current export (2026-03-18) | n/a | 0 added / 0 modified / 0 deleted, gates pass | `python -m ingestion.update --dry-run` |
| Dry-run wall time (parse + chunk + diff) | n/a | 13.5 s | `/usr/bin/time -p` on the same command |
| June 17 export, dry run | n/a | 9,487 → 9,453 sections, 16,576 → 16,584 chunks; 37 / 149 / 71; 1 gate (Title 13) | `python -m ingestion.update --dry-run --source chicago-il-1-june.html` |
| Local collections | `chicago_municipal_code` (16,576) | `municipal_code_2026-03-18` (16,576) behind `municipal_code` | `push_index --target http://localhost:6333 --status` |
| Local copy check (snapshot copy vs original) | n/a | 0 sections differ, 16,576 = 16,576, 1.9 s | `push_index --verify --collection municipal_code_2026-03-18 --target-collection chicago_municipal_code` |
| Prod before the migration: local vs prod `chicago_municipal_code` | unchecked since 2026-09-28 (count only) | 0 sections differ, 16,576 = 16,576 | `push_index --target <tunnel> --verify --collection municipal_code_2026-03-18 --target-collection chicago_municipal_code` |
| Prod server-side copy to `municipal_code_2026-03-18` | n/a | 16,576 points in 3.5 s, re-verified 0 differences, alias `municipal_code` created | `push_index --target <tunnel> --snapshot-copy chicago_municipal_code --collection municipal_code_2026-03-18`, then `--verify`, `--switch` |
| Backend tests | 1,462 | 1,483 (+21 in `test_ingestion_pipeline.py`) | `make test` |
| Eval tests / vitest | 88 / 290 | 90 / 292 | `make test` |

**Not measured:**
- The full-embed time for a new vintage (no new vintage was applied; M4 measures it).
- Upload time over the tunnel (no upload ran; the prod migration used a server-side snapshot copy).
- Live latency through the alias vs the old name (expected the same: an alias is a name lookup; checked only that `/api/code/section/17-2-0304-A` answered 200 in 1.1 s before the deploy).
- Whether any heading-only change exists between the March and June exports beyond what the content diff shows (the old manifest had no title hashes; the June dry run compared titles from the rebuilt one).

## Item 5: City Clerk API client (WS1 M1, #64, 2026-10-21)

**"Passed" includes "Signed".**
- **Decision:** a matter has passed when `status == "90-Final"` and `subStatus` is one of `Passed`, `Passed as Substitute` or `Signed` (plus `Adopted`, `Approved` and `Approved as Substitute`, which resolutions and orders end with).
- **Alternatives:** the plan's rule, `subStatus` starts with "Passed".
- **Why:** 4 of the 59 main-category code amendments since March 18 end "Signed". One of them is SO2026-0024930, the 2026-06-17 omnibus amendment to Titles 2, 14, 17 and 18. The plan's rule would have dropped a Title 17 amendment.
- **Vocabulary:** final `subStatus` values over a year of records (8,639 rows, 2025-10-01 to 2026-10-21) are pinned as `KNOWN_FINAL_SUBSTATUSES`. An unknown value is contract drift for the sync to flag, not something to guess about.
- **Revisit if:** the live contract test sees a new final status.

**Categories are matched as a string range, not with `eq`.**
- **Decision:** `category_filter` sends `matterCategory ge 'X' and matterCategory lt 'X'+1`, with several categories OR'ed in one request.
- **Alternatives:**
  - `eq` misses subcategories;
  - `startswith` and `contains` return HTTP 400 (both tried);
  - filtering only on status and date and checking categories client-side would page through about 8.6k rows a year.
- **Why:** code amendments also come as subcategories ("MUNICIPAL CODE AMENDMENTS | 4-60-023 Package Goods", mostly liquor moratoria). Since March 18 that is 100 records, not 59. The range filter returns them in one page.

**The plan's "54 passed code amendments" is 97 on current data.**
- **Why:** the plan counted the main category only, without "Signed". Main category: 59 final = 52 Passed/Passed as Substitute + 4 Signed + 2 Failed + 1 Vetoed. With subcategories: 100 final, 97 passed.
- **The Title 17 count is unchanged at 16.** Subcategories add none, and "Signed" adds the omnibus, which the plan's 16 already counted by title.

**Title 17 = the title names Title 17 or a `17-x` section.**
- **Decision:** a regex on the title.
- **Alternatives:** keyword matching ("zoning", "transit", "pedestrian").
- **Why:** keywords pull in O2026-0026413 (Chapter 9-64, parking under CTA tracks). The section-number rule gives exactly the 16 on live data.
- **Limits:** `touched_sections` and `kind` come from the title (`sections_confidence = "title"`) until M2's reviewed file replaces them. `addresses` stays empty until M2/M5.

**The passed text of a substitute is the Legislation PDF named for the SO number.**
- **Decision:** prefer one with "Final" in the name, else any SO-named one.
- **Alternatives:** match on "Final" only.
- **Why:** TOD Streets (SO2026-0025391) has its passed text as `SO2026-0025391.pdf`, with no "Final". Matching on "Final" would have picked the original `O… Ordinance.pdf`, which is not what passed.

**Failure contract and politeness, as planned, plus one fix.**
- Every function raises `ClerkUnavailable` and never returns `[]`. That covers a failed page mid-pagination and a short page.
- A 400 raises `ClerkQueryError` and is not retried. 5xx and network errors get 3 tries with 1/2/4 s backoff.
- Pages are fetched serially with a 1 s pause, and calls are cached for 6 h.
- **Fix found by the live test:** the shared `httpx.AsyncClient` is bound to the event loop that made it. A module-level client failed with "Event loop is closed" the second time `asyncio.run` (or a new pytest loop) used it, which the daily sync could have hit.
- **Evidence:** a transient failure was seen live once while paging. It succeeded on retry.

**Numbers** (live API, 2026-10-21)

| Measure | Value | How measured |
|---|---|---|
| Passed code amendments after 2026-03-18 (incl. subcategories) | 97 (plan: 54, main category only) | `python -m backend.retrieval.clerk passed-since 2026-03-18` |
| Title 17 amendments after 2026-03-18 | 16 | `python -m backend.retrieval.clerk title17 2026-03-18` |
| Newest `recordCreateDate` | 2026-10-20T22:01:07Z; the newest `introductionDate` in the same window was 2026-12-08 | `python -m backend.retrieval.clerk latest` |
| Final records 2025-10-01 → 2026-10-21 | 8,639 (18 pages of 500; 1–3 s per page) | the recorded survey request, `filter=status eq '90-Final' and finalActionDate gt 2025-10-01T00:00:00Z` |
| Backend tests | 1,483 → 1,510 (+27 offline Clerk tests); +5 live contract tests (integration) | `make test`; `pytest backend/tests/test_clerk_contract.py -m integration` |

**Not measured:**
- How often the API fails over a day. Only one transient failure was seen; WS6's probe will measure the rate.
- Behaviour above about 20k matching records (guarded by `max_records`, untested live).

## Item 6: amendments since the code vintage (WS1 M2)

**`codified` means "in the code text we serve", and all 23 seeds are `false`.**
- **Decision:** the review file's `codified` flag is about our text, not American Legal's. Every amendment passed after our March 18 vintage starts `false`; M4's codification check flips the ones the June 17 export contains.
- **Alternatives:** `null` ("not checked yet") until M4.
- **Why:** the degradation rule lists committed `codified: false` entries even when the Clerk can't be checked. With `null`, a Clerk outage would have hidden TOD Streets, the one the plan names as must-not-disappear.
- **Revisit if:** we ever serve two code texts at once.

**Summaries are null until someone reads the ordinance; only TOD Streets has one.**
- **Decision:** `summary` stays null for the 22 title-only seeds, with `summary_basis` saying where a summary came from (`ordinance` for SO2026-0025391, read in full during the 2026-10-20 research). The prompt rule says: with no summary, say only what the title names, and infer nothing.
- **Alternatives:** the plan's "summaries from their titles".
- **Why:** a title copied into `summary` would read as a reviewed description everywhere it shows (Profile, report, chat). The gas-station title "prohibit issuance of permits for gas stations in B3, C1 and C2" is easy to over-read as "B3 bans gas stations outright".
- **Revisit if:** §3.7 reviews land (M4/M4b); each sets `summary`, `review_status: reviewed` and `product_effect`.

**Other cited titles = an explicit prefix list: 7 records, not the plan's ~6.**
- **Decision:** `CITED_PREFIXES` covers Title 14, 2-44, 2-45-165 (exactly), 2-120 and 18-14.
- **Why:**
  - The plan's "2-44-070 (repealed)" is O2026-0024022, whose title leads with a new 2-4-130 and repeals 2-44-070 at the end. With 2-44-140 and 2-44-170, Chapter 2-44 is three records.
  - The prefix is `2-45-165`, not `2-45`, so the MBE database (2-45-150, SO2024-0012388) stays out.
  - Recorded live list: 97 passed, 16 Title 17, 7 cited other, 74 other (the classifier test pins all four numbers).
- **Revisit if:** the product starts citing another chapter (add it to the list and the test).

**A chapter named only as the place a new section goes is dropped.**
- **Decision:** "Chapter 17-3 by adding Section 17-3-0600" yields `17-3-0600`, not `17-3` + `17-3-0600`. A lone chapter ("Chapter 17-9 regarding waste-related uses") is kept. "17-9-0109A" is normalized to `17-9-0109-A`.
- **Alternatives:** keep the M1 client's raw list.
- **Why:** with `17-3` kept, every business-district section (bulk table, use table, pedestrian streets) would have been "amended by TOD Streets".

**Overlap rules: same section, subsection, chapter, or indexed article. Never a sibling, never a decimal neighbour.**
- **Why:**
  - The plan's acceptance number is 3 amendments on `17-3-0503-D`, and that is what these rules give.
  - `17-9-0129.1` is a separate section from `17-9-0129` (the cannabis amendment names both), so `.` is not a segment boundary.
  - The chunk endpoint gets article ids (`17-3-0500`), so an article must match the sections inside it.

**What makes an amendment "parcel-relevant".**
- **Decision:** a parcel's cited sections are:
  - the bulk-standard sections for its district family;
  - its family's use table (17-x-0207);
  - its overlays' sections (ADU 17-7-0574, transit 17-10-0102-B, landmarks 2-120-740, the Milwaukee Ave SCO article 17-7-1500);
  - the CHRS hold 14A-4-407.6 when orange or red.

  Map effects match by address:
  - a TOD street needs the number range;
  - a pedestrian-street removal without a range needs the parcel to still show the overlay;
  - an addition without a range matches nothing.
- **Alternatives:**
  - map the pedestrian-street overlay to 17-3-0503;
  - match street additions on the street name alone.
- **Why:**
  - §17-3-0503-D is the *list* of designated streets. Adding Belmont doesn't change a Halsted parcel's rules, and the first version flagged all three street amendments for every pedestrian-street parcel.
  - A name-only match would flag every Belmont or Clark parcel when only some segments were designated.
  - Live results: 1601 N Milwaukee (B3-2) flags only SO2026-0024923, the B3 gas-station rule. 4000 N Western (B3-2, in tests) flags TOD Streets and the gas-station rule.
- **Revisit if:** M4b transcribes the Belmont, Clark and Lawrence segments (add `from`/`to`), or a parcel-geometry abutment check replaces address ranges for TOD streets.

**A stale snapshot's rows stay listed; only the count needs a fresh check. A suspect snapshot's rows are dropped.**
- **Why:** a law that passed stays passed, so old rows are still true. But a check that saw an unknown `subStatus` or a vanished record may be reading garbage. The count (including "none") follows plan §5.6 exactly: fresh < 72 h, "as of <date>" to 14 days, then withheld.

**Sync failure modes are distinct exits.**
- **Decision:**
  - exit 1 = unreachable: the last good rows and `checked_at` are kept and the failures counted;
  - exit 2 = suspect;
  - both go to Sentry and leave the systemd unit failed.
- **Why:** WS6 M2's alarms need "couldn't check" and "checked and found something wrong" apart. The M1 client already raises instead of returning `[]`.
- **Added to the client:** `clerk.final_since` returns all final outcomes (not just passed), so the sync can see an unknown `subStatus` that `passed_since` would silently drop.

**The timer runs at 06:00 Chicago time via `OnCalendar=... America/Chicago`.**
- **Why:** the server runs UTC. `systemd-analyze calendar` on the server (systemd 259) normalizes it and gave the next run as 11:00 UTC.

**The Profile note gets a new id, `code_currency`.**
- **Decision:** a new id replaces `code_vintage` whenever currency data exists. `code_vintage` remains the fallback.
- **Alternatives:** keep the old id.
- **Why:** the frontend renders a known id from its i18n key and an unknown one from the note's English `text`. A new id lets the count show on prod before M3 adds the translated keys; the old id would have kept showing the old sentence with no count. Spanish users see English for this one note until M3/WS7.

**A section the text lacks returns a 404 with a structured detail, not a 200.**
- **Why:** existing clients treat 200 as "here is code text". `detail.added_by` carries the ordinance, and M3 renders it.

**Chat gets a compacted `code_currency`.**
- **Decision:** full rows only for amendments that touch the parcel or a retrieved chunk; record, date and title for the rest; no URLs (the Sources footer links them).
- **Why:** 12,063 → 5,062 characters on the 1601 N Milwaukee context, about 1.75k fewer input tokens on every parcel turn (estimated at ~4 chars/token). Every chat turn is a production cost.

**The report shows the parcel's rows in the zoning section; the full list goes in Data Sources.**
- **Why:** the full 16-row table pushed Bulk & Density two pages down on 1601 N Milwaukee. The zoning section now shows the sentence, this parcel's row and a pointer.

**One shared report renderer.**
- **Decision:** `render_report_html()` is extracted from `/api/report`. Four report tests that each copied the Jinja setup now call it.
- **Why:** the new `rdate` filter would otherwise have needed adding in five places, and that duplication is how a test renderer drifts from production.

**Deferred to M7, as the plan's table says:** the `ci.yml` warn step. `currency_check` is built and tested.

**Process slip, recorded so it isn't repeated:**
- **What happened:** a bare `pytest backend/tests` (without `-m "not integration"`) ran `test_balcony_clarification`, which calls the Anthropic API. The call was rejected ("credit balance is too low"), so nothing was spent.
- **Rule:** build work runs `make test` or `-m "not integration"` only.

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Passed code amendments after the vintage (live Clerk) | 97 total: 16 Title 17, 7 cited other | `python -m backend.legislation.sync --print` |
| Profile JSON, 1601 N Milwaukee | no amendment data → 16 listed with Clerk links, 1 parcel-relevant, `check_state: fresh` | `curl localhost:8001/api/scorecard?address=1601+N+Milwaukee+Ave` (local backend + local snapshot) |
| Same, snapshot deleted | → `since: null`, note says "We couldn't check…", 16 still listed from the review file | the same, with `backend/data/legislation_snapshot.json` moved aside |
| `amended_since` on `/api/code/section/17-3-0503-D` | absent → 3 (Belmont, Clark, Lawrence) | `curl localhost:8001/api/code/section/17-3-0503-D` |
| `code_currency` in the chat payload (1601 N Milwaukee) | 12,063 → 5,062 chars (parcel context: 49,327 chars before compaction) | `json.dumps(ctx["code_currency"], indent=2)` vs `currency.for_model(...)` |
| Report PDF, 1601 N Milwaukee | new block on page 5 of 22 | `curl localhost:8001/api/report?address=1601+N+Milwaukee+Ave -H "Cookie: session=dev"` then `pdftotext` |
| Backend tests | 1,510 → 1,566 (+54 in `test_legislation_currency.py`, +1 coverage note, +1 i18n guard) | `make test` |

**Not measured:**
- What the extra computed field costs per request on `/api/scorecard`: two mtime-cached JSON reads plus section matching, never timed.
- Chat answer behaviour under the extended rule 34. That needs a live model, which build work may not spend; the first real parcel chat after the deploy is the check.
- Which Title 17 sections the omnibus (SO2026-0024930) touches: it has no section list until M4 reads it, so `amendments_touching` never returns it.
- Prod's first sync run (after the timer is installed).
