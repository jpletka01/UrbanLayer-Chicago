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
  { id: "scorecard", title: "The Property Profile" },
  { id: "parcel-identity", title: "Parcel Identity" },
  { id: "lot-facts", title: "Lot Facts & Provenance" },
  { id: "verifiable", title: "Verifiable Answers" },
  { id: "report", title: "Feasibility Report (PDF)" },
  { id: "zoning-cache", title: "Zoning Cache" },
  { id: "payments", title: "Payments & Monetization" },
  { id: "discovery", title: "Property Discovery" },
  { id: "conversation", title: "Conversation Management" },
  { id: "auth", title: "Authentication & Security" },
  { id: "rate-limiting", title: "Rate Limiting" },
  { id: "security-hardening", title: "Security & Hardening" },
  { id: "map", title: "Map & Geo Visualization" },
  { id: "sidebar-cards", title: "Sidebar & Data Cards" },
  { id: "analytics", title: "Analytics" },
  { id: "usage-analytics", title: "Usage Analytics" },
  { id: "file-upload", title: "File Upload & Vision" },
  { id: "admin", title: "Admin & Observability" },
  { id: "correctness", title: "Measuring Correctness" },
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
            <em>"What can I build here, and should I?"</em> Type an address and you get the parcel's
            full <Accent>Property Profile</Accent> (zoning, overlays, incentives, tax projection, comparable sales — about a second when
            cached, 15–40 seconds on a first lookup, which queries 25+ public sources);
            interrogate it via chat with cited municipal code; and buy a $25
            PDF <Accent>Development Feasibility Report</Accent>. Live at <Mono>urbanlayerchicago.com</Mono>.
          </P>
          <P>
            Under the hood it is a retrieval-augmented generation (RAG) system combining <Accent>25+ live
            datasets</Accent> across 5 APIs (Chicago Socrata, Cook County Socrata, ArcGIS, Census, and external
            services), <Accent>semantic search</Accent> over the entire Chicago Municipal Code (16,576
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
              ["Evaluate (today's wedge)", "\"I found a parcel. Should I develop it?\"", "Property Profile (free hook) → Chat (cited analysis) → $25 Report (the deliverable)"],
              ["Discover (second wedge)", "\"Find me parcels worth evaluating.\"", "Property Discovery workbench (filters over ~949k parcels) → each result flows into Evaluate"],
            ]}
          />
          <P>
            The <Accent>Property Profile</Accent> is the hook: fast, free, anonymous, and <em>zero LLM cost</em> — it
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
│  ├─ Qdrant Vector Search (16,576 chunks, bge-base)        │
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
│  map_data → tokens → done │  37 synthesis rules
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
              ["Persistence", "SQLite via aiosqlite (WAL), schema v14", "Single user, single writer — simplest correct solution"],
              ["Auth", "Google OAuth2 + self-rolled JWT", "One-click sign-in; httpOnly cookies + CSRF double-submit"],
              ["Frontend", "React + TypeScript + Vite + Tailwind v3", "Type-safe, light/dark/system themes; Inter / Inter Tight / JetBrains Mono"],
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
            containing the Chicago Municipal Code, including Title 14 (the building code) and Titles 16–17 (zoning). Gitignored due to size.
          </P>
          <Code>{`HTML (100MB) → parse → 9,487 sections → chunk → 16,576 chunks → embed → Qdrant
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

          <Sub>The Title That Was Parsed and Then Thrown Away — An Ingestion Story</Sub>
          <P>
            For months the corpus had no building code at all — Title 14, the rules a demolition or renovation permit
            actually turns on. The project's own notes blamed the parse regex and said a fresh HTML download was needed.
            Both were wrong: the committed HTML already contained Title 14 and the section regex already matched it.
            A <em>second, narrower</em> gate in the write path (<Mono>{"\\d+-\\d+-\\d+"}</Mono>) then rejected every section the
            parser had just found. Both now derive from a single section-id pattern, so they cannot drift apart again.
          </P>
          <P>
            Title 14 turned out to be eleven lettered volumes (14A, 14B … 14X), and the Energy Transformation Code letters
            its chapter and section segments too (<Mono>14N-C4-C402</Mono>), which also recovered 50 headings that had
            been silently missing. The corpus grew from <Accent>8,615 to 9,487 sections</Accent> and from{" "}
            <Accent>14,535 to 16,576 chunks</Accent>, purely additive. Pushing it to production surfaced three traps worth
            keeping: embedding assigns a random id per point, so re-inserting <em>duplicates</em> rather than replaces
            (116 duplicate points were created locally before this was understood — verify per-section counts, not just
            the total); the content hash omits the section title, so a heading-only fix is a silent no-op; and a code
            deploy does not update the vector store, because Qdrant lives on a persisted volume.
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
            out. Property Profile and chat stayed up, so the outage was report-only. <Accent>The first wrong guess:</Accent>{" "}
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
    "raw": "1601 N Milwaukee Ave",
    "type": "address",
    "resolved_community_area": 24,
    "resolved_address": "1601 N Milwaukee Ave, Chicago, IL",
    "resolved_lat": 41.9109,
    "resolved_lon": -87.6778
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
              ["done", "final metadata", "Attach context/plan/mapData to message; carries truncated and citation_warnings"],
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
            Clicking switches sidebar to the Data tab. Parcel facts cite <Mono>[data:{"<fact id>"}]</Mono>, accepted only
            when that turn actually carries a provenance entry for the fact.
          </P>
          <P>
            Citations are <Accent>checked, not trusted</Accent>: every completed answer is validated against the turn's
            own context (<Mono>citations.py</Mono>) — a <Mono>[7]</Mono> when only five code chunks were retrieved, or a{" "}
            <Mono>[data:x]</Mono> for a source that was not present, is logged and reported on the <Mono>done</Mono>{" "}
            event, and the full-pipeline eval fails the query. Before this, the UI silently dropped a fabricated marker, so it
            was invisible to users, logs and evals alike. The model also no longer writes its own links — see Verifiable
            Answers.
          </P>

          <Sub>Answers That Say When They Were Cut Off</Sub>
          <P>
            Answers have a 2,000-token ceiling. On the parcel benchmark, 6 of 7 chat answers hit it mid-sentence with no
            indication, and two lost the final question. The stream now reads the model's stop reason: on a cut-off it
            appends a localized notice and sets <Mono>truncated: true</Mono> on <Mono>done</Mono>, and the prompt
            asks for roughly 800 words, every numbered part answered in order, no closing recap. The token cap was
            deliberately <em>not</em> raised — brevity and a visible notice first, because a higher cap is a cost decision.
            Silent cut-offs went from 6 of 7 to zero; 2 of 7 still reach the ceiling, and now say so.
          </P>

          <Sub>Synthesis Rules</Sub>
          <P>
            The system prompt enforces 37 rules including: always cite inline (never end-of-message); surface 7-day crime data lag;
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

          {/* ── The Property Profile ── */}
          <SectionHeading id="scorecard">The Property Profile</SectionHeading>
          <P>
            The Property Profile is the product's hook: type an address, get the parcel's complete structured assessment:
            about a second once an address is cached, 15–40 seconds for a first lookup while 25+ sources respond. It is <Accent>free, anonymous, and zero LLM cost</Accent> — <Mono>GET /api/scorecard</Mono> reads
            straight from the data layer and domain orchestrators, no synthesis pass. It earns the user's trust ("this
            is right") before asking for anything, then bridges into the chat (Investigate buttons) and the paid report
            (Download CTA).
          </P>
          <P>
            The page (<Mono>ScorecardPage.tsx</Mono>) accepts a parcel three ways, in precedence
            order: <Mono>?pin=</Mono> → <Mono>?address=</Mono> → <Mono>?lat=&amp;lon=</Mono>. A pin-confirmed result
            canonicalizes the URL to <Mono>?pin=&amp;address=</Mono> (the address is display-only); legacy URLs keep
            working. The hero is a display-scale address with a circled resolution badge (green check = exact, amber =
            approximate or unconfirmed, meaning on hover), an area · ward · PIN subline, a one-sentence verdict, and{" "}
            <em>one</em> action row with one filled button — the report offer, with its sample link directly beside it.
            A deterministic <Accent>verdict band</Accent> (six categories, no model) leads the page with its reasons as tags;
            a four-tile KPI strip follows (zoning/FAR, assessed value against the area median, estimated tax with its
            effective rate, comps median), then four module bands — Build, Costs, Market, Record — plus a Neighborhood
            module, each opening with a one-sentence takeaway.
          </P>
          <P>
            Three scoped maps each answer one question: <em>place</em> (satellite or streets, the parcel outline, comps and
            transit scoped to the opening viewport), <em>zoning</em> (the quilt around the parcel) and{" "}
            <em>boundaries</em> (overlay, TIF and enterprise-zone boundaries, with hover that picks every stacked layer).
            Definitions live in tooltips, never in on-page copy, and every "ask" chip opens a grounded quick-chat dock instead
            of navigating away. The whole surface is the free preview of what the $25 report contains.
          </P>

          <Sub>Marketing Copy Is a Claim Too</Sub>
          <P>
            The homepage's hero card and its "every rule, one verdict" section described 1601 N Milwaukee Ave with invented
            data: a made-up PIN, "B3-2 at FAR 1.2" (the ordinance says 2.2), a quote attributed to §17-2-0300 (the
            <em> residential</em> chapter), $8,420 in tax and "0 active overlays". The live profile, one click away, says
            otherwise — it is a landmark in a historic district and reads "Constrained upside". Both sections now use the live
            record and verbatim Title 17 text. The same audit caught the page promising "~2 seconds" when a cold lookup takes
            15–40 s and a cached one about a second. The loading state now names the address, counts elapsed seconds and says
            what a first lookup costs — it does not fake per-step progress, because the sources resolve in parallel and
            nothing is streamed. And because the profile caches are in-memory (crime and 311 live 15 minutes, and every deploy
            empties them), a warm-up script requests the three demo addresses after each deploy and a timer repeats it every
            ten minutes: measured on production, 14.8 s cold versus 0.8 s warm.
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
Consumers → Property Profile (renders pin + confidence badge)
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

          <Sub>The Same Bug on a Second Surface</Sub>
          <P>
            The Address Points fix landed on the Property Profile — and the chat kept the old behavior. An address typed into
            chat went through the router's Census geocode, whose street-interpolated point can sit in a neighboring parcel or
            zoning district. The parcel benchmark (see Measuring Correctness) caught it: on seven hard parcels, chat named the
            wrong zoning district on two and showed a neighbor's PIN and facts on five. A typed address in chat is now
            resolved through the same Address Points / Assessor path as the Profile and uses the parcel's own point, PIN and
            community area; if no confident parcel exists it keeps the geocode, <em>marks the result approximate, and the
            answer says so</em>. Wrong districts went from 2 to 0 and the chat's PIN matched the Profile's on 7 of 7. The
            lesson generalizes: fixing identity on one surface does not fix it on another, and only a benchmark that asks both
            the same question noticed.
          </P>
          <P>
            Two smaller identity guards came from the same review. The geocoder is national, so "1600 Pennsylvania Ave
            Washington DC" used to return a full Property Profile assembled from Chicago sources — including a brownfield
            hundreds of miles away — with a $25 report offer; the profile and report endpoints now return 422 unless the point
            is in, or within about 200 m of, a Chicago community area. And a typo in the search box ("2130 N Hoyn Ave")
            used to submit the raw text on Enter, taking 56 seconds and resolving to an unverified neighbor even while the
            dropdown showed the right address; Enter now takes the corrected suggestion when the house number matches.
          </P>

          {/* ── Lot Facts & Provenance ── */}
          <SectionHeading id="lot-facts">Lot Facts &amp; Provenance</SectionHeading>
          <P>
            The lot facts — land area, building sqft, tax bill, zoning envelope — are the product's paid core, and a
            July 2026 audit started from nothing more than a hunch that too many of them were blank. Rather than fix
            anecdotes, the first move was a <Accent>benchmark</Accent>: a frozen panel of 100 real addresses (sampled
            from Cook County Address Points, stratified across all 7 Chicago township PIN prefixes, committed to the
            repo so every run measures the same parcels) pushed through the live <Mono>/api/scorecard</Mono> surface,
            with every field classified as present, missing, or <em>legitimately absent</em> — vacant land has no
            building sqft, exempt parcels have no tax bill, and counting those as gaps would corrupt the metric. A
            sequential retry pass split true data gaps from transient API failures.
          </P>
          <P>
            The numbers were damning and precise: land and building sqft sat at <Accent>~20%</Accent> (0% outside
            residential — the only populated source was the CCAO characteristics dataset, which covers regression-class
            residential only), stories at 1% (a column-mapping bug: <Mono>char_ncu</Mono> is the <em>commercial unit
            count</em>, not stories, and <Mono>char_apts</Mono> ships decoded words like <Mono>"Two"</Mono> that an
            int-parse silently nulled), and — the sharpest finding — <Accent>production had served zero tax data since
            launch</Accent>: the 9.4 GB PTAXSIM database was optional-by-design, was never seeded on the box, and
            nothing anywhere surfaced its absence. Local ran at 100% while every real customer saw nulls.
          </P>
          <P>
            The fixes came in waves, each re-measured against the same panel. The elegant one: PTAXSIM turned out to
            ship an indexed <Mono>pin_geometry_raw</Mono> table — a WKT polygon for every parcel in the county — so
            land area is now <Accent>computed on demand from the parcel's own boundary</Accent> (equirectangular
            scaling, ~ms per lookup, no new dependency), covering every property class the assessor datasets don't.
            Building facts fill through a provenance-labeled fallback chain: CCAO characteristics → condo unit
            characteristics → the Commercial Valuation dataset (one row <em>per building</em> per economic unit — you
            sum the latest year) → city building footprints. Fallbacks never override assessor data, and every derived
            number carries its source (<Mono>land_sqft_source: "geometry"</Mono>), which the Property Profile renders as a
            muted suffix. Honest beats complete: planned developments show "Set by PD ordinance" instead of a blank
            FAR, and a failed zoning lookup now raises into a visible partial-failure instead of rendering as
            "no zoning".
          </P>
          <P>
            The same arc added fact families the product never had: per-PIN <Accent>tax exemptions</Accent> (with the
            buyer caveat — owner-occupancy exemptions don't transfer, so the listed bill understates a buyer's bill),
            <Accent> assessment appeal history</Accent> from both the Assessor and Board of Review stages plus a
            spatial neighbor aggregate ("107 appeals within a block, 38 won reductions, median −16.9%"), ward +
            alderman on the identity line, and distress/opportunity flags (city-owned land with application status,
            scofflaw list, short-term-rental opt-outs, historic tax-sale years — always dated, never dressed up as
            current distress). End state on the panel: <Accent>every critical field ≥85%, most at 100%</Accent>, and
            the benchmark stays in the repo as the regression gate for the data layer.
          </P>

          {/* ── Verifiable Answers ── */}
          <SectionHeading id="verifiable">Verifiable Answers</SectionHeading>
          <P>
            A zoning tool is only useful if you can check it, and a screening page that never says where it stops reads as a
            determination. In October 2026 the Property Profile and the chat were rebuilt around one principle: <Accent>every
            claim should be checkable, dated, and honest about its edges</Accent>. Each piece below is deterministic — no model
            decides what to cite — and each statement about the code is pinned to the ingested ordinance text by a test, so a
            wrong claim fails CI rather than shipping.
          </P>

          <Sub>A dated source for every fact</Sub>
          <P>
            <Mono>/api/scorecard</Mono> returns a <Mono>provenance</Mono> map: for the district (with the ordinance and both
            dates), each standard (with the code section it comes from and the code's current-through date), each overlay (with
            the City layer and link), the parcel identity, the land and building area (with the dataset that supplied it) and
            the code vintage. A fact that isn't present gets no entry. The benchmark counts how many stated facts carry one:
            <Accent> 46 of 46</Accent> — but only <Accent>25 of 46</Accent> carry a date the source itself gives; overlays and
            identity carry only the date we queried them, because the City's layers publish no per-feature date. Taxes,
            comparables and permits are not covered yet. The page reports the weaker number alongside the stronger one.
          </P>

          <Sub>Click a standard, read the code</Sub>
          <P>
            Every standard on the zoning card links to the exact subsection it comes from ("§17-2-0304-A"). The click opens that
            subsection's text, the table it cites, and how current the code is — "current through …, a later amendment may not
            be reflected." The index holds whole articles (17-2-0300 is ~32,000 characters, with tables appended as blocks), so{" "}
            <Mono>GET /api/code/section/{"{id}"}</Mono> cuts the cited subsection out, re-merges tables the index had split into
            row batches, and parses the flattened "Row n: A: x; B: y" text back into columns. A missing section is a 404, never a
            guess. It reads the production index, so it needed no new data and no image change.
          </P>

          <Sub>How the address became this parcel</Sub>
          <P>
            The Profile used to show a PIN and a green check. It now says which record matched the address, lists every parcel
            the county's two address sources give for it (the used one marked), flags when the sources disagree, recognizes a
            condominium (a building PIN versus its unit PINs is not a disagreement), shows the gap between the address point and
            the parcel's center, and gives the reason when identity could not be confirmed. Running it on the seven benchmark
            parcels turned up what a single check hid: a vacant lot has no address point at all and resolves through the
            Assessor; one address maps to three parcels; for another, the county's two "authoritative" sources name{" "}
            <em>different parcels</em>; and one is a condo building with one building PIN and about fifty unit PINs. It also
            exposed a latent bug in the Assessor resolver: the portal spells one year both "2025.0" and "2025", so
            raw-text bucketing counted two years and a multi-parcel address could resolve to a single parcel with false
            confidence.
          </P>

          <Sub>Where the analysis stops</Sub>
          <P>
            Each parcel now carries notes saying where the page's analysis ends, each true and sourced. For this parcel: a
            Planned Development's numbers come from its ordinance, not the base district (with the ordinance PDF); a Chicago
            Landmark or landmark district needs the Commission on Chicago Landmarks' written approval (§2-120-740); an orange or
            red historic-survey building can have a demolition permit held up to 90 days (§14A-4-407.6); a recent rezoning may not
            be on the City's map yet; an ADU zone has limits. For every parcel: the alderman's notice role on map amendments,
            Planned Developments and special uses (§17-13); the City's 90-day map lag; the Municipal Code's current-through date;
            and that this is a screening tool — the City's Zoning Verification Letter is the official confirmation. The benchmark
            requires that each parcel carry <em>exactly</em> the notes that apply (7 of 7). Honest edges: the survey-hold note is
            unit-tested only because no benchmark parcel is rated orange or red, and the PDF report does not carry these notes yet.
          </P>

          <Sub>Rezoned three months ago — and the product couldn't say so</Sub>
          <P>
            One benchmark parcel had been rezoned from M1-2 to RT-4 by an ordinance passed in June 2026. The City's zoning layer
            already returns the ordinance date, the record's last-edited timestamp, and the clerk's ordinance number and link —
            and all of it was being discarded. Worse, the layer's <em>application</em> number (<Mono>23082T1</Mono>) was shown as
            "the ordinance", and the chat model read it as a year. The lookup now keeps those fields, names the application number
            for what it is, flags a district changed within 180 days, and reads the Municipal Code export's own "Current through
            Council Journal of …" header at ingestion. Every Profile carries two stamps — when this district's zoning record was
            last updated, and the date the indexed code is current through — and chat names the ordinance with its clerk link,
            says the code text may lag, and notes that the City says amendments can take up to 90 days to reach the map. The stamp
            is deliberately labelled for <em>this district's record</em>, not "the map": the layer gives per-polygon edit dates,
            not a refresh date for the whole map.
          </P>

          <Sub>Naming the overlays, and what they require</Sub>
          <P>
            The Profile used to call the 606 district "Special Districts", call any hit on the ADU layer "ADU eligible" without
            naming the zone or its limits, link nothing for a Planned Development, and describe a landmark's consequence as "expect
            design review". The City's layers carry the real names, links and limits, so they are now shown: the 606 district by name
            with its code link and its real scope (RS-3 and RT-3.5 only), the ADU zone with its annual limit and owner-occupancy
            rule, the PD's number and ordinance PDF, and the written-approval requirement for landmarks. Coach houses are "by
            right" in RT, RM and B1–C2, allowed with the zone's limits in an RS ADU-Allowed Area, and not allowed in RS outside
            one — pinned to the use tables and §17-7-0570.
          </P>

          <Sub>One helper per claim, pinned to the code</Sub>
          <P>
            The benchmark found two claims the product was getting wrong, and in both the fix was a single deterministic helper
            feeding every surface — the Profile payload, a cold chat turn, and the Profile-to-chat handoff.
          </P>
          <P>
            <Accent>The density bonus the code doesn't give.</Accent> Every transit-served parcel was told it gets "reduced parking
            minimums and a density bonus". The code gives parking relief to every district (§17-10-0102-B) but FAR, height and
            lot-area increases only to dash-3 districts (B-3, C-3, D-3), and only through a Type 1 amendment, a Planned
            Development or an ARO entitlement (§17-3-0402/0403/0408-B). The chat model had also read "B-3 and C-3 districts" as
            "B3 and C3". <Mono>tod_benefits()</Mono> now decides, pinned to the ordinance text by a test; the benchmark's
            confident-wrong count on the Profile went from 2 to 0.
          </P>
          <P>
            <Accent>The number the model recalled from memory.</Accent> The Profile never showed minimum lot area per dwelling
            unit — the number a unit count turns on — and chat filled it in from memory. On a vacant RM-4.5 lot it said 1,000 sq ft,
            FAR 2.2 and "3 units"; the zoning table says 700 sq ft, FAR 1.7 and 4 units. The zone table now rides into the model's
            context on every parcel-resolved turn, a prompt rule forbids quoting a standard that isn't in the data, and the Profile
            shows "max units by lot area" with its arithmetic ("3,191 ÷ 700 = 4.6 → 4") and an explicit label that it is
            lot-area-per-unit only, since FAR, height and parking can bind first. Not done yet: setbacks, and applying the 606
            reduction to the yield.
          </P>

          <Sub>The model does not write its own sources</Sub>
          <P>
            The benchmark's baseline chat answers carried 18 URLs; <Accent>9 were composed by the model</Accent> — American Legal
            links with made-up ids (one id cited for two different sections) and Legistar links nobody supplied. A reader who
            clicks one lands somewhere that does not say what the answer claims. Three layers now prevent that. A streaming{" "}
            <Mono>UrlGuard</Mono> drops any URL we did not supply (a link keeps its visible label); it is tested to produce
            identical output however the stream is chunked, loses nothing at end-of-stream, and cannot be stalled by a stray
            bracket. The prompt forbids writing links or a sources section. And a deterministic "Sources for the parcel data used"
            block is appended from the provenance map plus the code chunks the answer actually cited, with the code's
            current-through date. Replaying three recorded benchmark runs through the guard offline, it would have removed 10, 5 and
            1 model-written URLs and kept every URL we supplied (8, 9 and 9) — a replay, not yet a live-chat measurement. The
            guard is deliberately conservative: even a real City page the model wrote is dropped unless we supplied it.
          </P>

          <Sub>An honest absence beats a wrong number</Sub>
          <P>
            The assessor's commercial valuation keys one record to a whole "economic unit", often several PINs, and its
            building-area total was attributed to whichever member parcel was looked up. On the benchmark a 7-PIN strip center's
            43,790 sq ft landed on a 4,347 sq ft lot — "existing FAR 10.07, at the cap" — and across the 100-address panel,
            Presidential Towers' 745,629 sq ft was shown on a single lot. Area is now attributed only to a single-PIN unit or the
            unit's keypin; other members show no floor area and a note ("recorded for an N-parcel complex"), a plausibility guard
            treats an existing FAR above three times the zone cap as unknown, and a city-footprint fallback is skipped when the
            footprint exceeds the lot. The coverage metric <em>got worse by design</em>: 12 panel parcels moved from a wrongly
            attributed area to an explained absence, which the benchmark now classifies as expected-absent instead of hiding.
          </P>

          {/* ── Feasibility Report (PDF) ── */}
          <SectionHeading id="report">Development Feasibility Report (PDF)</SectionHeading>
          <P>
            The $25 PDF report is the revenue wedge — the moment a professional needs a deliverable for a client,
            lender, or partner. It's priced per-unit (no subscription threshold), it demonstrates every underlying
            system in one artifact, and it markets itself ("Generated by UrbanLayer" travels to whoever receives it).
            <Mono>GET /api/report</Mono> assembles the same retrieval the Property Profile uses, then renders HTML/CSS to PDF
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
            While Stripe keys are not configured (as on production today), <Mono>GET /api/payments/status</Mono> reports that report
            purchases and Pro subscriptions cannot start, and the buy buttons say "purchases coming soon" instead of failing
            silently — sample reports and access-code redemption, which need no Stripe, keep working, and checkout returns
            automatically once keys are present. Retried Stripe webhooks are idempotent, so a redelivery cannot double-count the
            funnel's money step.
          </P>
          <P>
            Purchases are <Accent>PIN-keyed</Accent>: the <Mono>report_purchases</Mono> table (schema v9) records the
            14-digit pin, so entitlement is checked against the exact parcel. The frontend's report functions
            (<Mono>fetchReport</Mono>, <Mono>createReportCheckoutSession</Mono>, <Mono>checkReportAccess</Mono>) all
            take a whole <Mono>SelectedParcel</Mono> and derive the wire params internally — hand-constructing report
            identity is a compile error. Legacy pin-less purchase rows stay entitled permanently via a 4-decimal
            coordinate match. Stripe's success URL is <Mono>?pin=…&amp;report_purchased=1</Mono>, which the Property Profile
            reads to auto-download the report right after payment.
          </P>

          {/* ── Property Discovery ── */}
          <SectionHeading id="discovery">Property Discovery</SectionHeading>
          <P>
            Discovery is the second workflow: "find me parcels worth evaluating." It's a filter/search workbench
            covering the <Accent>full city — all 77 community areas / ~949k parcels</Accent> — where each result flows
            straight into the Evaluate pipeline (click a row → Property Profile → Report). Free users see a top-10 teaser;
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
            WAL mode via <Mono>aiosqlite</Mono>, singleton connection, schema v14. Tables: <Mono>conversations</Mono>,
            <Mono>messages</Mono> (with JSON blob columns for context/plan/mapData), <Mono>uploads</Mono>,
            <Mono>llm_calls</Mono>, <Mono>request_logs</Mono>, <Mono>schema_version</Mono>,
            <Mono>users</Mono>, <Mono>refresh_tokens</Mono>, <Mono>share_tokens</Mono>, <Mono>report_purchases</Mono> (v9),
            and <Mono>events</Mono> (v10, usage analytics); v11 made purchases PIN-bound, v12 added account-deletion
            tombstones, v13 newsletter subscribers, and v14 early-adopter access codes with a time-boxed premium grant. JSON blob columns
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
              ["premium", "100 queries/day, all features", "Manual upgrade or an early-adopter access code"],
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
            estimates (Sonnet $3/$15 per MTok, Haiku 4.5 $1/$5 per MTok, prompt-cache reads at 0.1× input and five-minute cache writes at 1.25×).
          </P>

          {/* ── Security & Hardening ── */}
          <SectionHeading id="security-hardening">Security &amp; Hardening</SectionHeading>
          <P>
            In September 2026 the repository was reviewed the way an outside engineer would read it — code, then the live site,
            then the server — before it was shared. The result was a day of fixes (PRs #24–#30) and a one-time server hardening
            run. The common thread: most of the dangerous defaults were <em>convenient for development and wrong for
            production</em>, and nothing in a green test run would have said so.
          </P>

          <Sub>The rate limit the client could rewrite</Sub>
          <P>
            Anonymous chat limits were keyed on the leftmost <Mono>X-Forwarded-For</Mono> entry — a header the client controls.
            Sending a different value on each request meant unlimited anonymous chat and, with it, a way to exhaust the{" "}
            <em>global</em> daily LLM budget for every user. The trust chain is now explicit: nginx trusts{" "}
            <Mono>CF-Connecting-IP</Mono> only from Cloudflare's published ranges, overwrites <Mono>X-Real-IP</Mono> and{" "}
            <Mono>X-Forwarded-For</Mono> with the real peer instead of appending to what the client sent, and the application
            reads only <Mono>X-Real-IP</Mono>, and only from a private-network peer. IPv6 clients are bucketed per /64 so rotating
            within an allocation doesn't reset the window. Verified against a header-echo backend: forged headers from a
            non-Cloudflare source never reach it.
          </P>

          <Sub>Ids were enough</Sub>
          <P>
            Several endpoints treated knowing an id as authorization. Upload download and delete had no auth at all; the
            conversation-uploads list accepted anonymous callers; the share-token endpoint returned any conversation's token to
            any signed-in user; <Mono>/chat</Mono> loaded turn summaries for whatever conversation id it was handed and attached any
            upload ids to the model prompt, pulling another user's questions and files into the caller's request; and "clear all
            conversations" deleted the entire uploads directory — every user's files. Every path now checks ownership, unauthorized
            ids return 404 so they cannot be probed, and conversation ids are random UUIDs instead of a timestamp plus{" "}
            <Mono>Math.random</Mono>.
          </P>

          <Sub>A production that didn't know it was production</Sub>
          <P>
            Three settings had development defaults that are vulnerabilities in production: no <Mono>GOOGLE_CLIENT_ID</Mono>{" "}
            disables auth (every request becomes an admin), no <Mono>JWT_SECRET</Mono> falls back to a key published in the
            repository, and no <Mono>STRIPE_WEBHOOK_SECRET</Mono> skips signature checks, so a forged event could grant premium.
            With <Mono>ENVIRONMENT=production</Mono> the app now <Accent>refuses to start</Accent> if any of these is missing or
            weak, or if secure cookies are off or the frontend URL isn't https; unsigned webhooks are rejected in production
            regardless. Related: <Mono>/api/report?mock=true</Mono> replaced every section with fixture data for template QA, and
            any user with access to a parcel's report could request it — a PDF of invented numbers presented as that parcel's
            feasibility report. It is now admin-only.
          </P>

          <Sub>Input that reaches something expensive</Sub>
          <P>
            A ~2,000-character address returned a bare 500 (the geocoder's firewall answers with a 200 and an HTML page, and only
            timeouts and status errors were caught); the <Mono>pin</Mono> parameter was interpolated unchecked into a SoQL filter;
            chat history had no length cap, so one request could carry an arbitrarily large forged history into a paid model call;
            and the <Mono>language</Mono> code was interpolated verbatim into the system prompt. Addresses are capped, PINs are
            normalized to digits and length-checked, history is capped per message and in total, and language is normalized to a
            supported code.
          </P>

          <Sub>The CSP that blocked its own scripts</Sub>
          <P>
            The inline pre-paint theme script was blocked on every page (the policy carried no hash), and the session-replay
            analytics hosts were missing, so replay recorded nothing — the content-security policy was quietly breaking the
            site's own features. The policy is now defined once and referenced from both server blocks, with the script's
            hash, <Mono>object-src</Mono>, <Mono>base-uri</Mono> and <Mono>form-action</Mono> added. Default servers drop requests
            for unknown hosts and reject TLS handshakes without the site's SNI, so scans of the bare origin address get nothing.
          </P>

          <Sub>Deploying as root</Sub>
          <P>
            The deploy job logged in as <Mono>root</Mono> with a key that could do anything on the box and did not verify the
            server's host key. Deploys now run as a dedicated <Mono>deploy</Mono> user whose key can run exactly one forced
            command — fast-forward only, fails on a broken build — with the host-key fingerprint pinned, inside a protected{" "}
            <Mono>production</Mono> environment limited to <Mono>main</Mono>. The server side of this was a written, executed
            runbook: an admin user created before root login was disabled, password authentication off, an origin firewall that
            admits web traffic only from Cloudflare, unattended security upgrades, and a nightly database backup. Running it for
            real produced two corrections worth keeping: a <Mono>--system</Mono> user otherwise gets <Mono>/nonexistent</Mono> as
            its home directory, so sshd never finds its key; and the deploy action's SSH client negotiates{" "}
            <em>ECDSA</em> first, so pinning the ed25519 fingerprint fails with "host key mismatch". The runbook also caught a
            wrong claim of our own — the backup script's default path was wrong, so the repository assumed no backups existed, but the
            server's cron entry had passed the right path all along; both the script and the docs were corrected.
          </P>

          <Sub>The vector database that was open to the internet</Sub>
          <P>
            While planning a corpus update, <Mono>docker-compose.yml</Mono> turned out to publish the vector store's port on{" "}
            <Mono>0.0.0.0</Mono>, and Qdrant ships with no authentication: the production index was readable <em>and writable</em>{" "}
            from the public internet with a single <Mono>curl</Mono>. The obvious fix is wrong: adding a loopback mapping in the
            production override would have <em>appended</em> to the list under Compose's merge semantics, leaving the public binding
            alive while looking closed. The fix removes host publishing from the base file (the backend reaches the store over the
            compose network) and republishes on <Mono>127.0.0.1</Mono> only in the development override that production never
            loads. After the change the production collection was checked point-for-point against the local corpus.
          </P>

          <Sub>A code reviewer that never ran</Sub>
          <P>
            The project's AI pull-request review workflow had failed at environment validation on every PR for three months — its
            API key was never configured — leaving a permanently red check that reviewed nothing. It was replaced with what is free
            on a public repository: CodeQL (<Mono>security-extended</Mono>, deliberately not the noisier quality pack), secret
            scanning with push protection, Dependabot alerts and security updates, and grouped monthly version updates. The scope
            change is stated plainly: <em>CodeQL finds security issues, not correctness bugs, so there is currently no general
            automated reviewer.</em>
          </P>
          <P>
            The first CodeQL run produced the most consequential finding: the SSH deploy action was referenced by a{" "}
            <em>mutable tag</em> on the very step that receives the production SSH key. It is now pinned to a commit SHA, and every
            job declares least-privilege permissions. Twenty-three log-injection alerts (user-controlled strings reaching logs)
            were fixed once, centrally, with a filter on the root log <em>handlers</em> that escapes CR/LF — handlers rather than
            loggers because a handler sees library loggers too, and rather than editing 23 call sites because the 24th would
            escape. CodeQL cannot see a runtime filter, so those alerts are dismissed with a written reason; the policy is to keep
            the Security tab at zero open so a real finding stays visible.
          </P>

          <Sub>Dependency triage, and what a green check proves</Sub>
          <P>
            Twelve Dependabot PRs arrived at once. Nine safe ones were batched into a single change, because every merge to{" "}
            <Mono>main</Mono> is a deploy — ten merges would have meant ten container rebuilds and ten brief outage windows —
            taking npm vulnerabilities from 14 to 2. Two were rejected despite passing CI: a Python 3.11→3.14 runtime bump passed
            because the test job installs Python separately and never builds the Dockerfile, and a test-tooling major passed because
            npm only <em>warns</em> on a Node engine mismatch. A green check is evidence of what CI ran, not that a change is safe.
          </P>

          {/* ── 12. Map & Geo ── */}
          <SectionHeading id="map">Map & Geo Visualization</SectionHeading>

          <Sub>Mapbox + deck.gl Over Leaflet</Sub>
          <P>
            WebGL rendering handles thousands of points smoothly in the sidebar's constrained viewport. deck.gl's
            declarative layer API makes filter toggling trivial — just rebuild the layers array. Leaflet with
            SVG overlays would struggle at 2,500 crime points. The chat map follows the app theme (the dark basemap{" "}
            <Mono>dark-v11</Mono> in dark mode); the Property Profile's place map adds a satellite ⇄ streets toggle.
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
            Sixteen client events trace the path from landing to purchase — among them <Mono>visit_start</Mono> (with
            referrer, UTM parameters and a persisted first-touch attribution), <Mono>hero_address_submit</Mono>,{" "}
            <Mono>scorecard_view</Mono>, <Mono>investigate_click</Mono>, <Mono>chat_message_sent</Mono>,{" "}
            <Mono>report_cta_click</Mono>, <Mono>sample_report_click</Mono>, <Mono>checkout_started</Mono> and{" "}
            <Mono>discovery_search</Mono> — plus two money events, <Mono>purchase_completed</Mono> and{" "}
            <Mono>subscription_started</Mono>, that are written <em>only by the Stripe webhook</em> and excluded from the client
            allowlist, so the funnel's money step cannot be spoofed from a browser. Each carries a per-tab <Accent>session ID</Accent> and a cross-session <Accent>visitor ID</Accent>, so the
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
              ["Claude Haiku 4.5", "$1.00 / MTok", "$5.00 / MTok"],
            ]}
          />
          <P>
            The table was wrong until October 2026: Haiku 4.5 had been priced at Haiku 3.5's rates, prompt-cache reads and
            writes were ignored even though every call records them, and an unpriced model silently fell back to Sonnet rates.
            Because this table feeds both the admin dashboard and the daily budget cap, the cap was under-counting. Cache tokens
            are now priced and summed into the budget check, and an unpriced model logs a warning.
          </P>

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

          {/* ── Measuring Correctness ── */}
          <SectionHeading id="correctness">Measuring Correctness</SectionHeading>
          <P>
            Every other suite on this page asks whether the system reproduces its own inputs: did retrieval return the section
            the question names, is the field populated, does the answer cite what it retrieved. None of them asks whether the
            answer is <em>right</em>. So in October 2026 a different kind of test was built, deliberately designed to find where
            a zoning tool is wrong — and its first run was kept on the public record on purpose.
          </P>

          <Sub>The parcel kit</Sub>
          <P>
            Twelve Chicago parcels, each chosen because it breaks a lazy system: a vacant lot whose address geocodes into the
            neighboring district; a parcel inside a landmark district; a Planned Development whose numbers live in an ordinance, not a
            base-district table; one rezoned three months earlier; a downtown DC-16 parcel; an M2-3 manufacturing parcel where
            residential is prohibited; one inside the Lakefront Protection District; and a transit-served B3-3 (the <em>positive</em>
            case) beside a C2-5 where the same transit rules do <em>not</em> add density. The answer for each was read from primary
            sources — the City's zoning layer and map service, the Municipal Code text, ordinance PDFs and Cook County Assessor
            data — with the source recorded per field. Where a key is read from the code, it is read from the ingested text, never
            from the product's output.
          </P>
          <Table
            headers={["Field", "What is scored"]}
            rows={[
              ["A", "Zoning district in effect — a wrong answer is a critical miss, because everything else derives from it"],
              ["B", "The parcel's use question (is a two-flat allowed?)"],
              ["C", "Bulk numbers: FAR, height, minimum lot area per unit"],
              ["D", "Overlays and designations, as a set (missing, false and denied ones all counted)"],
              ["E", "Parking and transit rule (only on the parcels near transit)"],
              ["F", "The parcel's task question (how many units, what approvals, what ADU limits)"],
            ]}
          />
          <P>
            Two surfaces are scored on the same fields: the deterministic Property Profile, and the chat given only an address
            (no PIN, as a first-time user would type it). Each field scores 2 / 1 / 0, or "no claim", and a wrong answer stated
            flatly is flagged <Accent>confident-wrong</Accent> — the failure that matters most for a tool people act on. District,
            numbers and overlays are scored mechanically; use, parking and task answers by expected-phrase rubrics; a person's
            scores can override any field, and the report prints how often the automatic score agreed with the hand score. A call
            that fails is reported as <em>not scored</em>, never as a score. Recorded runs can be re-scored offline
            (<Mono>make kit-replay</Mono>), a replay scores against the key version it was recorded under, and the public page is
            regenerated from the committed results by a script whose output a test checks for staleness.
          </P>

          <Sub>What the first run found</Sub>
          <P>
            The Profile resolved the right district on all seven original parcels but stated a false claim (every transit-served
            parcel gets a density bonus) and never showed the number a unit count turns on. The chat, given only an address,
            located the parcel from a geocoded street point instead of the parcel, which put it in the neighboring district on two
            of seven, invented bulk numbers from memory, and stopped at its token cap mid-answer on most parcels without saying so.
            A recent rezoning could not be stated at all, and a multi-parcel strip center's building area had been attributed to a
            single lot. Each became one small change with a before-and-after run:
          </P>
          <WideTable
            headers={["Run", "Profile accuracy / confident-wrong", "Chat accuracy / confident-wrong", "What changed"]}
            rows={[
              ["Starting point (7 parcels)", "80% / 2", "68% / 7 · wrong district on 2", "First run, recorded as found"],
              ["Chat resolves a typed address to its parcel", "—", "81% / 1 · no wrong districts", "Same Address Points path as the Profile"],
              ["No false transit density bonus", "83% / 0", "87% / 1", "tod_benefits() pinned to the ordinance"],
              ["The binding number", "94% / 0", "90% / 0", "Min lot area per unit + unit yield with arithmetic"],
              ["Freshness stamps", "94% / 0", "97% / 0", "Ordinance date, code vintage, recent-rezoning flag"],
              ["Overlays named with their requirements", "97% / 0", "—", "606 district, ADU zone limits, PD links, landmark approval"],
              ["Key grows to 12 parcels; one key error corrected", "94% / 2", "—", "Downtown, manufacturing, lakefront, transit; see below"],
            ]}
          />
          <P>
            The chat has been scored on 7 of the 12 parcels so far; its latest recorded row is 95% coverage, 96% accuracy and one
            confident-wrong field, with no wrong districts. A generic web-search language model, run once on the first seven
            parcels with no access to this repository, made a claim on about a third of the fields and was right on about half of
            those.
          </P>

          <Sub>The Landmark Layer That Wasn't — A Verification Story</Sub>
          <P>
            Adding a parcel on Lake Shore Drive made the answer key and the product disagree about whether the building was an
            individual Chicago Landmark. Rather than assume either side, the next step was a second primary source. The zoning
            map's layer 7, labelled "Landmark Buildings", turned out to be the <Accent>historic-resources survey</Accent> — 9,298
            orange- and red-rated buildings, 9,108 of them with no designation date — not designations. The real landmarks are
            layer 5 (59 of the 60 official landmarks fall inside it, against 39 for layer 7, cross-checked against the City's
            317-landmark list) and landmark districts are layer 6.
          </P>
          <P>
            Both the product <em>and the original answer key</em> had made the same misreading. On production, owners of roughly
            9,000 orange-rated buildings were being told a permit needs the Commission on Chicago Landmarks' written approval
            (§2-120-740) while the rule that actually applies — a possible 90-day demolition delay (§14A-4-407.6) — was hidden.
            The layer is no longer queried as a landmark source, and the correction is printed on the benchmark page with its
            date. The lesson went into the method: <em>a disagreement between product and key is a signal to check both</em>, and a
            map layer's meaning must be verified against a second source, not just its name. An earlier draft of the key had also
            used the product's own output as ground truth; three such errors were fixed when the key was rebuilt from primary
            sources.
          </P>

          <Sub>Review, limits, and reproduction</Sub>
          <P>
            The key has been generated into a blind review packet — the key, its sources and thirteen judgment questions, with no
            tool output — so a Chicago zoning professional can review the evidence without seeing any tool's answers. Their
            agreement rate and every disagreement will be published whether or not the key changes. Until then, the limits are part
            of the result:
          </P>
          <Table
            headers={["Limit", "Why it matters"]}
            rows={[
              ["Twelve parcels", "They show kinds of failure, not a statistically reliable accuracy rate"],
              ["Key not yet reviewed by a Chicago professional", "The most interpretive parcels are the minimum-lot-area, transit and ADU ones"],
              ["Overlay truth comes from the same City service the product queries", "Overlay scores are not independent evidence; district, numbers and task answers are"],
              ["Rubrics were written looking at earlier runs", "Agreement with a person's scores is in-sample, and each fix is in-sample on the parcel that exposed it"],
              ["Chat varies run to run", "One run per row; compare runs by the cases that fail, not the third digit"],
              ["Chat scored on 7 of 12 parcels", "The newest parcels have Profile results only so far"],
              ["Code text is current through March 18, 2026", "A later amendment is not in the key"],
            ]}
          />
          <P>
            The benchmark page, the answer key with a source for every field, the dated run reports and a blank scorecard for
            scoring another tool are all in the repository (<Mono>docs/benchmark/</Mono>, <Mono>eval/kit/</Mono>); the Profile run
            is free and the chat run costs about a dollar.
          </P>

          {/* ── 17. Eval & Benchmarks ── */}
          <SectionHeading id="eval">Eval & Benchmarks</SectionHeading>

          <Sub>Query Test Suite (44 questions)</Sub>
          <P>
            <Mono>eval/queries.json</Mono> with expected intent, sources, community area, and search terms.
            Router-only eval checks that the LLM produces the right retrieval plan. Full pipeline eval
            runs the complete chat flow, checks for expected terms in the response, and fails a query on any citation warning
            from the server's citation check. Every run records the git SHA, the router and synthesizer models, and a hash of the
            prompt file, so two runs are only compared when they measured the same system. The table below is the May 2026
            run of the original 26-question set; the set has since grown to 44.
          </P>
          <Table
            headers={["Metric", "Value"]}
            rows={[
              ["Total queries (May 2026 set)", "26"],
              ["Pass rate", "22/26 → 26/26 after the router began writing better zoning search queries"],
              ["Total latency p50", "13.6 s"],
              ["Total latency p95", "59 s → 24 s (retrieval p95 54 s → 18 s)"],
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
              ["v5", "26", "2", "0", "0", "0", "Synonym expansion, keyword-aware dedup, 0.20 keyword weight (reranker on)"],
              ["Sep 2026, production config", "24", "4", "0", "0", "0", "Reranker off, 5.8 s for all 28 queries; Title 14 now in the corpus"],
            ]}
          />
          <P>
            v5 reached <Accent>100% A/B</Accent> across the (expanded) 28-query set, and still does in the production
            configuration. The two C-grades that survived v4
            (<Mono>adu_allowed</Mono>, <Mono>lot_coverage_rm5</Mono>) were terminology gaps; synonym expansion at query
            time closed them. Note the benchmark numbers are from the <em>full</em> pipeline including the reranker —
            in production (reranker off) the dense+keyword fallback carries the chat path, and the report path uses the
            precomputed zoning cache rather than retrieval at all.
          </P>

          <Sub>Reranker Ablation, and a Stale Label</Sub>
          <P>
            The decision to leave the reranker off is backed by a table, not intuition. Re-run on 28 questions with the reranker
            on, one question improves by one grade (25 A / 3 B against 24 A / 4 B) at roughly 13× the wall time on a laptop — and
            about 40 seconds per search on the production CPUs, which is what caused the June report timeouts.
          </P>
          <P>
            The same re-run's one "D" turned out to be a <em>stale label, not a regression</em>. The{" "}
            <Mono>demolition_permit</Mono> question's gold sections named adjacent chapters because, as its own note said, the
            building code wasn't indexed when it was written. Once Title 14 was indexed, retrieval ranked §14A-4-407
            ("Demolition", the permit requirements) first. The gold now includes it, and the reason is recorded on the question:
            labels change only with that kind of evidence.
          </P>
          <P>
            The LLM judge got the same scrutiny. Its documented dimension weights (citation 30%, factuality 30%, completeness 20%,
            rules 20%) were only a fallback — whenever the judge returned its own holistic grade, that won — and a reply wrapped
            in a markdown fence failed to parse and scored every dimension F. The overall grade is now always the weighted blend,
            fences are stripped, and the judge's source list gained the two data sources it was missing (which had made citing them
            look fabricated). Still true, and stated in the repository: the judge is reference-free (Sonnet grades Sonnet) and
            uncalibrated against human grades.
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

          <Sub>Lot-Info Coverage Benchmark (100-address frozen panel)</Sub>
          <P>
            <Mono>eval/lot_coverage.py</Mono> measures field-level completeness of the lot facts customers pay for,
            across a committed panel of 100 representative addresses (see the Lot Facts &amp; Provenance section for
            the full story). Every field classifies as present / missing / expected-absent, and a sequential verify
            pass splits persistent data gaps from transient retrieval failures — yielding both a first-hit and a
            best-case coverage number per field.
          </P>
          <Table
            headers={["Critical field", "Before (2026-07-02)", "After (2026-07-03)"]}
            rows={[
              ["Tax bill / rate (production)", "0% since launch", "100%"],
              ["Land sqft", "21%", "100%"],
              ["Building sqft", "20%", "85%"],
              ["Zoning FAR", "83%", "98.9%"],
              ["Zoning class (first hit)", "96%", "100%"],
              ["Year built / stories", "20% / 1%", "47% / 46%"],
            ]}
          />

          <P>
            The most recent run (September 2026, 0 fetch errors): the county's PIN matched on 97% (the 3 misses are adjacent
            addresses the county data doesn't match confidently — the profile marks them unconfirmed instead of guessing), land
            area, class, zoning, assessment history and tax bill at 100%, zoning FAR 98.9%, year built 88%, stories 69% and units
            31% (secondary fields with no reliable non-residential source). Building area reads as 76 present, 12 explained
            absences and 12 tax-exempt misses: the 12 explained ones are members of multi-PIN commercial units whose assessor total
            had been attributed to a single lot, and are now withheld on purpose.
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
            GitHub Actions has four gates. A <Accent>test</Accent> job runs the backend suite (about 1,440 unit tests; 61
            real-API integration tests are excluded), the eval-scorer tests, the frontend vitest suite (257 tests) and the full
            TypeScript build. A <Accent>lint</Accent> job runs ruff and ESLint. A <Accent>CodeQL</Accent> scan runs on pull
            requests, pushes and weekly. A <Accent>changes</Accent> job decides whether a push needs a deploy at all: a push
            touching only docs runs the tests but skips the container restart (proven live when a docs-only push reported{" "}
            <Mono>deploy: skipped</Mono>), and it fails safe — a mixed docs-and-code push deploys. On success, the deploy job
            reaches the server as a least-privilege <Mono>deploy</Mono> user with a pinned host key and runs a fast-forward-only
            script, so a push to <Mono>main</Mono> is a deploy. <Mono>main</Mono> requires the test and lint checks and blocks
            force-pushes and deletion.
          </P>
          <P>
            Because merge is deploy, merges are serialized: merging three PRs back-to-back once started three concurrent deploys
            that collided at container recreation ("name already in use") and took the site to a Cloudflare 521 until a failed run
            was re-run alone. The rule since: merge one, wait for its deploy to finish, then merge the next.
          </P>

          <Sub>Gates That Weren't Gating — A Testing Story</Sub>
          <P>
            The pre-review audit found that several guards existed on paper and ran nowhere:
          </P>
          <Table
            headers={["Finding", "Fix"]}
            rows={[
              ["171 frontend tests existed; no workflow ran them", "vitest runs in CI and gates the deploy"],
              ["ESLint reported 76 problems and nothing ran it — including a real crash: charts returned early before some hooks, so a chart that mounted empty and then got data threw \"rendered more hooks than during the previous render\"", "Hooks fixed; ESLint and ruff gate the deploy; the warning count can only go down"],
              ["requirements.txt lacked stripe, weasyprint and sentry — a clean clone had 4 failures and 8 collection errors; CI passed only because it installed a different file", "One requirements chain; a clean clone now installs and runs from the README"],
              ["All 14 zoning-parity checks skipped in CI because the section JSONs were gitignored build output — the test that blocks fabricated zoning numbers ran only on one laptop", "The 74 KB of ordinance sections it reads are committed; it runs everywhere"],
              ["Unit tests silently touched the network: retrieval degrades gracefully by design, so a test that forgot a mock still passed while making real calls with retries", "An autouse guard fails any non-integration test that opens a socket or resolves DNS; it found exactly five"],
              ["The eval scorers themselves were untested — a scorer bug silently changes every reported number", "88 scorer tests run in CI: plan checks, the retrieval A–F rules, coverage statuses, lot-field classification against a recorded response, judge parsing"],
            ]}
          />
          <P>
            The same sweep gave the repo a <Mono>Makefile</Mono> (<Mono>setup</Mono>, <Mono>test</Mono>, <Mono>lint</Mono>,{" "}
            <Mono>check</Mono>, <Mono>dev</Mono>), pinned tool versions, an <Mono>.env.example</Mono> listing every setting the code
            reads (one inline comment had been parsed as the WalkScore API key), and a committed Title 16–17 sample so a fresh
            clone's chat can cite real sections after a 30-second seed.
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
              ["Chat failed for any parcel with a new crime/311 category", "A month-over-month change of None was compared to 0 in the prompt formatter, so synthesis raised; the same pass found raw exception text streamed to the browser", "Rendered as \"new this month\"; users get a generic retry message while detail stays in the log"],
              ["Empty Discovery page on a cold visit", "The CSRF cookie is issued by the first /auth/me call; a POST could go out before it returned (2 of 3 cold loads)", "authFetch waits for one shared bootstrap before any state-changing request"],
              ["Anonymous visits logged 401 errors", "The refresh cookie is httpOnly, so only the server can know whether one exists", "/auth/me reports can_refresh; the client refreshes only when it can"],
              ["Rate limit bypass, id-only authorization, fail-open config, root deploys, open vector store, mutable action tag", "See Security & Hardening", "Fixed in September 2026"],
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
            <Mono>/scorecard</Mono> (parcel Property Profile, non-AI), <Mono>/discovery</Mono> (Property Discovery
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
            As the surface area grew (Property Profile, Report, Discovery, chat, landing), arbitrary <Mono>text-[Npx]</Mono>{" "}
            sizes, ad-hoc <Mono>white/opacity</Mono> chrome, and off-palette hues had crept in. A unification pass
            replaced them with a small, role-based token system, and a later redesign ("Bento Pro") replaced its look while
            keeping its mechanics. The goal: decisions are made by <em>picking a token</em>, not inventing a value.
          </P>
          <Sub>Theming</Sub>
          <P>
            Every color is a CSS variable behind a stable Tailwind class name (<Mono>bg-dark-surface</Mono>,{" "}
            <Mono>text-text-primary</Mono>), so flipping between light, dark and system is a swap of the variables, not of the
            markup. A pre-paint script prevents a flash of the wrong theme (and the content-security policy carries its hash). An
            always-dark island, like the hero, mode-locks its subtree with a data attribute; content sections must flip.
          </P>
          <Sub>Palette: orange does the work, violet costs money</Sub>
          <P>
            A near-black canvas in dark mode and a warm near-white in light, separated by hairline borders rather than shadows.
            One brand accent, orange <Mono>#F9A474</Mono>, is the only chrome color in both modes; violet is reserved for anything
            that costs money (the report CTA, premium). Hue is otherwise reserved for genuine state (good, caution, bad) and for
            functional data encodings — map colors, the Discovery upside ramp, data pills — where color carries meaning rather
            than decoration. The chart rule is just as strict: series 1 is brand orange and series 2 a neutral gray, never
            blue — a validated-but-off-brand blue read as clip-art.
          </P>
          <Sub>Type scale</Sub>
          <P>
            Ten named steps replace every arbitrary pixel size — <Mono>text-display / stat / section / subtitle /
            lead / title / body / caption / micro / overline</Mono>. Each bakes in size, line-height, and weight, so
            you pick the step rather than overriding weight per use. Three scoped families: <Accent>Inter</Accent> for body and UI,{" "}
            <Accent>Inter Tight</Accent> for display headings only, and <Accent>JetBrains Mono</Accent> for PINs, code and data.
          </P>
          <Sub>Radius by role, and primitives</Sub>
          <P>
            Radius encodes role rather than taste: cards, panels and modals use the large bento radii (28px / 20px),
            controls and inputs <Mono>rounded-lg</Mono>, chips and badges <Mono>rounded-md</Mono>. Three shared primitives in{" "}
            <Mono>src/components/ui/</Mono> — <Mono>Card</Mono>, <Mono>Chip</Mono>, <Mono>Modal</Mono> — replace hand-rolled
            chrome, and the action hierarchy is fixed: one filled primary per row, outlined secondary, link-style tertiary, and a
            violet premium button.
          </P>

          {/* ── 20. Testing ── */}
          <SectionHeading id="testing">Testing</SectionHeading>
          <P>
            ~1,500 backend tests (about 1,440 unit + 61 real-API integration), plus 88 tests of the eval scorers themselves.
            The everyday baseline is <Mono>pytest -m "not integration"</Mono> — the integration tests hit live external APIs
            and fail on network/GIS flakiness, not code, and an autouse guard fails any unit test that touches the network.
            The frontend adds a <Mono>vitest</Mono> suite (257 tests across 32 files — Discovery compiler/selectors, landing,
            nav-string budgets, i18n parity, the hero's crop geometry), a Playwright overflow audit across five phone profiles,
            and a <Mono>npm run build</Mono> (<Mono>tsc -b</Mono> plus Vite) that is the real deploy gate. The zoning-parity
            test diffs every hand-typed zoning standard against the ordinance tables parsed from the Municipal Code; the
            ordinance-pinned tests behind the Verifiable Answers section (transit benefits, coverage notes, provenance code
            sections) fail CI if a claim drifts from the code text.
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
              ["Hetzner (CX22, now CX32)", "AWS EC2, DigitalOcean, Railway", "Started at 4GB RAM for €4.50/mo — 5-10x cheaper than US cloud for equivalent specs; bumped to 8GB when the discovery index and PDF rendering landed", "Higher latency for US users (~100ms); no managed scaling"],
              ["Cloudflare Origin Cert", "Let's Encrypt + certbot", "15-year validity, zero renewal automation, no cron jobs, no renewal failures", "Locked into Cloudflare proxying; cert only valid behind Cloudflare"],
              ["Concurrency semaphore", "Unbounded parallelism, queue", "Prevents OOM from 10+ concurrent retrieval tasks on 4GB RAM; simple asyncio primitive", "Limits throughput; sequential bottleneck under high concurrency"],
              ["ML preload at startup", "Lazy-load on first request", "First user doesn't wait 8s for model download; OOM caught at deploy time, not at runtime", "Slower container startup (~30s); startup fails if model missing"],
              ["CPU-only PyTorch", "Full PyTorch with CUDA", "Production server is x86 CPU; avoids shipping ~2GB of unused CUDA libraries", "No GPU acceleration; inference is slower (acceptable for query volume)"],
              ["Conversation sharing via token", "Snapshot duplication, public URLs", "No data duplication; CASCADE delete auto-revokes; owner retains control", "Share breaks if conversation is deleted; no offline/archived shares"],
              ["Property Profile as free zero-LLM hook", "Gate everything behind chat/auth", "Fast, zero-cost facts earn trust before asking for an account or payment; pushes users to Property Profile first, chat second", "Some users never reach the paid report"],
              ["$25 per-unit report wedge", "Subscription-only", "A $25 per-parcel decision is a far lower bar than $99/mo; a tangible PDF that markets itself", "Lower ARPU than pure subscription; per-report compute cost"],
              ["Precomputed zoning cache", "On-demand reranked AI extraction", "Reranker too slow on prod vCPUs; deterministic full-section fetch + hybrid merge is faster AND more accurate (57/59 high-confidence)", "Cache must be rebuilt when Title 17 changes; setbacks uncross-validated"],
              ["SelectedParcel single write site", "Resolve the parcel ad hoc per surface", "Guarantees the pin shown is the pin queried, purchased, and reported on", "More plumbing; every handoff must thread identity"],
              ["Address→PIN via Address Points", "Census geocode + nearest centroid", "Authoritative resolution to the exact parcel — typed addresses were ~77% wrong while GIS is down", "One more Socrata dataset; coverage gaps degrade to 'approximate'"],
              ["Stripe hosted Checkout", "Self-hosted card form", "No PCI surface; one integration covers both one-time and subscription", "Redirect flow; Stripe lock-in"],
              ["Off-box, memory-bounded index build", "Build on the live serving process", "Full-city index build (~3GB) doesn't compete with the server for RAM; bounded by per-CA ingest + streaming finalize", "Extra deploy step; index is stale between monthly rebuilds"],
              ["Subprocess PDF render", "Render in the request process", "Isolates WeasyPrint memory — an OOM kills the child, not the worker", "IPC + temp-file handoff overhead"],
              ["Role-based design tokens", "Ad-hoc Tailwind classes", "Picking a type/neutral/radius token prevents drift across a growing surface area", "One-time migration cost"],
              ["Benchmark key from primary sources, failures published", "A benchmark scored against the product's own output; publishing only the passing runs", "A key read from the ordinance, with the failing first run kept, is the only way a score can mean something; each fix then ships with a before/after row", "Twelve parcels show kinds of failure, not a rate; the key still needs outside review"],
              ["One deterministic helper per claim, pinned to the code text", "A prompt rule; trusting the model's memory of the ordinance", "The Profile, a cold chat turn and the handoff all read the same answer, and a wrong claim fails CI", "Each claim needs a helper and a test; coverage grows one claim at a time"],
              ["The model never writes URLs", "Trusting citations; post-hoc link checking", "A streaming guard drops any link we didn't supply and a footer is built from provenance, so a reader can't land on a page that doesn't say what the answer claims", "Conservative: a real City page the model wrote is dropped unless we supplied it"],
              ["Say where the analysis stops", "Presenting the page as a determination", "A screening page that never states its edges reads as an official answer; the City's Zoning Verification Letter is named as the confirmation", "More text on the zoning card; notes must be kept pinned to the code"],
              ["Fail-closed production config", "Convenient dev defaults in every environment", "Missing auth, a published JWT key or unsigned webhooks are vulnerabilities, not conveniences", "The app refuses to start until production settings are right"],
              ["CodeQL + Dependabot, not an LLM reviewer", "A model reviewing every PR", "The model reviewer never ran (no key) and a permanently red check is worse than none; the free native tools are real and gate nothing falsely", "Security only — no general correctness reviewer"],
              ["Truncation notice before a higher token cap", "Raising the output limit", "Shorter answers plus a visible cut-off notice fixed the silent failure without raising per-answer cost", "Two of seven benchmark answers still reach the cap (and say so)"],
              ["Explained absence over a fuller-looking metric", "Attributing a multi-parcel complex's area to one lot", "A wrong 745,629 sq ft on a single lot is worse than an honest blank with a note; the coverage number dropped on purpose", "Lower headline coverage"],
              ["Batch dependency PRs", "Merging each Dependabot PR", "Every merge to main is a deploy; ten merges is ten rebuilds and ten outage windows", "One larger change to review"],
            ]}
          />

          {/* ── 22. At Scale ── */}
          <SectionHeading id="scale">At Scale</SectionHeading>
          <P>
            Current architecture optimized for single-user deployment on a single 8GB VPS. Here's what changes at 1,000x users:
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
              ~1,500 backend tests, 257 frontend tests. 16,576 code chunks indexed. ~949k parcels in the discovery index.
              25+ live datasets. 4 domain orchestrators. Property Profile + cited chat + $25 PDF report + discovery,
              scored on a 12-parcel public benchmark.
              Built with FastAPI, Claude, Qdrant, React, Mapbox, deck.gl, WeasyPrint, and Stripe.
              Live at urbanlayerchicago.com.
            </p>
          </div>
        </article>
      </div>
    </div>
  );
}
