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
- `guides/report-status.md` — **Master report feature tracker**: shipped (V3-V6), blocked/data-dependent, confirmed limitations, rejected features, future ideas
- `guides/report-v6-improvements.md` — V6 open issues: parcel map needs real geometry, year_built data gaps, ownership limitation, comps map validation
- `guides/report-v6-audit.md` — **Rejection audit of `report_v6g.pdf`** (2026-06-10): every finding ranked by decision-quality impact × effort, quadrant view, execution order, verified root causes. Key caveat: audited PDF was mock=true — regenerate real-data before fixing
- `guides/report-v6-execution-plan.md` — **Master V6 phased execution plan & status.** Phase 1 (viability: R1 zoning fallback, R2 tax/assessment, R3 comps, R4 formatting) **SHIPPED 2026-06-10 (commit f0c1996)** with verified results; Phases 2–4 (credibility, decision-quality, UX/viz) pending. Verification parcels: EX subject `14283190070000` + taxable control `14331030110000`. Read this first for current report work.

## Strategy (load only for product planning / business discussions)
- `strategy/north-star.md` — **North Star Product Plan**: manifesto, wedge (per-unit reports), feature audit, development phases, customer validation plan. This is the governing strategy document.
- `strategy/product-coherence-audit.md` — **Product Coherence Audit (2026-06-11, post-SelectedParcel)**: founder-level first-principles review. Verdict: one product ("parcel dossier machine" — find/open/interrogate/buy), front door wired to the wrong room (homepage → auth-walled chat; Scorecard orphaned; "report" vocabulary collision; map defaults inverted). Funnel map, per-surface coherence scorecard, future-state conceptual architecture. Step 1 (renaming + chat→Scorecard bridge) SHIPPED 2026-06-11 — see §10 for per-item status; remaining steps need fresh approval. Read alongside north-star.md for any product/UX/funnel work.
- `strategy/competitive-analysis.md` — Chicago Cityscape comparison, data gaps, structural weaknesses
- `strategy/product-roadmap.md` — Revenue features, pricing model, target personas, open questions
- `strategy/design-guidelines.md` — Hybrid dashboard+chat model, UX principles, when to use chat vs tools

## Archive (historical — don't load unless asked about past decisions)
- `archive/2026-06-11_rename-and-bridge.md` — Coherence audit step 1 (shipped 2026-06-11): "report" reserved for the paid artifact (chat export → "transcript", landing copy points at the $25 report), chat→Scorecard bridge (ScorecardBridgeCard + clickable ReportTeaser + `scorecard_bridge_click` event).
- `archive/2026-06-11_selected-parcel.md` — SelectedParcel unification (shipped 2026-06-11): frontend parcel-identity primitive, pin-keyed handoffs + canonical `?pin=` URLs, PIN-bound purchases (db schema v11), SelectedParcel-typed report API. Includes the full spec, verification results, and binding findings.
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
