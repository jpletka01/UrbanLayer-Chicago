# Project Handoff — Chicago City Intelligence

A snapshot of what's been built, the decisions behind it, and what should come next. Companion to `README.md` (user-facing setup) and `~/.claude/plans/velvet-gliding-salamander.md` (the original implementation plan).

---

## TL;DR

A RAG-powered chat interface for natural-language questions about Chicago. Combines live Chicago Data Portal (Socrata) data with semantic search over the entire Chicago Municipal Code. Single killer query: *"What's going on near 2400 N Milwaukee Ave?"* → a unified response covering crime, 311, building activity, business licenses, and applicable zoning, all from one prompt.

**Current status (2026-05-31):** Full pipeline operational. Ingestion complete (14,535 chunks in Qdrant, down from 14,628 after table consolidation). Eval suite passes 26/26 queries (100%). Retrieval quality benchmark: **A=13 B=1 C=4** on 18 user-style queries (up from A=11 B=1 C=4 D=1 F=1 before improvements). Most recent work: **URL-based conversation routing** — each conversation gets its own `/c/:id` URL via `react-router-dom`; bookmarkable, browser back/forward support, direct-link loading with invalid-ID redirect. Previous: Zoning UX overhaul, geocoding fix, zoning map integration, analytics category audit, SQLite persistence, map interactivity. 192 tests passing.

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
- Vector search uses raw HTTP API (httpx) instead of qdrant-client Python library due to client v1.18.x incompatibility with server v1.9.0.

---

## What's Done

Everything below is in the repo, tested and verified.

### Backend (`backend/`)
- `main.py` — FastAPI app, `/chat` SSE endpoint with phase timing events (now also emits `map_data` events and enforces message limits), `/autocomplete`, `/section/{section_id}` (full reassembled municipal-code section, backs clickable cross-references), `/api/map-data` (raw geo-located rows for the map panel), and **`/api/conversations/*`** (7 CRUD endpoints for SQLite-backed conversation persistence)
- `router.py` — Claude-based router producing strict `RetrievalPlan` JSON; system prompt embeds the 77 community-area names + 30+ neighborhood aliases + **search query guidance for zoning-specific terminology**
- `synthesizer.py` — streaming Claude synthesis call with **inline citation markers** (`[1]`, `[2]`) for code chunks
- `conversation.py` — **Multi-turn context synthesis** with improved heuristics for detecting follow-up questions, context references ("their", "it", "what about"), and clarification answers
- `assembler.py` — pure context-merging function with caps (now sourced from `config.py`: `top_crime_types`, `top_311_types`, `top_chunks`, etc.), `Open - Dup` dedup, auto data-lag note, **capped-result detection** (sets `capped=True` when row count hits the `$limit` guard)
- `models.py` — Pydantic types: `RetrievalPlan`, `ContextObject`, `ChatChunk` (with `t_ms` timing), `Message`, `ChatRequest`; all five summary models carry a `capped: bool` flag
- `config.py` — env via pydantic-settings (Anthropic key, Socrata token, Qdrant URL, model/dataset IDs) **plus tuning knobs**: per-LLM `*_max_tokens`, per-source query `*_limit`s, assembler `top_*` caps, `db_path`, `message_limit`
- `db.py` — **SQLite persistence layer** via `aiosqlite`. WAL mode, singleton connection, schema versioning. Tables: `conversations`, `messages` (with `context_json`/`plan_json`/`map_data_json` blob columns), `uploads` (schema-only, future-proofing), `schema_version`. CRUD helpers + bulk import for localStorage migration
- `analytics.py` — **Server-side analytics**: month-over-month trend computation from raw Socrata rows. Groups by year-month + category, skips partial current month, returns `TrendItem` list. Results attached to `ContextObject.analytics` so Claude can cite trends in synthesis
- `llm.py` — single `lru_cache`d `get_anthropic_client()` shared by router/synthesizer/conversation (was three per-request clients)
- `prompts.py` — the three system prompts (`ROUTER_SYSTEM_TEMPLATE`, `SYNTHESIZER_SYSTEM`, `CONVERSATION_SYNTHESIS`), moved out of the logic modules; synthesizer prompt includes capped-result handling rule
- `retrieval/`:
  - `socrata.py` — shared async client with retry/backoff, `X-App-Token`, `$limit` guard, and a `grouped_count()` helper for the repeated top-N aggregation shape
  - `utils.py` — `cutoff_iso()` shared by the dataset wrappers (was three duplicated `_cutoff_iso` helpers)
  - `crime.py` — `ijzp-q8t2` (neighborhood-aggregated + block-level), uses two parallel queries for crime counts + arrest counts (SoQL `case()` doesn't exist)
  - `three11.py` — `v6vf-nfxy` (open requests + response times, `Open - Dup` filtered)
  - `buildings.py` — `ydr8-5enu` permits (uses `reported_cost` field) + `22u3-xenr` violations
  - `business.py` — `uupf-x98q` active licenses
  - `map_data.py` — raw geo-located row fetching for the map panel (`crimes_for_map`, `requests_311_for_map`, `permits_for_map`, `zoning_for_map`); uses `socrata_get` directly with higher row limits (200/150/100) and `latitude IS NOT NULL` filters
  - `vector_search.py` — Qdrant semantic search via raw HTTP API + payload-filter cross-ref expansion, lazy embedder; per-section dedup, keyword boost scoring, cross-encoder reranker (infrastructure present, disabled by default); `get_full_section()` reassembles a whole section from its chunks for the `/section` endpoint
  - `geo.py` — 77 community areas + alias table + Census Geocoder + shapely
- `tests/` — **177 tests** (unit + integration), all passing

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
  - `MessageBubble` (react-markdown, inline citations, copy button, typewriter)
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
  - `sidebar/MapLegend` (compact color legend, auto-hides when no layers active)
  - `DisclaimerBanner` (amber, legal disclaimer)
  - `HistorySidebar` (conversation history)
- `lib/`:
  - `api.ts` (SSE fetch streaming; `fetchSection` with an immutable-section cache; **conversation CRUD functions**: `listConversations`, `getConversation`, `createConversation`, `deleteConversationAPI`, `saveMessages`, `updateMessageMapData`, `importConversations`)
  - `useChat.ts` (owns the SSE consumption loop + per-turn state; lifted out of `App.tsx`; **now accepts `conversationId`**, handles `map_data` SSE events, enforces client-side 10-message limit, exposes `atMessageLimit`)
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
- **Retrieval quality benchmark** — `eval/retrieval_benchmark.py` with **18 user-style queries** evaluating vector search quality: gold section hit rate, section duplication, table fragment detection, grade (A–F). Baseline v3: A=13, B=1, C=4 (no D or F)

---

## What's NOT Done / Known Issues

### 1. ~~Citation tooltip overlaps text (transparent background)~~ — RESOLVED (2026-05-29)
Originally a Tailwind color-name collision (`bg-dark` vs `dark.bg`). After fixing that, tooltip backgrounds were still invisible because `#1f1f1f` had near-zero contrast against the surrounding dark surfaces. Final fix: bumped tooltip to `#333` with `#444` border (via inline style to bypass Tailwind class-ordering issues), switched to `position: fixed` with `useLayoutEffect` viewport clamping so tooltips can't be clipped by the sidebar's `overflow-y: auto`, and strengthened the section-detail drawer backdrop to `bg-black/80 backdrop-blur-sm`.

### 2. ~~Source detail drawer covers sidebar~~ — RESOLVED (2026-05-28)
Source cards now expand **in-place** in `SourceCitation.tsx` (full text shown inline, no height cap). The `SourceDetailDrawer` was repurposed for a different job: viewing the full text of a *cross-referenced* section fetched on demand (see session log).

### 3. ~~Typewriter effect stops after first citation~~ — RESOLVED (2026-05-29)
The `useTypewriter` effect depended on `content.length`, which changes on every SSE token. Each change cleared and recreated the interval, preventing the typewriter from advancing while tokens arrived rapidly. When streaming ended, `setDisplayedLength(content.length)` dumped all remaining text at once. Fix: removed `content.length` from the effect dependency (the interval already reads the target via a ref), added a `wasStreamingRef` so the interval continues after streaming ends until it catches up (instead of dumping), and added adaptive step sizing (1/2/3 chars per tick based on how far behind).

### 4. ~~No annotations for API-sourced data~~ — RESOLVED
Socrata statistics are now marked with `[data:crime]` / `[data:311]` / etc. markers rendered as colored `DataPill` components that open the Data tab and scroll to the relevant card.

### 5. The Municipal Code is gitignored
- `chicago-il-codes.html` (~100MB) is not in version control (`.gitignore` line 17).
- Anyone cloning the repo needs to obtain it separately.

### 6. ~~Map view~~ — RESOLVED (2026-05-31)
Implemented with Mapbox GL JS + deck.gl instead of Leaflet (better WebGL performance, dark basemap support, deck.gl's ScatterplotLayer handles thousands of points efficiently). See session log below.

### 7. Deferred but probably worth doing
- **LLM-as-judge eval** — grade synthesis answers for citation accuracy + factuality
- **Cost/token logging** — wrap the Anthropic client to record tokens per request
- **Deployment** — currently local-only
- ~~**Postgres / server-side history** — for multi-device sync~~ — RESOLVED: SQLite persistence implemented (2026-05-31)
- **File upload support** — `uploads` table exists in SQLite schema but no UI or backend handling yet

### 8. Known fragile heuristics
- **Sub-header detection inside tables** uses length cap (<80 chars) and min-chars threshold (400 chars before splitting)
- **Multi-row header count** inferred from consecutive row patterns
- **Cross-references** filter to section IDs only
- **Keyword boost weight (0.15)** is hand-tuned — too high drowns out semantic similarity, too low has no effect
- **Reranker disabled** — the MS MARCO cross-encoder hurts on legal text; needs a legal-domain model

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

## Recommended Next Steps (Prioritized)

### Step 1 — Legal-domain cross-encoder reranker
The MS MARCO reranker hurt on legal text (see session log). A fine-tuned reranker (e.g., bge-reranker-v2-m3 or a custom model trained on municipal code relevance judgments) would unlock the reranking stage. The infrastructure is already wired — just swap the model name in `config.py` and set `reranker_enabled=True`.

### Step 2 — Test multi-turn conversations thoroughly
The conversation synthesis should now handle follow-ups like "do you have their website?" — verify this works in practice.

### ~~Step 3 — Zoning overlay on map~~ — RESOLVED (2026-05-31)
Replaced the broken Socrata endpoint with ArcGIS MapServer. Zoning polygons now render on the map with per-district colors, hover/click interaction, and Zoning/Points toggle controls. The old `VITE_ENABLE_ZONING_LAYER` env var is no longer needed.

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
4. **Files most likely to need edits**:
   - `frontend/src/components/MessageBubble.tsx` — typewriter/citation interaction (Issue #3)
   - `frontend/src/lib/useTypewriter.ts` — animation timing
   - `frontend/src/components/CrossRefPill.tsx` / `SourceDetailDrawer.tsx` — cross-reference behavior
   - `backend/retrieval/vector_search.py` — `get_full_section` / cross-ref resolution

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
├── backend/
│   ├── main.py                     # FastAPI /chat (SSE w/ t_ms timing) + /api/conversations/* CRUD
│   ├── router.py                   # Claude router (with search query guidance)
│   ├── synthesizer.py              # Claude streaming synth (with citation markers + analytics)
│   ├── conversation.py             # Multi-turn context synthesis (improved heuristics)
│   ├── assembler.py                # Pure (pytest-covered)
│   ├── analytics.py                # Server-side MoM trend computation for synthesis
│   ├── db.py                       # SQLite persistence (aiosqlite, WAL, schema versioning)
│   ├── models.py
│   ├── config.py
│   ├── data/                       # SQLite database (gitignored)
│   ├── retrieval/                  # socrata.py + per-dataset wrappers + geo.py + vector_search.py + map_data.py + zoning.py
│   └── tests/                      # 192 tests (unit + integration)
├── ingestion/
│   ├── data/                       # Generated: sections/, chunks.jsonl, community_areas.geojson
│   ├── parse_chicago_code.py       # HTML → sections JSON, --stats flag
│   ├── chunk.py                    # sections → chunks.jsonl
│   ├── embed_and_store.py          # chunks → Qdrant
│   └── load_community_areas.py     # CA polygons → GeoJSON
├── eval/
│   ├── queries.json                # 26 test queries
│   ├── run_eval.py                 # --router-only | --full <URL>
│   ├── retrieval_benchmark.py      # 18-query retrieval quality benchmark
│   ├── baseline_router.md          # Router-only results
│   └── baseline_full_v2.md         # Full pipeline results (26/26 passing)
└── frontend/
    ├── src/components/             # Hero, ChatInput, MessageBubble, CitationPill, SourceCitation, Sidebar, etc.
    │   └── sidebar/                # MapView, MapLayerToggles, MapLegend, ArrestFilter, DateRangeSlider,
    │                               #   DataView, AnalyticsSection, PieChart, TrendTable, SourcesView
    ├── src/lib/                    # api (SSE), history (API-backed), types, useTypewriter, clipboard,
    │                               #   mapColors (shared color constants), analytics (trend/pie computation),
    │                               #   useConversationRouter (URL ↔ state sync)
    └── src/App.tsx                 # State machine with per-message context + URL routing
```

## Quick Reference — Useful Commands

```bash
# Tests + builds
source .venv/bin/activate
python -m pytest backend/tests/ -q           # 192 tests
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
python -m eval.retrieval_benchmark --out eval/retrieval_quality.md  # Vector search quality

# Backend + frontend dev
docker compose up -d qdrant
uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                              # :5173

# Smoke-test /chat
curl -N -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```
