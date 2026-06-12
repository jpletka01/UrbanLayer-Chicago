import { useEffect, useState } from "react";
import PageHeader from "./PageHeader";

const SECTIONS = [
  { id: "overview", title: "Project Overview" },
  { id: "architecture", title: "Architecture" },
  { id: "data-layer", title: "Data Layer" },
  { id: "document-processing", title: "Document Processing" },
  { id: "vector-search", title: "Vector Search Pipeline" },
  { id: "router", title: "LLM Router" },
  { id: "domain-orchestrators", title: "Domain Orchestrators" },
  { id: "synthesis", title: "Streaming Synthesis" },
  { id: "conversation", title: "Conversation Management" },
  { id: "auth", title: "Authentication & Security" },
  { id: "rate-limiting", title: "Rate Limiting" },
  { id: "map", title: "Map & Geo Visualization" },
  { id: "sidebar-cards", title: "Sidebar & Data Cards" },
  { id: "analytics", title: "Analytics" },
  { id: "file-upload", title: "File Upload & Vision" },
  { id: "admin", title: "Admin & Observability" },
  { id: "eval", title: "Eval & Benchmarks" },
  { id: "infrastructure", title: "Infrastructure & Deployment" },
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
      <PageHeader />

      {/* Mobile TOC toggle */}
      <div className="lg:hidden sticky top-12 z-20 bg-dark-bg border-b border-dark-border">
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
        <nav className="hidden lg:block w-56 shrink-0 sticky top-12 h-[calc(100vh-3rem)] overflow-y-auto py-8 pr-6 pl-6">
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
            It combines <Accent>18+ live datasets</Accent> across 5 APIs (Chicago Socrata, Cook County Socrata,
            ArcGIS, Census, and external services), <Accent>semantic search</Accent> over the entire Chicago
            Municipal Code (14,535 vector-indexed chunks), and <Accent>LLM synthesis</Accent> via Claude
            to produce sourced, cited answers with interactive map visualizations. Live
            at <Mono>urbanlayerchicago.com</Mono>.
          </P>
          <P>
            The killer query: <em>"What's going on near 2400 N Milwaukee Ave?"</em> A single prompt triggers the
            LLM router, which geocodes the address, identifies the community area, and dispatches parallel retrieval
            across crime statistics, open 311 service requests, building permits, code violations, business licenses,
            vacant buildings, food inspections, applicable zoning, regulatory overlays, nearby incentive programs,
            property records, demographics, and transit access. The response includes inline citations,
            month-over-month trend analysis, and a map with filterable data layers — synthesized via streaming SSE
            in 3-8 seconds.
          </P>
          <P>
            Four <Accent>domain orchestrators</Accent> extend beyond basic API queries: Property (parcel → assessment → sales → tax
            estimation), Regulatory (22 ArcGIS overlay layers + FEMA flood + EPA brownfields), Incentives (TIF
            financials + Enterprise/Opportunity Zones + grant programs), and Neighborhood (demographics + transit
            proximity + Walk Score). Each runs sub-queries in parallel with graceful degradation when external
            services are unavailable.
          </P>
          <P>
            What makes this different from querying APIs directly: the system resolves addresses to community areas via
            Census geocoding, fetches from multiple datasets concurrently behind a concurrency semaphore, applies
            domain-specific aggregation and capping, computes analytics, routes through workflow-aware orchestrators,
            and uses an LLM to synthesize a human-readable answer that cites its sources. A user would need to
            make 15+ API calls across 5 services, understand SoQL and ArcGIS query syntax, cross-reference zoning
            codes, and interpret Cook County parcel data to replicate one query.
          </P>

          {/* ── 2. Architecture ── */}
          <SectionHeading id="architecture">Architecture</SectionHeading>
          <P>
            Multi-layer RAG architecture with domain orchestrators. Each layer serves a distinct retrieval need:
            recent structured data (Socrata APIs), spatial regulatory data (ArcGIS), property records
            (Cook County), static legal text (Qdrant vector search), and natural-language reasoning (LLM synthesis).
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
│  → RetrievalPlan JSON     │  Sources, location, intent, workflow_hint
└─────────┬─────────────────┘
          ▼
┌───────────────────────────────────────────────────────────┐
│  Parallel Retrieval — Semaphore(4) concurrent tasks       │
│  ├─ Socrata APIs (crime, 311, permits, violations,        │
│  │   business, vacant, food inspections)                  │
│  ├─ Qdrant Vector Search (14,535 chunks, bge-base)        │
│  ├─ ArcGIS Zoning (point lookup + polygon fetch)          │
│  ├─ Domain Orchestrators:                                 │
│  │   ├─ Property  (parcel → char/assess/sales/tax)        │
│  │   ├─ Regulatory (22 overlays + FEMA + EPA + ARO)       │
│  │   ├─ Incentives (TIF + EZ + OZ + grants)               │
│  │   └─ Neighborhood (demographics + transit + WalkScore) │
│  └─ Map Data (raw geo-located rows: 2500/1000/500)        │
└─────────┬─────────────────────────────────────────────────┘
          ▼
┌───────────────────────────┐
│  Context Assembly         │  Aggregation, capping, dedup
│  + Analytics              │  Month-over-month trends (text format)
└─────────┬─────────────────┘
          ▼
┌───────────────────────────┐
│  Streaming Synthesis      │  Sonnet — 2000 tok budget
│  SSE: plan → context →    │  Inline citations, trend weaving
│  map_data → tokens → done │  26 synthesis rules
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
              ["Auth", "Google OAuth2 + self-rolled JWT", "One-click sign-in; httpOnly cookies + CSRF double-submit"],
              ["Frontend", "React + TypeScript + Vite + Tailwind v3", "Type-safe, dark theme, fast builds (~322KB JS)"],
              ["Map", "Mapbox GL JS + deck.gl", "WebGL handles 1000s of points, declarative layers"],
              ["Geocoding", "Census Geocoder + Shapely", "Free, no API key, deterministic"],
              ["Hosting", "Hetzner CX22 (Nuremberg)", "Cheapest x86 VPS: 2 vCPU, 4GB RAM, €4.50/mo"],
              ["DNS/TLS", "Cloudflare Full (Strict)", "Zero-maintenance Origin Certificate (expires 2041)"],
            ]}
          />

          {/* ── 3. Data Layer ── */}
          <SectionHeading id="data-layer">Data Layer</SectionHeading>

          <Sub>Chicago Socrata Datasets</Sub>
          <P>
            All structured city data comes from the Chicago Data Portal via SoQL queries. Each query carries a
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
              ["Vacant Buildings", "kc9i-wq85", "Abandonment, code enforcement", "20", "—"],
              ["Food Inspections", "4ijn-s7e5", "Pass/fail rates, risk levels", "20", "—"],
              ["Community Areas", "igwz-8jzy", "Address → CA polygons", "—", "—"],
              ["IUCR Codes", "c7ck-438e", "Crime code translation", "—", "—"],
            ]}
          />
          <P>
            Two separate row limits exist because the chat context needs <em>aggregated summaries</em> (top-5 crime types =
            10 tokens) while the map needs <em>individual geo-located rows</em> for plotting. Map limits (2,500 crime)
            cover ~90 days in busy community areas — the original 200-row limit only covered ~7 days.
          </P>

          <Sub>Cook County Property Data</Sub>
          <P>
            Property domain queries hit Cook County Socrata endpoints (separate from the city portal).
            PIN14 resolution via <Accent>Cook County GIS</Accent> ArcGIS service (primary) with automatic
            fallback to the <Accent>Socrata Parcel Universe</Accent> (<Mono>pabr-t5kh</Mono>) when the GIS spatial
            index is down. Once a PIN is resolved, four datasets are queried in parallel:
          </P>
          <Table
            headers={["Dataset", "Source", "Returns"]}
            rows={[
              ["Parcel Universe", "Socrata pabr-t5kh", "PIN lookup fallback, address standardization"],
              ["Characteristics", "CCAO API", "Sq ft, stories, units, bedrooms, bathrooms, age, class"],
              ["Assessments", "CCAO API", "5-year history: land, building, total assessed values"],
              ["Sales History", "CCAO API", "10 most recent sales with dates, prices, deed types"],
            ]}
          />

          <Sub>Incentive Zone Data</Sub>
          <Table
            headers={["Dataset", "ID", "Use"]}
            rows={[
              ["TIF Boundaries", "eejr-xtfb", "Point-in-polygon TIF district membership"],
              ["TIF Financial Reports", "72uz-ikdv", "Fund balance, expenditures, tax increment by year"],
              ["Enterprise Zones", "64xf-pyvh", "EZ boundary check + zone name"],
              ["SBIF Projects", "etqr-sz5x", "Small Business Improvement Fund grants by CA"],
              ["NOF Large Grants", "j7ew-b73u", "Neighborhood Opportunity Fund (large)"],
              ["NOF Small Grants", "rym7-49n8", "Neighborhood Opportunity Fund (small)"],
              ["ARO Housing", "s6ha-ppgi", "Affordable Requirements Ordinance projects by CA"],
            ]}
          />

          <Sub>External APIs & GIS Services</Sub>
          <Table
            headers={["Service", "Provider", "Use"]}
            rows={[
              ["Zoning MapServer (22 layers)", "Chicago ArcGIS", "Zone class, overlays, TOD, ADU, SSA, landmarks"],
              ["Cook County GIS Parcels", "Cook County ArcGIS", "Address → PIN14 via spatial query"],
              ["FEMA Flood Zones", "FEMA ArcGIS", "Flood zone designation, SFHA flag"],
              ["EPA Brownfields", "EPA ArcGIS", "Nearby contamination sites"],
              ["HUD Opportunity Zones", "Census tract FIPS", "OZ eligibility by tract designation"],
              ["Census Geocoder", "US Census Bureau", "Address → lat/lon (free, no key)"],
              ["FCC Census Block API", "FCC", "Lat/lon → 11-digit Census tract FIPS"],
              ["Census Reporter API", "Census Reporter", "ACS demographics by tract (income, race, age, education)"],
              ["Walk Score API", "WalkScore.com", "Walkability/transit/bike scores (0-100)"],
              ["CTA/Metra GTFS", "Local JSON", "Transit station proximity, TOD eligibility"],
            ]}
          />

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
            to a network lookup. Census tract resolution via FCC Census Block API for demographic and Opportunity
            Zone lookups.
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
          <P>
            <Accent>Production note:</Accent> The cross-encoder reranker (<Mono>bge-reranker-v2-m3</Mono>, ~1.3GB)
            is disabled in production via <Mono>RERANKER_ENABLED=false</Mono> to fit within 4GB server RAM.
            The pipeline falls back to the proven 0.85 dense + 0.15 keyword scoring. Re-enable at 8GB+ RAM.
          </P>

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
            and detailed search query guidance. The router selects from 10 source tags and assigns a workflow hint
            that determines which domain orchestrators activate.
          </P>

          <Sub>Output Schema</Sub>
          <Code>{`{
  "sources": ["crime_api", "311_api", "vector_search", "property", "regulatory", ...],
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
  "search_query": "zoning permitted uses residential district",
  "workflow_hint": "site_due_diligence"
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

          <Sub>Workflow Hints</Sub>
          <P>
            Workflow hints tell the assembler which domain orchestrators to activate. The router infers
            the workflow from the user's question — "Is this site contaminated?" triggers <Mono>site_due_diligence</Mono>,
            "Can I open a restaurant here?" triggers <Mono>business_launch</Mono>.
          </P>
          <Table
            headers={["Workflow", "Orchestrators", "Example Query"]}
            rows={[
              ["site_due_diligence", "Property + Regulatory + Incentives + Neighborhood", "\"Tell me everything about this lot\""],
              ["development_feasibility", "Property (no sales) + Regulatory + Zoning + Code", "\"Can I build a 4-story here?\""],
              ["business_launch", "Zoning + Code + Business + Incentives", "\"Can I open a bakery at this address?\""],
              ["property_intelligence", "Property (deep) + Tax", "\"What's the assessment history for this PIN?\""],
              ["neighborhood_overview", "Standard + Demographics + Transit", "\"What's the vibe in Pilsen?\""],
              ["general", "Standard behavior", "Default when no specific workflow detected"],
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
5. FCC Census Block API → 11-digit FIPS tract (for demographics + OZ)
6. Store resolved_lat/lon for ArcGIS zoning lookup + map pin`}</Code>

          {/* ── 7. Domain Orchestrators ── */}
          <SectionHeading id="domain-orchestrators">Domain Orchestrators</SectionHeading>
          <P>
            Four domain orchestrators handle complex, multi-step retrieval pipelines that go beyond simple API queries.
            Each runs sub-queries in parallel via <Mono>asyncio.gather</Mono> with graceful degradation — if the Cook
            County GIS is down, property still returns via the Socrata fallback. If FEMA returns a 500, the regulatory
            response shows "Unknown" for flood zone instead of failing the entire query.
          </P>

          <Sub>Property Orchestrator</Sub>
          <Code>{`Address → Census Geocoder → (lat, lon)
  → Cook County GIS Parcel Lookup (spatial query)
    └─ Fallback: Socrata Parcel Universe (bounding-box)
  → PIN14
  → asyncio.gather():
    ├─ Characteristics (CCAO): sq ft, stories, units, bedrooms, bath, age, class
    ├─ Assessments (CCAO): 5-year land/building/total values
    ├─ Sales History (CCAO): 10 most recent with dates, prices, deed types
    └─ Tax Estimation (PTaxSim, optional): bill breakdown by taxing agency`}</Code>
          <P>
            The Cook County GIS spatial index is intermittently broken (queries can timeout 60s+). The Socrata Parcel
            Universe fallback resolves PINs via bounding-box query without polygon geometry. Workflow-conditional:
            <Mono>development_feasibility</Mono> skips assessment and sales history to reduce response size.
          </P>

          <Sub>Regulatory Orchestrator</Sub>
          <Code>{`(lat, lon) → asyncio.gather():
  ├─ ArcGIS Zoning Overlays (22 layers):
  │   ├─ Planned Developments    ├─ Lakefront Protection
  │   ├─ Pedestrian Streets      ├─ Landmark Districts
  │   ├─ Historic Districts      ├─ Individual Landmarks
  │   ├─ National Register       ├─ Special Districts
  │   ├─ FEMA Floodplain (local) ├─ PMD SubAreas
  │   ├─ TOD (CTA)               ├─ TOD (Metra)
  │   ├─ ADU Eligible            ├─ ARO Zones
  │   └─ Special Service Areas
  ├─ FEMA Flood Zone API → zone designation, SFHA flag
  ├─ EPA Brownfields → nearby contamination sites
  └─ ARO Housing Projects → affordable units by community area`}</Code>
          <P>
            All 22 ArcGIS overlay layers are queried in a single parallel batch. Each returns ordinance numbers,
            feature names, and boundaries. The FEMA lookup is independent — the ArcGIS layer 11 provides the
            local floodplain while the FEMA API provides the federal designation. The regulatory summary assembles
            all active overlays into a structured object with a human-readable description for the synthesizer.
          </P>

          <Sub>Incentives Orchestrator</Sub>
          <Code>{`Two modes, selected by location type:

POINT-BASED (address/lat-lon):
  (lat, lon) → asyncio.gather():
    ├─ TIF district membership (point-in-polygon)
    │   └─ If in TIF: fetch financial reports (5 most recent)
    │       → Fund analysis: increment, balance, expenditures
    ├─ Enterprise Zone check (Socrata boundary query)
    ├─ Opportunity Zone check (Census tract → OZ designation)
    └─ Grant programs (SBIF + NOF by community area)

NEIGHBORHOOD-WIDE (community area name):
  community_area → asyncio.gather():
    ├─ All TIF districts overlapping the CA
    │   └─ Per-district fund analysis
    ├─ Grants by CA (SBIF + NOF large + NOF small)
    └─ EZ/OZ not applicable (no point)`}</Code>
          <P>
            TIF fund analysis interprets financial report fields: property tax increment (current and cumulative),
            fund balance, expenditure history, and net income trends. The assembler also interprets Cook County
            property class codes (6b, 6c, 7a, 7b, 7c, 8) as tax incentive classes — properties with these codes
            receive reduced assessments for commercial/industrial development.
          </P>

          <Sub>Neighborhood Orchestrator</Sub>
          <Code>{`community_area + (lat, lon) → asyncio.gather():
  ├─ Demographics (Census Reporter API via tract FIPS):
  │   Population, median income, home value, rent, age,
  │   poverty rate, unemployment, owner-occupied %, education,
  │   5-bucket distributions (age, income, race, education, transport)
  ├─ Transit Access:
  │   ├─ Nearest CTA rail station (name, distance, lines served)
  │   ├─ Nearest Metra station (name, distance, line)
  │   └─ TOD eligibility + type
  └─ Walk Score (walkability, transit score, bike score)`}</Code>
          <P>
            Demographics come from American Community Survey (ACS) 5-year estimates via Census Reporter, not
            pre-computed. Median values are estimated from bracket distributions. The system compares tract-level
            stats against county and city medians for context. Transit station data is pre-loaded from a GTFS
            extract at startup — no API call per query.
          </P>

          {/* ── 8. Streaming Synthesis ── */}
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
              ["context", "ContextObject JSON", "Citation data, sidebar content, domain card data"],
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
            The system prompt enforces 26 rules including: always cite inline (never end-of-message); surface 7-day crime data lag;
            use "at least N" for capped results; append legal disclaimer when <Mono>requires_disclaimer</Mono> is
            true; weave the 2-4 most notable month-over-month trends naturally; state zoning classification as a
            definitive fact with the official map URL (never invent URLs). When domain orchestrator data is present,
            additional rules activate: format property assessments as a table, describe regulatory overlays with
            practical implications, explain TIF/EZ/OZ eligibility, and note transit accessibility with TOD status.
          </P>

          <Sub>Analytics in Synthesis</Sub>
          <P>
            Month-over-month trends are formatted as human-readable text, not JSON, and appended to the user prompt.
            Example: <Mono>BATTERY: 245 (up 23%)</Mono>. This saves ~40% tokens vs a JSON structure while giving Claude
            enough information to weave trends into the narrative.
          </P>

          {/* ── 9. Conversation Management ── */}
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
            ("do you have", "how do I"); short questions lacking explicit location keywords. A deterministic
            regex-based check detects neighborhood switching ("compare to Englewood", "what about Lincoln Park")
            before falling back to LLM synthesis.
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

          <Sub>Conversation Sharing</Sub>
          <P>
            Users can share conversations via a unique URL-safe token. <Mono>POST /api/conversations/:id/share</Mono> generates
            the token (one per conversation). The shared view at <Mono>/s/:shareToken</Mono> is fully read-only — same
            chat UI, sidebar, and map, but no input box and no modification. Shares are revokable
            via <Mono>DELETE /api/conversations/:id/share</Mono>. The share token has a <Mono>CASCADE</Mono> foreign
            key — deleting the conversation automatically revokes the share.
          </P>

          <Sub>SQLite Persistence</Sub>
          <P>
            WAL mode via <Mono>aiosqlite</Mono>, singleton connection, schema v6. Tables: <Mono>conversations</Mono>,
            <Mono>messages</Mono> (with JSON blob columns for context/plan/mapData), <Mono>uploads</Mono>,
            <Mono>llm_calls</Mono>, <Mono>request_logs</Mono>, <Mono>schema_version</Mono>,
            <Mono>users</Mono>, <Mono>refresh_tokens</Mono>, <Mono>share_tokens</Mono>. JSON blob columns
            because context/plan/mapData are written once and read whole — no query benefit from normalization
            for a single-user app.
          </P>

          {/* ── 10. Authentication & Security ── */}
          <SectionHeading id="auth">Authentication & Security</SectionHeading>

          <Sub>Google OAuth2 Flow</Sub>
          <P>
            One-click sign-in via Google OAuth2 redirect. The backend handles the full authorization code flow:
            <Mono>/api/auth/google</Mono> redirects to Google's consent screen, <Mono>/api/auth/google/callback</Mono> exchanges
            the authorization code for user info, creates or updates the user in SQLite, issues JWT tokens,
            and redirects back to the frontend with cookies set.
          </P>

          <Sub>Token Architecture</Sub>
          <Table
            headers={["Token", "TTL", "Storage", "Purpose"]}
            rows={[
              ["Access Token", "15 minutes", "httpOnly cookie", "Authenticates API requests"],
              ["Refresh Token", "7 days", "httpOnly cookie (path=/api/auth)", "Rotates access tokens silently"],
              ["CSRF Token", "15 minutes", "JS-readable cookie", "Double-submit pattern for state-changing requests"],
            ]}
          />
          <P>
            Refresh tokens use hash-based rotation: the database stores <Mono>sha256(token)</Mono>, not the raw token.
            On refresh, the old token is invalidated and a new one is issued. CSRF protection via double-submit
            pattern — the frontend reads the CSRF cookie and sends it as a header on every non-GET request. All
            cookies set <Mono>Secure</Mono> and <Mono>SameSite=Lax</Mono> in production.
          </P>

          <Sub>User Tiers</Sub>
          <Table
            headers={["Tier", "Access", "How Assigned"]}
            rows={[
              ["anonymous", "3 queries/day, basic features", "No sign-in"],
              ["free", "25 queries/day, conversation history", "Google sign-in"],
              ["premium", "100 queries/day, all features", "Manual upgrade"],
              ["admin", "Unlimited, admin dashboard", "Database flag"],
            ]}
          />

          <Sub>Frontend Auth Integration</Sub>
          <P>
            <Mono>AuthProvider</Mono> wraps the app, exposing <Mono>useAuth()</Mono> throughout. The auth gate
            fires on <Mono>sendMessage</Mono> — unauthenticated users see a modal with a "Sign in with Google"
            button. The <Mono>401-interceptor</Mono> in <Mono>authFetch()</Mono> intercepts expired tokens:
            attempts <Mono>POST /api/auth/refresh</Mono> (coalescing concurrent refreshes via a module-level
            promise), re-reads the CSRF cookie, and retries the original request once. Dev mode
            (<Mono>GOOGLE_CLIENT_ID</Mono> unset) bypasses auth entirely — no sign-in UI shown.
          </P>

          {/* ── 11. Rate Limiting ── */}
          <SectionHeading id="rate-limiting">Rate Limiting</SectionHeading>
          <P>
            In-memory sliding-window rate limiter with per-user and per-tier limits. No Redis dependency — the
            single-process architecture means in-memory state is correct and simpler. Rate limit state resets
            on server restart, which is acceptable for this scale.
          </P>
          <Table
            headers={["Tier", "Per Hour", "Per Day"]}
            rows={[
              ["Anonymous", "3", "3"],
              ["Free", "10", "25"],
              ["Premium", "30", "100"],
              ["Admin", "Unlimited", "Unlimited"],
            ]}
          />
          <P>
            A <Accent>daily API budget cap</Accent> ($5/day default, configurable) guards against runaway LLM costs
            regardless of tier. When the cap is hit, all non-admin users get a 429 with a <Mono>Retry-After</Mono> header
            indicating seconds until the budget resets. The budget is computed from <Mono>llm_calls</Mono> table cost
            estimates (Sonnet $3/$15 per MTok, Haiku $0.80/$4 per MTok).
          </P>

          {/* ── 12. Map & Geo ── */}
          <SectionHeading id="map">Map & Geo Visualization</SectionHeading>

          <Sub>Mapbox + deck.gl Over Leaflet</Sub>
          <P>
            WebGL rendering handles thousands of points smoothly in the sidebar's constrained viewport. deck.gl's
            declarative layer API makes filter toggling trivial — just rebuild the layers array. Leaflet with
            SVG overlays would struggle at 2,500 crime points. Dark basemap (<Mono>dark-v11</Mono>) instead
            of <Mono>streets-v12</Mono> because the entire app is dark-themed.
          </P>

          <Sub>Layer Stack</Sub>
          <P>
            Layers render bottom-to-top. Polygon layers (zoning, overlays, incentive zones) render underneath
            point layers (crime, 311, permits) so dots are always clickable.
          </P>
          <Table
            headers={["Layer", "Type", "Details"]}
            rows={[
              ["Zoning Districts", "GeoJsonLayer", "Parcel boundaries, 16 zone prefix colors (residential=yellow, business=blue, etc.)"],
              ["Overlay Districts", "GeoJsonLayer", "Regulatory overlays: landmarks, historic, TOD, ADU, SSA, lakefront"],
              ["Incentive Zones", "GeoJsonLayer", "TIF boundaries, Enterprise Zones, hash-based color per district"],
              ["Parcel Boundary", "GeoJsonLayer", "Queried parcel polygon outline from Cook County GIS"],
              ["Crime", "ScatterplotLayer", "30 named types with semantic colors (hot reds=violent, cool blues=non-violent)"],
              ["311", "ScatterplotLayer", "14 departments with distinct colors, hash-based fallback"],
              ["Permits", "ScatterplotLayer", "8 normalized types, radius scaled by estimated_cost"],
              ["Transit Stations", "ScatterplotLayer", "Nearby CTA/Metra stations with line colors"],
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

          <Sub>Map Legends</Sub>
          <P>
            Dynamic legends render based on active layers: zoning category colors, overlay district types with
            ordinance numbers, incentive zone labels (TIF district names, EZ/OZ designations). Legend items are
            interactive — clicking focuses the map on that zone's bounds.
          </P>

          {/* ── 13. Sidebar & Data Cards ── */}
          <SectionHeading id="sidebar-cards">Sidebar & Data Cards</SectionHeading>

          <Sub>Sidebar Layout</Sub>
          <P>
            The sidebar is drag-to-resize (snap-close at {"<"}200px, max 60% of viewport). Collapsed state shows
            a 44px rail with tab icons. Two tabs: <Accent>Data</Accent> (map + analytics + domain cards)
            and <Accent>Sources</Accent> (ranked municipal code chunks with citations). The sidebar auto-opens
            when the first <Mono>context</Mono> SSE event arrives.
          </P>

          <Sub>Domain Cards</Sub>
          <P>
            Eight specialized sidebar cards render structured data from domain orchestrators. Each
            uses <Mono>CollapsibleCard</Mono> — a shared component with expand/collapse animation, header
            with icon, and structured content layout.
          </P>
          <Table
            headers={["Card", "Data Shown"]}
            rows={[
              ["PropertyCard", "Parcel info, characteristics (sq ft, stories, class), assessment history table, sales history"],
              ["RegulatoryCard", "Active overlays with ordinance numbers, flood zone, brownfield proximity, ARO projects"],
              ["IncentivesCard", "TIF district + fund analysis, EZ/OZ status, grant programs (SBIF/NOF), tax incentive class"],
              ["NeighborhoodCard", "Demographics (income, poverty, education), transit access, Walk Score badges"],
              ["ViolationsCard", "Open vs closed counts, category breakdown, recent violations with codes"],
              ["BusinessCard", "License types, top business activities, license count by category"],
              ["FoodInspectionCard", "Pass/fail rates, risk level distribution, recent inspections"],
              ["VacantBuildingsCard", "By-department counts, recent reports with fines"],
            ]}
          />

          <Sub>InfoTooltips</Sub>
          <P>
            Domain-specific terms (overlay names, zone classes, incentive programs, flood zone designations) are
            wrapped in <Mono>InfoTooltip</Mono> components that show hover/tap popovers with plain-language
            definitions. Definitions are centralized in <Mono>termDefinitions.ts</Mono> and
            rendered via a portal-based popover with dotted underline trigger, 150ms hover persistence,
            and click-away dismiss on mobile. Example: hovering "Lakefront Protection District" shows its purpose
            and restrictions.
          </P>

          {/* ── 14. Analytics ── */}
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

          {/* ── 15. File Upload & Vision ── */}
          <SectionHeading id="file-upload">File Upload & Vision</SectionHeading>
          <P>
            Users can attach images and PDFs to messages for multimodal analysis. The backend
            uses <Accent>Claude Vision</Accent> to interpret uploaded files alongside the retrieval context and
            municipal code — for example, uploading a photo of a building and asking "What zoning violations
            might apply here?"
          </P>
          <Table
            headers={["Constraint", "Value"]}
            rows={[
              ["Supported formats", "JPEG, PNG, WebP, PDF"],
              ["Max file size", "10 MB per file"],
              ["Max files per message", "3"],
              ["Auto-resize", "Images >1568px downscaled (quality=85 JPEG)"],
              ["Storage", "Per-conversation upload directory in SQLite-tracked metadata"],
            ]}
          />
          <P>
            Image resizing uses PIL to prevent exceeding Claude's vision input limits. PDFs are base64-encoded
            and sent as document blocks. Uploads are tracked per-conversation with cleanup on conversation delete.
          </P>

          {/* ── 16. Admin & Observability ── */}
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

          <Sub>Cache Statistics</Sub>
          <P>
            25 <Mono>TTLCache</Mono> instances across all retrieval modules (crime, 311, permits, violations,
            business, vacant, food inspections, zoning, overlays, census tracts, parcels, etc.). The admin dashboard
            surfaces per-cache hit rates and miss counts. TTLs range from 15 minutes (operational data like crime)
            to 60 minutes (property/regulatory) to 3,600 seconds (geographic lookups). Cache maxsizes tuned
            per module based on expected cardinality.
          </P>

          <Sub>Admin Dashboard</Sub>
          <P>
            Full <Mono>/admin</Mono> page with period selector (Today / 7d / 30d / All Time). Six sections:
            stat cards (requests, tokens, cost, errors), time-series area chart, cost-by-model and calls-by-phase
            pie charts, latency percentile table (p50/p90/p99 by phase), retrieval benchmark grade visualization,
            synthesis quality judge results, conversation stats (total conversations, avg messages, user breakdown),
            and paginated request log. All charts are custom SVG — no charting library. Protected
            by <Mono>ProtectedRoute</Mono> requiring admin tier.
          </P>

          {/* ── 17. Eval & Benchmarks ── */}
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

          <Sub>Data Source Coverage Benchmark</Sub>
          <P>
            <Mono>eval/source_coverage.py</Mono> runs 29 queries across all data sources and checks that each
            sub-source (crime, 311, permits, property characteristics, zoning overlays, TIF financials, etc.)
            is retrieved and included in the response.
          </P>
          <Table
            headers={["Metric", "Value"]}
            rows={[
              ["Total queries", "29"],
              ["Sub-source checks", "40"],
              ["Covered", "34/40 (85%)"],
              ["Known gaps", "Property characteristics (GIS intermittent), Tax (PTaxSim optional), ARO routing"],
            ]}
          />

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

          {/* ── 18. Infrastructure & Deployment ── */}
          <SectionHeading id="infrastructure">Infrastructure & Deployment</SectionHeading>

          <Sub>Docker Architecture</Sub>
          <P>
            Multi-stage Docker builds for both backend and frontend. The backend image uses CPU-only
            PyTorch (<Mono>torch==2.7.0+cpu</Mono> from PyTorch's index URL) to avoid shipping ~2GB of CUDA
            libraries. HuggingFace models (bge-base-en-v1.5 embedding, ~500MB) are baked into the image at
            build time — no download on first startup. Runs as a non-root user. The frontend is a
            multi-stage node build → nginx serve.
          </P>

          <Sub>Production Server</Sub>
          <Table
            headers={["Spec", "Value"]}
            rows={[
              ["Provider", "Hetzner Cloud (Nuremberg, Germany)"],
              ["Instance", "CX22 — 2 vCPU (shared), 4GB RAM, 40GB SSD"],
              ["Swap", "2GB (prevents OOM kills during ML inference spikes)"],
              ["Cost", "~€4.50/month"],
              ["OS", "Ubuntu 22.04"],
            ]}
          />
          <P>
            Chosen over AWS/DigitalOcean/Railway for cost — 4GB RAM at Hetzner costs less than 1GB on most
            US cloud providers. The trade-off is higher latency for US users (Nuremberg → US adds ~100ms)
            and no managed scaling, but acceptable for a portfolio project.
          </P>

          <Sub>DNS & TLS</Sub>
          <P>
            Cloudflare manages DNS and TLS termination. <Accent>Full (Strict) mode</Accent> with a Cloudflare
            Origin Certificate installed on the server — valid for 15 years (expires 2041). This eliminates
            Let's Encrypt renewal complexity and certbot dependencies. The nginx production config handles
            HTTP → HTTPS redirect on port 80, SSL termination on port 443, HSTS headers, and a Content Security
            Policy tuned for Mapbox GL JS, deck.gl, Google Fonts, Google avatars, Cloudflare Insights, and Sentry.
          </P>

          <Sub>CI/CD Pipeline</Sub>
          <P>
            GitHub Actions workflow on push to <Mono>main</Mono>: runs all 480 backend tests, TypeScript type
            check, and frontend build. On success, SSHs into the production server, pulls the latest code,
            and rebuilds Docker containers. Claude Code GitHub App provides AI code review on PR
            open/synchronize events.
          </P>

          <Sub>Monitoring & Reliability</Sub>
          <Table
            headers={["System", "Purpose"]}
            rows={[
              ["Sentry (EU region)", "Exception tracking with source maps, traces synthesis/retrieval errors"],
              ["UptimeRobot", "5-minute health checks against /health endpoint, email alerts on downtime"],
              ["Daily backup cron", "3am UTC, SQLite database + uploads, 7 rolling backups"],
              ["Admin dashboard", "Self-hosted observability: LLM costs, latency, error rates, request logs"],
            ]}
          />

          <Sub>Production Hardening</Sub>
          <P>
            Several issues discovered and fixed after the initial production deployment:
          </P>
          <Table
            headers={["Issue", "Root Cause", "Fix"]}
            rows={[
              ["OOM kills", "10+ concurrent retrieval tasks + ML model loading", "Semaphore(4) concurrency limit + blocking ML preload at startup"],
              ["Reranker crashes", "bge-reranker-v2-m3 (~1.3GB) exceeds 4GB RAM", "Disabled via RERANKER_ENABLED=false; falls back to dense+keyword"],
              ["HTTP 413 on saves", "Message blobs with context/plan/mapData exceeded nginx limit", "client_max_body_size 16m + client strips blobs from chat history"],
              ["CSP blocking", "Google avatars, Sentry, Cloudflare scripts blocked", "Expanded CSP connect-src/img-src/script-src directives"],
              ["Auth race condition", "Conversation load fired before auth resolved", "Gated init on !authLoading flag"],
              ["Silent write failures", "fetch() non-OK responses not thrown", "All write functions now throw on non-OK"],
              ["SSE stream crashes", "Non-fatal LLM errors killed the entire stream", "Two-tier try-except: fatal vs non-fatal call isolation"],
            ]}
          />

          {/* ── 19. Frontend Architecture ── */}
          <SectionHeading id="frontend">Frontend Architecture</SectionHeading>

          <Sub>State Machine</Sub>
          <P>
            <Mono>App.tsx</Mono> implements a dual-mode UI: splash (landing page) and workspace (chat + sidebar).
            Activation: <Mono>{"active = messages.length > 0 || streaming"}</Mono>. Hard cut between modes
            with opacity transition. First user message auto-creates a conversation and routes to <Mono>/c/:id</Mono>.
          </P>

          <Sub>URL Routing</Sub>
          <P>
            <Mono>react-router-dom</Mono> with five routes: <Mono>/</Mono> (splash),{" "}
            <Mono>/c/:id</Mono> (conversation), <Mono>/s/:shareToken</Mono> (shared read-only
            view), <Mono>/admin</Mono> (dashboard, admin-only via <Mono>ProtectedRoute</Mono>),
            and <Mono>/about</Mono> (this page).
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

          <Sub>Address Autocomplete</Sub>
          <P>
            The chat input includes Census Geocoder-backed address autocomplete. As the user types a Chicago
            address, <Mono>/autocomplete?q=...</Mono> returns up to 5 matching addresses with coordinates.
            Selecting a suggestion populates the input and pre-resolves the location for faster routing.
            Debounced at 300ms to avoid excessive API calls.
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

          <Sub>Stream Close Detection</Sub>
          <P>
            <Mono>useChat.ts</Mono> tracks a <Mono>receivedDone</Mono> flag. If the SSE stream ends without
            a <Mono>done</Mono> event and the request wasn't user-aborted, the UI shows "Connection lost — please
            try again." This catches silent backend crashes, nginx timeouts, and Cloudflare disconnects without
            leaving the user staring at a frozen typewriter.
          </P>

          <Sub>Responsive Design</Sub>
          <P>
            Below 768px, the sidebar is replaced with a bottom sheet overlay (<Mono>MobileSidebarSheet.tsx</Mono>) —
            Framer Motion slide-up, drag-down-to-dismiss on the handle area, backdrop click to close. Workspace header
            shows shortened brand name ("UrbanLayer" vs "UrbanLayer — Chicago") and truncated breadcrumb. Chat
            padding adjusts from <Mono>px-6</Mono> to <Mono>px-3</Mono>.
          </P>

          {/* ── 20. Testing ── */}
          <SectionHeading id="testing">Testing</SectionHeading>
          <P>
            480 tests across 40 test files. All passing. Frontend: <Mono>tsc</Mono> build clean, <Mono>npm run build</Mono> produces
            ~322KB JS + 16KB CSS.
          </P>
          <Table
            headers={["Domain", "Test Files", "Key Coverage"]}
            rows={[
              ["Core", "router, assembler, retrieval, synthesizer", "CA resolution, geocoding, intent classification, cap detection, permit aggregation"],
              ["Vector Search", "vector_search", "Payload conversion, section dedup, cross-ref expansion, legend detection"],
              ["Property", "parcels, characteristics, assessments, sales, tax_estimate, orchestrator", "GIS lookup + fallback, CCAO parsing, PIN resolution, tax calculation"],
              ["Regulatory", "overlays, flood, environmental, orchestrator", "22-layer ArcGIS parsing, FEMA zones, EPA brownfields, ARO housing"],
              ["Incentives", "tif, ez, oz, grant_programs, orchestrator", "TIF fund analysis, zone membership, OZ tract check, SBIF/NOF totals"],
              ["Neighborhood", "demographics, transit, walkscore, orchestrator", "Census tract resolution, CTA/Metra proximity, Walk Score parsing"],
              ["City Data", "socrata, zoning, food_inspections, vacant_buildings, aro_housing", "SoQL limit guard, ArcGIS parsing, inspection grouping, department counts"],
              ["Auth & Sharing", "auth, share", "OAuth flow, JWT token rotation, CSRF validation, share token CRUD"],
              ["Persistence", "db, conversation, models", "Schema migration, conversation CRUD, message saving, JSON blobs"],
              ["API & Integration", "api, integration, map_data, analytics", "SSE endpoint, end-to-end flow, row fetching, MoM trends"],
            ]}
          />
          <P>
            Testing patterns: unit tests with <Mono>unittest.mock</Mono> for all I/O (Socrata, Qdrant, Census Geocoder,
            Cook County GIS, FEMA, EPA, CCAO). Shared fixtures in <Mono>conftest.py</Mono> (<Mono>mock_settings</Mono> with
            dataset IDs + limits). Async tests via <Mono>pytest-asyncio</Mono>. No external API calls — all network
            tests are mocked. Autouse fixture clears all 25 TTL caches between tests.
          </P>

          {/* ── 21. Design Decisions ── */}
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
              ["Google OAuth", "Email/password, magic link, Auth0", "One-click sign-in, no password management, no email service needed, trusted provider", "Google-only; users without Google accounts can't sign in"],
              ["JWT + httpOnly cookies", "Session storage, bearer tokens in localStorage", "XSS-proof token storage; browser auto-sends cookies; no JS access to tokens", "CSRF protection needed (double-submit pattern); cookie config complexity"],
              ["In-memory rate limiting", "Redis, database-backed", "Single-process — in-memory state is correct and simplest; no external dependency", "Resets on restart; not horizontally scalable"],
              ["Domain orchestrators", "Monolithic retrieval function", "Each domain has different data sources, access patterns, and fallback strategies; separation of concerns", "More modules to maintain; orchestrator coordination overhead"],
              ["Hetzner CX22", "AWS EC2, DigitalOcean, Railway", "4GB RAM at €4.50/mo — 5-10x cheaper than US cloud for equivalent specs", "Higher latency for US users (~100ms); no managed scaling"],
              ["Cloudflare Origin Cert", "Let's Encrypt + certbot", "15-year validity, zero renewal automation, no cron jobs, no renewal failures", "Locked into Cloudflare proxying; cert only valid behind Cloudflare"],
              ["Concurrency semaphore", "Unbounded parallelism, queue", "Prevents OOM from 10+ concurrent retrieval tasks on 4GB RAM; simple asyncio primitive", "Limits throughput; sequential bottleneck under high concurrency"],
              ["ML preload at startup", "Lazy-load on first request", "First user doesn't wait 8s for model download; OOM caught at deploy time, not at runtime", "Slower container startup (~30s); startup fails if model missing"],
              ["CPU-only PyTorch", "Full PyTorch with CUDA", "Production server is x86 CPU; avoids shipping ~2GB of unused CUDA libraries", "No GPU acceleration; inference is slower (acceptable for query volume)"],
              ["Conversation sharing via token", "Snapshot duplication, public URLs", "No data duplication; CASCADE delete auto-revokes; owner retains control", "Share breaks if conversation is deleted; no offline/archived shares"],
            ]}
          />

          {/* ── 22. At Scale ── */}
          <SectionHeading id="scale">At Scale</SectionHeading>
          <P>
            Current architecture optimized for single-user deployment on a 4GB VPS. Here's what changes at 1,000x users:
          </P>
          <WideTable
            headers={["Component", "Current Approach", "At 1,000x Users"]}
            rows={[
              ["Database", "SQLite (single writer, WAL mode)", "PostgreSQL with connection pooling (pgBouncer). Index on created_at for admin queries. Message blob cleanup policy (TTL)"],
              ["Auth", "In-memory rate limits, single-process JWT", "Redis for session/rate-limit state. OAuth with multiple providers. JWT key rotation"],
              ["Geocoding", "Census Geocoder (per-IP rate limit)", "Cache results in local DB. At high volume, use a local geocoding database (Pelias) or paid API with higher limits"],
              ["Embedding inference", "CPU-bound via sentence-transformers", "GPU-accelerated (ONNX runtime or TensorRT). Batch queries. Cache embeddings for repeated queries"],
              ["Map data", "2,500 crime rows per query", "Geo-hexagon binning (H3) for dense areas. Dynamic limits based on viewport bounds. Server-side clustering"],
              ["LLM costs", "~$0.05 per query (Sonnet)", "Prompt caching for repeated system prompts. Haiku fallback for simple queries. Per-user quotas"],
              ["Streaming", "Single-process FastAPI", "Load balancer with sticky sessions. Connection limits. Graceful shutdown on deploy"],
              ["Vector search", "Single Qdrant instance (Docker)", "Qdrant cluster with replicas. Quantized vectors (scalar/product). Collection aliases for zero-downtime reindexing"],
              ["Rate limiting", "In-memory sliding window", "Redis-backed sliding window. Token budget per tier with rollover. Abuse detection"],
              ["Domain orchestrators", "Direct API calls per request", "Response caching by (location, time_range). Pre-computed property/regulatory profiles for hot addresses"],
              ["Conversation history", "Full list, no pagination", "Paginated + archived. Move old conversations to cold storage. Search via full-text index"],
              ["Admin queries", "Full-table scans in SQLite", "Materialized views for overview/timeseries. Dedicated analytics DB (ClickHouse or TimescaleDB)"],
              ["Context window", "Full history in synthesis prompt", "Sliding window with summarization. Older turns compressed to 1-2 sentences each"],
              ["Frontend section cache", "In-memory Map (14,600 entries)", "IndexedDB or Redis. LRU eviction for rarely-accessed sections"],
            ]}
          />

          <div className="mt-16 pt-8 border-t border-dark-border/50">
            <p className="text-text-muted text-sm">
              480 tests passing. 14,535 chunks indexed. 18+ live datasets. 4 domain orchestrators.
              Built with FastAPI, Claude, Qdrant, React, Mapbox, and deck.gl.
              Live at urbanlayerchicago.com.
            </p>
          </div>
        </article>
      </div>
    </div>
  );
}
