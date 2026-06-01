import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const SECTIONS = [
  { id: "overview", title: "Project Overview" },
  { id: "architecture", title: "Architecture" },
  { id: "data-layer", title: "Data Layer" },
  { id: "document-processing", title: "Document Processing" },
  { id: "vector-search", title: "Vector Search Pipeline" },
  { id: "router", title: "LLM Router" },
  { id: "synthesis", title: "Streaming Synthesis" },
  { id: "conversation", title: "Conversation Management" },
  { id: "map", title: "Map & Geo Visualization" },
  { id: "analytics", title: "Analytics" },
  { id: "admin", title: "Admin & Observability" },
  { id: "eval", title: "Eval & Benchmarks" },
  { id: "frontend", title: "Frontend Architecture" },
  { id: "testing", title: "Testing" },
  { id: "decisions", title: "Design Decisions" },
  { id: "scale", title: "At Scale" },
];

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-2xl font-semibold text-text-primary tracking-tight scroll-mt-20 pt-12 pb-4">
      {children}
    </h2>
  );
}

function Sub({ children }: { children: React.ReactNode }) {
  return <h3 className="text-lg font-semibold text-text-primary mt-8 mb-3">{children}</h3>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-text-secondary leading-relaxed mb-4">{children}</p>;
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="rounded-lg bg-dark-elevated border border-dark-border p-4 overflow-x-auto text-sm font-mono text-text-secondary mb-4">
      {children}
    </pre>
  );
}

function Accent({ children }: { children: React.ReactNode }) {
  return <span className="text-accent font-medium">{children}</span>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return <code className="text-sm bg-dark-elevated px-1.5 py-0.5 rounded font-mono text-text-primary">{children}</code>;
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-dark-border mb-4">
      <table className="w-full text-sm">
        <thead className="bg-dark-elevated">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-text-primary font-medium whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-border">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-dark-surface/50">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5 text-text-secondary whitespace-nowrap">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WideTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-dark-border mb-4">
      <table className="w-full text-sm">
        <thead className="bg-dark-elevated">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-text-primary font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-border">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-dark-surface/50">
              {row.map((cell, j) => (
                <td key={j} className={`px-4 py-2.5 text-text-secondary ${j === 0 ? "whitespace-nowrap font-medium" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AboutPage() {
  const [activeSection, setActiveSection] = useState("overview");
  const [tocOpen, setTocOpen] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );

    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setTocOpen(false);
  };

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      {/* Header */}
      <header className="h-14 border-b border-dark-border flex items-center px-6 sticky top-0 z-30 bg-dark-bg/95 backdrop-blur-sm">
        <h1 className="text-lg font-semibold tracking-tight">
          <Link to="/" className="text-accent hover:text-accent-hover transition-colors">UrbanLayer</Link>
          <span className="text-text-muted ml-2">About</span>
        </h1>
      </header>

      {/* Mobile TOC toggle */}
      <div className="lg:hidden sticky top-14 z-20 bg-dark-bg border-b border-dark-border">
        <button
          onClick={() => setTocOpen(!tocOpen)}
          className="w-full flex items-center justify-between px-6 py-3 text-sm text-text-secondary"
        >
          <span>{SECTIONS.find((s) => s.id === activeSection)?.title ?? "Overview"}</span>
          <svg
            className={`w-4 h-4 transition-transform ${tocOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {tocOpen && (
          <nav className="border-t border-dark-border bg-dark-surface px-6 py-3 max-h-[60vh] overflow-y-auto">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                className={`block w-full text-left py-1.5 text-sm transition-colors ${
                  activeSection === s.id ? "text-accent" : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {s.title}
              </button>
            ))}
          </nav>
        )}
      </div>

      <div className="max-w-6xl mx-auto flex">
        {/* Desktop sidebar TOC */}
        <nav className="hidden lg:block w-56 shrink-0 sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto py-8 pr-6 pl-6">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Contents</p>
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`block w-full text-left py-1.5 text-sm transition-colors ${
                activeSection === s.id
                  ? "text-accent font-medium"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {s.title}
            </button>
          ))}
        </nav>

        {/* Content */}
        <article className="flex-1 min-w-0 py-4 px-4 md:px-6 lg:pl-8 lg:pr-12 pb-32">

          {/* ── 1. Project Overview ── */}
          <SectionHeading id="overview">Project Overview</SectionHeading>
          <P>
            UrbanLayer is a retrieval-augmented generation (RAG) system for natural-language questions about Chicago.
            It combines <Accent>live city data</Accent> from 8 Socrata API endpoints, <Accent>semantic search</Accent> over
            the entire Chicago Municipal Code (14,535 vector-indexed chunks), and <Accent>LLM synthesis</Accent> via
            Claude Sonnet to produce sourced, cited answers with interactive map visualizations.
          </P>
          <P>
            The killer query: <em>"What's going on near 2400 N Milwaukee Ave?"</em> A single prompt triggers parallel
            retrieval across crime statistics, open 311 service requests, building permits, code violations, business
            licenses, and applicable zoning — then synthesizes everything into a coherent response with inline citations,
            month-over-month trend analysis, and a map with filterable data layers.
          </P>
          <P>
            What makes this different from querying APIs directly: the system resolves addresses to community areas via
            Census geocoding, fetches from multiple datasets concurrently, applies domain-specific aggregation and capping,
            computes analytics, and uses an LLM to synthesize a human-readable answer that cites its sources. A user
            would need to make 6+ API calls, understand SoQL, and cross-reference zoning codes to replicate one query.
          </P>

          {/* ── 2. Architecture ── */}
          <SectionHeading id="architecture">Architecture</SectionHeading>
          <P>
            Three-layer RAG architecture. Each layer serves a distinct retrieval need: recent structured data (Socrata APIs),
            static legal text (vector search over municipal code), and natural-language reasoning (LLM synthesis).
          </P>
          <Code>{`User Message
  │
  ▼
┌───────────────────────────┐
│  Conversation Synthesis   │  Haiku — 300 tok budget
│  (multi-turn expansion)   │  Detects follow-ups, stitches context
└─────────┬─────────────────┘
          ▼
┌───────────────────────────┐
│  LLM Router               │  Sonnet — 600 tok budget
│  → RetrievalPlan JSON     │  Sources, location, intent, search_query
└─────────┬─────────────────┘
          ▼
┌───────────────────────────┐
│  Parallel Retrieval       │  asyncio.gather()
│  ├─ Socrata (crime, 311,  │  5 datasets, row-limited
│  │   permits, violations, │
│  │   business)            │
│  ├─ Qdrant Vector Search  │  14,535 chunks, bge-base-en-v1.5
│  ├─ ArcGIS Zoning         │  Point lookup + polygon fetch
│  └─ Map Data              │  Raw geo-located rows (2500/1000/500)
└─────────┬─────────────────┘
          ▼
┌───────────────────────────┐
│  Context Assembly         │  Aggregation, capping, dedup
│  + Analytics              │  Month-over-month trends
└─────────┬─────────────────┘
          ▼
┌───────────────────────────┐
│  Streaming Synthesis      │  Sonnet — 2000 tok budget
│  SSE: plan → context →    │  Inline citations, trend weaving
│  map_data → tokens → done │
└───────────────────────────┘`}</Code>

          <Sub>Stack</Sub>
          <Table
            headers={["Layer", "Technology", "Rationale"]}
            rows={[
              ["Backend", "Python 3.11 + FastAPI", "Async-first, SSE streaming, OpenAPI for free"],
              ["LLM", "Claude Sonnet 4.6 (router + synth)", "Best tool-use and structured output reliability"],
              ["Conversation", "Claude Haiku 4.5", "Cheap multi-turn expansion (300 tok)"],
              ["Vector DB", "Qdrant v1.9.0 (Docker)", "Free, fast, metadata filtering, payload search"],
              ["Embeddings", "BAAI/bge-base-en-v1.5 (768-dim)", "Better legal text discrimination than bge-small"],
              ["Reranker", "BAAI/bge-reranker-v2-m3", "Same family as embeddings, avoids MS MARCO domain mismatch"],
              ["Streaming", "SSE (text/event-stream)", "Synthesis is 3-8s; streaming TTFT is better UX"],
              ["Persistence", "SQLite via aiosqlite (WAL)", "Single user, single writer — simplest correct solution"],
              ["Frontend", "React + TypeScript + Vite + Tailwind v3", "Type-safe, dark theme, fast builds (~322KB JS)"],
              ["Map", "Mapbox GL JS + deck.gl", "WebGL handles 1000s of points, declarative layers"],
              ["Geocoding", "Census Geocoder + Shapely", "Free, no API key, deterministic"],
            ]}
          />

          {/* ── 3. Data Layer ── */}
          <SectionHeading id="data-layer">Data Layer</SectionHeading>

          <Sub>Socrata Datasets</Sub>
          <P>
            All structured data comes from the Chicago Data Portal via SoQL queries. Each query carries a
            mandatory <Mono>$limit</Mono> guard to prevent unbounded fetches. The shared client
            in <Mono>socrata.py</Mono> enforces this — a missing limit raises <Mono>ValueError</Mono>.
            Retry logic: 3 attempts with exponential backoff (0.5s, 1s, 2s) for 5xx errors.
          </P>
          <Table
            headers={["Dataset", "ID", "Use", "Chat Limit", "Map Limit"]}
            rows={[
              ["Crimes 2001–Present", "ijzp-q8t2", "Crime patterns, arrest rates", "35", "2,500"],
              ["311 Service Requests", "v6vf-nfxy", "Quality-of-life complaints", "50", "1,000"],
              ["Building Permits", "ydr8-5enu", "Development activity, costs", "500", "500"],
              ["Building Violations", "22u3-xenr", "Property condition", "50", "—"],
              ["Business Licenses", "uupf-x98q", "Neighborhood character", "100", "—"],
              ["Community Areas", "igwz-8jzy", "Address → CA polygons", "—", "—"],
              ["IUCR Codes", "c7ck-438e", "Crime code translation", "—", "—"],
              ["Zoning Districts", "ArcGIS MapServer", "Point lookup + polygons", "—", "200-600"],
            ]}
          />
          <P>
            Two separate row limits exist because the chat context needs <em>aggregated summaries</em> (top-5 crime types =
            10 tokens) while the map needs <em>individual geo-located rows</em> for plotting. Map limits (2,500 crime)
            cover ~90 days in busy community areas — the original 200-row limit only covered ~7 days.
          </P>

          <Sub>Capped-Result Detection</Sub>
          <P>
            When <Mono>len(rows) {">="} limit</Mono>, the assembler sets <Mono>capped: true</Mono> on that summary.
            The synthesizer prompt instructs Claude to say "at least N" instead of stating N as an exact count.
            This prevents misleading statements like "50 building permits issued" when 50 is actually the query cap.
          </P>

          <Sub>ArcGIS Zoning</Sub>
          <P>
            The Socrata zoning dataset (<Mono>p8va-airx</Mono>) is non-queryable — its <Mono>.geojson</Mono> and
            JSON endpoints both return errors. Instead, the city's public ArcGIS Zoning MapServer at{" "}
            <Mono>gisapps.chicago.gov</Mono> is used. No API key required, no observed rate limit. Supports both
            point queries (resolve a lat/lon to a zone class like "RM-6") and envelope queries (fetch all
            200-600 zoning polygons for a community area's bounding box). Native SRS is EPSG:3435 (IL State Plane East),
            reprojected to WGS84 via <Mono>outSR=4326</Mono>.
          </P>

          <Sub>Geocoding</Sub>
          <P>
            Census Geocoder (free, no key, deterministic) + Shapely point-in-polygon against cached community area
            polygons. 77 community areas + 30+ hardcoded neighborhood aliases (e.g., "Wicker Park" → CA 24,
            "Boystown" → CA 6, "The Loop" → CA 32). Aliases are stable enough that hardcoding is preferable
            to a network lookup.
          </P>

          {/* ── 4. Document Processing ── */}
          <SectionHeading id="document-processing">Document Processing</SectionHeading>
          <P>
            Source: <Mono>chicago-il-codes.html</Mono>, a ~100MB HTML export from American Legal Publishing
            containing the full Chicago Municipal Code (Titles 1-18). Gitignored due to size.
          </P>
          <Code>{`HTML (100MB) → parse → 8,615 sections → chunk → 14,535 chunks → embed → Qdrant
                                                                       ↓
                                                              bge-base-en-v1.5 (768-dim)
                                                              ~3 minutes with MPS acceleration`}</Code>

          <Sub>Parsing</Sub>
          <P>
            BeautifulSoup state machine tracking Title → Chapter → Article → Subarticle → Part → Section hierarchy.
            Table extraction handles colspan/rowspan and composite multi-row headers. Cross-references extracted via regex.
          </P>
          <P>
            The HTML has a malformed <Mono>&lt;div&gt;</Mono> in Title 18 that causes lxml to silently nest the
            trailing ~8MB (the republished Titles 16/17 "Zoning & Land Use Ordinance") inside an earlier element.
            Without the fix, 250 republished sections and 1 net-new section were missing. Workaround: split the
            file at the republication banner string and parse each half separately.
          </P>

          <Sub>Chunking</Sub>
          <P>
            Section-aware chunking with hierarchical header re-duplication — every chunk includes the
            full Title → Chapter → Section breadcrumb so it's interpretable standalone. Critical for legal text
            where cross-references matter.
          </P>
          <P>
            Table-aware processing flattens tables to <Mono>Row N: header=value</Mono> format for embedding.
            Sub-header splits are deferred when the current block is under 400 chars (<Mono>TABLE_BLOCK_MIN_CHARS</Mono>),
            preventing fragmentation into ~200-char table blocks. A merge pass consolidates consecutive small
            <Mono>[TABLE]</Mono> pieces. This reduced chunk count from 14,628 to 14,535 and dropped
            17-10-0200 (parking table) from 26 to 22 chunks.
          </P>

          {/* ── 5. Vector Search Pipeline ── */}
          <SectionHeading id="vector-search">Vector Search Pipeline</SectionHeading>

          <Sub>Embedding Model Evolution</Sub>
          <Table
            headers={["Model", "Dimensions", "Context", "Issue"]}
            rows={[
              ["MiniLM-L6-v2", "384", "256 tokens", "Too short for legal text, missed long subsections"],
              ["bge-small-en-v1.5", "384", "512 tokens", "Confused similar terms across contexts (deck→canopy, bakery→shared kitchen)"],
              ["bge-base-en-v1.5", "768", "512 tokens", "Better semantic discrimination, query prefix for asymmetric retrieval"],
            ]}
          />
          <P>
            BGE query prefix (<Mono>"Represent this sentence for searching relevant passages: "</Mono>) enables
            asymmetric retrieval — documents encoded without prefix, queries with it. Cold start goes from ~5s to ~8s;
            query latency unchanged.
          </P>

          <Sub>Full Pipeline (v4)</Sub>
          <Code>{`query
  → prepend BGE query prefix
  → encode with bge-base (768-dim)                        [thread pool]
  → Qdrant async dense search (limit = top_k × 5)
  → filter legend-only table chunks
  → keyword boost: combined = 0.85 × dense + 0.15 × keyword_overlap
  → cross-encoder rerank ALL candidates                   [thread pool]
  → blend: final = 0.80 × norm_dense + 0.20 × norm_reranker
  → sort by blended score
  → per-section dedup (keep best chunk per section)
  → cross-reference expansion (1-hop, batched Qdrant call)
  → return top_k CodeChunks`}</Code>

          <Sub>Score Blending Rationale</Sub>
          <P>
            <Accent>Keyword boost (0.15)</Accent>: catches exact-term relevance that embeddings miss. "Lot coverage" matching
            a chunk about lot coverage percentages instead of lot area standards.
          </P>
          <P>
            <Accent>Reranker weight (0.20)</Accent>: preserves the proven dense+keyword signal while using the cross-encoder
            as refinement. Weight tuned via benchmark: 0.50 regressed <Mono>setback_single_family</Mono>, 0.35
            regressed <Mono>minimum_lot_size</Mono>, 0.20 was the sweet spot.
          </P>

          <Sub>Why MS MARCO Was Rejected</Sub>
          <P>
            <Mono>cross-encoder/ms-marco-MiniLM-L-6-v2</Mono> is trained on web search (MS MARCO = Bing queries).
            Municipal code has different relevance signals — a chunk about "home occupations" is relevant to
            "Can I run a bakery from my home?" even though it never mentions "bakery." MS MARCO over-indexes on
            keyword overlap. With MS MARCO enabled, grades dropped from A=11 to A=9 D=2 F=2. Replaced
            with <Mono>bge-reranker-v2-m3</Mono> (same BGE family as the embedding model).
          </P>

          <Sub>Why Rerank Before Dedup</Sub>
          <P>
            The v3 pipeline deduped to 20 unique sections first, then reranked those 20. This meant the reranker was
            stuck with whatever chunk the dense embedding liked most per section. The v4 pipeline reranks ALL ~60
            candidate chunks first, then dedup picks the best-scoring chunk per section after blending. This lets
            the reranker choose a better chunk from multi-part sections (e.g., selecting the chunk
            with "square feet" from the lot area table instead of the table legend).
          </P>

          <Sub>Per-Section Deduplication</Sub>
          <P>
            Long sections like 17-2-0300 (27 chunks) and 2-44-080 (30 chunks) dominated results because multiple
            chunks embed similarly. For "affordable housing," all 5 results came from just 2 sections.
            Dedup keeps only the highest-scoring chunk per section. Overfetch bumped from 3x to 5x to compensate
            for the higher skip rate.
          </P>

          <Sub>Cross-Reference Expansion</Sub>
          <P>
            One-hop expansion: for each returned chunk, fetch referenced sections via a single batched Qdrant
            scroll request using <Mono>should</Mono> (OR) filters. Replaces up to 15 serial HTTP calls with 1.
            Cross-ref scores capped at <Mono>min(chunk.score, 0.5)</Mono> to prioritize primary results.
            Only section IDs matching <Mono>{"^\\d+[A-Za-z]?-\\d+-\\d+"}</Mono> are expanded — skips
            "Title17", "Ch.17-2", etc. Backend filters cross-refs against a cached set of known section IDs
            (scrolled from Qdrant once, ~8,600 unique sections).
          </P>

          {/* ── 6. LLM Router ── */}
          <SectionHeading id="router">LLM Router</SectionHeading>
          <P>
            Claude Sonnet produces a structured <Mono>RetrievalPlan</Mono> JSON from the user message.
            600-token budget. The system prompt embeds the full 77 community area names + 30+ aliases
            and detailed search query guidance.
          </P>

          <Sub>Output Schema</Sub>
          <Code>{`{
  "sources": ["crime_api", "311_api", "vector_search", ...],
  "location": {
    "raw": "2400 N Milwaukee Ave",
    "type": "address",
    "resolved_community_area": 22,
    "resolved_address": "2400 N Milwaukee Ave, Chicago, IL",
    "resolved_lat": 41.9267,
    "resolved_lon": -87.6973
  },
  "intent": "neighborhood_overview",
  "time_range_days": 90,
  "requires_disclaimer": false,
  "search_query": "zoning permitted uses residential district"
}`}</Code>

          <Sub>Intent Types</Sub>
          <Table
            headers={["Intent", "Sources Triggered", "Example"]}
            rows={[
              ["neighborhood_overview", "crime + 311 + permits + vector", "\"What's happening in Wicker Park?\""],
              ["incident_lookup", "crime + vector", "\"Crime near this address?\""],
              ["legal_question", "vector_search", "\"Can I build a coach house in RS-3?\""],
              ["event_query", "permits or 311", "\"Building permits in Logan Square?\""],
              ["trend_analysis", "crime + analytics", "\"Is crime up or down?\""],
              ["clarification_needed", "none (emits question)", "No location provided"],
            ]}
          />

          <Sub>Search Query Guidance</Sub>
          <P>
            The router prompt contains specific rewriting rules for the vector search query — not just for zoning
            but across the full municipal code. Examples: "Can I run a bakery from my home?" → search "home occupation
            rules"; "How tall can my fence be?" → search "accessory structures setback residential" (not just "fence").
            This is an alternative to reranking — guide the query at routing time rather than trying to fix
            retrieval after the fact.
          </P>

          <Sub>Location Resolution Chain</Sub>
          <Code>{`1. LLM parses location.resolved_community_area from message
2. Fallback: community_area_by_name() — exact match against 77 CA names + aliases
3. If type == "address": Census Geocoder → (lat, lon)
4. Shapely point-in-polygon → community area integer (1-77)
5. Store resolved_lat/lon for ArcGIS zoning lookup + map pin`}</Code>

          {/* ── 7. Streaming Synthesis ── */}
          <SectionHeading id="synthesis">Streaming Synthesis</SectionHeading>
          <P>
            Claude Sonnet with a 2,000-token budget. Streams via SSE (<Mono>text/event-stream</Mono>). Every event
            carries <Mono>t_ms</Mono> (milliseconds since request received) for per-phase latency tracking.
          </P>

          <Sub>SSE Event Types</Sub>
          <Table
            headers={["Event", "Payload", "Purpose"]}
            rows={[
              ["plan", "RetrievalPlan JSON", "Frontend shows intent, opens sidebar"],
              ["context", "ContextObject JSON", "Citation data, sidebar content"],
              ["map_data", "MapDataResponse JSON", "Inline map data (no separate fetch)"],
              ["token", "text string", "Streaming synthesis text"],
              ["error", "error message", "MESSAGE_LIMIT_REACHED or exception"],
              ["done", "final metadata", "Attach context/plan/mapData to message"],
            ]}
          />

          <Sub>Citation System</Sub>
          <P>
            <Accent>Code chunks</Accent> cited with <Mono>[1]</Mono>, <Mono>[2]</Mono> etc. (1-indexed
            into <Mono>context.code_chunks</Mono>). Frontend renders these as clickable <Mono>{"§ <section>"}</Mono> pills
            with hover tooltips showing section title + 150-char preview. Clicking opens the sources sidebar,
            scrolls to and auto-expands the source, plays a flash animation.
          </P>
          <P>
            <Accent>API data</Accent> cited with <Mono>[data:crime]</Mono>, <Mono>[data:311]</Mono>, etc.
            Clicking switches sidebar to the Data tab.
          </P>

          <Sub>Synthesis Rules</Sub>
          <P>
            The system prompt enforces: always cite inline (never end-of-message); surface 7-day crime data lag;
            use "at least N" for capped results; append legal disclaimer when <Mono>requires_disclaimer</Mono> is
            true; weave the 2-4 most notable month-over-month trends naturally; state zoning classification as a
            definitive fact with the official map URL (never invent URLs).
          </P>

          <Sub>Analytics in Synthesis</Sub>
          <P>
            Month-over-month trends are formatted as human-readable text, not JSON, and appended to the user prompt.
            Example: <Mono>BATTERY: 245 (up 23%)</Mono>. This saves ~40% tokens vs a JSON structure while giving Claude
            enough information to weave trends into the narrative.
          </P>

          {/* ── 8. Conversation Management ── */}
          <SectionHeading id="conversation">Conversation Management</SectionHeading>

          <Sub>Multi-Turn Context Synthesis</Sub>
          <P>
            When a user sends a short follow-up or answers a clarification question, the raw message often lacks
            enough context for the router. A pre-routing step uses Claude Haiku (300-token budget) to synthesize
            the conversation history into a self-contained query.
          </P>
          <P>
            Example: User asks "What's the zoning?" → Assistant asks "Which address?" → User says "Wicker Park" →
            Haiku synthesizes "What's the zoning in Wicker Park?" before routing.
          </P>
          <P>
            Detection heuristics in <Mono>needs_synthesis()</Mono>: very short messages ({"<"}50 chars) after an
            assistant question; context references ("their", "it", "what about"); follow-up patterns
            ("do you have", "how do I"); short questions lacking explicit location keywords.
          </P>

          <Sub>Per-Message Context Snapshots</Sub>
          <P>
            Each assistant message stores its own <Mono>context</Mono>, <Mono>plan</Mono>, <Mono>mapData</Mono>,
            and <Mono>mapFetchedAt</Mono>. Citations remain valid across multi-turn conversations —
            you can't accidentally cite context that was computed for a different query. Clicking a past user
            message loads that question's sidebar state.
          </P>

          <Sub>10-Message Limit</Sub>
          <P>
            Enforced on both sides. Backend: if <Mono>{">="} 10</Mono> user messages in SQLite, emits
            <Mono>error: "MESSAGE_LIMIT_REACHED"</Mono>. Frontend: replaces input with "Start a new conversation."
            Controls token costs and prevents context window explosion. Configurable
            via <Mono>message_limit</Mono> in <Mono>config.py</Mono>.
          </P>

          <Sub>SQLite Persistence</Sub>
          <P>
            WAL mode via <Mono>aiosqlite</Mono>, singleton connection, schema v2. Tables: <Mono>conversations</Mono>,
            <Mono>messages</Mono> (with JSON blob columns for context/plan/mapData), <Mono>uploads</Mono>,
            <Mono>llm_calls</Mono>, <Mono>request_logs</Mono>, <Mono>schema_version</Mono>. JSON blob columns
            because context/plan/mapData are written once and read whole — no query benefit from normalization
            for a single-user app.
          </P>

          {/* ── 9. Map & Geo ── */}
          <SectionHeading id="map">Map & Geo Visualization</SectionHeading>

          <Sub>Mapbox + deck.gl Over Leaflet</Sub>
          <P>
            WebGL rendering handles thousands of points smoothly in the sidebar's constrained viewport. deck.gl's
            declarative layer API makes filter toggling trivial — just rebuild the layers array. Leaflet with
            SVG overlays would struggle at 2,500 crime points. Dark basemap (<Mono>dark-v11</Mono>) instead
            of <Mono>streets-v12</Mono> because the entire app is dark-themed.
          </P>

          <Sub>Layer Stack</Sub>
          <Table
            headers={["Layer", "Type", "Details"]}
            rows={[
              ["Zoning", "GeoJsonLayer", "Parcel boundaries, 16 zone prefix colors, rendered first (underneath dots)"],
              ["Crime", "ScatterplotLayer", "30 named types with semantic colors (hot reds=violent, cool blues=non-violent)"],
              ["311", "ScatterplotLayer", "14 departments with distinct colors, hash-based fallback for unknown types"],
              ["Permits", "ScatterplotLayer", "8 normalized types, radius scaled by estimated_cost"],
              ["Address Pin", "ScatterplotLayer", "Blue dot with white stroke at queried address"],
            ]}
          />

          <Sub>Dynamic Filters</Sub>
          <P>
            Filter controls adapt based on what the router requested. Crime-only query → crime-type sub-filters
            with 1% threshold (types below 1% bucketed into "Other"). 311-only → department filters. Overview →
            source-level toggles. All filters compose: type toggles → arrest/status/cost filter → date range slider.
          </P>
          <P>
            Solo toggle behavior: single-click isolates a type, double-click resets to all.
            Click-to-detail popup shows all fields for that item, with coordinates as a Google Maps Street View link
            (<Mono>map_action=pano</Mono>).
          </P>

          <Sub>Zoning Overlay</Sub>
          <P>
            GeoJsonLayer with Chicago's standard zoning color scheme: residential=yellow, business=blue,
            commercial=purple, manufacturing=magenta, planned development=gray, downtown=teal, parks=green.
            "Zoning" and "Points" toggles allow viewing the zoning overlay alone. Click popup shows zone class,
            definition, allowed uses, and link to the official zoning map.
          </P>

          {/* ── 10. Analytics ── */}
          <SectionHeading id="analytics">Analytics</SectionHeading>

          <Sub>Server-Side MoM Trends</Sub>
          <P>
            Month-over-month trend computation runs server-side in <Mono>analytics.py</Mono>, not just in the
            frontend. The server has access to the complete month of data without sampling bias. Results are
            attached to <Mono>context.analytics</Mono> so Claude can cite specific trends in synthesis.
            Formatted as text (not JSON) — saves ~40% tokens. Skips the current partial calendar month.
            Capped at 8 categories per source, sorted by current count.
          </P>

          <Sub>Custom SVG Donut Chart</Sub>
          <P>
            Built from scratch using SVG arc path geometry. No chart library — avoids adding recharts (~200KB)
            or chart.js (~170KB) for a single chart type. The entire analytics feature adds ~5KB gzipped.
          </P>
          <P>
            Key feature: <Accent>thin-slice ring</Accent>. Slices at or below 2% are nearly invisible in the main
            donut. On hover, a second concentric ring fades in (250ms) outside the main donut, redistributing
            only the thin slices proportionally to fill 360°. A 100ms grace period prevents flicker when the cursor
            crosses the 3px gap. Enlarged invisible hit areas (5px beyond visible arc) improve discoverability.
          </P>

          <Sub>Trend Tables</Sub>
          <P>
            Sortable MoM trend rows with colored directional arrows. Red ↑ for crime increases (increases are bad),
            green ↓ for decreases. Sortable by type, current count, prior count, or trend percentage.
          </P>

          {/* ── 11. Admin & Observability ── */}
          <SectionHeading id="admin">Admin & Observability</SectionHeading>

          <Sub>LLM Call Tracking</Sub>
          <P>
            <Mono>tracked_create()</Mono> wraps non-streaming API calls, <Mono>tracked_stream()</Mono> wraps
            streaming calls. Both capture input/output/cache tokens, wall-clock duration, and error status.
            Logged to the <Mono>llm_calls</Mono> SQLite table with phase (router/synthesizer/conversation)
            and request group ID. Non-fatal — if the DB write fails, the chat flow continues.
          </P>

          <Sub>Cost Estimation</Sub>
          <Table
            headers={["Model", "Input", "Output"]}
            rows={[
              ["Claude Sonnet 4.6", "$3.00 / MTok", "$15.00 / MTok"],
              ["Claude Haiku 4.5", "$0.80 / MTok", "$4.00 / MTok"],
            ]}
          />

          <Sub>Admin Dashboard</Sub>
          <P>
            Full <Mono>/admin</Mono> page with period selector (Today / 7d / 30d / All Time). Six sections:
            stat cards (requests, tokens, cost, errors), time-series area chart, cost-by-model and calls-by-phase
            pie charts, latency percentile table (p50/p90/p99 by phase), retrieval benchmark grade visualization,
            synthesis quality judge results, conversation stats, and paginated request log.
            All charts are custom SVG — no charting library.
          </P>

          {/* ── 12. Eval & Benchmarks ── */}
          <SectionHeading id="eval">Eval & Benchmarks</SectionHeading>

          <Sub>Query Test Suite (26 queries)</Sub>
          <P>
            <Mono>eval/queries.json</Mono> with expected intent, sources, community area, and search terms.
            Router-only eval checks that the LLM produces the right retrieval plan. Full pipeline eval
            runs the complete chat flow and checks for expected terms in the response.
          </P>
          <Table
            headers={["Metric", "Value"]}
            rows={[
              ["Total queries", "26"],
              ["Pass rate", "22/26 (84.6%)"],
              ["Router latency p50", "2,478 ms"],
              ["Retrieval latency p50", "3,565 ms"],
              ["TTFT p50", "4,827 ms"],
              ["Total latency p50", "13,788 ms"],
            ]}
          />

          <Sub>Retrieval Quality Benchmark (18 queries)</Sub>
          <P>
            <Mono>eval/retrieval_benchmark.py</Mono> with gold section IDs and expected answer terms per query.
            Grades: A (gold hit + terms), B (gold hit, some terms missing), C (partial), D/F (miss).
          </P>
          <Table
            headers={["Version", "A", "B", "C", "D", "F", "Key Change"]}
            rows={[
              ["v1 (baseline)", "11", "1", "4", "1", "1", "No dedup, no keyword boost"],
              ["v3", "13", "1", "4", "0", "0", "Per-section dedup + keyword boost"],
              ["v4 (current)", "15", "1", "2", "0", "0", "bge-reranker-v2-m3, rerank-before-dedup"],
            ]}
          />
          <P>
            Remaining 2 C-grades (<Mono>adu_allowed</Mono>, <Mono>lot_coverage_rm5</Mono>) are term-mismatch
            issues — the answer terms don't appear in any chunk of the retrieved sections. Not a retrieval problem
            but a terminology gap.
          </P>

          <Sub>LLM-as-Judge Synthesis Eval</Sub>
          <P>
            <Mono>eval/run_eval.py --full {"<URL>"} --judge</Mono> grades each synthesized answer using Claude Sonnet
            as the evaluator. Four dimensions, weighted:
          </P>
          <Table
            headers={["Dimension", "Weight", "Checks"]}
            rows={[
              ["Citation Accuracy", "30%", "[N] markers reference valid code_chunks; [data:X] matches present sources"],
              ["Factuality", "30%", "Numbers match context; capped data uses \"at least N\"; no hallucination"],
              ["Completeness", "20%", "Direct answer first; crime lag noted; MoM trends woven when analytics present"],
              ["Rule Compliance", "20%", "Disclaimer when required; zoning stated as fact with official URL"],
            ]}
          />
          <P>
            Results are written to <Mono>eval/judge_results.json</Mono> and visualized in the admin dashboard.
            Deterministic: <Mono>temperature=0</Mono>. Context truncated to 600 chars per chunk and 15K total
            to keep judge costs reasonable.
          </P>

          {/* ── 13. Frontend Architecture ── */}
          <SectionHeading id="frontend">Frontend Architecture</SectionHeading>

          <Sub>State Machine</Sub>
          <P>
            <Mono>App.tsx</Mono> implements a dual-mode UI: splash (landing page) and workspace (chat + sidebar).
            Activation: <Mono>{"active = messages.length > 0 || streaming"}</Mono>. Hard cut between modes
            with opacity transition. First user message auto-creates a conversation and routes to <Mono>/c/:id</Mono>.
          </P>

          <Sub>URL Routing</Sub>
          <P>
            <Mono>react-router-dom</Mono> with three routes: <Mono>/</Mono> (splash),{" "}
            <Mono>/c/:id</Mono> (conversation), <Mono>/admin</Mono> (dashboard).
            Conversations are bookmarkable and work with browser back/forward.
            A <Mono>useConversationRouter</Mono> hook syncs <Mono>conversationId</Mono> state with the URL
            bidirectionally. Direct URL access loads the conversation from the API; invalid URLs redirect to <Mono>/</Mono>.
          </P>

          <Sub>Per-Message State Switching</Sub>
          <P>
            Clicking a past user message loads that turn's context, plan, and map data into the sidebar.
            Map data has a 24-hour staleness check — if older, it's re-fetched via <Mono>/api/map-data</Mono> and
            the stored message is updated via PATCH. Uses <Mono>useRef</Mono> patterns to avoid stale closures
            in async callbacks.
          </P>

          <Sub>Typewriter Effect</Sub>
          <P>
            <Mono>useTypewriter</Mono> hook with adaptive step sizing: 1 char/tick normally, 2 when 20+ behind,
            3 when 50+ behind. A <Mono>wasStreamingRef</Mono> distinguishes "never streamed" (show immediately)
            from "just finished streaming" (let the interval catch up). ~15ms per character.
          </P>

          <Sub>Section Cache</Sub>
          <P>
            <Mono>fetchSection()</Mono> in <Mono>api.ts</Mono> is memoized with a <Mono>Map{"<string, Promise>"}</Mono>.
            Municipal code sections are immutable, so cached indefinitely. Hover-prefetch on a cross-reference
            pill and the subsequent click share a single network request.
          </P>

          <Sub>Responsive Design</Sub>
          <P>
            Below 768px, the sidebar is replaced with a bottom sheet overlay (<Mono>MobileSidebarSheet.tsx</Mono>) —
            Framer Motion slide-up, drag-down-to-dismiss on the handle area, backdrop click to close. Workspace header
            shows shortened brand name ("UrbanLayer" vs "UrbanLayer — Chicago") and truncated breadcrumb. Chat
            padding adjusts from <Mono>px-6</Mono> to <Mono>px-3</Mono>.
          </P>

          {/* ── 14. Testing ── */}
          <SectionHeading id="testing">Testing</SectionHeading>
          <P>
            194 tests across 15 test files. All passing. Frontend: <Mono>tsc</Mono> build clean, <Mono>npm run build</Mono> produces
            ~322KB JS + 16KB CSS.
          </P>
          <Table
            headers={["Module", "Test File", "Key Coverage"]}
            rows={[
              ["Router", "test_router.py", "CA resolution, geocoding, clarification detection, time-range defaults"],
              ["Assembler", "test_assembler.py", "Crime cap to top-5, arrest rate, capped flag, Open-Dup filter, permit cost agg, violation categorization"],
              ["Vector Search", "test_vector_search.py", "Payload conversion, section dedup, cross-ref expansion, legend detection, regex patterns"],
              ["Analytics", "test_analytics.py", "MoM trends, edge cases (new categories, zero change), period formatting"],
              ["Conversation", "test_conversation.py", "Follow-up detection heuristics (short messages, pronouns, context refs)"],
              ["Geo", "test_geo.py", "Point-in-polygon, name resolution, alias table"],
              ["DB", "test_db.py", "Conversation CRUD, message saving, schema versioning"],
              ["Socrata", "test_socrata.py", "$limit guard enforcement, retry logic"],
              ["Zoning", "test_zoning.py", "ArcGIS lookup parsing, polygon fetch"],
              ["API", "test_api.py", "SSE endpoint, conversation CRUD"],
              ["Integration", "test_integration.py", "End-to-end request flow"],
              ["Map Data", "test_map_data.py", "Row fetching, coordinate cleaning, cost renaming"],
            ]}
          />
          <P>
            Testing patterns: unit tests with <Mono>unittest.mock</Mono> for all I/O (Socrata, Qdrant, Census Geocoder).
            Shared fixtures in <Mono>conftest.py</Mono> (<Mono>mock_settings</Mono> with dataset IDs + limits).
            Async tests via <Mono>pytest-asyncio</Mono>. No external API calls — all network tests are mocked.
          </P>

          {/* ── 15. Design Decisions ── */}
          <SectionHeading id="decisions">Design Decisions</SectionHeading>
          <WideTable
            headers={["Decision", "Alternatives Considered", "Why This Choice", "Tradeoff"]}
            rows={[
              ["SSE streaming", "WebSocket, polling", "Unidirectional server→client fits synthesis streaming; no bidirectional state needed", "Harder to debug than polling; connection management"],
              ["SQLite (aiosqlite)", "PostgreSQL, localStorage", "Single user, single writer — simplest correct solution; WAL mode for concurrent reads", "Not multi-writer safe; migration needed at scale"],
              ["Custom SVG charts", "recharts, chart.js, visx", "Existing PieChart was already custom SVG; avoids 200KB+ dependency; exact theme match", "More code to maintain; no pre-built chart types"],
              ["bge-base-en-v1.5", "OpenAI text-embedding-3, Cohere", "Local (no API calls), free, same BGE family as reranker, 768-dim for legal text discrimination", "Slower cold start (~8s), CPU-bound encoding"],
              ["Census Geocoder", "Google Maps, Mapbox Geocoding", "Free, no API key, deterministic, no rate limit concerns", "Less accurate than Google for ambiguous addresses"],
              ["Qdrant (self-hosted)", "Pinecone, Weaviate, ChromaDB", "Free, Docker-based, payload filtering for cross-refs, HTTP API avoids client version conflicts", "Self-hosted = operational burden; no managed scaling"],
              ["Rerank before dedup", "Dedup then rerank", "Best chunk per section survives after blending; multi-part sections get correct chunk selected", "Slower (reranker runs on all ~60 candidates)"],
              ["Per-message context", "Shared conversation context", "Citations survive across turns; per-question state switching; map data staleness tracking", "Larger SQLite blobs; more storage per message"],
              ["Map data in SSE", "Separate /api/map-data call", "Eliminates round-trip for current turn; keeps client state in sync", "Larger SSE payloads; coupling between chat + map flows"],
              ["Analytics as text", "JSON in synthesis prompt", "~40% token savings; trends read naturally in synthesized answer", "Less structured; harder for Claude to parse edge cases"],
              ["Deck.gl + Mapbox", "Leaflet, Google Maps", "WebGL handles 1000s of points; declarative layer API; dark basemap", "Heavier bundle; Mapbox token required (public pk.*)"],
              ["10-message limit", "Unlimited, sliding window", "Controls token costs; prevents context window explosion", "Users must start new conversations; no long sessions"],
              ["Hardcoded CA aliases", "API lookup, LLM resolution", "Fast, deterministic, no network call; aliases are stable", "Can't add aliases without code change"],
              ["JSON blob columns", "Normalized tables", "Context/plan/mapData written once, read whole; no query benefit from normalization", "Can't query individual fields within blobs"],
              ["Non-fatal LLM logging", "Required logging, separate service", "DB errors in tracked_create/tracked_stream are caught — logging never degrades chat UX", "Silent logging failures; could miss cost data"],
            ]}
          />

          {/* ── 16. At Scale ── */}
          <SectionHeading id="scale">At Scale</SectionHeading>
          <P>
            Current architecture optimized for single-user local deployment. Here's what changes at 1,000x users:
          </P>
          <WideTable
            headers={["Component", "Current Approach", "At 1,000x Users"]}
            rows={[
              ["Database", "SQLite (single writer, WAL mode)", "PostgreSQL with connection pooling (pgBouncer). Index on created_at for admin queries. Message blob cleanup policy (TTL)"],
              ["Geocoding", "Census Geocoder (per-IP rate limit)", "Cache results in local DB. At high volume, use a local geocoding database (Pelias) or paid API with higher limits"],
              ["Embedding inference", "CPU-bound via sentence-transformers", "GPU-accelerated (ONNX runtime or TensorRT). Batch queries. Cache embeddings for repeated queries"],
              ["Map data", "2,500 crime rows per query", "Geo-hexagon binning (H3) for dense areas. Dynamic limits based on viewport bounds. Server-side clustering"],
              ["LLM costs", "~$0.05 per query (Sonnet)", "Prompt caching for repeated system prompts. Haiku fallback for simple queries. Per-user quotas"],
              ["Streaming", "Single-process FastAPI", "Load balancer with sticky sessions. Connection limits. Graceful shutdown on deploy"],
              ["Vector search", "Single Qdrant instance (Docker)", "Qdrant cluster with replicas. Quantized vectors (scalar/product). Collection aliases for zero-downtime reindexing"],
              ["Rate limiting", "10 messages per conversation", "Per-user rate limits (API key tiers). Sliding window with token budget per tier"],
              ["Conversation history", "Full list, no pagination", "Paginated + archived. Move old conversations to cold storage. Search via full-text index"],
              ["Admin queries", "Full-table scans in SQLite", "Materialized views for overview/timeseries. Dedicated analytics DB (ClickHouse or TimescaleDB)"],
              ["Context window", "Full history in synthesis prompt", "Sliding window with summarization. Older turns compressed to 1-2 sentences each"],
              ["Frontend section cache", "In-memory Map (14,600 entries)", "IndexedDB or Redis. LRU eviction for rarely-accessed sections"],
            ]}
          />

          <div className="mt-16 pt-8 border-t border-dark-border/50">
            <p className="text-text-muted text-sm">
              194 tests passing. 14,535 chunks indexed. 8 live datasets. Built with FastAPI, Claude, Qdrant,
              React, Mapbox, and deck.gl.
            </p>
          </div>
        </article>
      </div>
    </div>
  );
}
