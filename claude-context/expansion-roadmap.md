# Expansion Roadmap — UrbanLayer

## Completed Phases

All expansion phases from the original `chicago_expansion_plan.md` are complete:

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Infrastructure + Regulatory Domain | Done — models, routing, domain orchestrators, overlay layers 2-24 |
| Phase 2 | Property Domain | Done — parcels, characteristics, assessments, sales, PTAXSIM tax estimation |
| Phase 3 | Regulatory Domain | Done — overlays, FEMA flood, EPA brownfields |
| Phase 4 | Incentives Domain | Done — TIF boundaries + financials, Enterprise Zones, Opportunity Zones |
| Phase 5 | Neighborhood Domain | Done — demographics, transit proximity, Walk Score API |
| Phase 6 | Frontend Integration | Done — PropertyCard, RegulatoryCard, IncentivesCard, NeighborhoodCard, map overlay/incentive polygons |
| Phase 7 | Polish & Optimization | Done — TTL caching, startup preloading, graceful degradation, workflow_hint, eval expansion (39 queries), overlay/incentive map geometry |

Original Buckets 1-3 also complete: mobile responsiveness, file upload, admin dashboard, LLM-as-judge eval, legal-domain reranker, data source coverage benchmark (29 queries across 29 sub-sources, 83% coverage rate).

## Remaining Opportunities (Tier 3)

These were identified as "nice to have" and not yet implemented:

| Integration | Value | Difficulty | Notes |
|-------------|-------|------------|-------|
| ~~Cook County Tax Incentive Classes (6b, 7a)~~ | ~~Medium~~ | ~~Low~~ | **Done** — Interprets `class` field from Parcel Universe as incentive classification (6b/6c/7a/7b/7c/8). Enriches IncentivesSummary in assembler. |
| ~~SBIF Projects~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `grant_programs.py` queries `etqr-sz5x` (2,152 records) by community area name |
| ~~Neighborhood Opportunity Fund~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — Combined with SBIF in `grant_programs.py`. Queries `j7ew-b73u` (large) + `rym7-49n8` (small) |
| ~~ARO Housing Data~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `aro_housing.py` queries `s6ha-ppgi` (598 records). Enriches RegulatorySummary when regulatory_domain active |
| ~~Food Inspections~~ | ~~Low~~ | ~~Low~~ | **Done** — `food_inspections_api`, pass/fail/risk breakdown, recent inspections |
| ~~Vacant Buildings~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `vacant_buildings_api`, by-department counts, recent reports with fines |
| Illinois Professional Licenses | Low | Medium | Different Socrata portal (data.illinois.gov). Deferred — low value, different base URL/auth pattern |

## ArcGIS Layer Audit (2026-06-04)

Evaluated the 5 unintegrated Chicago Zoning MapServer layers. None warranted integration:

| Layer | Name | Decision | Reasoning |
|-------|------|----------|-----------|
| 10 | Downtown Area | Skip | Single large polygon, not actionable for property-level queries |
| 14 | TSL Route | Skip | CTA transit routes — redundant with TOD station layers (13, 24) already integrated |
| 18 | Special District SubArea | Skip | Duplicates PMD SubAreas (layer 12) already integrated |
| 19 | Downtown Exclusion Zone | Skip | Narrow regulatory exclusion, very limited use case |
| 21 | Planning Regions | Skip | Administrative boundaries, not actionable for users |

## Tier 3 Design Decisions (2026-06-04)

**Tax Incentive Classes**: The `class` field was already being retrieved from the Parcel Universe dataset in `parcels.py`. Rather than adding a new API call, the assembler now interprets existing class codes (6b/6c/7a/7b/7c/8) as tax incentive classifications. The property class comes from the property domain but the incentive interpretation lives in the assembler since it enriches the IncentivesSummary — a cross-domain concern handled at assembly time rather than in either orchestrator.

**SBIF + NOF combined**: All three datasets (SBIF, NOF Large, NOF Small) share identical schemas and represent the same concept (city grant programs). Combined into a single `grant_programs.py` module that queries all 3 in parallel and tags results by program source. They're wired into the incentives domain orchestrator (not as separate source tags) because they're contextual enrichment for incentive analysis, not standalone data sources worth routing separately.

**ARO Housing as parallel source**: ARO housing runs as a standalone task in `main.py` (parallel with the regulatory domain), not nested inside the regulatory orchestrator. This avoids adding latency — the regulatory orchestrator would need to complete overlay detection before conditionally fetching housing data. Instead, ARO housing always fetches for the community area when regulatory_domain is active, and the assembler attaches it to RegulatorySummary. The dataset is small (598 records) so the unconditional query is cheap.

**Violation categorization hybrid**: Investigated using `violation_code` as the primary categorization key. The codes are heterogeneous alphanumeric strings (CN190019, EV1110, AAG679, BR1010) with no consistent structure — a full code-to-category mapping would require maintaining thousands of entries. Instead, added code-prefix mapping for the two clear prefixes (EV→Elevator, BR→Boiler) and expanded keyword coverage to catch common abbreviations (e.g., "ELEVA" for elevator, "ELECT" for electrical). The keyword approach remains primary.

## Planned: Multi-Language Support (i18n)

Full implementation plan in `language-plan.md`. Target languages: English (default), Spanish, Polish, Simplified Chinese, Traditional Chinese.

**Architecture**: Backend stays English-only (DB, Qdrant, APIs unchanged). Translation at two boundaries: (1) synthesizer streams response in target language via `LANGUAGE_INSTRUCTION` appended to system prompt, (2) React frontend localized via `react-i18next` with bundled JSON catalogs.

**Key changes**:
- `ChatRequest.language` field threaded through entire SSE pipeline
- DB schema v7: `language` column on conversations table
- Conversation synthesis forced for non-English follow-ups (English heuristics don't match other languages)
- Router prompt reinforced: `search_query` always in English (bge-base-en-v1.5 is English-only)
- `POST /api/translate` endpoint (Haiku + TTLCache) for on-demand source chunk translation
- `LanguageSelector` component in header, ~90+ hardcoded strings extracted to i18n keys
- Term definitions (~300 entries) in separate per-language JSON files with English fallback

**Latency**: +0ms for English path; +200-600ms for non-English (forced synthesis + language instruction overhead).

## Revenue Sprint Progress (2026-06-07)

| Feature | Status | Notes |
|---------|--------|-------|
| **Property Scorecard + Data Upgrades** | Done | `GET /api/scorecard?address=...`, crime YoY, permit contacts, address-level 311. Frontend at `/scorecard` |
| **Site Explorer / Property Finder** | Planned | Bulk parcel filtering by community area + property class |
| **PDF Zoning Reports v1** | Done | `GET /api/report?address=...`, 5-section WeasyPrint PDF (Cover, Property, Zoning/Regulatory, Incentives/Neighborhood, Disclaimers). Vector search for bulk standards. Frontend download button on Scorecard. |
| **PDF Zoning Reports v2** | Planned | Premium development feasibility report. 8-section professional layout, 5 targeted vector searches + Haiku extraction, calculated development potential, comparable sales, address-specific permits, adjacent zoning. Full spec in §8 below. |
| **Stripe Payment System** | Done | Free/Pro tiers, Stripe Checkout, webhook lifecycle, billing portal, `require_tier()` gating on `/api/report` |

Full sprint plan in `urbanlayer_master_strategy.md` section 7.

## Production Readiness

| Item | Status |
|------|--------|
| Docker Compose (Qdrant + backend + frontend) | Done |
| Dockerfile (FastAPI backend) | Done — multi-stage, CPU-only PyTorch, baked HF models, non-root user |
| Dockerfile (Frontend) | Done — multi-stage Vite build + nginx, `NGINX_CONF` build arg for dev/prod |
| Production nginx config | Done — `nginx.prod.conf` with HTTPS (Cloudflare Origin Cert), security headers, gzip, CSP for Mapbox |
| Production compose override | Done — `docker-compose.prod.yml` layers port 443 + SSL volume on base config |
| Server deployment (HTTP) | Done — all 3 services running at `http://178.105.184.66` |
| DNS + HTTPS (Cloudflare) | Done — Full (Strict) + Origin Certificate, security headers verified |
| Qdrant data transfer | Done — 14,535 vectors snapshot-transferred |
| Google OAuth setup | Done — OAuth client configured, auth active on server |
| CI pipeline (tests + type check) | Done — `.github/workflows/ci.yml`, auto-deploy on push to main |
| CI/CD deploy secrets | Done — `SERVER_SSH_KEY` + `SERVER_HOST` configured in GitHub repo secrets |
| Monitoring / alerting | Done — UptimeRobot active, Sentry active (EU region DSNs configured) |
| AI code review on PRs | Done — `.github/workflows/code-review.yml`, `anthropics/claude-code-action@v1`, Claude Code GitHub App installed |
| Tier 3 production deploy | Done — PR #1 merged (2026-06-05), all integrations live on production |
| CI fixes | Done — `anthropic_api_key` default, Walk Score test mocking, `id-token: write` permission, `ANTHROPIC_API_KEY` secret |
| CI deploy key | Done — passphrase-free ed25519 key, verified end-to-end (2026-06-05) |

---

## 8. PDF Zoning Report v2 — Premium Development Feasibility Report

> **Status:** Planned (designed 2026-06-07). v1 is live. v2 transforms the report from "property data summary" into a **development feasibility analysis** that answers the builder's core question: "What can I build here, and what will it cost?"

> **Revenue target:** $100–200/report (or bundled into Pro subscription). Undercuts Chicago Cityscape's $1,000 custom zoning assessments by 80–90%.

> **Latency expectation:** Premium reports can take 10–15 seconds. Psychologically, longer generation time signals more comprehensive analysis.

### 8.1 What Builders Need (from Cityscape competitive research)

1. **What can I build?** — Permitted uses, special uses, conditional uses for this zoning district
2. **How much can I build?** — FAR × lot area = max buildable sq ft, max height, max stories, lot coverage limit
3. **Where on the lot?** — Front/side/rear setbacks, building envelope
4. **Parking requirements** — Minimum stalls by use type
5. **Regulatory constraints** — Overlays, planned development restrictions, historic review, landmark status
6. **Environmental risks** — Flood zone, brownfield contamination, soil concerns
7. **Financial feasibility** — Tax projection, TIF funding available, incentive eligibility, recent comparable sales
8. **Market context** — Demographics, transit access, nearby development activity
9. **Property condition** — Violations, 311 complaints, existing building characteristics
10. **Utility/infrastructure access** — Water, sewer, electric (limited by data availability)

### 8.2 What v1 Has vs. What v2 Adds

| Need | v1 State | v2 Enhancement |
|------|----------|----------------|
| Permitted uses | Generic vector search | 5 targeted per-district vector queries + Haiku extraction |
| FAR/height/setbacks | One vector search, often vague | Structured extraction → calculated development potential |
| Parking requirements | Not queried | Targeted Title 17-5 query with parking ratios |
| Adjacent land use | Not fetched | 4-directional zoning lookup at cardinal points |
| Nearby comparable sales | Only subject property sales | Radius query on CCAO sales dataset (0.25mi, 3yr) |
| Address-specific permits | Community-area aggregate only | Exact-address Socrata query with contractor names |
| Building envelope calc | Not computed | FAR × lot_sqft = max buildable area |
| Development potential | Not synthesized | max_buildable - existing_bldg = surplus capacity |
| Nearby development activity | Not tracked | New construction/demolition permits within 0.25mi |

### 8.3 Phase 1: Zoning Code Deep Dive (5 Targeted Vector Searches + Haiku Extraction)

Chicago's Municipal Code Title 17 (Zoning Ordinance) structure:
- **17-2**: Use Standards (what's allowed in each district)
- **17-3**: Bulk, Density & Area Standards (FAR, height, lot coverage, setbacks)
- **17-5**: Off-Street Parking & Loading (minimum spaces by use type)
- **17-8**: Development Standards (landscaping, screening, lighting)

**5 targeted queries** (replacing single generic search):

1. **Bulk Standards**: `"{zone_class} floor area ratio maximum building height lot coverage minimum lot area"` → FAR, height (ft), lot coverage %, minimum lot size
2. **Setbacks & Yards**: `"{zone_class} required setbacks front yard side yard rear yard transition setback"` → Front/side/rear minimums in feet, transition rules
3. **Permitted & Special Uses**: `"{zone_class} permitted uses use group special use"` → As-of-right vs. special approval categories
4. **Parking Requirements**: `"off-street parking spaces required {zone_class} dwelling unit commercial retail"` → Minimum parking ratios
5. **Development Standards**: `"{zone_class} landscaping screening loading dock building entrance"` → Site design requirements

**Haiku Extraction Step** (~$0.001/report):

Send all 5 sets of chunks to Claude Haiku with structured extraction prompt:
```json
{
  "far": "float or null",
  "max_height_ft": "int or null",
  "max_stories": "int or null",
  "lot_coverage_pct": "float or null",
  "min_lot_area_sqft": "int or null",
  "front_setback_ft": "int or null",
  "side_setback_ft": "int or null",
  "rear_setback_ft": "int or null",
  "parking_residential": "string or null (e.g. '1 per unit')",
  "parking_commercial": "string or null (e.g. '1 per 500 sqft')",
  "permitted_uses": ["key categories"],
  "special_uses": ["requires approval"],
  "notes": ["important caveats or conditions"]
}
```

**Calculated Development Potential** (from extracted values + property data):
- `max_buildable_sqft = FAR × land_sqft`
- `max_lot_coverage_sqft = lot_coverage_pct × land_sqft`
- `development_surplus = max_buildable_sqft - existing_bldg_sqft`
- `parking_spaces_required` (estimated from use + unit count or sqft)

### 8.4 Phase 2: New Data Retrievals

#### A. Nearby Comparable Sales (`backend/retrieval/property/sales.py`)
- Query CCAO sales dataset (`wvhk-k5uv`) with bounding box (±0.004° ≈ 0.25mi)
- Filter: same property class prefix, last 3 years, limit 10
- Return: address, sale_date, sale_price, building_class, sqft, price_per_sqft, distance_mi

#### B. Address-Specific Permits (`backend/retrieval/buildings.py`)
- Query permits dataset (`ydr8-5enu`) by exact street address fields
- Last 5 years, all types, limit 20
- Return: permit_type, work_description, issue_date, reported_cost, contractor contacts

#### C. Adjacent Parcel Zoning (`backend/retrieval/zoning.py`)
- Call `lookup_zoning()` at 4 cardinal points (N/S/E/W, ~50m offset)
- Return: `dict[direction → zone_class]`
- Shows zoning transitions and compatibility constraints

#### D. Nearby New Construction (`backend/retrieval/buildings.py`)
- Permits dataset filtered for "NEW CONSTRUCTION" or "WRECKING/DEMOLITION" within 0.25mi, last 12 months
- Return: count by type, recent projects with addresses

### 8.5 Phase 3: Report Structure (8 Sections)

#### Section 1: Executive Summary (1 page)
- Address, PIN, zone class, lot size, current use
- **Headline**: "This {lot_sqft} sq ft lot in {zone_class} allows up to {max_buildable_sqft} sq ft at {max_height} ft."
- 3–5 key findings bullets
- Traffic-light indicators: green (favorable) / yellow (attention) / red (constraint)

#### Section 2: Zoning & Development Standards (1–2 pages)
- Zone class + description
- Bulk standards table (FAR, height, lot coverage, min lot area)
- Setbacks table (front/side/rear/transition)
- Development envelope (calculated max buildable area)
- Permitted uses grouped by category
- Special/conditional uses
- Parking requirements by use type
- Overlay restrictions + planned development status

#### Section 3: Property & Physical Characteristics (1 page)
- Current building: class, age, sqft, stories, units
- Land: lot size
- Tax assessment: current + 3-year history + PTAXSIM estimate
- Development surplus: current vs. maximum allowed
- Tax incentive class (6b/7a if applicable)

#### Section 4: Regulatory & Environmental (1 page)
- 14-layer overlay matrix with development impact descriptions
- FEMA flood zone + insurance implications
- EPA brownfield proximity + remediation status
- ARO housing obligations
- Historic/landmark review requirements
- TOD eligibility (bonus density, reduced parking)

#### Section 5: Financial Feasibility & Incentives (1 page)
- TIF district + available funding + recent awards
- Opportunity Zone benefits
- Enterprise Zone benefits
- Grant program history (SBIF/NOF)
- Tax projection (PTAXSIM)
- Property class incentive details

#### Section 6: Market Context & Comparables (1–2 pages)
- Nearby sales table (5–10 comps with $/sqft)
- Demographics (population, income, education, owner-occupancy)
- Walk/Transit/Bike Scores
- Transit access (CTA/Metra + distance)
- Nearby development activity

#### Section 7: Site Condition & History (1 page)
- Building violations (open/closed, by category)
- 311 complaints at address (types, high-risk flags)
- Address-specific permit history (work, costs, contractors)
- Vacant building reports

#### Section 8: Data Sources & Disclaimers (1 page)
- Full source citation with freshness dates
- Methodology notes
- Professional disclaimer
- Recommended next steps

### 8.6 Implementation: Key Files

| File | Change |
|------|--------|
| `backend/zoning_extract.py` | **New** — Haiku extraction of structured zoning parameters from code chunks |
| `backend/retrieval/property/sales.py` | New: `nearby_comparable_sales()` |
| `backend/retrieval/buildings.py` | New: `address_specific_permits()`, `nearby_new_construction()` |
| `backend/retrieval/zoning.py` | New: `adjacent_parcel_zoning()` |
| `backend/main.py` | New `_fetch_report_data()`, update `/api/report` endpoint |
| `backend/models.py` | New: `ComparableSale`, `ZoningStandards`, `DevelopmentPotential`, `NearbyDevelopment`, `ReportData` |
| `backend/templates/zoning_report.html` | Full rewrite — 8-section professional layout |

### 8.7 What v2 Cannot Solve (Genuine Data Gaps → "Recommended Next Steps")

| Need | Why We Can't | What the Report Says |
|------|-------------|---------------------|
| Property ownership names | Cook County CAPTCHA-protected | "Consult Cook County Recorder of Deeds" |
| Utility locations (water/sewer/electric) | Not in public GIS | "Contact DWM and ComEd for utility maps" |
| Soil/geotechnical data | Requires physical boring | "Recommend Phase I ESA and geotech report" |
| Survey / exact property lines | Requires licensed surveyor | "Engage licensed surveyor for boundary survey" |
| Pending zoning changes | City Clerk PDFs only | "Check Legistar for active zoning applications" |
| Easements | Title search required | "Recommend title search for recorded easements" |
| Traffic counts | CDOT doesn't expose freely | "Request traffic study from CDOT if required" |

These are explicitly called out as "Recommended Next Steps" in Section 8 — this adds value by telling builders exactly what else they need to investigate.

### 8.8 Verification Plan

1. **Vector search quality**: Query 5 targeted searches for RT-4, B3-2, C1-3 districts. Verify FAR/height/setbacks in results.
2. **Haiku extraction**: Confirm structured JSON output for known zone classes matches published standards.
3. **Comparable sales**: Test at 2400 N Milwaukee — expect nearby residential/commercial sales.
4. **Address permits**: Test at known active address — expect permit history with contractors.
5. **Adjacent zoning**: Verify 4-directional lookup at known zone boundaries.
6. **Development potential**: For RT-4 lot (FAR=1.2), verify max_buildable = 1.2 × land_sqft.
7. **Full PDF**: Generate for 3 test addresses (residential, commercial, industrial). All sections render, calculations correct, fallbacks work.
8. **Regression**: All existing tests pass, TypeScript clean, scorecard endpoint unaffected.
