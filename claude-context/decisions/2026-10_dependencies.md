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
