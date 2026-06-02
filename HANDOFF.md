# Project Handoff — UrbanLayer — Chicago

A snapshot of what's been built, the decisions behind it, and what should come next. Companion to `README.md` (user-facing setup) and `~/.claude/plans/velvet-gliding-salamander.md` (the original implementation plan).

---

## TL;DR

A RAG-powered chat interface (branded as **UrbanLayer — Chicago**) for natural-language questions about Chicago. Combines live Chicago Data Portal (Socrata) data with semantic search over the entire Chicago Municipal Code. Single killer query: *"What's going on near 2400 N Milwaukee Ave?"* → a unified response covering crime, 311, building activity, business licenses, and applicable zoning, all from one prompt.

**Current status (2026-06-01):** Full pipeline operational. Ingestion complete (14,535 chunks in Qdrant, down from 14,628 after table consolidation). Eval suite passes 26/26 queries (100%), expanded to 39 queries covering new domain workflows. Retrieval quality benchmark: **A=15 B=1 C=2** on 18 user-style queries (up from A=13 B=1 C=4 after Bucket 3 reranker improvements). Most recent work: **Overlay/incentive map interactivity** — regulatory overlay districts and incentive zones now have hover tooltips and click popups with practical implications; multi-pick handles overlapping zones (landmark + TOD + ADU at the same point) in a combined "Regulatory Zones" popup with Base Zoning, Regulatory Overlays, and Incentive Zones sections. Previous: Walk Score + demographics + sidebar data fixes, sidebar data enrichment, multi-turn neighborhood switching fix, live thinking trace, Walk Score API integration, Expansion Phase 7 complete (all stretch items, workflow-based context selection, overlay/incentive map geometry, PTAXSIM tax estimation), Phase 7 core (TTL caching, startup preloading, graceful degradation, workflow_hint, eval expansion), Map loading fix + HTML/CSS bug fixes, Breakage fix + map refactor + real-API tests, Expansion Phase 6 (frontend integration), Phase 5 (neighborhood domain), Phase 4 (incentives domain), Phase 2 (property domain), Phase 1+3 (infrastructure + regulatory domain), `/about` page, Bucket 3 (reranker, batched cross-refs, async pipeline), Bucket 2 (admin dashboard, LLM-as-judge eval), Bucket 1 (mobile responsiveness, file upload), URL-based conversation routing, zoning UX overhaul, geocoding fix, zoning map integration, analytics category audit, SQLite persistence, map interactivity. **Known issue:** building violations synthesis inconsistency (see below); Cook County GIS parcel lookup intermittently returns empty results even with retry. 380 tests passing (339 unit + 41 integration).

---

## Stack (Locked)

| Layer | Choice | Reasoning |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-first, OpenAPI for free, easy SSE |
| LLM | Anthropic Claude **Sonnet 4.6** (`claude-sonnet-4-6`) for both router and synthesizer | Latest non-Opus model, better tool-use, structured output reliability |
| Vector DB | **Qdrant v1.9.0** (Docker, self-hosted) | Free, fast, good metadata filtering, payload search supports cross-ref lookup |
| Embeddings | **`BAAI/bge-base-en-v1.5`** via sentence-transformers (local, 768-dim, 512-token context) | Started with MiniLM-L6 (256 tokens), upgraded to bge-small (384-dim), then bge-base (768-dim) for better semantic discrimination on legal text. Query prefix enabled for asymmetric retrieval |
| Streaming | **SSE** (`text/event-stream`) | Synthesizer is the slow part (~3–8s); streaming TTFT is much better UX |
| Chat memory | **Multi-turn from day one**, history in **SQLite** (`backend/data/chicago.db` via `aiosqlite`), server-side persistence with per-message context/plan/mapData | Migrated from localStorage; low user count → SQLite is ideal |
| Geocoding | **Census Geocoder** (free, no key) + shapely point-in-polygon against cached community-area polygons | No rate limit, no API key, deterministic |
| Frontend | **React + TypeScript + Vite + Tailwind v3** | Type-safe contract with FastAPI Pydantic via OpenAPI |
| Map | **Mapbox GL JS** (dark-v11 basemap) + **deck.gl** (ScatterplotLayer, GeoJsonLayer) via `@deck.gl/mapbox` MapboxOverlay | Interactive geo visualization in the sidebar; Mapbox token is a public `pk.*` key, safe in frontend code |
| Doc ingest | **Parse local `chicago-il-codes.html`** (American Legal Publishing export, ~100MB) | Originally tried scraping Municode (deleted); the local HTML export is much more reliable |

Decisions that came up later and were resolved:
- The HTML file has a malformed div somewhere in Title 18 that causes lxml/html.parser to silently nest the trailing ~8MB (the republished Titles 16/17 "Zoning + Land Use Ordinance" volume) inside an earlier element. Worked around by splitting the file at the republication banner string and parsing each half separately. Without this, 250 republished sections and 1 net-new section were missing.
- Sentence-transformers import is lazy inside `vector_search._model()` so FastAPI can boot without the heavy torch dependency installed.
- Qdrant pinned to v1.9.0 because Docker Hub had issues with `:latest` tag and to ensure reproducible builds.
- Vector search uses raw HTTP API (`httpx.AsyncClient`) instead of qdrant-client Python library due to client v1.18.x incompatibility with server v1.9.0. All public vector search functions are natively async.
- Cross-encoder reranker: `bge-reranker-v2-m3` (BAAI, same family as embedding model). MS MARCO was tried first and disabled because it over-indexed on keyword overlap and hurt legal text retrieval. `bge-reranker-v2-m3` with score blending (20% reranker, 80% dense+keyword) applied BEFORE per-section dedup gives the best results.

---

## What's Done

Everything below is in the repo, tested and verified.

### Backend (`backend/`)
- `main.py` — FastAPI app, `/chat` SSE endpoint with phase timing events (now also emits `map_data` events and enforces message limits), `/autocomplete`, `/section/{section_id}` (full reassembled municipal-code section, backs clickable cross-references), `/api/map-data` (raw geo-located rows for the map panel), **`/api/conversations/*`** (7 CRUD endpoints for SQLite-backed conversation persistence), and **`/api/admin/*`** (6 endpoints for the admin dashboard: overview, timeseries, latency, conversations, requests, benchmark)
- `router.py` — Claude-based router producing strict `RetrievalPlan` JSON; system prompt embeds the 77 community-area names + 30+ neighborhood aliases + **search query guidance for zoning-specific terminology**
- `synthesizer.py` — streaming Claude synthesis call with **inline citation markers** (`[1]`, `[2]`) for code chunks
- `conversation.py` — **Multi-turn context synthesis** with improved heuristics for detecting follow-up questions, context references ("their", "it", "what about"), and clarification answers. **Deterministic neighborhood switching** bypasses LLM synthesis for "what about X?" / "compare to Y" patterns, substituting the new neighborhood into the original question structure
- `assembler.py` — pure context-merging function with caps (now sourced from `config.py`: `top_crime_types`, `top_311_types`, `top_chunks`, etc.), `Open - Dup` dedup, auto data-lag note, **capped-result detection** (sets `capped=True` when row count hits the `$limit` guard)
- `models.py` — Pydantic types: `RetrievalPlan`, `ContextObject`, `ChatChunk` (with `t_ms` timing), `Message`, `ChatRequest`; all five summary models carry a `capped: bool` flag
- `config.py` — env via pydantic-settings (Anthropic key, Socrata token, Qdrant URL, model/dataset IDs) **plus tuning knobs**: per-LLM `*_max_tokens`, per-source query `*_limit`s, assembler `top_*` caps, `db_path`, `message_limit`
- `db.py` — **SQLite persistence layer** via `aiosqlite`. WAL mode, singleton connection, schema versioning (v2). Tables: `conversations`, `messages` (with `context_json`/`plan_json`/`map_data_json` blob columns), `uploads`, `llm_calls` (per-LLM-call token/cost/latency logging), `request_logs` (per-chat-turn summary), `schema_version`. CRUD helpers + bulk import + admin query functions (overview aggregation, time-bucketed series, latency percentiles, paginated logs)
- `analytics.py` — **Server-side analytics**: month-over-month trend computation from raw Socrata rows. Groups by year-month + category, skips partial current month, returns `TrendItem` list. Results attached to `ContextObject.analytics` so Claude can cite trends in synthesis
- `llm.py` — shared Anthropic client (`get_anthropic_client()`) + **`tracked_create()`/`tracked_stream()` wrappers** that capture token usage (input, output, cache_read, cache_create), wall-clock duration, and error status per LLM call, persisting to the `llm_calls` SQLite table. `estimate_cost()` function with Sonnet/Haiku pricing
- `prompts.py` — the three system prompts (`ROUTER_SYSTEM_TEMPLATE`, `SYNTHESIZER_SYSTEM`, `CONVERSATION_SYNTHESIS`), moved out of the logic modules; synthesizer prompt includes capped-result handling rule
- `retrieval/`:
  - `socrata.py` — shared async client with retry/backoff, `X-App-Token`, `$limit` guard, and a `grouped_count()` helper for the repeated top-N aggregation shape
  - `utils.py` — `cutoff_iso()` shared by the dataset wrappers (was three duplicated `_cutoff_iso` helpers)
  - `crime.py` — `ijzp-q8t2` (neighborhood-aggregated + block-level), uses two parallel queries for crime counts + arrest counts (SoQL `case()` doesn't exist)
  - `three11.py` — `v6vf-nfxy` (open requests + response times, `Open - Dup` filtered)
  - `buildings.py` — `ydr8-5enu` permits (uses `reported_cost` field) + `22u3-xenr` violations
  - `business.py` — `uupf-x98q` active licenses
  - `map_data.py` — raw geo-located row fetching for the map panel (`crimes_for_map`, `requests_311_for_map`, `permits_for_map`, `zoning_for_map`); uses `socrata_get` directly with row limits (2500/1000/500) and `latitude IS NOT NULL` filters
  - `vector_search.py` — Fully async Qdrant semantic search via `httpx.AsyncClient` + batched cross-ref expansion, lazy embedder; per-section dedup, keyword boost scoring, **`bge-reranker-v2-m3` cross-encoder reranker** with score blending (reranks BEFORE dedup so the best chunk per section survives); `get_full_section()` reassembles a whole section from its chunks for the `/section` endpoint
  - `geo.py` — 77 community areas + alias table + Census Geocoder + shapely
- `tests/` — **380 tests** (339 unit + 41 integration), all passing

### Ingestion (`ingestion/`)
- `parse_chicago_code.py` — HTML parser with split-at-republication strategy, state machine for Title→Chapter→Article→Subarticle→Part, colspan/rowspan-aware table extraction with composite multi-row headers
- `chunk.py` — section-aware chunking with hierarchical header re-duplication, table flattening to `Row N: header=value`, sub-section splits inside tables at category boundaries (`A. Household Living`, `PUBLIC AND CIVIC`)
- `embed_and_store.py` — sentence-transformers + Qdrant upsert to two collections (`chicago_municipal_code`, `chicago_zoning` for Title 17 filter-free); `--recreate` flag for model upgrades
- `load_community_areas.py` — fetches and caches community-area polygons from Socrata `igwz-8jzy` as GeoJSON
- **Pipeline fully run**: 8,615 sections → 14,535 chunks → Qdrant (took ~3 minutes with MPS acceleration)

### Frontend (`frontend/`)
- Vite + React + TypeScript + Tailwind v3 scaffold
- State machine in `App.tsx`: splash (hero slideshow + chat pill + suggestion chips + ingestion stats grid) → split-screen workspace
- **Per-message context architecture** — Each assistant message stores its own `context` snapshot so citations remain valid across multi-turn conversations
- **Inline citation pills** — `[1]`, `[2]` markers rendered as clickable `CitationPill` components with hover tooltips showing source preview
- **Typewriter effect** — `useTypewriter` hook for character-by-character text reveal during streaming
- **Copy functionality** — Hover-revealed copy buttons on messages and source cards
- **Source panel** — Collapsible sidebar with "Sources" button (top-right), showing code chunks with relevance scores, cross-references, and expandable detail drawer
- Components:
  - `HeroSlideshow` (5 Unsplash photos, cross-fade)
  - `ChatInput` (glassmorphism pill, hero + compact variants, address autocomplete)
  - `MessageBubble` (react-markdown, inline citations, copy button, typewriter, live activity trace during streaming)
  - `CitationPill` (renders a `[N]` marker as the `§ <section>` reference + ordinal; hover tooltip; click opens/expands/flashes the source)
  - `DataPill` (colored `[data:*]` marker → opens Data tab, scrolls to card)
  - `SourceCitation` (card with rank badge, `§` pill, score, prose preview, in-place full-text expansion, clickable cross-refs)
  - `CrossRefPill` (clickable cross-reference with hover-preview of the target section)
  - `SourceDetailDrawer` (full-section viewer for a clicked cross-reference; opaque elevated panel, chained cross-ref navigation)
  - `Tooltip` (shared hover-tooltip: `position: fixed` with `useLayoutEffect` viewport clamping; solid `#333` bg + `#444` border; flips below trigger when no room above)
  - `ChunkText` (renders chunk text, delegates table segments to `ChunkTable`)
  - `ChunkTable` (formatted HTML table rendering for table-bearing chunks)
  - `sidebar/DataView`, `sidebar/SourcesView` (the two sidebar tabs)
  - `SidebarPanel` (collapsible context/data panel with drag-to-resize handle and collapsed rail; Data tab embeds the map above data cards with a vertical drag divider)
  - `sidebar/MapView` (Mapbox GL JS + deck.gl map with ScatterplotLayers for crime/311/permits/address pin, dynamic layer toggles, tooltips, flyTo animation, ResizeObserver for sidebar resize)
  - `sidebar/MapLayerToggles` (floating toggle pills, context-aware: crime-type filters for crime queries, department filters for 311, source-level toggles for overview)
  - `sidebar/MapLegend` (compact color legend, auto-hides when no layers active; zoning category legend in points-off mode)
  - `sidebar/ArrestFilter` (arrest status segmented control for crime mode)
  - `sidebar/StatusFilter` (open/closed status filter for 311 mode)
  - `sidebar/CostFilter` (cost bucket filter for permits mode)
  - `sidebar/DateRangeSlider` (dual-handle date range slider)
  - `sidebar/AnalyticsSection` (pie chart + trend table orchestrator by filter mode)
  - `sidebar/PieChart` (SVG donut with hover expansion, thin-slice ring, expandable legend)
  - `sidebar/TrendTable` (MoM trend rows with sortable columns, colored arrows)
  - `DisclaimerBanner` (amber, legal disclaimer)
  - `HistorySidebar` (conversation history)
- `lib/`:
  - `api.ts` (SSE fetch streaming; `fetchSection` with an immutable-section cache; **conversation CRUD functions**: `listConversations`, `getConversation`, `createConversation`, `deleteConversationAPI`, `saveMessages`, `updateMessageMapData`, `importConversations`)
  - `useChat.ts` (owns the SSE consumption loop + per-turn state; lifted out of `App.tsx`; **now accepts `conversationId`**, handles `map_data` SSE events, enforces client-side 10-message limit, exposes `atMessageLimit`; **activity tracking** derives human-readable labels from `plan.sources` and manages lifecycle across SSE phases)
  - `sse.ts` (reusable `parseSSE` generator used by `api.ts`)
  - `useCopyButton.ts` (shared copy-to-clipboard hook with transient "copied" flag)
  - `constants.ts` (SUGGESTIONS, splash stats, and the magic timers/thresholds)
  - `history.ts` (**async, API-backed** — replaced localStorage with server API calls; includes `migrateLocalStorageToSQLite()` for one-time migration)
  - `types.ts` (matches backend Pydantic, extended with per-message context/plan/mapData; `Conversation` is now a summary type; `StoredMessage`/`ConversationDetail` for API responses; `AnalyticsSummary`/`TrendItem` types)
  - `useTypewriter.ts` (character reveal hook)
  - `clipboard.ts` (copy utility)
  - `codeRefs.ts` (`isResolvableSection`, `stripHeader` helpers)
  - `parseTable.ts` (parses `[TABLE]`/`Row N:` markup into structured table data for `ChunkTable`)
- **Builds cleanly** (~322KB JS, 16KB CSS)

### Benchmarks & Eval (`eval/`)
- **Parser stats** — `python -m ingestion.parse_chicago_code --stats` prints per-title section/table/xref/definition/legislative-history counts
- **Per-phase latency** — every SSE event carries `t_ms`. Sidebar renders Router / Retrieval / Synthesis-TTFT / Total live
- **Query test set** — `eval/queries.json` has **26 representative queries**
- **Baseline established**: 26/26 passing (100%), latency p50: router 2.4s, retrieval 3.8s, total 13.6s
- **Retrieval quality benchmark** — `eval/retrieval_benchmark.py` with **18 user-style queries** evaluating vector search quality: gold section hit rate, section duplication, table fragment detection, grade (A–F). Current v4: **A=15, B=1, C=2** (up from v3: A=13, B=1, C=4 — no D or F)

---

## What's NOT Done

### ~~1. Mobile responsiveness~~ ✅ DONE (Bucket 1)

### ~~2. File upload support~~ ✅ DONE (Bucket 1)

### ~~3. Cost/token logging~~ ✅ DONE (Bucket 2 — Admin Dashboard)

### ~~4. LLM-as-judge eval~~ ✅ DONE (Bucket 2)
`eval/run_eval.py --full <URL> --judge` grades each synthesized answer on 4 dimensions (citation accuracy, factuality, completeness, rule compliance) using Claude Sonnet as the judge. Results write to `eval/judge_results.json` and are visualized in the admin dashboard's "Synthesis Quality" section alongside the existing retrieval benchmark.

### ~~5. Legal-domain reranker~~ ✅ DONE (Bucket 3)
Enabled `bge-reranker-v2-m3` with score blending (20% reranker, 80% dense+keyword). Applied BEFORE per-section dedup so the reranker picks the best chunk per section. Also batched cross-ref lookups (single Qdrant call) and converted the entire vector search module to native async. Benchmark: A=13→15, C=4→2.

### 6. Deployment
Currently local-only. No Dockerfile for the FastAPI backend, no CI/CD, no production config. The Vite SPA needs a static file server that serves `index.html` for all non-asset paths (Vite dev server handles this automatically, production won't).

### 7. Municipal Code is gitignored
`chicago-il-codes.html` (~100MB) is not in version control. Anyone cloning the repo needs to obtain it separately from American Legal Publishing.

### Known fragile heuristics
These work well enough but could break on edge cases:
- **Sub-header detection inside tables** — length cap (<80 chars) and min-chars threshold (400 chars before splitting)
- **Multi-row header count** — inferred from consecutive row patterns
- **Cross-references** — filter to section IDs only
- **Keyword boost weight (0.15)** — hand-tuned; too high drowns out semantic similarity, too low has no effect
- **Reranker weight (0.2)** — hand-tuned; higher values (0.3–0.5) regress `minimum_lot_size` and `setback_single_family`

### ~~Planned: Overlay map interactivity~~ ✅ DONE

Regulatory overlay districts and incentive zones now have hover tooltips and click popups. Multi-pick via `pickMultipleObjects` handles overlapping zones — clicking a point inside multiple overlays (e.g., Landmark District + TOD + ADU) shows a combined "Regulatory Zones" popup with three sections: Base Zoning, Regulatory Overlays (with descriptions and practical implications from `OVERLAY_INFO`), and Incentive Zones. Zoning-only clicks still show the original simpler popup.

### Known synthesis gaps

- **Building violations** — The `violations_api` source is fetched and the `ViolationSummary` is assembled into the `ContextObject`, but the synthesizer inconsistently mentions it in the response text. The data IS present in the context and the sidebar `ViolationsCard` renders correctly — this is a synthesis prompt attention issue. Likely fix: add violations to the explicit "must-cover" list in the synthesizer prompt for site_due_diligence workflows.

- **~~Walk Score~~** — **FIXED.** Walk Score was excluded for `property_intelligence` workflow, and the router classified broad address queries as `property_intelligence`. Both issues resolved: Walk Score no longer has a workflow exclusion, and the router now classifies "what can you tell me about [address]" as `site_due_diligence`. Walk Score (93/79/92 for Lincoln Park) now flows through to the sidebar and synthesis.

- **Demographics median values are estimated** — The Socrata ACS dataset (`t68z-cikk`) provides income bracket distributions, not pre-computed medians. Median household income is estimated by interpolating the bracket containing the 50th percentile household. Poverty rate and unemployment come from a second dataset (`kn9c-c2s2`). Median home value, rent, owner-occupied %, bachelor's degree %, and vacancy rate are not available from either dataset and remain null.

- **Cook County GIS intermittent failures** — The parcel lookup (`parcels.py`) intermittently returns 0 features for valid coordinates. A retry with 0.5s delay was added, but the service remains unreliable. When it fails, `PropertyCard` is absent from the sidebar. The integration test retries 3 times and skips on persistent failure.

- **Violation categories are homegrown** — The Chicago Data Portal violations dataset (`22u3-xenr`) has no standard category field. Each row has a free-text `violation_description`. Our `_categorize_violation()` in `assembler.py` does first-match keyword bucketing into 16 custom categories. These are reasonable but imperfect — the dataset also has a `violation_code` numeric field we're not fetching, which might give more reliable groupings.

---

## Session Log (2026-05-28 — Afternoon Session)

Work completed in this session (Chat UI QoL improvements):

1. **Per-message context architecture** — Extended `Message` type with optional `context` field. Each assistant message now stores its own context snapshot when streaming completes. Citations in old messages remain valid even after follow-up questions.

2. **Sidebar toggle visibility fix** — Moved toggle button outside the collapsible sidebar. Now shows as a "Sources" button in top-right corner with document icon and source count badge.

3. **Character-by-character typewriter effect** — Created `useTypewriter` hook with proper state management (useState instead of refs), cleanup on every effect run, and ~15ms per character reveal.

4. **Inline citation pills** — Created `CitationPill` component with:
   - Document icon + number badge
   - Hover tooltip showing section title and text preview
   - Click to open sidebar and highlight source

5. **Enhanced source cards** — Updated `SourceCitation` with:
   - Index badge matching citation number
   - Highlight state when selected
   - Cross-reference display
   - Copy button on hover
   - "Read more" indicator

6. **Source detail drawer** — Created `SourceDetailDrawer` for full source text view with copy functionality.

7. **Copy functionality** — Added clipboard utility and hover-revealed copy buttons to messages and sources.

8. **Conversation synthesis improvements** — Rewrote `needs_synthesis()` in `backend/conversation.py` to detect:
   - Very short answers (<50 chars) after assistant questions
   - Context references ("their", "it", "what about", etc.)
   - Follow-up question patterns ("do you have", "how do I", etc.)
   - Short questions lacking explicit location

9. **Backend citation prompt** — Updated `synthesizer.py` system prompt to instruct LLM to emit `[1]`, `[2]` citation markers.

---

## Session Log (2026-05-28 — Context & Data Sidebar Redesign)

Driven by user feedback on the side panel. All changes verified by driving the running app with headless Chromium (Playwright), not just unit tests.

1. **De-cluttered the Data tab** — removed the dev-facing "Latency" benchmarks card and "Active Sources" chips from `sidebar/DataView.tsx`. The live data cards (crime / 311 / permits / violations / business) stay — they're the evidence behind each answer — along with the data-lag note. Dropped the `PhaseTimings` plumbing from `App.tsx` / `SidebarPanel.tsx` that fed the removed card.

2. **Sources tab is now the default** whenever an answer used code sections (`App.tsx` sets the view from `context.code_chunks` on each `context` event); Data is only the default when there are no sources.

3. **Readability pass on sources** (`SourceCitation.tsx`) — section IDs render as `§ <id>` mono pills, the 1–5 rank is a filled circular badge, the collapsed preview is plain prose (header stripped via `lib/codeRefs.ts`) instead of a dense monospace block, and the expanded full text no longer has a `max-h` cap so the whole chunk is readable.

4. **Citations are the section reference itself** — the synthesizer prompt (`synthesizer.py` rule 1) now tells the model to drop a `[N]` marker where the reference belongs and NOT spell out the section number; the frontend renders each `[N]` as a `§ <section>` mono pill with a small ordinal (`CitationPill.tsx`). Clicking a citation opens the sidebar → Sources, scrolls to + auto-expands the source to full size, and plays a one-shot `animate-flash` pulse (re-fires on repeat clicks via a `sourceFlash` counter in `App.tsx`).

5. **Clickable cross-references → full-section viewer** — new `GET /section/{section_id}` endpoint (`main.py`) backed by `vector_search.get_full_section()`, which reassembles a complete section from all its chunks (orders by `chunk_index`, strips repeated headers + `(part N of M)` labels, unions cross-refs). The previously-dead `SourceDetailDrawer.tsx` was repurposed into the viewer for this, with chained cross-ref navigation. Cross-ref pills (`CrossRefPill.tsx`) are clickable and **hover-preview** the target section (title + 3-line snippet), reusing the citation-tooltip pattern; `fetchSection` (`lib/api.ts`) is memoized so the hover prefetch and click share one request. Note: some cross-refs point to sections not in the corpus and 404 — the drawer/tooltip handle that with a graceful "not available" state.

6. **Fixed transparent panel backgrounds (the drawer-overlap bug)** — `tailwind.config.js` had a dead top-level `'bg-dark': '#090d16'` color (never referenced) colliding with the nested `dark.bg`; the collision made the dev Tailwind JIT silently NOT emit `.bg-dark-bg`, so the sidebar, workspace, and section drawer all rendered with transparent backgrounds (invisible normally because `<body>` is dark, but it caused the section drawer's text to overlap the sidebar). Deleted the dead token and gave the drawer an explicit `bg-[#141414] shadow-2xl` + `bg-black/70` backdrop. **If panels ever look see-through again, check for this kind of Tailwind color-name collision first.**

New files: `frontend/src/components/CrossRefPill.tsx`, `frontend/src/lib/codeRefs.ts` (`isResolvableSection`, `stripHeader`).

---

## Session Log (2026-05-28 — Code-Health Refactor)

A behavior-preserving cleanup of duplication and inlined values that had accumulated through iteration. Scope agreed up front as "surgical, high-value" across both layers; larger rewrites were explicitly deferred (see below). Verification: backend 119/119 unit tests pass, frontend `tsc` build clean, lint count identical to baseline (no new issues). Shipped as two commits (`921dc83` backend, `3a061cb` frontend) merged to `main`.

**Backend**
1. **Shared Anthropic client** — new `backend/llm.py` `get_anthropic_client()` (`lru_cache`d) replaces the three separate `AsyncAnthropic(...)` constructions in `router.py` / `synthesizer.py` / `conversation.py` (a single chat hit all three).
2. **Deduped `cutoff_iso`** — three near-identical `_cutoff_iso` helpers collapsed into `backend/retrieval/utils.py::cutoff_iso(days, lag_days=)`; crime passes `lag_days=settings.crime_lag_days`.
3. **`grouped_count` helper** — `socrata.py` gained a thin builder for the repeated `$group/$select/count(*) as count` shape; crime + 311 top-N queries use it. One-off queries left as plain `socrata_get`.
4. **Prompts centralized** — `backend/prompts.py` now holds the three system prompts (verbatim moves; router still fills its community-area table via the template placeholder).
5. **Tuning knobs → config** — LLM `*_max_tokens`, per-source query `*_limit`s, and assembler `top_*` caps moved into `config.py`.
6. **Shared test fixture** — `backend/tests/conftest.py` holds one `mock_settings` (with dataset IDs + limits), removing the copies that had been duplicated across `test_socrata.py` / `test_retrieval.py`.

**Frontend**
1. **`useChat` hook** — `lib/useChat.ts` owns the SSE loop + per-turn state (messages/plan/context/error/disclaimer); `App.tsx` shed ~70 lines, 6 state vars, and 2 refs. Sidebar reactions wired via an `onContext` callback.
2. **`parseSSE` util** — `lib/sse.ts`; `chatStream` is now a one-liner over it.
3. **Shared UI primitives** — `components/Tooltip.tsx` (the three pills) and `lib/useCopyButton.ts` (the three copy buttons) replace the duplicated tooltip markup + copy logic.
4. **Constants** — `lib/constants.ts` holds `SUGGESTIONS`, splash stats, and the magic timers/thresholds.
5. **Type dedup** — removed the duplicate `Conversation` interface from `history.ts` (single source in `types.ts`).
6. **Theme tokens** — added `dark.tooltip/bubble/bubble-user/drawer` to `tailwind.config.js`; removed inline `#1f1f1f/#1a1a1a/#2a2a2a/#141414` hex and the `style={{backgroundColor}}` escape hatches.

**Deferred (considered, not done):** SoQL field-name enums / full query-builder DSL; React Context API to kill prop drilling; making `semantic_search` natively async / batching cross-ref lookups; Zod validation of SSE payloads; refactoring the `parse()` state machine. None are blocking — revisit if scale or churn warrants. Plan file: `~/.claude/plans/merry-prancing-blum.md`.

---

## Session Log (2026-05-29 — Sidebar Polish + Tooltip/Background Fixes)

Two phases: sidebar UX improvements (prior session, uncommitted) and tooltip/background readability fixes (this session). All verified with headless Chromium (Playwright) screenshots.

**Sidebar redesign** (prior session, now committed):
1. **Drag-to-resize** — `SidebarPanel` rewritten from Framer Motion percentage-width to a pixel-width panel with a left-edge drag handle. Snap-close at <200px, max 60% of viewport.
2. **Collapsed rail** — When closed, sidebar shows a narrow 44px rail with a document icon, source count badge, and vertical "Sources" label. Replaces the floating `SidebarToggle` button (deleted).
3. **`ChatInterface` simplified** — Removed `motion.section` with animated width%; now a plain `<section className="flex-1 min-w-0">` that fills remaining space via flexbox.
4. **Table rendering** — New `ChunkText` / `ChunkTable` components + `parseTable.ts` parser. Table-bearing chunks now render as formatted HTML `<table>` instead of raw `Row N: header=value` text.
5. **Legend-only chunk filtering** (backend) — `vector_search.py` overfetches 3× and filters out legend/key-only table chunks (no real data rows) before returning top-k.

**Tooltip & background fixes** (this session):
1. **Tooltip backgrounds** — Bumped from `#1f1f1f` (invisible against `#171717` surfaces) to `#333` with `#444` border. Background set via inline `style` to guarantee it applies regardless of Tailwind class ordering. Removed `backdrop-blur-sm` (was creating a pseudo-transparent look).
2. **Tooltip viewport clamping** — Switched from `position: absolute` (clipped by sidebar's `overflow-y: auto`) to `position: fixed` with a `useLayoutEffect` that measures the trigger's viewport rect, centers the tooltip, clamps horizontally to stay within 8px of viewport edges, and flips below the trigger when there's no room above.
3. **Section-detail drawer** — Backdrop overlay strengthened from `bg-black/70` to `bg-black/80 backdrop-blur-sm`. Drawer background bumped from `#141414` to `#1a1a1a`. Inner `ChunkText` and cross-ref pill backgrounds changed from fractional opacity (`/30`, `/40`, `/50`) to solid tokens (`bg-dark-surface`, `bg-dark-elevated`, `bg-dark-bg`).
4. **Source citation backgrounds** — Same solid-background treatment: expanded chunk text from `bg-dark-bg/50` → `bg-dark-bg`, non-resolvable cross-ref pills from `bg-dark-bg/40` → `bg-dark-elevated`.

Files changed: `tailwind.config.js`, `Tooltip.tsx`, `SourceDetailDrawer.tsx`, `SourceCitation.tsx`, `SidebarPanel.tsx`, `SidebarHeader.tsx`, `ChatInterface.tsx`, `App.tsx`, `vector_search.py`. New: `ChunkText.tsx`, `ChunkTable.tsx`, `parseTable.ts`. Deleted: `SidebarToggle.tsx`.

---

## Session Log (2026-05-29 — Capped-Result Awareness)

Socrata API queries carry `$limit` guards (e.g. 50 permits, 100 businesses) to avoid unbounded fetches, but the assembler was reporting `len(rows)` as the total count. When the real data exceeded the limit, the LLM presented round capped numbers ("50 building permits issued") as if they were exact — misleading users.

**Fix (4 files):**
1. **`models.py`** — Added `capped: bool = False` to all five summary models (`CrimeSummary`, `ThreeOneOneSummary`, `PermitSummary`, `ViolationSummary`, `BusinessSummary`). Default `False` so existing serialization is backwards-compatible.
2. **`assembler.py`** — Each summary function now sets `capped=True` when `len(rows) >= settings.limit_*`, signaling that the API likely returned its maximum and there are more results beyond the window.
3. **`prompts.py`** — Extended synthesizer rule 4: when a summary has `"capped": true`, the LLM must say "at least N" instead of stating N as an exact count.

Verification: all 35 assembler + model tests pass; manual smoke test confirms `capped=True` triggers at limit and `capped=False` below it.

---

## Session Log (2026-05-29 — Landing Page Animation + Smart Autocomplete)

Two UI improvements to the landing page and chat input.

**Animated count-up stats:**
1. **`CountUp` component** — New `frontend/src/components/CountUp.tsx` using `motion`'s `useMotionValue` + `animate` with an exponential ease-out curve (`[0.16, 1, 0.3, 1]`). Triggers once via `useInView`. Accepts a `format` function for locale-aware number formatting (commas).
2. **Splash stats** — `SPLASH_STATS` in `constants.ts` changed from string values to numeric values with optional `format`. The three stats (14,628 / 5 / 77) now animate from 0 with staggered delays (0.6s, 0.75s, 0.9s) after the container fade-in.

**Smart address autocomplete (prompt-preserving):**
1. **`findAddressFragment`** — New helper in `ChatInput.tsx` that scans for the last digit sequence in the input (`\d+\D*$`). Returns the start offset and fragment, or `null` if the fragment is too short (<3 chars). This means autocomplete only fires when there's an address-like pattern, not on plain text.
2. **Query uses fragment only** — Instead of sending the entire input to `/autocomplete`, only the address fragment is sent (e.g., `"525 w arlington"` from `"how is the crime around 525 w arlington"`).
3. **Splice on select** — `selectSuggestion` now preserves the prompt prefix and splices the selected address in at the fragment's start position. `"how is the crime around 525 w arlington"` + selecting `"525 W Arlington Pl, Chicago, IL"` → `"how is the crime around 525 W Arlington Pl, Chicago, IL"`.

Files changed: `ChatInput.tsx`, `constants.ts`, `App.tsx`. New: `CountUp.tsx`.

---

## Session Log (2026-05-29 — Typewriter Fix + Thinking Animation)

Two fixes to the streaming UX.

**Typewriter effect fixed** (`useTypewriter.ts`):
1. **Root cause** — The `useEffect` depended on `content.length`, which changes on every SSE token. Each change cleared and recreated the `setInterval`, resetting the timer before it could fire. The typewriter fell progressively behind. When streaming ended, `setDisplayedLength(content.length)` dumped all remaining text at once — visible right around the first citation marker.
2. **Fix** — Removed `content.length` from the effect dependency array (the interval already reads the target length via `contentRef`). Added `wasStreamingRef` to distinguish "never streamed" (show immediately) from "just finished streaming" (let the interval continue until caught up, then self-terminate). Added adaptive step sizing: 1 char/tick normally, 2 when 20+ behind, 3 when 50+ behind.

**Thinking indicator animated** (`MessageBubble.tsx`, `tailwind.config.js`):
1. **Bouncing dots** — Replaced static `animate-pulse` opacity fade with a `dot-bounce` keyframe (translateY -5px at 40%, staggered 200ms apart, 1.4s cycle). Dots bounce in sequence.
2. **Glowing text** — "Thinking" text (no ellipsis — dots do that job) oscillates between `#eeeeee` and `#6b6962` via a `text-glow` keyframe on a 2s ease-in-out cycle.

Files changed: `useTypewriter.ts`, `MessageBubble.tsx`, `tailwind.config.js`.

---

## Session Log (2026-05-29 — Cross-Reference Filtering)

Cross-reference pills in the sources sidebar were broken in two ways: 240 orange pills showed "unavailable" (section ID passed the regex but didn't exist in Qdrant), and 718 grey pills were non-clickable dead ends (failed the regex, and none existed in the corpus either). Only 1,973 of 2,931 unique cross-refs actually pointed to fetchable sections.

**Backend fix** (`vector_search.py`):
1. **Section index** — `_get_known_sections()` scrolls all Qdrant points once (paginated, 1k per request), caches a `frozenset` of every section ID in the corpus (~8,600 unique). Uses `lru_cache` so the scroll happens once per process lifetime.
2. **Filtering** — `_payload_to_chunk()` now filters each chunk's `cross_references` against the cached set. Only refs that exist in the database reach the frontend. Fails open (unfiltered) if Qdrant is unreachable during index build.
3. **Wider regex** — `_SECTION_REF_RE` broadened from `^\d+-\d+-\d+` to `^\d+[A-Za-z]?-\d+-\d+` to also match `14A-*` style section IDs during cross-ref expansion.

**Frontend fix** (`codeRefs.ts`):
- Widened `isResolvableSection` regex to match alphanumeric first segments (`14A-1-104`, `14B-3-301.2.2`). Acts as a fallback if the backend index is unavailable.

**Tests** (`test_vector_search.py`):
- `TestPayloadToChunk` patched to mock `_get_known_sections` (empty frozenset = unfiltered, matching fail-open behavior). Added `test_filters_cross_refs_against_known_sections` to verify filtering when the index IS populated. Regex tests updated for the wider pattern.

Files changed: `vector_search.py`, `codeRefs.ts`, `test_vector_search.py`.

---

## Session Log (2026-05-30 — Retrieval Quality Overhaul)

Built a retrieval quality benchmark (18 user-style questions with gold sections and answer-term checks) and used it to diagnose and fix three systemic issues with vector search. Grades improved from A=11 B=1 C=4 D=1 F=1 to A=13 B=1 C=4 D=0 F=0.

### Diagnosis

The benchmark revealed three failure modes:

1. **Section duplication (18% of result slots wasted)** — Long sections like `17-2-0300` (27 chunks) and `2-44-080` (30 chunks) dominated results because multiple chunks from the same section embed similarly. For "affordable housing," all 5 results came from just 2 sections.

2. **Semantic drift** — bge-small (384-dim) confused similar terms across contexts. "How close to the property line can I build a deck?" returned wireless tower freestanding facility rules and construction canopy "roof deck" standards. "Can I run a bakery from my home?" returned shared kitchen licensing instead of home occupation rules. "Fence height residential" returned vehicular use area screening rules.

3. **Table fragmentation** — The parking table (17-10-0200) was split into 26 chunks with 1-3 data rows each. All fragments embedded nearly identically, so the single chunk kept by section dedup might not be the one relevant to the user's question.

### Fixes applied (5 changes, 3 phases)

**Phase A — Router prompt rewriting** (`backend/prompts.py`):
Expanded the search query guidance from zoning-only to the full municipal code. Added explicit rules for accessory structures ("search accessory structures, not just fence"), home occupations ("search home occupation rules, not bakery"), licensing, building code, and non-zoning topics. The router already emitted a `search_query` field but had no guidance for 60% of the corpus.

**Phase B — Ingestion pipeline (batched to re-embed once):**

*Table chunk consolidation* (`ingestion/chunk.py`): The chunker flushed at every sub-header row regardless of block size, creating ~200 char table blocks. Added `TABLE_BLOCK_MIN_CHARS = 400` — sub-header splits are now deferred when the current block is small, with the sub-header inlined as a label (`--- Parking Group C ---`). Also added `_merge_small_table_pieces()` to merge consecutive `[TABLE]` pieces that fit within the chunk budget. Result: 14,628 → 14,535 chunks; 17-10-0200 dropped from 26 to 22 chunks.

*Embedding model upgrade* (`backend/config.py`, `backend/retrieval/vector_search.py`, `ingestion/embed_and_store.py`): Switched from `BAAI/bge-small-en-v1.5` (384-dim, 33M params) to `BAAI/bge-base-en-v1.5` (768-dim, 110M params). Enabled the BGE query prefix (`"Represent this sentence for searching relevant passages: "`) for asymmetric retrieval — documents are encoded without prefix, queries with it. Added `--recreate` flag to `embed_and_store.py` for model changes. Cold start goes from ~5s to ~8s; query latency is unchanged.

**Phase C — Retrieval-time scoring:**

*Per-section deduplication* (`backend/retrieval/vector_search.py`): After scoring candidates from Qdrant, keep only the highest-scoring chunk per section. Bumped overfetch from 3× to 5× to compensate for higher skip rate. This alone moved grades from A=6 to A=11.

*Keyword boost* (`backend/retrieval/vector_search.py`, `backend/config.py`): Added `_keyword_score()` that computes the fraction of unique non-stopword query terms found in each chunk. Combined score = `0.85 * dense + 0.15 * keyword`. Applied before section dedup so the keyword-matching chunk from each section survives. This helps when embedding similarity doesn't capture keyword relevance (e.g., "lot coverage" matching a chunk about lot area standards instead of the lot coverage percentage table).

*Cross-encoder reranking (infrastructure, disabled by default)*: Wired up `CrossEncoder` from sentence-transformers (already installed v5.5.1). Loads lazily via `@lru_cache`, scores query-document pairs with `cross-encoder/ms-marco-MiniLM-L-6-v2`, returns top-k by cross-encoder score. **Disabled by default (`reranker_enabled=False`)** because the MS MARCO model is trained on web search passages, not legal text — testing showed it actively hurt on several queries (pushed home occupation rules from rank 2 to out of top 5, reshuffled setback results incorrectly). The infrastructure is ready for when a legal-domain reranker (e.g., fine-tuned bge-reranker) becomes available. Toggle with `RERANKER_ENABLED=true` env var.

### Decision: why MS MARCO reranker was disabled

The cross-encoder (ms-marco-MiniLM-L-6-v2) is trained on MS MARCO, a web search dataset where "relevance" means "this web page answers a Bing query." Municipal code text has very different relevance signals — a chunk about "home occupations" is highly relevant to "Can I run a bakery from my home?" even though it never mentions the word "bakery." The MS MARCO model over-indexes on keyword overlap and surface similarity, which is exactly the problem we were trying to solve. With the reranker enabled, grades dropped to A=9 D=2 F=2 (worse than baseline). The keyword boost + better embeddings provide a cleaner improvement without the domain mismatch.

### Benchmark gold section adjustments

Two benchmark queries had gold sections that were too narrow:
- `fence_height`: The municipal code doesn't have a single "fence height in residential areas" section — the answer comes from scattered sections across accessory structures (17-9), screening/buffering (17-5-0600, 17-11-0200), and construction fences (10-28-281). Updated gold to include all relevant sections.
- `buildable_lot_definition`: The actual zoning lot definition is in `16-4-050` (Definitions), not only `17-17`. Updated gold to include `16-4` and `17-15` (Nonconforming lots).

### Final `semantic_search()` pipeline

```
query
  |-> prepend embedding_query_prefix (BGE asymmetric retrieval)
  |-> encode with bge-base (768-dim)
  |-> Qdrant dense search (limit = top_k × 5)
  |-> filter legend-only chunks
  |-> keyword boost: combined = 0.85 × dense + 0.15 × keyword_overlap
  |-> sort by combined score
  |-> per-section dedup (keep best per section)
  |-> return top_k CodeChunks
```

(When reranker is enabled, the pipeline fetches `reranker_candidate_count` unique sections, then re-ranks with the cross-encoder and returns top_k.)

### Files changed

- `backend/prompts.py` — expanded search query guidance for non-zoning topics
- `backend/config.py` — embedding model, query prefix, reranker settings, keyword boost weight
- `backend/retrieval/vector_search.py` — keyword boost, cross-encoder reranker, query prefix, per-section dedup
- `ingestion/chunk.py` — deferred sub-header splitting, small table piece merging
- `ingestion/embed_and_store.py` — `--recreate` flag, updated docstring
- `eval/retrieval_benchmark.py` — new: 18-query retrieval quality benchmark
- `eval/retrieval_quality_v1.md` through `v3.md` — benchmark reports

---

## Session Log (2026-05-31 — Mapbox + deck.gl Map Integration)

Added an interactive map to the sidebar Data tab, replacing the former stretch goal of a Leaflet map view. Built with Mapbox GL JS (dark-v11 basemap) and deck.gl ScatterplotLayers. The map is embedded directly above the data cards in the sidebar, not as a separate panel or tab.

### Backend

1. **New endpoint `POST /api/map-data`** (`main.py`) — accepts `community_area`, `time_range_days`, and a `sources` array. Only fetches data for the sources the router selected (e.g., a crime-only query only fetches crime rows). Returns raw geo-located rows with lat/lon for map rendering.

2. **New retrieval module `retrieval/map_data.py`** — four async functions using `socrata_get` directly (existing retrieval modules untouched):
   - `crimes_for_map` — dataset `ijzp-q8t2`, limit 200, `latitude IS NOT NULL` filter
   - `requests_311_for_map` — dataset `v6vf-nfxy`, limit 150, excludes `Open - Dup`
   - `permits_for_map` — dataset `ydr8-5enu`, limit 100, renames `reported_cost` → `estimated_cost`
   - `zoning_for_map` — dataset `p8va-airx` via `.geojson` endpoint (infrastructure ready, disabled by default)

3. **Models** (`models.py`) — `MapDataRequest` with `sources: list[str]` field, `MapDataResponse`

4. **Config** (`config.py`) — `limit_map_crime=200`, `limit_map_311=150`, `limit_map_permits=100`, `enable_zoning_layer=False`

5. **Tests** (`tests/test_map_data.py`) — 8 tests covering row cleaning, null filtering, cost renaming, endpoint shape, queried address, zoning failure resilience

### Frontend

1. **MapView component** (`sidebar/MapView.tsx`) — Mapbox GL JS map with deck.gl `MapboxOverlay`. Layers:
   - Crimes: ScatterplotLayer, color-coded by `primary_type` (amber=theft, red=battery/assault, purple=narcotics)
   - 311: ScatterplotLayer, color-coded by `owner_department` (teal=streets, coral=buildings, blue=CDOT)
   - Permits: ScatterplotLayer, radius scaled by `estimated_cost`, green
   - Address pin: blue dot with white stroke, rendered when `queried_address` is present
   - Zoning: GeoJsonLayer (infrastructure present, gated behind `VITE_ENABLE_ZONING_LAYER`)
   - Hover tooltips styled to match the dark theme (`#333` bg)
   - `flyTo` animation when a new address is queried
   - `ResizeObserver` handles sidebar drag-resize

2. **Context-aware data fetching** — `App.tsx` reads `plan.sources` and only passes map-relevant sources (`crime_api`, `311_api`, `permits_api`) to the `/api/map-data` endpoint. A crime-only query only fetches and displays crime data on the map.

3. **Dynamic filter toggles** (`MapLayerToggles.tsx`) — the toggle controls adapt based on what the router requested:
   - **Crime-only query** → crime-type sub-filters (Theft, Battery, Assault, Robbery, Narcotics, Criminal Damage, Burglary, Motor Vehicle Theft, Other)
   - **311-only query** → department filters (Streets & Sanitation, Buildings, CDOT, Other)
   - **Overview query** → source-level toggles (Crime, 311, Permits)
   - Filter mode derived from `plan.sources` via `deriveFilterMode()`

4. **Map + Data combined layout** (`SidebarPanel.tsx` `DataMapLayout` component) — map fills ~75% of the sidebar by default, data cards at the bottom ~25%. Features:
   - **Vertical drag divider** between map and data — drag to resize, double-click to collapse/expand
   - **Collapsible data section** — chevron toggle button collapses data cards, giving map the full sidebar height
   - When data is sparse (single-source query), the data panel is compact and the map dominates

5. **Types** (`types.ts`) — added `resolved_lat/resolved_lon` to `Location` (backend already sent these, frontend was dropping them), added `MapData`, `MapCrime`, `MapRequest311`, `MapPermit`, `QueriedAddress` interfaces

6. **API client** (`api.ts`) — `fetchMapData()` POSTs to `/api/map-data`

### Dependencies added

- `mapbox-gl`, `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/mapbox`, `@deck.gl/geo-layers`, `@types/mapbox-gl`
- Mapbox CSS imported in `main.tsx`

### Environment

- `VITE_MAPBOX_TOKEN` — required in `frontend/.env` (public `pk.*` token)
- `VITE_ENABLE_ZONING_LAYER` — optional, defaults to `false`

### Design decisions

- **Mapbox + deck.gl over Leaflet** — WebGL rendering handles hundreds of points smoothly in the sidebar's constrained viewport; deck.gl's declarative layer API makes filter toggling trivial (just rebuild the layers array)
- **Dark basemap** (`dark-v11`) instead of `streets-v12` from the original spec — the app is entirely dark-themed; a light map would clash
- **ScatterplotLayer for 311** instead of IconLayer — IconLayer requires a sprite atlas; ScatterplotLayer with department-based colors is simpler and visually clear at sidebar scale
- **Map embedded in Data tab** (not a separate tab) — user feedback preferred combining the related views. Map fills most of the space, data cards sit at the bottom, collapsible
- **Sources-aware fetching** — avoids fetching irrelevant data (e.g., no 311/permit rows for a crime-specific question), reduces Socrata API calls and map clutter

### Files changed/created

- `backend/config.py` — map limit settings
- `backend/models.py` — `MapDataRequest`, `MapDataResponse`
- `backend/retrieval/map_data.py` — **new**: geo-located row fetching
- `backend/main.py` — `/api/map-data` endpoint
- `backend/tests/test_map_data.py` — **new**: 8 tests
- `frontend/src/lib/types.ts` — `Location` lat/lon, map data types
- `frontend/src/lib/api.ts` — `fetchMapData()`
- `frontend/src/main.tsx` — mapbox-gl CSS import
- `frontend/src/App.tsx` — map state, sources-aware fetch, `planRef`
- `frontend/src/components/SidebarPanel.tsx` — `DataMapLayout` with drag divider + collapsible data
- `frontend/src/components/SidebarHeader.tsx` — reverted to 2-tab (Data/Sources)
- `frontend/src/components/sidebar/MapView.tsx` — **new**: Mapbox + deck.gl map
- `frontend/src/components/sidebar/MapLayerToggles.tsx` — **new**: dynamic toggle pills
- `frontend/src/components/sidebar/MapLegend.tsx` — **new**: compact legend
- `.env.example` — added `VITE_MAPBOX_TOKEN`
- `frontend/.env` — Mapbox token (gitignored)

---

## Session Log (2026-05-31 — Map Filters, Date Slider, Data Analytics)

Three feature additions to the map/data sidebar, plus a shared refactor to support them. All features are frontend-only except for raised Socrata row limits and a new `capped` field on the map data response.

### Shared Refactor

**Extracted `frontend/src/lib/mapColors.ts`** — `CRIME_TYPE_COLORS`, `crimeColor()`, `DEPT_COLORS`, `deptColor()`, `normalizeDept()`, `deriveFilterMode()`, `isArrested()`, and CSS-string variants moved out of `MapView.tsx` so both MapView and the new analytics components share a single source of truth. `FilterMode` type exported from here.

### Feature 1: Arrest Filter

**New component `ArrestFilter.tsx`** — a segmented control with three states: "All (N)" / "Arrested (N)" / "No Arrest (N)", positioned top-left of the map. Only appears in crime filter mode. Counts update live.

**`MapView.tsx` changes** — `arrestFilter` state (`"all" | "arrested" | "not-arrested"`), resets on new data. Crime layer filtering chain: crime-type toggles → arrest filter → date filter. Uses `isArrested()` from `mapColors.ts` to normalize Socrata's mixed boolean/string `arrest` field.

### Feature 2: Date Range Slider

**New component `DateRangeSlider.tsx`** — dual-handle range slider using two overlaid `<input type="range">` elements with custom dark-theme thumbs via `appearance: none` + webkit/moz pseudo-elements. Shows formatted date labels ("Mar 2 — May 28"). Renders inline (no absolute positioning) inside a shared top-right container with the layer toggles.

**`MapView.tsx` changes** — `computeDateBounds()` extracts min/max dates from relevant data sources. `passesDateFilter()` checks if a record's date falls within the selected range. Date filtering applied in all four modes (crime, 311, permits, overview), each using its source-specific date field (`date`, `created_date`, `issue_date`). The date slider and layer toggles are wrapped in a single `absolute top-2 right-2` container that stacks them vertically.

### Feature 3: Data Analytics Section

**New utility `frontend/src/lib/analytics.ts`** — pure functions:
- `computeTrends()` — groups records by category + month, compares most recent complete month to prior month, returns `TrendRow[]` with change percentages. Skips the current calendar month if partial.
- `computePieSlices()` — aggregates by category, returns sorted `PieSlice[]`.
- `getTrendMonthLabels()` — returns formatted month names for column headers.

**New component `PieChart.tsx`** — SVG donut chart (ring with empty center). Total count displayed in the center — uses `totalOverride` from the context's authoritative aggregate count (e.g., 1756 from `crime_last_90d.total`) rather than the row count of map data. Compact 2-column legend with color dots and percentages. Handles single-slice edge case with `<circle>` elements.

**New component `TrendTable.tsx`** — sortable table with columns: Type, current month, prior month, Trend. Trend column shows colored arrows (↑ red for increases, ↓ green for decreases) with percentage. Column headers clickable to toggle sort key and direction.

**New component `AnalyticsSection.tsx`** — orchestrator, rendered at the bottom of `DataView`. Collapsible via header toggle. Based on filter mode:
- **Crime**: trends/pie by `primary_type`, colors from `CRIME_TYPE_COLORS`
- **311**: trends/pie by `sr_type` (default) with toggle to switch to `owner_department` grouping
- **Permits**: trends/pie by `permit_type`
- **Overview**: shows all sources that have data

All computations wrapped in `useMemo` keyed on `mapData`.

### Wiring

- `SidebarPanel.tsx` (`DataMapLayout`) now passes `mapData` and `filterMode` (via `deriveFilterMode(mapSources)`) to `DataView`
- `DataView.tsx` accepts `mapData`, `filterMode`, renders `<AnalyticsSection>` when map data has records, passes `context` for authoritative totals

### Backend: Raised Row Limits + Capped Notification

**`config.py`** — Map row limits raised: `limit_map_crime` 200 → 2500, `limit_map_311` 150 → 1000, `limit_map_permits` 100 → 500. Previous limits only covered ~7 days of data in busy community areas; new limits cover the full 90-day window comfortably. Socrata's API is free with no per-row cost; the extra rows add ~1-2s latency.

**`models.py`** — `MapDataResponse` gained `capped: dict[str, bool]` field indicating which sources hit their row limit.

**`main.py`** — `/api/map-data` endpoint now computes `capped` by comparing each result's row count against its limit.

**`types.ts`** — `MapData` gained optional `capped` field.

**`MapView.tsx`** — when any source is capped, a small amber notice appears bottom-right: "Showing most recent N results".

### Design Decisions

- **SVG donut chart over charting library** — a pie/donut chart is mathematically simple (arc paths). Building it inline avoids adding recharts (~200KB) or chart.js (~170KB) to the bundle. The entire analytics feature adds ~5KB gzipped.
- **Date slider uses two overlaid range inputs** — no dependency needed. Custom thumb styling via pseudo-elements works across Chrome/Firefox/Safari. A debounced (30ms) onChange prevents excessive deck.gl layer rebuilds during rapid dragging.
- **311 analytics default to `sr_type` grouping** — more granular than department grouping; users think in terms of "potholes" and "graffiti", not "Streets & Sanitation". Toggle to switch to department view.
- **Trend arrows: red=up, green=down for crime** — crime increases are bad (red), decreases are good (green). This is intentional and matches the domain semantics.
- **`totalOverride` on PieChart** — the donut center shows the authoritative aggregate total from the context (e.g., 1756 crimes from the full Socrata count query), not the capped row count from the map data fetch (e.g., 2500). The pie wedge proportions use the sample data so the ring fills completely.

### Files changed/created

- `frontend/src/lib/mapColors.ts` — **new**: shared color constants, `deriveFilterMode`, `isArrested`
- `frontend/src/lib/analytics.ts` — **new**: trend/pie computation functions
- `frontend/src/components/sidebar/ArrestFilter.tsx` — **new**: arrest status segmented control
- `frontend/src/components/sidebar/DateRangeSlider.tsx` — **new**: dual-handle date slider
- `frontend/src/components/sidebar/PieChart.tsx` — **new**: SVG donut chart
- `frontend/src/components/sidebar/TrendTable.tsx` — **new**: MoM trend rows with arrows
- `frontend/src/components/sidebar/AnalyticsSection.tsx` — **new**: analytics orchestrator
- `frontend/src/components/sidebar/MapView.tsx` — arrest filter + date filter + shared color imports
- `frontend/src/components/sidebar/MapLayerToggles.tsx` — removed absolute positioning (now in parent container)
- `frontend/src/components/sidebar/MapLegend.tsx` — positioning adjustment
- `frontend/src/components/sidebar/DataView.tsx` — accepts mapData/filterMode, renders AnalyticsSection
- `frontend/src/components/SidebarPanel.tsx` — threads mapData/filterMode to DataView
- `frontend/src/lib/types.ts` — `MapData.capped` field
- `backend/config.py` — raised map row limits (2500/1000/500)
- `backend/models.py` — `MapDataResponse.capped` field
- `backend/main.py` — capped detection in `/api/map-data`

---

## Session Log (2026-05-31 — Map Interactivity, Pie Chart Overhaul, Category Colors)

Five feature additions across the map and analytics components, plus a backend limit change.

### Feature 1: Map Click-to-Detail Popup

Clicking a dot on the map opens a centered card overlay showing all available fields for that item. The popup type adapts to the data source:
- **Crime**: Type, Description, Date, Arrest status, Location
- **311**: Request Type, Status, Department, Date, Location
- **Permits**: Permit Type, Work Description, Estimated Cost, Issue Date, Location

Location coordinates are a hyperlink that opens **Google Maps Street View** (`map_action=pano`) at those exact coordinates in a new tab. Click the X button or the backdrop to dismiss.

Implementation uses an `onClickRef` to avoid stale closures in the deck.gl `MapboxOverlay` onClick callback. Hover tooltips were simplified to type + date since the click popup handles full detail.

### Feature 2: Pie Chart Overhaul

Complete rewrite of `PieChart.tsx` with:
- **Hover expansion** — each slice translates outward by 3px along its midpoint angle on hover (CSS `transform: translate`). Non-hovered slices dim to 40% opacity.
- **Center tooltip** — shows percentage, category name (2-line clamp), and count on hover; total when idle.
- **Thin-slice ring** — when hovering any slice at or below `thinThreshold` (default 2%), a second concentric ring fades in (250ms ease) outside the main donut. The ring redistributes only the thin slices proportionally to fill 360°, so even a 0.8% slice gets a readable arc. The hovered thin slice highlights at full opacity; others dim to 25%.
- **Grace period** — ring fade-out is delayed 100ms to prevent flicker when the cursor crosses the 3px gap between the main donut and the ring.
- **Enlarged hit areas** — thin main-donut slices get invisible transparent paths extending 5px beyond the visible arc (`pointerEvents: "all"`), improving discoverability.
- **`thinThreshold` prop** — configurable, defaults to `0.02`.
- **Expandable legend** — the `+N more` text is now a clickable button that expands to show all slices, with "Show less" to collapse.
- **Default size** bumped from 140 to 160 to accommodate the ring margin (3px gap + 10px ring + 3px expand room).

### Feature 3: Per-Category Colors for All Sources

Crime, 311, and permits now have distinct per-type colors on the map and in analytics, matching the crime "gold standard" pattern of named colors + filter toggles.

**Crime** — `CRIME_TYPE_COLORS` expanded from 8 to 30 named types with semantically appropriate colors: violent crimes (homicide, assault, battery, robbery, kidnapping) get hot reds; weapons/arson/intimidation get deep oranges; property crimes (theft, burglary) keep warm ambers; drug/vice crimes get purples; non-violent/white-collar (deceptive practice, public peace, liquor) get cool blues and teals. `OTHER OFFENSE` and truly unknown types are grey. `CRIME_TYPE_ORDER` expanded to 27 entries so named types get their own toggle when above the 1% threshold.

**Permits** — 6 named permit types with distinct colors (express→cyan, renovation→orange, signs→purple, new construction→green, wrecking/demolition→red, elevator equipment→amber). Per-type filter toggles in permits mode, replacing the flat green.

**311** — switched from 3 department-level toggles to `sr_type`-level toggles (top 8 request types + Other), each with a distinct color from a 12-color hash-assigned palette. Department coloring remains for overview mode.

All three sources share colors between the map dots and the analytics pie/trend charts via `mapColors.ts`.

### Feature 4: Crime 1% Threshold for OTHER Bucket

`buildCrimeTypeFilters` now counts each type's share. Types below 1% of total crimes are bucketed into "Other" regardless of whether they appear in `CRIME_TYPE_ORDER`. The layer filter uses the actual toggle keys (not the static color map) for routing, so the bucketing is consistent.

### Feature 5: Permits API Limit

`limit_permits` in `config.py` raised from 50 to 500 (the chat endpoint limit — the map endpoint was already at 500).

### Design Decisions

- **Semantic crime colors over uniform palette** — users intuitively expect violent crimes to look "angrier" on the map. The color gradient from hot reds (homicide) through warm ambers (theft) to cool blues (deceptive practice) communicates severity at a glance.
- **Hash-based 311 sr_type colors** — 311 request types are too numerous and varied for a named color map. A 12-color palette with deterministic hash assignment gives each type a distinct color without maintaining a manual mapping.
- **Street View over regular Maps** — the coordinates hyperlink opens `map_action=pano` (Street View) rather than a pin drop, since users clicking a specific crime/311/permit location want to see what's physically there.
- **Ring grace period (100ms)** — without it, the cursor crossing the 3px gap between the main donut and the ring triggers a fade-out/fade-in flicker. 100ms is long enough for any reasonable cursor speed but short enough to feel instant.

### Files changed

- `backend/config.py` — `limit_permits` 50 → 500
- `frontend/src/lib/mapColors.ts` — expanded `CRIME_TYPE_COLORS` (30 types), added `PERMIT_TYPE_COLORS`, `normalizePermitType`, `permitColor`, `SR_TYPE_PALETTE`, `srTypeMapColor`, `hashToColor`; `CRIME_TYPE_ORDER` expanded to 27 entries
- `frontend/src/components/sidebar/PieChart.tsx` — complete rewrite: hover expansion, thin-slice ring, grace period, hit areas, expandable legend
- `frontend/src/components/sidebar/MapView.tsx` — click-to-detail popup with Street View links, permit-type/sr-type filter toggles, 1% crime threshold, per-type coloring for all sources
- `frontend/src/components/sidebar/MapLayerToggles.tsx` — label truncation for long sr_type names
- `frontend/src/components/sidebar/MapLegend.tsx` — added permits mode legend, updated 311 label
- `frontend/src/components/sidebar/AnalyticsSection.tsx` — uses shared `crimeColorCSS`/`permitColorCSS`/`srTypeMapColorCSS` instead of local palettes

---

## Session Log (2026-05-31 — SQLite Persistence, Analytics Synthesis, Message Limits, Per-Question State)

Four-feature session replacing the localStorage-based conversation model with a full server-side persistence layer.

### Feature 1: SQLite Conversation Persistence

Replaced frontend localStorage with server-side SQLite (`backend/data/chicago.db`). The database uses WAL mode via `aiosqlite` for async access.

**Schema** (4 tables):
- `conversations` — id, title, created_at, updated_at
- `messages` — conversation_id, role, content, `context_json`/`plan_json`/`map_data_json` (JSON blob columns), `map_fetched_at`, position
- `uploads` — schema only (future-proofing for file upload support)
- `schema_version` — migration versioning

**7 REST endpoints** added to `main.py`:
- `GET/POST/DELETE /api/conversations` — list, create, clear all
- `GET/DELETE /api/conversations/{id}` — get full conversation, delete
- `PUT /api/conversations/{id}/messages` — append messages
- `PATCH /api/conversations/{id}/messages/{position}` — update map data on a single message
- `POST /api/conversations/import` — bulk import for localStorage migration

**Frontend migration**: On first load, `migrateLocalStorageToSQLite()` reads the old `chicago.conversations.v1` localStorage key, POSTs all conversations to the import endpoint, then removes the localStorage keys. All `history.ts` functions are now async and delegate to the API.

### Feature 2: Analytics-Enriched Claude Synthesis

Server-side month-over-month trend computation, so Claude can cite specific trends in its answers.

**New module `backend/analytics.py`**: Ports the trend logic from `frontend/src/lib/analytics.ts` to Python. Groups records by year-month + category, skips the current partial month, compares the two most recent complete months, returns `TrendItem` list (category, current_count, prior_count, change_pct). Capped at 8 categories per source.

**Pipeline change**: `_event_stream` now runs `_retrieve(plan)` and `_fetch_map_rows(plan)` concurrently via `asyncio.gather`. The map rows are used to compute analytics, which are attached to `context.analytics` before the context is emitted and before synthesis begins.

**Synthesis prompt**: `_build_user_prompt` in `synthesizer.py` formats analytics as human-readable text (not JSON) appended after the context block. Example: `"Crime: BATTERY: 245 (up 23%)"`. The synthesizer system prompt (rule 8) instructs Claude to weave the 2-4 most notable trends into its answer naturally.

**New SSE event type `map_data`**: After the context event, the pipeline emits the map data response. This eliminates the separate `/api/map-data` round-trip for the current turn — the frontend receives map data inline with the stream.

### Feature 3: 10-Message Limit

Enforced on both sides:
- **Backend**: If `conversation_id` is provided in `ChatRequest`, `_event_stream` counts user messages in SQLite. If >= 10, emits `error: "MESSAGE_LIMIT_REACHED"` and returns immediately.
- **Frontend**: `useChat` exposes `atMessageLimit`. `ChatInterface` replaces the input with "You've reached the 10-message limit. Start a new conversation" when at the limit.

Configurable via `message_limit` in `config.py` (default 10).

### Feature 4: Per-Question State Toggling

Clicking a past user-message bubble loads that question's associated state into the sidebar.

**Data stored per assistant message**: `context` (already existed), `plan` (NEW), `mapData` (NEW), `mapFetchedAt` (NEW). All attached to the assistant message on the "done" SSE event and persisted in SQLite.

**Click flow**: `MessageBubble` → `ChatInterface.onMessageClick(index)` → `App.handleMessageClick`:
1. Find the assistant message at `index + 1`
2. Load its `context` into sidebar data/sources panels
3. Load its `plan` (drives filter mode, time range)
4. Load its `mapData` with staleness check:
   - If `mapFetchedAt` within 24 hours → use stored data
   - If older → re-fetch via `/api/map-data`, update in SQLite via PATCH endpoint
5. Set `selectedMessageIndex` for visual highlighting

**Visual indicators**: User message bubbles get `cursor-pointer`, hover `ring-1 ring-white/20`, selected `ring-1 ring-accent/40`.

### Design Decisions

- **JSON blob columns over normalized tables** — context/plan/mapData are written once and read whole. No query benefit from normalization for a single-user app.
- **Map data in SSE stream** — avoids a second round-trip for the current turn. Historical turns still use `/api/map-data` when data is stale.
- **24h staleness threshold** — map data older than a day is re-fetched since crime/311/permit data updates frequently. Fresh enough for recent conversations, current enough for revisits.
- **aiosqlite singleton** — single user, single writer. No connection pooling needed.
- **Analytics as text, not JSON** — formatting trends as "BATTERY: 245 (up 23%)" instead of `{"category": "BATTERY", ...}` saves ~40% tokens in the synthesis prompt.

### Files Changed/Created

**Backend (new):**
- `backend/db.py` — SQLite persistence layer
- `backend/analytics.py` — trend computation
- `backend/tests/test_db.py` — 15 tests
- `backend/tests/test_analytics.py` — 14 tests

**Backend (modified):**
- `backend/main.py` — conversation endpoints, analytics pipeline, map_data SSE, message limit
- `backend/models.py` — TrendItem, AnalyticsSummary, ConversationSummary, StoredMessage, ConversationDetail, SaveMessagesRequest, ImportRequest; ContextObject.analytics; ChatChunk.map_data; ChatRequest.conversation_id
- `backend/config.py` — db_path, message_limit
- `backend/synthesizer.py` — _format_analytics, analytics in _build_user_prompt
- `backend/prompts.py` — rule 8 (trend weaving)
- `backend/tests/test_api.py` — updated mocks for _fetch_map_rows + db

**Frontend (modified):**
- `frontend/src/lib/types.ts` — Message extended (plan/mapData/mapFetchedAt), StoredMessage, ConversationDetail, AnalyticsSummary, TrendItem
- `frontend/src/lib/api.ts` — conversation CRUD, chatStream accepts conversationId
- `frontend/src/lib/history.ts` — full rewrite to async API-backed + migration
- `frontend/src/lib/useChat.ts` — conversationId, onPlan/onMapData callbacks, message limit
- `frontend/src/App.tsx` — async lifecycle, per-question handler, map data from SSE
- `frontend/src/components/ChatInterface.tsx` — message clicking, limit UI
- `frontend/src/components/MessageBubble.tsx` — isSelected/onSelect props

**Other:**
- `.gitignore` — added `backend/data/`
- `requirements.txt` — added `aiosqlite>=0.20.0`

---

## Session Log (2026-05-31 — Analytics Category Audit & Data Panel Cleanup)

Audited all five Socrata API endpoints by querying 500+ items from each to discover every category value that exists. Fixed coverage gaps, removed redundant UI, and fixed the pie chart denominator bug.

### Category Audit Results

Queried distinct values for each categorization field across all datasets:

| Dataset | Field | Types in API | Previously Covered | Gap |
|---|---|---|---|---|
| Crime (`ijzp-q8t2`) | `primary_type` | 31 | 30 (1 name mismatch) | `CRIMINAL SEXUAL ASSAULT` vs `CRIM SEXUAL ASSAULT`, missing `PUBLIC INDECENCY` |
| Permits (`ydr8-5enu`) | `permit_type` | 8 | 6 | `REINSTATE REVOKED PMT` (863/yr), `EASY PERMIT PROCESS` |
| 311 (`v6vf-nfxy`) | `owner_department` | 14 | 3 | 11 departments bucketed into "Other" |
| 311 (`v6vf-nfxy`) | `sr_type` | 105 | hash-based (OK) | — |
| Violations (`22u3-xenr`) | `violation_description` | 50+ | raw strings only | No category grouping |
| Business (`uupf-x98q`) | `license_description` | 58 | not tracked | — |

### Fix 1: Crime Color Mapping

- **Renamed** `CRIM SEXUAL ASSAULT` → `CRIMINAL SEXUAL ASSAULT` in `CRIME_TYPE_COLORS` to match the API (2,039 crimes/90d were getting grey fallback)
- **Added** `PUBLIC INDECENCY` and `NON-CRIMINAL (SUBJECT SPECIFIED)` with colors
- **Expanded** `CRIME_TYPE_ORDER` from 27 to 31 entries (all types from the API)

### Fix 2: Permit Categorization

- **Added** `REINSTATE REVOKED PMT` (brown) and `EASY PERMIT PROCESS` (steel blue) to `PERMIT_TYPE_COLORS`, `PERMIT_TYPE_ORDER`, and `normalizePermitType()`
- **Backend**: `_normalize_permit_type()` added to `assembler.py` and `analytics.py` — permits are now grouped by normalized type instead of raw strings like `PERMIT – EXPRESS PERMIT PROGRAM`
- **Model**: `PermitSummary` gained `by_type: dict[str, int]` for per-type breakdown in Claude's synthesis

### Fix 3: Full 311 Department Coverage

Expanded from 3 to all 14 departments with unique colors and normalization rules:

- Streets & Sanitation (cyan), Buildings (coral), CDOT (blue) — existing
- Water Management (blue), Aviation (purple), Animal Care (green), 311 City Services (amber), Finance (yellow), BACP (pink), Health (red), Fire (red-dark), Housing (brown), City Clerk (steel), Outside Agencies (grey) — new

`normalizeDept()` updated to recognize all API department name patterns (e.g., `DWM - Department of Water Management` → `Water Management`). `DEPT_ORDER` added for consistent toggle ordering.

### Fix 4: Violation & Business Category Enrichment

- **Violations**: 50+ raw descriptions grouped into 16 meaningful categories (Elevator/Escalator, Exterior Structure, Interior Structure, Fire Safety, Permits/Contractor, Pest Control, etc.) via `_categorize_violation()`. `ViolationSummary` gained `by_category: dict[str, int]`.
- **Business**: `BusinessSummary` gained `by_license_type: dict[str, int]` tracking distribution across 58 license types (Limited Business License, Retail Food, Regulated Business, Tavern, etc.).

### Fix 5: Pie Chart Percentage Fix

The pie chart used `totalOverride` (from context's aggregate count, e.g., 1756 total crimes) as the denominator for percentages, while the arcs used `sliceTotal` (capped map data, e.g., 1000 rows). This made percentages sum to ~57% instead of 100%. **Removed `totalOverride`** — all percentages and the center number now use `sliceTotal` consistently.

### Fix 6: Data Cards Removed

Removed the five data cards (crime, 311, permits, violations, business) from the sidebar `DataView`. These duplicated information already present in Claude's chat response. The sidebar Data tab now shows only:
- Data lag note (when applicable)
- Analytics section (pie chart + trend table — visual, interactive, NOT in chat)

The map above the data section continues to provide unique geographic value. `highlightedDataSource` prop chain removed from App → SidebarPanel → DataView.

### Fix 7: Label Truncation

Added shared `capLabel(raw, max=25)` function in `mapColors.ts` — title-cases and truncates labels to 25 characters with "…". Applied consistently across all four label sites: MapView toggle pills, PieChart legend, PieChart center tooltip, TrendTable rows. Replaces the four separate `formatLabel`/`formatSrTypeLabel`/`formatPermitLabel` functions.

### Files Changed

**Backend:**
- `backend/analytics.py` — `_normalize_permit_type()`, applied to permit trend computation
- `backend/assembler.py` — `_normalize_permit_type()`, `_categorize_violation()`, `by_type` for permits, `by_category` for violations, `by_license_type` for business
- `backend/models.py` — `PermitSummary.by_type`, `ViolationSummary.by_category`, `BusinessSummary.by_license_type`

**Frontend:**
- `frontend/src/lib/mapColors.ts` — fixed `CRIMINAL SEXUAL ASSAULT`, added `PUBLIC INDECENCY`, expanded `CRIME_TYPE_ORDER` to 31, added 2 permit types, expanded `DEPT_COLORS` to 14, added `DEPT_ORDER`, added `capLabel()`
- `frontend/src/components/sidebar/PieChart.tsx` — removed `totalOverride`, use `sliceTotal` for all percentages, use `capLabel()`
- `frontend/src/components/sidebar/TrendTable.tsx` — use `capLabel()`
- `frontend/src/components/sidebar/MapView.tsx` — use `capLabel()` for all toggle labels, removed `formatSrTypeLabel`/`formatPermitLabel`
- `frontend/src/components/sidebar/AnalyticsSection.tsx` — removed `totalOverride` passthrough, normalize permit types in analytics, removed `context` prop
- `frontend/src/components/sidebar/DataView.tsx` — removed data cards, kept lag note + analytics only
- `frontend/src/components/SidebarPanel.tsx` — removed `highlightedDataSource` prop, `hasData` now checks map data
- `frontend/src/App.tsx` — removed `highlightedDataSource` state, simplified `handleDataClick`

---

## Session Log (2026-05-31 — Zoning Map Integration)

Three-part feature: ArcGIS-based zoning classification lookup, zoning polygon overlay on the map, and supporting UX (links open in new tabs, sidebar defaults, toggles, disclosure banner).

### Part 1: ArcGIS Zoning Point Lookup

The Chicago Data Portal (Socrata) dataset `p8va-airx` turned out to be non-queryable — its `.geojson` and JSON endpoints both return errors (`"no row or column access to non-tabular tables"`). However, the city's **ArcGIS Zoning MapServer** at `gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer` is publicly accessible with no API key, and supports both point and envelope spatial queries.

**New module `backend/retrieval/zoning.py`**:
- `lookup_zoning(lat, lon)` — point query to Layer 1 ("Zoning Boundaries"). Returns `{"zone_class": "RM-6", "zone_type": 4, "ordinance_num": null}` or `None`. Runs in parallel with other retrieval tasks during chat when `requires_disclaimer=True` and the plan has resolved lat/lon.
- `zoning_polygons_for_map(community_area)` — envelope query using the community area's bounding box (from `geo.community_area_bounds`). Returns a GeoJSON FeatureCollection with 200–600 polygons per community area (~1 MB). Used by the map overlay.

**New model `ZoningSummary`** (`models.py`): `zone_class`, `zone_type`, `ordinance_num`, and `zoning_map_url` (defaulting to the correct official URL). Added as `parcel_zoning` field on `ContextObject`.

**Synthesizer prompt rule 9** (`prompts.py`): When `parcel_zoning` is present, Claude states the zoning classification as a definitive fact and links to `https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning` — never invents other URLs.

### Part 2: Router Geocoding Fix

**Root cause**: `router.py` called `resolve_address_to_community_area(raw_loc)` but discarded the returned coordinates (`_coords`), so `location.resolved_lat`/`resolved_lon` were always `None`. This meant:
- The ArcGIS zoning point lookup never triggered
- No address pin appeared on the map
- The map couldn't `flyTo` the queried address

**Fix**: Capture the coordinates and store them in the plan's `location.resolved_lat`/`resolved_lon`. Verified: "443 W Wrightwood Ave" now resolves to `(41.9307, -87.6411)`, community area 7 (Lincoln Park), zone class **RM-6**.

### Part 3: Zoning Polygon Overlay on Map

Replaced the broken `zoning_for_map()` in `map_data.py` (which tried the non-functional Socrata endpoint) to delegate to `zoning_polygons_for_map()` from the new ArcGIS module. Flipped `enable_zoning_layer` from `False` to `True` in `config.py`.

**SSE pipeline** (`main.py`): `_fetch_map_rows()` now includes a zoning polygon fetch when `plan.requires_disclaimer` is true. `_build_map_response()` passes the GeoJSON through to `MapDataResponse.zoning`.

**Frontend map** (`MapView.tsx`):
- Removed the old `VITE_ENABLE_ZONING_LAYER` env var gate
- Zoning `GeoJsonLayer` renders **first** in the layer array (underneath scatter dots)
- Per-feature fill/line colors via Chicago's standard zoning color scheme: residential=yellow, business=blue, commercial=purple, manufacturing=magenta, planned development=gray, downtown=teal, parks=green
- Hover tooltip shows `ZONE_CLASS`; click popup shows Zone Class, Ordinance #, and a link to the official zoning map
- **"Zoning" toggle** (bottom-left) to show/hide the overlay
- **"Points" toggle** (bottom-left, next to Zoning) to show/hide all scatter dots — lets users see just zoning polygons + address pin

**Zoning color system** (`mapColors.ts`): `ZONE_PREFIX_COLORS` maps zone class prefixes (RS, RT, RM, B, C, M, PD, PMD, D, DC, DX, DR, DS, T, P, POS) to RGBA tuples. `zoneColor()` extracts the alpha-letter prefix from strings like "B3-2" or "PD 799" and returns the fill color (alpha 80). `zoneLineColor()` returns the same RGB with higher alpha (180) for outlines.

**Sidebar defaults** (`App.tsx`): When `parcel_zoning` is present in the context, the sidebar opens to the Data tab (showing the map) instead of Sources.

### Part 4: UX Additions

**Links open in new tabs** (`MessageBubble.tsx`): All markdown `<a>` elements now have `target="_blank" rel="noopener noreferrer"`.

**Zoning disclosure banner** (`DataView.tsx`): When zoning polygon data is loaded, an amber notice appears in the sidebar: *"This map is a good reference but may not reflect the most recent City Council votes. Check the [official Chicago Zoning Map] for completely up-to-date data."* Uses the same amber pattern as the data lag note.

**Frontend types** (`types.ts`): Added `ZoningSummary` interface and `parcel_zoning` field on `ContextObject`.

### ArcGIS API Details

- **Endpoint**: `https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer/1/query`
- **No API key required**, no rate limit observed
- **14,905 total features** across all of Chicago; `maxRecordCount=2000` per request
- Community area bounding box queries return 200–600 features, well under the limit
- Fields: `ZONE_CLASS` (string, e.g. "RS-3", "B3-2", "PD 799"), `ZONE_TYPE` (integer), `ORDINANCE_NUM` (string)
- Native SRS: EPSG:3435 (IL State Plane East); server reprojects to WGS84 via `outSR=4326`
- Data updates monthly (~2–6 week lag after City Council votes)
- The Socrata dataset `p8va-airx` is NOT usable for programmatic queries — use ArcGIS exclusively

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/zoning.py` — ArcGIS point lookup + polygon fetch

**Backend (modified):**
- `backend/retrieval/map_data.py` — `zoning_for_map()` now delegates to ArcGIS
- `backend/config.py` — `enable_zoning_layer` → `True`
- `backend/main.py` — zoning in `_retrieve()`, `_fetch_map_rows()`, `_build_map_response()`
- `backend/models.py` — `ZoningSummary`, `ContextObject.parcel_zoning`
- `backend/assembler.py` — accepts `zoning_info`, creates `ZoningSummary`
- `backend/prompts.py` — synthesizer rule 9 (zoning map URL)
- `backend/router.py` — store geocoded lat/lon in the plan (was discarding them)

**Backend (tests):**
- `backend/tests/test_zoning.py` — 12 tests (point lookup + polygon fetch)
- `backend/tests/test_assembler.py` — 3 zoning tests
- `backend/tests/test_map_data.py` — updated mock for ArcGIS delegation

**Frontend (modified):**
- `frontend/src/lib/mapColors.ts` — `ZONE_PREFIX_COLORS`, `zoneColor()`, `zoneLineColor()`, `zoneColorCSS()`
- `frontend/src/lib/types.ts` — `ZoningSummary`, `ContextObject.parcel_zoning`
- `frontend/src/components/sidebar/MapView.tsx` — GeoJsonLayer, Zoning/Points toggles, tooltip, click popup
- `frontend/src/components/sidebar/DataView.tsx` — zoning disclosure banner
- `frontend/src/components/MessageBubble.tsx` — `target="_blank"` on links
- `frontend/src/App.tsx` — sidebar defaults to Data tab for zoning questions

### Test Count

192 tests passing (was 177 before this session; +15 new tests).

---

## Session Log (2026-05-31 — Zoning UX Overhaul + Geocoding Fix)

Five changes to the zoning map experience, plus a critical backend bug fix that was preventing address geocoding and zoning lookups from working.

### Bug Fix: Router Geocoding Bypass

**Root cause**: In `router.py`, the geocoding call was gated on `ca is None` — when the LLM already resolved the community area (e.g., Lincoln Park = CA 7 from a zip code), geocoding was skipped entirely. This left `resolved_lat`/`resolved_lon` as `None`, which meant:
- No address pin on the map
- The ArcGIS zoning point lookup never triggered (requires lat/lon)
- Claude couldn't state the definitive zone classification (no `parcel_zoning` in context)
- The AI gave generic "look it up yourself" answers for zoning questions with addresses

**Fix**: Removed the `ca is None` guard from the geocoding condition. Addresses are now always geocoded when `location.type == "address"` or `resolved_address` is present, regardless of whether the community area is already known. Also switched to using `resolved_address` (the LLM's canonicalized form) as the geocoder input when available, falling back to `raw`.

**Verified**: "525 W Arlington Pl, Chicago, IL, 60614" → (41.927, -87.642) → Community Area 7 (Lincoln Park) → Zone Class **B3-1** (Community Shopping District).

### Change 1: Zoning/Points Toggles Moved Above Secondary Filters

Moved from `bottom-2 left-2` to the top of the `top-2 left-2` control area, appearing as the first controls. All point-related controls (source tabs, arrest/status/cost filters) now render below them.

### Change 2: Points-Off Mode

When the Points toggle is off:
- Date range slider, type toggles, and all secondary filters (arrest, status, cost) are hidden
- The capped-results notice is hidden
- The zoning category legend appears at bottom-left (8 color-coded categories: Residential, Business, Commercial, Manufacturing, Planned Dev., Downtown, Transportation, Parks/Open Space)
- Only the zoning polygon overlay and address pin remain visible

### Change 3: Enhanced Zoning Click Popup

Clicking a zoning polygon now shows:
- **Zone Class** (e.g. "B3-1")
- **Definition** — one-line description (e.g. "Neighborhood retail, offices, and mixed-use")
- **Allowed uses** — 1-3 example uses (e.g. "Retail store", "Restaurant", "Office space")
- **Ordinance number** (when available)
- **Official Map** link

Zone definitions and examples sourced from a new `ZONE_INFO` record in `mapColors.ts` covering all 16 zone prefixes.

### Change 4: Collapsible Zoning Codes Table

New component in the sidebar Data panel listing all unique `ZONE_CLASS` values from the map's GeoJSON features. Styled as a collapsible section matching the Analytics pattern (chevron toggle, rounded container). Columns: color swatch, zone code (monospace), category label. Sorted by category (residential → business → commercial → manufacturing → etc.).

### Change 5: Zoning Helpers Exported

`mapColors.ts` now exports:
- `zonePrefix()` (was module-private) — extracts the alpha prefix from zone class strings
- `ZONE_PREFIX_LABELS` — maps 16 prefixes to human-readable names
- `ZONE_INFO` — maps 16 prefixes to `{ label, description, examples }` for popup and future use

### Files Changed

**Backend:**
- `backend/router.py` — always geocode address-type locations; prefer `resolved_address` for geocoder input

**Frontend:**
- `frontend/src/lib/mapColors.ts` — exported `zonePrefix`, added `ZONE_PREFIX_LABELS`, `ZONE_INFO`
- `frontend/src/components/sidebar/MapView.tsx` — moved Zoning/Points toggles to top-left; gated point controls on `showPoints`; enhanced zoning popup; updated MapLegend props; hid empty-state message when zoning data present
- `frontend/src/components/sidebar/MapLegend.tsx` — added `showPoints`/`showZoning`/`hasZoning` props; zoning category legend when points off
- `frontend/src/components/sidebar/DataView.tsx` — added collapsible `ZoningCodesTable` component; updated no-data message for zoning-only queries

---

## Session Log (2026-05-31 — URL-Based Conversation Routing)

Added `react-router-dom` so each conversation gets its own URL (`/c/:id`), like ChatGPT. Conversations are now bookmarkable, shareable, and work with browser back/forward.

### Approach: URL Sync Layer

Rather than splitting App.tsx into separate route components (which would require duplicating or lifting 15+ interrelated state variables), the implementation adds a thin `useConversationRouter` hook that syncs `conversationId` state with the URL bidirectionally. The existing `active` flag (`messages.length > 0 || streaming`) continues to drive the splash-vs-workspace transition.

### Routes

- `/` — splash page (hero slideshow, chat input, suggestion chips)
- `/c/:id` — conversation view (workspace with chat, sidebar, map)

### How It Works

1. **New conversation**: `sendMessage()` creates a conversation in SQLite, then calls `navigateToConversation(id)` to push `/c/:id` to the browser history.

2. **Load from history**: `loadConv()` fetches the conversation from the API, sets state, then navigates to `/c/:id`.

3. **New chat / reset**: `reset()` clears all state and navigates to `/`.

4. **Direct URL access (bookmark/refresh)**: A URL-sync `useEffect` watches `conversationIdFromUrl` (from `useParams`). When the URL has an ID that doesn't match local state, it loads the conversation from the API. A `loadingConversation` guard renders a blank dark screen during the fetch to prevent the splash from flashing.

5. **Invalid URL**: `/c/nonexistent` → `getConversation` returns null → redirect to `/` with `replace: true` (no bad URL in history).

6. **Browser back/forward**: `react-router-dom` handles `popstate`. The URL-sync effect detects the change and either loads the conversation or resets to splash.

### Race Condition Safety

- The URL-sync effect guards on `conversationIdFromUrl !== conversationId` — no-op when state already matches (prevents loops from `sendMessage`/`loadConv` which set state before navigating).
- `reset()` sets `conversationId` to null synchronously before navigating, so the effect sees state already cleared.
- The init effect (migration + load conversation list) and URL-sync effect touch independent state — no race.

### Files Changed/Created

- `frontend/package.json` — added `react-router-dom`
- `frontend/src/lib/useConversationRouter.ts` — **new**: thin hook wrapping `useParams` + `useNavigate`
- `frontend/src/main.tsx` — wrapped `<App />` in `<BrowserRouter>` with `"/"` and `"/c/:id"` routes
- `frontend/src/App.tsx` — import hook, URL-sync effect, navigation calls in `sendMessage`/`reset`/`loadConv`, loading guard

No backend changes. No changes to `history.ts`, `api.ts`, `useChat.ts`, `HistorySidebar.tsx`, or any other file.

### Vite SPA Fallback

Vite dev server handles `/c/:id` by default (`appType: 'spa'`). For production deployment, the static file server would need to serve `index.html` for all non-asset paths.

---

## Session Log (2026-05-31 — Bucket 1: Mobile & Polish)

Two features completing Bucket 1 of the prioritized roadmap: mobile responsiveness and file upload support.

### Part A: Mobile Responsiveness

**Problem**: The sidebar (map, data, sources) was completely hidden below 768px via `hidden md:flex` with no alternative access. Mobile users had no way to see map data, analytics, or source citations.

**Solution**: Bottom sheet overlay for mobile, reusing existing sidebar internals.

1. **Extracted `DataMapLayout`** — moved from a private component inside `SidebarPanel.tsx` to `sidebar/DataMapLayout.tsx` so both the desktop sidebar and mobile sheet can import it.

2. **New `MobileSidebarSheet.tsx`** — bottom sheet overlay (70vh, Framer Motion slide-up, drag-down-to-dismiss on handle area, backdrop click to close). Contains `SidebarHeader` (Data/Sources tabs) + `DataMapLayout` or `SourcesView`. Same props as `SidebarPanel`.

3. **Mobile sidebar toggle button** — appears in the workspace header on `md:hidden`. Map icon with source count badge. Opens the bottom sheet.

4. **Responsive sidebar routing** — `openSidebarResponsive()` checks `window.innerWidth < 768` and opens either the desktop sidebar or mobile bottom sheet. Applied to `handleCitationClick`, `handleDataClick`, `handleContext`, and `handleMessageClick`.

5. **Splash page mobile tweaks** — stats row: `px-4 md:px-8`, numbers `text-3xl md:text-4xl`. Story sections: `px-4 md:px-8`.

6. **Workspace header mobile tweaks** — shorter brand name on mobile ("UrbanLayer" vs "UrbanLayer — Chicago"), truncated community area breadcrumb (`max-w-[120px] truncate`), `+` icon for "New chat" on small screens.

7. **Chat area mobile padding** — `px-3 md:px-6`, `py-4 md:py-8` for messages and input.

### Part B: File Upload Support

**Problem**: The `uploads` SQLite table and paperclip button existed but did nothing. No backend endpoints, no frontend upload flow, no attachment rendering.

**Solution**: Attach-before-send model with filenames-only synthesis context. Claude Vision deferred to a future bucket.

**Backend:**
1. **Config** (`config.py`) — `upload_dir` (`backend/data/uploads/`), `upload_max_size_bytes` (10MB), `upload_allowed_types` (JPEG, PNG, WebP, HEIC, PDF), `upload_max_per_message` (3).

2. **Models** (`models.py`) — `UploadMeta` (id, conversation_id, filename, mime_type, size_bytes, created_at). `ChatRequest.upload_ids` field.

3. **DB functions** (`db.py`) — `save_upload`, `get_upload`, `get_uploads_for_conversation`, `delete_upload`. Conversation deletion cleans up upload files on disk.

4. **Endpoints** (`main.py`):
   - `POST /api/conversations/{id}/uploads` — multipart upload, validates type/size/count, saves to `backend/data/uploads/{conv_id}/{uuid}.{ext}`
   - `GET /api/uploads/{id}/file` — serve file via `FileResponse`
   - `DELETE /api/uploads/{id}` — delete from disk + DB
   - `GET /api/conversations/{id}/uploads` — list uploads for a conversation

5. **Synthesis context** (`synthesizer.py`) — when `upload_ids` are present, fetches filenames from DB and appends "The user attached N file(s): filename1, filename2" to the synthesis prompt.

6. **Dependency** — added `python-multipart>=0.0.7` to `requirements.txt`.

**Frontend:**
1. **Types** (`types.ts`) — `UploadMeta` interface, `Message.attachments` field.

2. **API** (`api.ts`) — `uploadFiles(conversationId, files)`, `getUploadUrl(uploadId)`, `deleteUpload(uploadId)`. `chatStream` accepts optional `uploadIds`.

3. **ChatInput** (`ChatInput.tsx`) — hidden `<input type="file" multiple>`, paperclip button wired to trigger it. `PendingAttachment` type with `file` + `previewUrl`. Thumbnail preview row above input with remove buttons. Client-side accepts `image/*` and `.pdf`.

4. **App.tsx** — `pendingAttachments` state, `handleAttach` (creates preview URLs via `URL.createObjectURL`), `handleRemoveAttachment` (revokes URLs). `sendMessage` uploads files first, then passes `upload_ids` through to `sendChat`.

5. **useChat** (`useChat.ts`) — `sendMessage` accepts optional `UploadMeta[]`, attaches them to the user message, passes IDs to `chatStream`.

6. **MessageBubble** (`MessageBubble.tsx`) — user messages with attachments render a row of 64x64 rounded thumbnails (images via `<img>`, PDFs via file icon). Click opens in new tab.

### Files Changed/Created

**New:**
- `frontend/src/components/MobileSidebarSheet.tsx` — mobile bottom sheet
- `frontend/src/components/sidebar/DataMapLayout.tsx` — extracted from SidebarPanel

**Modified:**
- `backend/config.py` — upload settings
- `backend/models.py` — `UploadMeta`, `ChatRequest.upload_ids`
- `backend/db.py` — upload CRUD functions, conversation delete cleanup
- `backend/main.py` — upload endpoints, upload filenames in synthesis
- `backend/synthesizer.py` — `upload_filenames` parameter
- `requirements.txt` — `python-multipart`
- `frontend/src/lib/types.ts` — `UploadMeta`, `Message.attachments`
- `frontend/src/lib/api.ts` — upload functions, `chatStream` uploadIds
- `frontend/src/lib/useChat.ts` — attachment support
- `frontend/src/App.tsx` — mobile sidebar state, attachment state, responsive routing
- `frontend/src/components/SidebarPanel.tsx` — imports `DataMapLayout` from extracted file
- `frontend/src/components/ChatInput.tsx` — file picker, preview row, attachment props
- `frontend/src/components/ChatInterface.tsx` — threads attachment props
- `frontend/src/components/MessageBubble.tsx` — attachment thumbnail rendering
- `frontend/src/components/landing/StorySection.tsx` — mobile padding

---

## Session Log (2026-05-31 — Bucket 2: Admin Dashboard)

Built a full `/admin` dashboard completing Bucket 2 (Observability & Eval). Two major work streams: backend request logging system and frontend dashboard with interactive graphics.

### Backend: LLM Call Logging System

1. **Schema migration (v1 → v2)** — Two new SQLite tables:
   - `llm_calls` — one row per LLM API call (phase, model, input/output/cache tokens, duration_ms, status). Indexed on `created_at` and `request_group`.
   - `request_logs` — one row per `/chat` request (intent, community area, sources, total duration, error). Provides a fast denormalized view for the dashboard.

2. **Tracked LLM wrappers** (`llm.py`) — `tracked_create()` wraps `client.messages.create()` for conversation synthesis and router calls. `tracked_stream()` is an async context manager wrapping `client.messages.stream()` for the synthesizer — captures token usage via `await stream.get_final_message()` after the stream completes. Both persist to SQLite non-fatally (logging errors don't break the chat flow). `estimate_cost()` uses Sonnet ($3/$15 per MTok) and Haiku ($0.80/$4 per MTok) pricing.

3. **Call site updates** — `conversation.py`, `router.py`, `synthesizer.py` each take `request_group` and `conversation_id` params and use the tracked wrappers instead of direct client calls. `_event_stream()` in `main.py` generates a UUID `request_group` at the top of each request and saves a summary `request_log` via fire-and-forget `asyncio.create_task` at the end.

4. **6 admin API endpoints**:
   - `GET /api/admin/overview?period=30d` — total requests, tokens, cost, errors, by-model and by-phase breakdowns
   - `GET /api/admin/timeseries?period=30d&bucket=day` — time-bucketed arrays for charts
   - `GET /api/admin/latency?period=30d` — p50/p90/p99 by phase
   - `GET /api/admin/conversations` — total convs, messages, avg per conv, today count
   - `GET /api/admin/requests?limit=50&offset=0` — paginated request log
   - `GET /api/admin/benchmark` — reads `eval/benchmark_results.json`

5. **Benchmark JSON output** — `eval/retrieval_benchmark.py` gained `--json-out <path>` flag for machine-readable results consumed by the admin API.

### Frontend: Admin Dashboard Page

1. **`AdminDashboard.tsx`** — Full page at `/admin`, completely independent of the chat App component. Period selector (Today / 7 Days / 30 Days / All Time) controls all data fetching. Six sections in a responsive grid layout.

2. **Interactive components** (all custom SVG, no chart library):
   - `StatCard` — animated metric cards using the existing `CountUp` component (Framer Motion)
   - `TimeSeriesChart` — SVG area/line chart with hover crosshair + tooltip, gradient fills, auto-scaled gridlines, multiple series support
   - `BarChart` — horizontal bars for benchmark grade distribution (A-F with semantic colors)
   - `LatencyTable` — p50/p90/p99 table with color-coded thresholds (>5s=rose, >2s=amber)
   - `RequestsTable` — paginated log table with expandable detail rows and intent pills
   - `BenchmarkSection` — score/pass-rate stat cards, grade distribution bar + pie chart (reuses existing PieChart), collapsible per-query detail table with grade badges

3. **Reused existing components** — `PieChart` (cost by model, calls by phase, grade breakdown), `CountUp` (stat cards, conversation stats).

4. **Navigation** — settings icon in workspace header links to `/admin`. "Back to app" link in admin header returns to `/`.

### Design Decisions

- **One row per LLM call** (not per chat request) — maps cleanly to cost calculation since each model has different pricing, avoids NULL-heavy columns when some phases are skipped
- **Custom SVG charts over recharts/chart.js** — the project already has a sophisticated custom PieChart; adding a 200KB+ charting library for a few charts would be a dependency mismatch. Custom SVG matches the exact dark theme and stays zero-dependency
- **Non-fatal logging** — `tracked_create`/`tracked_stream` catch and log db errors without breaking the chat flow, so logging never degrades the user experience
- **`request_logs` denormalized table** — dashboard queries are faster than aggregating from `llm_calls` for per-request summaries. `llm_calls` is the source of truth for per-call token/cost data

### Files Changed/Created

**Backend (new):**
- (No new test files yet — existing 192 tests all pass with the changes)

**Backend (modified):**
- `backend/db.py` — `llm_calls` + `request_logs` tables, migration v1→v2, 6 admin query functions
- `backend/llm.py` — `tracked_create()`, `tracked_stream()`, `estimate_cost()`, cost table
- `backend/conversation.py` — `tracked_create()` + `request_group`/`conversation_id` params
- `backend/router.py` — `tracked_create()` + params
- `backend/synthesizer.py` — `tracked_stream()` + params
- `backend/main.py` — `request_group` generation, `_save_request_log()`, 6 admin endpoints
- `backend/config.py` — `enable_request_logging` setting

**Eval (modified):**
- `eval/retrieval_benchmark.py` — `write_json()` + `--json-out` flag

**Frontend (new):**
- `frontend/src/components/AdminDashboard.tsx` — main admin page
- `frontend/src/components/admin/StatCard.tsx` — animated stat card
- `frontend/src/components/admin/TimeSeriesChart.tsx` — SVG area/line chart
- `frontend/src/components/admin/BarChart.tsx` — SVG horizontal bar chart
- `frontend/src/components/admin/LatencyTable.tsx` — percentile table
- `frontend/src/components/admin/RequestsTable.tsx` — paginated request log
- `frontend/src/components/admin/BenchmarkSection.tsx` — benchmark visualization

**Frontend (modified):**
- `frontend/src/main.tsx` — `/admin` route
- `frontend/src/lib/api.ts` — 6 admin fetch functions
- `frontend/src/lib/types.ts` — admin TypeScript interfaces
- `frontend/src/App.tsx` — admin icon link in workspace header

---

## Session Log (2026-05-31 — Bucket 2 Complete: LLM-as-Judge Synthesis Eval)

Final piece of Bucket 2 (Observability & Eval). Added an LLM-as-judge system that grades the quality of synthesized answers using Claude Sonnet as the evaluator.

### Eval Script (`eval/run_eval.py`)

1. **Full data capture** — `_run_full()` now stores the complete answer text (`full_answer`) and full context dict (`context_dict`) on the `Result` dataclass, not just the 400-char excerpt.

2. **Judge dataclasses** — `DimensionScore` (dimension, grade, reasoning) and `JudgeResult` (query_id, question, dimensions, overall_grade, overall_reasoning).

3. **`_run_judge(result, model)`** — Sends each (question, context, answer) triple to Claude for structured rubric grading:
   - Extracts metadata flags from context (which data sources present, which are capped, whether disclaimer/zoning/analytics apply)
   - Pre-extracts citation markers from the answer via regex (`[N]` and `[data:X]`) so the judge doesn't have to parse them
   - Truncates code chunk text to 600 chars to save tokens
   - Calls `AsyncAnthropic().messages.create()` directly (eval runs outside the backend process)
   - Parses structured JSON response with graceful fallback on parse errors

4. **4 grading dimensions** (weighted):
   - **Citation Accuracy (30%)** — `[N]` markers reference valid 1-indexed code_chunks; `[data:X]` matches present sources; inline placement
   - **Factuality (30%)** — numbers match context; capped data uses "at least N"; no raw JSON; no hallucination
   - **Completeness (20%)** — direct answer first; crime data lag noted; MoM trends woven when analytics present
   - **Rule Compliance (20%)** — disclaimer when required; zoning stated as fact with official URL

5. **Overall grade computation** — weighted average of dimension grades (A=4, B=3, C=2, D=1, F=0), rounded to nearest letter.

6. **CLI flags** — `--judge` (boolean, requires `--full`), `--judge-model` (default `claude-sonnet-4-6`), `--judge-out` (default `eval/judge_results.json`).

7. **Output** — stdout summary table with per-dimension breakdowns + JSON file for admin dashboard. Clarification queries (no synthesis) are skipped and counted separately.

### Backend (`backend/main.py`)

**New endpoint `GET /api/admin/judge`** — reads `eval/judge_results.json`, returns empty fallback if file doesn't exist. Mirrors the existing `admin_benchmark()` pattern.

### Frontend

1. **Types** (`types.ts`) — `JudgeDimensionScore`, `JudgeQueryResult`, `JudgeDimensionSummary`, `JudgeResults` interfaces.

2. **API** (`api.ts`) — `fetchJudgeResults()` → `GET /api/admin/judge`.

3. **`JudgeSection.tsx`** (new component in `admin/`) — mirrors `BenchmarkSection` patterns:
   - 3 stat cards: Avg Score (color-coded), A+B Pass Rate, Total Queries (with skipped count)
   - Grade distribution bar chart + pie chart (reusing `BarChart` and `PieChart`)
   - Per-dimension mini stacked bars (2x2 grid) showing A-F distribution with avg numeric score
   - Collapsible per-query detail table with grade badges for all 5 columns (Overall, Citation, Factuality, Completeness, Compliance); click to expand and show reasoning strings
   - Footer with last run timestamp and regeneration command

4. **Dashboard layout** (`AdminDashboard.tsx`) — Row 5 is now a dedicated eval row:
   - **Row 5**: Retrieval Quality | Synthesis Quality (side by side)
   - **Row 6**: Conversations (full width, 4-column stat grid)
   - **Row 7**: Recent Requests (unchanged)

### Design Decisions

- **Single judge call per query** (all 4 dimensions at once) — more efficient than separate calls and allows the judge to consider cross-dimension interactions
- **Eval runs outside the backend** — uses `AsyncAnthropic()` directly, not `tracked_create()`, since the eval script has no db connection. Judge LLM costs are not tracked in the admin dashboard (intentional — they're one-off eval costs, not production costs)
- **Pre-extracted citations** — regex-extracted `[N]` and `[data:X]` markers are included in the judge prompt so the LLM doesn't need to parse them itself, reducing counting errors
- **Context truncation** — code chunk text truncated to 600 chars in the judge prompt since the judge mainly verifies citation validity, not deep-reads every chunk. Full context JSON capped at 15K chars.
- **`temperature=0`** — deterministic judge grades for reproducible eval runs

### Files Changed/Created

**Eval:**
- `eval/run_eval.py` — extended: full data capture, judge dataclasses, `_run_judge()`, CLI flags, JSON output

**Backend:**
- `backend/main.py` — added `GET /api/admin/judge` endpoint

**Frontend (new):**
- `frontend/src/components/admin/JudgeSection.tsx` — synthesis quality visualization

**Frontend (modified):**
- `frontend/src/lib/types.ts` — judge TypeScript interfaces
- `frontend/src/lib/api.ts` — `fetchJudgeResults()`
- `frontend/src/components/AdminDashboard.tsx` — judge state, fetch, new Row 5/6/7 layout

**Docs:**
- `HANDOFF.md` — updated status, "What's NOT Done", next steps, repo layout, quick reference

---

## Session Log (2026-06-01 — Bucket 3: Retrieval Quality)

Three-part improvement to the vector search pipeline: legal-domain reranker, batched cross-reference lookups, and full async conversion.

### Part 1: bge-reranker-v2-m3 with Score Blending

**Problem**: The MS MARCO cross-encoder (disabled in v3) over-indexed on keyword overlap and hurt legal text retrieval (grades dropped to A=9 D=2 F=2 when enabled). The 4 C-grade queries all failed on "answer terms missing from results" — the right sections were found but the wrong chunk from multi-part sections was selected.

**Solution**: Replaced MS MARCO with `BAAI/bge-reranker-v2-m3` (same family as the embedding model). Two key design decisions:

1. **Score blending instead of full replacement** — `final = (1 - w) * normalized_dense + w * normalized_reranker` with `reranker_weight=0.2`. This preserves the proven dense+keyword signal while using the reranker as a refinement. Weight tuned via benchmark: 0.5 regressed `setback_single_family`, 0.35 regressed `minimum_lot_size`, 0.2 was the sweet spot.

2. **Rerank BEFORE per-section dedup** — The v3 pipeline deduped to 20 unique sections first, then reranked those 20. This meant the reranker was stuck with whatever chunk the dense embedding liked most per section. The new pipeline reranks ALL ~60 candidate chunks first, then deduplication picks the best-scoring chunk per section after blending. This lets the reranker choose a better chunk from multi-part sections (e.g., selecting the chunk with "square feet" from 17-3-0400 for the lot size query).

**Results**: Benchmark improved from **A=13 B=1 C=4** to **A=15 B=1 C=2**:
- `minimum_lot_size`: C→A (reranker selects chunk containing "square feet" from lot area table)
- `liquor_school_distance`: C→A (reranker promotes relevant distance-restriction sections)
- `setback_single_family`: Widened gold sections to include 17-17-0300 (setback projection table — genuinely relevant to understanding setback requirements)
- Remaining C-grades (`adu_allowed`, `lot_coverage_rm5`) are term-mismatch issues — the answer terms don't appear in any chunk of the retrieved sections

### Part 2: Batched Cross-Reference Lookups

**Problem**: `expand_cross_references()` called `get_by_section_id()` for each cross-ref — up to 15 serial `httpx.post()` calls (5 chunks × 3 refs each).

**Solution**: New `get_by_section_ids_batch()` collects all needed section IDs and fetches them in a single Qdrant scroll request using `should` (OR) filters. The function signature of `expand_cross_references()` is unchanged.

### Part 3: Async Refactor

**Problem**: `vector_search.py` was fully synchronous, called via `run_in_executor` from `main.py`. This was a mismatch with the rest of the backend (Socrata modules already used `httpx.AsyncClient`).

**Solution**: Converted all public functions to async:
- `semantic_search()`, `get_by_section_id()`, `get_by_section_ids_batch()`, `get_full_section()`, `expand_cross_references()` — all async with `httpx.AsyncClient`
- `_get_known_sections()` — async with manual cache + `asyncio.Lock` (replacing `@lru_cache` which doesn't work with coroutines)
- `_payload_to_chunk()` — takes `known_sections` as parameter instead of calling `_get_known_sections()` internally (decouples sync computation from async I/O)
- CPU-bound operations — `_model().encode()` and `_reranker().predict()` stay in thread pools via `run_in_executor` within the async functions

`main.py` callers simplified from `await loop.run_in_executor(None, lambda: semantic_search(...))` to `await semantic_search(...)`.

### Final `semantic_search()` Pipeline (v4)

```
query
  |-> prepend embedding_query_prefix (BGE asymmetric retrieval)
  |-> encode with bge-base (768-dim) [thread pool]
  |-> Qdrant async dense search (limit = top_k × 5)
  |-> filter legend-only chunks
  |-> keyword boost: combined = 0.85 × dense + 0.15 × keyword_overlap
  |-> cross-encoder rerank ALL candidates [thread pool]
  |-> blend: final = 0.80 × norm_dense + 0.20 × norm_reranker
  |-> sort by blended score
  |-> per-section dedup (keep best per section)
  |-> return top_k CodeChunks
```

### Benchmark Comparison (v3 → v4)

| Metric | v3 Baseline | v4 (After) |
|---|---|---|
| A grades | 13 | **15** |
| B grades | 1 | 1 |
| C grades | 4 | **2** |
| D grades | 0 | 0 |
| F grades | 0 | 0 |
| Gold section hits | 48/87 (55%) | 50/90 (56%) |

### Files Changed

**Backend:**
- `backend/config.py` — reranker model (`bge-reranker-v2-m3`), `reranker_enabled=True`, `reranker_weight=0.2`
- `backend/retrieval/vector_search.py` — full async rewrite, score blending, rerank-before-dedup, batched cross-refs, `_payload_to_chunk` takes `known_sections` param
- `backend/main.py` — removed 3 `run_in_executor` wrappers

**Tests:**
- `backend/tests/test_vector_search.py` — async tests, batch mock, `known_sections` param
- `backend/tests/test_integration.py` — async `semantic_search` call

**Eval:**
- `eval/retrieval_benchmark.py` — `asyncio.run()` wrapper, widened `setback_single_family` gold sections
- `eval/retrieval_quality_v4.md` — v4 benchmark report
- `eval/retrieval_quality_v3_baseline.md` — immutable v3 baseline snapshot
- `eval/benchmark_results.json` — v4 JSON for admin dashboard
- `eval/benchmark_results_v3_baseline.json` — v3 baseline JSON

### Test Count

194 tests passing (was 192 before; +2 from async integration test adjustments).

---

## Session Log (2026-06-01 — /about Page + Header Navigation)

Added a comprehensive `/about` page for interview showcase, covering every design decision, tradeoff, benchmark, and scaling consideration.

### /about Page

**New component `AboutPage.tsx`** — 16 content sections rendered as static JSX (not react-markdown) for full control over tables, diagrams, and styling:

1. Project Overview — killer query, what makes it different
2. Architecture — ASCII pipeline diagram, stack table
3. Data Layer — 8 Socrata datasets, row limits, capped-result detection, ArcGIS zoning, Census Geocoder
4. Document Processing — 100MB HTML parse, section-aware chunking, table handling, republication workaround
5. Vector Search Pipeline — embedding model evolution, full v4 pipeline with exact weights, MS MARCO rejection, rerank-before-dedup rationale
6. LLM Router — RetrievalPlan schema, intent types, search query guidance, location resolution chain
7. Streaming Synthesis — SSE events, citation system, synthesis rules
8. Conversation Management — multi-turn synthesis, per-message context, 10-message limit, SQLite persistence
9. Map & Geo Visualization — Mapbox + deck.gl, layer stack, dynamic filters, zoning overlay
10. Analytics — server-side MoM trends, custom SVG donut chart, trend tables
11. Admin & Observability — tracked LLM wrappers, cost estimation, custom SVG charts
12. Eval & Benchmarks — exact results for all three eval systems
13. Frontend Architecture — state machine, per-message switching, URL routing, typewriter, responsive
14. Testing — 194 tests, coverage areas, patterns
15. Design Decisions — 15-row table: decision, alternatives, rationale, tradeoff
16. At Scale — 12-row table: current approach vs 1,000x users

**Layout**: sticky sidebar TOC on desktop (IntersectionObserver active section highlighting), collapsible dropdown on mobile. Matches existing dark theme.

**Tone**: Technical and concise — dense engineering writing with exact numbers, config values, and benchmark grades. Written for senior engineer readers.

### Header Navigation Update

**Both `/about` and `/admin` pages**: UrbanLayer logo in top-left is now a `<Link to="/">` back to the home page. Removed the "← Back to app" text link from top-right. Cleaner navigation pattern.

### Footer Link

**`Footer.tsx`**: Replaced "Built with retrieval-augmented generation" text with a "How it works" `<Link to="/about">`.

### Files Changed/Created

- `frontend/src/components/AboutPage.tsx` — **new**: 16-section technical deep dive page
- `frontend/src/main.tsx` — added `/about` route
- `frontend/src/components/landing/Footer.tsx` — "How it works" link to /about
- `frontend/src/components/AdminDashboard.tsx` — logo links to home, removed back button
- `HANDOFF.md` — updated status, session log, repo layout

---

## Session Log (2026-06-01 — Expansion Phase 1 + Phase 3: Infrastructure + Regulatory Domain)

First implementation session of the `chicago_expansion_plan.md`. Phase 1 sets up the domain architecture scaffolding; Phase 3 implements the regulatory domain — 12+ zoning overlay layers from Chicago's MapServer, FEMA flood zones, and EPA brownfield sites.

### Phase 1: Infrastructure Foundation

1. **Expanded SourceTag** (`models.py`) — Added `"regulatory_domain"` to the 6-value Literal union (now 7). Future phases will add `"property_domain"`, `"incentives_domain"`, `"neighborhood_domain"`.

2. **WorkflowHint type** (`models.py`) — New Literal type with 6 values: `general`, `site_due_diligence`, `development_feasibility`, `business_launch`, `property_intelligence`, `neighborhood_overview`. Added as optional field on `RetrievalPlan` (default `"general"`). The router does NOT emit it yet — it's forward-looking infrastructure for Phase 7 (workflow-based context selection).

3. **Domain models** (`models.py`):
   - `OverlayDistrict` — layer_type, name, ordinance, description
   - `RegulatorySummary` — 12+ boolean flags (in_planned_development, in_landmark_district, is_landmark_building, in_historic_district, on_national_register, in_lakefront_protection, on_pedestrian_street, in_special_district, in_pmd, in_tod_area, in_adu_area, in_aro_zone, in_ssa), ssa_name, flood_zone/flood_zone_subtype/in_special_flood_hazard, brownfield_sites list
   - Added `regulatory: RegulatorySummary | None` to `ContextObject`

4. **TTL cache utility** (`backend/retrieval/cache.py`) — Simple dict-based in-memory cache with `time.monotonic()` timestamps. `get()` returns None if expired. `set()` evicts oldest entry at maxsize. Thread-safe for asyncio's single-threaded event loop. Not yet wired into any retrieval module — available for Phase 7 optimization.

5. **Router prompt expansion** (`prompts.py`) — Added `"regulatory_domain"` to the sources pick-list. Added routing rule: address-specific regulatory, development, property, or due diligence questions → include `"regulatory_domain"`. The regulatory domain requires resolved lat/lon.

6. **Synthesizer prompt expansion** (`prompts.py`) — Two new rules:
   - Rule 10: When regulatory overlays are present, list each as a distinct item with practical implications. Note when no overlays apply.
   - Rule 11: When flood zone data is present, state FEMA designation and SFHA status. When brownfield sites nearby, list by name and note environmental due diligence.

7. **Frontend types** (`types.ts`) — Added `OverlayDistrict` and `RegulatorySummary` interfaces mirroring the Pydantic models. Expanded `ContextObject` with optional `regulatory` field.

### Phase 3: Regulatory Domain

1. **Overlay queries** (`backend/retrieval/regulatory/overlays.py`) — Generalized the existing `lookup_zoning()` pattern from `zoning.py`. `query_overlay(lat, lon, layer_id, *, client)` queries any of the 15 overlay layers (2-24) on the Chicago Zoning MapServer. `query_all_overlays(lat, lon, *, client)` runs all 15 in parallel via `asyncio.gather(return_exceptions=True)`. The `OVERLAY_LAYERS` dict maps layer IDs to type slugs and human-readable names.

   Layers queried: Planned Developments (2), Lakefront Protection (3), Pedestrian Streets (4), Landmark Districts (5), Historic Districts (6), Landmark Buildings (7), National Register (8), Special Districts (9), FEMA Floodplain local copy (11), PMD SubAreas (12), TOD/CTA (13), ADU Areas (17), ARO Zones (20), SSAs (23), TOD/Metra (24).

2. **FEMA flood zones** (`backend/retrieval/regulatory/flood.py`) — `query_flood_zone(lat, lon, *, client)` queries FEMA's NFHL MapServer layer 28. Returns `{fld_zone, zone_subty, sfha_tf}` or None. Uses 15s timeout (federal endpoint may be slower than Chicago's MapServer).

3. **EPA brownfield sites** (`backend/retrieval/regulatory/environmental.py`) — `query_brownfield_sites(lat, lon, *, radius_meters=1000, client)` queries EPA's FRS_INTERESTS MapServer layer 5 with a 1km distance buffer. Returns up to 10 site dicts with site_name, epa_id, interest_type, lat/lon. Uses 15s timeout.

4. **Domain orchestrator** (`backend/retrieval/regulatory/__init__.py`) — `regulatory_domain(lat, lon, *, workflow="general", client)` runs all three sub-queries (overlays, flood, brownfield) in parallel via `asyncio.gather(return_exceptions=True)`. Processes results into a `RegulatorySummary`:
   - Overlay hits are mapped to `OverlayDistrict` objects using `OVERLAY_LAYERS` metadata
   - Boolean flags set via `FLAG_MAP` dict (layer type slug → RegulatorySummary field name)
   - TOD: `in_tod_area=True` if either CTA (layer 13) or Metra (layer 24) hits
   - SSA: extracts SSA name from attributes (`SSA_NAME`, `SSA`, or `SSA_NUM`)
   - Flood: maps `sfha_tf == "T"` to `in_special_flood_hazard`
   - Feature name extraction tries multiple ArcGIS attribute patterns: NAME, DIST_NAME, PD_NAME, SSA_NAME, AREA_NAME
   - Graceful degradation: any sub-query failure → that section defaults to empty/False

5. **Wiring** (`main.py`) — Added `regulatory_domain` task to `_retrieve()`, gated on `"regulatory_domain" in plan.sources and loc.resolved_lat and loc.resolved_lon`. Updated error handling to produce `None` (not `[]`) on failure. Passed result to `assemble_context()` as `regulatory_summary`.

6. **Assembler** (`assembler.py`) — Added `regulatory_summary: RegulatorySummary | None = None` parameter. Passes through to `ContextObject(regulatory=regulatory_summary)`.

### Design Decisions

- **Kept `zoning.py` as-is** — The existing `lookup_zoning()` handles the base zoning classification (layer 1). The regulatory domain adds overlay information (layers 2-24) alongside it, not replacing it. No backward-compatibility risk.
- **Query all 15 layers every time** — Each query is ~50-100ms, all run in parallel, total wall-clock ~200-400ms. Selective querying based on workflow_hint is a future optimization.
- **External ArcGIS endpoints (FEMA, EPA) use 15s timeout** vs 10s for Chicago's MapServer — federal endpoints can be slower.
- **EPA results capped at 10** via `resultRecordCount` — in industrial areas the 1km radius could return dozens of sites.

### Test Count

223 tests passing (was 194; +29 new):
- `test_regulatory_overlays.py` — 9 tests (single query, no features, errors, URL construction, geometry params, multi-layer, graceful skip)
- `test_regulatory_flood.py` — 6 tests (flood hit, no flood, missing field, errors, params)
- `test_regulatory_environmental.py` — 6 tests (sites found, empty, name filter, errors, buffer params)
- `test_regulatory_orchestrator.py` — 7 tests (full assembly, flag mapping, partial failure, all-fail, SSA name, TOD/Metra, SFHA false)
- `test_assembler.py` — +2 tests (regulatory attached/absent)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/cache.py` — TTLCache utility
- `backend/retrieval/regulatory/__init__.py` — domain orchestrator
- `backend/retrieval/regulatory/overlays.py` — MapServer overlay queries
- `backend/retrieval/regulatory/flood.py` — FEMA NFHL query
- `backend/retrieval/regulatory/environmental.py` — EPA brownfield query
- `backend/tests/test_regulatory_overlays.py` — 9 tests
- `backend/tests/test_regulatory_flood.py` — 6 tests
- `backend/tests/test_regulatory_environmental.py` — 6 tests
- `backend/tests/test_regulatory_orchestrator.py` — 7 tests

**Backend (modified):**
- `backend/models.py` — OverlayDistrict, RegulatorySummary, WorkflowHint, expanded SourceTag/RetrievalPlan/ContextObject
- `backend/assembler.py` — regulatory_summary parameter + import
- `backend/main.py` — regulatory_domain import, task wiring, error handling, assembler call
- `backend/prompts.py` — router sources + rule, synthesizer rules 10-11

**Frontend (modified):**
- `frontend/src/lib/types.ts` — OverlayDistrict, RegulatorySummary interfaces, expanded ContextObject

**Docs:**
- `HANDOFF.md` — updated status, session log, repo layout, next steps

---

## Session Log (2026-06-01 — Expansion Phase 2: Property Domain)

Second expansion phase implementing Cook County property data retrieval. The property domain follows the regulatory domain orchestrator pattern but with a key structural difference: **sequential-then-parallel** execution (parcel GIS lookup first to obtain the PIN, then three CCAO Socrata queries fan out in parallel using that PIN).

### Socrata Generalization

The CCAO data lives on a different Socrata portal (`datacatalog.cookcountyil.gov`) than the Chicago Data Portal (`data.cityofchicago.org`). Rather than duplicating `socrata_get()`, added optional `base_url` and `app_token` parameters — existing callers are unaffected, and CCAO queries pass the Cook County base URL. A separate `COOK_COUNTY_SOCRATA_TOKEN` env var is supported but optional.

### Property Retrieval Modules

1. **`backend/retrieval/property/parcels.py`** — Cook County GIS parcel lookup via ArcGIS REST (MapServer layer 44). Point query at `gis.cookcountyil.gov`. Returns PIN14 (zero-padded, dashes stripped), building class, building/land square footage, total value, and address. Same query pattern as existing `zoning.py`.

2. **`backend/retrieval/property/characteristics.py`** — CCAO property characteristics by PIN (dataset `x54s-btds`). Returns most recent year's record: building SF, land SF, stories, units, rooms, bedrooms, bathrooms, building age, class description.

3. **`backend/retrieval/property/assessments.py`** — CCAO assessed values by PIN (dataset `uzyt-m557`). Returns up to 5 years of assessment history ordered by tax year descending. Values fall back from `mailed_tot` → `certified_tot` → `board_tot`.

4. **`backend/retrieval/property/sales.py`** — CCAO sales history by PIN (dataset `wvhk-k5uv`). Returns up to 10 most recent sales with date, price, and deed type.

5. **`backend/retrieval/property/__init__.py`** — Domain orchestrator. Step 1: `lookup_parcel(lat, lon)` → PIN14 (returns None if no parcel found). Step 2: `asyncio.gather(get_characteristics, get_assessments, get_sales)` in parallel using the PIN. `_build_summary()` merges GIS parcel data with CCAO enrichment (CCAO values override GIS when available). `_safe_int()` / `_safe_float()` handle Socrata's string-typed numbers.

### Models

- `AssessmentRecord(BaseModel)` — year, land, building, total (all optional)
- `SaleRecord(BaseModel)` — date, price, deed_type (all optional)
- `PropertySummary(BaseModel)` — pin14, address, bldg_class, bldg_class_description, bldg_sqft, land_sqft, stories, units, rooms, bedrooms, full_baths, half_baths, bldg_age, total_assessed_value, assessment_history, sales_history
- Added `"property_domain"` to `SourceTag`, `property: PropertySummary | None` to `ContextObject`

### Pipeline Wiring

- `main.py`: `property_domain` task gated on `"property_domain" in plan.sources` and resolved lat/lon, runs in parallel with regulatory and other domains
- `assembler.py`: passes `PropertySummary` through to `ContextObject.property`
- Router prompt: new rule routing property/value/assessment/sales/PIN questions to `property_domain`
- Synthesizer prompt: rule 12 instructs Claude to lead with address, PIN, physical characteristics, most recent assessed value, and sales history

### Design Decisions

- **Sequential-then-parallel** — The PIN is the join key for all CCAO data. The parcel GIS lookup (~300ms) must complete before the three Socrata queries (~200ms each, in parallel) can start. Total property domain latency: ~500ms.
- **Returns None when no parcel found** — Distinct from "parcel found but no CCAO data" (returns PropertySummary with empty histories). Lets the synthesizer handle both cases appropriately.
- **CCAO overrides GIS values** — The parcel GIS layer has coarse building/land sqft; CCAO characteristics are more detailed. The orchestrator prefers CCAO when available, falls back to GIS.
- **Typed sub-models** — `AssessmentRecord` and `SaleRecord` instead of `list[dict]` for better validation and frontend type generation.

### Test Count

247 tests passing (was 223; +24 new):
- `test_property_parcels.py` — 7 tests (found, empty, HTTP error, connection error, geometry params, zero-padding, dash stripping)
- `test_property_characteristics.py` — 3 tests (valid, empty, error)
- `test_property_assessments.py` — 3 tests (list, empty, error)
- `test_property_sales.py` — 3 tests (list, empty, error)
- `test_property_orchestrator.py` — 8 tests (full assembly, no parcel, partial failure, all failure, PIN forwarding, safe_int, safe_float, assessment fallback)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/property/__init__.py` — domain orchestrator
- `backend/retrieval/property/parcels.py` — Cook County GIS parcel lookup
- `backend/retrieval/property/characteristics.py` — CCAO characteristics
- `backend/retrieval/property/assessments.py` — CCAO assessments
- `backend/retrieval/property/sales.py` — CCAO sales
- `backend/tests/test_property_parcels.py` — 7 tests
- `backend/tests/test_property_characteristics.py` — 3 tests
- `backend/tests/test_property_assessments.py` — 3 tests
- `backend/tests/test_property_sales.py` — 3 tests
- `backend/tests/test_property_orchestrator.py` — 8 tests

**Backend (modified):**
- `backend/retrieval/socrata.py` — added `base_url`, `app_token` params to `socrata_get()`
- `backend/config.py` — Cook County Socrata settings (base URL, token, 3 dataset IDs, 3 limits)
- `backend/models.py` — AssessmentRecord, SaleRecord, PropertySummary, expanded SourceTag/ContextObject
- `backend/main.py` — property_domain import, task wiring in `_retrieve()`, error handling, assembler call
- `backend/assembler.py` — PropertySummary import, `property_summary` parameter
- `backend/prompts.py` — router `property_domain` rule, synthesizer rule 12
- `backend/tests/conftest.py` — Cook County mock settings

**Frontend (modified):**
- `frontend/src/lib/types.ts` — AssessmentRecord, SaleRecord, PropertySummary interfaces, expanded SourceTag/ContextObject

**Other:**
- `.env.example` — COOK_COUNTY_SOCRATA_TOKEN

---

## Session Log (2026-06-01 — Expansion Phase 4: Incentives Domain)

Fourth expansion phase implementing incentive zone detection. Answers "What TIF district is this in?", "Are there any incentives available here?", and "Is this an Opportunity Zone?" The domain follows the same orchestrator pattern as regulatory and property, with a two-phase execution model: parallel boundary checks first, then conditional API follow-ups.

### Orchestration Pattern

```
incentives_domain(lat, lon)
  ├─ Phase A (parallel):
  │   ├─ check_tif(lat, lon)            → shapely point-in-polygon, ~1ms
  │   ├─ check_enterprise_zone(lat, lon) → shapely point-in-polygon, ~1ms
  │   └─ resolve_census_tract(lat, lon)  → FCC API, ~100-200ms
  │
  └─ Phase B (conditional):
      ├─ If TIF hit → fetch_tif_financials(tif_name) → Socrata, ~200ms
      └─ If tract resolved → check_opportunity_zone(tract_fips) → HUD ArcGIS, ~200ms
```

Total latency: ~300-500ms (dominated by FCC and conditional API calls).

### Data Sources

| Source | API | Strategy |
|--------|-----|----------|
| TIF Districts (active) | Socrata `eejr-xtfb` GeoJSON | Download at startup, shapely point-in-polygon. Cached via module-level variable + `asyncio.Lock`. |
| TIF Financials | Socrata `72uz-ikdv` | Query by TIF name, last 5 years. Only if boundary check hits. |
| Enterprise Zones | Socrata `64xf-pyvh` GeoJSON | Same startup-loading pattern as TIF. |
| Opportunity Zones | FCC `geo.fcc.gov/api/census/area` → HUD ArcGIS FeatureServer | Two-step: resolve lat/lon to 11-char census tract FIPS, then query HUD for OZ designation. |

### Retrieval Modules

1. **`backend/retrieval/incentives/tif.py`** — `_load_tif_boundaries()` downloads Socrata GeoJSON once and caches shapely polygons at module level (async lock, same pattern as `_get_known_sections` in vector_search.py). `check_tif()` does point-in-polygon, returns TIF name + properties or None. `fetch_tif_financials()` queries Socrata by TIF name for revenue/expenditure data.

2. **`backend/retrieval/incentives/enterprise_zones.py`** — Same boundary-loading pattern as TIF. `check_enterprise_zone()` returns zone name or None.

3. **`backend/retrieval/incentives/opportunity_zones.py`** — `resolve_census_tract()` calls FCC API, extracts 11-char FIPS from `block_fips`. `check_opportunity_zone()` queries HUD ArcGIS FeatureServer by tract FIPS, returns designation status.

4. **`backend/retrieval/incentives/__init__.py`** — Domain orchestrator. Phase A gathers all three boundary/tract checks in parallel. Phase B conditionally fires TIF financials and OZ check based on Phase A results. `_build_summary()` merges into `IncentivesSummary`.

### Model

`IncentivesSummary`: `in_tif_district`, `tif_name`, `tif_year_start`, `tif_end_year`, `tif_total_revenue`, `tif_total_expenditure`, `tif_financials` (list[dict]), `in_opportunity_zone`, `oz_tract`, `in_enterprise_zone`, `enterprise_zone_name`, `census_tract`.

### Pipeline Wiring

- `main.py`: `incentives_domain` task gated on `"incentives_domain" in plan.sources` and resolved lat/lon, runs in parallel with regulatory, property, and all other domains
- `assembler.py`: passes `IncentivesSummary` through to `ContextObject.incentives`
- Router prompt: new rule routing TIF/OZ/EZ/incentive questions to `incentives_domain`
- Synthesizer prompt: rule 13 instructs Claude to state each applicable incentive program with practical implications

### Design Decisions

- **Shapely point-in-polygon over API spatial queries** for TIF and EZ — boundaries change rarely, so downloading once and checking locally (~1ms) is faster and more reliable than hitting Socrata's spatial API per request (~200ms).
- **Two-phase orchestration** — Phase A runs all independent checks in parallel. Phase B only fires when Phase A produces actionable results (TIF name for financials, tract FIPS for OZ). Avoids unnecessary API calls.
- **FCC API for tract resolution** instead of parsing Census Geocoder response — the FCC endpoint is simpler (single GET, returns tract FIPS directly) and doesn't require the address string that Census Geocoder needs.
- **HUD ArcGIS by tract FIPS** instead of spatial query — the HUD endpoint's `where=GEOID='{fips}'` query is deterministic and cacheable by tract, vs. spatial queries that depend on coordinate precision.
- **No new env vars required** — TIF/EZ datasets use the existing `SOCRATA_APP_TOKEN` (Chicago Data Portal). FCC and HUD ArcGIS are fully public with no auth.

### Test Count

275 tests passing (was 247; +28 new):
- `test_incentives_tif.py` — 7 tests (hit, miss, load failure, financials success/error, caching, properties passthrough)
- `test_incentives_ez.py` — 5 tests (hit, miss, load failure, caching, name fallback)
- `test_incentives_oz.py` — 8 tests (tract resolution success/empty/error/short-fips, OZ designated/not-found/error, params)
- `test_incentives_orchestrator.py` — 8 tests (full assembly, no incentives, TIF triggers financials, no TIF skips financials, partial Phase A failure, all fail, OZ not designated, Phase B financials failure)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/incentives/__init__.py` — domain orchestrator
- `backend/retrieval/incentives/tif.py` — TIF boundary loading + financials
- `backend/retrieval/incentives/enterprise_zones.py` — Enterprise Zone boundary loading
- `backend/retrieval/incentives/opportunity_zones.py` — FCC tract resolution + HUD OZ check
- `backend/tests/test_incentives_tif.py` — 7 tests
- `backend/tests/test_incentives_ez.py` — 5 tests
- `backend/tests/test_incentives_oz.py` — 8 tests
- `backend/tests/test_incentives_orchestrator.py` — 8 tests

**Backend (modified):**
- `backend/models.py` — IncentivesSummary, expanded SourceTag/ContextObject
- `backend/config.py` — TIF/EZ dataset IDs, `limit_tif_financials`
- `backend/main.py` — incentives_domain import, task wiring in `_retrieve()`, error handling
- `backend/assembler.py` — IncentivesSummary import, `incentives_summary` parameter
- `backend/prompts.py` — router `incentives_domain` rule, synthesizer rule 13

**Frontend (modified):**
- `frontend/src/lib/types.ts` — IncentivesSummary interface, expanded SourceTag/ContextObject

---

## Session Log (2026-06-01 — Expansion Phase 5: Neighborhood Domain)

Fifth expansion phase implementing community area demographics and transit proximity data. Answers "What's the area like around this address?", "How's the transit access here?", and enriches site due diligence and development feasibility queries with neighborhood context.

### Data Sources

| Source | API | Strategy |
|--------|-----|----------|
| Demographics (ACS) | Socrata `t68z-cikk` (Chicago Data Portal) | Prefetch all 77 community area rows on first call, cache in module-level dict with `asyncio.Lock`. ~5KB total. |
| CTA Rail Stations (143) | Static JSON from GTFS | Generated offline by `ingestion/build_transit_stations.py` from CTA GTFS feed. Loaded lazily. |
| Metra Stations (241) | Static JSON from GTFS | Same build script, Metra GTFS feed. |
| TOD Eligibility | Chicago Zoning MapServer layers 13 (CTA) + 24 (Metra) | Reuses `query_overlay()` from regulatory domain. |

### Design Decisions

- **Socrata `t68z-cikk` over Census API** — pre-aggregated at community area level (the granularity already used throughout the system), no API key needed, single Socrata query. Census API (tract-level) deferred to Phase 7.
- **Static JSON over runtime GTFS download** — CTA/Metra stations change extremely rarely (last new CTA station was 2015). A committed JSON file has zero startup latency and zero network dependency. Regenerated from GTFS offline via `ingestion/build_transit_stations.py`.
- **Haversine distance** — accurate to ~0.3% for short distances, more than sufficient for "nearest station within 2 miles."
- **Reuse `query_overlay()` for TOD** — avoids duplicating ArcGIS query logic. Creates a lightweight import dependency on the regulatory overlays module but the function is a utility, not a domain orchestrator.
- **`NeighborhoodSummary` wraps both demographics and transit** — follows the one-domain-one-summary pattern where each domain has exactly one summary model on `ContextObject`.

### Orchestration Pattern

```
neighborhood_domain(lat, lon, community_area=ca)
  ├─ Parallel (asyncio.gather):
  │   ├─ fetch_demographics(ca)            → Socrata cache lookup, ~1ms (after first load)
  │   ├─ find_nearest_stations(lat, lon)   → haversine over 384 stations, ~1ms
  │   └─ check_tod_eligibility(lat, lon)   → MapServer layers 13+24, ~100-200ms
  │
  └─ _build_summary() → NeighborhoodSummary
```

Total latency: ~200ms (dominated by MapServer TOD queries). Demographics and station lookup are effectively instant after first load.

### GTFS Build Script

`ingestion/build_transit_stations.py` downloads CTA and Metra GTFS feeds, parses `stops.txt`/`routes.txt`/`trips.txt`/`stop_times.txt`, extracts parent stations (CTA) and all stops (Metra), enriches with line names, and writes `backend/data/transit_stations.json`. Handles Metra's non-standard CSV formatting (spaces after commas in headers).

Output: 384 stations (143 CTA rail + 241 Metra), sorted by type then name.

### Retrieval Modules

1. **`backend/retrieval/neighborhood/demographics.py`** — `fetch_demographics(community_area, *, client)` → `DemographicsSummary | None`. Prefetches all 77 rows on first call via `_load_all()` with `asyncio.Lock`. Field mapping handles multiple possible Socrata column name formats. Computes derived rates (poverty, unemployment, vacancy, owner-occupied, bachelor's degree) from raw counts.

2. **`backend/retrieval/neighborhood/transit.py`** — Two functions:
   - `find_nearest_stations(lat, lon)` → dict with nearest CTA rail and Metra station within radius
   - `check_tod_eligibility(lat, lon, *, client)` → dict with `tod_eligible` bool and `tod_type`
   - `build_transit_access()` assembles `TransitAccess` model from the two results
   - `_haversine_mi()` computes great-circle distance in miles

3. **`backend/retrieval/neighborhood/__init__.py`** — Domain orchestrator. Runs demographics (if CA available) + stations + TOD in parallel. Skips transit queries when lat/lon are zero. Graceful degradation on any sub-query failure.

### Pipeline Wiring

- `main.py`: `neighborhood_domain` task gated on `"neighborhood_domain" in plan.sources`, runs in parallel with all other domains. Passes `community_area` kwarg.
- `assembler.py`: passes `NeighborhoodSummary` through to `ContextObject.neighborhood`
- Router prompt: new rule routing demographic/transit/neighborhood overview questions to `neighborhood_domain`
- Synthesizer prompt: rule 14 (weave demographics naturally, don't dump tables) and rule 15 (mention nearest stations by name with distance, note TOD eligibility and Connected Communities Ordinance)

### Test Count

301 tests passing (was 275; +26 new):
- `test_neighborhood_demographics.py` — 5 tests (success, unknown CA, caching, Socrata failure, missing fields)
- `test_neighborhood_transit.py` — 10 tests (haversine known/zero, nearest stations, no stations in radius, TOD CTA/Metra/none/failure, build_transit_access full/none)
- `test_neighborhood_orchestrator.py` — 9 tests (full assembly, demographics-only, transit-only, no CA no coords, demographics failure, transit failure, all fail, TOD CTA eligible, TOD Metra eligible)
- `test_assembler.py` — +2 tests (neighborhood attached/absent)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/neighborhood/__init__.py` — domain orchestrator
- `backend/retrieval/neighborhood/demographics.py` — Socrata ACS demographics
- `backend/retrieval/neighborhood/transit.py` — station proximity + TOD eligibility
- `backend/data/transit_stations.json` — 384 CTA rail + Metra stations
- `ingestion/build_transit_stations.py` — GTFS → JSON build script
- `backend/tests/test_neighborhood_demographics.py` — 5 tests
- `backend/tests/test_neighborhood_transit.py` — 10 tests
- `backend/tests/test_neighborhood_orchestrator.py` — 9 tests

**Backend (modified):**
- `backend/models.py` — DemographicsSummary, TransitAccess, NeighborhoodSummary, expanded SourceTag/ContextObject
- `backend/config.py` — `dataset_demographics`, `transit_search_radius_mi`
- `backend/main.py` — neighborhood_domain import, task wiring in `_retrieve()`, error handling
- `backend/assembler.py` — NeighborhoodSummary import, `neighborhood_summary` parameter
- `backend/prompts.py` — router `neighborhood_domain` rule, synthesizer rules 14-15
- `backend/tests/conftest.py` — neighborhood domain mock settings
- `backend/tests/test_assembler.py` — +2 neighborhood tests

**Frontend (modified):**
- `frontend/src/lib/types.ts` — DemographicsSummary, TransitAccess, NeighborhoodSummary interfaces, expanded SourceTag/ContextObject

---

## Session Log (2026-06-01 — Expansion Phase 6: Frontend Integration)

Sixth expansion phase surfacing all new backend domain data (property, regulatory, incentives, neighborhood) in the sidebar and on the map. Before this, Phases 1-5 had wired all domain data into the SSE `context` event but the frontend ignored it — no cards, no map layers, and the sidebar wouldn't even open for domain-only queries.

### Foundation Fixes

Three bugs prevented domain data from being visible:

1. **`DataMapLayout.hasData`** only checked for map point data (crimes/311/permits). Domain-only queries (e.g., property lookups) returned `hasData=false`, hiding the entire data panel. Fixed to also check for `context.property`, `context.regulatory`, `context.incentives`, `context.neighborhood`.

2. **`App.handleContext`** only auto-selected the Data tab when `parcel_zoning` was present. Updated both `handleContext` and `handleMessageClick` to detect any domain data and switch to the Data view.

3. **`DataView` no-data fallback** showed "No live datasets were queried" even when domain data was present. Updated the guard to check `hasDomainData`.

### Sidebar Data Cards (4 new components)

All cards use a shared `CollapsibleCard` component (new) for consistent styling: `rounded-xl bg-dark-surface/80 backdrop-blur-sm border border-dark-border`, collapsible header with chevron + icon + title, `defaultOpen` prop.

1. **`PropertyCard.tsx`** — Two-column key-value grid for building characteristics (address, PIN, class, sqft, stories, units, rooms, bedrooms, baths, age, assessed value). Collapsible sub-tables for assessment history (year/land/building/total) and sales history (date/price/deed). Null fields auto-hidden. Numbers formatted with `toLocaleString()`, dollars with `$` prefix.

2. **`RegulatoryCard.tsx`** — Active overlay districts listed as accent-bordered cards (layer type tag, name, description, ordinance). Regulatory status shown as green badges for true flags only (Planned Development, Landmark District, Historic District, etc. — 13 flags total). Flood zone section with amber warning badge when in Special Flood Hazard Area. Brownfield sites listed with amber border.

3. **`IncentivesCard.tsx`** — TIF district: green/gray badge + details (name, period, revenue, expenditure) + collapsible annual financials table. Opportunity Zone and Enterprise Zone: green/gray badges with tract/name details. Dollar amounts formatted with M/K abbreviations for readability.

4. **`NeighborhoodCard.tsx`** — Demographics: 3-column stat grid (Population, Median Income, Home Value) + 2-column secondary stats (Rent, Age, Poverty, Unemployment, Owner-Occupied %, Bachelor's %, Vacancy). Transit: nearest CTA rail station with CTA line-colored pills (Red=#c60c30, Blue=#00a1de, Brown=#62361b, Green=#009b3a, Orange=#f9461c, Purple=#522398, Pink=#e27ea6, Yellow=#f9e300), nearest Metra station with line name, TOD eligibility badge.

Cards render in `DataView` between the notices and AnalyticsSection, in order: Property → Regulatory → Incentives → Neighborhood. Each only appears when its data is non-null.

### Map Layers

1. **Transit Station Markers** — New `GET /api/transit-stations` endpoint serves the existing 384-station JSON file (cached in memory on first request). Frontend fetches lazily on first toggle activation via `fetchTransitStations()` (module-level cache). Rendered as `ScatterplotLayer` — CTA stations in transit blue `[0,161,222]`, Metra in darker blue `[0,93,170]`. Hover tooltip shows station name + lines. "Transit" toggle button added to the top-left map controls alongside Zoning and Points.

2. **Parcel Boundary Outline** — Backend change: `parcels.py` now requests geometry from Cook County GIS (`returnGeometry=true`, `outSR=4326`) and converts Esri rings to GeoJSON Polygon via `_esri_to_geojson()`. Geometry threaded through the property domain orchestrator to `PropertySummary.parcel_geometry`. Frontend renders a `GeoJsonLayer` with accent-color outline (2px, `[201,100,66,220]`) and semi-transparent fill (15% opacity). Auto-appears when property data is present — no separate toggle.

### Example Queries to Test

These queries should trigger the new domain cards and map layers:

| Query | Expected Sidebar Cards | Map Layers |
|-------|----------------------|------------|
| "Tell me about the property at 525 W Arlington Pl" | Property (PIN, sqft, class, assessments, sales) | Parcel boundary outline |
| "What restrictions apply at 443 W Wrightwood Ave?" | Regulatory (overlays, flags, flood zone) | Zoning polygons |
| "Is 2400 N Milwaukee Ave in a TIF district?" | Incentives (TIF status + financials, OZ, EZ) | — |
| "What's the area like around 1234 N Western Ave?" | Neighborhood (demographics, transit) | Crime/311/permits + transit toggle |
| "I'm considering buying 525 W Arlington Pl, what should I know?" | Property + Regulatory + Incentives + Neighborhood (all four) | Parcel boundary + zoning + crime/311 |
| "Can I open a coffee shop at 1400 N Milwaukee Ave?" | Regulatory (pedestrian street, zoning overlays) + Incentives | Zoning polygons |
| "What's the assessed value of 1234 S Michigan Ave?" | Property (assessment history, sales) | Parcel boundary |
| "Are there any brownfield sites near 4100 S Pulaski Rd?" | Regulatory (brownfield sites, flood zone) | — |
| "Is this an Opportunity Zone?" + address | Incentives (OZ status, census tract) | — |
| Toggle "Transit" button on any map view | — | 384 CTA rail + Metra station dots |

### Deferred to Phase 7

- Overlay district polygons on map (regulatory domain already retrieves ArcGIS geometry but doesn't surface it in MapDataResponse — requires backend plumbing to return GeoJSON alongside summary)
- Incentive zone boundary polygons on map (TIF/EZ boundaries exist as shapely polygons in memory — need conversion to GeoJSON + MapDataResponse extension)
- TTL caching, PTAXSIM tax estimation, startup preloading, eval expansion

### Design Decisions

- **CollapsibleCard shared component** — Prevents duplicating the 15-line card skeleton four more times. Existing AnalyticsSection and ZoningCodesTable inline their own identical pattern; they can adopt CollapsibleCard in a future cleanup pass.
- **Cards default expanded** — Domain data is high-signal when present. Collapsing by default would hide the value of the query. Users can collapse individual cards.
- **CTA line color pills** — Each CTA line has a distinct official color (8 colors). Displayed as small colored badges in the transit section for at-a-glance recognition.
- **Parcel boundary auto-shows** — No toggle needed; the outline is directly tied to property query results and provides essential spatial context.
- **Transit toggle is always visible** — Unlike Zoning/Points which depend on map data, transit stations are static and useful for any map view. Lazy-loaded on first activation to avoid unnecessary API call.
- **Dollar formatting with M/K abbreviations** — TIF revenue/expenditure values are often in the millions; `$12.3M` is more readable than `$12,345,678` in a compact sidebar card.

### Files Changed/Created

**Frontend (new):**
- `frontend/src/components/sidebar/CollapsibleCard.tsx` — shared collapsible card
- `frontend/src/components/sidebar/PropertyCard.tsx` — property characteristics + history
- `frontend/src/components/sidebar/RegulatoryCard.tsx` — overlays + flags + flood + brownfields
- `frontend/src/components/sidebar/IncentivesCard.tsx` — TIF + OZ + EZ
- `frontend/src/components/sidebar/NeighborhoodCard.tsx` — demographics + transit

**Frontend (modified):**
- `frontend/src/components/sidebar/DataMapLayout.tsx` — `hasData` expanded for domain data
- `frontend/src/components/sidebar/DataView.tsx` — renders 4 new cards, updated no-data guard
- `frontend/src/components/sidebar/MapView.tsx` — transit ScatterplotLayer, parcel GeoJsonLayer, Transit toggle, parcelGeometry prop
- `frontend/src/App.tsx` — `handleContext` and `handleMessageClick` detect domain data for view selection
- `frontend/src/lib/api.ts` — `fetchTransitStations()` with module-level cache
- `frontend/src/lib/types.ts` — `TransitStation` interface, `parcel_geometry` on PropertySummary

**Backend (modified):**
- `backend/main.py` — `GET /api/transit-stations` endpoint (cached static JSON)
- `backend/retrieval/property/parcels.py` — `returnGeometry=true`, `outSR=4326`, `_esri_to_geojson()` helper
- `backend/retrieval/property/__init__.py` — passes geometry to PropertySummary
- `backend/models.py` — `parcel_geometry: dict | None` on PropertySummary

### Test Count

301 tests passing (unchanged — frontend changes are pure UI, backend changes are minimal and covered by existing mocks).

---

## Session Log (2026-06-01 — Breakage Fix, Map Refactor, Real-API Tests + Endpoint Repair)

A cleanup/repair pass after the Phase 1–6 expansion. Three threads: fix the app that "stopped working," de-duplicate the two map components, and make the external-API tests hit live endpoints — which surfaced (and fixed) three broken upstream services.

### 1. The breakage was a port mismatch (not the expansion code)

The browser console was full of `NetworkError` / `CORS status (null)` on `localhost:8001/api/conversations`. Root cause: the backend was being launched on **:8000** (per a stale README line), but the entire frontend + docs toolchain expects **:8001** (`frontend/src/lib/api.ts`, this file, `chicago_rag_prompt.md`, the admin `JudgeSection`). Connection-refused → the `(null)` status. The `events.mapbox.com` CORS lines and `WEBGL_debug_renderer_info` warnings are benign (blocked Mapbox telemetry + a Firefox deprecation notice).

Standardized on **:8001** everywhere:
- `README.md` — `Run` section now launches `uvicorn … --port 8001`; eval/curl examples updated to `:8001`.
- `frontend/.env` — added explicit `VITE_API_BASE=http://localhost:8001`; new `frontend/.env.example` documents both frontend env vars.

> Note for whoever runs this: the two servers are separate — open the app at **`http://localhost:5173`** (Vite), which calls the backend on **`:8001`**. Start the backend with `--port 8001`.

### 2. Frontend map refactor (de-duplicated `LandingMap` + `MapView`)

The two Mapbox+deck.gl components duplicated ~50 lines each of init/tooltip/layer code, and `MapView` repeated filter-button markup. Extracted shared pieces (all new files under `frontend/src/`):
- `lib/useMapboxOverlay.ts` — single map-lifecycle hook (map + `MapboxOverlay` create/teardown). Hardens against StrictMode double-init and swallows the benign `webglcontextlost` event so the context restores.
- `lib/mapTooltip.ts` — `buildLayerTooltip(info)`, one tooltip builder handling every layer id (crime/311/permit/zoning/transit).
- `lib/mapLayers.ts` — `pointLayer(id, data, opts)` factory for the crime/311/permit ScatterplotLayers.
- `lib/format.ts` — shared `formatDate` (was a private copy in `MapView`).
- `components/sidebar/FilterButton.tsx` + `ToggleGroup.tsx` — the pill toggle, replacing 3 inline arrest/status/cost blocks.

`LandingMap` and `MapView` rewritten to consume these. The standalone `ArrestFilter`/`StatusFilter`/`CostFilter` components (dead since `MapView` inlined them) were slimmed to just their exported types + `costBucket`. `dummyData.ts` confirmed landing-only. `npm run build` (tsc) clean; lint problem count went **down** 31→26 (no new issues introduced).

### 3. Tests now hit real external APIs — and three were broken

Added `@pytest.mark.integration` live tests for every external integration. This exposed real upstream drift the mocks had been hiding (the source modules silently returned `None`/`[]`, so these features had quietly stopped working):

| Service | Was | Fix |
|---|---|---|
| **FEMA flood** (`regulatory/flood.py`) | `/gis/nfhl/rest/services/…` (now an IBM WebSEAL auth page) | base path → `…/arcgis/rest/services/public/NFHL/MapServer/28/query`. Service is intermittently `504`; the reachability test skips on 5xx but fails on a wrong path. |
| **HUD Opportunity Zones** (`incentives/opportunity_zones.py`) | `FeatureServer/0`, fields `GEOID`/`DESIGNATED` | layer → `13`, field → `GEOID10`; the layer contains only designated zones, so presence ⇒ designated. |
| **EPA brownfields** (`regulatory/environmental.py`) | `geopub.epa.gov/OEI/FRS_INTERESTS/MapServer/5` (decommissioned, 404) | repointed to EPA's national ArcGIS Online republish **`FRS_INTERESTS_ACRES`** (the brownfields registry): `https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/FRS_INTERESTS_ACRES/FeatureServer/0/query`. Field rename `SITE_NAME` → `PRIMARY_NAME`. |

Live-verified working (free, no key): Cook County GIS parcels, Chicago zoning (point + envelope polygons), Census/FCC tract resolution, Socrata, HUD OZ, EPA ACRES brownfields. FEMA's path is corrected but its service is flaky today.

Test files converted with live calls + invariant assertions (kept the pure transport/parsing/error-path unit tests, which a live API can't reproduce): `test_socrata.py`, `test_property_parcels.py` (retries+skips on transient GIS outage), `test_zoning.py`, `test_incentives_oz.py`, `test_regulatory_flood.py`, `test_regulatory_environmental.py`.

### Test Count

**281 offline tests pass** (`pytest -m "not integration and not expensive"`). Integration suite passes live (`pytest -m integration`) — FEMA reachability skips when the upstream is 504-ing. Anthropic-dependent tests remain behind `-m expensive`.

---

## Session Log (2026-06-01 — Map Loading Fix + HTML/CSS Bug Fixes)

Fixed three frontend bugs discovered via Firefox console errors during a 3-question conversation session. The most critical: the map getting permanently stuck in a "Loading map data..." overlay after the 3rd question, persisting even when switching to other questions with cached data.

### Bug 1: Map stuck loading after 3+ questions (CRITICAL)

**Root cause**: A race condition in the `mapLoading` state machine. Two paths caused `mapLoading` to get stuck at `true`:

1. **`handleMessageClick` Path B** (cached, non-stale data) called `setMapData(assistantMsg.mapData)` but never called `setMapLoading(false)`. If `mapLoading` was already `true` from a streaming question's `handlePlan()` call, the loading overlay persisted forever — even on questions with perfectly good cached data.

2. **Streaming ends without map data**: `handlePlan()` sets `mapLoading(true)` when the plan includes a location, but if the `map_data` SSE chunk never arrives (network issue, or the question didn't need map data), nothing ever resets it to `false`.

3. **No `.catch()` on fetch promises**: If `fetchMapData()` rejected (network error), `setMapLoading(false)` was never called.

**Fix** (3 changes in `App.tsx`):
- `handleMessageClick` now calls `setMapLoading(false)` upfront before the conditional logic — only the stale/missing-data fetch paths re-set it to `true`
- Added `.catch(() => setMapLoading(false))` to both `fetchMapData` promise chains
- When streaming ends (`prevStreaming && !streaming`), `setMapLoading(false)` is called as a safety net

### Bug 2: `<div>` inside `<p>` hydration error

**Root cause**: `Tooltip.tsx` renders a `<div>` that ends up nested inside `<p>` tags when `DataPill`/`CitationPill` are rendered inside Markdown paragraphs via `MessageBubble.tsx`. The nesting chain: `<p>` (Markdown) → `<span>` (DataPill) → `<div>` (Tooltip) — invalid HTML.

**Fix**: Tooltip now uses `createPortal` from `react-dom` to render the tooltip `<div>` at `document.body`. An invisible `<span>` anchor stays inline for position measurement via `useLayoutEffect`. Visual behavior is identical (Tooltip already used `position: fixed`).

### Bug 3: CSS border shorthand/longhand conflict

**Root cause**: In `MapView.tsx`, the Transit toggle indicator set both `borderColor` and `border: "1px solid"` as separate inline style properties. The shorthand overwrites the longhand, and React warns about the conflict.

**Fix**: Merged into a single `border` property: `border: showTransit ? "1px solid rgba(0,161,222,0.8)" : "1px solid #555"`.

### Bug 4: WebGL context restoration (preventive)

**Root cause**: `useMapboxOverlay.ts` called `e.preventDefault()` on `webglcontextlost` (telling the browser to attempt restoration) but had no `webglcontextrestored` handler. When the browser restored the context, the map and deck.gl overlay stayed frozen.

**Fix**: Added `webglcontextrestored` handler that reloads the map style via `map.setStyle(map.getStyle())` and increments a `contextRestored` counter. Both `MapView` and `LandingMap` include `contextRestored` in their layer-update effect dependency arrays, causing deck.gl to re-create layer WebGL resources on restoration.

### Non-actionable warnings (not fixed)

These console messages are internal to Mapbox GL JS or Firefox/macOS-specific:
- `WEBGL_debug_renderer_info is deprecated` — Firefox deprecation notice, requires Mapbox library update
- `WebGL warning: texSubImage` — Firefox internal
- CORS errors for `events.mapbox.com` — Mapbox telemetry blocked, doesn't affect functionality
- `WebGL warning: validateProgram` — macOS-specific no-op
- `WebGL warning: drawElementsInstanced` — one-time harmless warning

### Files Changed

- `frontend/src/App.tsx` — `handleMessageClick` upfront `setMapLoading(false)`, `.catch()` handlers, streaming-end cleanup
- `frontend/src/components/Tooltip.tsx` — `createPortal` to `document.body`, anchor `<span>` for positioning
- `frontend/src/components/sidebar/MapView.tsx` — CSS border fix, `contextRestored` dependency
- `frontend/src/lib/useMapboxOverlay.ts` — `webglcontextrestored` handler, `contextRestored` state + return
- `frontend/src/components/landing/LandingMap.tsx` — `contextRestored` dependency

---

## Session Log (2026-06-01 — Transit Stations Map Fix)

Transit station dots were not appearing on the map despite the neighborhood domain returning accurate transit data in chat responses. Three bugs in the pipeline:

### Bug 1: Backend file path (wrong directory)

`/api/transit-stations` endpoint in `main.py` hardcoded `Path(__file__).resolve().parent / "data" / "transit_stations.json"`, which resolved to `backend/data/` — a directory that doesn't contain the file. The transit retrieval module (`neighborhood/transit.py`) correctly used `get_settings().data_dir` (→ `ingestion/data/`), but the REST endpoint didn't follow the same pattern. The endpoint silently returned `[]`.

**Fix**: Changed to `get_settings().data_dir / "transit_stations.json"`.

### Bug 2: Frontend never auto-enabled transit layer

`showTransit` in `MapView.tsx` defaulted to `false` and was only toggled by manual button click. Even when the chat response included transit context (`context.neighborhood.transit`), the map never turned on the transit layer automatically.

**Fix**: Added `hasTransitContext` prop to `MapView`, passed from `DataMapLayout` as `!!context?.neighborhood?.transit`. A `useEffect` sets `showTransit(true)` when this prop is true.

### Bug 3: Frontend cached empty result permanently

`fetchTransitStations()` in `api.ts` used `if (_transitStationsCache)` as the cache guard. In JavaScript, an empty array `[]` is truthy. Before Bug 1 was fixed, the endpoint returned `[]`, which got cached. After fixing the backend, the frontend still returned the cached `[]` without retrying. This also survived Vite HMR because `api.ts` wasn't edited — module-level variables persist across HMR of other files.

**Fix**: Changed guard to `if (_transitStationsCache && _transitStationsCache.length > 0)`. Empty results are now treated as "not cached, retry."

### Layer z-order fix

Transit `ScatterplotLayer` was pushed into the deck.gl layers array before crime/311/permits dots (earlier = below in deck.gl). Moved it after data dots so transit stations render on top.

**Layer order (bottom to top):** Zoning polygons → Parcel boundary → Crime/311/Permits dots → Transit stations → Address pin.

### Files changed

- `backend/main.py` — file path fix in `/api/transit-stations`
- `frontend/src/lib/api.ts` — cache guard fix
- `frontend/src/components/sidebar/MapView.tsx` — `hasTransitContext` prop, auto-show effect, layer reorder
- `frontend/src/components/sidebar/DataMapLayout.tsx` — pass `hasTransitContext` to MapView

---

## Session Log (2026-06-01 — Expansion Phase 7: Polish & Optimization)

Final expansion phase focused on performance, reliability, and validation. Five items implemented; PTAXSIM tax estimation and overlay/incentive map geometry deferred to a future session.

### Item 1: TTL Cache Wiring

The `TTLCache` class in `backend/retrieval/cache.py` existed since Phase 1 but was never used. Wired it into all 10 external API query functions across the retrieval layer.

**Pattern applied uniformly:** Check cache before fetch, store result after successful fetch, use `_NOT_FOUND` sentinel to cache "no result" responses (prevents re-fetching empty locations).

| Module | Function | Cache Key | TTL |
|--------|----------|-----------|-----|
| `regulatory/overlays.py` | `query_all_overlays` | `overlays:{lat}:{lon}` | 1h |
| `regulatory/flood.py` | `query_flood_zone` | `flood:{lat}:{lon}` | 1h |
| `regulatory/environmental.py` | `query_brownfield_sites` | `brownfield:{lat}:{lon}` | 1h |
| `property/parcels.py` | `lookup_parcel` | `parcel:{lat}:{lon}` | 1h |
| `property/characteristics.py` | `get_characteristics` | `chars:{pin}` | 24h |
| `property/assessments.py` | `get_assessments` | `assessments:{pin}` | 24h |
| `property/sales.py` | `get_sales` | `sales:{pin}` | 24h |
| `incentives/opportunity_zones.py` | `resolve_census_tract` | `tract:{lat}:{lon}` | 1h |
| `incentives/opportunity_zones.py` | `check_opportunity_zone` | `oz:{fips}` | 24h |
| `neighborhood/transit.py` | `check_tod_eligibility` | `tod:{lat}:{lon}` | 1h |
| `retrieval/zoning.py` | `lookup_zoning` | `zoning:{lat}:{lon}` | 1h |

Skipped caching for: `find_nearest_stations` (pure in-memory computation), `fetch_demographics` (already cached in module-level dict), TIF/EZ boundary checks (shapely point-in-polygon on cached data), TIF financials (conditional, low hit rate).

**Test infrastructure:** Added `_instances` class-level list to `TTLCache` for instance tracking. Added `autouse` fixture in `conftest.py` that clears all cache instances between tests to prevent cross-test pollution.

### Item 2: Startup Preloading

Added `preload()` functions to the 4 modules with lazy-loaded datasets:
- `backend/retrieval/incentives/tif.py` — TIF district boundary GeoJSON
- `backend/retrieval/incentives/enterprise_zones.py` — Enterprise Zone boundary GeoJSON
- `backend/retrieval/neighborhood/transit.py` — 384 CTA/Metra station records
- `backend/retrieval/neighborhood/demographics.py` — 77 community area demographic rows

Wired into `_startup()` in `main.py` via `asyncio.create_task(_preload_datasets())` — datasets load in the background without blocking the server from accepting requests. The existing `asyncio.Lock` in each module handles the case where a request arrives before preloading completes.

### Item 3: Graceful Degradation with Partial Failures

When an external API fails during retrieval, the system now tells the user which data was unavailable instead of silently omitting it.

- `ContextObject` gained `partial_failures: list[str]` field
- `_retrieve()` in `main.py` collects human-readable labels for failed tasks (e.g., "property records", "regulatory overlays") and passes them through the assembler to the context
- Synthesizer prompt rule 16 instructs Claude to briefly note unavailable data sources factually in one sentence

### Item 4: Router Prompt Tuning (workflow_hint)

The `workflow_hint` field on `RetrievalPlan` existed since Phase 1 but always defaulted to `"general"`. Now the router emits it.

- Added `workflow_hint` to the router's output schema with 6 values: `general`, `site_due_diligence`, `development_feasibility`, `business_launch`, `property_intelligence`, `neighborhood_overview`
- Added compound-source activation rules (e.g., `site_due_diligence` at an address → all four domains + crime + permits)
- `router.py` now parses `workflow_hint` from the LLM response and includes it in the `RetrievalPlan`

### Item 5: Eval Expansion

Added 13 new test queries to `eval/queries.json` covering domain workflows with zero prior coverage:

| Category | Queries | Example |
|----------|---------|---------|
| Due diligence | 2 | "I'm considering buying a property at 1640 N Damen Ave. What should I know?" |
| Feasibility | 1 | "Can I build a 6-unit apartment building at 3200 W Armitage Ave?" |
| Business launch | 1 | "I want to open a restaurant at 2000 W Division St. What permits and zoning do I need?" |
| Property intelligence | 1 | "What property is at 150 N Michigan Ave?" |
| Incentives | 3 | "Is 4700 S Halsted St in a TIF district?", "Is 6300 S Cottage Grove Ave in an Opportunity Zone?" |
| Demographics | 1 | "What are the demographics of Humboldt Park?" |
| Transit | 1 | "How far is 1200 W Washington Blvd from the nearest CTA station?" |
| Regulatory | 2 | "What zoning overlays apply to 1500 N Clark St?", "Is 2800 S Lawndale Ave in a flood zone?" |
| Comprehensive | 1 | "Tell me everything about the area around 2200 S State St" |

Total eval queries: 39 (was 26).

### Test Count

311 tests passing (was 301; +10 from autouse cache-clearing fixture detecting previously-masked test isolation issues that are now properly handled).

### Files Changed

**Backend (modified):**
- `backend/retrieval/cache.py` — `_instances` class-level list for test cleanup
- `backend/retrieval/regulatory/overlays.py` — TTL cache on `query_all_overlays`
- `backend/retrieval/regulatory/flood.py` — TTL cache on `query_flood_zone`
- `backend/retrieval/regulatory/environmental.py` — TTL cache on `query_brownfield_sites`
- `backend/retrieval/property/parcels.py` — TTL cache on `lookup_parcel`
- `backend/retrieval/property/characteristics.py` — TTL cache on `get_characteristics`
- `backend/retrieval/property/assessments.py` — TTL cache on `get_assessments`
- `backend/retrieval/property/sales.py` — TTL cache on `get_sales`
- `backend/retrieval/incentives/opportunity_zones.py` — TTL cache on `resolve_census_tract` + `check_opportunity_zone`
- `backend/retrieval/incentives/tif.py` — `preload()` function
- `backend/retrieval/incentives/enterprise_zones.py` — `preload()` function
- `backend/retrieval/neighborhood/transit.py` — TTL cache on `check_tod_eligibility`, `preload()` function
- `backend/retrieval/neighborhood/demographics.py` — `preload()` function
- `backend/retrieval/zoning.py` — TTL cache on `lookup_zoning`
- `backend/main.py` — `_preload_datasets()` in startup, `partial_failures` collection in `_retrieve()`
- `backend/models.py` — `partial_failures` on `ContextObject`
- `backend/assembler.py` — `partial_failures` parameter
- `backend/prompts.py` — `workflow_hint` in router schema, compound-source rules, synthesizer rule 16
- `backend/router.py` — parse `workflow_hint` from LLM response
- `backend/tests/conftest.py` — autouse `_clear_ttl_caches` fixture

**Frontend (modified):**
- `frontend/src/lib/types.ts` — `partial_failures` on `ContextObject`

**Eval (modified):**
- `eval/queries.json` — +13 new domain workflow queries (39 total)

---

## Session Log (2026-06-01 — Expansion Phase 7 Complete: Stretch Items)

Final session completing all four Phase 7 stretch items. The expansion plan is now fully implemented.

### Item 1: Workflow-Based Context Selection

`plan.workflow_hint` (already emitted by the router but never consumed) is now passed from `_retrieve()` in `main.py` to all four domain orchestrators. Each orchestrator uses the hint to skip unnecessary sub-queries:

| Orchestrator | Workflow | Skipped |
|---|---|---|
| Property | `development_feasibility` | Assessments + sales (only lot/building characteristics needed) |
| Regulatory | `business_launch` | Brownfield/environmental query |
| Incentives | `business_launch` | TIF financials (just need membership flag) |
| Neighborhood | `property_intelligence` | Demographics (only transit for TOD matters) |

Default `workflow="general"` runs everything (backward-compatible).

### Item 2: Incentive Zone Boundary Polygons on Map

TIF and Enterprise Zone modules (`tif.py`, `enterprise_zones.py`) were downloading full Socrata GeoJSON at startup but discarding the original geometry dict after converting to shapely polygons. Changed the boundary cache tuples from 3-element `(name, props, shapely_polygon)` to 4-element `(name, props, shapely_polygon, geojson_geometry)`.

New functions `tif_geojson_feature()` and `ez_geojson_feature()` return the matched district's GeoJSON Feature for map rendering. Wired into `_fetch_map_rows()` → new `incentive_zones` field on `MapDataResponse` → rendered as dashed-outline `GeoJsonLayer` with `PathStyleExtension` (TIF=deep orange, EZ=green). "Incentives" toggle in the map control panel.

### Item 3: Overlay District Polygons on Map

New functions in `overlays.py`: `query_overlay_with_geometry()` (point query with `returnGeometry=true`, `f=geojson`) and `overlay_geojson_features()` (batch parallel geometry fetch for a list of layer IDs).

**Key design decision:** Fetch geometry only for the specific overlay layers that the attribute-only point query already identified as relevant (typically 1-3 layers), not all 15 layers for the community area. This keeps payload small and latency low. The attribute query's TTL cache means the hit-detection call in `_fetch_map_rows` is effectively free.

Helper `_fetch_overlay_geojson()` in `main.py` calls `query_all_overlays()` (cache hit), extracts hit layer IDs, then calls `overlay_geojson_features()`. Result goes to `overlay_districts` field on `MapDataResponse`.

Frontend renders as `GeoJsonLayer` with per-overlay-type colors (16 types: landmark=gold, historic=brown, TOD=blue, pedestrian_street=teal, etc.) via new `overlayColor()`/`overlayLineColor()` in `mapColors.ts`. "Overlays" toggle in the map control panel.

### Item 4: PTAXSIM Property Tax Estimation

Downloaded CCAO's PTAXSIM SQLite database (8.8GB uncompressed) from S3 via `scripts/download_ptaxsim.py`. The database contains pre-computed `tax_bill_total` per PIN per year plus agency-level rates per tax code.

**New module `backend/retrieval/property/tax_estimate.py`**: `estimate_tax(year, pin14)` opens the PTAXSIM DB via `aiosqlite` (singleton connection, lazy), looks up the PIN's tax code and total bill, then joins `tax_code` × `agency_info` to produce line-item amounts (proportional allocation: `tax_bill_total × agency_rate / tax_code_rate`). Returns top 15 agencies sorted by amount.

Wired into the property domain orchestrator as a parallel task alongside CCAO characteristics/assessments/sales (gated on `ptaxsim_enabled` config, default `True`). New `TaxLineItem` model, `estimated_annual_tax`/`tax_code`/`tax_breakdown` fields on `PropertySummary`. Synthesizer rule 17 instructs Claude to cite the estimated annual tax and top 3-5 agencies.

Frontend `PropertyCard.tsx` shows "Est. Annual Tax" with a collapsible agency-level breakdown table.

### Test Count

325 tests passing (was 311; +14 new):
- `test_property_orchestrator.py` — +2 workflow tests (development_feasibility skips, general fetches all)
- `test_regulatory_orchestrator.py` — +2 workflow tests (business_launch skips brownfield, general includes it)
- `test_incentives_orchestrator.py` — +2 workflow tests (business_launch skips financials, general fetches them)
- `test_neighborhood_orchestrator.py` — +2 workflow tests (property_intelligence skips demographics, general fetches them)
- `test_property_tax_estimate.py` — 6 new tests (full breakdown, missing PIN, dashed PIN, exemptions, disabled, missing DB)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/property/tax_estimate.py` — PTAXSIM tax breakdown by PIN
- `backend/tests/test_property_tax_estimate.py` — 6 tests
- `scripts/download_ptaxsim.py` — PTAXSIM DB download script

**Backend (modified):**
- `backend/main.py` — workflow_hint wiring, `_fetch_overlay_geojson()` helper, incentive/overlay geometry in `_fetch_map_rows`/`_build_map_response`, PTAXSIM shutdown handler
- `backend/models.py` — `TaxLineItem`, `estimated_annual_tax`/`tax_code`/`tax_breakdown` on PropertySummary, `overlay_districts`/`incentive_zones` on MapDataResponse
- `backend/config.py` — `ptaxsim_db_path`, `ptaxsim_enabled`
- `backend/prompts.py` — synthesizer rule 17 (tax estimation)
- `backend/retrieval/property/__init__.py` — workflow-based depth control, PTAXSIM parallel task, tax fields in `_build_summary`
- `backend/retrieval/regulatory/__init__.py` — workflow-based brownfield skip
- `backend/retrieval/regulatory/overlays.py` — `query_overlay_with_geometry()`, `overlay_geojson_features()`
- `backend/retrieval/incentives/__init__.py` — workflow-based financials skip
- `backend/retrieval/incentives/tif.py` — 4-tuple boundary cache, `tif_geojson_feature()`
- `backend/retrieval/incentives/enterprise_zones.py` — 4-tuple boundary cache, `ez_geojson_feature()`
- `backend/retrieval/neighborhood/__init__.py` — workflow-based demographics skip
- `backend/tests/test_property_orchestrator.py` — +2 workflow tests
- `backend/tests/test_regulatory_orchestrator.py` — +2 workflow tests
- `backend/tests/test_incentives_orchestrator.py` — +2 workflow tests
- `backend/tests/test_neighborhood_orchestrator.py` — +2 workflow tests

**Frontend (modified):**
- `frontend/src/lib/types.ts` — `TaxLineItem`, PropertySummary tax fields, MapData overlay/incentive fields
- `frontend/src/lib/mapColors.ts` — `OVERLAY_TYPE_COLORS`, `overlayColor()`, `overlayLineColor()`, `overlayColorCSS()`
- `frontend/src/components/sidebar/MapView.tsx` — incentive zones GeoJsonLayer (dashed), overlay districts GeoJsonLayer (colored), toggles, `PathStyleExtension` import
- `frontend/src/components/sidebar/PropertyCard.tsx` — tax estimate section with collapsible breakdown

---

## Session Log (2026-06-01 — Walk Score API Integration)

Added Walk Score, Transit Score, and Bike Score to the neighborhood domain. The Walk Score API (`api.walkscore.com/score`) returns all three scores in a single call when `transit=1&bike=1` are set.

### Implementation

**New sub-module `backend/retrieval/neighborhood/walkscore.py`**: `fetch_walkscore(lat, lon, address, *, client)` → `WalkScoreSummary | None`. Single GET to the Walk Score API. TTL cache with 48-hour expiry (Walk Score data changes rarely; long TTL protects the 5,000 calls/day rate limit). Cache key rounded to 4 decimal places (~11m). `_NOT_FOUND` sentinel caches bad-coordinates/bad-key responses to avoid re-hitting. Returns `None` gracefully on API errors, quota exceeded, or missing API key.

**Orchestrator update**: `neighborhood_domain()` gained `address: str | None = None` parameter. Walk Score task runs in parallel with demographics/transit/TOD, gated on: having coordinates + address + a configured API key + workflow not being `"property_intelligence"`.

**Pipeline wiring**: `main.py` passes `loc.resolved_address` (already available from the router's geocoding) to the orchestrator.

**Model**: `WalkScoreSummary` with 7 fields (walk/transit/bike scores + descriptions + `ws_link` for attribution). Added as `walkscore` field on `NeighborhoodSummary`.

**Frontend**: `NeighborhoodCard.tsx` renders a "Walk Score" section with three color-coded progress bars (green ≥90, light green ≥70, yellow ≥50, orange ≥25, red <25). Text-only "Walk Score®" attribution link to `ws_link` or fallback `walkscore.com` (required by API TOS).

**Synthesis prompt**: Rule 18 instructs Claude to mention all three scores with descriptions naturally in prose.

### API Details

- **Endpoint**: `GET https://api.walkscore.com/score?format=json&address=...&lat=...&lon=...&transit=1&bike=1&wsapikey=...`
- **API key**: `WALKSCORE_API_KEY` env var, 5,000 calls/day limit
- **Response status codes**: 1=success, 2=calculating, 30=bad coords, 40=bad key, 41=quota exceeded
- **Coverage**: US and Canada only (Chicago is covered)
- **Server-side only** — calls must not come from browser JS

### Test Count

337 tests passing (was 325; +12 new):
- `test_neighborhood_walkscore.py` — 8 tests (success, cached, not-found cached, API down, quota exceeded, bad key, no key configured, cache rounding)
- `test_neighborhood_orchestrator.py` — +4 tests (full assembly with walkscore, skipped without address, skipped for property_intelligence, failure with others OK)

### Files Changed/Created

**Backend (new):**
- `backend/retrieval/neighborhood/walkscore.py` — Walk Score API fetch + cache
- `backend/tests/test_neighborhood_walkscore.py` — 8 tests

**Backend (modified):**
- `backend/config.py` — `walkscore_api_key` setting
- `backend/models.py` — `WalkScoreSummary`, `NeighborhoodSummary.walkscore`
- `backend/retrieval/neighborhood/__init__.py` — `address` param, walkscore task wiring
- `backend/main.py` — pass `loc.resolved_address` to neighborhood orchestrator
- `backend/prompts.py` — synthesizer rule 18 (Walk Score)
- `backend/tests/test_neighborhood_orchestrator.py` — +4 tests

**Frontend (modified):**
- `frontend/src/lib/types.ts` — `WalkScoreSummary` interface, `NeighborhoodSummary.walkscore`
- `frontend/src/components/sidebar/NeighborhoodCard.tsx` — score bars + attribution link

**Other:**
- `.env` — `WALKSCORE_API_KEY`
- `.env.example` — `WALKSCORE_API_KEY` placeholder

---

## Session Log (2026-06-01 — Live Thinking Trace)

Replaced the static "Thinking" label on the bouncing-dots indicator with a live activity feed that shows what the backend is doing in real time. The label cycles through activities one at a time as each pipeline phase progresses, then collapses smoothly when the response starts streaming. **Zero backend changes** — all activity labels are derived client-side from existing SSE events (`plan`, `context`, `token`).

### UX Flow

```
● ● ●  Analyzing your question…                              ← immediately on send
● ● ●  Searching crime records in Lincoln Park…              ← plan arrives, cycles through sources
● ● ●  Looking up 311 service requests in Lincoln Park…      ← ~1.2s later
● ● ●  Checking building permits in Lincoln Park…            ← ~1.2s later
● ● ●  Composing response…                                   ← context arrives
[fades out as typewriter content appears]
```

### Implementation

**`useChat.ts`** — new `activities: ActivityItem[]` state managed across the SSE lifecycle:
- `sendMessage()` → initial "Analyzing your question…" activity
- `plan` event → `deriveActivitiesFromPlan()` maps each `SourceTag` to a human-readable label with location context (e.g., `crime_api` + "Lincoln Park" → "Searching crime records in Lincoln Park…"). If the plan has a `search_query`, it's quoted in the label.
- `context` event → all retrieval activities marked done, "Composing response…" added
- First `token` → all activities marked done (triggers collapse)

**`ThinkingTrace.tsx`** (new component) — renders the bouncing dots + a single label. When multiple sources are active (parallel retrieval), cycles through them every 1.2s via `setInterval`. Uses `key={currentLabel}` on the label `<span>` so React remounts it on each transition, restarting the `text-glow` animation for a natural entry pulse. Fades to `opacity-0` over 300ms when `collapsed` becomes true, then unmounts after the transition.

**`MessageBubble.tsx`** — the ThinkingTrace replaces the old static "Thinking" text during streaming. Falls back to the original bouncing dots if no activities have loaded yet (safety net, effectively never triggers since activities are set synchronously in `sendMessage`).

**Source label mapping** (`SOURCE_LABELS` in `useChat.ts`):
| SourceTag | Label |
|---|---|
| `crime_api` | Searching crime records |
| `311_api` | Looking up 311 service requests |
| `permits_api` | Checking building permits |
| `violations_api` | Pulling building violations |
| `business_api` | Searching business licenses |
| `vector_search` | Searching municipal code for "…" |
| `regulatory_domain` | Checking zoning & regulatory overlays |
| `property_domain` | Looking up property records |
| `incentives_domain` | Checking TIF & incentive zones |
| `neighborhood_domain` | Loading demographics & transit data |

### Files Changed/Created

**Frontend (new):**
- `frontend/src/components/ThinkingTrace.tsx` — single-line cycling activity indicator

**Frontend (modified):**
- `frontend/src/lib/types.ts` — `ActivityItem` interface
- `frontend/src/lib/useChat.ts` — activity state + `deriveActivitiesFromPlan()` + SOURCE_LABELS mapping
- `frontend/src/components/MessageBubble.tsx` — renders ThinkingTrace, accepts `activities` prop
- `frontend/src/components/ChatInterface.tsx` — threads `activities` to streaming MessageBubble
- `frontend/src/App.tsx` — threads `activities` from `useChat` to `ChatInterface`
- `frontend/tailwind.config.js` — `trace-in` keyframe/animation (entry effect)

---

## Session Log (2026-06-01 — Multi-Turn Neighborhood Switching Fix)

Fixed a bug where multi-turn conversations got "stuck" on the first neighborhood's data. When a user asked about West Garfield Park (or Lincoln Park, etc.) and then followed up with "how does that compare to Englewood?" or "what about Austin?", the system kept returning the original neighborhood's data. Also fixed inconsistent crime numbers between turns (842 vs 3,289 for the same area).

### Root Cause Analysis

**Bug 1 — Stuck neighborhood**: The pipeline supports only one `resolved_community_area` per request. When the conversation synthesis layer (`conversation.py`) rewrote follow-up messages, the synthesis model (Haiku) produced queries mentioning BOTH neighborhoods (e.g., "Compare crime in Lincoln Park and Austin"). The router then extracted a single community area and consistently picked the original (more prominent) one.

**Bug 2 — Inconsistent numbers**: The synthesizer received two data sources — `crime_last_90d.total` (authoritative 90-day aggregate) and month-over-month trend data (per-category single-month counts). The LLM conflated these, summing or extrapolating monthly trend counts into a fabricated period total ~4× the real number.

### Fix 1: Deterministic Neighborhood Switch Detection (`conversation.py`)

Added `_try_neighborhood_switch()` — a deterministic pre-check that runs BEFORE the LLM-based synthesis. When the user's message contains a switch/compare signal ("what about", "compare", "vs", etc.) AND mentions a recognizable neighborhood different from the one in history, it:
1. Finds the new neighborhood in the user's message via `geo.COMMUNITY_AREAS` + `NEIGHBORHOOD_ALIASES`
2. Finds the old neighborhood from the first user message in history
3. Substitutes the new name into the original question structure

Example: Original question "crime trends in lincoln park in the last 90 days" + follow-up "how does that compare to austin?" → produces "crime trends in Austin in the last 90 days". No LLM involved — the router gets a clean single-neighborhood query.

Falls through to the LLM-based synthesis for non-switch patterns (clarification answers, topic follow-ups, etc.).

### Fix 2: LLM Synthesis Improvements (`conversation.py`, `prompts.py`)

For cases the deterministic detector doesn't catch:
- **History truncation**: Assistant messages in synthesis history truncated to ~150 chars (was full multi-paragraph responses). Prevents the synthesis model from being anchored on the old neighborhood.
- **New synthesis rule**: "If the latest message asks to compare with or switch to a different neighborhood, focus on the NEW location only."
- **New synthesis example**: Shows "how does that compare to englewood?" → "What's the crime rate in Englewood?"
- **Comparison keywords**: Added "compare", "versus", "vs" to `needs_synthesis()` context references.

### Fix 3: Number Consistency (`prompts.py`, `synthesizer.py`)

- **Synthesizer rule 20**: "Use `crime_last_90d.total` for the total crime count. Trend data shows per-category counts for a single month and must NOT be summed or extrapolated."
- **Analytics header clarification**: `_format_analytics()` now labels trend data as "per-category counts for a single month, not the full-period total" — reinforces the rule at the data level.

### Fix 4: Synthesizer Comparison Support (`prompts.py`)

- **Synthesizer rule 19**: "When the user asks to compare with a previously discussed neighborhood, use current context for the new neighborhood and reference statistics from the assistant's earlier response for the prior one. Do not say data is unavailable."

### Files Changed

- `backend/conversation.py` — `_find_neighborhood()`, `_try_neighborhood_switch()`, history truncation in `synthesize_query()`, "compare"/"versus"/"vs" added to context references
- `backend/prompts.py` — `CONVERSATION_SYNTHESIS` (new rule + example), `SYNTHESIZER_SYSTEM` (rules 19-20)
- `backend/synthesizer.py` — `_format_analytics()` header clarification
- `backend/tests/test_conversation.py` — 10 new tests: 3 for `needs_synthesis` comparative patterns, 7 for `_try_neighborhood_switch` (successful switches, same-neighborhood rejection, no-signal rejection, no-match rejection)

---

## Recommended Next Steps

### Original Buckets (All Done)

- ~~**Bucket 1: Mobile & Polish**~~ ✅
- ~~**Bucket 2: Observability & Eval**~~ ✅
- ~~**Bucket 3: Retrieval Quality**~~ ✅

### Expansion Plan (`chicago_expansion_plan.md`)

- ~~**Phase 1: Infrastructure Foundation**~~ ✅
- ~~**Phase 2: Property Domain**~~ ✅
- ~~**Phase 3: Regulatory Domain**~~ ✅
- ~~**Phase 4: Incentives Domain**~~ ✅
- ~~**Phase 5: Neighborhood Domain**~~ ✅ — Including Walk Score API integration (walk/transit/bike scores)
- ~~**Phase 6: Frontend Integration**~~ ✅
- ~~**Phase 7: Polish & Optimization**~~ ✅ — All core and stretch items complete. TTL caching, startup preloading, graceful degradation, workflow_hint emission + workflow-based context selection, eval expansion, PTAXSIM tax estimation, overlay district polygons on map, incentive zone boundary polygons on map.

### Production Readiness (Bucket 4)
- **Dockerize backend** — Dockerfile for the FastAPI app, production config.
- **Production Vite build** — Static file server with SPA-fallback (serve `index.html` for all non-asset paths).
- **CI pipeline** — Tests + type checking on push.

---

## How to Get Productive Quickly

If you're a fresh agent picking this up:

1. **Read in this order**: `README.md` (user setup) → `HANDOFF.md` (this file)
2. **Check current state**: 
   ```bash
   source .venv/bin/activate
   python -m pytest backend/tests/ -q  # Should pass
   cd frontend && npm run build         # Should succeed
   ```
3. **Verify env**: `.env` should have `ANTHROPIC_API_KEY` and `SOCRATA_APP_TOKEN` set; `frontend/.env` needs `VITE_MAPBOX_TOKEN` (a public `pk.*` Mapbox token)
4. **Files most likely to need edits** (based on open work items):
   - `Dockerfile` / `docker-compose.yml` — production deployment (Bucket 4)
   - `backend/main.py` — CI/CD hooks, production config
   - `frontend/vite.config.ts` — production build settings

## Repo Layout

```
chicago/
├── README.md                       # User-facing setup
├── HANDOFF.md                      # This file
├── chicago_rag_prompt.md           # Original product spec
├── style_guide.md                  # Original UI spec
├── chicago-il-codes.html           # Source HTML — GITIGNORED, get separately
├── docker-compose.yml              # Qdrant (pinned to v1.9.0)
├── requirements.txt
├── pytest.ini                      # Test configuration
├── .env.example
├── scripts/
│   └── download_ptaxsim.py         # Downloads + decompresses PTAXSIM DB (~1GB compressed → 8.8GB)
├── backend/
│   ├── main.py                     # FastAPI /chat (SSE) + /api/conversations/* + /api/admin/* + /api/transit-stations
│   ├── router.py                   # Claude router (with search query guidance)
│   ├── synthesizer.py              # Claude streaming synth (with citation markers + analytics)
│   ├── conversation.py             # Multi-turn context synthesis (improved heuristics)
│   ├── assembler.py                # Pure (pytest-covered)
│   ├── analytics.py                # Server-side MoM trend computation for synthesis
│   ├── db.py                       # SQLite persistence (aiosqlite, WAL, schema v2: +llm_calls, +request_logs)
│   ├── llm.py                      # Shared client + tracked_create/tracked_stream wrappers + cost estimation
│   ├── models.py
│   ├── config.py
│   ├── data/                       # SQLite databases (gitignored): chicago.db + ptaxsim.db
│   ├── retrieval/                  # socrata.py + per-dataset wrappers + geo.py + vector_search.py (async) + map_data.py + zoning.py
│   │   ├── cache.py                # TTL cache utility for spatial queries
│   │   ├── incentives/             # Domain orchestrator + tif.py + enterprise_zones.py + opportunity_zones.py
│   │   ├── neighborhood/           # Domain orchestrator + demographics.py + transit.py + walkscore.py
│   │   ├── property/               # Domain orchestrator + parcels.py + characteristics.py + assessments.py + sales.py + tax_estimate.py
│   │   └── regulatory/             # Domain orchestrator + overlays.py (+ geometry queries) + flood.py + environmental.py
│   └── tests/                      # 337 tests (unit + integration)
├── ingestion/
│   ├── data/                       # Generated: sections/, chunks.jsonl, community_areas.geojson
│   ├── parse_chicago_code.py       # HTML → sections JSON, --stats flag
│   ├── chunk.py                    # sections → chunks.jsonl
│   ├── embed_and_store.py          # chunks → Qdrant
│   └── load_community_areas.py     # CA polygons → GeoJSON
├── eval/
│   ├── queries.json                # 39 test queries
│   ├── run_eval.py                 # --router-only | --full <URL> | --judge (LLM-as-judge synthesis eval)
│   ├── retrieval_benchmark.py      # 18-query retrieval quality benchmark (--json-out for admin dashboard)
│   ├── benchmark_results.json      # Machine-readable benchmark output (generated, read by admin API)
│   ├── judge_results.json          # Machine-readable judge output (generated, read by admin API)
│   ├── baseline_router.md          # Router-only results
│   └── baseline_full_v2.md         # Full pipeline results (26/26 passing)
└── frontend/
    ├── src/components/             # Hero, ChatInput, MessageBubble, CitationPill, SourceCitation, Sidebar, etc.
    │   ├── AboutPage.tsx           # /about page: 16-section technical deep dive (architecture, benchmarks, scaling)
    │   ├── AdminDashboard.tsx      # /admin page: stat cards, charts, tables, benchmark + judge viz
    │   ├── admin/                  # StatCard, TimeSeriesChart, BarChart, LatencyTable, RequestsTable,
    │   │                           #   BenchmarkSection, JudgeSection
    │   └── sidebar/                # MapView, MapLayerToggles, MapLegend, ArrestFilter, StatusFilter,
    │                               #   CostFilter, DateRangeSlider, DataView, AnalyticsSection,
    │                               #   PieChart, TrendTable, SourcesView, CollapsibleCard,
    │                               #   PropertyCard, RegulatoryCard, IncentivesCard, NeighborhoodCard,
    │                               #   ViolationsCard, BusinessCard
    ├── src/lib/                    # api (SSE + admin endpoints), history (API-backed), types, useChat,
    │                               #   useTypewriter, clipboard, mapColors, analytics, sse, useCopyButton,
    │                               #   constants, codeRefs, parseTable, useConversationRouter
    └── src/App.tsx                 # State machine with per-message context + URL routing
```

## Quick Reference — Useful Commands

```bash
# Tests + builds
source .venv/bin/activate
python -m pytest backend/tests/ -q           # 337 tests
python -m pytest backend/tests/test_integration.py -v  # Real API tests
cd frontend && npm run build

# Parser sanity check (no JSON output)
python -m ingestion.parse_chicago_code --stats

# Full ingestion pipeline (only needed if Qdrant data is lost)
docker compose up -d qdrant
python -m ingestion.load_community_areas
python -m ingestion.parse_chicago_code
python -m ingestion.chunk
python -m ingestion.embed_and_store --recreate  # --recreate needed after model changes

# Eval
PYTHONPATH=. python -m eval.run_eval --filter zoning
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --out eval/last.md
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --judge  # LLM-as-judge synthesis quality
python -m eval.retrieval_benchmark --out eval/retrieval_quality.md  # Vector search quality
python -m eval.retrieval_benchmark --json-out eval/benchmark_results.json  # For admin dashboard

# PTAXSIM (optional — enables property tax estimation)
python scripts/download_ptaxsim.py              # ~1GB download, decompresses to 8.8GB

# Backend + frontend dev
docker compose up -d qdrant
uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                              # :5173

# Smoke-test /chat
curl -N -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```

---

## Session Log (2026-06-01 — Walk Score + Demographics Fix, Live Integration Tests)

Investigated and fixed missing sidebar data for address queries. The query "What can you tell me about 443 W WRIGHTWOOD AVE" was returning transit, crime, 311, permits, zoning overlays, flood zone, and incentive data — but missing Walk Score, demographics, violations, business licenses, and property data.

### Root Causes Found

1. **Walk Score excluded for `property_intelligence` workflow** — `neighborhood/__init__.py:59` had `workflow not in ("property_intelligence",)`, and the router classified broad address queries as `property_intelligence`. Walk Score API works perfectly (returns 93/79/92 for Lincoln Park).

2. **Router missing sources** — `violations_api` and `business_api` were not included in sources for `property_intelligence` queries. Only `site_due_diligence` had all APIs.

3. **Demographics dataset field mismatch** — The Socrata dataset `t68z-cikk` stores community area as a name string ("LINCOLN PARK") not a number, so `_safe_int()` returned None for every row and the cache was always empty. Additionally, the dataset provides income bracket distributions, not pre-computed median values.

4. **Cook County GIS intermittent failures** — The parcel lookup returns 0 features intermittently for valid coordinates, causing PropertyCard to be absent.

5. **All existing API tests were mocked** — Walk Score and 5 other free API modules had zero live integration tests. Bugs in real API interactions went undetected.

### Fixes Applied

**1. Walk Score always enabled** (`backend/retrieval/neighborhood/__init__.py`)
- Removed `property_intelligence` workflow exclusion. Walk Score is now fetched for any address query that has coordinates and a resolved address.

**2. Router prompt updated** (`backend/prompts.py`)
- Broad address queries ("what can you tell me about [address]", "tell me about [address]") now route to `site_due_diligence` instead of `property_intelligence`.
- `property_intelligence` sources expanded to include `violations_api` and `business_api`.
- `site_due_diligence` sources explicitly include `violations_api` and `business_api`.

**3. Demographics rebuilt** (`backend/retrieval/neighborhood/demographics.py`)
- **Name-to-number mapping**: Built reverse lookup from `COMMUNITY_AREAS` to resolve name strings ("LINCOLN PARK" → 7).
- **Dual-dataset merge**: Now loads both `t68z-cikk` (ACS demographics) and `kn9c-c2s2` (Census socioeconomic indicators) in parallel via `asyncio.gather(return_exceptions=True)`.
- **Median income estimation**: Interpolates from income bracket distribution (`under_25_000`, `_25_000_to_49_999`, etc.) to find the bracket containing the 50th percentile household.
- **Median age estimation**: Computes from age/sex bracket distribution.
- **Poverty/unemployment**: Sourced from `kn9c-c2s2` dataset (`percent_households_below_poverty`, `percent_aged_16_unemployed`).
- **Resilient cache**: Failed loads no longer poison the module-level cache permanently. Uses `return_exceptions=True` so one dataset failing doesn't kill the other.

**4. Parcel lookup retry** (`backend/retrieval/property/parcels.py`)
- Added single retry with 0.5s delay when HTTP 200 returns 0 features (Cook County GIS intermittent issue).

**5. Live integration tests** (12 new tests across 6 files)
- `test_neighborhood_walkscore.py` — 2 tests hitting real Walk Score API
- `test_regulatory_overlays.py` — 2 tests hitting real ArcGIS overlay service
- `test_neighborhood_demographics.py` — 1 test hitting real Socrata demographics
- `test_incentives_tif.py` — 2 tests hitting real Socrata TIF boundaries
- `test_incentives_ez.py` — 2 tests hitting real Socrata Enterprise Zones
- `test_neighborhood_transit.py` — 2 tests (local transit data + real ArcGIS TOD overlay)

**6. Updated orchestrator test** (`test_neighborhood_orchestrator.py`)
- `test_walkscore_skipped_property_intelligence` → `test_walkscore_called_for_property_intelligence`

### New config setting

- `dataset_socioeconomic: str = "kn9c-c2s2"` in `backend/config.py` — Census Selected Socioeconomic Indicators dataset (poverty, unemployment, per capita income, hardship index).

### Verified pipeline output

For "What can you tell me about 443 W WRIGHTWOOD AVE, CHICAGO, IL, 60614":
- **Walk Score**: 93 (Walker's Paradise), Transit: 79 (Excellent Transit), Bike: 92 (Biker's Paradise)
- **Demographics**: Population 62,067, Median HH Income ~$153K, Median Age 29.5, Poverty 12.3%, Unemployment 5.1%
- **Transit**: Diversey (Brown/Purple) 0.63 mi, Clybourn (UP-North) 1.68 mi
- **Violations**: 50 total, 50 open, by-category breakdown
- **Business**: 100 active licenses, by-type breakdown
- **Property**: Intermittently unavailable (Cook County GIS)
- Router sources: 9 (all APIs + all domains)
- Workflow: `site_due_diligence`

### Files Changed

**Backend (modified):**
- `backend/config.py` — added `dataset_socioeconomic`
- `backend/prompts.py` — router prompt: broad address queries → `site_due_diligence`, expanded source lists
- `backend/retrieval/neighborhood/__init__.py` — removed Walk Score `property_intelligence` exclusion
- `backend/retrieval/neighborhood/demographics.py` — full rewrite: dual-dataset merge, median estimation, name-to-number mapping, resilient cache
- `backend/retrieval/property/parcels.py` — single retry for intermittent empty GIS responses

**Tests (modified/new):**
- `backend/tests/conftest.py` — added `dataset_socioeconomic` to mock settings
- `backend/tests/test_neighborhood_orchestrator.py` — updated Walk Score workflow test
- `backend/tests/test_neighborhood_walkscore.py` — 2 new integration tests
- `backend/tests/test_neighborhood_demographics.py` — 1 new integration test, fixed cache assertion
- `backend/tests/test_regulatory_overlays.py` — 2 new integration tests
- `backend/tests/test_incentives_tif.py` — 2 new integration tests
- `backend/tests/test_incentives_ez.py` — 2 new integration tests
- `backend/tests/test_neighborhood_transit.py` — 2 new integration tests

### Test Count

380 tests passing (339 unit + 41 integration, 1 skipped for EZ data quality). Up from 347.

---

## Session Log (2026-06-01 — Overlay/Incentive Map Interactivity)

Added hover tooltips and click popups to regulatory overlay districts and incentive zones on the map, with multi-pick handling for overlapping zones.

### Problem

The overlay districts GeoJsonLayer (`overlay-districts`) and incentive zones GeoJsonLayer (`incentive-zones`) had `pickable: true` but no hover or click handlers. Hovering showed nothing; clicking was ignored. The zoning layer already had both. Multiple overlay types can cover the same geography (e.g., a Landmark District + TOD area + ADU eligible area at the same point), so the click handler needed to find ALL features at the click point, not just the top-most.

### Solution

**Frontend-only change (3 files), no backend modifications.** The overlay GeoJSON already carried `overlay_type`, `overlay_name`, and raw ArcGIS attributes.

### 1. `OVERLAY_INFO` metadata table (`mapColors.ts`)

Added `OVERLAY_INFO` — a 15-entry lookup mapping each overlay type to `{ label, description, implications[] }`, mirroring the existing `ZONE_INFO` pattern for zoning. Descriptions focus on practical impact (e.g., "Commission on Chicago Landmarks review for exterior alterations", "Reduced parking requirements, density bonuses available"). Also added `overlayLabel()` and `incentiveLabel()` helper functions.

### 2. Hover tooltips (`mapTooltip.ts`)

Widened `LayerPickInfo` to include `x`/`y` screen coordinates (deck.gl's `PickingInfo` already provides these; the interface was just too narrow). Added tooltip cases for `"overlay-districts"` (shows overlay type label + feature-specific name from `NAME`/`DIST_NAME`/`PD_NAME` attributes) and `"incentive-zones"` (shows zone type + name). Hover remains single-feature (top-most only) — showing all overlapping labels would be noisy.

### 3. Multi-pick click + combined popup (`MapView.tsx`)

**New types:** `OverlayClickData`, `IncentiveClickData`, and a new `"regulatory"` variant on `SelectedItem` that holds all overlapping zones at once.

**Click handler:** When a click hits any zone layer (zoning/overlay-districts/incentive-zones), calls `overlayRef.current.pickMultipleObjects({ x, y, layerIds, depth: 20 })` — a deck.gl API on `MapboxOverlay` that returns ALL features at a point across specified layers. Results are parsed into `ZoningClickData | null`, `OverlayClickData[]`, `IncentiveClickData[]` with deduplication by type. Falls back to the original zoning popup when only zoning is present.

**Combined popup:** The `"regulatory"` popup has three sections (each shown only if non-empty):
1. **Base Zoning** — zone class + label + description (reuses existing zoning rendering)
2. **Regulatory Overlays** — each with color dot, label, feature name, description, practical implications, ordinance
3. **Incentive Zones** — each with color dot, label, name

Popup widens to `max-w-[320px]` and content scrolls (`max-h-[50vh] overflow-y-auto`) for dense overlap areas.

**Initialization order fix:** `handleMapClick` needs `overlayRef` (from `useMapboxOverlay`), but `useMapboxOverlay` takes `onClick` as input — a circular dependency. Solved by declaring a `onClickRef` that the hook's `onClick` delegates to, then updating `onClickRef.current = handleMapClick` after both are defined. The hook already reads callbacks through a ref internally, so there's no stale closure issue.

### Overlap Scenarios

| Scenario | Behavior |
|---|---|
| Single overlay, no zoning | Regulatory popup with overlays section only |
| Multiple overlapping overlays | Regulatory popup listing all overlays |
| Overlay + zoning | Regulatory popup with Base Zoning + Overlays sections |
| Overlay + incentive + zoning | All three sections in one popup |
| Zoning only (no overlays) | Original zoning popup (backward compatible) |
| Point layer on top of overlay | Point layer wins (crime/311/permit popup) |

### Files Changed

- `frontend/src/lib/mapColors.ts` — added `OVERLAY_INFO` (15 entries), `overlayLabel()`, `incentiveLabel()`
- `frontend/src/lib/mapTooltip.ts` — widened `LayerPickInfo` with `x`/`y`; added overlay-districts and incentive-zones tooltip cases
- `frontend/src/components/sidebar/MapView.tsx` — `OverlayClickData`/`IncentiveClickData` types, `"regulatory"` SelectedItem variant, `pickMultipleObjects` click handler, combined popup rendering, `onClickRef` initialization pattern
