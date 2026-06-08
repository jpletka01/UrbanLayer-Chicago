# Competitive Analysis — UrbanLayer

## Chicago Cityscape

### What They Are
Chicago Cityscape is a private LLC founded in 2014 by urbanist Steven Vance. It is a data aggregation platform (not AI-powered) that consolidates municipal, county, and state public records into a single searchable interface for real estate and construction professionals.

### Market Validation
- **22,580+ registered users** (growing at ~60 signups/week)
- **Pricing:** $50/mo (Permit Tracker), $85/mo (Lead Finder), $125/mo (Real Estate Pro), ~$1,375/yr annual
- **One-off reports:** $55 per Property Report, $150–$350 per Place Report
- **Custom zoning assessments:** $1,000+ per report
- **Team size:** 2–10 employees, estimated <$5M ARR
- **Geography:** Cook County (1.8M properties), recently expanded to Lake County IL (~300K) and Lake County IN (~300K)

### Their Three Subscription Tiers

| Tier | Price | Target | Core Value |
|------|-------|--------|------------|
| **Permit Tracker** | $50/mo | Subcontractors | Search all building permits and violations, extract contractor profiles |
| **Lead Finder** | $85/mo | Construction service providers | Permit Tracker + Proposed Projects detection + owner/developer contact info |
| **Real Estate Pro** | $125/mo | Developers, brokers, architects | Everything + 1.8M property database, incentives, cannabis sites, government land, comparison/appraisal tools |

### Features They Have That We Lack

| Feature | What It Does | Difficulty to Build | Revenue Impact |
|---------|-------------|---------------------|----------------|
| **Property Finder (Prospecting)** | Bulk filter parcels by zoning, transit proximity, vacancy, land use | High | Very High — this is their flagship paid feature |
| **People & Company Portfolios** | Index 200K+ developers/contractors/architects by permit history, rank by volume | Medium | High — subcontractors pay for this |
| **Automated Comps** | Filter nearby sales by distance, property class, price range for valuation | Medium | High — brokers and lenders need this daily |
| **Pending Zoning Changes** | Track active zoning change applications, variances, special uses through City Council | Medium (requires PDF parsing) | High — attorneys and developers pay premium for early intel |
| **Custom Polygon Reports** | Draw a boundary on the map, auto-generate a PDF summarizing everything inside it | Medium | Medium — Place Reports sell for $150–$350 each |
| **Demolition Alerts** | Daily email notifications of demolition permits | Low | Medium — retention feature |
| **Property Tracker** | Alerts when violations, permits, or license changes hit your watched properties | Low | Medium — portfolio management for landlords |
| ~~**Data Export (CSV/GIS)**~~ | ~~Download any dataset as Excel or GeoJSON~~ | ~~Low~~ | ~~Medium — **Shipped**: CSV export on Scorecard, Explorer, Analytics~~ |
| **ADU Portal** | Dedicated tool checking ADU eligibility, financing, and code requirements | Low | Low-Medium — niche but growing demand |
| **Cannabis Site Selection** | Filter for dispensary-eligible locations with buffer zone compliance | Low | Low-Medium — niche |
| **Weekly Picks Newsletter** | Algorithmically scored "top 10 developable properties" email every Monday | Low | Low — lead magnet for signups |

### Data They Have That Is Hard to Get Free

| Data Type | Why It's Hard | How They Get It | Can UrbanLayer Replicate? |
|-----------|--------------|-----------------|---------------------------|
| **Property owner / taxpayer names** | Cook County Assessor and Treasurer websites are CAPTCHA-protected, bulk scraping blocked | Lease bulk deed transfers from Cook County Clerk or commercial brokers (CoreLogic, Regrid) | Not for free. Would need a paid data license ($$$) or per-lookup scraping (fragile) |
| **Pending zoning change applications** | Published as scanned PDFs on City Clerk's Legistar portal, no structured dataset | Proprietary PDF parsers + manual data entry | Possible with LLM-based PDF extraction, but labor-intensive to maintain |
| **Illinois SOS corporate registrations** | No free bulk API, charges per search, scraping prohibited | Integrate corporate registration datasets to map LLCs to real owners | Not practically replicable without a paid data source |
| **Contractor contact info (phone/address)** | Removed from bulk Socrata dataset in 2019 for privacy | Likely scraped from individual permit application pages on chicago.gov/permit, or from business license records | Partially replicable via Business Licenses dataset or individual permit page lookups |

### Exploitable Weaknesses

1. **No AI / Natural Language Interface** — Users must learn dozens of filters and navigate dense tabular UI. They offer mandatory 30-minute onboarding sessions because the tool is hard to learn.
2. **No Municipal Code Search** — They link to external code sites but cannot answer legal/zoning interpretation questions like "Can I build a coach house in RT-4?"
3. **No Tax Projection** — They display historical tax bills but cannot simulate future taxes (UrbanLayer has PTAXSIM).
4. **Legacy Web Architecture** — Built incrementally since 2014; feels dated compared to modern SPA + WebGL map interfaces.
5. **No Free Tier** — No way to try before you buy. A generous free tier with conversion pressure is a proven SaaS growth strategy they are not using.

---

## Data Source Monetization

### Building Permits → Lead Gen
- **Current state:** Grouped by permit type with cost totals and work descriptions on a map.
- **High-value transformation:**
  - Parse `contact_1_type` through `contact_15_type` to identify which trade roles (electrical, plumbing, masonry) are missing from active permits.
  - Create a "Leads" data grid where subcontractors filter for permits missing their trade specialty.
  - Track demolition-to-new-construction ratios by neighborhood as a gentrification/investment signal.
  - Export contractor lead lists to CSV for CRM import.

### 311 Requests → Property Red Flags
- **Current state:** Grouped by department with top types.
- **High-value transformation:**
  - For address-specific searches, query 311 complaints at that exact parcel over the last 12 months.
  - Flag high-risk complaint types: "No Heat", "Water Quality", "Rodent Baiting", "Building Collapse Risk."
  - Position as a **pre-acquisition property health audit**: "This building has 12 open tenant complaints for rodent infestation and no heat. This indicates imminent code violations and tenant friction."

### Crime Data → Risk Scoring
- **Current state:** 2-month MoM trends on a map. Too short a timescale; seasonal noise makes it misleading.
- **High-value transformation:**
  - Switch to **Year-over-Year same-month comparison** to eliminate seasonal bias (e.g., June 2026 vs June 2025).
  - Calculate a localized **Crime Density Index** for business-relevant categories (Robbery, Burglary, Assault) within a 3-block radius.
  - Position for commercial tenants: "This location has a burglary rate 1.8x the neighborhood average, which will likely increase your commercial insurance premiums."

---

## Positioning & Personas

### Competitive Positioning Statement
UrbanLayer is not a "ChatGPT wrapper for city data." It is an **AI-powered urban intelligence platform** that combines the structured data aggregation of Chicago Cityscape with the legal reasoning capabilities of a junior zoning paralegal. The chat interface is not a gimmick—it is the tool that translates dense municipal code tables and regulatory overlays into plain-English, cited answers that save real estate professionals hours of manual research per property lookup.

### Target Customer Personas

1. **Zoning & Land Use Attorneys** — Highest willingness to pay. They bill $300–$600/hr and currently spend hours manually searching the municipal code. UrbanLayer's RAG over Title 17 is a direct time-saver. Marketing angle: *"WestLaw for Chicago zoning."*
2. **Commercial Real Estate Developers** — Need site due diligence (zoning, tax, incentives, environmental) consolidated in one place. Currently use Cityscape + multiple county websites. Marketing angle: *"Your entire due diligence checklist in one search."*
3. **Subcontractors & Construction Service Providers** — Want permit-based lead generation. Will pay $50–$85/mo for filtered lists of active projects missing their trade specialty. Marketing angle: *"Find projects that need you before your competitors do."*
4. **Commercial Brokers & Lenders** — Need comps, tax history, and violation audits for underwriting. Marketing angle: *"Collateral due diligence in 30 seconds."*
5. **Community Organizations & Nonprofits** — Lower willingness to pay individually, but potential for grant-funded institutional licenses. Marketing angle: *"Equitable development data for every neighborhood."*

### Open Strategic Questions

1. **Build vs. Buy for property ownership data?** Licensing bulk deed data from the Cook County Clerk or a broker like Regrid would unlock a major feature gap vs. Cityscape but adds recurring cost.
2. **PDF parsing for pending zoning changes?** The City Clerk's Legistar portal publishes zoning change applications as PDFs. LLM-based extraction could automate this, but maintaining accuracy is labor-intensive.
3. **When to expand beyond Chicago?** The entire pipeline (GIS layers, Socrata datasets, municipal code, county tax system) is Chicago/Cook County-specific. Replication to another city is essentially a rebuild. When does the market justify this investment?
4. **Freemium conversion rate assumptions?** At 3 free lookups/day, what conversion rate to Pro ($99/mo) is needed to cover LLM API costs? Need to model token costs per query against subscription revenue.
5. **Enterprise sales vs. self-serve?** Cityscape offers 30-minute onboarding calls and enterprise quotes. Should UrbanLayer pursue high-touch enterprise sales or optimize for self-serve conversion?
