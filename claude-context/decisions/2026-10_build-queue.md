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

## Item 6: amendments since the code vintage (WS1 M2, #65, 2026-10-21)

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

## Item 7: code text refresh to the June 17 export (WS1 M4, #66, 2026-10-21)

**The Title 13 gate was a real repeal, and bigger than item 4 recorded.**
- **Decision:** applied with `--force` after reading the export's editor's notes.
- **Evidence:** the 71 deleted sections are three chapters, not one: 13-84 (45, assembly units), 13-208 (20, temporary overnight shelters) and 13-212 (6, transitional shelters). Each chapter now reads "Reserved", with a note citing Coun. J. 6-17-26, p. 45214, Art. IV §§18, 20 and 21. That is the building-code omnibus, SO2026-0024930, though its title lists Titles 2, 14, 17 and 18, not 13. Item 4's note said "all 71 sections of chapter 13-208"; the per-chapter count corrects it.
- **Revisit if:** a gate trips on a refresh with no editor's note to explain it. That would be a parser regression, not law.

**Title 14 dots are subsections; Title 17 dots are not.**
- **Decision:** `sections_overlap` treats `14X-8-802.2.2` as inside `14X-8-802` (any `14<letter>-` id), and keeps `17-9-0129.1` separate from `17-9-0129`.
- **Alternatives:** match the amendment's dotted ids against the corpus ids by hand in the review file.
- **Why:** the codification check reported SO2026-0024086 (the 14X heat dates) as MISSING although 14X-8-802 carries its 5-20-26 citation. The corpus indexes Title 14 at the three-part section (`14X-8-802`), and the IBC-style numbering puts subsections after a dot. The same rule keeps CHRS's `14A-4-407.6` inside `14A-4-407`. Four overlap cases pin it.
- **Revisit if:** a Title 17 section is ever numbered with a dot subsection.

**Codified is decided from the text, not only from the check.**
- **Decision:** the check's nine matches were each confirmed against the section diff. Where the title and the diff disagreed, the passed ordinance was read (four PDFs: three scans read visually, one with a text layer).
- **What the reading changed:**
  - **SO2025-0021852** is titled "§14A-3-306 stop-work orders and §14A-4-406 excavation", but the substitute that passed doesn't touch 14A-3-306. It amends 4-36-010, 4-36-030 and 14A-4-406, and that's the section list now.
  - **SO2026-0024923** (gas stations): the substitute changes the 17-3-0207 row for B3, C1 and C2 from S to "-". That row is identical in the March and June exports, because the "March 18" export was downloaded on May 28, after passage, and already carried the new row. The March text was newer than its header in at least this one place.
  - **O2026-0024064** (waste uses) is narrower than its title. It is one exemption, for C2 container storage of up to 20 containers, from 17-9-0117-A and -G.1.
- **Revisit if:** never; this is the review rule (plan §3.6: no number without the text in hand).

**The omnibus is partly codified, and the review file can now say so.**
- **Decision:** SO2026-0024930 stays `codified: false` with a new `codified_partly: true`. Its `sections` list only the parts not in our text: Titles 14M, 14G and 14N (repealed and replaced effective 2026-10-01), Chapters 18-28 and 18-36 (repealed 2026-12-01), 14B-9-913/915 (Art. IV §§30–31) and the Art. V residential sections. `codification_check` reports such an entry as "partly", says whether its pending sections changed in a later export, and never flips the flag.
- **Alternatives:**
  - `codified: true` (the check's answer): this would drop it from every list, though the 14M/14G/14N text chat retrieves has been superseded since October 1;
  - leave it `false` with no marker: the next `--write` would flip it, because its §17-17 changes match by date.
- **Also:** its `relevance` is overridden to `cited_other` (`relevance_basis: review`). Its Title 17 part (Art. IV §44, the 17-17 definitions) is in the text. Counting it among "Title 17 amendments not in this text" would overstate the zoning gap on every Profile.
- **Known limit:** the check matches by Journal date, so it can't tell the articles apart. Today it already flags 14B-2-202 and 14B-10-1011 for re-review. Both changed on 6-17-26 under Art. IV (§§23, 32, which are in the text), while their Art. V changes are still pending. The flag only asks a person to look, which is the safe direction.
- **Revisit if:** an export carries the new 14M/14G/14N. The check then lists the changed sections for re-review.

**One product change: C1 and C2 use summaries.**
- **Decision:** "auto-oriented commercial" (C1) and "nearly any business" (C2) now add "no new gas stations, §17-3-0207". A test pins every B/C summary to the use-table row: C1 and C2 must say it while the row says "-", and the other families mustn't mention gas stations.
- **Alternatives:** leave it to chat, which retrieves the table.
- **Why:** these strings reach the Profile's zoning card and the $25 report verbatim, and both read as allowing a gas station. Everything else codified here lands in sections no deterministic rule reads (PPA buffer, Wrigley signs, Cicero overlay, 17-17 definitions, Title 14), so chat answers from the new text with no code change.

**The zoning cache is kept; only its fingerprint moves.**
- **Decision:** no `zoning_cache_build` run (it spends the production key). Instead:
  - `--check` reported the cache stale because the Title 17 fingerprint covers every section;
  - the five sections the builder reads (17-2-0300, 17-3-0400, 17-4-0400, 17-5-0400, 17-10-0200) have identical `content_hash` in both manifests;
  - so `_meta.corpus_fingerprint` is re-stamped to the new corpus, with a `_meta.fingerprint_rebased` note giving the date, the reason and the sections checked.
- **Alternatives:**
  - leave it stale: every later `--check` and WS6's artifact-age check would cry wolf;
  - narrow the fingerprint to the sections the builder reads: cleaner, but it changes `test_corpus_fingerprint_only_tracks_title_17`'s contract mid-refresh.
- **Revisit if:** a refresh changes one of those five sections. Then setbacks need a hand re-read (build-order item 7), or a build once a production run is approved.

**The kit's note expectation had gone stale at item 6; fixed here.**
- **Decision:** the key's `coverage.must` now expects `code_currency` instead of `code_vintage` on all 12 parcels, with a `corrections` entry saying why. The kit test is updated to match.
- **Why:** #65 replaced the note id whenever amendment data exists, which on prod is always. Since then the Profile kit has reported "0/12 parcels carry exactly their notes" on prod, on a product that was right. It was found by the first Profile kit run after #65, which is this one.

**The answer key moves to the new vintage without value changes.**
- **Evidence:** the keyed fields cite 17-2-0207/0300s, 17-3-0207/0400s, 17-4, 17-5-0204/0207/0404, 17-6-0204, 17-7-0573/0574/0591, 17-8-0512, 17-10-0102 and 17-13-0302/0600. The refresh changed none of them (17-3-0207's content is identical; see above). So `code_current_through` → 2026-06-17 and version 2026-10-21.1, with no `corrections` entry. The Profile-only kit was re-run locally and against prod (no chat, no model calls).

**Found along the way, not fixed here: section viewers 404 for chapter 17-7's overlay articles.**
- `/api/code/section/17-7-0574` (ADU) and `/17-7-0591` (606) return 404 on prod today, and the new `17-7-0510` (Cicero overlay) does the same.
- **Cause:** `code_sections.article_id` rounds a section down to the nearest `…00` article (17-7-0500). Chapter 17-7's articles start at 0510, 0550, 0570, 0580 and 0590.
- It's an existing bug: it's on prod against the March text, and the Profile cites both sections. Raised as its own follow-up, so this PR stays the refresh.

**Numbers** (2026-10-21; local unless marked prod)

| Measure | Before → after | Reproduce |
|---|---|---|
| Sections / chunks | 9,487 / 16,576 → 9,453 / 16,584 (37 added, 149 modified, 71 deleted; Title 17: 6 modified, 1 added; 1 gate, Title 13) | `python -m ingestion.update --dry-run` (13.3 s) |
| Full local embed + promote into `municipal_code_2026-06-17` | 354 s wall, 16,584 points = chunk count | `/usr/bin/time -p python -m ingestion.update --force` |
| Codification check, the 9 amendments passed after 2026-03-18 and on or before 2026-06-17 | 8 codified + 1 MISSING (Title 14 dot bug) → 8 codified + 1 partly (reviewed), 0 unexplained | `python -m backend.legislation.codification_check --diff ingestion/data/diff/2026-06-17/diff.json --sections ingestion/data/sections` |
| Corpus-pinned suite (8 files) on the new text | 6 failures, all hard-coded vintage dates → 188 passed; no table, number or citation change needed | the §3.6 pytest command, `-m "not integration"` |
| Zoning cache | STALE (fingerprint `4321bf04…`) → FRESH (`707f181e…`), entries untouched; the builder's 5 source sections have identical `content_hash` | `python -m backend.zoning_cache_build --check` |
| Profile JSON, 1601 N Milwaukee: `code_currency.since` | prod (March text) `{title17: 16, cited_other: 7}`, 1 parcel-relevant (SO2026-0024923) → local `{title17: 10, cited_other: 5}`, 0 parcel-relevant | `curl "<host>/api/scorecard?address=1601+N+Milwaukee+Ave"` |
| Profile kit, 12 parcels | prod before (March text): 117/122, 0 CW, A 12/12 → local after: 117/122, 0 CW, A 12/12; **0 of 12 parcels' field scores differ** | `PYTHONPATH=. python -m eval.parcel_kit --full <host> --surfaces profile` |
| Kit coverage panel (notes that apply) | 0/12 (stale `code_vintage` id) → 12/12 | same run, after the key fix |
| Tests | backend 1,566 (item 6's record) → 1,598; eval 90 → 90; vitest 292 → 292 | `make test` |

**Not measured:**
- Chat answers on the new text (no live model in build work). The first prod chat that cites a changed section is the check, plus next month's approved chat kit.
- Retrieval quality on the new index (no `--judge` eval). What's known: 16,584 points; sections' chunk-hash multisets are compared on push by `push_index --verify`.
- The kit run's `code` field reads `5347b8c` (main's HEAD): the run used this branch's uncommitted working tree.

**Prod push and deploy** (2026-10-21, prod)

| Step | Result | Reproduce |
|---|---|---|
| Tunnel target, found without `sudo` | Qdrant answered on the Docker bridge address listed in the server's `ip -4 neigh` table (no `docker inspect`, so no password) | `ssh urbanlayer-prod 'ip -4 neigh show'`, then `curl <addr>:6333/` on the server |
| `push_index --upload` | 16,584 points to `municipal_code_2026-06-17`, 41 s | `python -m ingestion.push_index --target <tunnel> --upload` |
| `push_index --verify` | 0 sections differ, 16,584 = 16,584, 20 s | `--verify` |
| `push_index --switch` | re-verified 0 differences; alias `municipal_code_2026-03-18` → `municipal_code_2026-06-17` | `--switch` |
| Merge to live vintage | 279 s from merge to `/api/code/section/17-2-0304-A` returning `current_through: 2026-06-17` | `curl https://urbanlayerchicago.com/api/code/section/17-2-0304-A` |
| Live Profile, 1601 N Milwaukee | `since {title17: 10, cited_other: 5}`, 0 parcel-relevant; note reads "current through the Council Journal of June 17, 2026 … 10 amendments" | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |
| Live C2 summary (368 W Chicago, C2-5) | carries "(no new gas stations, §17-3-0207)" | same, `zone_definition.uses` |
| Profile kit on prod, after vs before the deploy | 117/122, 0 CW, A 12/12, notes 12/12; **0 of 12 parcels differ** | `PYTHONPATH=. python -m eval.parcel_kit --full https://urbanlayerchicago.com --surfaces profile` |

Prod still holds `chicago_municipal_code` (pre-migration, 16,576 points, unserved; item 4 meant to drop it) and `municipal_code_2026-03-18` (the rollback). Both can go at the next refresh with `push_index --drop`.

## Fix: the section viewer finds chapter 17-7's off-hundred articles (standalone, not a queue item, 2026-10-21)

Found during item 7 (above). `/api/code/section/17-7-0574` (ADU) and `/17-7-0591` (606) returned 404 on prod although the Profile cites both: `article_id` rounded every section down to its `…00`, and chapter 17-7 indexes articles at 0450, 0510, 0550, 0560, 0570, 0580 and 0590.

**Which article holds a section is read from the index, bounded by the hundred.**
- **Decision:** `article_id` returns the largest indexed id in the same chapter that is ≤ the section and in the same hundred. With none, it falls back to the old `…00` rounding. The ids are registered by `set_indexed_sections`, which `vector_search._get_known_sections` calls on its one-time Qdrant scroll. The endpoint awaits that scroll before resolving, so a cold process doesn't fall back. `codification_check` registers the export's own sections from `--sections`.
- **Alternatives:**
  - a hard-coded table of chapter 17-7's articles: goes stale on the next refresh that adds an overlay (17-7-0510 was new in this one);
  - read `ingestion/data/sections/`: not in the image (`.dockerignore`), so prod would always fall back;
  - plain "largest ≤" without the hundred bound: an uncodified 17-3-0600 (TOD Streets) would resolve into 17-3-0500, so amendments to it would read as touching 17-3-0500 (the new test pins this);
  - pass the index into every `sections_overlap` call: `currency` and `chat_sources` are sync and offline, and they have no index at hand.
- **Why:** the index is the only source that's both on prod and current. Process state is a fair price because it degrades to exactly the old behavior when Qdrant is unreachable. `amendments._is_article` now follows the same rule, so 17-7-0570 ⇄ 17-7-0574 overlap, and 17-7-0500 (Burling Street) no longer claims ADU amendments.
- **Not changed:** an article-level id on the subsection endpoint (`/api/code/section/17-7-0510`, and `/17-2-0300` before this fix too) is still 404 ("not found in 17-7-0510"): the article's body has no heading paragraph of its own. Whole articles are served by `/section/{id}` (`/section/17-7-0510` is 200 on prod). Its sections 17-7-0511 to 0513 now open.
- **Revisit if:** an article spans more than a hundred, or a chapter indexes a section beside its article in the same hundred (it would claim the ids above it). Neither is in the 2026-06-17 index.

**Scan: off-hundred four-digit ids across the index** (2026-06-17 `chunks.jsonl`: 9,107 sections, 531 four-digit ids in 28 chapters)
- Title 17, articles off the hundred: **17-7** (0450, 0510, 0550, 0560, 0570, 0580, 0590) and **17-11** (0050). These are the only ones the bug affected.
- Outside Title 17, 10 chapters number *sections* by tens: 2-32 (19), 2-92 (7), 4-156 (7), 10-28 (15), 11-4 (170), 13-96 (23), 15-16 (54), 15-24 (21), 15-28 (20) and 18-28 (4). Each is its own indexed record. The old rounding sent 11-4-1010 to a non-existent 11-4-1000; it now maps to itself. The Profile cites none of them, and chat opens them through `/section/{id}`, which never used `article_id`.

**Numbers** (2026-10-21)

| `GET /api/code/section/…` | prod before | local after |
|---|---|---|
| 17-7-0574 (ADU) | 404 "not found in 17-7-0500" | 200, article 17-7-0570 |
| 17-7-0591 (606) | 404 | 200, article 17-7-0590 |
| 17-7-0513 (Cicero overlay) | 404 | 200, article 17-7-0510 |
| 17-7-0510 (the article id) | 404 | 404 (unchanged contract, see above) |
| 17-2-0304-A / 17-3-0503-D | 200 / 200 | 200 / 200 (articles 17-2-0300 / 17-3-0500) |

- Reproduce: `curl -s -o /dev/null -w "%{http_code}\n" https://urbanlayerchicago.com/api/code/section/17-7-0574`. For after: the same against `http://localhost:8011`, from `uvicorn backend.main:app --port 8011` on this branch with local Qdrant on the 2026-06-17 collection.
- Tests: 29 new backend cases (article ids, the 17-7 extractions, the endpoint, index registration, overlaps, codification; the old overlap table now also runs with the index registered). Backend 1,626 passed + 1 skipped; eval 90; vitest 292; `npm run build` green. Run as `make test` plus `cd frontend && npm run build && npm run test`.

## Item 8: disclosure UI (WS1 M3, 2026-10-21)

**The code-currency note leaves the collapsed "True of every parcel" list.**
- **Decision:** when the Profile payload carries the structured `code_currency`, `CoverageNotes` renders the note (with its amendment list one click away) between the parcel notes and the collapsed list. Without it (old payloads, chat) the note stays in the list as before.
- **Alternatives:** leave it among the general notes and rely on the zoning card's "· N later amendments" stamp.
- **Why:** M3 exists to tell users about the gap. Inside a closed disclosure the count is invisible, and the stamp alone is a bare number with nowhere to go. The cost is one more always-open sentence in the box.
- **Revisit if:** WS0 M4's `ConfidenceCaption` takes over the vintage line.

**One row format, three review states, taken from the two review fields.**
- **Decision:** `amendmentStatus()` maps `review_status` × `product_effect`: `applied` → "Reflected on this page"; `pending`, a missing effect, or never reviewed → "Not yet reviewed"; reviewed with `none` → "Reviewed; not reflected on this page". The Profile list, the viewer banners and the admin table share it.
- **Alternatives:** the plan's three labels verbatim ("Not reflected" for `none`).
- **Why:** `none` means a person read the ordinance and found nothing the page states; "Not reflected" alone reads as an unaddressed gap. TOD Streets has a reviewed summary but `product_effect: pending` (M4b applies it), so it correctly shows "Not yet reviewed" next to its summary today.
- **Revisit if:** M4b flips TOD to `applied`; the label changes with no code change.

**The note's sentence stays the backend's English `currency_sentence`; only the chrome is keyed.**
- **Decision:** the note text is the `text` the API sends (the same sentence chat and the report use). New keys cover the list label, status labels, banner and notice, plus the "later amendments" count.
- **Alternatives:** translate the sentence by id with params and plurals.
- **Why:** the sentence has four states (fresh, aging, unknown, zero) and the no-count rule for unknown lives in one place, the backend. Re-implementing it in two locale files is how "never 'none' without a fresh check" would drift.
- **Revisit if:** WS7 translates the product; the sentence is then built from `check_state`/`since` keys.

**The 404 for a not-yet-codified section is a value, not an exception.**
- **Decision:** `fetchSection` and `fetchCodeSubsection` resolve to `CodeChunk | SectionNotCodified | null`; `isNotCodified()` narrows. Only a 404 whose body carries `not_in_published_code` becomes the notice; other failures stay `null`. The notice is cached like a hit.
- **Alternatives:** a second fetcher just for notices; throwing from the existing ones.
- **Why:** every viewer already branches on "got text / didn't". A union keeps one request per section and the existing hover-prefetch cache, and the three callers (modal, drawer, pill) each needed a new branch anyway.
- **Revisit if:** a third kind of non-text answer appears (then a tagged result type).

**Day-only dates go through a new `formatDay`, not `formatDate`.**
- **Why:** `formatDate("2026-10-14")` parses as UTC midnight and prints "Oct 13, 2026" in Chicago (checked: `TZ=America/Chicago node -e 'new Date("2026-10-14").toLocaleDateString(...)'`). The Clerk's `passed_on` is already a Chicago calendar day.
- **Not changed:** existing `formatDate` callers; they may have the same off-by-one on day-only strings (not audited).

**The chat sources panel is covered where a section is opened, not on its cards.**
- **Decision:** the banner and not-codified notice sit in `SourceDetailDrawer` (opened from a cross-reference or citation) and the cross-reference pill's hover preview. The Sources tab's chunk cards carry no marker.
- **Why:** a chat answer that cites an amended section already says so (prompt rule 34) and ends with the footer line; the drawer is where the user reads the section text.
- **Revisit if:** users read the cards without opening them and miss it. That needs the per-turn `code_currency.amendments[].touches`, already in the context payload.

**Admin card reads the existing endpoint, with its own fetch.**
- **Decision:** `CodeCurrencySection` fetches `/api/admin/code-currency` itself (like `VouchersSection`), shows the status, age, check state, Clerk errors and an amendments table, and never prints a count when the check is stale. English-only, as the rest of `/admin`.
- **Why:** the dashboard's shared loading state is for period-filtered stats; this card has no period.

**Found, not fixed.**
- The admin card shows the code text as **red, 126 days old**, correctly: the June 17 export is past the 90-day alarm line. WS6 M2's monthly reminder is the intended nudge; a newer American Legal export is the fix.
- `e2e/mobile-overflow.spec.ts` "about" on the Galaxy S24 failed once with "Execution context was destroyed" mid-scroll and passed on rerun. The page is untouched by this PR; treat as a flake unless it repeats (it did not on the post-rebase run).

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Frontend tests | 292 in 36 files → 334 in 40 files (+42) | `cd frontend && npx vitest run` (before: same command in a worktree of `main`) |
| `make test` | exit 0 | `make test` |
| CI-parity build | clean | `cd frontend && npm run build` |
| Mobile overflow audit | 39 of 40 on the first run (the flake above, passes alone); 40 of 40 on the re-run after rebasing onto #68 | `cd frontend && npm run test:mobile` (needs `backend` + `frontend` from `.claude/launch.json`) |
| Profile, 1601 N Milwaukee (local backend, 2026-10-20 snapshot) | no amendment list → note + "Later amendments (10)" list; zoning stamp "2026-06-17 · 10 later amendments" | open `/scorecard?address=1601 N Milwaukee Ave`, expand the list |
| Same page at 360 px, list open | `scrollWidth` 360 = viewport; no element past the right edge inside the notes box | `javascript_tool` in the browser pane at 360×800 |
| Viewer banner | covered by tests; by hand with the live `/api/code/section/17-3-0503-D` payload injected into a modal (3 amendments listed, caveat "does not include those changes") | a fetch stub in the browser pane |
| Admin card (local, dev auth bypass) | new → status red, 10 Title 17 since, 10 unreviewed, table of 15 | open `/admin` |

**Not measured:**
- The deployed bundle: size change (the build output was not compared with `main`'s) and the live Profile, banner and admin card (the post-deploy check).
- The drawer's banner and the not-codified notice in the real chat flow: reaching them needs a chat turn, which build work may not spend. Tests cover both; the first prod parcel chat is the check.
- Spanish rendering: new keys carry English text (listed in `_untranslated.json`).
- Screen-reader behaviour of the amber banner (`role="note"` only).

## Item 9: source registry, probes, dry-run checker (WS6 M1, 2026-10-21)

**One registry entry per overlay layer, with the layer's own name as the contract.**
- **Decision:** the 14 zoning overlay layers are 14 entries (`chi.zoning.overlay.<OVERLAY_LAYERS type>`), not one group. Each pins the *service's* layer name and a count band. A test asserts the registry's layer ids equal `OVERLAY_LAYERS` exactly and that layer 7 is in neither.
- **Alternatives:** one "overlays" entry; pin the names `OVERLAY_LAYERS` already carries.
- **Why:** the landmark failure (F8) was a layer id that changed meaning, so the check has to be per layer. The names in `OVERLAY_LAYERS` are *ours* ("Lakefront Protection District"); the server's are different ("Lakefront", "TSL Station"), so a contract on ours would fail on day one. Measured against the live MapServer 2026-10-21.
- **Revisit if:** the City renames a layer on purpose; the alarm then asks for a review, which is the intent.

**Year columns count as December 31 of that year.**
- **Decision:** `max(year)` / `max(data_year)` / the ACS end year become `date(Y, 12, 31)`, so "2026" is not stale in January and a tolerance in days means the same thing for every source.
- **Alternatives:** January 1 (the plan's implied reading); compare years as integers.
- **Why:** with Jan 1, Assessor values for the current year read 290 days old on the day they are published. With Dec 31, the energy-benchmarking rule "warn when the newest year is below the current year minus two" is exactly `warn_days=730`: 2023 warns from January 2026.
- **Tolerances that differ from the plan's text, all on this convention:** Assessor values 365/730, commercial valuation 450/750, energy 730/1460, ptaxsim 800/1200 (tax year 2024 is 659 days old and the database is 5 months old).

**Three failure kinds, not one `error`.**
- **Decision:** a timeout or 5xx is `transient` (`warn`, then `alarm` on a second run in a row). An error *body* (Socrata `errorCode`, ArcGIS `{"error": ...}` on HTTP 200) is `service` and is `error` at once. A broken contract (layer name, a required field) is `error` at once; a feature count outside its band is `alarm`.
- **Alternatives:** the plan's literal "`error` becomes `warn`, then `alarm`" for everything; treating an error body like a blip.
- **Why:** a server that answers with an error body is not a network blip, and the plan's own M4 test says a 200-with-`error` body "gives `error`". Absorbing only transport failures keeps the two-run rule for what it is for.
- **Revisit if:** the City server starts returning error bodies under load; then a body that clears on the next run should be absorbed too.

**`availability_only` means "judged on findings, not on a date".**
- **Decision:** reachability sources (Census Geocoder, FCC, Walk Score, FEMA, Cook GIS layer 44) and coherence checks (Qdrant alias and count, zoning-cache vintage, `VERIFIED_AGAINST`) set `availability_only`. A source with a contract but no date field (the 13 overlays) is `unknown`, not `ok`.
- **Why:** "no date to read" has two meanings. A geocoder has none by nature and is fine when it answers right; an overlay layer *could* have one and doesn't, which the plan wants shown as unknown, not green.

**The completeness test reads the code's syntax tree, and digit-less ids needed a second rule.**
- **Decision:** `test_data_health_registry.py` parses `config.py`, `main.py`, `retrieval/**` and `discovery/**`, skips docstrings, and finds Socrata ids as string constants. An id containing a digit is recognised anywhere; an all-letter id (`aksk-kvfp`, `csik-bsws`, `eejr-xtfb`, `ydgz-vkrp`) looks like a hyphenated word, so it counts only when assigned to a `*dataset*` name or passed as the first argument to `socrata_get`/`grouped_count`/`socrata_aggregate`.
- **Alternatives:** regex over the source text (matches docstrings and comments, which name retired and unrelated datasets); a digit-required rule alone.
- **Why:** the digit-required version passed on the first run and was blind to 4 of 40 registered ids. Checked by comparing the found set with the registry: 36 → 39 after the second rule (the 40th, `kn9c-c2s2`, is retired and appears only in a docstring).
- **Revisit if:** a dataset id is built at runtime from a string; that needs its own rule.

**`VERIFIED_AGAINST` did not exist; it is added, and a test pins it to the served vintage.**
- **Decision:** `zoning_definitions.py` gains `VERIFIED_AGAINST = "2026-06-17"`, the probe alarms when it differs from `code_vintage.json`, and a unit test fails the next refresh PR until someone re-runs `test_zoning_ordinance_parity.py` and moves it.
- **Why:** the plan describes the constant as already there; it was not (`rg VERIFIED_AGAINST backend` found nothing). Evidence for "2026-06-17": the parity test, which compares every table value with the ingested June 17 text, passes (14 tests).
- **Revisit if:** the refresh runbook (WS1 M7) automates the parity run; the constant could then be written by it.

**Day-one differences from the plan's §3.10 table**, each from running the probes on 2026-10-21:

| Plan expected | This run | Why |
|---|---|---|
| Report's ACS label alarm | no row | WS0 M1 already derives the period from the data; there is no hard-coded label to compare |
| `t68z-cikk` fields-read alarm | warn (one release behind) | `demographics.py` no longer reads the missing columns (WS0 M1); the contract lists what it does read, and all are present |
| Vacant buildings warn | acked | the feed stopped 2025-10-08, 426 days; ack to 2027-01-31 |
| `transit_stations.json` warn | unknown | the artifact carries no build date; M5's sidecar adds it |
| (not in the table) Assessor sales | warn | newest `sale_date` 2026-08-12 is 70 days old against the plan's 60/120 |
| (not in the table) `internal.discovery_index` | alarm | the *local* index was built 2026-07-07; production rebuilds monthly |

**Three acks, for your review** (all to 2027-01-31, owner `jack`): `cook.address_points` (mitigated by `3723-97qp`), `chi.vacant_buildings` (feed stopped), `chi.nof_large` (stale since 2023-09-19 against a quarterly claim).

**The City GIS server returns 403 to a User-Agent containing a URL.**
- Found when the first dry run came back with all 15 City layers as errors. `curl -A "urbanlayer-data-health/1 (+https://urbanlayerchicago.com)"` gets 403; `-A "urbanlayer-data-health/1"` and `python-httpx/0.27.0` get 200. The checker sends the plain form, and a comment says why.

**Deferred, on purpose.**
- FEMA and EPA known-answer parcels (M4's sentinels; M1 checks reachability and the layer name).
- Persisting `previous_error` between runs (M2's store; `evaluate` already takes it).
- `transit_stations.json` build date and the GTFS comparison (M5's sidecar).
- Per-source latency budgets; one request-count and one wall-clock number cover M1.

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Sources in the registry | 0 → 80: 40 Socrata, 21 ArcGIS layers, 5 APIs, 5 artifacts, 3 internal, 2 local databases, 2 GTFS feeds, 1 vector index, 1 hand table | `python -c "from backend.data_health.registry import SOURCES; print(len(SOURCES))"` |
| Dry run, whole registry | 100 HTTP requests, 2.6 s and 3.0 s wall (two runs) against a plan limit of 400 requests / 3 min | `python -m backend.data_health.check --dry-run` |
| Day-one states | 44 ok, 9 frozen_ok, 5 warn, 3 acked, 17 unknown, 2 alarm (code text; local Discovery index) | same command |
| Run-to-run variation | in 5 full runs one source (FEMA NFHL, `ConnectError`) failed once and read `warn` by the two-run rule | same command, repeated |
| Costliest sources | 3 requests (zoning layer 1 and layer 2: layer JSON, count, newest edit) | `--dry-run --json` |
| Backend tests | 1,627 → 1,698 (+71: 16 registry, 25 probes, 30 evaluate) | `make test` |
| Frontend tests, lint warnings | 334 / 67, unchanged (no frontend change) | `make test`, `make lint` |
| Import weight | importing the checker loads no torch, numpy, qdrant_client, weasyprint, matplotlib, `backend.main` or `backend.discovery` | `test_importing_the_checker_loads_none_of_the_serving_stack` |

**Not measured:**
- A run inside the production container. This Mac has ptaxsim, the Walk Score key and an old Discovery index (that row alarms here); production's index is rebuilt monthly, and its network path to each service is untested until M2's timer runs.
- Behaviour under a real outage of each service (tested with mocks and one natural blip).
- Sentry and `/health` (M2).

---

## Item 10: provenance schema v2 (WS0 M2, 2026-10-21)

Backend and types only. No visible change: nothing reads the new fields until M4.

**v1 fields stay byte-for-byte; every new field is additive.**
- *Decision:* `as_of` stays `None` where the source gives no date (the overlay layers have no edit-date field). `as_of_basis: "queried"` says so. The guide's precedence ends at "`query_date` with basis `queried`", but copying the query date into `as_of` would have changed a v1 field's value and made an unknown date look like a known one.
- *Alternatives:* fill `as_of` from the registry's frozen vintage and data health now. Rejected for M2, because it moves a v1 value (a footprint-sourced building area would gain a 2015 `as_of`). `resolve_as_of()` implements the whole precedence and is tested, but M2's builder feeds it only the response date. M3's capture is where the registry steps start to apply.
- *Evidence:* `eval/provenance_diff.py` rebuilds provenance with the code on `main` and with this branch for the 12 recorded kit payloads. All v1 keys and values match, with one intended exception below.
- *Revisit if:* a consumer needs a non-null `as_of` on every entry. Then add `as_of_effective` rather than overloading `as_of`.

**A polygon-derived lot area is tier D (`our_calculation`), so its `kind` changes from `official_record` to `derived`.**
- *Decision:* follow the plan's inventory (§3.1: lot area "A / D"). When `land_sqft_source == "geometry"` the number is our planar area of the County's polygon, not a figure the County states. It lists `inputs: ["cook.ptaxsim"]` and `basis_tier: official_estimate`, the weakest input.
- *Alternatives:* leave it tier A to keep the diff pure. Rejected: a computed figure labeled as a record is the over-claim this standard exists to stop.
- *Evidence:* 8 of the 12 recorded parcels have a geometry-sourced lot area. Nothing in the frontend reads `kind` (`grep` of `frontend/src`: none). `kind` is already `derived` for an approximate parcel identity.
- *Revisit if:* a reader of `kind` appears. It is removed one release after nothing reads it.

**`record_updated` added to the as-of bases.**
- *Decision:* the guide's list (`source_updated`, `current_through`, `period_end`, `vintage`, `tax_year`, `queried`) has nothing for a zoning district's own `map_updated`. The `old_source` rule fires on dataset age: a 2021 map edit on a district would read "dataset is 5 years old", which is false. `record_updated` is exempt from `old_source`; the guide now lists it.
- *Alternative:* use `source_updated` and special-case the district. Rejected: a per-fact exception in the rule is the kind of thing the guide forbids ("let `provenance.py` decide").

**Confidence rules live in one function, with the coverage kind explicit.**
- *Decision:* `Coverage.sample` (`area_sample` | `comps` | none) selects which n rule applies. n < 30 withholds only an area sample; comps fade under 5 and withhold under 3; a list or an ACS figure has no n rule. The rule is in the data, so no caller has to remember it.
- *Alternative:* infer from the fact id. Rejected: the same fact id can be a list in one place and a sample in another.
- *Evidence:* `test_confidence_state.py` pins each boundary on both sides (9.99/10.00% and 24.99/25.00% coverage; n 29/30 and 2/3/4/5 for comps; CV 30.0/30.1% and 50.0/50.1%; AI agreement 95.0% vs 92.5% and 100% on 29).
- *Revisit if:* WS4's Assessor rents need a different n gate than 30. Then add a `SampleKind`, not a threshold override.

**Facts name their sources three ways, and the registry is checked both ways.**
- *Decision:* `FactSpec` has `source_id` (the usual supplier), `alt_source_ids` (other suppliers of the same recorded figure, e.g. GIS or footprints for an area) and `input_source_ids` (sources it is computed or located from, e.g. ptaxsim, the Parcel Universe, the geocoder). Tests assert every named source lists the fact in its `fact_keys`; that a registry source listing a fact we model is one the fact names; and that a recorded figure's tier equals its source's registry tier (inputs are exempt, since the figure is then tier D).
- *Registry edits (WS6 file, with WS0's ask):* `zoning.height` → `zoning.max_height` plus `zoning.min_lot_area_per_unit` on the Title 17 table; `property.land_sqft` / `property.bldg_sqft` added to the six area sources. These were the ids the Profile already emits.
- *Known simplification:* an authoritative `parcel.identity` names `cook.address_points` as its source, though it can come from the Assessor's address table. The resolver doesn't tell `build_provenance` which. `cook.parcel_addresses` is an alternate. M3 threads the method through.

**`ProvenanceEntry` forbids unknown fields and values.**
- *Decision:* `extra="forbid"` and literal types for tier, method key, basis, scope and confidence, so a typo fails a test rather than shipping. `to_dict()` always emits the v1 keys (including `note: null`, which v1 carried on some entries) and the v2 extras only when set, to keep payloads small.

**Not done here, on purpose:** reading `data_health` status (WS6 M2 lands the store; the import is guarded and tested with a fake), `ContextObject.provenance` persistence (M6), and any UI.

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend unit tests | 1,698 → 1,752 (+54: new `test_confidence_state.py` and an extended `test_provenance.py`) | `make test` (before: the same command on `main`) |
| Eval tests | 90 → 92 (the diff tool) | `make test` |
| Frontend tests, lint warnings | 334 / 67, unchanged | `make test`, `make lint` |
| Entries rebuilt on 12 recorded kit payloads | 131 entries; no entry removed or added; no v1 field removed | `PYTHONPATH=. python -m eval.provenance_diff eval/results/2026-10-21-m4/parcel_kit_raw --expect property.land_sqft.kind` |
| v1 values changed | 0, except `property.land_sqft.kind` (`official_record` → `derived`) on the 8 parcels with a polygon-derived lot area | same command without `--expect` |
| New keys on entries | 15 across the 12 parcels: tier, source_id, as_of_basis, age_days, scope, geography, method_key, method, method_params, basis_tier, inputs, confidence, confidence_reasons, value, plus `note: null` on the entries that had no `note` key | same command |
| Zoning values moved | 0: every `zoning.*` entry's v1 fields match `main` | same command |
| Sources named by `FACTS` that resolve in the registry | all (8 static facts plus 14 overlay types) | `test_every_fact_names_a_registered_source_that_lists_it` |

**Not measured:**
- Payload size (bytes) before and after. Each entry gains roughly 10 small fields; the Profile response carries 8–14 entries.
- `make kit-replay` re-scores the 2026-10-01 recordings, which predate provenance, so it shows nothing about this change. The payload diff above is the evidence that no zoning value moved.
- A live `/api/scorecard` from this branch. Local runs need the government APIs. The deployed API is checked after the merge instead.

---

## Item 11: status store, daily timer, Sentry alarms, dead-man (WS6 M2, 2026-10-21)

**The store is a separate SQLite file in journal mode DELETE, written by `sqlite3`, not aiosqlite.**
- *Decision:* `data_health.db` on the `backend_data` volume; the checker is the only writer and the app opens it `mode=ro` for `/health`.
- *Alternatives:* a table in `chicago.db` (rejected: the checker is another container, and the plan's reason stands: no lock contention with the app's WAL database). WAL mode for the new file (rejected: a read-only reader in another container needs the `-wal`/`-shm` side files to be usable, and one write a day gains nothing from WAL).
- *Revisit if:* the checker ever writes more than once a day or the panel (M3) polls hard. Then WAL plus a shared-memory-capable mount.

**What we last notified about is stored, not inferred from the previous state.**
- *Decision:* `source_status.alerted_state` / `alerted_at`. A transition is "red now, and not already notified for this state"; a heartbeat is "red, notified on an earlier day"; a recovery is "not red, but notified".
- *Alternatives:* compare today's state with yesterday's. Rejected: the 14-day quiet period holds back non-critical sources, and they must alert as a *new* issue when it ends, and a crash mid-run must not lose or repeat an email.
- *Evidence:* `test_a_standard_source_is_held_back_for_the_first_two_weeks_then_alerts`, `test_decide` (9 cases), and the §8 test.
- *Revisit if:* Sentry's own issue state (resolved, ignored) should drive re-alerting.

**`alarm` → `error` is a different issue; `warn` never alerts.**
- *Decision:* fingerprint is `["data-health", id, state]`, so a source that goes from stale to broken opens a second issue, as the plan says. A source that falls from red to `warn` or `acked` counts as recovered.
- *Alternative:* alert on `warn` too. Rejected: 6 sources are `warn` on day one; the plan keeps them on the panel.

**Partial runs are forbidden when writing.**
- *Decision:* `--write` with `--only` is a CLI error. A run deletes the rows of sources not in the run (how a finished drill clears, with a "recovered" event); a partial run would wipe the rest.
- *Alternative:* never delete; `--clear ID` only. Rejected: a retired registry source would sit in the store forever, and a drill would need a manual step to stop counting in `/health` alarms. `--clear` exists as well.

**The fault drill runs the full real check plus one synthetic source.**
- *Decision:* `--inject-fault stale:drill.<name>` or `broken:drill.<name>` adds a critical `drill.*` source with a canned probe result, in a normal run. Only `drill.*` ids are accepted, so the flag cannot paint a real source red.
- *Alternative:* a drill-only run. Rejected: the acceptance wants the Cron check-in and a refreshed `/health` age from the same run, and the run costs about 100 requests.

**The code-vintage alarm is acked until 2026-12-15, and the reminder is a monthly GitHub workflow.**
- *Decision:* `code.municipal_text` (critical, WS1's 60/90-day thresholds) would alarm on its first run and every day after. American Legal's newest export (current through 2026-06-17) is 126 days old on the day it was ingested. Alarming daily on something nobody can fix trains people to ignore the channel. So: an ack with a reason and an expiry (the registry's own mechanism), plus `code-export-reminder.yml`, which fails on the 1st of each month while `code_vintage.json:ingested_at` is over 35 days old. That is the "download a new export" nudge the queue asks for, on a signal that goes quiet when someone ingests.
- *Alternatives:* leave it alarming (daily noise); loosen the thresholds now (a WS1-owned decision made without the publisher's real cadence); ack with a far-off expiry (hides it).
- *Evidence:* `check --dry-run` on 2026-10-21: `code.municipal_text` alarm, 126 d, before the ack.
- *Revisit if:* the ack expires (2026-12-15). Measure the lag at each export (current-through vs download date) and set the thresholds against that, or alarm on `ingested_at` instead.

**Backup age is read from a status file the backup script writes beside the database.**
- *Decision:* `scripts/backup_db.sh` writes `backup_status.json` (time, file, size, copies) atomically into the directory of `chicago.db`, which is the `backend_data` volume the checker container already mounts. The probe judges it by hours: warn over 30, alarm over 36. `BACKUP_STATUS_REQUIRED=true` in `docker-compose.prod.yml` makes a missing file an alarm; unset (dev) it is "not probed here".
- *Alternatives:* a read-only bind mount of `/opt/urbanlayer/backups` into the checker (the directory is `root:jack` 2750; the container would need that group, and another mount on the serving compose file); SSH from the checker (a key in the container). Rejected: both widen what the container can touch for one number.
- *Why hours, not days:* the registry's day thresholds can't tell "one night missed" (about 26 h at the 05:37 check) from "healthy" (2.6 h) without an off-by-one. `availability_only` plus findings keeps the rule in one function.
- *Known gap:* it proves the script finished, not that the copy restores, and it does not see the off-box pull to the Mac.
- *Revisit if:* the status file and the real newest file ever disagree (a deploy that changes the script path). Then add the filename check from the host side.

**The checker's own row (`internal.checker`) is for the panel, not the pager.**
- *Decision:* a probe reads the store's last finished run (warn after 1 day, alarm after 3). The real dead-man is outside the box: `/health` (`checker: ok|late`, 36 h), the Sentry Cron monitor, and a daily GitHub workflow that fails (and emails) when `/health` is late, missing the block, or the site is down.
- *Alternative:* an UptimeRobot keyword monitor on `/health`. Not used: free tiers only and no new sign-ups (build-order decision 5).
- *Note:* the Cron monitor is created from the first check-in's `monitor_config` (crontab `37 5 * * *`, 90 min margin), so nothing is set up in the Sentry UI. Whether the free plan allows it is verified in the production drill.

**Sentry stays out of the dev requirements.**
- *Decision:* `alerting.Sink` is a protocol; `SentrySink` imports the SDK lazily; tests inject a fake sink, and one test fakes the `sentry_sdk` module to pin the fingerprint, tags and monitor config. The SDK is in `requirements.prod.txt` only, so CI never needs it.

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend unit tests | 1,752 → 1,802 (+50: store 13, alerting 22, probes +13 (backup age, checker), backup script 2) | `make test` (main measured the same way in a temporary worktree: 1,752) |
| Eval tests, frontend | 92 and 334, unchanged (no frontend change) | `make test` |
| Registry | 80 → 81 sources (`internal.backups`); `internal.checker` gains a probe; 2 sources still without one (`internal.sentinels`, `eval.kit_weekly`) and the transit artifact | `python -m backend.data_health.check --dry-run` |
| One full `--write --alert` run, this Mac | 100 HTTP requests, 4 s, 82 rows written (81 + the drill), 1 event for the drill | `DATA_HEALTH_DB_PATH=/tmp/x.db python -m backend.data_health.check --write --alert --inject-fault stale:drill.synthetic`, no `SENTRY_DSN` so events are logged |
| Next normal run | drill row removed, one "recovered" event | same command without the flag |
| Day-one alerts on this Mac | 1 critical-or-not alarm after the ack: `internal.discovery_index` (standard, so held back by the quiet period); `code.municipal_text` was the other until acked | dry run |

**Not measured:**
- A run inside the production container, its Sentry delivery, the Cron monitor's acceptance on the free plan, and `/health` on production. All of these are the post-merge drill (needs `sudo` to install the timer).
- `fed.fema.nfhl` returned `ConnectError` on every local run today (a `warn`, "first run"); whether production's network path reaches it is untested until the first production run.
- The GitHub workflows have only been exercised locally against stubbed `curl`; their first scheduled run happens after merge (the dead-man will fail until the timer is installed and has finished a run).

### Item 11 addendum: first production run (2026-10-21)

**The checker's HTTP client retries connection errors (3 times).**
- *Decision:* `make_client` uses `httpx.AsyncHTTPTransport(retries=3)`. It retries a connect failure only, never a request that got a response, and the per-probe request tally still counts requests, not retries.
- *Why:* the first production runs flagged `fed.fema.nfhl` "failed twice in a row: ConnectError" (it also failed on this Mac). FEMA's `hazards.fema.gov` resets about half of fresh connections: 5 of 8 new connections failed, 0 of 12 over one kept-alive connection (httpx, 2026-10-21). With a single attempt the "twice in a row" rule fires on a coin flip, which is the alert noise the rule exists to avoid.
- *Evidence:* 10 consecutive probe runs of `fed.fema.nfhl` after the change: 10 `ok`.
- *Revisit if:* a source that is really down starts to take 4x as long to report; the connect timeout is 8 s, so the worst case is about 32 s per probe.

**Found, not fixed here (WS6 M7):** `backend/retrieval/regulatory/flood.py` returns `None` on any FEMA error, the same value as "not in a mapped flood zone". With FEMA resetting connections, a Profile can say `in_special_flood_hazard: false` for a parcel whose lookup failed. This is the landmark-layer silent failure again (M7a fixed it for the overlays only). M7 should give flood the same tri-state, and the lookup should retry like the checker now does.

## Item 12: law passed after June 17, applied ahead of codification (WS1 M4b, 2026-10-21)

**Applied law speaks as its own parcel notes, not as a new field.**
- **Decision:** a reviewed amendment with `product_effect: applied` produces a coverage note (`tod_street`, `pedestrian_street_added`, `pedestrian_street_removed`, `milwaukee_sco_strip_centers`) carrying `ahead_of_code: true`. `legislation/applied.py` builds them; `build_coverage_notes` takes the parcel's address to match.
- **Alternatives:** a new `ContextObject.law_changes` field (a second list the Profile, chat prompt and every consumer would need to learn); changing the overlay objects or the zone summary (it would mix what the City's map says with what we infer from an ordinance).
- **Why:** coverage notes already reach the Profile (rendered with the English text as the fallback, so no frontend change and no new `es` keys), the chat context (rule 36) and the PDF. One prompt sentence and one template block cover the rest.
- **Also:** an applied amendment no longer appears in the "not reflected on this page" note. That note now means what it says.
- **Revisit if:** a surface needs the structured facts (the prohibited-use list as data, for a filter). Then `tod_street_status` is already the structured form.

**Transcribed from the scans, in session, and pinned both ways.**
- **Decision:** I read the ten passed PDFs as images (none has a text layer) and committed only the rows and phrases the product uses, at `backend/tests/fixtures/ordinances/passed_2026-07_to_10.json`, labeled as read-in-session. For each rule the test asserts the code against that transcription while the code text lacks the change (and that the code text still shows the *old* rows), and against the code text once a refresh carries it.
- **Alternatives:** trust the Clerk titles (the title of SO2026-0026276 says "by right"; the substitute enters S); store the PDFs (102 MB-class risk for nothing; the URLs are in `source_pdf`).
- **Evidence:** the readings changed three summaries. O2026-0025429 only adds the 7-EV-charger trigger (special use for all new gas stations was already text); SO2026-0026276 sets PMD 4B to special use, not by right; the Clark ordinance merges three rows into Belden–Grace and newly designates only 3000–3432 N and 3600–3800 N.
- **Revisit if:** a refresh codifies one. `codification_check --write` flips `codified`, and the test then reads the code text instead.

**TOD streets match by street address, with the street type.**
- **Decision:** a parcel is on a TOD street when its street, direction, number and street type fall in a §17-3-0603 segment. The note says plainly that a lot reaching the street only from a cross street is not caught.
- **Alternatives:** parcel geometry against the street's right-of-way (the plan's follow-up; no street-centerline artifact in the repo, and TOD streets are not in the zoning MapServer); matching without the street type (found while testing: "3036 W Lawrence **Pl**" matched Lawrence **Ave**; `map_effect_matches` had the same gap, so `suffix` is now an optional field on a map effect and `address_suffix` reads it).
- **Revisit if:** a cross-street lot on Western or Ravenswood shows up in a customer question, or the City publishes a TOD layer.

**Pedestrian-street notes can't depend on the map layer, because it's blind.**
- **Evidence:** the plan's first design said "note only where the overlay layer disagrees with the ordinance". Probing the local Profile shows layer 4 returns nothing at 1000 W Armitage, 1650 W Belmont, 2400 N Clark, 3300 W Lawrence or 3500 N Clark, all on long-designated pedestrian streets (a point-in-polygon lookup on street segments). Its silence says nothing about whether the map has caught up.
- **Decision:** match by address range alone and say the map "may" lag. An addition keeps its note after codification (the page can't otherwise say a lot abuts a pedestrian street); a removal goes quiet once the code text carries it. The report drops its "pedestrian street overlay" opportunity on a removed segment.
- **Not fixed here:** the Profile's `on_pedestrian_street` flag is effectively always false. A parcel on any pedestrian street, not just the changed ones, is missed. That is a WS0/WS6 finding (it feeds item 22's partial-failure work), raised in the PR.

**One in-session range choice: Lawrence is 3034–3042, not 3032–3042.**
- The table rows end at 3032 W and restart at 3042 W, and the ordinance's common address is 3034–3042. The effect uses the common address, the narrower claim, so a lot at 3032 is not told its designation was removed.

**Non-Title-17 items stay unreviewed, and the pending-review warning now points at them.**
- The four cited-other items (2-44-140, 2-44-170, 18-14, 2-45-165) are not parcel surfaces; they need a wording check, not a rule. `currency_check` warns on them after its pending threshold. The Title 17 list is fully reviewed: 10 of 10 after June 17.

**Numbers** (2026-10-21; local unless marked)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 1,803 → 1,855 collected (+52: `test_applied_law.py` 49, `test_legislation_currency.py` +3) | `make test`; `pytest backend/tests -m "not integration" --collect-only` on main in a worktree for the before |
| Eval, vitest | 92 / 334 unchanged; `npm run build` passes | `make test`; `cd frontend && npm run build` |
| Title 17 amendments after the vintage that are reviewed | 0 of 10 → 10 of 10 (5 applied, 5 none) | `python -c "import json;…"` over `code_amendments.json`, or `test_every_title17_amendment_after_the_vintage_is_reviewed_with_a_source_pdf` |
| Profile, 4000 N Western Ave (local backend, public data only) | no `tod_street` note → note present; 1 parcel-relevant amendment, listed as applied | `curl "http://localhost:8001/api/scorecard?address=4000+N+Western+Ave"` |
| Profile, 3036 W Lawrence Ave / 3100 N Clark St / 2100 N Milwaukee Ave | `pedestrian_street_removed` / `pedestrian_street_added` / `milwaukee_sco_strip_centers` notes present | same, other addresses |
| Off-segment checks | 4801 N Ravenswood, 2000 N Damen, 3500 N Clark, 3036 W Lawrence **Pl**: no note | same |

**Not measured:**
- Chat wording with the new prompt sentence (no live model). Pinned only by a test that the sentence exists; the first prod chat on Western Ave is the check, plus the monthly chat kit.
- The PDF visually: the template block is exercised by a render test, not opened as a PDF.
- `npm run test:mobile`: no layout change (the note renders in the existing "What this page doesn't cover" card; a screenshot at desktop width shows it wrapping normally).
- Cross-street lots on TOD streets, and a TOD street's abutting lots on the far side of an alley or cross street.

## Item 13: admin Data health panel (WS6 M3, 2026-10-21)

**A row on the admin dashboard, not a tab.**
- **Decision:** `DataHealthSection` is a new section on `AdminDashboard`, above Code Currency.
- **Alternative:** a tab, as the plan says. `AdminDashboard` has no tabs: it is a stack of sections (overview, latency, requests, Code Currency, Early Access), so a tab would have meant building tab chrome for one panel.
- **Revisit if:** the page grows past what one scroll reaches. Then tabs for the whole dashboard, as its own change.

**The payload is built by a module that imports none of the serving stack, and never raises.**
- **Decision:** `backend/data_health/panel.py` reads the store through the `open_readonly` handle `/health` uses. A missing or unreadable file returns a "checker late" payload with no rows, not a 500. A test runs `import backend.data_health.panel` in a subprocess and asserts torch, `backend.main` and discovery are absent.
- **Why:** an admin looking at a broken checker is exactly who must not meet an error page; and the module stays usable from the checker's container.
- **Revisit if:** the app and the checker ever stop sharing the `backend_data` volume.

**Every registered source gets a row even before its first check; unregistered stored rows are shown too.**
- **Decision:** rows = the live registry (retired excluded) plus any stored row with no registry entry. An unchecked source reads `unknown` / "not checked yet".
- **Why:** the plan's acceptance wants the M2 drill source visible and red, and a `drill.*` id is not in the registry. A source added to the registry reads honestly on the panel the day it merges, not only after the next 05:37 run.
- **Evidence:** `test_a_stale_source_comes_first_and_red_with_its_reason`, `test_every_registered_source_has_a_row_even_before_its_first_check`.

**Sort order: alarm, error, warn, unknown, acked, ok, frozen, critical first within a state.**
- **Decision:** the plan's order. The checker's console output puts `error` first; both are red, so the panel follows the plan, and critical sources lead each state so the ★ ones are never buried.
- The sort is applied on the server and again in the component (`sortSources` in `lib/dataHealth.ts`, tested), so a future payload that changes order can't reorder the panel silently.

**The "contract result" column says whether a structure check exists, not how it came out.**
- **Decision:** the column shows "checked" when the source's spec has a layer-name, field or count-band contract, and "—" otherwise. A failed structure check already makes the row `error` or `alarm`, with the finding in its reason.
- **Alternative:** a separate pass/fail field. The store has none: contract findings are folded into the state's reason (M1). Splitting them is M4's work, when value-set contracts and sentinels add results worth their own column.
- **Revisit if:** M4 stores per-contract results. This column then shows them.

**Not in scope, as the plan says:** the weekly kit summary (M5) and replacing the empty Benchmark/Judge panels.

**Numbers** (2026-10-21; local)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 1,855 → 1,869 (+14, `test_data_health_panel.py`) | `make test` |
| Frontend tests | 334 → 341 (+7, `DataHealthSection.test.tsx`); `npm run build` passes | `make test`; `cd frontend && npm run build` |
| Panel on a real store (one full `check --write` against the public APIs, 100 requests, plus the synthetic drill) | 82 rows; counts `2 alarm, 5 warn, 18 unknown, 4 acked, 44 ok, 9 frozen`, matching the CLI summary line; `drill.synthetic` first and red | `DATA_HEALTH_DB_PATH=… python -m backend.data_health.check --write --alert --inject-fault stale:drill.synthetic`, then the backend with the same env and `curl localhost:8001/api/admin/data-health` |
| Counts vs `/health` | `alarms` = alarm + error in the panel's counts (pinned by a test) | `test_counts_match_the_store_and_the_health_block` |

**Not measured:**
- Production: the panel's first load as admin, its counts against the live store and `/health`, and the stored drill history (checked after the deploy).
- `npm run test:mobile`: it audits public routes, and the admin panel is a desktop screen. The table scrolls sideways inside its own container; checked at desktop width only.
- The 18 `unknown` rows on this Mac are overlay layers the local run can't read; production's count differs.

## Item 14: capture metadata and cover every Profile figure (WS0 M3, 2026-10-21)

**A figure's entry is built from a declared list, and a second list written from the payload checks it.**
- **Decision:** `provenance_figures.figure_entries()` builds one entry per figure present. `expected_fact_ids(payload)` is written from the payload's JSON shape, independent of the builder. `test_confidence_coverage.py` runs the builder over the 12 recorded kit payloads and fails on any expected fact with no entry; `eval/confidence_audit.py` does the same over the 100-address panel.
- **Alternatives:** one table that drives both the builder and the check (a forgotten figure would be forgotten in both); a runtime assertion in the endpoint (it would turn a missing caption into a 500).
- **Evidence:** the audit's own first run flagged 19 entries the expectation didn't list. All were zeros: a 0% vacancy rate and a $0 exempt assessed value are figures the page shows, and "present" had treated 0 as absent. The expectation was fixed, not the builder. After the fix, 25 panel addresses: 0 unexpected.
- **Revisit if:** the Profile gains a figure. The coverage test fails until it has a spec in `FACTS` and a line in `expected_fact_ids`.

**Fact ids follow the registry, with registry keys that cover what is under them.**
- **Decision:** a registry `fact_key` now covers its own fact and the facts beneath it (`area.tract` lists `area.tract.median_gross_rent`). The two provenance tests that tie `FACTS` to the registry use that rule. The flag sources moved from one shared `property.flags` key to one key each, because a shared prefix would claim every flag for every source.
- **Alternatives:** 60 registry edits, one per fact; ids that ignore the registry (the plan's own `area.tract.median_gross_rent` wouldn't have matched `neighborhood.tract_demographics`).
- **Also:** two registry keys renamed (`neighborhood.tract_demographics` → `area.tract`, `neighborhood.demographics` → `area.community_area`); `chi.311` now lists the Profile among its surfaces.

**ACS margins of error come from the response, and percentages get the Census formula.**
- **Decision:** `CensusTractDemographics` keeps `acs_release`, `moe` and `cv` per field. A count's MOE is the published one; a share's MOE is the Bureau's proportion formula (the ratio formula when the radicand is negative), in percentage points; a bachelor's-or-more share sums its four numerators' MOEs in quadrature. The Census's negative sentinels are not margins.
- **Evidence:** 1601 N Milwaukee: median rent 2,435 ± 220, CV 0.055, matching the plan's example. The panel then fades 277 figures and withholds 223 of 4,807: tract unemployment is withheld on 32 of 97 parcels (CV over 50%), vacancy on 17 of 91.
- **Revisit if:** a better small-area source arrives (WS4).

**The class norm is stated with its derivation year, and it is a year stale.**
- **Evidence:** the frontend's 0.21 is the Chicago composite rate's mode (6.995%) times the state equalizer (3.0163), both tax year 2023 (read from ptaxsim). The same arithmetic on tax year 2024 gives 6.6186% × 3.0355 = 0.2009, so the norm runs about 5% high (a residential norm of 2.1% should read 2.0%).
- **Decision:** not changed here (M3 changes no displayed number). The entry carries the year and the 2024 figure in its note; a test pins the backend constant to the frontend's. The entry also gets `old_source` once the year is over 24 months old.
- **Revisit if:** item 15 touches the tax tile. Updating the constant is a one-line change in two places.

**Source dates come from the checker's store, then the frozen vintage; a year-only vintage reads as that year's end.**
- **Decision:** `data_health/status.latest()` (read-only, cached by file mtime) feeds `resolve_as_of`. The newest date in the data is `period_end`; the publisher's last touch is `source_updated`; an `unknown` row gives nothing. A frozen source dated by year (the 1996 survey) reads `1996-12-31`, basis `vintage`. A year still in progress has no end date yet (an assessment year 2026 has `as_of: null` and a `period`).
- **Not applied:** overlay entries and `zoning.district` keep their v1 dates (`queried` / the map record's edit date). A layer's newest-edit date would read as "old" on layers that rarely change, which is not the figure's age.
- **Test isolation:** an autouse fixture points the store at a missing file, so a developer's local checker run can't change a test.

**Figures that stay out.**
- The verdict is computed in the frontend from figures that now have entries; item 15 captions it.
- A negative result (not in a TIF district, no flags) is not a figure and gets none.
- No `provenance` on a parcel-less chat turn: that is item 20.

**Found along the way, not fixed here.**
- **The Profile never set `comp_basis`.** The scorecard's `ComparablesSummary` constructor dropped it, so the "widened to ½ mile and 5 years" line the plan found (finding 8) could never reach the page. It, the radius, the window and a `widened` flag now ride the payload.
- **Comps are not repeatable.** Two fresh runs of the same code gave different comp sets: 10 of 12 kit parcels changed between a fresh and a cached run (P1: 2 comps, then 1, with different sales). Main and the branch can't be told apart this way; that is a retrieval-reliability gap (partial 3-hop results). It matters to item 15: the n-based gates (fade under 5, withhold under 3) would flicker with it. On the panel, 70 of 86 price medians are withheld and 10 faded.
- FEMA flood zones also drop out of some runs (3 of 12 kit parcels, one side only), the failure mode WS6 M7 already names.

**Numbers** (2026-10-21; local backend, public data only)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 1,869 → 1,923 (+54: figures 27, coverage 27 across the 12 recorded payloads; 3 existing tests updated) | `make test` |
| Eval, vitest, build, lint | 92 / 341 unchanged; build passes; lint 67 warnings (cap 67), 0 errors | `make test`; `cd frontend && npm run lint && npm run build` |
| Entries per Profile, 1601 N Milwaukee | 14 → 58 | `curl "http://localhost:8001/api/scorecard?address=1601+N+Milwaukee+Ave"` |
| Profile payload, 1601 N Milwaukee, raw / gzipped (prod serves gzip) | 48.9 KB / 14.0 KB → 77.9 KB / 17.1 KB (provenance 9.1 → 37.1 KB raw; 1.5 → 4.5 KB gzipped). Under the 10 KB gzipped trim line, so entries stay in full | same, `gzip` over the JSON |
| Confidence audit, 100-address panel (before the zero fix) | 4,807 figures present, 4,807 with an entry (**100.0%**), 0 facts with gaps, 0 fetch errors; mean 48.3 entries, 62.1 KB per payload of which 30.3 KB provenance; 277 low, 223 withheld; every fact present on at least one address | `PYTHONPATH=. python -m eval.confidence_audit --full http://localhost:8001 --concurrency 2` (24 min) |
| Confidence audit after the zero fix, 25-address sample | 1,203 / 1,203 (100.0%), 0 unexpected | `… --sample 25` |
| Displayed figures, 12 kit parcels, fresh main vs fresh branch | 0 differences in the parcel's property, zoning, regulatory, incentive, tract, zone-definition, unit-yield and note fields (live feeds, comps, flood, appeals counts and address violations/311 excluded as volatile) | `eval.parcel_kit --full <url> --surfaces profile` on each, diff of the raw payloads |
| Profile kit scores | unchanged coverage and accuracy on both runs | same |

**Production** (2026-10-21, after the deploy of #79; docs only)

| Check | Result | Reproduce |
|---|---|---|
| 1601 N Milwaukee, `area.tract.median_gross_rent` | value 2,435, `precision` `{moe: 220, moe_level: 0.9, cv: 0.055}`, period 2020–2024, as_of 2024-12-31 | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |
| `property.stories` | as_of 2015-08-15, basis `source_updated` (from the checker's store), reason `old_source` | same |
| Source dates from the store | `property.sales` as_of 2026-08-12 (`period_end`); crime 2026-10-14 | same |
| Entries on the Profile | 56 on prod (58 locally: no FEMA zone came back on prod for this parcel) | same |
| `/api/area-stats?ca=24` | carries `area.benchmarks.market_value_per_land_sqft`; coverage share 0.4421, index built 2026-10-01 | `curl "https://urbanlayerchicago.com/api/area-stats?ca=24"` |
| 25-address production audit (serial) | 1,185 of 1,185 figures with an entry (100.0%), 0 gaps, 0 unexpected, 0 fetch errors; mean 47.4 entries, 61.9 KB per payload (30.1 KB provenance); 74 low, 51 withheld | `PYTHONPATH=. python -m eval.confidence_audit --full https://urbanlayerchicago.com --sample 25 --concurrency 1` |

**Not measured:**
- The pre-change mean payload on the panel (only 1601 N Milwaukee was measured before).
- Chat: `_provenance_for` is unchanged (still empty without a district) and nothing reads the new entries yet; no model call was made.
- The plan names `2015-08-14` for the footprints' as-of; the registry's frozen vintage, the checker's store and the data all say `2015-08-15`.

## Item 15: `ConfidenceCaption` on the Profile (#80, 2026-10-21)

**The frontend says; the backend decides.**
- **Decision:** `lib/confidence.ts` reads `entry.confidence` and never recomputes it. The one rule the frontend owns is display policy: `wantsCaption` (tier C–F, low or withheld, or reason `old_source`). The only copies are the minima a withheld sentence prints ("needs 3"), in `DISPLAY_THRESHOLDS`, and `test_frontend_confidence_constants.py` pins them to `provenance.py`.
- **Alternatives:** recompute states in the component (the guide forbids it); ship the minima inside each entry (a backend change; not worth it for four numbers).
- **Helpers take an injected `t` and return strings,** not structured parts, so the unit tests assert the real English copy and double as a locale check. *Alternative:* return keys and params and translate in the component (tests then check keys, not words).

**A context carries the provenance map; cards call `useFact(id)`.**
- **Decision:** `ScorecardPage` wraps the results in a provider; a card asks for its entry. Outside a provider every lookup is undefined and nothing renders, so the chat rail and every existing card test are unchanged.
- **Alternatives:** thread `provenance` through every card's props (and every future card's). The Zoning card keeps the prop it already had for its § buttons.
- **Found by lint:** the context and its hooks live in `lib/provenanceContext.ts`, the provider alone in `contexts/`. One file exporting both added two `react-refresh` warnings, and the warning cap is exactly 67.

**A withheld comps median is a dash everywhere it is stated, and the sales list stays.**
- **Decision:** the KPI tile reads "—" with the reason, the price strip drops its median marker, and the Market takeaway stops quoting a median (`takeaway.marketWithheld`). The verdict (`computeVerdict`) is untouched by design; it still reads the raw median.
- **Evidence: the plan's premise was wrong.** The plan assumed ¼-mile comp sets "usually have 5–20 sales". On the first 25 addresses of the lot panel (prod, 2026-10-21) the n values are 1 ×9, 2 ×6, 3 ×4, 4 ×1, and none reaches 5. 15 of 20 medians are withheld (n under 3), 5 are faded, **none is standard**. The comps KPI will read "—" on about three parcels in four.
- **Revisit if:** Jack wants a softer comps gate. It is one number each in `provenance.py` (`COMPS_HIDE_N_BELOW`, `COMPS_FADE_N_BELOW`), its tests and the guide, with no frontend change. The comps also differ between identical runs (item 14's finding), so a tile near the gate can flip between a value and "—" across reloads.

**Quiet means quiet, so some old hints are gone.**
- **Decision:** the Property card's `sourceHintFor` is replaced by captions plus a "Source:" line in the label's tooltip. The old "(owner-reported, energy benchmarking)", "(assessor commercial valuation)" and "(condo unit)" suffixes no longer print: those entries are tier A in a standard state, which the guide says stays quiet. They now live in the tooltip. The 2015 footprints and the lot area from the parcel polygon, which are tiers A-old and D, do print.
- **Revisit if:** owner-reported floor area should stay visible. Add `chi.energy_benchmarking` to `CAPTION_SOURCES` in `confidence.ts`.
- **Also quiet:** zoning standards (tier B), overlays, crime, incentives, flood. They are wired (a stale or low state will speak) but print nothing today. Crime's scope goes in the tooltip ("Covers: West Town") rather than a caption, because the figure is tier A.

**Calculations name their basis, not a date, and not "our calculation" when something else is said.**
- **Decision:** a calculation prints its method only when nothing else would print; it never prints an as-of date (its inputs have dates, it doesn't). A calculation that carries a `source` string (the lot area: "Parcel polygon area (Cook County property-tax database)") prints it.
- **Found in the browser:** the first version named any `cook.ptaxsim` calculation "Parcel polygon, county tax database", and so captioned the **class norm** that way too. Both entries list `cook.ptaxsim` as source and input, so the backend fields can't tell them apart. The `source` string can. The cost: that one caption is the backend's English, not a translated key.
- **Revisit if:** more calculations need a named basis. Give the entry a `method_params.basis` key and translate it.

**Two things with no entry get a static caption.** The Profile's violation category rows come from the address-scoped entry, which has no category fact (`area.violations.categories` is area-scoped and absent here). The rows say "Grouped by keyword (our grouping)" through `MethodCaption`, and the 311 high-risk list says the list is ours.

**Narrow tiles wrap the year instead of cutting it.** Found at 360 px in the browser: "$83K/yr (2024)" was ellipsized to "(…" because the value line truncates. The value and its note now sit in a wrapping flex row.

**The hatch has one user.** `.bg-hatch` is in `index.css` and the FAR meter uses it when FAR used is low. No other Profile fill can be low today: the Profile draws no bars from tract or benchmark figures. SVG charts and maps are not changed.

**CSV.** `buildScorecardCSV` takes the provenance map: rows with an entry gain Source, Authority, As of and Note (the page's own caption). A withheld figure is blank with its reason. Rows without an entry keep empty columns, so the file's shape is stable.

**Not built.** `stale` (amber date) waits for entries to carry it (WS6 M6). `unavailable` is built (`unavailable` prop, tested) but nothing passes it yet (WS6 M7).

**Verification used no model and no local backend.** A scratch stub replayed `/api/scorecard`, `/api/area-stats` and `/api/parcel-map` recorded from prod (read-only GETs), plus one mutated copy with a faded comps median and a faded FAR to exercise the low state. It lives outside the repo.

**Numbers** (2026-10-21)

| Measure | Before → after | Reproduce |
|---|---|---|
| Frontend tests | 341 (41 files) → 459 (47 files); the locale guard grows 38 → 106 tests as it covers the new `es` keys | `cd frontend && npm test` |
| Backend tests | 1,923 → 1,926 | `make test` |
| Lint warnings (cap 67) | 67 → 67, 0 errors | `cd frontend && npm run lint` |
| Main bundle | 3,922.18 kB (1,118.60 kB gzip) → 3,972.09 kB (1,131.57 kB gzip); CSS 103.10 → 103.32 kB | `cd frontend && npm run build` |
| Captions per Profile, 25-address prod sample (entries at the captioned sites that pass `wantsCaption`) | mean 6.1, range 4–10; 129 standard, 19 withheld, 5 low | `curl "https://urbanlayerchicago.com/api/scorecard?address=<first 25 of eval/lot_panel.json>, Chicago, IL"`, apply the rule to the provenance map |
| Comps sample sizes, same 25 | n = 1 ×9, 2 ×6, 3 ×4, 4 ×1 (20 with comps); 15 withheld, 5 low, 0 standard; 3 of 20 searches widened | same |
| Phone audit, Profile route | 5 of 5 devices, no horizontal overflow | `cd frontend && npx playwright test -g scorecard` (against the replay stub) |

**Not measured:**
- The other seven phone-audit routes (only the Profile changed; they need the full backend).
- Spanish rendering: new `es` strings are English and listed in `_untranslated.json`.
- Screen-reader reading of the captions and tooltips.
- The caption count includes only entries on the Profile payload; the area benchmark's caption comes from a separate request and is not in the 6.1.

**Production** (2026-10-21, after the deploy of #80; docs only)

| Check | Result | Reproduce |
|---|---|---|
| Served bundle | carries the caption copy ("City footprint survey", "Low confidence", "Couldn't be checked today", "Walk Score® (private company)", "Not shown: only") | `curl -s https://urbanlayerchicago.com/` → the `assets/index-*.js` it names, `grep` the strings |
| 1601 N Milwaukee, rendered in headless Chromium (dark and light) | KPI strip: assessed "$398K (2026)", tax "$83K/yr (2024)" with "Government model" and "class norm ≈5.3% · tax year 2023", benchmark "14,001 parcels · 44% coverage", comps "—" with "Not shown: only 1 sales (needs 3)". 12 captions on the page: the 2015 footprint stories, the 1996 survey, the lot area, Walk Score ×2 (Walk and Transit) and the rest as above | a Playwright script that loads `/scorecard?address=1601%20N%20Milwaukee%20Ave` and reads `[data-testid=confidence-caption]` |
| Comps repeatability | the same address had 2 sales in the morning's replay and 1 sale now: the tile is "—" either way, but the figure in the reason moves | same |

**Found after the deploy, not fixed here:** the withheld sentence reads "only 1 sales" (the unit is not pluralized). The fix is a `_one`/`_other` pair in `confidence.withheld.small_sample` and `confidence.sampleN`.

**Not measured:** the live browser tool was unavailable for the post-deploy check, so the DOM and screenshots came from a local headless Chromium against the live site; the admin and signed-in views were not checked.

## Item 16: passed, but not yet on the City map (#82, #83, 2026-10-21)

**The ordinance is matched on its record number, and "off the map" means no polygon carries it.**
- **Decision:** a passed rezoning is *on the map* when at least one layer-1 polygon has its record number in `CLERK_DOCNO`. The check is one batched `IN (…)` query (40 records) with distinct values, and an unreachable or erroring map raises `MapCheckUnavailable` (never "everything is off the map").
- **Alternatives:** also try the original record number and the number with the leading `S` removed (the plan's note about substitutes). **Evidence:** over all 352 passed rezonings of the last year the exact record number found 272 and the two variants added none, so they were dropped.
- **Result:** 80 are off the map today (the plan counted 79 on 2026-10-20). 42 of them passed on **July 15**, 98 days ago: a whole Council meeting's batch is still unmapped, past the plan's 90th percentile of 114 days only for the oldest, but well past the 90 days the coverage note promises.

**A title is parsed or it is listed. It is never repaired.**
- **Decision:** `address_titles.parse_title` returns segments (direction, street, type, range, side) or flags the title `partial`/`unparsed` with the reason. A partial parse gets no parcel flag. `backend/rezoning_overrides.json` (empty at first) is where a reviewed hand mapping goes.
- **Evidence:** 346 of the 352 recorded titles (98.3%) parse clean. The six that don't are the ones that should not be guessed: two reversed ranges ("1236-1230", "7600-7400"), two fused numbers ("34013551"), one typo ("75t St") and "W Fulton Market" (no street type). The test pins that exact list, so a new unreadable title is a decision, not a drift. Four formatting variants found while reading real titles are handled: `St- App No.`, no dash before `App No.`, no label (`- A-9059`), and a spelled-out type (`95th Street`).

**The parity rule stays, and the backtest says why.**
- **Decision:** both ends odd → odd side; both even → even; mixed or a single number → both.
- **Alternative tried:** when the parity-filtered query finds nothing, retry on both sides. **Evidence:** for those segments only 7 of 60 resolved parcels (2 of 29 on narrow ranges) sat on a polygon carrying the ordinance. They are mostly across the street, so the retry would have flagged the wrong parcels.

**Address Points is the resolver, and it only knows built addresses.**
- **Evidence:** of 269 clean on-map ordinances, 207 (77.0%) resolve to at least one parcel. The rest name addresses with no point (vacant lots are not in the dataset), so a parcel on one of them is not flagged. On today's 80 off-map ordinances, 77 have clean titles, 54 resolve to parcels, 23 resolve to none, and 3 titles are unreadable.
- **Revisit if:** the 23 matter. The Assessor's parcel-address dataset (`3723-97qp`, already used by `parcel_addresses.py`) carries vacant lots and would raise coverage; it needs its own backtest.

**What the backtest measured, and its limit.**
- 463 parcels (up to 8 per ordinance) from 207 on-map ordinances: **445 sit on a polygon carrying the ordinance: precision 96.1%** (gate 95%). Of the 18 misses, 4 are a newer ordinance on the same polygon (superseded); the other 14 are mostly polygons with no ordinance number at all. Excluding the superseded, 96.9%.
- **Wrong street: 0 of 463**, checked independently by asking Address Points for each sampled PIN's own streets, not through the range query that found it.
- **Limit:** the check is a point lookup at the parcel's address point, which can sit on a polygon edge, so some misses are the check's, not the resolver's. Per-parcel recall isn't measured (a polygon is not a parcel).

**The match is on the PIN first and the address only when the PIN is withheld.**
- **Decision:** `matches_for` flags a parcel whose PIN is in an off-map ordinance's set, unless the parcel's live map record already carries that ordinance. An approximate parcel (PIN withheld) is matched on the parsed address: direction, street, number in range, parity, and a street type that doesn't contradict. The snapshot must have been checked within 14 days, because a stale list could name an ordinance that has since reached the map.
- **Where it lives:** `ContextObject.passed_not_on_map` (a computed field, like `code_currency`), not `ZoningSummary.passed_not_on_map` as the plan named it, because the match needs the address and the PIN, which `ZoningSummary` doesn't have. It reaches the Profile JSON, the chat context and the report through the same object. It is a list, not one record, because two ordinances can list an address.
- **Wording, everywhere:** "a rezoning listing this address", never "rezoned", never to what. The chat rule says so, and tests assert the phrases.

**A rezoning failure never costs the code-amendment check.** `_rezoning_part` keeps the previous rows and records `rezoning_check.status = failed`. The map check and the Clerk query both fail loudly. The snapshot grows from about 20 KB to 357 KB (the parcel lists).

**Verified live, with no model call.** A real sync run (Clerk, the City's map and Address Points; 17 s) put 6711 S Western Ave (PIN 20193000320000) in O2026-0028350 (Oct 14, off the map), matched by PIN; 1218 W George St (on the map, rezoned in June) and 4000 N Western Ave get nothing.

**Found along the way.**
- The City's zoning server answers **403** to a custom `User-Agent` (it did not for the app's own shared client). The backtest uses that client.
- The sync fixture in `test_legislation_currency.py` needed an autouse stub for the new Clerk call; the network guard caught it.

**Found after the deploy: the Profile matched on the address, not the PIN.** On prod, 6711 S Western Ave came back `matched_by: address`, though its PIN is in the ordinance's parcel set. The Profile's `ContextObject.parcel_pin` was never set (the assembler takes it from the chat plan, and the Profile path has none), so the computed field fell back to the address. It still flagged this parcel, but a corner lot or a parcel whose other address point sits outside the listed range would have been missed. Fix (a follow-up PR): `scorecard()` and the report builder set the context's `parcel_pin` and `parcel_resolution` from the reconciled identity; a test pins a PIN-only match. Local checks had passed because the unit tests built the context by hand with a PIN. **Lesson:** a check that builds its input by hand can't catch an input the real path never sets; the live check did.

**Not built: landmark designations (the accepted Q9 answer).** The plan folded "passed landmark designations not yet on the map" into this item at about half a day. It is not half a day. Designations are a different Clerk category (`HISTORICAL LANDMARKS | Designation`: 3 passed since July, one of them a district named by "900 through 1100 blocks of W Bryn Mawr Ave"), their titles use a different grammar, and the landmark map layers carry no ordinance number to check against (layer 5 has a name, address and designation date as text). So "not yet on the map" would be a fuzzy name match, which is the opposite of this item's rule. It needs its own design. Proposed as a follow-up item.

**Numbers** (2026-10-21; public sources only, no model)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 1,926 → 1,979 (+53: parser 25, rezonings 28) | `make test` |
| Frontend tests | 461 → 470 | `cd frontend && npm test` |
| Lint warnings (cap 67) | 67 → 67, 0 errors; build passes | `cd frontend && npm run lint && npm run build` |
| Titles that parse clean | 346 of 352 (98.3%); 6 listed | `PYTHONPATH=. python -m eval.rezoning_backtest` |
| Backtest precision | 96.1% (445 of 463 parcels); 96.9% excluding superseded; wrong street 0 of 463 | same |
| Clean on-map ordinances with at least one parcel | 207 of 269 (77.0%) | same |
| Off the map today | 80 passed rezonings; 77 clean titles, 54 with parcels, 23 without, 3 unreadable; oldest waiting 341 days (one from Nov 2025), 42 from July 15 | `python -m backend.legislation.sync --print` |
| Sync with rezonings (Clerk + map + Address Points) | 17 s for 352 ordinances; snapshot 357 KB | `python -m backend.legislation.sync --out <file>` |
| Phone audit, Profile route | 5 of 5 devices, no overflow | `cd frontend && npx playwright test -g scorecard` (replay stub) |

**Not measured:**
- The first prod sync after deploy (the live snapshot has no rezonings until it runs).
- Per-parcel recall.
- How often a parcel the Profile flags is one the reader cares about (no usage yet).
- The other seven phone-audit routes.
- Spanish rendering (new strings are English, listed in `_untranslated.json`).

**Production** (2026-10-22, after the deploys of #82 and #83 and the first prod sync, run by hand with `sudo systemctl start legislation-sync.service`)

| Check | Result | Reproduce |
|---|---|---|
| First prod sync | `status=ok`, `rezonings: ok passed=352 off_map=80 flaggable=77 unparsed=3 no_parcels=23`: the same counts as the local run | `sudo journalctl -u legislation-sync.service -n 25` on the server |
| 6711 S Western Ave, after #82 only | flagged (O2026-0028350, "6701-6731 S Western Ave") but `matched_by: address` and the context's `parcel_pin` was null | `curl "https://urbanlayerchicago.com/api/scorecard?address=6711+S+Western+Ave"` |
| 6711 S Western Ave, after #83 | `parcel_pin` 20193000320000, `parcel_resolution` authoritative, `matched_by: pin`, coverage note `passed_not_on_map` | same |
| 1218 W George St (on the map, rezoned June) | `passed_not_on_map` absent; live map ordinance O2026-0025358 | same, `address=1218+W+George+St` |
| 4000 N Western Ave | absent | same |
| `/health` | `data_health.checker: ok` | `curl https://urbanlayerchicago.com/health` |

**Not measured:** the rendered amber box and the paid report's warning on prod (both tested offline and the box checked against a replayed payload; the report needs a purchase or an admin download). The 06:00 timer's own first run. `docker` is not available to `jack`, so any manual run needs `sudo systemctl start`.

## Item 17: contracts and daily sentinels (#85, 2026-10-22)

**The fields we read come from the code, by a scanner, and the list is committed.**
- **Decision:** `contracts --scan` takes each Socrata source's reader modules, collects every lowercase word inside a string literal, and keeps the ones that are columns of the live dataset. The result (`fields_read.json`: 37 sources, 280 columns) merges into each source's `required_fields`; a column the publisher renames or drops is an `error` on the next run. A test fails if a listed column is no longer mentioned by its modules, and if a new Socrata source with named columns has no entry.
- **Alternatives:** hand-typed lists in the registry (37 sources, and they drift); a runtime import of each module's query constants (modules build queries inline, so there is nothing to import).
- **Limit found while building it:** the assessor sources' own modules only *fetch* rows (`assessments.py` names `pin` and `year` and nothing else); the facts are built in `retrieval/property/__init__.py`. The first scan therefore gave `cook.assessor.values` 2 columns, not 12. `EXTRA_READERS` adds that module for the six property sources (values 2 → 12 columns, characteristics 2 → 19). Any other source whose reads happen in a different module than its fetch has the same blind spot.
- **Heuristic:** a word that is also a column of another dataset but is read for a different purpose is included. The cost is a false alarm only if that column later vanishes, which a person would want to hear about anyway.

**Value sets are three, chosen where a misread changes a fact.** Layer 1 `ZONE_CLASS` must start with a known district family (checked over all 1,526 distinct values: mostly `PD n`, plus typos like `RM4-.5` that still start with a family; every class in our zoning table starts with one, which a test asserts); layer 6 `LANDMARK` is Y or N; Address Points `st_predir` is a compass word. Wards (50) and community areas (77) have exact count bands; ward offices 45–55.

**One sentinel source, not thirteen.** `internal.sentinels` (critical) runs every parcel and reports the failures in its reason. *Alternative:* a source per parcel (13 rows on the panel, 13 alarms when the City renames a layer). One alarm per cause is the point; the reason names each parcel and field.

**The first live run alarmed on 8 of 13 parcels; none was a real misread, and each cause changed the design.**
- **Coordinates.** The kit key's overlay set for P11 includes the National Register property "The Cornelia", which the Assessor centroid misses (it sits 150 m away on a large parcel) and the address point hits. The sentinels now use the point the Profile resolves the address to (Address Points), and fall back to the centroid only for a vacant lot (P2, which has no address point).
- **`adu_area` and `tod_metra`** came back on parcels the key doesn't list them for: layer 17 now covers most of the city ("Zone 1, no limitations"; the key encodes ADU through field F for RS districts), and the key's "tod" is the CTA layer. *Alternatives:* edit the key (it is hand-verified and belongs to the kit), or alarm (permanently red). Decision: `UNCURATED_EXTRA` — finding one of these not in the key is not a mismatch; a key-listed overlay must still be found. *Revisit if* a misread of either becomes plausible: move them into the key.
- **A string match hid an overlay finding.** When an overlay layer is down the run keeps only district findings; the first version filtered on the word "district", which also appears in `special_district`. The test caught it; the comparison is now two functions (`compare_district`, `compare_overlays`), not a text filter.

**An alarm is never re-baselined automatically.** It is either a City data change (review, re-key the kit, regenerate `sentinels.json`) or our code reading it wrongly. The alarm text names the parcel and field, and flags a landmark type the key says is absent with "F8".

**The F8 replay is a recorded fact, not a story.** The live layer-7 hit at P11 (survey rating orange) is a fixture; the pre-fix layer mapping applied to it derives `landmark_building`, the key says there is none, and the sentinel alarms; with today's mapping the same hits are clean. A separate test keeps layer 7 out of `OVERLAY_LAYERS`.

**The positive control is 5749 W Race Ave** (Marie Schock House, designated 1999-01-20 on the official list `tdab-kixi`; layer 5 covers it). Note the list calls it L-225 and layer 5 labels it L-224: a discrepancy between the City's own sources, harmless here.

**Numbers** (2026-10-22; public sources only, no model)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 1,980 → 2,013 (+33: contracts 17, sentinels 16; four existing tests updated) | `make test` |
| Frontend tests | 470 → 471; lint 67/67 warnings, 0 errors; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Fields-read contracts | 37 sources, 280 columns (before the assessor readers: 245) | `python -m backend.data_health.contracts --scan` |
| Live schema check | all 280 columns exist today (no `MISSING LIVE`) | same |
| Sentinels, live | 13 of 13 match (12 kit parcels + the control); 2.7 s end to end, cold | `python -m backend.data_health.sentinels --check` |
| First sentinel run, before the two fixes above | 5 of 13 matched; 8 flagged (7 `adu_area`, 3 `tod_metra`, 1 missing `national_register`) | same, at the first commit |
| Full dry run | 81 sources, 106 HTTP requests in 2 to 4 s; contracts and sentinels add no `error`; the 1 alarm is the stale local Discovery index, unchanged | `python -m backend.data_health.check --dry-run` |

**Not measured:**
- The production run (needs the checker started by hand with `sudo`; the timer's first run after deploy will also show it).
- How often the key and the live overlay set legitimately drift (one run proves nothing about the alarm rate; the first 14 days are Sentry-quiet by design).
- Contracts on ArcGIS layers beyond layer name, count band and the two value sets (no fields-read lists for layers; the overlay readers take attributes by name inside `regulatory/`).
- The request count of the sentinels: they use production's own clients, so the checker's HTTP tally does not include them (about 13 × 15 City map calls).

**Production** (2026-10-22, after the deploy of #85)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; the served bundle carries the panel's new contract text ("Value sets: …") | `curl -s https://urbanlayerchicago.com/` → the `assets/index-*.js` it names, `grep "Value sets: "` |
| `/health` | `ok`; `data_health.checker: ok`; 1 alarm (the stale local Discovery index, as before) | `curl https://urbanlayerchicago.com/health` |
| Anonymous admin | `/api/admin/data-health` answers 401 | `curl -i https://urbanlayerchicago.com/api/admin/data-health` |
| Profile | 6711 S Western Ave still resolves and matches `passed_not_on_map` by PIN | `curl "https://urbanlayerchicago.com/api/scorecard?address=6711+S+Western+Ave"` |

**Not yet verified on prod:** the acceptance run (sentinels 13/13 and the contract results on the panel). It needs the checker started on the server, `sudo systemctl start data-health-check.service`, or the 05:37 UTC timer. After it runs, the admin panel's `internal.sentinels` row should read "13 of 13 sentinels match the answer key" and every Socrata row's contract cell should read "N fields …". Until then the only evidence is the local dry run in the Numbers block above, which hit the same services.

## Item 18: CI artifact ages and the weekly kit (#87, 2026-10-22)

**Running the kit found a regression of mine from item 16.** The Profile kit run printed "Verdict text was unavailable (node missing?)" although node is installed. `eval/kit/verdict_text.mjs` loads `frontend/src/lib/scorecardVerdict.ts` in plain Node, and item 16 had added `import { formatDay } from "./format"` to it; `format.ts` imports i18n, which plain Node can't load. The eval test that checks the verdict script had started to *skip* ("this node cannot strip TypeScript types") in item 16, and I put that down to the node version instead of looking. The caveat now passes the ISO date to `t` (like the older "recently rezoned" caveat) and imports nothing heavy; the test runs again (eval tests 92 → 103 with the new gate tests). **Lesson:** a skipped test that appears in a PR is a finding; read the reason before explaining it.

**The artifact-age check warns and never fails.** `artifacts --ci` annotates a PR with a `::warning` per stale artifact and always exits 0 in CI mode; the step is `continue-on-error` as well (a test asserts both, and that every annotation is a warning, never an error). *Alternative:* fail the job past the alarm age. Rejected (plan Q7): it would block a hotfix deploy because a code export is old. Outside CI the same command exits 1 on a red artifact, so a person running it by hand sees it.
- Today it annotates one thing, the code text (126 days; warn 60, alarm 90), and its message says the data-health registry has acked it until 2026-12-15, so a PR author isn't left wondering whether it is news.
- **The zoning cache** now records `_meta.code_vintage` (the builder writes it; the committed cache was edited by hand to `2026-06-17`, the vintage of the 2026-10-21 reviewed rebase recorded in `fingerprint_rebased`, no rebuild and no model). A cache whose recorded vintage differs from the code text's is an alarm.
- **Transit stations get a sidecar.** `transit_stations.meta.json` (`built_at: 2026-06-01`, from the artifact's git history, and the build script now writes it on every rebuild). It is allowlisted in `.gitignore`, `.dockerignore` and the Dockerfile `COPY` (a test asserts all three), because the daily checker reads it on the box. The probe also notes the CTA feed's `Last-Modified` (2026-09-14), so "a rebuild may be due" is visible.

**The weekly kit judges against an accepted run, not against 2.** Gate: field A is 2 for every parcel, no confident-wrong claim, no cell below the committed `eval/kit/accepted_profile.json`. The first accepted run is today's Profile kit on prod (117/122, 12/12 districts, 0 confident-wrong, verdict text included) after reading its table. *Alternative:* fail on any score under 2 (the key has legitimate 0/1/NP cells today: P8's use question scores 0 and several are "no claim"). Ranking: a claim that falls to silence is a regression, and so is silence becoming a wrong claim; improvements are reported so the file can be refreshed on purpose (`--update-accepted`, never to make a red run pass).
- **The drill is in the workflow, not the data.** `workflow_dispatch` with `inject_mismatch` corrupts P1's district in the *scored copy*; the gate must fail (a test asserts three failures: A not 2, confident-wrong, fell from 2 to 0).
- **The alarm path is GitHub's failed-run email**, plus one Sentry event when a `SENTRY_DSN` repo secret exists (without it the gate says so and carries on). No new service.
- The kit run in the workflow is Profile only: `/api/scorecard` is free and anonymous. The chat surface (about $1.20 a run, production credits) stays the monthly production check.

**The registry reads the workflow through the public Actions API.** `eval.kit_weekly`: warn at 9 days, alarm at 16 days or when the newest completed run failed. Before the first run (the workflow isn't on the default branch yet: HTTP 404) it reads *unknown*, never red; a GitHub rate limit or outage is a transient probe error, never "the kit failed". With both M5 placeholders filled, every registry source now has a probe or is a frozen artifact (a test asserts it).

**Not verified here (needs the merge):** the workflow itself. I can't run a GitHub Actions workflow from my side before it is on the default branch. After the merge: dispatch it once normally (must pass), once with `inject_mismatch` (must fail and email).

**Numbers** (2026-10-22; public sources only, no model)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,013 → 2,033 (+20) | `make test` |
| Eval tests | 92 → 103 (+11 gate tests; the verdict-script test runs again instead of skipping) | `python -m pytest eval/test_judge.py eval/tests -q` |
| Frontend tests, lint, build | 471 / 67 of 67 warnings / passes | `cd frontend && npm test && npm run lint && npm run build` |
| Profile kit on production | accuracy 117/122 (96%), coverage 61/64, confident-wrong 0, districts 12/12; 3 minutes | `PYTHONPATH=. python -m eval.parcel_kit --full https://urbanlayerchicago.com --surfaces profile` |
| Same run before the verdict fix | 104/110 (95%), 55/64 coverage: the verdict-derived cells (B/E/F) were missing | same, at the first commit |
| Artifact ages today | 1 annotation (code text, acked); the other five ok | `python -m backend.data_health.artifacts --ci` |
| Daily dry run | 81 sources, 108 requests; no source without a probe; `eval.kit_weekly` unknown until the first run | `python -m backend.data_health.check --dry-run` |

**Not measured:** a scheduled Monday run; the Sentry path (no `SENTRY_DSN` secret is set yet: Jack's call); how often the accepted baseline will need refreshing.

**A test that passed locally failed in CI, for the same reason as the item 16 skip: I ran it before the new file was tracked.** `test_every_committed_data_artifact_is_registered` lists tracked files under `ingestion/data` (`git ls-files`); the new `transit_stations.meta.json` was untracked when I ran `make test`, so it never saw it. The test now treats a `*.meta.json` sidecar as belonging to the registered artifact beside it, and checks that one exists. **Lesson:** `git add` new files before the final `make test`, since several tests read the index.

**Production** (2026-10-22, after the deploy of #87 and one manual dispatch of the new workflow)

| Check | Result | Reproduce |
|---|---|---|
| CI on the PR | the artifact-age step ran, printed one `::warning` (the code text, 127 days, acked) and the job stayed green | the "Committed artifact ages (warn only)" step in the PR's `test` job |
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Weekly kit, `workflow_dispatch` (normal) | passed in about 2 minutes: accuracy 117/122, coverage 61/64, confident-wrong 0, districts 12/12; the run's artifact (192 KB, kept 90 days) was uploaded | Actions > Weekly parcel kit |
| Registry | `eval.kit_weekly` read the run through the public Actions API: `ok`, dated 2026-10-22 | `python -m backend.data_health.check --dry-run --only eval.kit_weekly` |

**Not yet verified:** the drill (`inject_mismatch`: the run must go red and email) and the Monday schedule's first run. The drill sends a failure email on purpose, so it waits for Jack's go-ahead.

## Item 19: confidence in the $25 report (#90, 2026-10-22)

**The report's provenance is built where the report is rendered, and a failure there never blocks a paid report.**
- **Decision:** `render_report_html` builds the map (`report_provenance.entries_for_report`) and binds `conf_caption`, `conf_state` and `sources_rows` as Jinja globals. *Alternative:* compute it once in `_fetch_report_data`. Rejected: the admin mock path and every direct render would then miss it, and the map depends only on the finished `ReportData`.
- A failure to build it is logged and leaves the captions quiet (an existing test hands the renderer a mock object; the first version raised on it, which is how I found the guard was needed).
- The report reuses the Profile's `build_provenance`, so the two surfaces can't disagree about a figure's tier or date.

**AI labels appear only where the cache holds AI-read data, and the report claims nothing else.** The cache's setbacks, permitted and special uses, parking and notes are tier E (`ai_read_code`, "not verified", the district's code section, the code vintage the cache was checked against); FAR, height and the lot standards stay with the Title 17 table (tier B, no caption). The envelope is tier D built on E ("built on AI-read setbacks"); it exists only when AI-read setbacks do. When the standards came from the table fallback (`extraction_confidence` low or `definitions`), no entry is made and nothing is called AI-read. *Evidence, three real parcels rendered from live public data (no model):*
- 1601 N Milwaukee (B3-2): AI labels on setbacks and notes (§17-3-0400); the comps median "Not shown: only 1 sale".
- 642 W Belden (RT-4, the taxable control): one AI label, on notes (§17-2-0300): the residential cache entries hold notes but no setbacks.
- 481 W Deming (the exempt control): no AI label and no AI row in the table (served from the table); the comps median is faded ("Low confidence · 3 sales · 0.55 mi · 3 yr (search widened)").
- **So the plan's acceptance, "shows the AI labels", is parcel-dependent.** A residential parcel shows few; I kept it honest rather than label what isn't AI-read. If AI setbacks for residential districts matter to the report, that is a cache-content question (a rebuild needs the production key), not a rendering one.

**The sources table is generated and the static one is gone.** One row per source actually used (registry name, publisher, authority class, how current, what it supplied), strongest authority first. 48 catalog keys (24 per language) went with the old rows, which named eight categories whether or not the report used them. Real counts: 33 rows (1601 N Milwaukee), 27 (642 W Belden), 23 (481 W Deming). A survey or tax year shows as its period ("2020–2024", "2024"), not "December 31, 2024"; the backend's one-year range "2003–2003" shows as "2003".

**Quiet by default, with the same words as the Profile.** `caption()` mirrors `frontend/src/lib/confidence.ts` (tier C–F, low or withheld, or a source over 24 months old). In the PDF a standard official record prints nothing. The report's own comps gate (median only for 3 or more sales) already matched the standard; the per-sqft median is now also hidden when the backend withholds it.

**Fixed along the way: "only 1 sales".** The unit didn't agree with the count on the Profile (item 15) or in the new report. Both now use plural keys (`confidence.unit.sales_one/_other`, `conf.unit.sales__one/__other`) with tests for one and many.

**The PDF layout needed one fix, found by looking at it.** The sources heading and its intro paragraph sat alone at the foot of a page with the table on the next; the intro now keeps with the table (`page-break-after: avoid`). The 1601 N Milwaukee PDF is 24 pages; the sources table starts on page 21.

**Numbers** (2026-10-22; public data, no model, no purchase)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,033 → 2,051 (+18) | `make test` |
| Frontend tests | 471 → 476 (unit-plural cases, locale guard); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Sources table rows | 33 / 27 / 23 for 1601 N Milwaukee / 642 W Belden / 481 W Deming; every row resolves to a registry name | render script over `_fetch_report_data` + `render_report_html` (scratch) |
| Captions on those pages | 3 / 1 / 1 (setbacks, notes, comps; notes; comps) | same |
| Live Profile provenance as a table input (56 entries) | 20 or more rows; 27 of 56 entries would caption (13 are ACS tract figures, tier C) | `test_report_sources_table.py` |

**Not verified:** an admin download from production (needs an admin session, so Jack); the Spanish PDF beyond the structure (new strings are English, listed in `_UNTRANSLATED_ES`); `make kit` replay (the kit scores the Profile and chat, not the PDF).


**Production** (2026-10-22, after the deploy of #90)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle carries the plural unit keys (`sales_one`) | `grep sales_one` on the `assets/index-*.js` the home page names |
| Report endpoint, anonymous | answers 401, not 500 | `curl -i "https://urbanlayerchicago.com/api/report?address=1601+N+Milwaukee+Ave"` |
| Profile | 1601 N Milwaukee still returns its 56 provenance entries | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |

**Not verified on prod:** the rendered PDF, which needs an admin session. To check it: signed in as admin, open `https://urbanlayerchicago.com/api/report?address=1601+N+Milwaukee+Ave` (B3-2) and look for "AI · Read by AI from §17-3-0400 · … · not verified" under the setbacks and notes, an envelope caption if the lot geometry exists, the comps caption, and a Data Sources table of about 30 rows ending with the AI note. `&mock=true` shows every section populated.

## Item 20: confidence in chat (2026-10-22)

**A withheld figure is removed from the context, not hidden by an instruction.** `provenance.withhold_low_evidence(context, provenance)` runs once per chat turn, after retrieval and before the context reaches the sidebar or the model. It reads each entry's `confidence` (decided in `confidence_state`; nothing is recomputed) and, for a `withheld` figure, clears the value (`_clear_figure`: a tract field with its margin and CV, a comps median, a community-area figure), lists it in `ContextObject.withheld_figures` with its reason in plain words, and strips `value` from its entry. *Alternative:* leave the number and tell the model not to say it. Rejected: a model that has seen "poverty 1.0%" can still say it, and the Profile's rule is that a withheld value never leaves the server. *Evidence:* `test_a_withheld_tract_figure_never_reaches_the_model_and_says_why` builds the synthesizer's exact input and asserts the number is absent and the reason present; `test_thin_comps_lose_their_medians_but_keep_the_sales` keeps the sales list (the standard says the list always shows).
- **Clearing works on a copy.** Retrieval results are cached and shared across requests (the census tract is a `TTLCache` entry), so clearing in place would withhold the figure from every later answer. `_own()` deep-copies the container first; `test_clearing_a_figure_never_edits_the_shared_cached_object` pins it.
- **A figure the rules can withhold must have a place to be cleared.** `test_every_figure_that_can_be_withheld_has_a_place_to_be_cleared` loops every tract field, comps median and community-area figure. A withheld figure with no known place is still listed (the model is told not to state it) and logs a warning.
- **The Profile handoff trims comps to 8 sales** (`MAX_COMP_SALES`). The comps thresholds are below 5, so the trimmed count gives the same state as the full set; `test_four_comps_are_faded_not_withheld_and_a_trimmed_handoff_does_not_change_the_state` says so.

**The map is stored, not sent; the model gets two short lists instead.** `ContextObject.provenance` rides the SSE context chunk and `messages.context_json` (a reopened answer keeps the dates it was given) and is excluded in `synthesizer._build_user_text`. The model gets `withheld_figures` and `figure_notes`. *`figure_notes` is not in the plan's list, and I added it:* without it the rule "name estimates, calculations and AI readings as such" has nothing to act on, because the model never sees a figure's tier. It carries only figures that are `low` or tier D/E/F (an ACS tract figure is a standard official estimate, and rule 38 already asks for its period and margin), capped at 16. *Alternative:* send the whole map. Rejected on size: 56 entries are **36 KB** for 1601 N Milwaukee (the plan guessed 10–25 KB). The same list for the sample area-only turn is 499 bytes.
- **Storage is bigger than the plan guessed.** A parcel turn stores about 36 KB of provenance per answer, an area-only turn about 10 KB (15 entries). *Revisit if:* the conversations database grows noticeably; the compact form in the plan (ids, tier, dates, `value`, confidence) is still available. The field is capped at 400 entries so a saved message can't carry an unbounded map (`test_a_saved_message_cannot_carry_an_unbounded_map`).
- **Failure leaves chat working.** If building the map raises, it is logged and the answer streams without it (as with analytics). A bug there would show as a missing footer and sidebar captions, not a failed chat.

**Area-only turns now get a sources footer.** `_provenance_for` returned `{}` without a parcel district; that guard is gone, so a crime or census question carries dated entries, and the footer adds one line per area source: publisher's name, area, the period or "data through" date (or "queried" when the publisher gives none), the 90% margin-of-error level when one is published, and the bracket-median caveat. The heading reads "Sources for the data used" on an area-only answer and keeps "Sources for the parcel data used" otherwise. One existing test (`test_chat_streams_token_events`) counted two tokens and now sees the footer as a third; I changed it and said why.

**The sidebar prints margins and reasons, not a caption on every row.** An ACS figure is tier C, so the quiet rule would caption all 13 tract rows in a 360 px rail. Instead each figure shows its `±` margin where one is published, the section prints one line saying what `±` is, a withheld figure becomes a line ("Poverty: Not shown: the margin of error is 61% of the estimate."), a low community-area income is quieter (the existing caption already says why), Walk Score is captioned as a private company's index, and the violation grouping as ours. *Alternative:* a caption per row (Q3's alternative). Rejected for density. Checked in the browser on a stored conversation (no model): desktop and 375 px, no horizontal overflow.

**Prompt rule 38** asks for the period of any area statistic, "give or take" for a tract estimate, "roughly" and "estimated" for the bracket income, never a withheld figure (and its reason in words), and says `data_as_of` is the day we ran the query. It is pinned by presence only; whether the model follows it is not measured here.

**What it costs: the rules remove more than I expected.** Across 54 real Chicago tracts (697 figures), measured 2026-10-22: 534 standard (77%), 124 faded (18%), **39 withheld (6%)**; 29 of the 54 tracts lose at least one figure. The losses are concentrated in rates on small tracts: vacancy rate withheld in 14 of 54 (low in 29 more), unemployment 11 (low in 37), foreign-born 11. Population, income, rent, home value and the city and county medians are never withheld. That is the CV > 50% ceiling from Q1(c) doing what it was written to do, but vacancy and unemployment are tract figures a developer might ask about. *Revisit if:* Jack wants them shown faded with the margin instead of withheld (a one-line threshold change in `provenance.py`; the Profile does not show tract rates, so this affects chat only).

**Found along the way:** Census Reporter answers **429 ("too fast")** to a burst (6 concurrent requests, about 130 total), and blocked my client for at least ten minutes. Production is unaffected (its own address and one tract per question), but the scratch script returned "no data" for blocked tracts without saying so; `eval/tract_confidence.py` now fetches one tract a second.

**Numbers** (2026-10-22; public data and fixtures, no model, no production key)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 2,051 → 2,070 (+19, `test_chat_confidence.py`) | `make test` |
| Eval scorer tests | 103 → 104 (`test_tract_confidence.py`) | `make test` |
| Frontend tests | 485 pass, 8 new in `sidebar.confidence.test.tsx`; lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Tract figures: standard / faded / withheld | 54 tracts, 697 figures: 534 / 124 / 39 (77% / 18% / 6%) | `PYTHONPATH=. python -m eval.tract_confidence` (see below) |
| Tracts losing at least one figure | 29 of 54 | same |
| Provenance stored per answer | parcel handoff 56 entries, 36 KB; area-only sample 15 entries, 10 KB | `backend/tests/fixtures/profile_provenance_1601_milwaukee.json`; the sample is a scratch seed |
| Added to the model's input | `figure_notes` + `withheld_figures`: 0.6 KB on the area-only sample | scratch seed |
| Time to build, withhold and note a turn | 0.1 ms (area-only context, mean of 50; the data-health store read is cached) | scratch timing |

**Not measured, and why:**
- **`make kit` (chat).** The plan's acceptance is "scores not below the 2026-10-01 baseline" and "a neighborhood answer states the ACS period and margin". Both need the live model, which is production credits and off limits for build work. What is proven instead: the rule's text, that the period/margin/withheld data reach the prompt input, and that a withheld value does not. Not proven: that the model follows rule 38, or that it does not over-hedge because of `figure_notes`. A kit run, or a replay with the answers read in conversation, would close it.
- **The tract numbers above came from a scratch version of `eval/tract_confidence.py`** (same logic, 6 concurrent requests) before Census Reporter blocked my client; the committed script (one request a second) could not be re-run when I finished because the block hadn't lifted. Rerun it to confirm.
- **Spanish:** the one new key (`neighborhood.marginNote`) is English in `es` and listed in `_untranslated.json`.

**Production** (2026-10-22, after the deploy of #92)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle carries the rail's margin note ("90% margin of error") | `grep "90% margin of error"` on the `assets/index-*.js` the home page names |
| Profile payload unchanged | `context` has no `provenance`, `withheld_figures` or `figure_notes`; still 56 provenance entries for 1601 N Milwaukee | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |

**Not verified on prod:** the backend's chat path. No read-only request reaches it (the chat route spends the production key, and OpenAPI is off), so the deploy job's success is the only evidence the new image is running. To check it: ask any neighborhood question in chat and look for a "Sources for the data used" block with a period and the 90% margin-of-error level, and, in the Data panel, the tract's `±` margins. A tract with a very wide margin (a small tract's vacancy rate) should show "Not shown: …". Rule 38's effect on the answer text is not measured anywhere yet (no `make kit`).

## Item 21: data dates on every answer, report and Profile (#94, 2026-10-22)

**Most of M6 was already done; what was left is one builder and three places that show it.** WS0 had already taken the typed years out of the report wording (M1), renamed the Profile's "Data as of" to "Checked" (M1) and generated the sources table from the registry (M5). *Evidence:* the new lint finds no year range typed into `report_i18n.py`, the template, the locales, the footer or the prompts. What remained: a list of the headline dates, the chat line, the cover box, and the dates on the Profile.

**`vintages_for` reads the provenance map, not the context and the registry separately.** The plan had it combine record-level dates from the context with source-level dates from the registry status. *Alternative:* a second builder over the raw context. Rejected: WS0's provenance already resolves the precedence (the response's own date, then the data-health store, then the registry's frozen vintage), so a second builder would one day disagree with the captions. Run over the recorded 1601 N Milwaukee provenance it returns 8 dates; each equals its entry's date.

**A source with no date says when we asked.** A figure whose source gave no date gets kind `checked` ("Sales checked Oct 22, 2026"), not silence and not the query date dressed as a data date. *Why:* silence reads as "current". *Seen locally:* with no data-health store, sales and violations read "checked"; on production the store supplies "through <date>" (the recorded production fixture has "through" dates for both).

**The code's date is said once.** When the answer cites standards or code, the footer already prints the code-currency line ("Code text current through Jun 17, 2026 · 10 later zoning amendments"), so the Data dates line leaves it out; on a crime question the code date is not shown at all (it would be a date nobody asked for). The amendments count follows `code_currency`'s check state: fresh gives a count, aging a count with "as of", unknown "couldn't check recently", never a bare count.

**The area source lines lost their dates.** In item 20 I put "data through" and the survey period on each area line; with one Data dates line they would say everything twice, so the lines now carry the area, the window ("last 90 days") and the margin level. The tests I wrote in item 20 changed with them.

**The cover.** "Report Date" is now "Generated on <date>" plus a "Data as of" box (two columns, left-aligned). The cover already ran onto a second page (the map and the identifiers sit there), and the report is 24 pages before and after. "Not checked in this report:" lists the report's `partial_failures`, which are English labels today; M7 replaces them with per-source statuses.

**The Profile footer** shows the same list in the reader's language (`lib/dataDates.ts`, `dataDates.*`), beside "Checked <day>", which now prints "Oct 22, 2026" rather than the raw ISO date that sat next to it. Three catalogs word the same dates (chat and PDF: `dates.*`; Profile: `dataDates.*`); `test_the_frontend_wording_matches_the_backend_catalog` keeps them equal and checks every noun the builder can emit has wording.

**Not built, on purpose: the probe-versus-label alarm.** The WS6 plan said a mismatch between a source's `displayed_label` and what its probe reads would alarm until labels were registry-derived. No wording carries a typed vintage any more, so there is no label to compare; the lint guards that instead. *Revisit if:* a vintage is ever typed into a string again.

**Numbers** (2026-10-22; public data, no model)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,070 → 2,085 (+15, `test_data_dates.py`) | `make test` |
| Frontend tests | 485 → 512 (+4 for `dataDates`, +23 from the untranslated-keys guard, one per new `es` key); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Mobile overflow audit | 40 of 40 (8 routes, 5 phones) with the new footer | `cd frontend && npm run test:mobile` |
| Dates on the Profile and the cover, 1601 N Milwaukee | 8: zoning map record Dec 15, 2021; code text through Jun 17, 2026 (+10 later amendments); Assessor values 2026; tax year 2024; sales; ACS (tract) 2020–2024; crime through Oct 15, 2026; violations | `GET /api/scorecard?pin=14313320180000` (`data_dates`); render script over `_fetch_report_data` (scratch) |
| Report length | 24 pages before and after | same render |

**Not verified:** production (the report PDF needs an admin session, and the store-backed "through" dates for sales and violations only exist there); the Spanish pages beyond structure (new wording is English, listed in `_UNTRANSLATED_ES` and `_untranslated.json`); the chat footer end to end against the live model (no key used).

**Production** (2026-10-22, after the deploy of #94)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle carries the data-dates wording ("later zoning amendment") | `grep` on the `assets/index-*.js` the home page names |
| Profile payload | `data_dates` has 8 entries for 1601 N Milwaukee: zoning map record 2021-12-15, code text through 2026-06-17, Assessor values 2026, tax year 2024, **sales through 2026-08-12**, ACS (tract) 2020–2024, crime through 2026-10-15, **violations through 2026-10-20** | `curl "https://urbanlayerchicago.com/api/scorecard?pin=14313320180000"` |
| Report endpoint, anonymous | still 401 | `curl -i "https://urbanlayerchicago.com/api/report?address=1601+N+Milwaukee+Ave"` |

On production the store supplies the sales and violations dates ("through"); locally those read "checked", as expected.

**Not verified on prod:** the report PDF cover (needs an admin session: look for "Generated on", the "Data as of" box with the eight dates, and no "Report Date") and the chat footer's `Data dates:` line (the chat route spends the production key; ask any neighborhood or parcel question and look for it under the sources block).

## Item 22: partial failures, shown honestly (#96, 2026-10-22)

**The overlay half of M7 shipped in item 1; what was left turned out to be where the real silence was.** Overlays already said "couldn't check". The plan's list for the rest was module rows, a chat line, a report notice and live telemetry. Forcing the Assessor sales source to fail (the new fault flag, below) showed a worse gap: **the Profile lost its comps and its sales history and `partial_failures` stayed empty.** Reading why:
- `get_assessments` and `get_sales` caught an error, **cached "none on file" for 24 hours** and returned empty;
- the comparable-sales query caught an error and returned "no comps", which its caller **cached for an hour**;
- `get_characteristics` swallowed the error and returned None.

So an outage of the Assessor's feed would read as "no sales, no comps" for up to a day, with no caveat. *Evidence:* an AST scan of `backend/retrieval` for `except` handlers that store a negative result in a cache finds exactly three (assessments, sales, address points); address points' is a parse guard, not an outage, and the other two are fixed. All four calls now **raise and cache nothing**; the property domain (already built to catch exceptions) turns that into a gap, and the comps callers (scorecard, report) already turned an exception into "comparable sales". Five existing tests asserted the old behavior, including one named `test_negative_cache_prevents_retry` for the failure case; I rewrote them to say a failure raises and is not cached while a genuinely empty answer still is.
- **A gap is not always a failure.** `property assessments` and `property tax estimate` also appear for an exempt parcel, which has none. Showing "couldn't check" there would be false, so `PropertySummary.failed_calls` holds only the gaps that were a call failing, and only those go to the Profile's `partial_failures` (`test_a_record_the_source_does_not_have_is_a_gap_but_not_a_failed_call`). Chat already carried every gap.

**One table of what failed.** Three places had their own label dicts (chat retrieval, scorecard, report) and one literal ("comparable sales"). They now draw from `data_health/failures.py` (`LABELS`, `MODULES`, `failed_detail`), so the Profile, chat and report agree. `/api/scorecard` carries `failed_sources: [{key, labels}]`: the key places a failure in a module, the labels (what actually reported it, e.g. "property sales history") word it. The frontend's module table equals the backend's; a pytest reads the TypeScript and compares.

**Surfaces.**
- **Profile:** each of the five modules (Build, Costs, Market, Record, Area) shows an `UncheckedRow` at its head when its source failed, and a module with nothing else in it now stays on the page and the section rail. The Regulatory card keeps its own overlay row, so a `regulatory` failure only gets the module row when there is no card. The verdict has its own caveat when the district lookup failed ("can't say what district the parcel is in") instead of burying "parcel zoning" in the generic list.
- **Chat:** a `**Couldn't check today:**` line, written by us, after the sources block (or alone when there are none), so honesty no longer depends on the model following prompt rule 16.
- **Report:** a notice at the head of each section that left a source out (zoning, property, market, financial, site condition), using the words that reported it; the cover's "Not checked" line is item 21's.

**Live failure rate, in a file the app owns.** `live.py` counts each call's outcome per registry source (once per call, not per retry) in `socrata_get`, the overlay layers, the zoning layer and the census tract call; an hourly flush writes `backend/data/data_health_live.db`; the checker reads the last 24 hours (over 20% of at least 10 calls is `warn`, over 50% `alarm`). *Alternative:* the app writing into `data_health.db`. Rejected: that file has one writer by design (the checker), read-only for the app; two writers across two containers is what its journal mode was chosen to avoid. Telemetry never raises, drops ids the registry doesn't know, and keeps the counts if a flush fails (all pinned by tests).
- **Not counted yet:** the other ArcGIS layers (parcels, FEMA, EPA, HUD), Walk Score, the Clerk. *Revisit if:* an outage shows up on one of those first.
- **No threshold has met real traffic.** 20% and 50% are the plan's numbers; production has no live counts yet, so the false-alarm rate is unknown.

**The fault flag, generalized.** `DATA_HEALTH_FAULT` already forced an overlay layer to fail (M7a). It now also takes `socrata:<dataset>` and `source:<registry id>` (several joined by `;`), is ignored when `environment=production`, and logs loudly at startup when set. *Evidence, run locally from live public data:* with `overlay:5` the Profile's Regulatory card says "couldn't check landmark designation", the verdict is caveated and the hero lists it, and nothing says "not a landmark"; with `source:chi.zoning.districts;source:chi.crime;source:cook.assessor.sales` the Build, Costs, Market and Area modules each show their row and the verdict names the district.

**Numbers** (2026-10-22; public data, no model)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,085 → 2,115 (+30 in `test_partial_failures.py`; 5 old tests rewritten) | `make test` |
| Frontend tests | 512 → 524 (+7 for the row and the table, +1 verdict, +4 untranslated-key guards); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Mobile overflow audit | 40 of 40 | `cd frontend && npm run test:mobile` |
| Failure-caching sites in `backend/retrieval` | 3 found, 2 real (fixed), 1 parse guard | AST scan in the decision text |
| Fault run: forced sources → modules that say so | 4 of 5 modules, plus the verdict and the hero line | `DATA_HEALTH_FAULT=...` as above |

**Not measured / not verified:**
- How often production sources fail (no live counts exist until a day after deploy), and the checker's behavior on them. After the deploy `backend/data/data_health_live.db` appears within an hour; the next daily check reads it.
- The chat footer line and the report sections are pinned by tests, not seen end to end on production (the chat route spends the key; the report needs an admin session).
- About 70 `except Exception` blocks remain in the retrieval layer. I audited the ones that *cache* a failure, not each one that swallows an error and returns empty; flood, the incentive layers (QCT, OZ, NMTC), Walk Score and the parcel lookups are the next to read.
- Spanish: the new Profile strings are English, listed in `_untranslated.json`; the report's new notice is English in `_UNTRANSLATED_ES`.

**Production** (2026-10-22, after the deploy of #96; docs PR #95 merged first)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle carries the unchecked-row wording ("didn't answer when this page loaded") | `grep` on the `assets/index-*.js` the home page names |
| Profile payload | `failed_sources` is present and empty for 1601 N Milwaukee (nothing failed); 1 sale and 1 comp still arrive; 8 `data_dates`; 57 provenance entries (the extra one is `property.comps.median_price_per_buildable_sqft`, which the live comps set now supports) | `curl "https://urbanlayerchicago.com/api/scorecard?pin=14313320180000"` |
| Report endpoint, anonymous | still 401 | `curl -i "https://urbanlayerchicago.com/api/report?address=1601+N+Milwaukee+Ave"` |

**Not verified on prod:**
- The failure paths themselves: nothing has failed in production to show them, and the fault flag is (by design) ignored there. They were exercised locally with `DATA_HEALTH_FAULT`.
- `data_health_live.db` should appear in `backend/data/` within an hour of the deploy and the next daily check should read it. To confirm, on the server: `ls -l /opt/urbanlayer/backend/data/data_health_live.db` (it lives on the `backend_data` volume; if the path differs, `docker compose ... run --rm backend ls -l backend/data`). If it is missing after two hours, the flush task did not start.
- The chat `**Couldn't check today:**` line and the report's section notices (the chat route spends the key; the report needs an admin session).

## Item 16b: landmark designations the map doesn't show yet (WS1 M5b, #98, 2026-10-22)

**"Not yet on the map" is decided by the parcel's own overlay result, not by comparing names.** Item 16 declined this because the landmark layers carry a name, an address and a designation date as text and no ordinance number, so asking the rezoning question ("does a polygon carry this record number?") would have been a fuzzy match. The design that replaced it asks nothing of the map's text. A parcel is flagged when (1) a designation ordinance passed within `LOOKBACK_DAYS` has a title that lists this parcel's address or, for a district, a block it is on, **and** (2) the parcel's own landmark-layer result (the overlay query the Profile already ran, layers 5 and 6) does not already say landmark. If the map shows the parcel as a landmark or in a landmark district there is nothing to add; if it doesn't, the ordinance is news the map hasn't caught up to. *Alternative:* match the layer's name or address text to the title. Rejected for the reason above. *Evidence (live, 2026-10-22):* with the new snapshot rows, the three parcels whose designation is not on the map yet (13100 S Ellis Ave, 2 N Riverside Plz, a Bryn Mawr Ave parcel) are flagged by PIN, and the two already on the map (4644 S Dearborn St, 1926 N Halsted St) get nothing added and keep the existing "landmark" note.

**Words that stay true.** "A designation ordinance *listing this address* passed on <date>", never that the parcel is a landmark. A district's title names blocks ("900 through 1100 blocks of W Bryn Mawr Ave"); its boundary is in the ordinance, so the words are "names the blocks of ... which include this address ... this page cannot say whether this parcel is inside it". When a landmark layer failed (item 22's `unchecked_overlays`), the words say the map could not be checked and do not claim it says no. The ordinance's `name` is shown, except the title's generic word "building".

**The title grammar** (`designation_titles.py`, reusing the rezoning parser's street, type and parity rules): `Historical landmark designation for <name> at <address>[/<address>]` (the name may itself contain " at ", so the split is the first "at" followed by a number), `located at`, and blocks: a block is a hundred (`1600-1800 blocks` = 1600-1899), a side is a parity (east of a north-south street, north of an east-west one, is even) and a side on the wrong axis is refused, not widened. Anything unaccounted for is `partial`/`unparsed` and gets no flag. 14 of the 15 real titles read clean; the other ("5830 W Midway Park", a street with no type we recognize) is listed for review, not guessed.

**The lookback, measured.** `eval/designation_backtest.py` asks the landmark layers, for each resolved parcel, whether the map shows it today, bucketed by the ordinance's age (this run: 31 sampled parcels, 0 wrong-street, gate 0):

| Ordinance age | Individual landmark parcels on the map | District parcels on the map |
|---|---|---|
| under 30 days | 0 of 1 | 1 of 12 |
| 90 to 180 days | 2 of 3 | n/a |
| 180 to 400 days | 3 of 3 | 12 of 12 |

So the map takes more than 90 days for some (the Chicago Daily News Building, passed July 15, was still off the map at 99 days) and has caught up on everything past 180. `LOOKBACK_DAYS = 180`. *Revisit if:* a later run shows an ordinance still off the map past 180 days (then the flag would drop it while it is still news).
- **A district's listed blocks are not its boundary.** The Humboldt-Sacramento extension (246 days old) has all 12 sampled parcels on the map, so there the listed blocks matched the district. For the Bryn Mawr district at 29 days, 11 of 12 sampled parcels are not on the map yet. How many parcels on a listed block turn out to be outside a district polygon is not measured here (it would need the polygon of a district the map already carries, for which only one exists in the window).

**Coverage is partial, and says so.** Of the 8 designations in the 180-day window, 5 resolve to parcels (a single building is one Address Points row); 3 have no address point for the listed number (30 N LaSalle St, 2219 N Kenmore Ave, 2324 N Chalmers St), as do some of the older ones. Those are listed in the admin card (`designation_status`), and a parcel whose PIN is unresolved is matched on its parsed address instead, like the rezoning flag. A designation on a vacant lot resolves to nothing, same as rezonings.

**Surfaces.** A coverage note (`landmark_designation_passed`, §2-120-740 and the Clerk link), a box at the head of the Regulatory card, a verdict caveat that also stops the verdict reading confident, prompt rule 39 (never "not a landmark" while the field is present), the report's regulatory section plus its landmark status row ("Designation passed, not on the map yet" in place of "No"), and an admin line. The match is a computed field on `ContextObject` (like `passed_not_on_map`), so the Profile, a cold chat turn and a handoff agree.

**Same weakness as the rezoning check, stated:** a failed designation check keeps the previous rows and records `designation_check.status = failed`, but only the admin card shows it; the sync's Sentry report still fires only for the code-amendment check. *Revisit if:* the daily checker should register the Clerk-derived checks as sources (WS6).

**Numbers** (2026-10-22; Clerk, Address Points and the City's map are public and free; no model, no production key)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,115 → 2,157 (+42, `test_designations.py`) | `make test` |
| Eval tests | 104 → 106 | `make test` |
| Frontend tests | 524 → 542 (+18: box, verdict, admin card, untranslated-key guards); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Titles read clean | 14 of 15 (93%; gate 90%) | `PYTHONPATH=. python -m eval.designation_backtest` |
| Wrong-street parcels | 0 of 31 sampled (gate 0) | same |
| Designations placed on parcels in the window | 5 of 8 | `python -m backend.legislation.sync --print` (also runs the rest of the sync) |
| Recorded titles | 15, committed (`fixtures/clerk/landmark_designations_2026-10-22.json`) | the Clerk's `HISTORICAL LANDMARKS | Designation` category |

**Not verified:**
- Production: the flag needs the daily sync to have written `designations` into the prod snapshot (06:00 Chicago the next morning, or a manual `sudo systemctl start legislation-sync.service`); until then `matches_for` returns nothing, which is the safe state. After it runs, 13100 S Ellis Ave and 1122 W Bryn Mawr Ave should show the box.
- The report's new section and landmark row are pinned by tests, not seen in a PDF.
- The prompt rule's effect on an answer (no model).
- Spanish: new strings are English, listed as untranslated.

**Production** (2026-10-22, after the deploy of #98; docs PR #97 merged first)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI, lint, test and deploy green; `/health` ok | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle carries the designation wording ("designation passed") | `grep` on the `assets/index-*.js` the home page names |
| Profile payload | 1601 N Milwaukee Ave and 13100 S Ellis Ave return no `passed_landmark_designations` and `failed_sources: []`; their overlay flags are unchanged. This is the expected state until the daily sync writes `designations` into the production snapshot | `curl "https://urbanlayerchicago.com/api/scorecard?pin=25351000060000"` |
| Report endpoint, anonymous | still 401 | `curl -i "https://urbanlayerchicago.com/api/report?address=1601+N+Milwaukee+Ave"` |

**Not verified on prod, and needs one step from Jack:** the flag itself. The production snapshot has no `designations` until the sync runs: the 06:00 Chicago timer does it tomorrow, or run it now on the server (needs sudo): `sudo systemctl start legislation-sync.service`, then `sudo journalctl -u legislation-sync.service -n 30 --no-pager` (the log has a line `landmark designations: ok passed=8 ... with_parcels=5`). Afterwards `curl "https://urbanlayerchicago.com/api/scorecard?pin=25351000060000"` should show one `passed_landmark_designations` entry (O2026-0027058, building, 13100 S Ellis Ave), and `pin=14054080110000` one district entry (O2026-0027059); `pin=14313320180000` (1601 N Milwaukee) and `pin=20044480440000` (4644 S Dearborn St, already a landmark on the map) none. The report's new notice and the prompt rule's effect were not seen on prod.

## Item 23: fact snapshots, report originals, report cover (WS6 M8, #99, 2026-10-22)

**The policy, as Jack approved it (option C):** a purchase keeps the first report it renders as its **original**, stored once, byte for byte; every later download is a live render with today's data, and its cover says "Updated copy of the report first generated on <date>". Free and unlimited for now. `GET /api/report?copy=original` returns the stored PDF; no `copy`, or `updated`, renders live.
- **The first render is the original, whichever copy was asked for.** A purchase made before this shipped has no original; its next download becomes one, and Settings labels that honestly ("Original · <the day it was first kept>", not the purchase date). *Alternative:* back-fill by re-rendering old purchases. Rejected: that would invent an "original" that is today's data under yesterday's date.
- **Only the original keeps its PDF.** An updated copy keeps its facts and data dates (a row, about 3.7 KB), not a second 2 MB file. Subscribers and admins render without a purchase: their renders are recorded with `purchase_id` NULL and no PDF (the plan's free "report history"). A mock render is never recorded.

**"Stored once" is a database rule.** `report_renders` has a partial unique index on `purchase_id WHERE kind = 'original'`, so two concurrent first downloads cannot both become the original: the loser gets `OriginalExists` and is recorded as an updated copy (`test_a_race_for_the_original_makes_the_loser_an_updated_copy`). The file is written under a temporary name and renamed after the row is in; a refused or failed insert leaves no stray file and a row never points at a missing one.

**An original we cannot prove intact is never served as one.** Each stored PDF's SHA-256 is recorded when it is written and checked on every `copy=original`; a missing or altered file answers **410 `original_unavailable`** and Settings says the original couldn't be found while still offering an updated copy. *Alternative:* serve whatever is on disk. Rejected: the point of an original is that it is what was sold. A buyer cannot fetch another user's original (404): the stored original belongs to the purchase found for *this* user.

**The fact snapshot is built on the server, from a validated context, and nothing in it comes from the client's say-so.** `data_health/facts.py` `snapshot(context, ...)` keeps what a material change is measured against: the district and its ordinance, overlays (sorted, names normalized so spacing and punctuation never count as a change), the verdict-driving flags, standards, the code vintage and the sections cited, headline records, the date each source was current, the passed ordinances that list the parcel, and what could not be checked (as keys). A saved chat message gets its snapshot when it is stored, from the parsed context; the payload's own `facts`/`facts_json` is dropped by the request model (`test_a_snapshot_the_client_sends_is_ignored_the_server_builds_its_own`). An answer about an area or the code, or a context the server can't read, gets none, and a snapshot failure never fails the save. A user can still edit their own message's context; that changes only the notes on their own conversation. M9 does the comparing; this item only keeps what to compare.

**Schema v15** (`messages.facts_json`; `report_renders`), migrated in place: a v14 database keeps its messages, gets the column, the table and the index (`test_a_v14_database_migrates_in_place_and_keeps_its_messages`, which rolls a real file back to v14 first). Both foreign keys are `ON DELETE SET NULL`.

**Account deletion removes the user's PDFs and render rows and leaves the purchase ledger**, tombstoned as before. Files are removed after the commit, best-effort, like the uploads.

**Found by the tests, fixed:**
- Two bulk-standard facts cite the same section, so a snapshot listed `17-3-0400` twice (`bulk_sections` is now de-duplicated).
- The nightly backup would have broken on newer servers. My first version mirrored the originals with `cp -an`; `cp -n` exits non-zero for a file it skipped on coreutils 9.2 and later (and on macOS), and the script runs under `set -e`, so a second night would have failed the whole backup. It uses `rsync --ignore-existing` instead (rsync is already on the server: the off-box pull is an rrsync forced command).
- Existing Tier-0 report tests had no database; they now stub the purchase lookup the endpoint makes.

**Backups.** Originals live on the `backend_data` volume (`backend/data/reports/<purchase_id>/<ms>.pdf`) and exist nowhere else, so `scripts/backup_db.sh` now mirrors them beside the nightly database copy, append-only: `rsync --ignore-existing` never overwrites a file already copied (a damaged original can't replace its good copy) and never deletes one. This closes the server side of plan question Q8. **It is a second copy on the same disk, not an off-box one:** `scripts/pull_backups.sh` (on Jack's Mac) still pulls only `urbanlayer_*.db`. Extending it is one more rsync of `./reports/` and a run to test it; I left it alone because it runs from Jack's launchd and can't be tried from here. *Revisit if:* the box is lost with reports on it.

**Numbers** (2026-10-22; public data, no model; Stripe not involved, see below)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,157 → 2,187 (+30: snapshots 12, originals 15, backup script 3) | `make test` |
| Eval scorer tests | 106 | `make test` |
| Frontend tests | 542 → 551 (+9: the Settings row 5, untranslated-key guards 4); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Real report, 1601 N Milwaukee, local | first download 12.5 s, stored as the original (2,038,871 bytes); second download 5.3 s, an updated copy (the cover names the first's date); `copy=original` returned the first byte for byte (same SHA-256) | the scratch server run in the decision text: `DB_PATH=... REPORT_STORE_DIR=... uvicorn`, then three `curl`s of `/api/report?pin=14313320180000[&copy=original]` |
| Snapshot size | 1.3 KB for a bare parcel; 2.7 KB in the real report's `report_renders` row; the data dates 0.96 KB | same run: `select length(facts_json), length(vintages_json) from report_renders` |
| Disk | the original is **2.0 MB, not the plan's 1.5 MB**: about 2 GB per 1,000 purchases | same |

**Not verified:**
- **Stripe test mode.** The plan's acceptance is a purchase through Stripe's test mode. I did not run a checkout (no webhook forwarding here, and prod's Stripe is still off): I seeded a completed purchase row for the local dev user and drove the real report route, which exercises everything after the webhook.
- Production: see the block below. The first buyer download after deploy becomes that purchase's original; the server backup script change takes effect when the deploy pulls it, and the first run to confirm is `sudo /opt/urbanlayer/scripts/backup_db.sh` (look for "Report originals mirrored").
- Spanish: the new cover line and Settings strings are English, listed as untranslated.
- The off-box copy of the originals (above).

**Production** (2026-10-22, after the deploy of #99; docs PR #100 merged first)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | the served bundle changed to `index-CDKwAX8y.js` and carries the new Settings wording; `/health` ok. GitHub's job list for the run still read "test in progress, deploy waiting" after the run itself showed `completed / success`, so the live bundle, not that list, is the evidence | `curl https://urbanlayerchicago.com/health` |
| Frontend | the bundle has "Original · {{date}}", "Updated copy" and "kept exactly as sold" | `curl -s https://urbanlayerchicago.com/assets/index-*.js \| grep -o -E "kept exactly as sold\|Updated copy"` (the bundle name comes from the home page) |
| Profile payload | 1601 N Milwaukee Ave: B3-2, ordinance 17230, code through 2026-06-17, `failed_sources: []`, 57 provenance entries, `data_dates` present, no rezoning or designation flag: unchanged | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |
| Report and purchases, anonymous | `/api/report` and `/api/me/purchases` both 401 | `curl -i` on each |
| Health block | `data_health.alarms` reads 1 on the last checker run, 8.9 hours old, so it predates this deploy. Which source it is wasn't looked up here (it needs the admin panel) | `curl https://urbanlayerchicago.com/health` |

**Not verified on prod:**
- Everything behind a login: the Settings purchase row ("Original · date" and "Updated copy"), a real second download, and `copy=original`. Item 23's local run covered those against a scratch database; prod has no purchase to download yet (Stripe is off), so the first purchase will be the first live original.
- The server backup change: `sudo /opt/urbanlayer/scripts/backup_db.sh` once a purchase exists, then look for "Report originals mirrored". The off-box pull on Jack's Mac still needs `./reports/` added.

## Item 24: the monthly routine and its nudge (WS1 M7, 2026-10-22)

**Most of M7 was already built by other items; what was missing was the checklist and a nudge for the review.** The daily sync and its timer (item 6), the registry entries `code.municipal_text` and `chi.clerk.legislation` reading WS1's callables (items 9 and 11), the CI artifact-age warning (item 18) and the monthly export reminder (item 11) all exist. So the interim `ci.yml` step the plan allowed for "if WS6's registry isn't live yet" was not needed. What this item adds: `claude-context/guides/code-refresh.md`, an alarm for an unreviewed amendment, and the removal of the module that the registry replaced.

**The review nudge is its own registry source, `internal.amendment_review`, not a finding on `code.municipal_text`.**
- **Decision:** a new source (kind `internal`, `availability_only`, no ack) whose probe reads the Clerk snapshot and `backend/code_amendments.json` through `currency.review_backlog(today)`.
- **Alternatives:** a finding in the existing `probe_code_text` (the plan's §7.3 wording: "additional registry checks").
- **Why:** `code.municipal_text` is acked until 2026-12-15 (its vintage is always over 90 days old), and `evaluate._finish` turns any warn/alarm/error on an acked source into `acked`, which never reaches Sentry. A finding added there would have been silent for 54 days, which is exactly the lapse it exists to catch. `test_the_review_alarm_is_not_swallowed_by_the_code_text_ack` pins it: the first source has an ack, the new one has none, and the same overdue amendment evaluates to `alarm`.
- **Revisit if:** the ack on `code.municipal_text` goes away (then the two could merge, but the review would still be a different question from "how old is the text").

**Thresholds: a Title 17 amendment warns after 14 days and alarms after 45; any other warns after 45 and never alarms.** The first pair is the plan's (§7.3, accepted with Q7). *I added the second:* `currency_check`, which this item deletes, warned on **any** amendment pending more than 30 days, so a Title 17-only rule would have dropped a warning that exists today. *Evidence:* the four non-Title-17 amendments awaiting review today are O2026-0026243 and SO2025-0017573 (passed July 15, 99 days), SO2026-0027165 (Sept 23, 29 days) and SO2026-0027237 (Oct 14, 8 days). The first two are over the 45-day line, so this source reads **warn on the day it deploys**. That is true (nobody has read them) and a warn emails no one; I did not review them in this item.
- **Measured from passage, not from when we first saw it.** The Clerk may list an amendment days after Council passes it, so the clock starts before the sync can see it. *Not measured:* that lag. *Revisit if:* an amendment appears already near 14 days old.
- **Not judged without a fresh Clerk check** (older than 14 days, missing or `suspect`): the list may be missing new amendments, and `chi.clerk.legislation` and `code.municipal_text` already report that. The probe says so in its info line and adds no finding.

**`currency_check.py` is deleted.** Nothing but its own test called it. Its vintage-age warning (more than 90 days) is covered by `artifacts.py --ci` (60/90 days, in `ci.yml` since item 18), and its pending-review warning by the new source. *Alternative:* keep it. Rejected: two places saying the same thing drift, and the CI one only warned in a log nobody reads.

**The guide is written from what the refreshes actually needed, not from the plan's one-time runbook.** It differs from plan §3 on purpose:
- the prod Qdrant address is found with `ssh urbanlayer-prod 'ip -4 neigh show'` (item 7), not `docker inspect`, which needs sudo that `jack` doesn't have;
- there is no `backend/tests/fixtures/code_sections/` step (item 4 dropped it: the 14 pinned sections are committed in place);
- the zoning-cache step is `--check` and a fingerprint re-stamp when the builder's five sections are unchanged, and it says **not** to run the build, which spends the production key; the plan's step cost about $0.70;
- the kit is the free Profile kit; the plan had `make kit` before and after, about $1 each;
- it records the traps found on the way: a tripped gate can be a real repeal (read the editor's notes), titles overstate (read the diff), an omnibus can be partly codified, and the export's header can lag its contents (the "March 18" export already carried a May change).

**Not built:** the plan's "a passed rezoning off the map for more than 180 days (warn)" check. `chi.zoning.passed_not_on_map` is not a registry source (its numbers live on the admin card via `map_lag_status()`), and registering it needs a probe and a decision about what red means when the City's own map is the slow party. The guide tells the reader to check it by hand. *Revisit if:* an ordinance sits off the map past the 180-day lookback unnoticed.

**Numbers** (2026-10-22; local, public data, no model, no production key)

| Measure | Before → after | Reproduce |
|---|---|---|
| Backend tests | 2,187 → 2,195 (+9 new in `test_data_health_probes.py`, −1 for the deleted module) | `make test` |
| Eval scorer tests / frontend tests | 106 / 551, unchanged (no frontend file touched) | `make test` |
| Registry sources | 81 → 82 | `python -m backend.data_health.check --dry-run` (last line of the table) |
| `internal.amendment_review` on today's data | warn: 0 Title 17 and 4 other unreviewed, oldest 99 days | same dry run |
| Same source with one scratch Title 17 amendment passed 50 days ago | alarm ("has waited 50 days for review (warn after 14, alarm after 45)"); "would alert" went 1 → 2 | `LEGISLATION_SNAPSHOT_PATH=<a copy of the snapshot with one row added> python -m backend.data_health.check --dry-run` |
| `code.municipal_text` | still `acked` (until 2026-12-15) | same dry run |
| Added / removed | `claude-context/guides/code-refresh.md` (85 lines); `currency_check.py` (50 lines) removed | `git diff --stat origin/main` |

**Not verified:**
- **Production.** The new source appears in the admin panel and `/health`'s alarm count only after the deploy and the next daily checker run (or a manual `sudo systemctl start data-health-check.service`). Expect `internal.amendment_review` at warn, naming the two July 15 amendments. I did not look at the panel in a browser (it needs an admin login); the row is a plain registry entry and the panel lists sources generically.
- **The guide was not run end to end.** A real refresh needs a newer export than the one in hand. Every command's flags were checked against `--help`, and the steps come from items 4, 6, 7, 12 and 16's runs; the first refresh that follows it is the test, and should correct it.
- `npm run build` and `npm run lint` were not run: no frontend file changed.
- The first reminder email that points at the guide is the 1st of November.

**Production** (2026-10-22, after the deploy of #102; docs PR #101 merged first)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | the CI / Deploy run on `main` finished with `test`, `lint`, `changes` and `deploy` all `success`. The run's own status still read `in_progress` more than an hour later while its four jobs were completed, so the job list, not the run status, is the evidence (the reverse of item 23's quirk) | `gh run view <id> --json status,jobs` |
| Health | `/health` ok (`qdrant`, `db`, `ptaxsim` true); `data_health.checker` ok, last run 12.4 h old (so it predates the deploy), `alarms: 1` | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle is still `index-CDKwAX8y.js`, as expected: no frontend file changed | `curl -s https://urbanlayerchicago.com/ \| grep -o 'assets/index-[A-Za-z0-9_-]*\.js'` |
| Endpoints, anonymous | `/api/admin/data-health` and `/api/report` both 401 | `curl -i` on each |
| Profile payload | 1601 N Milwaukee Ave unchanged: B3-2, ordinance 17230, code through 2026-06-17, `code_currency` fresh with `{title17: 10, cited_other: 5}` since, `failed_sources: []`, 8 `data_dates`. 56 provenance entries against item 23's 57: the missing one is `property.comps.median_price_per_buildable_sqft`, and comps are known to differ between identical runs (item 14's follow-up); this change touches neither | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |

**Not verified on prod:**
- **The new source itself.** Nothing public reads `internal.amendment_review`, so no request from outside can show the new image running; the deploy job's success is the only evidence. To confirm: run the checker (`sudo systemctl start data-health-check.service`) or wait for the next daily run, then look at `/admin` > Data health. The row should read **warn**, naming O2026-0026243 (passed 2026-07-15) with 0 Title 17 and 4 other amendments unreviewed. If the row is missing after a checker run, the old image is still running. `/health`'s `alarms` should stay at 1: a warn does not count.
- The reminder workflow's new wording (the 1st of November).
- The landmark carry-over from item 16b is still open: `GET /api/scorecard?pin=25351000060000` has no `passed_landmark_designations` because the sync has not run since that deploy (`sudo systemctl start legislation-sync.service`).

## Fix: a flood lookup FEMA doesn't answer reads as "couldn't check", not "no flood zone" (standalone, follow-up to items 11, 22 and 24, 2026-10-22)

**Not a queue item.** Item 11 named it ("`flood.py` reads a failed FEMA lookup as 'not in a flood zone'"), item 22 listed flood first among the retrieval modules whose `except Exception` swallows an error, and item 24's production check found the daily checker's only alarm was `fed.fema.nfhl` (ConnectError twice). The fix follows item 22's pattern: the lookup raises, nothing caches the failure, the orchestrator turns it into a gap, `failures.py` words it, and every surface says "couldn't check".

**Measured before touching code: this was not a rare outage, it was the normal state.** `hazards.fema.gov` answers a query in ~0.3 s but resets most *fresh* connections (`curl`: 2 of 3 reset after connect on 2026-10-22; the checker probe's own note (`probes.py`, measured 2026-10-21) has 5 of 8 fresh connections reset against 0 of 12 over one kept-alive connection). The orchestrator opens a new `httpx.AsyncClient` per Profile and hands it to the flood call, so every production lookup is a fresh connection. Running the unmodified `main` (HEAD `41b879f`) locally against the live service for 1601 N Milwaukee Ave (`pin=14313320180000`): **3 of 4 fresh lookups returned `flood_zone: null, in_special_flood_hazard: false, failed_sources: [], partial_failures: []`**, byte-identical to a parcel with no mapped zone. So production Profiles, chat answers and reports have been silently dropping the flood zone most of the time, not just during the alarm.

**A failed lookup raises `FloodLookupError`; `None` is only FEMA's own "no mapped zone" answer, and only that is cached.**
- **Alternatives:** keep returning `None` and set a side-channel flag; return a sentinel object. Rejected: every caller that tests truthiness (templates, the Profile card, `provenance_figures`) would read the sentinel as an answer, which is the trap again. An exception cannot be mistaken for a value, and the domain orchestrator already catches exceptions (`return_exceptions=True`).
- **A 200 that is not an answer is a failure too.** ArcGIS answers some errors with HTTP 200 and an `error` body, and a maintenance page is HTTP 200 HTML. The old code read both as "no features" and cached `_NOT_FOUND` for an hour. The overlays already check `error` and a missing `features` list; flood now does the same (`test_a_200_that_is_not_an_answer_raises_and_is_not_cached_as_not_found`, four bodies). A feature with no `FLD_ZONE` stays "not found" (existing behavior, pinned by an existing test); I did not find a case of it.
- **The forced fault beats the cache** (`DATA_HEALTH_FAULT=source:fed.fema.nfhl`), so a point already looked up still reproduces the failure locally.

**Retry connection resets, 4 attempts 0.3 s apart. This is a scope call beyond the brief; please veto it if you disagree.** Without it, the change turns a silent ~65% flood loss into a visible ~65% "couldn't check", the live counter (`live.py`, >50% is `alarm`) would page on a healthy service, and Profiles would carry a warning most of the time. With it, the failure rate falls to roughly 0.6⁴ to 0.67⁴ = 13% to 20% (*computed* from the two measured reset rates, not measured). Only `ConnectError`, `ReadError` and `RemoteProtocolError` are retried: they fail in tens of milliseconds, so a Profile waits well under 2 s. A timeout is not retried (a hung service would make every Profile wait 4 × 15 s) and neither is an HTTP error or a bad body.
- **Alternatives:** `AsyncHTTPTransport(retries=3)` as the checker's probe does (rejected: the client is created by the orchestrator and shared with the City overlays and the EPA call, and changing its transport would change their behavior); a module-level kept-alive client (rejected: the orchestrator passes its own, and requests minutes apart would not share a connection anyway, since httpx expires idle connections after 5 s); a longer timeout (does not help a reset).
- **Revisit if:** FEMA stops resetting (then drop the retry), or the live failure rate stays above 20% with it (then the retry count is wrong or the service is down).

**`in_special_flood_hazard` is `None` (unknown), not `False`, when the lookup failed, and a new flag `flood_unchecked` says why.** `bool | None = False`, so a healthy payload keeps `False`/`True`. *Alternatives:* reuse `unchecked_overlays` (there *is* a `fema_floodplain` entry, layer 11, the City's local floodplain map; rejected: that list's wording is "the City's zoning map didn't answer", which would blame the wrong source); put the label in `RegulatorySummary.data_gaps` (rejected: that field is the overlay gap list and the report's overlay note prints it under the City-map sentence). So `main._domain_data_gaps` adds the label from the flag. *Cost:* one new key, `flood_unchecked: false`, in every healthy Profile payload; it is the only difference below.

**One label, in the one table: "FEMA flood zone" (`failures.LABELS["flood"]`), module `record`.** The Environment card, which holds the flood zone, is in the Profile's "what to watch for" module. The frontend table (`MODULE_OF`) equals the backend's (item 22's pytest compares them).

**Surfaces**
- **Profile.** The Environment card now renders when the flood zone is unchecked and puts item 22's `UncheckedRow` in the flood slot ("FEMA flood zone didn't answer when this page loaded ... That isn't a "no"", plus a link to FEMA's Flood Map Service Center). In place, not at the module head, like the Regulatory card's overlay row; the module-level row filters `flood` out so it is not said twice. Brownfield sites still show beside it. The sidebar `RegulatoryCard` (chat) gets the same row.
- **Verdict: hedge, do not downgrade.** Flood is a friction signal only when known and not zone X, so an unknown one means the verdict cannot rule out a floodplain constraint. It now says so in its own caveat (`floodUnchecked`) and the generic "some sources unavailable" line leaves the flood label out. *Alternatives:* treat unknown as friction, so the category becomes "constrained" (rejected: it would call parcels constrained on the strength of a service that fails most connections, and item 1 hedged unchecked overlays without changing the category either); change nothing (rejected: `confidence` already flips to caveated on any partial failure, but the line it prints, "some data sources were unavailable", does not say what that rules out). The category is unchanged (`does not change the category` test).
- **Chat.** The `**Couldn't check today:**` footer gets the label from `partial_failures` with no new code. The model's context shows `in_special_flood_hazard: null` and `flood_unchecked: true`, and prompt rule 16 now forbids "not in a flood zone / not in a Special Flood Hazard Area / insurance not required" for it (pinned by a test that finds the exact label in the prompt). A **Profile handoff skips the regulatory fetch**, so the turn would not have known: `_retrieve` now adds the label when the held `regulatory.flood_unchecked` is true. It adds *our* constant, never the client's `data_gaps` text (a test sends a markdown link in `data_gaps` and checks it never reaches the line), because the footer is persisted in the answer and a shared link carries it.
- **Report.** A notice at the head of Regulatory & Environmental (item 22's macro), the Flood Zone (FEMA) line says "Not checked: ..." in place of "No flood zone data available (FEMA NFHL query returned no result)", the executive summary's Environmental row is a yellow NOT CHECKED instead of a green CLEAR "No flood/brownfield risk", and the site checklist no longer ticks "FEMA flood zone determination" as completed and lists "Check the FEMA flood zone" under action required. The cover's "Not checked in this report" line is item 21's and picks it up. A genuine empty answer keeps its old wording.
- **Spanish.** New Profile strings are English in `es` and listed in `_untranslated.json`; the report's four new keys are English in `_ES` and in `_UNTRANSLATED_ES`.

**Data health.** `fed.fema.nfhl` is counted once per call (not per attempt) in `live.py`; its registry note now names the failure path and the retry. The registry keeps `availability_only`: the checker's probe is unchanged.

**Seen and left alone (out of scope):**
- `retrieval/regulatory/environmental.py:89` returns `[]` on any EPA error and the orchestrator does the same, so an EPA outage reads as "no nearby brownfield sites": the same trap as flood, one function over. `aro_housing.py:46` and `overlays.py:184` (`query_overlay_with_geometry`, map geometry only) return empty/None on error too.
- The report's "Completed in this report" checklist still ticks the overlay, tax, comps, permits and violations checks whether or not they failed; only flood is conditional now.
- `ExportReport.tsx` (the client-side chat export) prints a flood zone only when there is one, so an unchecked zone is still silent there.
- A Profile handoff still does not carry the Profile's unchecked *overlays* into the chat footer (flood now does).

**Numbers** (2026-10-22; public data, no model, no production key)

| Measure | Before → after | Reproduce |
|---|---|---|
| Silent flood loss, unmodified `main` against live FEMA, same parcel | 3 of 4 fresh lookups returned `flood_zone: null` with `failed_sources: []` and `partial_failures: []` | run `main` and `curl "localhost:8002/api/scorecard?pin=14313320180000"` four times, restarting between runs |
| Fresh connections reset by FEMA (`curl`, 8 s apart) | 2 of 3 (the probe note in `probes.py`: 5 of 8) | `curl` the layer-28 query URL |
| Branch against live FEMA, fresh process | 2 of 2 lookups answered (`flood_zone: X`); too few to measure the retry's rate | `curl "localhost:8003/api/scorecard?pin=14313320180000"` on a fresh `uvicorn` |
| Healthy Profile payload, `main` vs branch (1601 N Milwaukee, FEMA answered in both) | the `regulatory` subtree, `provenance["regulatory.flood"]`, `failed_sources`, `partial_failures`, `data_dates`, zone class and the provenance keys are identical; the only difference is the new `flood_unchecked: false` | `python` diff of the two JSON bodies |
| Same payload, other keys | comps (n 2 vs 1, median 310,000 vs 330,000 vs 290,000), traffic street order and appeals counts differ between *branch runs themselves* (two fresh branch processes gave two different comp sets); item 14's follow-up (comps vary between identical runs), not this change | same |
| `DATA_HEALTH_FAULT=source:fed.fema.nfhl`, `/api/scorecard` | `flood_zone: null`, `in_special_flood_hazard: null`, `flood_unchecked: true`, `failed_sources: [{key: flood, labels: [FEMA flood zone]}]`, `partial_failures: [FEMA flood zone]` | start `uvicorn` with the variable set |
| Same run in the browser, desktop and 375 px | Environment card "Couldn't check today" with the FEMA link and the brownfield site below it; verdict caveat and the hero line name it; no horizontal overflow (document width 375 at 375) | open `/scorecard?pin=14313320180000` |
| Backend tests | 2,195 → 2,222 collected (2,217 passed, 5 skipped; +16 in `test_flood_unchecked.py`, +11 net in `test_regulatory_flood.py`/orchestrator) | `make test` |
| Frontend tests | 554 (derived: 565 minus the tests added) → 565 (+4 verdict, +4 Environment card, +2 sidebar card, +1 `UncheckedRow`); lint 67/67; build passes; ruff clean | `cd frontend && npm test && npm run lint && npm run build` |
| Mobile overflow audit (run with the fault backend, so the new row was on the page) | 40 of 40 | `cd frontend && npm run test:mobile` |

**Not measured / not verified:**
- **The retry's real success rate.** Two lookups is not a rate. After the deploy, `data_health_live.db` shows it: `fed.fema.nfhl` failures over attempts, in the admin panel after the next daily check. If it is above 20% the retry count or the service is the problem.
- **The chat footer line end to end and the report PDF.** Both are pinned by tests (the footer builder, the rendered report HTML), not seen on a running server: the chat route spends the production key, and the report needs an admin session. The prompt rule is a prompt: nothing but a test of its text proves a model obeys it.
- **The Spanish UI** shows the new strings in English.
- **Production.** The failure path shows on production only while FEMA is actually resetting connections, and the retry will hide most of them. The healthy path is the thing to check there: a Profile still carries `flood_zone` and the new `flood_unchecked: false`.

**Production** (2026-10-22, after the deploy of #104, merge commit `69c2276`)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI / Deploy on `69c2276`: `changes`, `lint`, `test` and `deploy` all `success` (deploy finished 18:55 UTC, about 5 minutes after the merge) | `gh run view <id> --json jobs` |
| Health | `/health` ok (`qdrant`, `db`, `ptaxsim` true); checker ok, last run 1.1 h old; `alarms: 1` (the same `fed.fema.nfhl` alarm as before) | `curl https://urbanlayerchicago.com/health` |
| Frontend | the served bundle changed from `index-CDKwAX8y.js` to `index-DegLbUlP.js` and carries `floodUnchecked` and "FEMA flood zone" | `curl -s https://urbanlayerchicago.com/ \| grep -o 'assets/index-[A-Za-z0-9_-]*\.js'` |
| Profile payload, before the deploy | 1601 N Milwaukee: `flood_zone: null`, `in_special_flood_hazard: false`, `failed_sources: []`, `partial_failures: []` (the silent failure, on production) | `curl "https://urbanlayerchicago.com/api/scorecard?pin=14313320180000"` |
| Profile payload, after the deploy (3 requests about 20 s apart) | all three: `flood_zone: null`, `in_special_flood_hazard: null`, `flood_unchecked: true`, `failed_sources: [{key: flood, labels: [FEMA flood zone]}]`, `partial_failures: [FEMA flood zone]`. The rest of the flood subtree, `data_dates`, zone class and provenance keys are identical to before | same |
| The live page, headless, desktop and 375 px (three loads) | the Environment card says "Couldn't check today ... FEMA flood zone didn't answer ... That isn't a "no"" with the FEMA flood map link; the verdict carries its own caveat; the hero line reads "Some data unavailable: FEMA flood zone"; the page never says "not in a flood zone"; document width equals viewport width at 1280 and 375 | Playwright against the live URL |
| Anonymous `/api/report` | still 401 | `curl -i` |

**What production showed that the local runs did not:** from the production server FEMA failed **every** lookup I made after the deploy (3 API requests and 3 page loads, so 6 of 6, each after the 4 attempts), where from a dev machine about a third of fresh connections get through. So the retry rescued none of them here, and the 13% to 20% residual-failure estimate above (computed from the dev-machine reset rate) does not describe production today. Until FEMA, or whatever drops the server's connections, recovers, every Profile says it couldn't check the flood zone. That is the honest behavior, and it is what the daily alarm (`fed.fema.nfhl`, ConnectError twice in a row) was already reporting. Why production fails more than a dev machine is **not established**: a block or throttle on the server's address range, FEMA failing from some networks, and plain bad luck over a small sample all fit, and I did not test any of them.

**Not verified on production:**
- **The healthy path.** No production lookup got an answer, so I did not see a live Profile with a flood zone and `flood_unchecked: false`. That path was checked locally (payload identical to `main` apart from the new key) and by tests.
- **The live failure counts.** `data_health_live.db` flushes hourly (first flush about an hour after the container restarted, 19:55 UTC) and the checker reads it on its next daily run. With a failure rate near 100% the registry's live-rate rule (over 50% of at least 10 calls) should turn `fed.fema.nfhl` to alarm then; I have not seen it.
- **The chat footer line and the report PDF** (unchanged from the local result: the chat route spends the production key, the report needs an admin session).
- **The retry's real success rate** on production: it has no data except the six failures above.

## Item 25: "since then" for conversations, shared links and purchases (WS6 M9, 2026-10-22)

**What it does.** A reopened conversation, a shared link and a Settings purchase each compare what an answer or report said (the fact snapshot item 23 stores) with today's facts, and say what is *material*: `backend/data_health/diff.py` (`compare` is pure; `changes_for` fetches and caches), `corrections.json`, schema v16 `fact_checks`, `GET /api/conversations/{id}/changes` (owner), `GET /api/share/{token}/changes` (public), `changes` on `/api/me/purchases`, and `AnsweredOnNote` under each assistant bubble (Settings: an amber line on `PurchaseRow`). Zero model calls.

**Today's facts come from the Profile's own lookups.** `current_facts` calls `lookup_zoning` and `regulatory_domain` at the snapshot's point (sharing their one-hour caches), builds a `ContextObject` and runs the same `facts.snapshot`, so both sides of a comparison are made by one function. *Alternative:* a second, lighter "current" reader (overlays only). Rejected: two readers drift, and the name normalization that stops "ADU  Area" reading as a change lives in one place. *Revisit if* the cold lookup (about 15 ArcGIS requests plus FEMA, which timed out locally) makes the first note slow: it loads after the conversation renders, so the cost is a late note, not a slow page.

**Never "no change" for something we could not read.** A zoning lookup that fails makes no district claim; an overlay layer in `unchecked_overlays` today (or when the answer was made) is skipped both ways, so a layer the map failed to answer is never "removed" and one the old answer could not check is never "added". The result says `partial` ("no change in what we could read, couldn't re-check the district") or `unavailable`, never `none` (`test_a_failed_lookup_is_never_no_change`, `test_an_overlay_the_map_could_not_answer_makes_no_claim_either_way`). A check that could not read everything is **not cached**.

**Old answers are rebuilt on read, and marked.** A message with no `facts_json`, or a stored snapshot from before this item (it kept no lat/lon), takes its point from `plan_json` and, if it has none, is rebuilt from `context_json` (`reconstruct`, `reconstructed: true`). **Found while testing:** `ContextObject.code_vintage` is computed from today's files, so a rebuilt snapshot claimed the *current* code text. `reconstruct` therefore sets the vintage to the text before the first recorded refresh whenever the answer predates that refresh's `applied_at`; an answer with no date is not rebuilt. `_facts_json` now also stores the point so new snapshots need no rebuilding.

**What is compared** (plan §4.4): the district (normalized, with ordinance and Clerk link); overlays that carry a rule (13 layer types; special service areas are not one); a bulk standard of the *same* district; a Title 17 or cited-other amendment touching a section the answer cited, split into "after the answer" and "before the answer but not in its text"; a passed rezoning or landmark designation listing the parcel that the snapshot did not carry; a code text refresh that changed a cited section (`code_changes.json`); a recorded correction. Never crime, 311, permits, comps or Divvy.

**Corrections log.** Three entries, each checked against git: the landmark survey layer (`a621ea1`, 2026-10-02: predicate `flags.is_landmark_building`), and the 2026-07-06 zoning table heights (`04d2234`: RM-4.5/5.5/6/6.5, and the M districts by prefix). **Two candidates in the plan were left out because the snapshot cannot express them:** the commercial tax rate fix (no building class is stored) and the nearest-parcel identity fix (no resolution flag is stored). Adding either means putting that field in the snapshot first. *Alternative:* flag every report with an estimated tax made before 2026-07-06. Rejected: most of those figures were right, and a banner that is usually wrong teaches people to ignore it.

**Caps and cost.** At most 3 distinct parcels per conversation (newest answer first; the rest say only their date); today's facts kept per (parcel, UTC day) in `fact_checks`, a week of rows; answers under 24 hours old skip the check; the share endpoint adds a per-IP limit (20 a minute) and a 10-minute per-token cache on top, and is 404 once the share is revoked.

**Left out, on purpose.**
- **"Newer data available"** (a new tax year, assessment year or ACS release, plan §4.4's one quiet line): the current-facts side does not read property or ACS facts, and building that reader is a larger job than this item. The snapshot already stores the years, so it can follow.
- **Standards compared from the unit yield**, and **flood**: the snapshot does not keep flood, and unit yield depends on the property record.
- **The "Ask again" button re-sends the previous user message** as a normal chat turn (owner only). It does not carry a parcel pin, so a question that never named the address may route differently than when first asked.

**Numbers** (2026-10-22; public data, no model, no production key)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | 2,258 passed, 66 deselected (+36: `test_since_then.py` 35, one v15 to v16 migration test) | `make test` |
| Frontend tests | 617 passed (+10: `AnsweredOnNote` 8, `PurchaseRow` 2); lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Real lookups, scratch database (`DB_PATH`, `REPORT_STORE_DIR` in the scratchpad), a seeded 4-message conversation at 1601 N Milwaukee | 2 parcel answers got notes (one stored snapshot, one rebuilt); the district, overlays, a 2026-05-20 amendment touching 17-3-0207 and the landmark correction all showed; second call 11 ms from `fact_checks` (one row, 1.5 KB) | seed script, then `curl localhost:8001/api/conversations/scratch1/changes` |
| Browser, owner and shared view | both views show "Answered ..." then the amber callout with the ordinance link and "Open today's Property Profile"; the shared view has no "Ask again" | open `/c/scratch1` and `/s/<token>` on the dev server |

**Not verified:**
- **Production.** Nothing has run there yet; the check below needs a real conversation with a parcel answer.
- **The Settings row in a browser.** Its logic is covered by `PurchaseRow` and endpoint tests (a seeded purchase with an original), but the page was not opened with a purchase.
- **Mobile layout.** `npm run test:mobile` was not run; the note is inside the existing bubble footer, no new layout.
- **The seeded examples were hand-built.** They show the plumbing and wording on real map data, not the false-positive rate on real conversations. Their overlay "changes" came from the seeded snapshot having none.
- **Spanish.** The new strings are English, listed in `_untranslated.json`.
- **The transcript PDF export** carries "Answered <date>" under each answer by code and type check only.
- **Wording on a date near midnight.** The note shows the viewer's local date while `answered_on` is UTC; they can differ by a day.

**Production** (2026-10-22, after the deploy of #106, merge commit `a210ddd`)

| Check | Result | Reproduce |
|---|---|---|
| Deploy | CI / Deploy on `a210ddd`: `changes`, `lint`, `test` and `deploy` all `success`; CodeQL success | `gh run view <id> --json jobs` |
| Health | `/health` ok (`qdrant`, `db`, `ptaxsim` true); checker ok, last run 1.8 h old; `alarms: 1` (the known `fed.fema.nfhl`) | `curl https://urbanlayerchicago.com/health` |
| Frontend | served bundle `index-BOqqsknk.js` carries "rechecked today: no material change", "Ask again with today's data" and "Facts changed since your report" | `curl -s https://urbanlayerchicago.com/assets/index-*.js \| grep -o -E "rechecked today: no material change"` (name from the home page) |
| New routes exist (so the new image runs) | anonymous `/api/share/nope/changes` answers 404 `Shared conversation not found` (not the router's "Not Found"); `/api/conversations/x/changes` and `/api/me/purchases` answer 401 | `curl -i` on each |
| Profile payload | 1601 N Milwaukee: B3-2, ordinance 17230, code through 2026-06-17, `data_dates` present; `failed_sources` is the FEMA flood row, as since #104; 56 provenance entries (flood unchecked) | `curl "https://urbanlayerchicago.com/api/scorecard?address=1601+N+Milwaukee+Ave"` |

**Not verified on production:**
- **A real "since then" note.** It needs a signed-in conversation (or a share link) with a parcel answer; the chat route that makes one spends the production key, so I did not make one. The first look is yours: reopen an old parcel conversation and a share link of it.
- **The schema v16 migration on the production database** (no login to read it): it is covered by the v14 and v15 migration tests, and `/health` reports `db: true` after the restart.
- **The Settings purchase line** (no purchase exists on production; Stripe is off).
- **The cold-lookup time on the server.** FEMA fails there (see item 24 and the flood fix), but flood is not part of the comparison, so a note should not wait on it; not timed.

## Item 26 (WS1 M6): the new district, read from the ordinance by AI

**Decision: build the reader, ship it dormant.** Item 16 says a rezoning listing this address passed but is not on the map; M6 adds what it changes the parcel to. `backend/legislation/ordinance_reader.py` fetches the Legislation PDF that passed (the SO Final for a substitute, never the EDS), sends it to the model as a document block, and gets `[{map_no, from_district, to_district}]`. The daily sync (`sync._reader_part`) runs it for off-map rows that have parcels only when `ordinance_reader_enabled` is true and a key exists; both are off, so merging spends nothing. Its first live run is a production event (WS1 Q5; needs the production credits, open Q8).

**The one check that makes a reading showable.** `from_district` must equal the zone class the live map shows (`zoning.lookup_zoning`) at one of up to 3 of the ordinance's parcels; otherwise the row is `unvalidated` and the Profile keeps the link only. Alternatives: trusting the model's JSON (no way to catch a misread district); validating the *to* district against the zoning table (it exists for any real class, so it catches nothing). Revisit if: parcels in one ordinance sit in different districts (a multi-change ordinance); then the check passes if any parcel matches and `district_for` narrows by the viewing parcel's own district, and says nothing when still ambiguous.

**Failures are not "no district".** A PDF that won't fetch, a model error or an unparseable reply is stored as `failed` and retried the next run; a stored raw reading is re-validated against today's map without a new call, so a reading costs one model call per ordinance, not one per day. Reader version bumps re-read.

**What shows.** Profile zoning card line, a `passed_district` coverage note (which chat restates under prompt rule 36), and a report line, each reading "The ordinance changes it from C2-2 to B2-5 (read by AI from the scanned ordinance; check the PDF)". Only for a validated reading; `RT-4 to RT-4` (an ordinance that changes nothing) shows nothing. `matches_for` also carries `agreement {n, agree}` from the running agreement log (each off-map ordinance with a validated reading that reaches the map is compared with the map's district once).

**Left out:** a `ProvenanceEntry` for the AI-read district (the label is in the sentence; a new fact id touches the registry-completeness tests, and the figure is not a Profile number); the one-click "show standards for B2-5" (WS1 Q2 chose the banner); a fixture for 6711 S Western Ave (O2026-0028350, off the map) since the reader is exercised with fakes.

**Backtest.** 30 ordinances already on the map, random from the last 365 days (seed 26; 272 of 352 passed were on the map), their PDFs fetched from the Clerk at 1 request/s. Truth = the zone class of the map polygon whose `CLERK_DOCNO` is that ordinance, at up to 5 of its parcels. **I read the 30 PDFs myself in this conversation** (no production key) and committed the districts as written in `backend/tests/fixtures/ordinances/readings_on_map.json`. Result: **30 of 30 name the map's district** (one ordinance, O2026-0027136, has two blocks, RS3 to RT4 and RS3 to RS3; the map showed RT-4). It also found a real defect: ordinances write `RT4`, `RM 4.5`, `RM- 4.5`, `Rt-4` (8 of 30 needed normalizing), which the first normalizer rejected; fixed and tested, and the prompt now asks for the hyphenated form.

**Numbers** (2026-10-22)

| Measure | Result | Reproduce |
|---|---|---|
| Backend tests | `test_ordinance_reader.py` 15 tests (reply parsing, validation, reuse, failure not cached, multi-change narrowing, agreement log, `matches_for`, dormant sync, the 30-ordinance backtest fixture) | `make test` |
| Frontend | zoning-card test for the labeled district; lint 67/67; build passes | `cd frontend && npm test && npm run lint && npm run build` |
| Backtest | 30/30 agree with the map (gate 95%) | `python -m pytest backend/tests/test_ordinance_reader.py -k recorded` |

**Not verified:**
- **The production model.** The 30/30 is *my* reading of the PDFs, so it measures that the PDFs are readable and the validator and normalizer handle their spellings, not the production model's accuracy. The agreement log measures that, once the reader is switched on.
- **Harder PDFs.** All 30 are one-page typed ordinances. Multi-page, scanned or handwritten ones (a planned-development amendment, a map attachment) were not sampled.
- **The live sync path** (PDF fetch + model call + map lookup together): each piece has a fake in tests; the real run is the first production run.
- **The page with a validated district**: the card line is vitest-covered, but no snapshot with a reading exists to load in a browser. `npm run test:mobile` was not run (one extra line inside the existing box).
- **Spanish.** The new strings are English, listed in `_untranslated.json` and `_UNTRANSLATED_ES`.
