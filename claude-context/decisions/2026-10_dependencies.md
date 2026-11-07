# Dependencies

Format: see `README.md` in this folder.

---

## Item 1: one tested in-range npm update instead of eight Dependabot PRs (2026-10-30)

**Decision:** the frontend takes every update that its existing version ranges already allow, as one change: `npm update` under Node 24 and npm 11 (the versions CI uses), then the full gate. That is 23 `package.json` ranges (React 19.3, Vite 8.3, vitest 4.1.12, mapbox-gl 3.34, deck.gl 9.4 with luma.gl 9.4, Sentry 10.78, i18next, react-router, eslint 10.13 and the type packages) plus lockfile-only bumps (dompurify 3.4.17, postcss-selector-parser 6.1.5, source-map-js 1.2.2, brace-expansion 5.0.12). No major version changes.

- **Why one change.** The Dependabot PRs for the frontend (#36, #56, #57, #70, #74, #75, #88, #138) all rewrite the same lockfile, so each one conflicts with the others and has to be rebased and re-tested alone; none had run against `main` for 2 to 4 weeks. One tested change supersedes them. *Alternative:* merge them one by one with `@dependabot rebase`; rejected as eight rebases, eight deploys and eight chances to break the map for no extra safety.
- **Why Node 24 / npm 11.** On this Mac (Node 23, npm 10.9.2) `npm update` and any install of the Vite family crash inside npm ("Cannot read properties of null (reading 'edgesOut')"); the same commands succeed under Node 24 / npm 11, which is what CI runs. The lockfile is therefore written by npm 11.
- **Left out on purpose (major versions):** TypeScript 7 (#37 failed CI), vitest 5 (#38), Tailwind 4, Sentry 11, Motion 14, `@types/node` 26. Each needs its own change.

**Why it is safe enough to ship (evidence).** `npm ci` from a clean directory, `tsc --noEmit`, `npm run test` (76 files, 987 tests), `npm run lint` (0 errors, the same 66 warnings), `npm run build`, and `npm audit` (0 vulnerabilities) all pass. Because deck.gl, mapbox-gl and React moved, the Discovery browser specs (`discovery-phone`, `discovery-responsive`, `discovery-map-m2`, five emulated phones plus desktop) ran against a local dev stack on this branch with the pruned index: 30 passed, 0 failed, 20 skipped.

**Revisit if:** a user-visible regression shows up in the map after deploy (roll back this one commit), or Dependabot's grouping is configured so frontend patch/minor bumps arrive as a single group PR.

**Numbers**
- **Before:** 30 outdated packages, 8 open frontend Dependabot PRs, `npm audit` reported the transitive issues those PRs address.
- **After:** `npm audit` 0 vulnerabilities; 8 PRs superseded once this merges.
- **Not measured:** the live site (map rendering on real devices, bundle size change); the major-version items above; a Spanish or light-theme pass of the map.
- **Reproduce:** `cd frontend && npx -p node@24 -p npm@11 -- sh -c 'npm ci && npx tsc --noEmit && npm test && npm run lint && npm run build && npm audit'`

## Item 2: one tested compatibility batch; Python stays on 3.11 (2026-11-06)

**Decision:** take the three raised Python dependency floors (`uvicorn` 0.54, `pydantic-settings` 2.16, and `sentence-transformers` 6.2) together with the two frontend major updates (`motion` 14.9 and `@sentry/react` 11.11). Keep the production Docker image on Python 3.11. The six Dependabot PRs are not merged independently: their branches are stale, the two frontend PRs both rewrite the lockfile, and all three failed checks were the same Discovery test race fixed on `main` by `0cdd832`.

**Why:** CI had already resolved the newer Python packages under the old loose lower bounds, but this batch makes that tested baseline explicit. The project uses only `Sentry.init` plus `browserTracingIntegration`, which type-checks and tests unchanged under Sentry 11; Motion 14 likewise passes the full frontend gate. Python 3.15 is a runtime migration, not routine dependency maintenance. Its PR changes only the two `FROM` lines and leaves the Dockerfile copying `/usr/local/lib/python3.11`, so it would fail an image build even before Python-3.15 compatibility was assessed. The Dependabot policy already ignores Python majors; close that pre-existing PR rather than widen its scope.

**Alternatives:** merge the five safe Dependabot PRs one at a time; rejected because it produces lockfile conflicts, repeated CI, and multiple deploy opportunities for one coordinated compatibility change. Upgrade to Python 3.15 now; rejected because it needs a dedicated runtime-migration plan, corrected Dockerfile paths, and image verification. Leave the old minimums; rejected because a fresh build could resolve a materially older dependency set than the one CI just tested.

**Revisit if:** the production Docker build fails under the pinned Python 3.11 base, the frontend receives a Sentry event regression, or a Python 3.15 migration is explicitly scheduled.

**Numbers**

| Measure | Before | After |
|---|---:|---:|
| Frontend direct dependencies | Motion 12.43; Sentry React 10.78 | Motion 14.9.1; Sentry React 11.11.0 |
| Python floors | uvicorn 0.30; pydantic-settings 2.5; sentence-transformers 3.2 | uvicorn 0.54; pydantic-settings 2.16; sentence-transformers 6.2 |
| Backend unit tests | n/a | 2,742 passed, 66 deselected |
| Evaluator tests | n/a | 188 passed |
| Frontend tests | n/a | 952 passed |
| Frontend lint warnings | 66 allowed | 66 (cap 67) |

**Reproduce:** `PYTHONPATH=. /tmp/urbanlayer-deps-nov/bin/python -m pytest backend/tests -q -m 'not integration'`; `PYTHONPATH=. /tmp/urbanlayer-deps-nov/bin/python -m pytest eval/test_judge.py eval/tests -q`; `cd frontend && npx -p node@24 -p npm@11 -- sh -c 'npm run build && npm run test && npm run lint'`.

**Not verified:** the production-backend Docker image; the local Docker daemon was unavailable. No live deployment or production Sentry-event check was run.
