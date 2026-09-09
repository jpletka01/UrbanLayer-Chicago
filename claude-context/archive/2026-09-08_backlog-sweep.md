# Backlog sweep, Qdrant exposure fix, review-tooling switch (2026-09-07/09) — SHIPPED (`main` 9233646..fe948df)

A sweep through the standing backlog: nine commits, all live. Three findings mattered more
than the features.

**🔒 Production Qdrant was publicly exposed with no authentication** (`77939a0`). Found while
planning the Title-14 push: `docker-compose.yml` published `"6333:6333"`, which binds 0.0.0.0,
and Qdrant ships with no auth — the vector store was readable **and writable** from the internet
(`curl http://178.105.184.66:6333/collections` answered from a laptop, no credentials). Fixed by
removing host publishing from the base file (the backend uses the compose network) and
republishing on `127.0.0.1` only in the dev override, which prod never loads. **The obvious fix
is wrong**: adding a loopback mapping to `docker-compose.prod.yml` would have *appended* under
Compose merge semantics, leaving the public binding alive while appearing closed.

**Title 14 — the entire Chicago building code — was missing from the corpus, and the docs blamed
the wrong thing.** `known-issues` said the parse regex needed a re-ingest with a fresh HTML
download. Both wrong: the committed HTML already held Title 14, and `SECTION_RE` already matched
it. A *second, narrower* write-gate in `parse_chicago_code.main()` (`\d+-\d+-\d+`) then rejected
every section it had just parsed. Both now derive from one `_SECTION_ID`. Title 14 is **eleven
lettered volumes** (14A/14B/14C/14E/14F/14G/14M/14N/14P/14R/14X), and 14N (Energy Transformation
Code) letters its chapter/section segments too (`14N-C4-C402`). Aligning `SECTION_RE` also
recovered 50 missing headings. Corpus 8,615→9,487 sections / 14,535→16,576 chunks, purely
additive. Pushed to prod 2026-09-08 (see `guides/deployment.md` for the runbook that did not
previously exist).

**CI was not running the frontend tests at all** (`9233646`). 171 vitest tests existed and no
workflow invoked them. Also wired `source_check.save_hash` (defined, never called, so the
staleness check could only ever report "unknown") and gated `deploy` on non-docs changes —
proven live when a docs-only push produced `deploy: skipped`, closing the 2026-06-30 "every push
causes a Cloudflare 521" item.

**Features:** Discovery dual-thumb `RangeSlider` + `rangeFormat.ts` (finally consumes the
`RangeDisplay` metadata that had sat unread since PR2); Divvy proximity; Cook County Assessor
permit record (the `assessable` flag = a tax increase already attached to the parcel); and
FAR-normalized comps — `price / (land_sqft × FAR)`, the density-normalized land basis the
2026-08-17 market analysis ranked as gap #3. The README, still describing the Phase-I chat app
with the wrong embedding model and a nonexistent module, was rewritten.

## 2026-09-09 — PR review moved to GitHub-native tooling

The Claude review action (`code-review.yml`) was removed. It had never run: `ANTHROPIC_API_KEY`
was never configured, so it failed at env validation on every PR from 2026-06-05 to 2026-09-08 —
three months of a permanently-red check that reviewed nothing. Replaced with what is free on a
public repo: **CodeQL** (`codeql.yml`, python + javascript-typescript, `security-extended`, PRs +
weekly), **secret scanning + push protection**, **Dependabot alerts + security updates**, and
grouped monthly `dependabot.yml` version updates. All four were previously OFF.

**Scope changed and that matters:** CodeQL finds security issues, not correctness or pattern
adherence. There is now **no general automated reviewer** — GitHub's equivalent is Copilot code
review, which needs a paid plan.

First run: 3 high / 27 medium, plus 4 workflow alerts. The workflow ones were the valuable
finding — `appleboy/ssh-action@v1` was a MUTABLE TAG on the step that receives `SERVER_SSH_KEY`,
now pinned to a commit SHA, and every job now declares least-privilege `permissions`. Log
injection was fixed centrally with `backend/log_safety.py` rather than at 23 call sites. `main`
also got force-push/deletion protection (no required checks — direct push is the workflow here).

**Dependency triage (12 Dependabot PRs).** Nine batched into ONE commit rather than merged
individually, because every merge to `main` is a deploy — ten merges would have meant ten
container rebuilds. npm vulnerabilities went **14 → 2**. Rejected: python 3.11→3.14 (CI never
builds the Dockerfile, so its green check proved nothing) and qdrant-client ≥1.19.0 (widens a
documented gap; move the SERVER instead). Parked: vitest 4.1.11 (PR #20) — clears the last two
advisories and CI's Node 20 supports it, but the dev box runs EOL Node 23.9 which npm refuses.

## Reusable lessons

- **Verify a dataset before building on it.** The tax-sale sets behind data-expansion item 6 are
  frozen at tax year **2014/2015** — a decade-old delinquency is not current distress. The
  data-expansion doc had also gone stale as a "live backlog": 13 of 16 items were already
  implemented, and I began rebuilding two of them before finding them in `parcel_flags.py`.
- **And verify before "fixing" working code.** `parcel_flags` selects `application_url` from a
  dataset whose sample row lacks it; the column exists and is merely sparse (1,550 live rows).
  A sample-row field list is not a schema.
- **`embed_and_store` assigns `uuid.uuid4()` per point**, so re-inserting DUPLICATES rather than
  replaces. Faking existing sections as `diff.added` to force a re-embed created 116 duplicate
  points locally; recovery is `--full`. Any targeted corpus write must delete-by-section first,
  and verification must compare **per-section** counts, not just the total.
- **The manifest content-hash omits `section_title`**, so heading-only fixes are silent no-ops.
  Adding it was tried and reverted — it invalidates every hash, forcing a full re-embed and
  falsely tripping the zoning-cache staleness check, which would need `RERANKER_ENABLED=true`.
  Documented in `core/known-issues.md` instead.
- **`estimate_tax` leaves an aiosqlite worker thread alive**, so orchestrator tests PASS and then
  hang at interpreter shutdown — indistinguishable from a hung test. Stub it.
- **Don't annotate a cached object.** `nearby_comparable_sales` returns a cached dict; mutating it
  leaked annotations into the cache, so the next request skipped the land-area fill and reported
  null provenance for a geometry-derived value.
- **The property fan-out is a positional `coros` list with a hand-tracked `idx`**; `parcel_flags`
  was missing its `idx += 1` — harmless as the last entry, load-bearing once anything follows.
- **A green CI check is not evidence the change is safe** — it is evidence of what CI actually
  ran. The python 3.11→3.14 PR passed because the `test` job uses `setup-python` at 3.11 and never
  builds the Dockerfile. The vitest 5 PR passed because npm only *warns* on an engine mismatch.
  Both would have broken something CI never exercised.
- **Version bumps of test tooling are really Node-floor bumps.** Each vitest major raises the
  required Node range; pick the newest release every environment (CI, the Docker image, the dev
  box) can actually run, not the newest that exists.
- **Compose merges list entries by APPENDING.** Adding a "safer" `ports` mapping in an override
  leaves the original binding alive — the hole stays open while looking closed. Remove it at the
  source instead.

## Files changed

`ingestion/parse_chicago_code.py`, `ingestion/update.py`, `.github/workflows/ci.yml`,
`docker-compose.yml`, `docker-compose.override.yml`, `README.md`,
`backend/retrieval/neighborhood/divvy.py`, `backend/retrieval/property/assessor_permits.py`,
`backend/retrieval/property/comps_far.py`, `backend/models.py`, `backend/main.py`,
`backend/retrieval/property/__init__.py`, `backend/retrieval/neighborhood/__init__.py`,
`frontend/src/discovery/{RangeSlider,rangeFormat}.tsx|ts`, `frontend/src/components/ScorecardPage.tsx`,
`frontend/src/components/scorecard/{ScorecardPropertyCard,ScorecardComparablesCard}.tsx`,
`frontend/src/lib/types.ts`, `frontend/src/locales/{en,es}/{data,pages}.json`,
plus tests: `test_source_check.py`, `test_section_id_gate.py`, `test_divvy.py`,
`test_assessor_permits.py`, `test_comps_far.py`, `RangeSlider.test.tsx`, `rangeFormat.test.ts`.
