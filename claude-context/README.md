# Context Docs — UrbanLayer

Load only what you need for the current task. Don't read everything.

## Core (load 1-2 for most coding tasks)
- `core/architecture.md` — RAG pipeline, domain orchestrators, vector search pipeline, key design decisions
- `core/data-sources.md` — All datasets (Socrata, ArcGIS, external APIs), endpoint reference, PIN system
- `core/known-issues.md` — Active bugs, known limitations, fragile heuristics, gotchas, operational status

## Guides (load when working in a specific area)
- `guides/backend-guide.md` — Router, assembler, synthesizer, caching, HTTP clients, concurrency, testing, eval
- `guides/frontend-guide.md` — Components, design tokens, state management, map system, responsive, animations
- `guides/auth-and-conversations.md` — Full auth flow (Google OAuth + JWT), conversation persistence, sharing
- `guides/deployment.md` — Server ops, .env template, deploy commands, monitoring, database backups
- `guides/latency-reduction.md` — Completed + planned perf optimizations, pipeline timing reference
- `guides/report-v5-plan.md` — V5 Report plan (shipped 2026-06-10). Reference for understanding synthesis rules, envelope rendering spec, approval pathway logic.
- `guides/report-v4-plan.md` — V4 Report plan (items 1-7 shipped; item 8 superseded by V5)

## Strategy (load only for product planning / business discussions)
- `strategy/north-star.md` — **North Star Product Plan**: manifesto, wedge (per-unit reports), feature audit, development phases, customer validation plan. This is the governing strategy document.
- `strategy/competitive-analysis.md` — Chicago Cityscape comparison, data gaps, structural weaknesses
- `strategy/product-roadmap.md` — Revenue features, pricing model, target personas, open questions
- `strategy/design-guidelines.md` — Hybrid dashboard+chat model, UX principles, when to use chat vs tools

## Archive (historical — don't load unless asked about past decisions)
- `archive/2026-06-09_a-la-carte-reports.md` — A la carte $25 report purchases via Stripe one-time payment (code complete 2026-06-09)
- `archive/2026-06-08_i18n-spanish.md` — Full i18n implementation plan (shipped 2026-06-08)
- `archive/2026-06-05_deployment.md` — Phase-by-phase deployment log (all phases complete)
- `archive/2026-06-05_expansion-phases.md` — Completed expansion phases, Tier 3 decisions
- `archive/2026-06-07_revenue-sprint.md` — 4-feature sprint plan + implementation details (all shipped)

## Keeping Docs Current
After completing work, update the relevant files to reflect changes. If you added backend modules,
update `backend/CLAUDE.md`. Frontend changes → `frontend/CLAUDE.md`. New data sources →
`core/data-sources.md`. New bugs/issues → `core/known-issues.md`.

## Archivation Rules
When a feature, plan, or initiative is **fully shipped to production**, archive it:

1. **Create an archive file** using the template at `archive/TEMPLATE.md`. Name it `YYYY-MM-DD_short-name.md`.
2. **Strip the completed content** from active files — remove strikethrough items, "Done" statuses, shipped phase narratives, and fully-implemented plans. Keep only the one-line summary of what shipped (e.g., in a "Completed" table row or changelog line).
3. **Add the archive entry** to this README's Archive section.
4. **Don't archive partial work** — if 3 of 5 items shipped, archive the 3 and leave the 2 in the active file.
5. **Known-issues.md cleanup** — when a bug is fixed, move its entry from `core/known-issues.md` to the archive file for the feature that fixed it. Don't leave strikethrough "Fixed" entries in the active file.
