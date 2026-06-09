# PDF Report v4: High-Value Intelligence Additions

**Status:** Planned (2026-06-09)
**Prereq:** Report v3 shipped (TOC, glossary, construction map, comps sqft fix, spacing)

## Context

The $25 development feasibility report is the revenue product. At 14 pages it covers zoning, regulatory, property, market, financial, and site condition data — but several high-value pieces of information are either already in our data pipeline and not surfaced, or derivable from existing data with zero new API calls. The goal is to close information gaps that would otherwise require a professional to open 3+ separate city systems.

Target audience: developers, investors, brokers, architects, land acquisition professionals.

## Guiding Principle

Prioritize information that would otherwise require opening multiple city systems, assessor records, GIS tools, permit databases, or ownership records. Prefer objective intelligence over speculative interpretation.

## Ranked Implementation Plan

### 1. Enhanced Nearby Development Intelligence (HIGHEST value, LOW complexity)

**Why:** This may be the single highest-value improvement in the entire report. The raw data already exists in `NearbyDevelopment.recent_projects` — each dict has `permit_type`, `work_description`, `issue_date`, `reported_cost`, `street_number`, `street_direction`, `street_name`, `latitude`, `longitude`. Currently shown as just "4 permits / 2 permits" counts. Reducing this information to permit counts leaves a significant amount of value on the table.

The goal is to help users understand *what is actually being built nearby* rather than simply reporting permit volume.

**Changes:**
- **`backend/main.py`** (`_fetch_report_data`, ~line 1906): After building `nearby_dev`, enrich each project with `distance_mi` (via `_haversine_mi` from `sales.py`) and `formatted_address` (concatenate street parts)
- **`backend/templates/zoning_report.html`** (~line 829): After the counts info-grid and before the construction map, add a detail table with columns: Type (New/Demo), Address, Description (truncated), Cost, Date, Distance. Allocate generous space — this section justifies expanding beyond a compact table if data quality supports it. Cap at 10 rows.
- **`backend/main.py`** (`_apply_mock_overrides`): Add `distance_mi` and `formatted_address` to mock projects

No model changes — `recent_projects` is already `list[dict]`.

### 2. Parcel Geometry Map with Dimensions & Zoning Context (HIGH value, MEDIUM complexity)

**Why:** `PropertySummary.parcel_geometry` already contains a GeoJSON Polygon from Cook County GIS (`property/__init__.py` line 219, sourced from `parcels.py`). We just don't render it. Showing the lot shape with computed dimensions answers "what does this parcel look like?" without opening the county GIS viewer.

**Expanded scope:** In addition to parcel dimensions, evaluate whether the map can incorporate contextual zoning information already available in the report — specifically adjacent zoning classifications and nearby parcel context. The goal is for a user to understand the site's physical characteristics and immediate zoning environment without opening an external GIS system. Do not increase complexity significantly if this would materially delay implementation, but investigate whether the information is already available (e.g., from existing zoning API responses or nearby parcel queries).

**Changes:**
- **`backend/models.py`**: Add `parcel_map_b64: str | None = None` and `parcel_dimensions: dict | None = None` to `ReportData`
- **`backend/main.py`**: New `_generate_parcel_map(lat, lon, parcel_geojson, basemap_bytes, dimensions, zoning_context)` function following `_generate_zoning_map()` pattern — matplotlib Polygon patch on Mapbox basemap with dimension annotations on edges. If adjacent zoning data is available, annotate surrounding zones on the map.
- **`backend/main.py`**: New `_compute_parcel_dimensions(geojson_polygon)` — compute edge lengths via haversine×5280 for feet, area via Shoelace formula in local feet (cos(lat) correction), identify frontage vs depth by grouping edges by bearing
- **`backend/main.py`** (`_fetch_report_data`): After basemap fetch, if `ctx.property.parcel_geometry` exists, compute dimensions and generate map
- **`backend/templates/zoning_report.html`**: In Property section after the main info-grid (~line 688), add parcel map image + dimensions grid (frontage, depth, computed area, perimeter) with "Confirm with licensed surveyor" disclaimer
- **`backend/main.py`** (`_apply_mock_overrides`): Add mock rectangular polygon geometry + dimensions

**Graceful degradation:** When Cook County GIS is down (Socrata fallback), `parcel_geometry` is `None` — section simply doesn't render.

### 3. Ownership Intelligence from Sales History & Property Records (HIGH value, LOW complexity)

**Why:** One of the highest-value additions in the report. No new data fetching. All signals derived from `PropertySummary.sales_history` (date, price, deed_type), `PropertySummary.tax_breakdown` (agency names reveal exemptions), and existing property/assessor records. Answers "how long has the current owner held this?" and "what does the transfer history tell me?"

**Signals (all factual, defensible):**
- Ownership duration: years since last sale
- Non-arm's-length transfer: sale price ≤ $500 or quit claim deed
- Rapid turnover: <2 years between consecutive sales
- Owner-occupancy: homeowner exemption in tax breakdown
- Recent acquisition: last sale <2 years ago
- Long-term hold: last sale >10 years ago

**Additional signals to evaluate (investigate data availability):**
- Mailing address differs from property address (assessor records may contain mailing address)
- Out-of-state owner (derived from mailing address if available)
- Entity owner vs individual owner (corporate/LLC names in ownership records)
- Other objective ownership indicators available in CCAO or Cook County open data

The goal is to surface acquisition-relevant facts, not predictions or owner intent. During implementation, audit the full set of fields returned by CCAO and Cook County property APIs to identify any additional objective indicators.

**What we do NOT do:** guess owner names, predict intentions, make investment recommendations, speculate about owner motivation.

**Changes:**
- **`backend/models.py`**: Add `ownership_signals: list[dict] = Field(default_factory=list)` to `ReportData`
- **`backend/main.py`**: New `_derive_ownership_signals(prop: PropertySummary) -> list[dict]` — pure Python, no LLM, returns list of `{signal, detail, category}` dicts
- **`backend/main.py`** (`_fetch_report_data`): Call after property context is assembled
- **`backend/templates/zoning_report.html`**: After Sales History table (~line 736), add "Ownership Intelligence" subsection with note that taxpayer names are not available via open data
- **`backend/main.py`** (`_apply_mock_overrides`): Add mock ownership signals

### 4. Surface Existing Data Not Currently Exposed (HIGH value, LOW complexity)

**Why:** This is an explicit planning objective. There is high-value information already being fetched, computed, or stored in memory that is never rendered in the PDF. Surfacing it requires minimal engineering effort and no additional API calls — making it among the highest-ROI work available.

**Methodology:** Before building new features, audit every API response, computed value, and model field in the report pipeline to identify data that is fetched but discarded or available but not rendered.

**Priority categories to audit:**
- **Existing API response fields**: Fields returned by Socrata, ArcGIS, CCAO, and other data sources that are present in responses but not extracted into models
- **Existing computed values**: Intermediate calculations performed during data assembly that are not passed to the template
- **Existing GIS attributes**: Spatial query results that return metadata beyond what is currently used
- **Existing assessor attributes**: CCAO Characteristics (x54s-btds) returns 100+ fields; only ~10 are extracted
- **Existing zoning metadata**: Zoning API responses may contain attributes not currently surfaced
- **Existing permit metadata**: Building permit records contain fields beyond what is currently displayed
- **Existing property characteristics**: Tax, sales, and property records may contain unused fields

**Implementation approach:**
1. Audit each data source's raw API response against what is extracted in the corresponding retrieval module
2. Identify fields with clear user value for the target audience
3. Add extraction to models and rendering to templates
4. Prioritize fields that answer questions a developer/investor would otherwise need a separate system to answer

This category should be prioritized ahead of speculative synthesis features. Item 7 (Additional Building Characteristics) is a specific instance of this objective.

### 5. Additional Building Characteristics (MEDIUM value, LOW complexity)

**Why:** CCAO Characteristics (x54s-btds) is queried with no `$select` filter — all fields returned but only ~10 extracted. Adding exterior wall, basement, garage, A/C costs nothing and helps assess property condition. This is a concrete instance of the Item 4 objective.

**Changes:**
- **`backend/models.py`**: Add to `PropertySummary`: `exterior_wall`, `roof_type`, `basement`, `garage_size`, `air_conditioning` (all `str | None = None`)
- **`backend/retrieval/property/__init__.py`** (~line 156): Extract `char_ext_wall`, `char_roof_cnst`, `char_basement`, `char_gar1_size`, `char_ac` from characteristics response. Pass to PropertySummary constructor.
- **`backend/templates/zoning_report.html`**: In Property info-grid, add conditional rows for non-null values

### 6. Assessment Trend Analysis (MEDIUM value, LOW complexity)

**Why:** `PropertySummary.assessment_history` already has up to 5 years of (year, land, building, total). Currently shown as raw table. Computing the trend (total change %, CAGR) takes 5 lines of math and tells users whether the area is appreciating.

**Changes:**
- **`backend/models.py`**: Add `assessment_trend: dict | None = None` to `ReportData`
- **`backend/main.py`** (`_fetch_report_data`): After effective tax rate computation, calculate trend from assessment_history — total_change_pct, cagr_pct, years, direction
- **`backend/templates/zoning_report.html`**: After Assessment History table (~line 719), add one-line trend summary with contextual note
- **`backend/main.py`** (`_apply_mock_overrides`): Add mock trend data

### 7. Tax Breakdown by Agency (MEDIUM value, LOW complexity)

**Why:** `PropertySummary.tax_breakdown` already has ~15 `TaxLineItem` records (agency, rate, amount). Currently only the total is shown. Top 5 agencies explain where the money goes.

**Changes:**
- **`backend/templates/zoning_report.html`** only: In Financial section after Tax Estimate (~line 897), add table of top 5 agencies sorted by amount. Data is accessed via `report.context.property.tax_breakdown`.

No backend changes needed.

### 8. Opportunities & Constraints Synthesis (MEDIUM value, MEDIUM complexity)

**Why:** Cross-references data already scattered across sections to surface actionable insights. This is the "I would have had to open three systems" feature.

**Deprioritized because:** The strongest parts of the report are factual, verifiable, property-specific intelligence. There is a risk that deterministic synthesis rules create statements that sound insightful but are not consistently meaningful to users. Ship items 1-7 first — enhanced nearby development intelligence, parcel visualization, ownership intelligence, and additional hidden data — before investing in synthesized opportunity scoring or derived interpretations. The report should remain grounded primarily in objective information rather than inferred conclusions.

**Rules (deterministic, no LLM):**
- TOD parking reduction eligible (tod_eligible + parking requirements exist)
- TIF expiration within 3 years
- Vacant lot with full buildable area (bldg_sqft == 0, surplus > 0)
- Open violations as acquisition leverage
- EZ + TIF double benefit
- ARO requirement if ≥10 units in ARO zone
- Development surplus available
- Multiple incentive programs stacking
- High crime increase (any category >50% YoY)

**Changes:**
- **`backend/models.py`**: Add `opportunities: list[str]` and `constraints: list[str]` to `ReportData` (default_factory=list)
- **`backend/main.py`**: New `_synthesize_opportunities_constraints(report_data) -> tuple[list[str], list[str]]` — ~12 deterministic `if` rules
- **`backend/main.py`** (`_fetch_report_data`): Call after all data assembled
- **`backend/templates/zoning_report.html`**: In Executive Summary after Development Potential box (~line 501), add bullet lists with up/down arrows

## Implementation Order

**Phase 1** — Items 1, 5, 6, 7 (quick wins: template + minor backend enrichment, building characteristics audit)
**Phase 2** — Items 2, 3 (parcel map + ownership intelligence: new matplotlib function, dimension computation, ownership signal derivation)
**Phase 3** — Item 4 (systematic audit of all data sources for hidden value)
**Phase 4** — Item 8 (synthesis layer, only after objective data is fully surfaced)

Each phase ends with `mock=true` report generation and visual verification.

## Page Budget

| Item | Est. pages | Location |
|------|-----------|----------|
| 1. Nearby dev table | +0.5-0.75 | Market Context |
| 2. Parcel map + zoning context | +0.5-0.75 | Property |
| 3. Ownership signals | +0.2-0.3 | Property |
| 4. Existing data audit | +0.2-0.5 | Various |
| 5. Building chars | +0 (4 lines) | Property |
| 6. Assessment trend | +0 (2 lines) | Property |
| 7. Tax breakdown | +0.2 | Financial |
| 8. Opportunities/constraints | +0.3 | Executive Summary |
| **Total** | **+2.0-2.8** | **→ ~16-17 pages** |

No new top-level sections. No new page breaks. All additions go within existing sections.

## Key Data Sources Already Available (Not Currently Surfaced)

| Data | Source | Model Field | Currently Used |
|------|--------|-------------|---------------|
| Parcel polygon | Cook County GIS MapServer | `PropertySummary.parcel_geometry` | No |
| Nearby project details | Building Permits (ydr8-5enu) | `NearbyDevelopment.recent_projects` | Counts only |
| Assessment history | CCAO Assessments (uzyt-m557) | `PropertySummary.assessment_history` | Raw table only |
| Tax line items | PTAXSIM SQLite | `PropertySummary.tax_breakdown` | Total only |
| Sales history signals | CCAO Sales (wvhk-k5uv) | `PropertySummary.sales_history` | Raw table only |
| Building characteristics | CCAO Characteristics (x54s-btds) | Response has all fields | 10 of 100+ extracted |
| Adjacent zoning | Zoning API responses | Potentially available | Not investigated |
| Mailing address | CCAO/assessor records | Potentially available | Not investigated |

## What We Cannot Do (Data Limitations)

- **Taxpayer/owner names**: CAPTCHA-protected, not in open data. Requires paid service (Chicago Cityscape, Regrid). Documented in `core/data-sources.md`.
- **Deed recording details**: Cook County Recorder web-only, no API.
- **Unit count estimates**: Require assumptions about floor plans — excluded per user requirements against speculative estimates.

## Critical Files

- `backend/main.py` — enrichment logic, map generation, synthesis functions, mock overrides
- `backend/templates/zoning_report.html` — all template additions
- `backend/models.py` — new fields on ReportData and PropertySummary
- `backend/retrieval/property/__init__.py` — extract additional CCAO characteristic fields

## Verification

1. `python -m pytest backend/tests/ -q` — no regressions
2. Generate mock report: `curl -o /tmp/report-v4.pdf "http://localhost:8001/api/report?address=2400+N+Milwaukee+Ave&mock=true" -H "Cookie: session=dev"` (requires `VITE_MAPBOX_TOKEN` in env)
3. Visually verify: nearby dev table with distance/cost/description, parcel map with polygon + dimensions + zoning annotations, ownership signals after sales history, assessment trend after assessment table, tax breakdown in financial, building characteristics in property grid
4. Generate real report (no mock) to verify parcel geometry renders, real projects have distance, real assessments produce trend
5. Audit pass: compare raw API responses against extracted fields to identify remaining hidden value
