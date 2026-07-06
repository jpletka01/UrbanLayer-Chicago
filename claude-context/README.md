# Context Docs — UrbanLayer

Load only what the current task needs. **Don't read everything.** One line per file below; the
`load-urbanlayer-context` skill maps common work-types → the exact files to open.

**The definitive archive is the website About page** (`frontend/src/components/AboutPage.tsx`, ~35
sections): architecture, design decisions, and war stories in full. Files under `archive/` and `audits/`
are now short **pointers** into that record + git history — read them for the one-paragraph summary and
reusable lesson, not the full narrative.

## Core (load 1–2 for most coding tasks)
- `core/architecture.md` — RAG pipeline, domain orchestrators, vector search, key design decisions.
- `core/data-sources.md` — every dataset (Socrata, ArcGIS, external APIs), endpoint reference, PIN system.
- `core/known-issues.md` — active bugs, limitations, fragile heuristics, operational status. **Check first.**

## Guides — living (load when working in a specific area)
- `guides/backend-guide.md` — router, assembler, synthesizer, caching, HTTP clients, concurrency, testing, eval.
- `guides/frontend-guide.md` — components, design tokens, state, map system, responsive, animations.
- `guides/report.md` — **the $25 Feasibility Report** (current V6 architecture, render isolation, honesty rules, known data-blocks, QA parcels).
- `guides/zoning-cache.md` — precomputed zoning-extraction cache (reranker is out of the report path); rebuild + limits.
- `guides/parcel-resolution-truth-model.md` — the canonical address→PIN contract (who may write parcel identity; approximate/nearest-unverified rules).
- `guides/scorecard-dashboard-model.md` — the Scorecard's dashboard+chat model and card architecture.
- `guides/deployment.md` — server ops, `.env` template, deploy commands, monitoring, DB backups.
- `guides/ptaxsim-prod-seeding.md` — seeding the ptaxsim tax DB on prod (the "0 tax data since launch" runbook).
- `guides/auth-and-conversations.md` — Google OAuth + JWT, conversation persistence, sharing.
- `guides/latency-reduction.md` — completed + planned perf work, pipeline timing reference.

### Design system — **canonical: "Bento Pro"**
- `guides/bento-pro-redesign.md` — the token system + landing (source of truth for color/type/radius/primitives).
- `guides/bento-pro-phase3-app-surfaces.md` — Scorecard/Discovery redesign (the active design working doc).
- `guides/dot-matrix.md` — the LED dot-matrix halftone renderer (hero skyline backdrop + reusable image→dot art + the in-browser Playwright probe workflow).
- `guides/design-system.md`, `guides/light-dark-theming.md` — **HISTORICAL** (the "Cyanotype on Vellum" palette + Space Grotesk are retired by Bento Pro). The **theming mechanics still apply**: CSS-var-backed tokens, `ThemeProvider`/`useTheme`, `system` default, mode-lock islands with `data-theme`. Read only for that mechanism or the AA-contrast reasoning.

## Property Discovery — filter/search workbench (SHIPPED, full citywide, nav-linked)
- `property-discovery/` — engineering spec (`00`–`09`, normative) + implementation record. **Start with
  `10-implementation-status.md`.** Live on prod across all 77 community areas (~949k parcels). Impl:
  `backend/discovery/` + `frontend/src/discovery/`. Strategy/why: `strategy/property-discovery-filters.md`.
  (Spec drift to know: `03` says 29 filters — live is 32; wire is `{rows,total,nextOffset,gated}` + `/search/pins` + `/search/export`.)

## Strategy (load only for product/business planning)
- `strategy/north-star.md` — **governing** product plan: manifesto, wedge, feature audit, phases, validation.
- `strategy/2026-07-05_growth-strategy.md` — **active** go-to-market operating guide: product-dev rules + acquisition-infrastructure P0s (attribution, funnel events, SEO surface, email capture, privacy policy), channel plan (interviews → community → launch moments → programmatic SEO → paid), visitor-intelligence data model, feedback engine (feature-ask ledger, 3+ rule), weekly cadence + 30/60/90 + decision gate.
- `strategy/product-coherence-audit.md` — the "parcel dossier machine" first-principles review (steps 1–4 all shipped); funnel map + per-surface scorecard.
- `strategy/2026-06-15_homepage-coherence-pass.md` — coherence step 4 (shipped): entry/chat-access model + reusable IA frameworks. Read before homepage/entry work.
- `strategy/phase2-interview-kit.md` — customer-validation interview kit (recruiting, script, observation checklist).
- `strategy/competitive-analysis.md` — Chicago Cityscape comparison, data gaps, structural weaknesses.
- `strategy/product-roadmap.md` — revenue features, pricing model, personas, open questions.
- `strategy/design-guidelines.md` — hybrid dashboard+chat model, UX principles, chat-vs-tools.
- `strategy/property-discovery-filters.md` — filter/search strategy + why (the system is now shipped).
- `strategy/2026-07-02_data-expansion-candidates.md` — **live backlog** of available-but-unintegrated data, ranked (Tier 0–2; items 1–2 + appeals/ward shipped in the lot-info arc; CPS/Divvy tail remains).

## Archive & Audits (pointers — full stories on the About page)
- `archive/*` — one-paragraph markers for each shipped feature/incident (deployment, expansion, revenue, i18n,
  a-la-carte reports, coherence steps 1–3, selected-parcel, scorecard-ux, report-oom-reranker,
  `2026-06-report-saga` [V3→V6 + R5–R7], pin-resolution-seam, scorecard-chat-grounding, verdict-grounding-ux,
  chat-usability, lot-info-robustness, growth-instrumentation [attribution/funnel/SEO/privacy/capture +
  email/DNS setup], `2026-07-06_scorecard-usability` [class-aware tax fix (commercial eff-rate was 2.5×
  understated, incl. in the $25 report) + MiniChatDock + feedback/segment re-home + card-height fix]).
  `archive/TEMPLATE.md` is the archivation template.
- `audits/*` — resolved point-in-time investigations, each pointing at the archive entry or living guide that
  superseded it (full-site-sweep, resolver-investigation, gis-parcel-resolution-fix, design-ux-skills-audit,
  three-page-workflow-audit, lot-coverage-benchmark, verdict-flag-signals-panel-diff).

## Keeping Docs Current
After shipping, update the relevant **living** doc: backend modules → `backend/CLAUDE.md`; frontend →
`frontend/CLAUDE.md`; new data sources → `core/data-sources.md`; new bugs/limits → `core/known-issues.md`.
Design/token work → the Bento Pro guides. Then reflect the change in this manifest and, for durable
decisions/war stories, the About page.

## Archivation Rules
When a feature/plan/initiative is **fully shipped to production**:
1. **Create an archive pointer** using `archive/TEMPLATE.md`, named `YYYY-MM-DD_short-name.md` — one paragraph:
   what shipped, date, commit, the reusable lesson, and a link to the About page section for the full story.
2. **Strip the completed content** from active files — leave only a one-line "shipped" summary.
3. **Add/adjust the entry** in this README.
4. **Don't archive partial work** — if 3 of 5 items shipped, archive the 3, leave the 2 active.
5. **Fixed bug?** Move its `core/known-issues.md` entry into the archive pointer for the fix. No strikethrough
   "Fixed" entries left behind.
6. **The big narrative goes on the About page**, not into a long archive file — keep archive/audits as pointers.
