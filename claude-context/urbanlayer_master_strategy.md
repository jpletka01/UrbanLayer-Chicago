# UrbanLayer — Master Strategy & Exploration Prompt

> **Purpose:** This document captures the full strategic context for UrbanLayer, a RAG-powered urban intelligence platform for Chicago. It is intended to serve as a briefing document for any future conversation about product direction, feature prioritization, monetization, or design. The companion deep research report on Chicago Cityscape (the primary competitor) should be included alongside this document.

> **Geographic Scope:** All analysis and recommendations are scoped to the City of Chicago and Cook County, IL. Multi-city expansion is explicitly out of scope for now.

---

## 1. Competitive Landscape: Chicago Cityscape

### 1.1 What They Are
Chicago Cityscape is a private LLC founded in 2014 by urbanist Steven Vance. It is a data aggregation platform (not AI-powered) that consolidates municipal, county, and state public records into a single searchable interface for real estate and construction professionals.

### 1.2 Market Validation (Key Numbers)
- **22,580+ registered users** (growing at ~60 signups/week)
- **Pricing:** $50/mo (Permit Tracker), $85/mo (Lead Finder), $125/mo (Real Estate Pro), ~$1,375/yr annual
- **One-off reports:** $55 per Property Report, $150–$350 per Place Report
- **Custom zoning assessments:** $1,000+ per report
- **Team size:** 2–10 employees, estimated <$5M ARR
- **Geography:** Cook County (1.8M properties), recently expanded to Lake County IL (~300K) and Lake County IN (~300K)

### 1.3 Their Three Subscription Tiers

| Tier | Price | Target | Core Value |
|------|-------|--------|------------|
| **Permit Tracker** | $50/mo | Subcontractors | Search all building permits and violations, extract contractor profiles |
| **Lead Finder** | $85/mo | Construction service providers | Permit Tracker + Proposed Projects detection + owner/developer contact info |
| **Real Estate Pro** | $125/mo | Developers, brokers, architects | Everything + 1.8M property database, incentives, cannabis sites, government land, comparison/appraisal tools |

### 1.4 Features Cityscape Has That UrbanLayer Lacks

| Feature | What It Does | Difficulty to Build | Revenue Impact |
|---------|-------------|---------------------|----------------|
| **Property Finder (Prospecting)** | Bulk filter parcels by zoning, transit proximity, vacancy, land use | High | Very High — this is their flagship paid feature |
| **People & Company Portfolios** | Index 200K+ developers/contractors/architects by permit history, rank by volume | Medium | High — subcontractors pay for this |
| **Automated Comps** | Filter nearby sales by distance, property class, price range for valuation | Medium | High — brokers and lenders need this daily |
| **Pending Zoning Changes** | Track active zoning change applications, variances, special uses through City Council | Medium (requires PDF parsing) | High — attorneys and developers pay premium for early intel |
| **Custom Polygon Reports** | Draw a boundary on the map, auto-generate a PDF summarizing everything inside it | Medium | Medium — Place Reports sell for $150–$350 each |
| **Demolition Alerts** | Daily email notifications of demolition permits | Low | Medium — retention feature |
| **Property Tracker** | Alerts when violations, permits, or license changes hit your watched properties | Low | Medium — portfolio management for landlords |
| **Data Export (CSV/GIS)** | Download any dataset as Excel or GeoJSON | Low | Medium — expected by enterprise users |
| **ADU Portal** | Dedicated tool checking ADU eligibility, financing, and code requirements | Low | Low-Medium — niche but growing demand |
| **Cannabis Site Selection** | Filter for dispensary-eligible locations with buffer zone compliance | Low | Low-Medium — niche |
| **Weekly Picks Newsletter** | Algorithmically scored "top 10 developable properties" email every Monday | Low | Low — lead magnet for signups |

### 1.5 Data Cityscape Has That Is Hard to Get for Free

| Data Type | Why It's Hard | How They Get It | Can UrbanLayer Replicate? |
|-----------|--------------|-----------------|--------------------------|
| **Property owner / taxpayer names** | Cook County Assessor and Treasurer websites are CAPTCHA-protected, bulk scraping blocked | Lease bulk deed transfers from Cook County Clerk or commercial brokers (CoreLogic, Regrid) | Not for free. Would need a paid data license ($$$) or per-lookup scraping (fragile) |
| **Pending zoning change applications** | Published as scanned PDFs on City Clerk's Legistar portal, no structured dataset | Proprietary PDF parsers + manual data entry | Possible with LLM-based PDF extraction, but labor-intensive to maintain |
| **Illinois SOS corporate registrations** | No free bulk API, charges per search, scraping prohibited | Integrate corporate registration datasets to map LLCs to real owners | Not practically replicable without a paid data source |
| **Contractor contact info (phone/address)** | Removed from bulk Socrata dataset in 2019 for privacy | Likely scraped from individual permit application pages on chicago.gov/permit, or from business license records | Partially replicable via Business Licenses dataset or individual permit page lookups |

### 1.6 Cityscape's Structural Weaknesses (Exploitable)

1. **No AI / Natural Language Interface** — Users must learn dozens of filters and navigate dense tabular UI. They offer mandatory 30-minute onboarding sessions because the tool is hard to learn.
2. **No Municipal Code Search** — They link to external code sites but cannot answer legal/zoning interpretation questions like "Can I build a coach house in RT-4?"
3. **No Tax Projection** — They display historical tax bills but cannot simulate future taxes (UrbanLayer has PTAXSIM).
4. **Legacy Web Architecture** — Built incrementally since 2014; feels dated compared to modern SPA + WebGL map interfaces.
5. **No Free Tier** — No way to try before you buy. A generous free tier with conversion pressure is a proven SaaS growth strategy they are not using.

---

## 2. UrbanLayer's Current Technical Assets

### 2.1 What's Already Built and Deployed
UrbanLayer is live at `https://urbanlayerchicago.com` on a Hetzner CX32 (8GB RAM) with full CI/CD pipeline, Sentry monitoring, UptimeRobot, and Google OAuth.

| Capability | Implementation | Status |
|-----------|---------------|--------|
| **RAG over Chicago Municipal Code** | 14,535 vector chunks from 8,615 sections in Qdrant, table-aware chunking with composite headers | Production |
| **LLM Router + Synthesizer** | Claude Sonnet 4.6 for routing and synthesis, Claude Haiku 4.5 for conversation synthesis | Production |
| **Parallel Multi-Source Retrieval** | asyncio.gather across Socrata, ArcGIS, Census, FEMA, EPA, HUD, Walk Score | Production |
| **Property Domain** | Cook County parcels (GIS + Socrata fallback), characteristics, assessments, sales, PTAXSIM tax estimation | Production |
| **Regulatory Domain** | 14 ArcGIS zoning overlay layers, FEMA flood, EPA brownfields, ARO housing | Production |
| **Incentives Domain** | TIF boundaries + financials, Enterprise Zones, Opportunity Zones, SBIF/NOF grants, tax incentive class interpretation | Production |
| **Neighborhood Domain** | Demographics (ACS), Census Reporter tract-level data, transit proximity (CTA/Metra GTFS), Walk Score | Production |
| **Crime / 311 / Permits / Violations / Business Licenses / Vacant Buildings / Food Inspections** | All Socrata APIs with caching, aggregation, and map data | Production |
| **Interactive Map** | Mapbox GL JS + deck.gl with overlay/incentive polygon rendering | Production |
| **Conversation Persistence** | SQLite (WAL mode, schema v6), per-user scoping, shareable links | Production |
| **SSE Streaming** | Full pipeline streaming (plan → context → tokens → done) with phase timing | Production |
| **Cross-encoder Reranking** | bge-reranker-v2-m3 at 20% blend weight with dense search | Production |
| **Auth + Rate Limiting** | Google OAuth2, JWT cookies, tiered rate limits (anon 3/day, free 25/day, admin unlimited) | Production |
| **Admin Dashboard** | Custom SVG charts, LLM usage tracking, request logs | Production |
| **Mobile UX** | Adjustable snap-height bottom sheet, 3-tab layout (Map/Data/Sources) | Production |
| **Eval Suite** | 39 router queries + 29-query source coverage benchmark (93% coverage) | Production |

### 2.2 What's Designed but Not Yet Built

| Feature | Design Status | Reference |
|---------|--------------|-----------|
| PDF Zoning Report v2 (premium development feasibility) | Fully specified — 5 vector searches, Haiku extraction, 4 new data sources, 8-section layout | `claude-context/expansion-roadmap.md` §8 |
| Multi-language support (Spanish priority) | Fully specified 7-phase implementation plan | `language-plan.md` |
| Latency reduction (4 remaining items) | Planned | `claude-context/latency-reduction.md` |
| Advanced context management | Designed, not implemented | `claude-context/known-issues.md` |

---

## 3. Value Proposition & Revenue-Generating Features

### 3.1 UrbanLayer's Unfair Advantages Over Cityscape

| Advantage | Why It Matters |
|-----------|---------------|
| **Natural Language Legal Research** | Users ask plain-English zoning questions and get cited answers from the Municipal Code. Cityscape cannot do this at all. |
| **PTAXSIM Tax Simulation** | UrbanLayer can project future property taxes, not just show historical bills. This is a killer feature for acquisition underwriting. |
| **Modern UX** | Single-screen split layout with Mapbox GL + deck.gl vs. Cityscape's dense, decade-old tabular portal. |
| **AI-Powered Synthesis** | Instead of showing raw data tables, UrbanLayer interprets and explains what the data means for the user's specific question. |
| **Free Tier as Growth Engine** | Cityscape has no free tier. A generous free tier with conversion pressure is UrbanLayer's primary user acquisition strategy. |

### 3.2 Features Ranked by Revenue Potential

#### Tier 1: Direct Revenue Drivers

1. **Site Exploration / Property Finder** — Bulk parcel filtering by zoning, transit, vacancy, overlays. Gate entirely behind paid tier. This is the single highest-value feature to build.
2. **Premium Zoning Reports (PDF)** — Auto-generated due diligence reports combining all orchestrator outputs. Charge $100–$200/report or bundle into subscription. Undercuts Cityscape's $1,000 custom reports by 80%.
3. **Zoning & Municipal Code Update Alerts** — Daily/weekly cron diffing the municipal code HTML. Paid users "watch" chapters or geographic areas. Email alerts on changes.
4. **Contractor Intelligence / Lead Gen** — Parse `contact_X_type` fields from permits dataset to identify projects missing specific trade contractors (electrical, plumbing, etc.). Subcontractors pay for these leads.

#### Tier 2: Retention & Efficiency

5. **Non-AI Power User Dashboard ("Scorecard")** — Structured, instant-load property cards that bypass the LLM entirely. Zero API cost, sub-second response. Addresses power users who find chat too slow.
6. **Spanish Language Support** — Backend stays English; LLM synthesizes in Spanish. Already fully designed in `language-plan.md`. Captures underserved South/West Side broker and contractor market.
7. **Property Tracker Alerts** — Watch specific addresses for new violations, permits, or assessment changes. Email notifications. Basic retention feature.

#### Tier 3: Hygiene & Infrastructure

8. **Payment System** — Stripe integration with tiered subscriptions.
9. **Support System** — In-conversation problem reporting with context auto-attached.
10. **User Analytics** — Track intent types, tools used, pages visited (not raw questions for privacy). Critical for product development decisions.
11. **Light Mode** — Standard UX expectation. Keep free.

### 3.3 Recommended Pricing Model

| Tier | Price | Includes | Conversion Strategy |
|------|-------|---------|---------------------|
| **Free** | $0 | 3 single-address lookups/day, basic chat, map view, 2 conversations/day | Hook users, demonstrate value |
| **Pro** | $99/mo ($1,089/yr) | Unlimited chat, municipal code RAG, PTAXSIM tax projections, basic PDF reports, 311/crime/permit analytics, Spanish language | Undercut Cityscape's $125/mo while offering AI features they lack |
| **Enterprise** | $249/mo ($2,749/yr) | Everything in Pro + Site Exploration (bulk filtering), zoning alert monitoring, contractor lead gen, CSV/GIS data exports, team seats | Capture power users and small firms |

---

## 4. Data Source Monetization Strategy

### 4.1 Building Permits — From Map Dots to Lead Gen
- **Current state:** Grouped by permit type with cost totals and work descriptions on a map.
- **High-value transformation:**
  - Parse `contact_1_type` through `contact_15_type` to identify which trade roles (electrical, plumbing, masonry) are missing from active permits.
  - Create a "Leads" data grid where subcontractors filter for permits missing their trade specialty.
  - Track demolition-to-new-construction ratios by neighborhood as a gentrification/investment signal.
  - Export contractor lead lists to CSV for CRM import.

### 4.2 311 Requests — From Noise to Property Red Flags
- **Current state:** Grouped by department with top types.
- **High-value transformation:**
  - For address-specific searches, query 311 complaints at that exact parcel over the last 12 months.
  - Flag high-risk complaint types: "No Heat", "Water Quality", "Rodent Baiting", "Building Collapse Risk."
  - Position as a **pre-acquisition property health audit**: "This building has 12 open tenant complaints for rodent infestation and no heat. This indicates imminent code violations and tenant friction."

### 4.3 Crime Data — From Scatter Maps to Risk Scoring
- **Current state:** 2-month MoM trends on a map. Too short a timescale; seasonal noise makes it misleading.
- **High-value transformation:**
  - Switch to **Year-over-Year same-month comparison** to eliminate seasonal bias (e.g., June 2026 vs June 2025).
  - Calculate a localized **Crime Density Index** for business-relevant categories (Robbery, Burglary, Assault) within a 3-block radius.
  - Position for commercial tenants: "This location has a burglary rate 1.8x the neighborhood average, which will likely increase your commercial insurance premiums."

---

## 5. Future Design Guidelines

### 5.1 The Hybrid Model: Dashboard + Chat as One System
The chat and the structured dashboard must not feel like two separate features (the "conjoined twins" problem). They must behave as a single coordinated system.

#### Dashboard → Chat ("Investigate" Buttons)
- Every data card, map point, and grid row should have a chat icon that pre-populates a contextual question.
- Example: User sees a zoning label `RT-4` on a property card. Clicking it opens the chat with: "What are the setbacks, height limits, and allowed uses for RT-4?"
- Example: User sees a contractor name on a permit row. Clicking "Investigate" opens: "What is [Contractor Name]'s permit history and violation rate in Chicago?"

#### Chat → Dashboard ("Visual Commands")
- When the user asks a location-based question, the chat response should drive the map (zoom, draw boundaries, highlight points).
- When the user asks a comparison question, the frontend should split-screen two property cards side-by-side.
- The SSE stream already sends map payloads alongside text tokens — extend this pattern to drive dashboard state.

#### Division of Labor
- **Dashboard & Map (The "What" and "Where"):** Fast, deterministic, structured facts. No LLM latency. No hallucination risk. Zero API cost.
- **Chat Copilot (The "Why" and "How"):** Legal interpretation, regulatory exceptions, cross-source synthesis, plain-English explanations of complex zoning rules.

### 5.2 When to Use Chat vs. When to Use Tools

| Use Case | Best Interface | Rationale |
|----------|---------------|-----------|
| Bulk prospecting / lead gen | Data grid with filters | Speed, export, deterministic results |
| Single-address due diligence | Structured dashboard (scorecard) | Instant load, no LLM cost |
| Zoning interpretation / legal questions | Chat (RAG over Municipal Code) | Requires reasoning over legal text |
| "Explain this data" follow-ups | Chat with dashboard context hand-off | AI excels at synthesis and explanation |
| Comparing two properties | Chat driving split-screen dashboard | Needs both structured data and narrative |
| Contractor background check | Chat with permit database queries | Requires cross-referencing multiple datasets |
| Monitoring / alerts | Automated email notifications | Async, no user interaction needed |

### 5.3 UX Principles for UrbanLayer

1. **Speed over spectacle.** Power users will choose a 200ms database query over a 5-second LLM response every time for routine lookups. Reserve the LLM for tasks that genuinely require reasoning.
2. **Every data point should be actionable.** If a data card shows a zoning class, it should link to an explanation. If a permit row shows a contractor, it should link to their profile. Dead-end data is wasted screen space.
3. **Export everything.** Enterprise users expect CSV/PDF export on every data view. This is table stakes for B2B SaaS.
4. **The chat should feel like a colleague, not a chatbot.** It should reference the data the user is already looking at, not ask them to re-explain their context.
5. **Disclaimers are non-negotiable.** Every AI-generated zoning interpretation must carry a disclaimer that it is not legal advice. Every data point must cite its source and freshness date. In commercial real estate, a wrong answer can cost millions.

---

## 6. Additional Context for Future Conversations

### 6.1 Known Technical Constraints
- Cook County GIS parcel lookup is intermittently broken (spatial index issue). Socrata Parcel Universe is the automatic fallback but lacks polygon geometry.
- CCAO assessment API returns 400 errors for some PINs. Graceful degradation is in place but the LLM occasionally hallucinates values when data is null.
- PTAXSIM database is 8.8GB and optional. Tax estimation is skipped if the DB is not present.
- The municipal code HTML source (`chicago-il-codes.html`, ~100MB) is not in version control. Anyone deploying needs to obtain it from American Legal Publishing.
- Reranker + embedding models consume ~2GB RAM. Server is currently 8GB (CX32). Heavy queries with 10+ parallel retrievals can stress memory.

### 6.2 Data Freshness & Limitations
- Crime data has a 7-day reporting lag.
- Census ACS 5-year estimates have a ~2-year lag (2023 data = 2019–2023 period).
- Cook County assessments are triennial by township; recent years may show $0 or stale values.
- Vacant buildings dataset (`kc9i-wq85`) is sparsely updated (only 8 records in 2025).
- FEMA NFHL MapServer is intermittently flaky (occasional 500s).

### 6.3 The Competitive Positioning Statement
UrbanLayer is not a "ChatGPT wrapper for city data." It is an **AI-powered urban intelligence platform** that combines the structured data aggregation of Chicago Cityscape with the legal reasoning capabilities of a junior zoning paralegal. The chat interface is not a gimmick—it is the tool that translates dense municipal code tables and regulatory overlays into plain-English, cited answers that save real estate professionals hours of manual research per property lookup.

### 6.4 Target Customer Personas (Priority Order)

1. **Zoning & Land Use Attorneys** — Highest willingness to pay. They bill $300–$600/hr and currently spend hours manually searching the municipal code. UrbanLayer's RAG over Title 17 is a direct time-saver. Marketing angle: *"WestLaw for Chicago zoning."*
2. **Commercial Real Estate Developers** — Need site due diligence (zoning, tax, incentives, environmental) consolidated in one place. Currently use Cityscape + multiple county websites. Marketing angle: *"Your entire due diligence checklist in one search."*
3. **Subcontractors & Construction Service Providers** — Want permit-based lead generation. Will pay $50–$85/mo for filtered lists of active projects missing their trade specialty. Marketing angle: *"Find projects that need you before your competitors do."*
4. **Commercial Brokers & Lenders** — Need comps, tax history, and violation audits for underwriting. Marketing angle: *"Collateral due diligence in 30 seconds."*
5. **Community Organizations & Nonprofits** — Lower willingness to pay individually, but potential for grant-funded institutional licenses. Marketing angle: *"Equitable development data for every neighborhood."*

### 6.5 Open Strategic Questions for Future Discussion

1. **Build vs. Buy for property ownership data?** Licensing bulk deed data from the Cook County Clerk or a broker like Regrid would unlock a major feature gap vs. Cityscape but adds recurring cost.
2. **PDF parsing for pending zoning changes?** The City Clerk's Legistar portal publishes zoning change applications as PDFs. LLM-based extraction could automate this, but maintaining accuracy is labor-intensive.
3. **When to expand beyond Chicago?** The entire pipeline (GIS layers, Socrata datasets, municipal code, county tax system) is Chicago/Cook County-specific. Replication to another city is essentially a rebuild. When does the market justify this investment?
4. **Freemium conversion rate assumptions?** At 3 free lookups/day, what conversion rate to Pro ($99/mo) is needed to cover LLM API costs? Need to model token costs per query against subscription revenue.
5. **Enterprise sales vs. self-serve?** Cityscape offers 30-minute onboarding calls and enterprise quotes. Should UrbanLayer pursue high-touch enterprise sales or optimize for self-serve conversion?

---

## 7. Implementation Plan: 4-Feature Sprint

> **Status:** Planned (as of 2026-06-07). This section contains the technical implementation plan for 4 revenue-critical features, based on competitive analysis of Chicago Cityscape and internal architecture review.

> **Primary goal:** Revenue-ready product. Every monetizable feature ships with a payment gate.

> **Stack constraint:** Stay lean. No new databases, no new services beyond current stack (SQLite, single Hetzner CX32, FastAPI + React). Exceptions: Stripe (payment infra) and WeasyPrint (server-side PDF).

### 7.1 Sprint Sequencing (14 days)

| Days | Feature | Why This Order |
|------|---------|----------------|
| 1-4 | Property Scorecard + Data Upgrades | Creates the backend endpoint everything else depends on. Data upgrades (YoY crime, address-level 311, permit contacts) ship with it so premium surfaces launch with premium data. |
| 5-8 | Site Explorer ✅ | Most complex UI feature, gets 4 days. Important to build before PDF reports because the Explorer showcases the map interaction design. |
| 9-11 | PDF Zoning Reports (v1, scoped) | Server-side PDF via WeasyPrint. 5 focused pages, no html2canvas risk. Uses scorecard data + optional zoning RAG for bulk standards. |
| 12-14 | Payment System (Stripe) | Gates Scorecard, PDF, and Explorer behind paid tier. Free tier with 3 lookups/day → Pro at $99/mo. |

**Deferred to next sprint:** Spanish language support (fully designed in `language-plan.md`, zero dependencies, self-contained).

### 7.2 Feature 1: Property Scorecard + Data Upgrades

**Concept:** Non-AI instant-load property dashboard. New endpoint `/api/scorecard/{address}` calls all 4 existing domain orchestrators in parallel without the LLM router or synthesizer. Zero Anthropic API cost, sub-second load on warm cache.

**Backend — New endpoint in `main.py`:**
```
GET /api/scorecard/{address}
```

Flow:
1. `geocode_address(address)` from `geo.py` → `(community_area, (lat, lon))`
2. `asyncio.gather` all 4 domain orchestrators + zoning + ARO + address-level 311:
   - `property_domain(lat, lon, workflow="property_intelligence")`
   - `regulatory_domain(lat, lon, workflow="site_due_diligence")`
   - `incentives_domain(lat, lon, ca_name=..., workflow="site_due_diligence")`
   - `neighborhood_domain(lat, lon, community_area=ca, address=..., workflow="property_intelligence")`
   - `lookup_zoning(lat, lon)`
   - `aro_housing_by_community_area(ca_number)`
   - `address_311_complaints(lat, lon)` — new function
3. Return `ScorecardResponse` JSON

Wrap all orchestrators in `_RETRIEVAL_SEM` and `return_exceptions=True` for graceful degradation.

**Geocoding failure handling:**
1. Primary: Census Geocoder (existing)
2. Fallback: Mapbox Geocoding API (restrict to Chicago bounding box, token already available via `VITE_MAPBOX_TOKEN`)
3. PIN input: Accept `?pin={pin14}` query param → skip geocoding, look up lat/lon from Parcel Universe
4. Error: HTTP 422 with suggestion to try a different format or enter a PIN

**Data Upgrade 1a — Crime YoY Comparison:** Replace 2-month MoM (seasonal noise) with Year-over-Year same-month comparison. New function `crime_yoy_by_community_area()` in `crime.py` fetches the same date range from 1 year ago. Assembler computes YoY deltas.

**Data Upgrade 1b — Permit Contacts:** Expand `$select` in `buildings.py` detail query to include `contact_1_type, contact_1_name` through `contact_3_type, contact_3_name`. Extract general contractor names in assembler. New `PermitSummary.recent_contractors` field.

**Data Upgrade 1c — Address-Level 311:** New function `address_311_complaints()` in `three11.py` queries 311 within ~50m radius of the address (bounding box on lat/lon). Flags high-risk complaint types: "No Heat", "Rodent Baiting", "Water in Basement", "Building Dangerous/Hazardous". Surfaces as a property health audit on the Scorecard.

**Frontend — New route `/scorecard/:address`:** Full-width 2-column grid reusing existing card components (PropertyCard, RegulatoryCard, IncentivesCard, NeighborhoodCard). Address input with autocomplete. Loading skeleton. Clear geocoding error states.

**Chat ↔ Dashboard — Contextual "Investigate" entry points:** Each data card gets specific chat shortcuts (not a generic "Ask AI" button):
- Zone class label → `"What are the allowed uses, setbacks, and FAR for RT-4 zoning?"`
- Active overlay badge → `"What are the development restrictions for [overlay name]?"`
- TIF district → `"How much TIF funding is available in [district] and what projects qualify?"`
- Flood zone → `"What are the flood insurance requirements for FEMA zone [code]?"`
- High violations count → `"Explain common violation types at [address] and remediation costs."`
- Community area → `"What's going on near [address]?"` (full RAG pipeline)

Implementation: `onInvestigate?: (question: string) => void` prop on each card → navigates to `/?q={question}`.

### 7.3 Feature 2: Site Explorer / Property Finder ✅ DONE (2026-06-07)

**Concept:** Map-based bulk parcel filtering by community area and property class. Cityscape's highest-value paid feature ($125/mo tier). **Implemented** as `backend/retrieval/explore.py` + `/api/explore` (paginated) + `/api/explore/map` (5000 cap). Frontend at `/explore` with split-screen layout, class-colored deck.gl dots, paginated table, click-to-Scorecard via lat/lon. Premium-gated.

**Backend — New endpoint in `main.py`:**
```
GET /api/explore?community_area={number}&class_prefix={prefix}&limit=100&offset=0
```

**New module `backend/retrieval/explore.py`** queries Cook County Parcel Universe (`pabr-t5kh`).

**Cook County Socrata — already handled.** `socrata_get()` accepts `base_url` and `app_token`. `config.py` already has `cook_county_socrata_base = "https://datacatalog.cookcountyil.gov/resource"`. Uses the same pattern as `property/parcels.py:_socrata_parcel_fallback()`.

**Query strategy:**
1. Get bounding box from `community_area_bounds(ca)` in `geo.py`
2. SoQL `$where`: lat/lon bounding box + optional class prefix filter
3. `$limit=100&$offset=0&$order=pin`
4. Parallel `count(pin)` query for total count

**Property class groups:** Residential (prefix `2`), Multi-family (`3`), Commercial (`5`), Industrial (`6`), Vacant (`0`/`1`). Lookup dict with ~50 class codes → descriptions.

**PIN → Scorecard navigation:** Parcel Universe returns PIN + lat/lon, not addresses. Extend Scorecard endpoint to accept `?lat=...&lon=...` as alternative to `{address}` — skip geocoding, reverse community-area lookup via `community_area_by_point()`.

**Frontend — New route `/explore`:** Split-screen layout.
- Left panel (40%): Filter controls + results table (scrollable, paginated at 100/page)
- Right panel (60%): Mapbox + deck.gl map

**Map behavior:**
- All parcels shown on map (deck.gl handles thousands) — table paginates independently
- Hover sync for visible table page only
- Community area selection → `flyTo` bounds
- Click dot → popup with PIN, class description, "View Report" link

**Color mapping by class prefix:**
- Residential: `#4fc3f7` (light blue)
- Multi-family: `#7e57c2` (purple)
- Commercial: `#ffd54f` (amber)
- Industrial: `#ef5350` (red)
- Vacant: `#78909c` (gray)

**Designed for future paid tier:** Additional filters (lot size, assessment value, transit proximity) → more `$where` clauses. CSV/GeoJSON export. Saved searches. Freeform polygon via `@mapbox/mapbox-gl-draw`.

### 7.4 Feature 3: PDF Zoning Reports (v1)

**Approach:** Server-side PDF via WeasyPrint. Produces native PDF with selectable text, vector graphics, proper page breaks. No html2canvas, no WebGL capture issues.

**v1 Report Specification (5 Pages):**

**Page 1 — Cover:** UrbanLayer branding, property address, PIN, zoning classification, community area, report date. Clean branded header (no map screenshot in v1).

**Page 2 — Property:** PIN, building class + description, physical characteristics table, 3-year assessment history with YoY change, sales history with price-per-sqft, estimated annual tax (PTAXSIM), tax incentive class, address-level 311 complaint summary, recent permits with contractor names. Source: Cook County Assessor via Socrata.

**Page 3 — Zoning & Regulatory:** Zone class + full name, bulk standards from municipal code RAG (FAR, height, setbacks — graceful fallback to "Consult Title 17" if RAG returns nothing), 14-layer overlay status matrix (checkmark/dash), FEMA flood zone, EPA brownfields, ARO housing. Source: Chicago Zoning MapServer, FEMA, EPA.

**Page 4 — Incentives & Neighborhood:** TIF district financials, OZ/EZ status, SBIF/NOF grants, demographics (population, income, poverty, unemployment, owner-occupied), Walk Score / Transit Score / Bike Score, transit access. Source: Cook County Assessor, HUD, Census ACS, Walk Score API.

**Page 5 — Data Sources & Disclaimers:** Full source citation table with freshness dates. Methodology notes. Legal disclaimer (prominent).

**Backend — New endpoint:**
```
GET /api/report/{address}?format=pdf
```

Flow: scorecard data → optional vector search for zoning bulk standards → Jinja2 HTML template → WeasyPrint → PDF StreamingResponse.

**New dependency:** `pip install weasyprint` + Docker `apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`.

**v1 Status: Done** (2026-06-07). Live at `/api/report?address=...` with download button on Scorecard page.

**v2 Plan: Premium Development Feasibility Report** (full spec in `claude-context/expansion-roadmap.md` §8):
- Transform from data summary → actionable development feasibility analysis ($100–200/report)
- 5 targeted Title 17 vector searches (bulk standards, setbacks, uses, parking, development standards) + Claude Haiku structured extraction (~$0.001/report)
- Calculated development potential: FAR × lot_sqft = max buildable area, development surplus
- 4 new data retrievals: nearby comparable sales (CCAO `wvhk-k5uv`), address-specific permits, adjacent parcel zoning (4-directional), nearby new construction/demolition activity
- 8-section professional report: Executive Summary → Zoning & Standards → Property → Regulatory → Incentives → Market & Comps → Site Condition → Sources & Disclaimers
- Traffic-light indicators, structured tables from Haiku-extracted values, "Recommended Next Steps" for genuine data gaps
- New files: `backend/zoning_extract.py`, new functions in `buildings.py`, `zoning.py`, `property/sales.py`
- New models: `ZoningStandards`, `DevelopmentPotential`, `ComparableSale`, `NearbyDevelopment`, `ReportData`

### 7.5 Feature 4: Payment System (Stripe)

**Tier Structure:**

| Tier | Price | Includes | Limits |
|------|-------|---------|--------|
| **Free** | $0 | Scorecard (3/day), basic chat (3/day), map view | No PDF reports, no Explorer |
| **Pro** | $99/mo ($1,089/yr) | Unlimited scorecard, PDF reports, Explorer, chat, municipal code RAG | All features unlocked |

**Backend — Stripe Checkout integration:**
- New module `backend/payments.py`: `POST /api/checkout` (create session), `POST /api/webhook/stripe` (handle events), `GET /api/subscription` (status check)
- Schema v7 migration: add `tier`, `stripe_customer_id`, `stripe_subscription_id` to `users` table
- New FastAPI dependency `check_tier(required)` for endpoint gating
- Apply to: `/api/scorecard` (free: 3/day, pro: unlimited), `/api/report` (pro only), `/api/explore` (pro only), `/chat` (free: 3/day, pro: unlimited)

**Frontend:**
- `PricingPage.tsx` — `/pricing` route, Free vs Pro comparison, Stripe Checkout button
- `UpgradePrompt.tsx` — modal on 403 `upgrade_required` responses
- `UserMenu.tsx` — tier badge (Free / Pro)
- Explorer/Scorecard — gated states for free users (blurred results, upgrade CTA overlay)

**Stripe flow:** User clicks upgrade → `POST /api/checkout` → redirect to Stripe → webhook fires → tier updated → redirect back.

### 7.6 Updated Pricing Model (Revised from §3.3)

| Tier | Price | Includes | Conversion Strategy |
|------|-------|---------|---------------------|
| **Free** | $0 | 3 scorecard lookups/day, 3 chat queries/day, map view, no PDF reports, no Explorer | Hook users, demonstrate value |
| **Pro** | $99/mo ($1,089/yr) | Unlimited scorecard, unlimited PDF reports, full Explorer, unlimited chat, municipal code RAG, PTAXSIM tax projections | Undercut Cityscape's $125/mo while offering AI features they lack |
| **Enterprise** | $249/mo ($2,749/yr) | Everything in Pro + team seats, CSV/GIS export, zoning alert monitoring, contractor lead gen, API access | Capture firms. Deferred to future sprint. |

### 7.7 Shared Infrastructure

**Navigation:** Shared `NavBar` component with links to Chat, Explore, Pricing. UserMenu with tier badge.

**Feature interconnections:**
- Scorecard → Chat: Contextual "Investigate" buttons per data card
- Scorecard → PDF: "Download Report" triggers `/api/report/{address}` (pro only)
- Explorer → Scorecard: Click parcel → `/scorecard/?lat=...&lon=...`
- Chat → Scorecard: "View Scorecard" link when address context exists
- Payment → All: 403 responses trigger `UpgradePrompt`

### 7.8 Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cook County GIS down | Scorecard PropertyCard empty | Socrata fallback exists. Other domains still work without PIN |
| Census Geocoder fails | Scorecard can't load | Mapbox fallback + PIN input option |
| Parcel Universe slow for large CAs | Explorer timeout | Cap `$limit=100`, parallel count query, "Load more" |
| WeasyPrint system deps | PDF fails in Docker | Add `apt-get install` to Dockerfile. Test build early |
| Municipal code RAG misses bulk standards | Zoning page incomplete | Graceful fallback: "Consult Title 17" |
| Stripe webhook reliability | Tier not updated after payment | Webhook + polling fallback via `/api/subscription` |

### 7.9 Verification Plan

1. **Scorecard:** Load `/scorecard/2400+N+Milwaukee+Ave` in <2s. Test residential, commercial, industrial addresses. Test geocoding failure → error message. Test PIN input bypass.
2. **Data upgrades:** YoY crime shows sensible deltas. Address-level 311 at known building. Permit contacts populated.
3. **Investigate buttons:** Click zone class → chat opens with correct pre-populated question.
4. **Explorer:** Logan Square + Residential → map zooms, dots appear, table populates. Austin (large CA) → pagination works. Hover sync. Click row → Scorecard loads via lat/lon.
5. **PDF Report:** 5-page PDF downloads with all sections, proper page breaks, branding. Test TIF address and non-TIF. Multiple PDF viewers.
6. **Payment:** Stripe test checkout → webhook → tier update. Free-tier limits enforced. Pro unlimited. Gated states display correctly.
7. **Regression:** All ~444 existing tests pass. TypeScript type check clean. Docker build succeeds.
