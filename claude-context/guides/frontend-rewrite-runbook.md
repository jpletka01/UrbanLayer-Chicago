# Front-end rewrite: runbook

How the rewrite is run, phase by phase, and where to pick it up. **Start here** when resuming rewrite work.

| Read | For |
|---|---|
| `guides/frontend-redesign-vision.md` | What we are building and why (the brief: audience, page rules, frame, every page) |
| `decisions/2026-11_frontend-rewrite.md` | What has been decided and why: Item 73 (SnowUI base), Item 74 (visual system), Item 75 (how it is built), later items per phase |
| This file | Where we are, what each phase delivers, and the end-of-milestone checklist |
| `plans/2026-11-07_frontend-implementation-plan.md` (local, not in the repo) | The full approved plan, revision 3 |
| The latest `plans/*_frontend-phase-*-prompt.md` (local) | The prompt that starts the next phase in a fresh conversation or session |

Until a route flips, `guides/page-design.md` and the Bento Pro guides govern the live site; the new UI lives behind `?ui=next`.

## Status

| Phase | What it delivers | Status |
|---|---|---|
| 0 | Baseline: Items 73–75 on `main`, success criteria | **Done** 2026-11-07 (PR #201) |
| 1 | Thin prototype behind the preview boundary: readiness registry, frame, Profile Overview + Build on today's data, cleaned parcel map, Ask drawer, one Discovery flow; old/new isolation test | **Done** 2026-11-07, owner-approved (PR #203; Items 76–80: one tile per tab, no satellite, Cities: Skylines map required) |
| 2 | Latency spike: p50/p95 per retrieval task, cold and warm; only catastrophic fixes or honest progressive loading (the owner named slow loading, Item 79) | **Done** 2026-11-07, owner-approved (PR #204; Items 81–83: cold p50 26.8 s / p95 46.0 s; TIF and crime caches; a first screen in about 1–3 s from `/api/scorecard/first`; production repeat visits slowed by FEMA failing from the server) |
| 3 | Builder test against the pass criteria in Item 75 (model budget $2, chat only in the follow-up task; Item 83) | **Deferred** 2026-11-08 by the owner (no builders lined up; Item 88). Production latency re-measured (Item 87). Kit ready locally (`research/16-builder-test-kit/`, not in the repo). The test must run before any route flips by default |
| 4 | Profile response split, designed from the Phase 2 data | **Done** 2026-11-08, owner-approved (PR #210; Item 89: the Profile in parts behind `/api/profile/*`, one record per lookup, 20 s per-source deadline, the City's building records late, the Profile's outline before the first screen; Overview about 4 s p50 locally, production pass after deploy) |
| 5 | Map tracks M1 (base + one persistent map), M2 (parcels), M3 (official zoning geometry); the Cities: Skylines look is required (Item 80) | **Done** 2026-11-09, owner-approved ("thumbs up"; PR #212; Items 90–98: MapLibre over our own tiles from the City's streets, parks, water and official zoning; lots from the County's full-precision outlines; zoning in NAD83 on the lot lines; one persistent map, On/Off key by color family, pins, Street View link-out; color-blind textures). Production needs the tile files built once on the server (Items 91–92) |
| 6 | Remaining Profile tabs and Discovery, route by route; routes flip as approved | **Done** 2026-11-10, owner-approved route by route: Money (Item 99), the parts fixes (Items 100-101), Neighborhood (Item 102), History (Item 103, PR #216), **Discovery** (Item 104: the one map over the whole city colored by room to build, a block grid when zoomed out, matches as outlines, the City's 98 neighborhoods, filter groups in plain words, list cards with a colored block slice; room to build known for 87.3% of lots, 8.0% unknown). History and Discovery merge together; production then needs the Discovery data steps in Item 104 |
| 7 | Data tracks M4 (capacity), M5 (land in use), M6 (3D), each blocked by its thresholds | **In progress** 2026-11-10: step 1 measured (Item 105: the County's 2022 LiDAR building heights; no-go for filling Discovery's stories, go for M6's heights in feet); track order is the owner's call |
| 8 | Full chat page, landing and signed-in home | Waiting |
| 9 | Commercial epics, each with its own plan: quotas, billing and entitlements, identity, Saved; then Deep analysis and subscription | Waiting |
| 10 | Restyles, native Spanish read-through, stabilization window, deletion of the old UI | Waiting |

## Working rules (from Item 75)
- Branch from current `main` in a worktree. Open PRs freely once the local gates pass; **never merge** without green CI, verification and the owner's go (merge = deploy). Batch ready work into few merges.
- CI gates: `npm run build`, `npm run test`, `npm run lint`, backend `pytest -m "not integration"`. Local release gates: the mobile matrix, page budgets, Playwright axe, a keyboard walkthrough.
- No production model calls in automated development or tests; human prototype testing only within the budget the owner approves ($2 for Phase 3). Test chat only when a change updates or fixes chat (Item 83).
- Docs: during the rewrite the brief and the decisions file govern new UI work; the Bento Pro guides and `page-design.md` describe today's live UI only (Item 78). No satellite map anywhere in the new UI; every map must reach the Cities: Skylines look before its route flips (Item 80).
- Every new screen: icons beside visible labels, reuse without leaking into old pages, light and dark, English and Mexican Spanish (usted) in the same PR, accessible.

## End-of-milestone checklist
Run this when a phase (or a large part of one) is finished, before stopping:
1. **Decisions:** add the phase's Item(s) to `decisions/2026-11_frontend-rewrite.md` (decision, alternatives, evidence, revisit-if, numbers) and its line in `decisions/README.md`.
2. **Status:** update the table above, and the brief's "What comes next" if the order or scope changed.
3. **Operational docs:** `frontend/CLAUDE.md` / `backend/CLAUDE.md` for new files and conventions; the `claude-context/README.md` manifest if a doc was added.
4. **About page:** for shipped work that is a big engineering decision or a hard problem (the owner keeps it as the project record).
5. **Next prompt:** write `plans/<date>_frontend-phase-<N>-prompt.md` (local): goal, what to read, scope, acceptance, open questions for the owner, the rules above, and this checklist. Copy it into the shared session-notes folder when one is in use.
   (Process confirmed by the owner 2026-11-07: owner reviews the running prototype on localhost and gives a thumbs up or notes; then docs, close-out, and a new session started with the next prompt.)
6. **Hand off:** give the owner the prompt and offer it as a new session; stop the current conversation there to keep context small.
