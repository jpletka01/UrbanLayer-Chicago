---
name: load-urbanlayer-context
description: Load the right UrbanLayer context docs for the task at hand. Use at the start of any non-trivial coding, design, product, or ops task in this repo to pull the minimal set of files that actually matter — before reading code or editing. Routes work-types (report, Scorecard, chat/RAG, parcel resolution, lot facts, Property Discovery, design/theming, deployment, data sources, auth, perf, strategy) to specific docs. Wraps claude-context/README.md (the file-by-file manifest and source of truth for descriptions).
---

# Load UrbanLayer context

Pull the **minimum** set of docs for the current task — don't read everything. This skill is a
task-router; the per-file descriptions and statuses live in `claude-context/README.md` (the manifest),
and the definitive architecture + design-decision + war-story archive is the website **About page**
(`frontend/src/components/AboutPage.tsx`).

## Always in play
- Root `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md` are living operational docs (loaded/near-loaded each session) — trust them first.
- **Before shipping anything:** skim `claude-context/core/known-issues.md` (active bugs, fragile heuristics, operational status).
- **Push to `main` = deploy.** Get approval before pushing code; gate local checks on `npm run build` (not `tsc --noEmit`); verify the running image via the live API, not git HEAD.

## Route by what the task touches

| The task touches… | Read (in this order) |
|---|---|
| **The $25 Feasibility Report** (PDF, synthesis, envelope, render) | `guides/report.md` → `guides/zoning-cache.md` → `core/known-issues.md` |
| **Zoning extraction / FAR / Title-17 standards** | `guides/zoning-cache.md` → `guides/report.md` |
| **Scorecard / Verdict Band / decision-support** | `guides/scorecard-dashboard-model.md` → `frontend/CLAUDE.md` (ScorecardPage) → `archive/2026-06-30_verdict-grounding-ux.md` |
| **Chat pipeline** (router, assembler, synthesizer, RAG) | `core/architecture.md` → `guides/backend-guide.md` |
| **Chat grounding / Scorecard→chat handoff** | `frontend/CLAUDE.md` (grounding patterns) → `archive/2026-06-21_scorecard-chat-grounding.md` + `archive/2026-06-30_verdict-grounding-ux.md` |
| **Parcel resolution / address→PIN / geocoding** | `guides/parcel-resolution-truth-model.md` → `core/known-issues.md` (Cook County GIS) → `archive/2026-06-21_pin-resolution-seam.md` |
| **Lot facts / property retrieval / tax / provenance** | `archive/2026-07-03_lot-info-robustness.md` → `guides/ptaxsim-prod-seeding.md` → gate with `eval/lot_coverage.py` |
| **Property Discovery** (filters, search, index) | `property-discovery/10-implementation-status.md` → `property-discovery/` spec `00`–`09` → `frontend/CLAUDE.md` (`src/discovery/`) |
| **Design / CSS / tokens / component chrome** | `guides/bento-pro-redesign.md` → `guides/bento-pro-phase3-app-surfaces.md` → `frontend/CLAUDE.md` (Design Tokens) |
| **Hero backdrop / dot-matrix / canvas viz** | `guides/dot-matrix.md` |
| **Theming mechanics** (CSS-var tokens, dark/light, FOUC) | `guides/light-dark-theming.md` (mechanics only — palette is retired; Bento Pro is canonical) |
| **Map / geo visualization / deck.gl layers** | `frontend/CLAUDE.md` (Map sections) → `core/architecture.md` |
| **Mobile / responsive / phone layout** | `frontend/CLAUDE.md` (Responsive — incl. the 5-device overflow-audit harness; gate layout work with `npm run test:mobile`) |
| **Data sources / new dataset / endpoints** | `core/data-sources.md` → `strategy/2026-07-02_data-expansion-candidates.md` (backlog) |
| **Deployment / server ops / Docker / nginx** | `guides/deployment.md` → root `CLAUDE.md` (Workflow Rules) |
| **Auth / conversations / sharing** | `guides/auth-and-conversations.md` |
| **Performance / latency** | `guides/latency-reduction.md` |
| **i18n / adding a language** | `frontend/CLAUDE.md` (i18n) + `backend/CLAUDE.md` |
| **Product / strategy / funnel / pricing** | `strategy/north-star.md` (governing) → `strategy/product-coherence-audit.md` (+ `2026-06-15_homepage-coherence-pass.md` for entry/IA) |

## Notes
- Files under `archive/` and `audits/` are **pointers** (one paragraph + reusable lesson). Open them for the
  summary; go to the About page or git history for the full narrative.
- If a task spans two rows, load both left columns' top file, not every file — stay minimal.
- When something ships, update the living doc + the manifest per `claude-context/README.md` → Archivation Rules.
- If a needed topic isn't in the table, scan the manifest `claude-context/README.md` directly.
