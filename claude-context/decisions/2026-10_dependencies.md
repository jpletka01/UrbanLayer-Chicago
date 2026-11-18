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

## Item 2: one tested compatibility batch; Python stays on 3.11 (2026-11-18)

**Decision:** take the raised Python floors (`uvicorn` 0.54, `pydantic-settings` 2.16.2, `sentence-transformers` 6.2) and the two frontend majors (`motion` 14, `@sentry/react` 11) in one PR, reapplied onto `main` by hand from the stale tested batch #191 (cut 2026-11-06, before the MapLibre switch, so its `package.json` and lockfile no longer applied). Close the superseded Dependabot PRs #169–#173 and #191. Close #168 (Python 3.15) and #37 (TypeScript 7) and teach `dependabot.yml` to stop proposing them.

**Why:** CI installs `requirements-dev.txt` fresh, so it already resolves the newest versions under the old loose floors; raising the floors makes that tested set the minimum a fresh build can get. The app calls only `Sentry.init` + `browserTracingIntegration`, unchanged under Sentry 11. #170's only failure was the Discovery vitest race, not sentence-transformers. #168 changes only the `FROM` lines and leaves the Dockerfile copying `/usr/local/lib/python3.11`, so its image cannot build; and to Dependabot 3.11 → 3.15 is a *minor*, which is why the existing "ignore majors" rule let it through. #37 cannot install: `typescript-eslint` (latest 8.73.0) declares `typescript >=4.8.4 <6.1.0`, so `npm ci` fails ERESOLVE.

**Alternatives:** rebase #191 as is; rejected, it would revert MapLibre to mapbox-gl/deck.gl and drop `PyJWT[crypto]` (Apple/Microsoft ID tokens, Item 121). Merge the Dependabot PRs one by one; rejected, lockfile conflicts and several deploys for one change. Python 3.15 now; rejected, a runtime migration needs its own plan and image check. TypeScript 7 with `--legacy-peer-deps`; rejected, lint would run against an unsupported parser.

**Revisit if:** `typescript-eslint` accepts TypeScript 7 (then remove the `typescript` ignore); a Python migration is scheduled (remove the minor ignore); Sentry events stop arriving after deploy.

**Not verified locally:** the new Python floors (the shared `.venv` is older: uvicorn 0.48, pydantic-settings 2.14, sentence-transformers 5.5); CI's fresh install is the test. No production Docker image built locally.

## Item 3: the 2026-11-18 Dependabot batch as one PR; i18next 27 and @types/node 26 ignored (2026-11-18)

**Decision:** take #256 (pytest floor 9.2), #257 (Pillow floor 13), #258 (python-multipart floor 0.0.33) and #259 (the frontend group: lucide-react 1.73, maplibre-gl 6.18, postcss, Playwright 1.65, @vitejs/plugin-react 6.3, eslint 10.15, eslint-plugin-react-refresh, globals, typescript-eslint 8.72.2, Vite 8.3.8, vitest 5.1) in one PR and close them. Close #260 (`@types/node` 26) and #261 (i18next 27) and add Dependabot ignores for the majors of `@types/node`, `i18next` and `react-i18next`.

**Why:** the four PRs touch different files but would mean four deploys; one tested change is one deploy (Item 1). Pillow is used only for `Image.open`, `thumbnail(…, Image.LANCZOS)` and JPEG `save` (`vision.py`, `report_builder.py`'s map composites), all unchanged in 13; the D3 report-map tests exercise them. `@types/node` should describe the Node that runs the code: CI and the image use `frontend/.nvmrc` = 24, so its 26 types would allow APIs that aren't there. i18next 27 cannot go alone: react-i18next 18 is the first release that accepts it (peer `i18next >= 27.0.1`), and with both installed `tsc -b` reports 39 errors in 14 files, all the same kind: the new `TFunction<ns>` is a rest-tuple union that no longer fits the plain `(key: string, opts?) => string` helpers the app passes `t` into (`scorecardVerdict.TFunc`, `useChat`, `savedModel`, `ExportReport`, …). No looser helper signature accepted it (`Record<string, unknown>`, `Record<string, any>`, `TOptions` all fail). The fix is a typed-`t` refactor across the helpers plus a react-i18next major, for no change a visitor sees.

**Alternatives:** cast `t` at each of the 39 call sites; rejected, it hides the mismatch rather than fixing it. A `useLooseT` wrapper hook in the 14 files; possible, but it pairs with the react-i18next 18 runtime major and belongs in its own tested change. Merge the four safe PRs one by one; rejected, four deploys.

**Revisit if:** a security advisory lands for i18next 26 or react-i18next 17; i18n work is planned anyway (then do the typed-`t` migration and drop both ignores); CI moves to Node 26 (drop the `@types/node` ignore).

**Numbers**
- **Gates on this branch:** backend `pytest -m "not integration"` 3,330 passed, 5 skipped, run with Pillow 13.0.0, pytest 9.2.0 and python-multipart 0.0.34 on top of the shared `.venv`; frontend `npm run build` ok, `npm run lint` 0 errors / 45 warnings (cap 65), vitest 87 files / 798 tests passed.
- **Not measured:** MapLibre 6.18 in a real browser (vitest and the build only; the post-deploy `sweep:live` is the check); a production Docker image built locally.
- **Reproduce the i18next failure:** `cd frontend && npm install i18next@^27.2.1 react-i18next@^18.0.2 && npx tsc -b`.
