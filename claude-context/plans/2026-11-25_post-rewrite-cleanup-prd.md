# PRD — Post-rewrite cleanup (code-debt pass)

Status: **Executed 2026-11-25** (Item 137; the PDF-report retirement waits on the zero-purchases check) · 2026-11-25 · Owner: Jack · Executor: one agent session, in phases with stop gates

## 1. Why

The front-end rewrite (Phases 0–13, Items 73–130) is done and the old UI was deleted in Phase 10. File-level dead code is therefore already small, but a rewrite leaves debt at a finer grain: two components doing one job, names that only made sense while two UIs lived side by side, exports and i18n keys nobody reads, backend endpoints only the old UI called, and docs that describe a world that no longer exists. Left alone, each of these misleads the next person (or agent) who reads the code.

**Goal:** a codebase where everything that ships is used, every concept has one implementation, and names describe today's product — with no change a user can see.

## 2. What a 2026-11-25 spot check already found

These seed the inventory; the agent confirms each and finds the rest.

| # | Finding | Evidence | Likely action |
|---|---------|----------|---------------|
| F1 | Only one frontend file unreachable from `main.tsx`: `lib/parcelMap.ts` (76 lines) | import-graph walk, tests excluded | Delete |
| F2 | **Two chat-message renderers.** The chat page uses `app/chat/ChatMessage.tsx`; the Ask drawer (`app/ask/AskDrawer.tsx`) still uses the old `components/MessageBubble.tsx`, which drags in `ThinkingTrace`, `DisclaimerBanner`, `CitationPill`, `DataPill`, `Tooltip` | grep of importers | Consolidate onto the new one (needs Jack's look — visible) |
| F3 | Two component homes: `src/components/` (18 files) + `src/components/ui/` beside `app/ui/`; `components/ui/Modal` has no importers | grep | Move survivors into `app/`, delete the rest |
| F4 | Rewrite-era names: 18 `*NextPage.tsx` files, `AuthOverlays` wrapping `AuthOverlaysNext`, `.ui-next` CSS class in 34 files | `git ls-files`, grep | Rename (pure mechanical) |
| F5 | 5 of 87 backend routes have no frontend reference: `/api/admin/cache`, `/api/auth/apple/callback`, `/api/auth/dev/authorize`, `/api/community-area`, `/api/newsletter` | route list vs `frontend/src` + `e2e` | Per route: callbacks/ops stay, the rest Ask |
| F6 | ESLint: 45 warnings against a cap of 65 (21 `set-state-in-effect`, 15 `only-export-components`) | `eslint -f json` | Lower cap to 45 now; fix where cheap |
| F7 | Stale docs: `AGENTS.md` (memory says use CLAUDE.md), guides marked "history" (Bento Pro, `design-system.md`, `page-design.md`, `light-dark-theming.md`), ~50 local prompt files in `plans/` | CLAUDE.md, README manifest | Archive per `claude-context/README.md` rules |

## 3. Scope

**In scope**
- `frontend/src`: dead files, unused exports/types, duplicate components, rewrite-era names, unused CSS/tokens, unused i18n keys (en + es together), unused npm deps.
- `backend/`: routes, modules, functions and settings with no caller; tests that only test dead code.
- Repo: stale docs, scripts, config, CI steps; root clutter.
- Guardrails that stop debt regrowing (§7).

**Out of scope (non-goals)**
- No visible change, redesign, copy change or new feature. F2 is the one exception, and only with Jack's OK.
- No refactors for taste. "Could be cleaner" is not a reason; "two things do one job" or "nothing uses this" is.
- No data, index, schema or migration changes; no production server access.
- No Anthropic API spend (no live chat/judge runs). $0 eval suites are fine.
- No merge to `main`. Branch + PR only; Jack merges.

## 4. Method

### Phase 0 — Baseline (measure before touching)
Record in the decision entry: frontend LOC (non-test), backend LOC (non-test), file counts, `npm run build` chunk sizes (gzip), lint warning count, vitest + pytest counts and pass state, `npm run test:mobile` result. These are the before numbers the PR reports against.

### Phase 1 — Inventory (read-only; no edits)
Produce `claude-context/audits/2026-11_cleanup-inventory.md`, one row per candidate. Tools, in order of trust:

1. **Frontend:** `knip` (unused files, exports, types, deps — needs Jack's OK to add as a devDependency), plus an import-graph walk from `main.tsx` and the lazy imports in `app/pages.ts`.
2. **Backend:** `vulture` at high confidence, then a route→caller map (frontend, e2e, `scripts/`, `deploy/`, systemd timers, Stripe/OAuth webhooks, eval harness).
3. **i18n:** every key in `locales/en/*.json` checked against `t("…")` calls; flag keys built from template strings as "dynamic — keep unless proven".
4. **CSS:** classes/tokens in `app/app.css` and `index.css` with no use in `.tsx`.
5. **Duplicates:** pairs of components/hooks/helpers that do the same job (F2-style), found by reading `src/components`, `src/lib` and `src/contexts` against `app/`.
6. **Docs:** every file in `claude-context/README.md` marked history/stale, plus `AGENTS.md`, `docs/`, `plans/`.

Each row: **path · what it is · evidence (who calls it, or the search that found nobody) · verdict · risk**.

Verdicts:
- **Delete** — no caller, evidence attached.
- **Consolidate** — keep one implementation; name which survives and why.
- **Rename** — correct but misnamed; mechanical.
- **Keep** — looks dead but isn't (dynamic use, external caller, ops tool); write down why so the next audit doesn't re-flag it.
- **Ask Jack** — product call, visible change, or evidence is unclear.

### Gate 1 — Jack reviews the inventory
Agent stops here. Jack marks the Ask rows and spot-checks Deletes. Nothing is edited before this.

### Before Phase 2 — clear the runway
Open PRs touching `frontend/src` as of 2026-11-25: #278 (map Layers, Item 136) and #271 (landing hero video, Item 134). Merge or close them first, or the rename commit will conflict with both. Dependabot #270 (Tailwind 3 → 4) is a major upgrade that rewrites CSS config. Close it, or do it as its own project after this pass. Do not combine it with this cleanup. Branch Phase 2 from a fresh `main`.

### Phase 2 — Execute, lowest risk first
One branch (`chore/post-rewrite-cleanup`), one commit per category so each can be reverted alone, one PR (per the batch-merges preference):

1. Delete confirmed-dead files and exports (+ their tests).
2. Remove unused deps, i18n keys (en + es in the same commit), CSS.
3. Mechanical renames (`*NextPage` → `*Page`, `AuthOverlaysNext` folded in, `.ui-next` → a neutral root class). Rename only; no logic in the same commit.
4. Consolidations (F2/F3), each its own commit.
5. Backend dead routes/modules.
6. Docs archived per `claude-context/README.md`.
7. Guardrails (§7).

After every commit: `npm run build`, `npm run test`, `npm run lint`, `pytest -q`. A red gate means revert that commit, not patch forward.

### Gate 2 — Localhost review
Agent runs the app, says exactly which screens changed (should be: Ask drawer only, if F2 approved), runs `npm run test:mobile` and the `live-site-sweep` skill against localhost, and reports the after numbers vs Phase 0. Jack gives a thumbs-up, then merges.

## 5. Rules that make deletions safe

- **Evidence or it stays.** Every deletion cites the search that found no caller. "Looks old" is not evidence.
- **Search for strings, not just imports.** Lazy `import()`, route paths, i18n keys, CSS class names, `data-*` hooks, env vars, and endpoint URLs are all referenced as strings. Also search `e2e/`, `scripts/`, `deploy/`, `eval/`, `ingestion/`, `.github/`, Dockerfiles and compose files.
- **External callers count.** OAuth/Apple callbacks, Stripe webhooks, health checks, timers, admin curl endpoints, and links in emails or already-shared URLs can have no frontend reference and still be live. Default to Keep + reason.
- **Delete tests with the code they test, never to make a gate pass.**
- **No behaviour change hidden in a cleanup commit.** If a consolidation changes output, it's flagged in the PR and shown at Gate 2.
- **Decisions logged** in `claude-context/decisions/` (alternatives, evidence, revisit-if), committed in the same PR.

## 6. Done means

- Inventory exists and every row has a verdict.
- Zero non-test files unreachable from `main.tsx`; `knip` clean or every remaining item has a Keep reason.
- One implementation per concept for everything flagged Consolidate.
- No `Next`/`ui-next` names left except where Jack chose to keep them.
- All gates green; no visible change other than those Jack approved.
- PR body reports before/after: LOC, files, bundle gzip, lint warnings, test counts.

## 7. Keeping it clean afterwards (ratchets)

- Lower the ESLint `--max-warnings` cap to the new count; lower it again whenever it drops.
- `knip` in CI as a failing check (with a config listing the deliberate Keeps).
- ESLint `no-restricted-imports`: `app/` may not import from deleted/legacy folders once they're gone.
- Optional: a bundle-size budget in CI for the main chunk.
- At the end of each future redesign phase, the runbook's close-out checklist adds one line: "delete what this phase replaced, in this PR."

## 8. Open questions for Jack

1. OK to add `knip` (frontend) and `vulture` (backend dev) as dev dependencies?
2. F2: consolidate the Ask drawer onto the new chat message renderer? It is a visible change.
3. F5: are `/api/newsletter` and `/api/community-area` still wanted, or leftovers?
4. `plans/` is local and untracked: archive the shipped prompts to a dated folder, or leave as-is?
5. Backend in the same pass, or frontend first and backend as a second PR?
