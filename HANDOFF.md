# Project Handoff — Chicago City Intelligence

A snapshot of what's been built, the decisions behind it, and what should come next. Companion to `README.md` (user-facing setup) and `~/.claude/plans/velvet-gliding-salamander.md` (the original implementation plan).

---

## TL;DR

A RAG-powered chat interface for natural-language questions about Chicago. Combines live Chicago Data Portal (Socrata) data with semantic search over the entire Chicago Municipal Code. Single killer query: *"What's going on near 2400 N Milwaukee Ave?"* → a unified response covering crime, 311, building activity, business licenses, and applicable zoning, all from one prompt.

**Current status (2026-05-29):** Full pipeline operational. Ingestion complete (14,628 chunks in Qdrant). Eval suite passes 26/26 queries (100%). Multi-turn conversation synthesis added. Chat UI significantly improved with per-message citation binding, typewriter effects, and source preview tooltips. The context/data sidebar was redesigned — citations now render as the actual `§` section reference, cross-references are clickable and open a full-section viewer. Most recent work: **sidebar polish + tooltip/background fixes** — sidebar rewritten with a drag-to-resize handle and a collapsed rail; table chunks now render as formatted HTML tables; tooltip backgrounds are solid `#333` with `#444` borders and use `position: fixed` with viewport clamping so they can't be clipped by the sidebar's overflow container; the section-detail drawer has a stronger `bg-black/80 backdrop-blur-sm` overlay. Previous: **capped-result awareness** — Socrata `$limit` guards detected and surfaced so the LLM says "at least N" instead of exact counts.

---

## Stack (Locked)

| Layer | Choice | Reasoning |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-first, OpenAPI for free, easy SSE |
| LLM | Anthropic Claude **Sonnet 4.6** (`claude-sonnet-4-6`) for both router and synthesizer | Latest non-Opus model, better tool-use, structured output reliability |
| Vector DB | **Qdrant v1.9.0** (Docker, self-hosted) | Free, fast, good metadata filtering, payload search supports cross-ref lookup |
| Embeddings | **`BAAI/bge-small-en-v1.5`** via sentence-transformers (local, 384-dim, 512-token context) | Originally chose MiniLM-L6 (256-token context, too small for legal sections); upgraded during Title-17 work. Same dim → Qdrant config unchanged |
| Streaming | **SSE** (`text/event-stream`) | Synthesizer is the slow part (~3–8s); streaming TTFT is much better UX |
| Chat memory | **Multi-turn from day one**, history in client `localStorage`, server is stateless | Simplest persistence model, scales |
| Geocoding | **Census Geocoder** (free, no key) + shapely point-in-polygon against cached community-area polygons | No rate limit, no API key, deterministic |
| Frontend | **React + TypeScript + Vite + Tailwind v3** | Type-safe contract with FastAPI Pydantic via OpenAPI |
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
- `main.py` — FastAPI app, `/chat` SSE endpoint with phase timing events, `/autocomplete`, and `/section/{section_id}` (full reassembled municipal-code section, backs clickable cross-references)
- `router.py` — Claude-based router producing strict `RetrievalPlan` JSON; system prompt embeds the 77 community-area names + 30+ neighborhood aliases + **search query guidance for zoning-specific terminology**
- `synthesizer.py` — streaming Claude synthesis call with **inline citation markers** (`[1]`, `[2]`) for code chunks
- `conversation.py` — **Multi-turn context synthesis** with improved heuristics for detecting follow-up questions, context references ("their", "it", "what about"), and clarification answers
- `assembler.py` — pure context-merging function with caps (now sourced from `config.py`: `top_crime_types`, `top_311_types`, `top_chunks`, etc.), `Open - Dup` dedup, auto data-lag note, **capped-result detection** (sets `capped=True` when row count hits the `$limit` guard)
- `models.py` — Pydantic types: `RetrievalPlan`, `ContextObject`, `ChatChunk` (with `t_ms` timing), `Message`, `ChatRequest`; all five summary models carry a `capped: bool` flag
- `config.py` — env via pydantic-settings (Anthropic key, Socrata token, Qdrant URL, model/dataset IDs) **plus tuning knobs**: per-LLM `*_max_tokens`, per-source query `*_limit`s, and assembler `top_*` caps
- `llm.py` — single `lru_cache`d `get_anthropic_client()` shared by router/synthesizer/conversation (was three per-request clients)
- `prompts.py` — the three system prompts (`ROUTER_SYSTEM_TEMPLATE`, `SYNTHESIZER_SYSTEM`, `CONVERSATION_SYNTHESIS`), moved out of the logic modules; synthesizer prompt includes capped-result handling rule
- `retrieval/`:
  - `socrata.py` — shared async client with retry/backoff, `X-App-Token`, `$limit` guard, and a `grouped_count()` helper for the repeated top-N aggregation shape
  - `utils.py` — `cutoff_iso()` shared by the dataset wrappers (was three duplicated `_cutoff_iso` helpers)
  - `crime.py` — `ijzp-q8t2` (neighborhood-aggregated + block-level), uses two parallel queries for crime counts + arrest counts (SoQL `case()` doesn't exist)
  - `three11.py` — `v6vf-nfxy` (open requests + response times, `Open - Dup` filtered)
  - `buildings.py` — `ydr8-5enu` permits (uses `reported_cost` field) + `22u3-xenr` violations
  - `business.py` — `uupf-x98q` active licenses
  - `vector_search.py` — Qdrant semantic search via raw HTTP API + payload-filter cross-ref expansion, lazy embedder; `get_full_section()` reassembles a whole section from its chunks for the `/section` endpoint
  - `geo.py` — 77 community areas + alias table + Census Geocoder + shapely
- `tests/` — **130+ tests** (unit + integration), all passing

### Ingestion (`ingestion/`)
- `parse_chicago_code.py` — HTML parser with split-at-republication strategy, state machine for Title→Chapter→Article→Subarticle→Part, colspan/rowspan-aware table extraction with composite multi-row headers
- `chunk.py` — section-aware chunking with hierarchical header re-duplication, table flattening to `Row N: header=value`, sub-section splits inside tables at category boundaries (`A. Household Living`, `PUBLIC AND CIVIC`)
- `embed_and_store.py` — sentence-transformers + Qdrant upsert to two collections (`chicago_municipal_code`, `chicago_zoning` for Title 17 filter-free)
- `load_community_areas.py` — fetches and caches community-area polygons from Socrata `igwz-8jzy` as GeoJSON
- **Pipeline fully run**: 8,615 sections → 14,628 chunks → Qdrant (took ~3 minutes with MPS acceleration)

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
  - `SidebarPanel` (collapsible context/data panel with drag-to-resize handle and collapsed rail)
  - `DisclaimerBanner` (amber, legal disclaimer)
  - `HistorySidebar` (conversation history)
- `lib/`:
  - `api.ts` (SSE fetch streaming; `fetchSection` with an immutable-section cache)
  - `useChat.ts` (owns the SSE consumption loop + per-turn state; lifted out of `App.tsx`)
  - `sse.ts` (reusable `parseSSE` generator used by `api.ts`)
  - `useCopyButton.ts` (shared copy-to-clipboard hook with transient "copied" flag)
  - `constants.ts` (SUGGESTIONS, splash stats, and the magic timers/thresholds)
  - `history.ts` (localStorage conversations)
  - `types.ts` (matches backend Pydantic, extended with per-message context; single source of `Conversation`)
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

---

## What's NOT Done / Known Issues

### 1. ~~Citation tooltip overlaps text (transparent background)~~ — RESOLVED (2026-05-29)
Originally a Tailwind color-name collision (`bg-dark` vs `dark.bg`). After fixing that, tooltip backgrounds were still invisible because `#1f1f1f` had near-zero contrast against the surrounding dark surfaces. Final fix: bumped tooltip to `#333` with `#444` border (via inline style to bypass Tailwind class-ordering issues), switched to `position: fixed` with `useLayoutEffect` viewport clamping so tooltips can't be clipped by the sidebar's `overflow-y: auto`, and strengthened the section-detail drawer backdrop to `bg-black/80 backdrop-blur-sm`.

### 2. ~~Source detail drawer covers sidebar~~ — RESOLVED (2026-05-28)
Source cards now expand **in-place** in `SourceCitation.tsx` (full text shown inline, no height cap). The `SourceDetailDrawer` was repurposed for a different job: viewing the full text of a *cross-referenced* section fetched on demand (see session log).

### 3. Typewriter effect stops after first citation
The typewriter animation works initially but dumps remaining text all at once after the first `[1]` citation appears. **Root cause:** The `renderChildrenWithCitations` function in `MessageBubble.tsx` may be causing re-renders that reset the typewriter state. Needs investigation.

### 4. ~~No annotations for API-sourced data~~ — RESOLVED
Socrata statistics are now marked with `[data:crime]` / `[data:311]` / etc. markers rendered as colored `DataPill` components that open the Data tab and scroll to the relevant card.

### 5. The Municipal Code is gitignored
- `chicago-il-codes.html` (~100MB) is not in version control (`.gitignore` line 17).
- Anyone cloning the repo needs to obtain it separately.

### 6. Stretch goals (Phase I)
- **Leaflet map view** showing crime pins, 311 markers, zoning overlay. *Not started.*

### 7. Deferred but probably worth doing
- **LLM-as-judge eval** — grade synthesis answers for citation accuracy + factuality
- **Cost/token logging** — wrap the Anthropic client to record tokens per request
- **Deployment** — currently local-only
- **Postgres / server-side history** — for multi-device sync

### 8. Known fragile heuristics
- **Sub-header detection inside tables** uses length cap (<80 chars)
- **Multi-row header count** inferred from consecutive row patterns
- **Cross-references** filter to section IDs only

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

## Recommended Next Steps (Prioritized)

### Step 1 — Debug typewriter + citations interaction
Investigate why typewriter effect stops working after first citation. May need to memoize citation processing or adjust how content is passed to the hook. (Issue #3 — still open.)

### Step 2 — Decide how to handle un-resolvable cross-references
Some cross-refs point to sections not in the corpus and return 404 (handled gracefully today as "not available"). Options: hide them rather than render clickable, or investigate why those sections are missing from ingestion.

### Step 3 — Test multi-turn conversations thoroughly
The conversation synthesis should now handle follow-ups like "do you have their website?" — verify this works in practice.

### Step 4 — Stretch: Leaflet map view
Crime pins, 311 markers, zoning overlay. Not started.

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
3. **Verify env**: `.env` should have `ANTHROPIC_API_KEY` and `SOCRATA_APP_TOKEN` set
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
│   ├── main.py                     # FastAPI /chat (SSE w/ t_ms timing)
│   ├── router.py                   # Claude router (with search query guidance)
│   ├── synthesizer.py              # Claude streaming synth (with citation markers)
│   ├── conversation.py             # Multi-turn context synthesis (improved heuristics)
│   ├── assembler.py                # Pure (pytest-covered)
│   ├── models.py
│   ├── config.py
│   ├── retrieval/                  # socrata.py + per-dataset wrappers + geo.py + vector_search.py
│   └── tests/                      # 130+ tests (unit + integration)
├── ingestion/
│   ├── data/                       # Generated: sections/, chunks.jsonl, community_areas.geojson
│   ├── parse_chicago_code.py       # HTML → sections JSON, --stats flag
│   ├── chunk.py                    # sections → chunks.jsonl
│   ├── embed_and_store.py          # chunks → Qdrant
│   └── load_community_areas.py     # CA polygons → GeoJSON
├── eval/
│   ├── queries.json                # 26 test queries
│   ├── run_eval.py                 # --router-only | --full <URL>
│   ├── baseline_router.md          # Router-only results
│   └── baseline_full_v2.md         # Full pipeline results (26/26 passing)
└── frontend/
    ├── src/components/             # Hero, ChatInput, MessageBubble, CitationPill, SourceCitation, Sidebar, etc.
    ├── src/lib/                    # api (SSE), history (localStorage), types, useTypewriter, clipboard
    └── src/App.tsx                 # State machine with per-message context
```

## Quick Reference — Useful Commands

```bash
# Tests + builds
source .venv/bin/activate
python -m pytest backend/tests/ -q           # 130+ tests
python -m pytest backend/tests/test_integration.py -v  # Real API tests
cd frontend && npm run build

# Parser sanity check (no JSON output)
python -m ingestion.parse_chicago_code --stats

# Full ingestion pipeline (only needed if Qdrant data is lost)
docker compose up -d qdrant
python -m ingestion.load_community_areas
python -m ingestion.parse_chicago_code
python -m ingestion.chunk
python -m ingestion.embed_and_store

# Eval
PYTHONPATH=. python -m eval.run_eval --filter zoning
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --out eval/last.md

# Backend + frontend dev
docker compose up -d qdrant
uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev                              # :5173

# Smoke-test /chat
curl -N -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What kind of crime is happening in Wicker Park?","history":[]}'
```
