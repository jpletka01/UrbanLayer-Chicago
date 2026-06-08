# Revenue Sprint — 4-Feature Sprint

**Completed**: 2026-06-07
**Status**: Shipped to production

## What Was Built
4-feature revenue sprint — Property Scorecard + Data Upgrades, Site Explorer, PDF Zoning Reports (v1→v3), Stripe Payment System. All shipped. Free/Pro tier gating active on all premium endpoints.

## Revenue Sprint Progress

| Feature | Status | Notes |
|---------|--------|-------|
| **Property Scorecard + Data Upgrades** | Done | `GET /api/scorecard?address=...`, crime YoY, permit contacts, address-level 311. Frontend at `/scorecard` |
| **Site Explorer / Property Finder** | Done | `GET /api/explore` + `/api/explore/map`, Cook County Parcel Universe (`pabr-t5kh`) by community area + property class. Frontend at `/explore` with Mapbox/deck.gl map (5K parcel cap), paginated table, class-colored dots. Premium-gated. |
| **PDF Zoning Reports v1** | Done | `GET /api/report?address=...`, 5-section WeasyPrint PDF (Cover, Property, Zoning/Regulatory, Incentives/Neighborhood, Disclaimers). Vector search for bulk standards. Frontend download button on Scorecard. |
| **PDF Zoning Reports v2/v3** | Done | v3 shipped (2026-06-08). Premium development feasibility report with Haiku zoning extraction, comparable sales, address-specific permits, traffic-light indicators, professional styling. |
| **Investigate Buttons** | Done | Contextual "Investigate" links below each Scorecard data card. Shared `InvestigateButton` component navigates to `/?q=...`. App.tsx reads `?q=` param and auto-sends to chat. 8 card-level buttons + 2 header buttons. i18n (en/es). |
| **Stripe Payment System** | Done | Free/Pro tiers, Stripe Checkout, webhook lifecycle, billing portal, `require_tier()` gating on `/api/report` |

Full sprint plan below (§7.1–7.9 from `urbanlayer_master_strategy.md`).

## Implementation Details

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

**v2/v3 Plan: Premium Development Feasibility Report** (full spec in `claude-context/expansion-roadmap.md` §8):
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

### 7.6 Updated Pricing Model

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

## Key Decisions

- **Sprint sequencing rationale**: Scorecard first as backend dependency (all other features consume its data pipeline), Explorer before PDF (showcases the map interaction design pattern), Payment last to gate everything once all premium surfaces exist.
- **Non-AI scorecard approach**: Zero Anthropic API cost for structured property lookups. Reuses all 4 existing domain orchestrators without the LLM router or synthesizer. Sub-second load on warm cache.
- **WeasyPrint over html2canvas**: Server-side PDF generation produces native PDF with selectable text, vector graphics, proper page breaks. No browser rendering dependency, no WebGL capture issues.
- **Free/Pro only (no Enterprise yet)**: Ship with two tiers to validate conversion. Enterprise tier ($249/mo with team seats, CSV/GIS export, API access) deferred to future sprint.
- **Cook County Parcel Universe for Explorer**: Same Socrata dataset already used as property domain fallback. Query by community area bounding box + property class prefix. 5K parcel cap for map performance.
