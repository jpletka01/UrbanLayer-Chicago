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
  { id: "scorecard", title: "The Scorecard" },
  { id: "parcel-identity", title: "Parcel Identity" },
  { id: "report", title: "Feasibility Report (PDF)" },
  { id: "zoning-cache", title: "Zoning Cache" },
  { id: "payments", title: "Payments & Monetization" },
  { id: "discovery", title: "Property Discovery" },
  { id: "conversation", title: "Conversation Management" },
  { id: "auth", title: "Authentication & Security" },
  { id: "rate-limiting", title: "Rate Limiting" },
  { id: "map", title: "Map & Geo Visualization" },
  { id: "sidebar-cards", title: "Sidebar & Data Cards" },
  { id: "analytics", title: "Analytics" },
  { id: "usage-analytics", title: "Usage Analytics" },
  { id: "file-upload", title: "File Upload & Vision" },
  { id: "admin", title: "Admin & Observability" },
  { id: "eval", title: "Eval & Benchmarks" },
  { id: "infrastructure", title: "Infrastructure & Deployment" },
  { id: "frontend", title: "Frontend Architecture" },
  { id: "design-system", title: "Design System" },
  { id: "testing", title: "Testing" },
  { id: "decisions", title: "Design Decisions" },
  { id: "scale", title: "At Scale" },
];

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-section font-semibold text-text-primary tracking-tight scroll-mt-20 pt-12 pb-4">
      {children}
    </h2>
  );
}

function Sub({ children }: { children: React.ReactNode }) {
  return <h3 className="text-subtitle font-semibold text-text-primary mt-8 mb-3">{children}</h3>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-text-secondary leading-relaxed mb-4">{children}</p>;
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="rounded-lg bg-dark-elevated border border-dark-border p-4 overflow-x-auto text-body font-mono text-text-secondary mb-4">
      {children}
    </pre>
  );
}

function Accent({ children }: { children: React.ReactNode }) {
  return <span className="text-accent font-medium">{children}</span>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return <code className="text-body bg-dark-elevated px-1.5 py-0.5 rounded font-mono text-text-primary">{children}</code>;
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-dark-border mb-4">
      <table className="w-full text-body">
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
      <table className="w-full text-body">
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
          className="w-full flex items-center justify-between px-6 py-3 text-body text-text-secondary"
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
                className={`block w-full text-left py-1.5 text-body transition-colors ${
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
          <p className="text-caption font-semibold text-text-muted uppercase tracking-wider mb-4">Contents</p>
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`block w-full text-left py-1.5 text-body transition-colors ${
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
            UrbanLayer is a <Accent>parcel feasibility engine</Accent> for Chicago real-estate professionals — it
            answers the question every developer, architect, and attorney asks before committing capital:{" "}
            <em>"What can I build here, and should I?"</em> Type an address and in ~2 seconds you get the parcel's
            full <Accent>Scorecard</Accent> (zoning, overlays, incentives, tax projection, comparable sales);
            interrogate it via chat with cited municipal code; and buy a $25
            PDF <Accent>Development Feasibility Report</Accent>. Live at <Mono>urbanlayerchicago.com</Mono>.
          </P>
          <P>
            Under the hood it is a retrieval-augmented generation (RAG) system combining <Accent>25+ live
            datasets</Accent> across 5 APIs (Chicago Socrata, Cook County Socrata, ArcGIS, Census, and external
            services), <Accent>semantic search</Accent> over the entire Chicago Municipal Code (14,535
            vector-indexed chunks), and <Accent>LLM synthesis</Accent> via Claude to produce sourced, cited answers
            with interactive map visualizations. The product began as a neighborhood Q&amp;A tool and was
            deliberately refocused onto site feasibility — the engine is the same, but every surface now points at
            one workflow: <em>evaluate a parcel, then act.</em>
          </P>
          <P>
            Two complementary workflows sit on top of the engine:
          </P>
          <Table
            headers={["Workflow", "Question", "Surfaces"]}
            rows={[
              ["Evaluate (today's wedge)", "\"I found a parcel. Should I develop it?\"", "Scorecard (free hook) → Chat (cited analysis) → $25 Report (the deliverable)"],
              ["Discover (second wedge)", "\"Find me parcels worth evaluating.\"", "Property Discovery workbench (filters over ~949k parcels) → each result flows into Evaluate"],
            ]}
          />
          <P>
            The <Accent>Scorecard</Accent> is the hook: instant, free, anonymous, and <em>zero LLM cost</em> — it
            renders structured facts straight from the data layer. The <Accent>chat copilot</Accent> is the engine
            and the differentiator: an LLM router geocodes the address, resolves the parcel, and dispatches parallel
            retrieval across crime, 311, permits, violations, business licenses, zoning, regulatory overlays,
            incentive programs, property records, demographics, and transit — synthesizing a cited answer via
            streaming SSE in 3-8 seconds. The <Accent>$25 PDF report</Accent> is the wedge: a tangible deliverable
            that proves the value of every underlying system in one artifact.
          </P>
          <P>
            Four <Accent>domain orchestrators</Accent> extend beyond basic API queries: Property (parcel → assessment → sales → tax
            estimation), Regulatory (22 ArcGIS overlay layers + FEMA flood + EPA brownfields), Incentives (TIF
            financials + Enterprise/Opportunity Zones + grant programs), and Neighborhood (demographics + transit
            proximity + Walk Score). Each runs sub-queries in parallel with graceful degradation when external
            services are unavailable.
          </P>
          <P>
            What makes this different from querying APIs directly: the system resolves an address to an authoritative
            14-digit parcel PIN, fetches from multiple datasets concurrently behind a concurrency semaphore, applies
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
              ["Reranker", "BAAI/bge-reranker-v2-m3 (disabled in prod)", "Same family as embeddings; too slow on prod vCPUs — report now uses a precomputed zoning cache instead"],
              ["Payments", "Stripe (Checkout + webhooks)", "One-time $25 report + $99/mo Pro subscription; no PCI surface"],
              ["Streaming", "SSE (text/event-stream)", "Synthesis is 3-8s; streaming TTFT is better UX"],
              ["Persistence", "SQLite via aiosqlite (WAL), schema v11", "Single user, single writer — simplest correct solution"],
              ["Auth", "Google OAuth2 + self-rolled JWT", "One-click sign-in; httpOnly cookies + CSRF double-submit"],
              ["Frontend", "React + TypeScript + Vite + Tailwind v3", "Type-safe, dark theme; Inter / Space Grotesk / IBM Plex Mono"],
              ["PDF Reports", "WeasyPrint + Jinja + matplotlib", "HTML/CSS → PDF; rendered in an isolated child process"],
              ["Map", "Mapbox GL JS + deck.gl", "WebGL handles 1000s of points, declarative layers"],
              ["Geocoding", "Census Geocoder + Shapely + Cook County Address Points", "Free, deterministic; authoritative address→PIN resolution"],
              ["Hosting", "Hetzner CX32 (Nuremberg)", "4 vCPU, 8GB RAM + 8GB swap (upgraded from CX22/4GB)"],
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

          <Sub>The Assessment That Was Always Zero — A Data Story</Sub>
          <P>
            Building the discovery index, a key field came back <Accent>0% populated</Accent>: total assessed value was
            null for every one of ~949k parcels, which silently disabled the entire "undervalued" recipe. The data
            existed and the join wasn't wrong in any obvious way — yet every parcel resolved to a valueless row.
          </P>
          <P>
            The cause is a Socrata semantics trap. The CCAO assessment dataset carries an in-progress current year
            whose value columns stay NULL until the assessment is mailed — and <em>Socrata omits NULL fields from its
            JSON entirely</em>. So a query ordering <Mono>year DESC</Mono> and taking the first row got the in-progress
            year, which arrived with no value columns at all. The fix requires a non-null total in the predicate
            ("the latest year that actually carries values"), taking population from 0% to 99%. The same audit confirmed
            the scorecard/report path was already safe — it iterates to the first row with a real total rather than
            grabbing the raw latest.
          </P>
          <P>
            A methodology footnote from the same effort: a 300-row <em>sample</em> reported 74% coverage of a field
            whose true coverage across the full set was 28% — sampling a skewed dataset lied by 46 points.{" "}
            <em>Measure the whole set when the cost is a one-time batch job.</em>
          </P>

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
          <Sub>The 8 MB That Vanished — A Parsing Story</Sub>
          <P>
            Early on, the index was quietly missing 251 sections — with no error, just absent content. The cause was a
            single malformed <Mono>&lt;div&gt;</Mono> in Title 18 of the source HTML that made lxml <em>silently</em>{" "}
            nest the trailing ~8 MB of the document — the republished Titles 16/17 "Zoning &amp; Land Use Ordinance,"
            the single most important content for a feasibility tool — inside an earlier element, where the section
            walker never reached it. The data didn't throw; it lied about its own shape.
          </P>
          <P>
            The fix sidesteps the broken markup entirely: split the file at the republication banner string and parse
            each half as its own document. The lesson — when a parser's output is suspiciously short, suspect the{" "}
            <em>input's</em> structure before your traversal logic — is the same instinct that later caught the
            null-field assessment bug.
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

          <Sub>Full Pipeline (v5)</Sub>
          <Code>{`query
  → synonym expansion (_expand_query: 11 trigger terms — ADU, loading, demolition…)
  → district code normalization (e.g. "RM5" → "RM-5")
  → prepend BGE query prefix
  → encode with bge-base (768-dim)                        [thread pool]
  → Qdrant async dense search (limit = top_k × 5, overfetch for dedup)
  → filter legend-only table chunks
  → keyword boost: combined = 0.80 × dense + 0.20 × keyword_overlap
  → cross-encoder rerank the top 20 candidates            [single-worker pool]
  → blend: final = 0.80 × norm_dense + 0.20 × norm_reranker
  → sort by blended score
  → keyword-aware per-section dedup (best chunk per section)
  → cross-reference expansion (1-hop, batched Qdrant call)
  → return top_k CodeChunks`}</Code>
          <P>
            v5 added synonym expansion, district-code normalization, keyword-aware dedup, and bumped the keyword
            weight from 0.15 to 0.20 — lifting the retrieval benchmark from 75% to{" "}
            <Accent>100% A/B (26 A, 2 B across 28 queries)</Accent>.
          </P>
          <Sub>The Reranker Incident — A Debugging Story</Sub>
          <P>
            The cross-encoder reranker is the one piece of this pipeline that is <Mono>RERANKER_ENABLED=false</Mono> in
            production — and getting there was the single hardest debugging episode in the project. It's worth telling
            in full, because the path to the fix was a chain of wrong turns.
          </P>
          <P>
            <Accent>The symptom.</Accent> One day <Mono>/api/report</Mono> started returning 504s — every report timed
            out. Scorecard and chat stayed up, so the outage was report-only. <Accent>The first wrong guess:</Accent>{" "}
            an out-of-memory kill. The box runs ML models in 8GB, the timing felt like memory pressure, so the first
            response hardened against OOM — swap was grown 2GB → 8GB and the PDF render was moved into an isolated
            child process. Sensible defense-in-depth, but it didn't fix the 504s, because memory was never the cause.
          </P>
          <P>
            <Accent>The real culprit.</Accent> The report's zoning extraction fired <em>five</em> reranked semantic
            searches in parallel, and on the production vCPUs a single reranked search took 40-60s — so the five-way
            fan-out blew straight past the nginx timeout. The obvious quick fix —
            pin <Mono>torch.set_num_threads(1)</Mono> — actually made it <em>worse</em>: it stripped intra-op
            parallelism without removing the real problem. Profiling found two compounding issues: unbounded rerank
            concurrency (the five searches each dispatched a Torch <Mono>predict()</Mono> to a shared executor and
            thrashed) and a 3× oversized batch (60 pairs reranked just to return 3). The clincher was a native run
            where swap was physically impossible and the stall <em>still</em> reproduced at 0.99× the serial floor —
            proof it was CPU serialization, not memory, all along.
          </P>
          <P>
            <Accent>The fix that wasn't enough.</Accent> A proper fix followed: rerank only the top 20 candidates,
            route every <Mono>predict()</Mono> through a single-worker executor, make the thread count configurable.
            On a dev machine the five-way path dropped from 35.7s to 12.4s. But verified <em>on the real production
            box</em>, a single 20-pair <Mono>predict()</Mono> was still ~40s and the report path ~280s ≫ the 180s
            ceiling — the bge cross-encoder is simply ~15× slower per core on these shared vCPUs than on the M4 Pro it
            was tuned on. So the fix was rolled back and the flag stayed off.
          </P>
          <P>
            <Accent>How we overcame it.</Accent> The breakthrough was reframing the problem: the report didn't need a
            faster reranker, it needed to <em>not call one</em>. The zoning extraction was moved offline into a{" "}
            <Accent>precomputed cache</Accent> (see the Zoning Cache section) — which, as a bonus, fixed a separate
            silent accuracy bug. The reranker is now out of the report path entirely; the chat pipeline falls back to
            the proven 0.80 dense + 0.20 keyword scoring. The lessons that stuck: <em>profile on the hardware you
            actually ship to</em> (the prod box behaves nothing like a laptop), and the best fix for a slow dependency
            on a hot path is sometimes to remove it from the path, not to speed it up.
          </P>

          <Sub>Score Blending Rationale</Sub>
          <P>
            <Accent>Keyword boost (0.20)</Accent>: catches exact-term relevance that embeddings miss. "Lot coverage" matching
            a chunk about lot coverage percentages instead of lot area standards. (Raised from 0.15 in v5.)
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
            stuck with whatever chunk the dense embedding liked most per section. The v4/v5 pipeline reranks the top
            candidates (the top 20 by combined dense+keyword score) <em>before</em> dedup, so dedup picks the
            best-scoring chunk per section after blending. This lets the reranker choose a better chunk from
            multi-part sections (e.g., selecting the chunk with "square feet" from the lot area table instead of the
            table legend). When the reranker is disabled in production, the same ordering applies to the blended
            dense+keyword score.
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

          {/* ── The Scorecard ── */}
          <SectionHeading id="scorecard">The Scorecard</SectionHeading>
          <P>
            The Scorecard is the product's hook: type an address, get the parcel's complete structured assessment in
            ~2 seconds. It is <Accent>free, anonymous, and zero LLM cost</Accent> — <Mono>GET /api/scorecard</Mono> reads
            straight from the data layer and domain orchestrators, no synthesis pass. It earns the user's trust ("this
            is right") before asking for anything, then bridges into the chat (Investigate buttons) and the paid report
            (Download CTA).
          </P>
          <P>
            The page (<Mono>ScorecardPage.tsx</Mono>) accepts a parcel three ways, in precedence
            order: <Mono>?pin=</Mono> → <Mono>?address=</Mono> → <Mono>?lat=&amp;lon=</Mono>. A pin-confirmed result
            canonicalizes the URL to <Mono>?pin=&amp;address=</Mono> (the address is display-only); legacy URLs keep
            working. Above the card grid sits the <Accent>identity band</Accent>: a Mapbox static thumbnail (shown only
            when a real pin resolved), an i18n'd parcel-confidence badge with a tooltip that explains a degraded state
            ("Area data — exact parcel not confirmed"), the dash-formatted PIN linking to the Cook County Assessor, and
            a facts-only verdict line composed from context flags (zone name · TIF · OZ · TOD · ADU · ARO · flood).
          </P>
          <P>
            Three page-local cards render the highest-signal facts without a model in the loop:{" "}
            <Mono>ZoningCard</Mono> (renders the Title-17 bulk standards from the scorecard API's <Mono>zone_definition</Mono>),{" "}
            <Mono>CrimeYoYCard</Mono> (year-over-year with prior-year base counts), and <Mono>Address311Card</Mono>.
            Each card carries exactly one muted "Investigate" link into the chat (solid accent is reserved for the
            purchase CTA), and the financial snapshot strip surfaces assessed value, annual tax, median comp sale, and
            active incentive zones. The whole surface is the free preview of what the $25 report contains.
          </P>

          {/* ── Parcel Identity ── */}
          <SectionHeading id="parcel-identity">Parcel Identity</SectionHeading>
          <P>
            A feasibility tool lives or dies on resolving the <em>right</em> parcel. A wrong zoning class or a
            neighbor's tax bill destroys trust permanently — and money changes hands per parcel — so parcel identity is
            modeled explicitly with one producer, one holder, and four consumers.
          </P>
          <Code>{`Producer  → _resolve_location (backend/main.py)
              returns ResolvedLocation(lat, lon, address, pin, confidence)
              strict precedence: explicit lat/lon → supplied PIN
                → address→PIN (Cook County Address Points 78yw-iddh)
                → degraded geocode + nearest-centroid → 422
Holder    → SelectedParcel, held in SelectedParcelContext (frontend)
              select(ParcelQuery) is the ONLY write site — it calls
              /api/scorecard and commits the backend's resolved pin /
              confidence / lat / lon / address atomically
Consumers → Scorecard (renders pin + confidence badge)
              Report   (request / entitlement / purchase keyed on pin)
              Chat     (reads per-message pins as history — read-only)
              Discovery(emits ?pin= navigation intent only)`}</Code>
          <P>
            Confidence is deliberately <Accent>two-valued</Accent> — <Mono>"authoritative"</Mono> or{" "}
            <Mono>"approximate"</Mono>, no other tier. Identity is never constructed client-side from raw input, URL
            params, or a Discovery row. The invariants: no silent re-resolution when a pin is known; no fidelity
            downgrade at a handoff (never coordinates when a pin exists, never an address when either exists);
            money/entitlement keys on the pin when one exists (legacy pin-less purchases stay entitled via a 4-decimal
            coordinate match); and a pin is never shown detached from its confidence tier.
          </P>
          <Sub>The Parcel That Resolved to the Neighbor — A Correctness Story</Sub>
          <P>
            For a tool that sells a per-parcel report, resolving the <em>wrong</em> parcel isn't cosmetic — it bills
            someone for their neighbor's analysis. While the Cook County GIS spatial index is down (its broken index
            times out 60s+), a typed address resolved through a coordinate pipeline: Census geocode → nearest parcel
            centroid. A read-only audit of 111 real addresses measured how often that hit the right parcel:{" "}
            <Accent>23%</Accent>. The other ~77% weren't condo-unit ambiguity — 100% of the misses were a{" "}
            <em>different building</em> on the block.
          </P>
          <P>
            The root cause was geometric. The Census geocoder returns a <em>street-interpolated</em> point — median
            31m, p90 66m from the true parcel, offset toward the street. Chicago lots are ~7.6m wide, so 31m is about
            four lots over, and "nearest centroid" almost always snapped to a neighbor. A second bug compounded it: the
            Socrata fallback fetched only the first 20 of the 500-600 parcels in the bounding box <em>with no
            ordering</em>, so the true parcel often wasn't even a candidate.
          </P>
          <P>
            The fix abandoned coordinates for identity entirely. An address is now resolved against the authoritative
            Cook County <Accent>Address Points</Accent> dataset (<Mono>78yw-iddh</Mono>) directly to a PIN, and the
            parcel is fetched by PIN — coordinates became display-only. Exact-PIN accuracy jumped
            to <Accent>98-100%</Accent>. The sharpest lesson came from a near-miss: the dataset stores the directional
            as <Mono>"WEST"</Mono>, not <Mono>"W"</Mono>, so the natural <Mono>st_predir = 'W'</Mono> query
            matched <em>nothing</em> and would have silently shipped a no-op feature to production. It was caught only
            by probing the live dataset, not by unit tests against mocked data — <em>verify the real artifact, not your
            assumption of it.</em>
          </P>

          {/* ── Feasibility Report (PDF) ── */}
          <SectionHeading id="report">Development Feasibility Report (PDF)</SectionHeading>
          <P>
            The $25 PDF report is the revenue wedge — the moment a professional needs a deliverable for a client,
            lender, or partner. It's priced per-unit (no subscription threshold), it demonstrates every underlying
            system in one artifact, and it markets itself ("Generated by UrbanLayer" travels to whoever receives it).
            <Mono>GET /api/report</Mono> assembles the same retrieval the Scorecard uses, then renders HTML/CSS to PDF
            via <Accent>WeasyPrint</Accent> over a Jinja template (<Mono>zoning_report.html</Mono>) with matplotlib map
            overlays.
          </P>
          <Sub>What the report contains</Sub>
          <P>
            A page-1 <Accent>Development Snapshot</Accent> decision box (lot · zone · max buildable · value · key
            constraint · approval path), a comp-implied valuation with honest data-limit handling, FAR-utilization
            framing ("existing X sf uses Y% of the FAR-allowed Z sf"), indicative unit yield from authoritative
            minimum-lot-area tables, a SIMPLE/MODERATE/COMPLEX regulatory <Accent>approval pathway</Accent>, an
            "Ownership Intelligence" read derived from sales/tax signals (Cook County doesn't expose owner names), and
            zoning/construction/comps maps with auto-scaled distance bars and reference rings. The synthesis is
            deterministic where it must be — ~29 opportunity/constraint rules, not a free-form LLM essay — so the
            numbers never contradict the tables.
          </P>
          <Sub>Render isolation</Sub>
          <P>
            WeasyPrint's <Mono>write_pdf()</Mono> runs in an <Accent>isolated child process</Accent>{" "}
            (<Mono>backend/report_render.py</Mono>): the parent spawns <Mono>python -m backend.report_render</Mono> with
            the HTML in a temp file and the PDF out. The child imports <em>only</em> WeasyPrint (~118 MB peak), not the
            FastAPI app or the ~3 GB discovery index, sets <Mono>oom_score_adj=1000</Mono>, carries a generous{" "}
            <Mono>RLIMIT_AS</Mono> backstop, and is killed by a parent wall-clock timeout → a clean 503 instead of an
            OOM-killed worker.
          </P>
          <Sub>The Crash That Only Happened in Production — A Reproducibility Story</Sub>
          <P>
            An earlier report-reliability incident was a textbook "works on my machine": reports generated fine
            locally, but the production worker kept dying under load. The first theory blamed the flaky Cook County
            GIS — but blackholing GIS locally didn't reproduce it (the Socrata fallback absorbed the failure with no
            exception; GIS only added latency), so that theory was <em>disproven</em> rather than assumed.
          </P>
          <P>
            The real causes were memory and the event loop. Each report held ~375 MB of render data (map rasters +
            WeasyPrint), and <Mono>write_pdf()</Mono> ran <em>synchronously</em> on the event loop — at completion it
            blocked <Mono>/health</Mono> for 6.4s, and three concurrent reports saturated the single worker and all
            timed out. Why it never showed locally: a 48 GB dev Mac <em>compresses</em> memory under pressure (a slow
            timeout cascade), while the 8 GB production box just <Accent>OOM-kills</Accent> the worker outright — the
            same bug with a completely different failure mode by environment.
          </P>
          <P>
            The fix bounded report generation with a <Mono>Semaphore(2)</Mono> and offloaded <Mono>write_pdf()</Mono>{" "}
            to a thread so it can't block the loop (the subprocess isolation above came later, in the reranker-era
            hardening). The lesson: a generous dev machine can <em>hide</em> a resource bug that a constrained
            production box surfaces as a hard kill — reproduce on production-like limits.
          </P>
          <Sub>Honesty over completeness</Sub>
          <P>
            Where the data is thin, the report says so rather than fabricating. Land-value ranges render only with ≥3
            land-bearing comps (condo-dense blocks rarely have them) — otherwise a labeled "Valuation Indicators"
            fallback anchors on median comp <em>sale price</em>. Tax-exempt parcels get a "Tax-Exempt (Class EX)"
            callout, not a residential comp number. The deliberate refusals (no automated pro-forma/IRR, no "PERMITTED"
            entitlement verdicts, no fabricated parcel geometry) are as much a part of the design as the features.
          </P>

          {/* ── Zoning Cache ── */}
          <SectionHeading id="zoning-cache">Zoning Cache</SectionHeading>
          <P>
            The report's AI zoning extraction was silently failing for months. Two compounding bugs: (1) semantic
            search fetched only a ~1,800-char <em>slice</em> of the ~30,000-char Title-17 bulk-standards table, so
            ~48/61 zones came back <Mono>low</Mono>/null and the report silently fell back to the deterministic table;
            and (2) Haiku wrapped its JSON in markdown fences, so a bare <Mono>json.loads()</Mono> threw at char 0 and
            was swallowed → fallback again. The reader saw correct bulk numbers (from the table) but zero AI value-add,
            with no error.
          </P>
          <P>
            The fix removes the reranker from the report path entirely. An offline build
            (<Mono>backend/zoning_cache_build.py</Mono>) does a <Accent>deterministic full-section fetch</Accent> of
            the complete bulk-standards table per district chapter (no semantic search, no reranker), runs it through
            Haiku, then does a <Accent>hybrid merge</Accent>: the table is authoritative for FAR / height / coverage,
            and the AI adds the setbacks and minimum-lot values the table lacks. The result —{" "}
            <Accent>57/59 zones high-confidence, 0 FAR errors</Accent> — is committed
            to <Mono>ingestion/data/zoning_cache.json</Mono> and read at request time
            by <Mono>zoning_cache.py</Mono>, falling back to the table on a miss.
          </P>
          <P>
            Known limits: AI-supplied setbacks/min-lot are not cross-validated against an authoritative source the way
            the FAR/height/coverage table is, so they carry lower trust; parking ratios were deferred (feeding the
            parking section alongside the bulk table regressed FAR extraction). A deploy gotcha worth recording: a
            committed data artifact needs a <Mono>.dockerignore</Mono> allowlist entry too, not just a{" "}
            <Mono>.gitignore</Mono> exclusion — the first push built without the cache and CI false-reported green.
          </P>

          {/* ── Payments & Monetization ── */}
          <SectionHeading id="payments">Payments &amp; Monetization</SectionHeading>
          <P>
            Two price points, both through <Accent>Stripe</Accent> (<Mono>backend/payments.py</Mono>): a one-time{" "}
            <Accent>$25 Development Feasibility Report</Accent> and a <Accent>$99/mo Pro</Accent> subscription
            (unlimited reports). The a-la-carte report is the wedge — the decision is "is this worth $25 for this
            parcel right now?", a far lower bar than "$99/mo forever" — and after a few reports the Pro math makes
            itself obvious ("4 reports ≈ a month of Pro").
          </P>
          <Table
            headers={["Endpoint", "Purpose"]}
            rows={[
              ["POST /api/checkout/report", "Stripe Checkout session for a single $25 report"],
              ["POST /api/checkout", "Stripe Checkout session for the $99/mo Pro subscription"],
              ["POST /api/webhook/stripe", "Webhook → records the purchase / activates the subscription"],
              ["GET /api/report/access", "Entitlement check before generating or re-downloading a report"],
            ]}
          />
          <P>
            Purchases are <Accent>PIN-keyed</Accent>: the <Mono>report_purchases</Mono> table (schema v9) records the
            14-digit pin, so entitlement is checked against the exact parcel. The frontend's report functions
            (<Mono>fetchReport</Mono>, <Mono>createReportCheckoutSession</Mono>, <Mono>checkReportAccess</Mono>) all
            take a whole <Mono>SelectedParcel</Mono> and derive the wire params internally — hand-constructing report
            identity is a compile error. Legacy pin-less purchase rows stay entitled permanently via a 4-decimal
            coordinate match. Stripe's success URL is <Mono>?pin=…&amp;report_purchased=1</Mono>, which the Scorecard
            reads to auto-download the report right after payment.
          </P>

          {/* ── Property Discovery ── */}
          <SectionHeading id="discovery">Property Discovery</SectionHeading>
          <P>
            Discovery is the second workflow: "find me parcels worth evaluating." It's a filter/search workbench
            covering the <Accent>full city — all 77 community areas / ~949k parcels</Accent> — where each result flows
            straight into the Evaluate pipeline (click a row → Scorecard → Report). Free users see a top-10 teaser;
            premium users get the full list, an interactive map, and CSV export.
          </P>
          <Sub>Compile, don't evaluate</Sub>
          <P>
            The frontend (<Mono>frontend/src/discovery/</Mono>) never filters data itself — it compiles panel/topic/text
            inputs into a <Mono>SearchRequest</Mono> and renders chips and summaries from the server's canonical query
            state (<Mono>response.cqs</Mono>), so the UI can never disagree with what the server actually ran. The
            backend (<Mono>backend/discovery/</Mono>) holds the predicates, evaluator, and registry, and serves three
            routes: <Mono>/search</Mono> (rows), <Mono>/search/pins</Mono> (the full coordinate set for the map), and{" "}
            <Mono>/search/export</Mono> (premium CSV).
          </P>
          <Sub>The prospecting index</Sub>
          <P>
            Filtering ~949k parcels interactively requires a precomputed index with derived fields:{" "}
            <Mono>value_percentile</Mono>, an <Mono>upside_score</Mono> heuristic (documented v1, not oversold),{" "}
            <Mono>is_teardown_candidate</Mono>, and transit proximity, plus a <Mono>populated_fields</Mono> manifest
            that drives honest cold-start behavior. Recipe shortcuts ("undervalued multifamily") show 3-state counts —
            "Live · N" / "No matches yet" / "Needs data" — instead of advertising filters that can't run. Building the
            index surfaced the <Accent>CCAO valueless-latest-year bug</Accent>: the assessor's in-progress year has
            null value columns that Socrata omits from JSON, so a naive "latest year" join resolved every parcel to a
            valueless row — fixed by requiring a non-null total (and verified safe in the scorecard/report path too).
          </P>
          <Sub>Memory-bounded, off-box build</Sub>
          <P>
            The full-city index is built off the live backend (<Mono>docker compose run --rm</Mono>, its own cgroup,
            shared data volume) and is memory-bounded by construction: per-community-area ingest plus a streaming
            finalize that recomputes percentiles/manifests over the SQLite index in chunks. Full 77-CA runtime is
            ~2.98 GB RSS — 39% of the 8 GB box, ~2.37 KB/parcel. (The earlier "1.8M parcels won't fit" worry was a unit
            error: that figure is Cook County <em>with</em> suburbs; Chicago's 77 CAs are ~949k.) A monthly refresh
            timer keeps it current.
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
            WAL mode via <Mono>aiosqlite</Mono>, singleton connection, schema v11. Tables: <Mono>conversations</Mono>,
            <Mono>messages</Mono> (with JSON blob columns for context/plan/mapData), <Mono>uploads</Mono>,
            <Mono>llm_calls</Mono>, <Mono>request_logs</Mono>, <Mono>schema_version</Mono>,
            <Mono>users</Mono>, <Mono>refresh_tokens</Mono>, <Mono>share_tokens</Mono>, <Mono>report_purchases</Mono> (v9),
            and <Mono>events</Mono> (v10, usage analytics); v11 made purchases PIN-bound. JSON blob columns
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
            <Mono>AuthProvider</Mono> wraps the app, exposing <Mono>useAuth()</Mono> throughout. There is{" "}
            <em>no</em> gate on <Mono>sendMessage</Mono> — anonymous chat works at the server-enforced 3/day IP limit
            (in-memory only, never persisted), so the front door doesn't ask for an account. The sign-in modal appears
            only at identity moments (save/share, purchase, or a 429 rate-limit). The <Mono>401-interceptor</Mono>{" "}
            in <Mono>authFetch()</Mono> intercepts expired tokens:
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

          {/* ── Usage Analytics ── */}
          <SectionHeading id="usage-analytics">Usage Analytics</SectionHeading>
          <P>
            Distinct from the LLM-cost observability above, a lightweight first-party tracker
            (<Mono>frontend/src/lib/tracking.ts</Mono>) instruments the funnel so customer validation is backed by
            behavior, not just opinion. No third-party analytics SDK — events are written to the
            app's own <Mono>events</Mono> table (schema v10) and surfaced in the admin engagement dashboard.
          </P>
          <P>
            Eight events trace the path from landing to purchase: <Mono>page_view</Mono>, <Mono>hero_address_submit</Mono>,{" "}
            <Mono>hero_librarian_click</Mono>, <Mono>investigate_click</Mono>, <Mono>chat_message_sent</Mono>,{" "}
            <Mono>scorecard_bridge_click</Mono>, <Mono>report_cta_click</Mono>, and <Mono>sample_report_click</Mono>.
            Each carries a per-tab <Accent>session ID</Accent> and a cross-session <Accent>visitor ID</Accent>, so the
            same person can be followed across visits without accounts.
          </P>
          <P>
            Delivery is cheap and loss-resistant: events batch in memory and flush every 30s, with
            a <Mono>navigator.sendBeacon</Mono> on page hide so the last events survive a tab close. Ingestion is
            fire-and-forget on the backend — a failed analytics write never degrades the user-facing request.
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

          <Sub>Retrieval Quality Benchmark (28 queries)</Sub>
          <P>
            <Mono>eval/retrieval_benchmark.py</Mono> with gold section IDs and expected answer terms per query.
            Grades: A (gold hit + terms), B (gold hit, some terms missing), C (partial), D/F (miss).
          </P>
          <Table
            headers={["Version", "A", "B", "C", "D", "F", "Key Change"]}
            rows={[
              ["v1 (baseline)", "11", "1", "4", "1", "1", "No dedup, no keyword boost"],
              ["v3", "13", "1", "4", "0", "0", "Per-section dedup + keyword boost"],
              ["v4", "15", "1", "2", "0", "0", "bge-reranker-v2-m3, rerank-before-dedup"],
              ["v5 (current)", "26", "2", "0", "0", "0", "Synonym expansion, keyword-aware dedup, 0.20 keyword weight"],
            ]}
          />
          <P>
            v5 reaches <Accent>100% A/B</Accent> across the (expanded) 28-query set. The two C-grades that survived v4
            (<Mono>adu_allowed</Mono>, <Mono>lot_coverage_rm5</Mono>) were terminology gaps; synonym expansion at query
            time closed them. Note the benchmark numbers are from the <em>full</em> pipeline including the reranker —
            in production (reranker off) the dense+keyword fallback carries the chat path, and the report path uses the
            precomputed zoning cache rather than retrieval at all.
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
              ["Sub-source checks", "41"],
              ["Covered", "38/41 (93%)"],
              ["Known gaps", "Property characteristics (GIS intermittent), Assessments (CCAO 400s), Tax (PTaxSim optional)"],
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
              ["Instance", "CX32 — 4 vCPU, 8GB RAM, 80GB SSD (upgraded from CX22/4GB, 2026-06-06)"],
              ["Swap", "8GB (swappiness=10) — cushions transient render/index spikes (grown from 2GB)"],
              ["OS", "Ubuntu 22.04"],
            ]}
          />
          <P>
            Chosen over AWS/DigitalOcean/Railway for cost — the same RAM at Hetzner costs a fraction of US cloud
            providers. The CX22 (4GB) was outgrown once the discovery index (~3GB resident) and PDF rendering landed,
            so the box was bumped to 8GB plus 8GB swap. The trade-off is higher latency for US users (Nuremberg → US
            adds ~100ms) and no managed scaling, but acceptable for a portfolio project.
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
            GitHub Actions workflow on push to <Mono>main</Mono>: runs the backend test suite (~599 unit tests;
            56 real-API integration tests are excluded), the frontend vitest suite, the TypeScript type check, and
            the frontend build. On success, SSHs into the production server, pulls the latest code, and rebuilds
            Docker containers — so a push to <Mono>main</Mono> is a deploy. Claude Code GitHub App provides AI code
            review on PR open/synchronize events.
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
              ["/api/report 504s", "Reranker hung extract_zoning_standards (~40s/search × 5 parallel) past the nginx ceiling — diagnosed past a false OOM lead", "RERANKER_ENABLED=false + report decoupled via a precomputed zoning cache; dedicated nginx 180s timeout on /api/report"],
              ["Report worker OOM risk", "WeasyPrint render + 3GB index in one process", "write_pdf() isolated in a ~118MB child process (oom_score_adj, RLIMIT_AS, wall-clock timeout → clean 503)"],
              ["Silent zoning extraction failure", "Partial-slice retrieval of 30K-char tables + markdown-fenced LLM JSON, both swallowed → silent table fallback", "Precomputed zoning cache (full-section fetch + hybrid merge); strip code fences before json.loads"],
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
            <Mono>App.tsx</Mono> implements a dual-mode UI: splash (the address-first homepage) and workspace (chat +
            sidebar). The homepage hero (<Mono>HeroEntrance</Mono>) leads with a single address input that opens{" "}
            <Mono>/scorecard?address=</Mono> — the code-research chat (the "librarian") is a quiet secondary entrance,
            keeping the front door pointed at the feasibility product. Workspace
            activation: <Mono>{"active = messages.length > 0 || streaming"}</Mono>, a hard cut with an opacity
            transition. The first user message auto-creates a conversation and routes to <Mono>/c/:id</Mono>.
          </P>

          <Sub>URL Routing</Sub>
          <P>
            <Mono>react-router-dom</Mono> routes: <Mono>/</Mono> (address-first splash),{" "}
            <Mono>/c/:id</Mono> (conversation), <Mono>/s/:shareToken</Mono> (shared read-only view),{" "}
            <Mono>/scorecard</Mono> (parcel Scorecard, non-AI), <Mono>/discovery</Mono> (Property Discovery
            workbench), <Mono>/pricing</Mono> (Free vs Pro), <Mono>/admin</Mono> (dashboard, admin-only
            via <Mono>ProtectedRoute</Mono>), and <Mono>/about</Mono> (this page). <Mono>/explore</Mono> was retired —
            it now redirects to <Mono>/discovery</Mono>. Conversations and parcels are bookmarkable and work with
            browser back/forward. A <Mono>useConversationRouter</Mono> hook syncs <Mono>conversationId</Mono> with the
            URL bidirectionally; invalid conversation URLs redirect to <Mono>/</Mono>.
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

          {/* ── Design System ── */}
          <SectionHeading id="design-system">Design System</SectionHeading>
          <P>
            As the surface area grew (Scorecard, Report, Discovery, chat, landing), arbitrary <Mono>text-[Npx]</Mono>{" "}
            sizes, ad-hoc <Mono>white/opacity</Mono> chrome, and off-palette hues had crept in. A unification pass
            replaced them with a small, role-based token system — the same tokens this page is built on. The goal:
            decisions are made by <em>picking a token</em>, not inventing a value.
          </P>
          <Sub>Type scale</Sub>
          <P>
            Ten named steps replace every arbitrary pixel size — <Mono>text-display / stat / section / subtitle /
            lead / title / body / caption / micro / overline</Mono>. Each bakes in size, line-height, and weight, so
            you pick the step rather than overriding weight per use.
          </P>
          <Sub>One neutral ramp</Sub>
          <P>
            A single neutral system (bg <Mono>#0d0d0d</Mono> → surface → elevated → hover, with subtle/regular/strong
            borders, and primary/secondary/muted text) retired the parallel <Mono>white/opacity</Mono> chrome fork and
            the one-off <Mono>bubble/drawer/tooltip</Mono> tokens. The accent is a single warm
            terracotta (<Mono>#c96442</Mono>) with hover and muted variants.
          </P>
          <Sub>Radius by role</Sub>
          <P>
            Radius encodes role rather than taste: card/panel/modal <Mono>rounded-xl</Mono>, control/input/button{" "}
            <Mono>rounded-lg</Mono>, chip/badge <Mono>rounded-md</Mono>, inline code <Mono>rounded</Mono>, and
            avatar/dot/pill <Mono>rounded-full</Mono> (<Mono>2xl</Mono> reserved, by intent, for chat bubbles, the
            composer, and Pricing cards).
          </P>
          <Sub>Fonts</Sub>
          <P>
            Three families, each scoped: <Accent>Inter</Accent> for body/UI, <Accent>Space Grotesk</Accent> for display
            (scoped to <Mono>.text-display</Mono> / <Mono>.text-section</Mono> headings only), and{" "}
            <Accent>IBM Plex Mono</Accent> for PINs, code, and data.
          </P>
          <Sub>Primitives &amp; color discipline</Sub>
          <P>
            Three shared primitives in <Mono>src/components/ui/</Mono> — <Mono>Card</Mono>, <Mono>Chip</Mono>,{" "}
            <Mono>Modal</Mono> — replace hand-rolled card/chip/dialog chrome. The §6 color rule keeps chrome to{" "}
            <Accent>accent + neutral only</Accent>; hue is reserved for genuine state
            (<Mono>positive</Mono>=emerald, <Mono>negative</Mono>=rose, <Mono>warning</Mono>=amber). The deliberate
            exemptions — text over photos, and functional data encoding (map colors, the Discovery upside ramp, data
            pills, CTA/score colors) — are where color carries real meaning rather than decoration.
          </P>

          {/* ── 20. Testing ── */}
          <SectionHeading id="testing">Testing</SectionHeading>
          <P>
            ~655 backend tests (599 unit + 56 real-API integration). The everyday baseline is{" "}
            <Mono>pytest -m "not integration"</Mono> — the integration tests hit live external APIs and fail on
            network/GIS flakiness, not code. The frontend adds a <Mono>vitest</Mono> suite (~51, covering the Property
            Discovery compiler/selectors), a clean <Mono>tsc</Mono> build, and a <Mono>npm run build</Mono> producing
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
              ["Report & Payments", "report_tier0/1, report_render, zoning_extract, resolve_location", "Render isolation, zoning extraction, address→PIN precedence, Stripe entitlement"],
              ["Discovery", "discovery (compile/evaluate/registry) + vitest", "CQS compile, predicate evaluation, index build, FE compiler/selectors"],
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
              ["Scorecard as free zero-LLM hook", "Gate everything behind chat/auth", "Instant zero-cost facts earn trust before asking for an account or payment; pushes users to Scorecard first, chat second", "Some users never reach the paid report"],
              ["$25 per-unit report wedge", "Subscription-only", "A $25 per-parcel decision is a far lower bar than $99/mo; a tangible PDF that markets itself", "Lower ARPU than pure subscription; per-report compute cost"],
              ["Precomputed zoning cache", "On-demand reranked AI extraction", "Reranker too slow on prod vCPUs; deterministic full-section fetch + hybrid merge is faster AND more accurate (57/59 high-confidence)", "Cache must be rebuilt when Title 17 changes; setbacks uncross-validated"],
              ["SelectedParcel single write site", "Resolve the parcel ad hoc per surface", "Guarantees the pin shown is the pin queried, purchased, and reported on", "More plumbing; every handoff must thread identity"],
              ["Address→PIN via Address Points", "Census geocode + nearest centroid", "Authoritative resolution to the exact parcel — typed addresses were ~77% wrong while GIS is down", "One more Socrata dataset; coverage gaps degrade to 'approximate'"],
              ["Stripe hosted Checkout", "Self-hosted card form", "No PCI surface; one integration covers both one-time and subscription", "Redirect flow; Stripe lock-in"],
              ["Off-box, memory-bounded index build", "Build on the live serving process", "Full-city index build (~3GB) doesn't compete with the server for RAM; bounded by per-CA ingest + streaming finalize", "Extra deploy step; index is stale between monthly rebuilds"],
              ["Subprocess PDF render", "Render in the request process", "Isolates WeasyPrint memory — an OOM kills the child, not the worker", "IPC + temp-file handoff overhead"],
              ["Role-based design tokens", "Ad-hoc Tailwind classes", "Picking a type/neutral/radius token prevents drift across a growing surface area", "One-time migration cost"],
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
            <p className="text-text-muted text-body">
              ~655 backend tests. 14,535 code chunks indexed. ~949k parcels in the discovery index.
              25+ live datasets. 4 domain orchestrators. Scorecard + cited chat + $25 PDF report + discovery.
              Built with FastAPI, Claude, Qdrant, React, Mapbox, deck.gl, WeasyPrint, and Stripe.
              Live at urbanlayerchicago.com.
            </p>
          </div>
        </article>
      </div>
    </div>
  );
}
