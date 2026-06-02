# UrbanLayer Chicago — Expansion Implementation Plan

## Context

UrbanLayer is a RAG-powered urban intelligence platform for Chicago that currently combines live Socrata data (crime, 311, permits, violations, business licenses), semantic search over the full Chicago Municipal Code (Qdrant), zoning lookups (ArcGIS), interactive mapping (Mapbox + deck.gl), and LLM synthesis (Claude). The platform answers natural-language questions about Chicago neighborhoods, regulations, and public records.

This plan expands UrbanLayer into a comprehensive development, zoning, permitting, site-selection, due-diligence, and business-launch intelligence platform. The expansion adds parcel-level property data, regulatory overlay analysis, incentive zone detection, demographic context, transit access scoring, and environmental constraint identification — enabling workflows like "Can I build here?", "Should I buy this property?", and "Can I open a business here?"

The key discovery from research: **Chicago's existing Zoning MapServer contains 26 layers** covering planned developments, landmarks, historic districts, FEMA floodplain, TOD boundaries, pedestrian streets, ADU areas, ARO zones, and SSAs — all queryable with the same ArcGIS REST pattern UrbanLayer already uses for zoning. Combined with Cook County's comprehensive open data portal (Socrata API, same technology as the Chicago Data Portal), roughly 80% of the needed integrations use patterns already present in the codebase.

---

## 1. Executive Summary

### What We're Adding

| Domain | Key Capability | Primary Sources | Auth Required |
|--------|---------------|-----------------|---------------|
| **Property** | Parcel lookup, characteristics, assessments, sales, tax estimation | Cook County GIS + CCAO Socrata + PTAXSIM | None (free) |
| **Regulatory** | 12+ overlay districts, flood zones, brownfields, landmarks | Chicago Zoning MapServer layers 2-26 + FEMA + EPA | None (free) |
| **Incentives** | TIF, Opportunity Zones, Enterprise Zones, tax incentive classes | Chicago Data Portal + HUD + CDFI | None (free) |
| **Neighborhood** | Demographics, transit access, TOD eligibility | Census API + GTFS + MapServer | Census API key (free) |
| **Development** | Pipeline intelligence, ARO requirements | Existing permits + new overlay data | None |

### Scale of Effort

- **New retrieval modules:** ~15-18
- **New API integrations:** ~12 distinct services
- **Estimated total implementation:** 6-8 weeks for a single engineer
- **Incremental cost per query:** ~$0.006-0.009 additional (more context tokens to LLM)
- **Latency impact:** +500-800ms retrieval (masked by parallel execution)

### What's NOT Feasible via Free APIs

- **Property ownership/taxpayer names** — Not in any free API. Assessor website is CAPTCHA-protected. Requires paid service (Chicago Cityscape, Regrid) or manual scraping.
- **Planned development applications** — No public dataset. Plan Commission agendas are PDF-only.
- **Illinois Secretary of State business entity search** — No API. Web-only with scraping prohibition.
- **Detailed deed/recording documents** — Cook County Clerk search is web-only, no API.

---

## 2. Ranked Integration Opportunities

Priority is based on: user value (how often someone would need this), data quality, implementation difficulty, and synergy with existing features.

### Tier 1: Core (Must Have) — Weeks 1-4

| # | Integration | Value | Difficulty | Why Core |
|---|------------|-------|------------|----------|
| 1 | Cook County GIS Parcel Lookup | Critical | Low | Unlocks PIN, which keys all property data. Same ArcGIS REST pattern as existing zoning.py |
| 2 | Zoning MapServer Layers 2-26 | Critical | Low | 12 overlay layers via identical endpoint pattern. Answers "what restrictions apply?" |
| 3 | CCAO Property Characteristics | High | Low | Lot size, building area, stories — essential for feasibility. Socrata API, same as existing integrations |
| 4 | CCAO Assessed Values | High | Low | Assessment history, property class — essential for due diligence |
| 5 | CCAO Parcel Sales | High | Low | Sale history — essential for due diligence |
| 6 | TIF Districts | High | Low | Boundaries on Chicago Data Portal (Socrata). TIF financials available. Answers "what incentives exist?" |
| 7 | FEMA Flood Zones | High | Low | Direct ArcGIS REST query. Critical risk factor for any property analysis |
| 8 | Census/ACS Demographics | High | Medium | Free API with key. Pre-aggregated community area data already on Chicago Data Portal |

### Tier 2: High Value (Should Have) — Weeks 4-6

| # | Integration | Value | Difficulty | Why Tier 2 |
|---|------------|-------|------------|------------|
| 9 | Opportunity Zones | Medium-High | Medium | Requires census tract resolution step. Static data (designations fixed) |
| 10 | Enterprise Zones | Medium | Low | Simple spatial query on Chicago Data Portal |
| 11 | CTA/Metra Station Proximity | Medium-High | Medium | GTFS parsing + spatial index. Enables TOD eligibility |
| 12 | EPA Brownfields | Medium | Low | ArcGIS REST query. Environmental risk factor |
| 13 | PTAXSIM Tax Estimation | High | Medium | Downloadable SQLite DB. Complex but high value for due diligence |

### Tier 3: Enhancement (Nice to Have) — Weeks 6-8+

| # | Integration | Value | Difficulty | Notes |
|---|------------|-------|------------|-------|
| 14 | Cook County Tax Incentive Classes (6b, 7a, etc.) | Medium | Low | Query CCAO by PIN for property class |
| 15 | SBIF Projects | Low-Medium | Low | Historical grant data, Socrata |
| 16 | Neighborhood Opportunity Fund | Low-Medium | Low | Grant data, Socrata |
| 17 | ARO Housing Data | Low-Medium | Low | Affordable housing datasets |
| 18 | Food Inspections | Low | Low | Useful for restaurant/food business queries |
| 19 | Vacant Buildings | Low-Medium | Low | Investment opportunity signal |
| 20 | Illinois Professional Licenses | Low | Medium | Different Socrata portal (data.illinois.gov) |

---

## 3. Dataset Inventory

### Cook County Open Data Portal (`datacatalog.cookcountyil.gov`)

All datasets use Socrata SODA 2.1 API. Base endpoint: `https://datacatalog.cookcountyil.gov/resource/{ID}.json`

| Dataset | ID | Key Fields | Update Freq | Join Key |
|---------|-----|-----------|-------------|----------|
| Parcel Universe (Current) | `pabr-t5kh` | pin, class, township, lat, lon, spatial attributes | Monthly | PIN |
| Parcel Universe (Historical) | `nj4t-kc8j` | pin, tax_year, class, township | Annually | PIN + year |
| Assessed Values | `uzyt-m557` | pin, tax_year, mailed_tot, certified_tot, board_tot | Monthly | PIN + year |
| Parcel Sales | `wvhk-k5uv` | pin, sale_date, sale_price, deed_type, sale_validity | Monthly | PIN |
| Single/Multi-Family Characteristics | `x54s-btds` | pin, char_bldg_sf, char_land_sf, char_rooms, char_fbath, char_age | Monthly | PIN |
| Condo Characteristics | `3r7i-mrz4` | pin, char_bldg_sf, char_rooms, char_fbath | Monthly | PIN |
| Parcel Addresses | `3723-97qp` | pin, addr, city, zip | Monthly | PIN |
| Appeals | `y282-6ig3` | pin, tax_year, case_no, result | Monthly | PIN + year |
| Tax-Exempt Parcels | `vgzx-68gb` | pin, exemption_type, tax_year | Monthly | PIN |
| Annual Tax Sale (delinquencies) | `55ju-2fs9` | pin, tax_year, amount | Annually | PIN |
| Commercial Valuation | `csik-bsws` | pin, market_value, income_approach | Annually | PIN |

**Auth:** Free. App token recommended via `X-App-Token` header for higher rate limits (~1,000 req/hour guaranteed).

**Rate limits:** Shared IP pool throttled without token. With token, effectively unlimited for normal use.

**Max records per query:** 50,000 (via `$limit` parameter).

### Chicago Data Portal (`data.cityofchicago.org`)

Same Socrata SODA 2.1 API. Base endpoint: `https://data.cityofchicago.org/resource/{ID}.json`

| Dataset | ID | Category | Key Fields | Join Key |
|---------|-----|----------|-----------|----------|
| TIF District Boundaries | `eejr-xtfb` | Geographic | geometry (multipolygon), tif_name | Spatial |
| Inactive TIF Districts | `5eit-itsp` | Geographic | geometry, tif_name | Spatial |
| TIF Projects (Annual Report) | `72uz-ikdv` | Financial | tif_name, year, revenue, expenditure | TIF name + year |
| TIF Itemized Expenditures | `umwj-yc4m` | Financial | tif_name, year, description, amount | TIF name + year |
| Enterprise Zone Boundaries | `64xf-pyvh` | Geographic | geometry, zone_name | Spatial |
| Zoning Districts (current) | `dj47-wfun` | Geographic | geometry, zone_class, zone_type | Spatial |
| Landmark Districts | `zidz-sdfj` | Historic | district_name, landmark_date | Name |
| Individual Landmarks | `uct4-hrvh` | Historic | landmark_name, address, date_built | Address |
| NRHP Listings | `yw5d-szpx` | Historic | name, address, date_listed | Address |
| ACS 5-Year by Community Area | `t68z-cikk` | Demographics | community_area, population, income, etc. | Community Area # |
| Community Area Boundaries | `igwz-8jzy` | Geographic | geometry, area_numbe | Community Area # |
| Census Tracts 2020 | `4hp8-2i8z` | Geographic | geometry, tractce20, geoid20 | Tract FIPS |
| Industrial Corridors | `e6xh-nr8w` | Geographic | geometry, corridor_name | Spatial |
| Pedestrian Streets | `w3m8-5y6d` | Zoning | geometry, street_name | Spatial |
| SSA Boundaries | `2k7v-9xvk` | Geographic | geometry, ssa_number, ssa_name | Spatial |
| SBIF Projects | `etqr-sz5x` | Incentives | address, amount, status | Address |
| NOF Large Grants | `j7ew-b73u` | Incentives | address, amount, status | Address |
| NOF Small Grants | `rym7-49n8` | Incentives | address, amount, status | Address |
| ARO Rentals | `wyrz-5mk7` | Housing | address, units, compliance | Address |
| Affordable Housing | `b4ex-5mdc` | Housing | address, units, type | Address |
| City-Owned Land | `aksk-kvfp` | Property | pin, address, sq_ft, ward | PIN |
| Vacant Buildings | `kc9i-wq85` | Property | address, date_reported | Address |
| Food Inspections | `4ijn-s7e5` | Business | license_number, facility_name, results | License # |
| Ward Boundaries (2023+) | `p293-wvbd` | Geographic | geometry, ward | Spatial |
| Building Code Scofflaw List | `crg5-4zyp` | Violations | address, owner_name | Address |

### Census Bureau API (`api.census.gov`)

**Endpoint:** `https://api.census.gov/data/{year}/acs/acs5`

**Auth:** Free API key required. Register at `census.gov/data/developers/api-key.html`. Without key: 500 queries/day. With key: substantially higher.

**Key Variables:**

| Variable | Description |
|----------|-------------|
| B01003_001E | Total Population |
| B19013_001E | Median Household Income |
| B25001_001E | Total Housing Units |
| B25077_001E | Median Home Value |
| B25064_001E | Median Gross Rent |
| B25003_002E | Owner-Occupied Units |
| B25003_003E | Renter-Occupied Units |
| B15003_022E | Bachelor's Degree holders |
| B23025_005E | Unemployed |
| B25002_003E | Vacant Housing Units |
| B01002_001E | Median Age |
| B17001_002E | Below Poverty Level |

**Example query (all tracts in Cook County):**
```
https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E,B19013_001E,B25077_001E&for=tract:*&in=state:17%20county:031&key=YOUR_KEY
```

**Geographies:** tract, block group, county, place, PUMA. Chicago = place `1714000`.

### PTAXSIM (Downloadable SQLite)

**Download:** `https://ccao-data-public-us-east-1.s3.amazonaws.com/ptaxsim/ptaxsim-2024.0.0.db.bz2`

**Contents:** Cleaned data from Cook County Clerk, Treasurer, and Assessor. Contains tax extensions, rates, agency information, PIN-level assessments and exemptions, equalization factors, TIF information.

**Usage:** `tax_bill(year, pin)` → line-item tax amounts by taxing district.

**Update:** Annual release (typically Q1).

### Illinois State Data

| Dataset | Portal | ID | Notes |
|---------|--------|-----|-------|
| Professional Licenses | data.illinois.gov | `pzzh-kp68` | ~1.2M records, 100+ license types, daily refresh |

---

## 4. API Inventory

### ArcGIS REST Services (No Auth)

All follow the same query pattern:
```
{base_url}/{layer_id}/query?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
```

| Service | Base URL | Auth | Rate Limit | Notes |
|---------|----------|------|-----------|-------|
| Chicago Zoning MapServer | `gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer` | None | None documented | 26 layers, UrbanLayer already uses layer 1 |
| Chicago DPD FeatureServer | `gisapps.chicago.gov/arcgis/rest/services/ExternalApps/dpd/FeatureServer` | None | None documented | TIF, SBIF, workforce, planning regions |
| Cook County GIS Parcels | `gis.cookcountyil.gov/traditional/rest/services/cookVwrDynmc/MapServer` | None | Max 2,000 records/query | Layer 44 = current parcels |
| Cook County Historical Parcels | `gis.cookcountyil.gov/traditional/rest/services/parcelHistorical/MapServer` | None | Max 2,000/query | Layers 0-25 (years 2000-2025) |
| Cook County Enhanced Parcels | `gis.cookcountyil.gov/hosting/rest/services/Hosted/Parcel_2022/FeatureServer/0` | None | Unknown | Enriched with political districts, TIF, school |
| FEMA NFHL | `hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer` | None | None documented | Layer 28 = Flood Hazard Zones |
| EPA Facilities | `geopub.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer` | None | 10,000 records max | Layer 5 = Brownfields. Also: Superfund (0), TRI (1), RCRA (4) |
| NPS Historic Places | `mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer` | None | None documented | National Register points and polygons |
| HUD Opportunity Zones | `services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Opportunity_Zones/FeatureServer/0` | None | ArcGIS Online limits | Federal QOZ boundaries by census tract |
| Census TIGERweb | `tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer` | None | 100,000 records max | Layer 4 = Census Tracts |
| FWS Wetlands | `fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer` | None | None documented | National Wetlands Inventory |

### Socrata SODA APIs (Free, App Token Recommended)

Three portals, same API pattern: `https://{domain}/resource/{dataset_id}.json?$where=...&$limit=N`

| Portal | Domain | App Token Source |
|--------|--------|-----------------|
| Chicago Data Portal | data.cityofchicago.org | Already configured (SOCRATA_APP_TOKEN) |
| Cook County Open Data | datacatalog.cookcountyil.gov | Same token format, register separately |
| Illinois Open Data | data.illinois.gov | Same token format |

### Other APIs

| API | Endpoint | Auth | Notes |
|-----|----------|------|-------|
| Census ACS | `api.census.gov/data/{year}/acs/acs5` | Free API key | 500 req/day without key |
| Census Geocoder | `geocoding.geo.census.gov/geocoder/geographies/address` | None | Returns tract FIPS. Already used for address geocoding |
| FCC Census Block | `geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json` | None | Fast lat/lon → tract/block resolution (~100ms) |
| CTA GTFS (static) | `transitchicago.com/downloads/sch_data/google_transit.zip` | None | Static schedule data including stops.txt |
| Metra GTFS (static) | `schedules.metrarail.com/gtfs/schedule.zip` | None | Includes station locations |
| Pace GTFS (static) | `pacebus.com/gtfs/gtfs.zip` | None | Non-commercial use only |
| CTA Train Tracker | `lapi.transitchicago.com/api/1.1/ttarrivals.aspx` | Free API key | Real-time arrivals, 100K req/day |
| Divvy GBFS | `gbfs.divvybikes.com/gbfs/gbfs.json` | None | Real-time station/bike data |
| **Walk Score API** | **`api.walkscore.com/score?format=json&lat=...&lon=...&transit=1&bike=1&wsapikey=...`** | **API key (free tier)** | **✅ INTEGRATED — Walk/Transit/Bike scores (0-100). 5,000 calls/day. 48h TTL cache. Requires address + lat/lon. Server-side only.** |

---

## 5. GIS Layer Inventory

### Chicago Zoning MapServer — Complete Layer Map

**Base:** `https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer`

| Layer | Name | Use in UrbanLayer | Priority |
|-------|------|-------------------|----------|
| 0 | Zoning Districts (simple) | Already use layer 1 instead | Skip |
| **1** | **Zoning Districts (detailed)** | **Already integrated** | Existing |
| **2** | **Planned Developments** | PD restrictions, overrides base zoning | Core |
| **3** | **Lakefront Protection** | Additional review requirements | Core |
| **4** | **Pedestrian Streets** | Facade/signage requirements for retail | Core |
| **5** | **Landmark Boundaries** | Permit review restrictions | Core |
| **6** | **Historic Districts** | Demolition/alteration restrictions | Core |
| **7** | **Landmark Buildings** | Individual building protection | Core |
| **8** | **National Register** | Federal historic tax credit eligibility | Core |
| **9** | **Special Districts** | PMDs, special zoning overlays | Core |
| 10 | Downtown Zoning District | Downtown boundary reference | Optional |
| **11** | **FEMA Floodplain** | Flood risk (local copy) | Core |
| **12** | **PMD SubAreas** | Planned Manufacturing District subareas | Core |
| **13** | **TSL/CTA Stations** | Pre-computed TOD boundaries | Core |
| 14 | TSL Bus Routes | Transit service level routes | Optional |
| 15 | City Boundary | Reference | Skip |
| 16 | Community Areas | Already have from geo.py | Skip |
| **17** | **ADU Areas** | Accessory Dwelling Unit eligibility | Core |
| 18 | Ward Boundaries | Political context | Optional |
| 19 | Downtown Exclusion | Where certain rules don't apply | Optional |
| **20** | **ARO Zones** | Affordable Requirements Ordinance applicability | Core |
| 21 | Empowerment Zones | Economic development overlay | Optional |
| 22 | Reserved | — | Skip |
| **23** | **SSAs (Special Service Areas)** | Business improvement districts | Core |
| **24** | **TSL Metra Stations** | Pre-computed Metra TOD boundaries | Core |
| 25 | Lake Michigan | Reference | Skip |

**Query pattern (identical for all layers):**
```
GET {base}/query?where=1=1&geometry=-87.6298,41.8781&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
```

This is the exact same pattern as the existing `lookup_zoning()` in `backend/retrieval/zoning.py`.

### External GIS Layers

| Source | Layer | Endpoint | Key Fields |
|--------|-------|----------|-----------|
| Cook County Parcels | 44 | `gis.cookcountyil.gov/.../cookVwrDynmc/MapServer/44/query` | PIN14, BLDGClass, BldgSqft, LandSqft, TotalValue, Address, geometry |
| FEMA Flood Zones | 28 | `hazards.fema.gov/.../NFHL/MapServer/28/query` | FLD_ZONE (A, AE, X, etc.), ZONE_SUBTY, SFHA_TF, STATIC_BFE |
| EPA Brownfields | 5 | `geopub.epa.gov/.../FRS_INTERESTS/MapServer/5/query` | SITE_NAME, EPA_ID, CLEANUP_STATUS |
| EPA Superfund | 0 | Same base as EPA Brownfields | SITE_NAME, NPL_STATUS |
| HUD Opportunity Zones | 0 | `services.arcgis.com/.../Opportunity_Zones/FeatureServer/0/query` | GEOID, DESIGNATED, geometry |
| NPS Historic Places | Points | `mapservices.nps.gov/.../nrhp_locations/MapServer` | RESNAME, ADDRESS, NRIS_Refnum |

---

## 6. Data Model Recommendations

### Domain Model

Organize new data into five domains based on **data dependency chains** (not conceptual themes). This determines orchestration:

```
Property Domain (keyed on PIN, sequential then parallel)
  └─ Address → lat/lon → Parcel GIS → PIN → [Characteristics, Assessments, Sales, Tax] in parallel

Regulatory Domain (keyed on lat/lon, fully parallel)
  └─ lat/lon → [Layers 1-26 + FEMA + EPA + NPS] all in parallel

Incentives Domain (keyed on lat/lon + census tract, mostly parallel)
  └─ lat/lon → [TIF boundary, Enterprise Zone] in parallel
  └─ census tract → [Opportunity Zone]
  └─ TIF ID (if hit) → TIF financials (sequential)

Neighborhood Domain (keyed on community area + lat/lon + address)
  └─ community area → [Demographics] 
  └─ lat/lon → [Transit proximity]
  └─ lat/lon + address → [Walk Score API] (walk/transit/bike scores)

Development Domain (existing, keyed on community area)
  └─ community area → [Permits, Violations, Business Licenses]
  └─ search query → [Vector Search]
```

### New Pydantic Models

Add to `backend/models.py`:

```python
# --- Property Domain ---
class PropertySummary(BaseModel):
    pin14: str | None = None
    address: str | None = None
    bldg_class: str | None = None
    bldg_class_description: str | None = None
    bldg_sqft: int | None = None
    land_sqft: int | None = None
    stories: int | None = None
    units: int | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    bldg_age: int | None = None
    total_assessed_value: float | None = None
    assessment_history: list[dict] = []   # [{year, land, bldg, total}]
    sales_history: list[dict] = []         # [{date, price, deed_type}]
    estimated_annual_tax: float | None = None
    tax_code: str | None = None
    parcel_geometry: dict | None = None    # GeoJSON polygon for map

# --- Regulatory Domain ---
class OverlayDistrict(BaseModel):
    layer_type: str       # "planned_development", "landmark", "historic_district", etc.
    name: str | None = None
    ordinance: str | None = None
    description: str | None = None

class RegulatorySummary(BaseModel):
    zoning: ZoningSummary | None = None    # existing model
    overlays: list[OverlayDistrict] = []
    in_planned_development: bool = False
    in_landmark_district: bool = False
    is_landmark_building: bool = False
    in_historic_district: bool = False
    on_national_register: bool = False
    in_lakefront_protection: bool = False
    on_pedestrian_street: bool = False
    in_pmd: bool = False
    in_adu_area: bool = False
    in_aro_zone: bool = False
    flood_zone: str | None = None          # FEMA zone (A, AE, X, etc.)
    flood_zone_description: str | None = None
    in_special_flood_hazard: bool = False
    brownfield_sites: list[dict] = []      # nearby EPA sites
    in_ssa: str | None = None              # SSA name if applicable

# --- Incentives Domain ---
class IncentivesSummary(BaseModel):
    in_tif_district: bool = False
    tif_name: str | None = None
    tif_end_year: int | None = None
    tif_total_revenue: float | None = None
    tif_available_balance: float | None = None
    in_opportunity_zone: bool = False
    oz_tract: str | None = None
    in_enterprise_zone: bool = False
    enterprise_zone_name: str | None = None
    property_tax_incentive_class: str | None = None  # 6b, 7a, 7b, 8

# --- Neighborhood Domain ---
class DemographicsSummary(BaseModel):
    population: int | None = None
    median_household_income: int | None = None
    median_home_value: int | None = None
    median_gross_rent: int | None = None
    median_age: float | None = None
    poverty_rate: float | None = None
    unemployment_rate: float | None = None
    owner_occupied_pct: float | None = None
    bachelors_degree_pct: float | None = None
    vacancy_rate: float | None = None

class TransitAccess(BaseModel):
    nearest_cta_rail: str | None = None
    cta_rail_distance_mi: float | None = None
    cta_lines: list[str] = []
    nearest_metra: str | None = None
    metra_distance_mi: float | None = None
    metra_line: str | None = None
    tod_eligible: bool = False
    tod_type: str | None = None   # "CTA rail", "Metra", "high-frequency bus"

# --- Walk Score (INTEGRATED) ---
class WalkScoreSummary(BaseModel):
    walk_score: int | None = None          # 0-100
    walk_description: str | None = None    # e.g. "Very Walkable"
    transit_score: int | None = None       # 0-100
    transit_description: str | None = None # e.g. "Excellent Transit"
    bike_score: int | None = None          # 0-100
    bike_description: str | None = None    # e.g. "Very Bikeable"
    ws_link: str | None = None             # property page URL (attribution)

# --- Expanded ContextObject ---
# Add optional fields to existing ContextObject:
#   property: PropertySummary | None = None
#   regulatory: RegulatorySummary | None = None
#   incentives: IncentivesSummary | None = None
#   demographics: DemographicsSummary | None = None
#   transit: TransitAccess | None = None
#   walkscore: WalkScoreSummary | None = None  # ✅ INTEGRATED
```

### PIN System

The **Property Index Number (PIN)** is the universal join key for all Cook County property data:

- Format: `TT-SS-BBB-PPP-UUUU` (14 digits)
  - TT = Township, SS = Section, BBB = Block, PPP = Parcel, UUUU = Unit (0000 = non-condo)
- 10-digit PIN (first 10) identifies the land parcel
- 14-digit PIN identifies a specific unit (condos)
- Always zero-pad to 14 digits when querying APIs
- Obtained via Cook County GIS spatial query (lat/lon → parcel → PIN14)

### Joins and Relationships

```
Address → Census Geocoder → (lat, lon)
  ├── (lat, lon) → Cook County GIS → PIN14 → CCAO Socrata datasets
  ├── (lat, lon) → Zoning MapServer → overlays, restrictions
  ├── (lat, lon) → FEMA/EPA ArcGIS → environmental constraints
  ├── (lat, lon) → TIF/Enterprise Zone boundaries → incentive eligibility
  ├── (lat, lon) → FCC API → Census Tract → OZ lookup, ACS demographics
  └── Community Area (existing) → Socrata sources (crime, 311, permits, etc.)
```

---

## 7. Workflow Recommendations

### A) Site Due Diligence — "I'm considering buying 1234 N Western Ave"

**Router emits:** `sources: [property_domain, regulatory_domain, incentives_domain, crime_api, 311_api, permits_api, violations_api, business_api], workflow_hint: site_due_diligence`

**Retrieval sequence (all domains run in parallel):**

```
┌─ property_domain ──────────────────────────────────────┐
│  1. Parcel GIS lookup (lat,lon) → PIN14                │  ~300ms
│  2. Parallel:                                           │
│     ├─ CCAO Characteristics (PIN)                      │  ~200ms
│     ├─ CCAO Assessments, 5 years (PIN)                 │  ~200ms
│     ├─ CCAO Sales history (PIN)                        │  ~200ms
│     └─ PTAXSIM tax estimate (PIN)                      │  ~50ms (local)
│  Total: ~500ms (300 sequential + 200 parallel)         │
└────────────────────────────────────────────────────────┘

┌─ regulatory_domain ────────────────────────────────────┐
│  All in parallel:                                       │
│  ├─ Zoning layer 1 (existing)                          │
│  ├─ Planned Development (layer 2)                      │
│  ├─ Lakefront Protection (layer 3)                     │
│  ├─ Landmark/Historic (layers 5-8)                     │
│  ├─ Flood zone (layer 11 or FEMA direct)               │
│  ├─ ADU area (layer 17)                                │
│  ├─ ARO zone (layer 20)                                │
│  ├─ SSA (layer 23)                                     │
│  └─ EPA brownfields (spatial)                          │
│  Total: ~400ms (all parallel)                          │
└────────────────────────────────────────────────────────┘

┌─ incentives_domain ────────────────────────────────────┐
│  Parallel:                                              │
│  ├─ TIF boundary query                                 │  ~200ms
│  ├─ Enterprise Zone query                              │  ~200ms
│  └─ OZ lookup (tract → CDFI list)                      │  ~200ms
│  If TIF hit: TIF financials (sequential)               │  +200ms
│  Total: ~200-400ms                                     │
└────────────────────────────────────────────────────────┘

┌─ existing sources (unchanged, in parallel) ────────────┐
│  ├─ Crime by community area                            │
│  ├─ 311 by community area                              │
│  ├─ Permits by community area                          │
│  ├─ Violations by community area                       │
│  └─ Business licenses by community area                │
│  Total: ~800ms (existing latency)                      │
└────────────────────────────────────────────────────────┘
```

**Expected output sections:**
1. Property overview (address, PIN, lot size, building, assessed value, last sale)
2. Tax estimate (annual amount, rate, key taxing districts)
3. Zoning and regulatory status (base zone, all overlays, restrictions)
4. Risk factors (flood zone, brownfield proximity, landmark restrictions)
5. Incentive eligibility (TIF, OZ, Enterprise Zone)
6. Neighborhood context (crime trends, 311 issues, development activity)

### B) Development Feasibility — "Can I build a 6-unit building here?"

**Router emits:** `sources: [property_domain, regulatory_domain, vector_search, permits_api], workflow_hint: development_feasibility, search_query: "RM residential multi-unit FAR height setback lot coverage parking"`

**Key data requirements:**
- Lot dimensions from CCAO characteristics (to calculate max buildable area)
- Base zoning class from layer 1 (determines FAR, height, setbacks)
- All overlays that modify development rights (PD, landmark, ADU, ARO, lakefront, TOD)
- Municipal Code sections on applicable bulk/density standards (vector search)
- Recent comparable permits nearby (development activity signals)

**Computational steps (post-retrieval, in assembler):**
- If lot size and FAR known: calculate max floor area = lot_sqft × FAR
- If max floor area and unit count known: calculate avg unit size
- Flag if in ARO zone (affordable unit requirements apply)
- Flag if in TOD area (parking reductions may apply)
- Flag if landmark/historic (additional review required)

**Synthesis focus:** Lead with zoning classification and what it allows. State maximum FAR, height, setbacks for the district. List every applicable overlay and its impact. Reference specific Municipal Code sections. Compare requested units to what zoning permits.

### C) Business Launch — "Can I open a coffee shop here?"

**Router emits:** `sources: [regulatory_domain, vector_search, business_api, incentives_domain], workflow_hint: business_launch, search_query: "retail food establishment allowed uses commercial district food service license requirements"`

**Key data requirements:**
- Zoning class (is retail food a permitted use in this district?)
- Pedestrian street status (signage/facade requirements)
- SSA membership (potential business improvement district resources)
- Municipal Code on licensing, health requirements, signage
- Nearby businesses (competition and character analysis)
- Incentive eligibility (TIF grants, Enterprise Zone tax breaks)

**Synthesis focus:** Lead with whether the use is permitted. List required licenses and permits. Note any special requirements from overlays. Mention incentive programs. Provide nearby business context.

### D) Property Intelligence — "Tell me everything about this parcel"

**Router emits:** `sources: [property_domain, regulatory_domain, incentives_domain, permits_api, violations_api], workflow_hint: property_intelligence`

**Deep property focus:** Full assessment history (5+ years), all sales, complete tax estimate with district breakdown, all regulatory overlays, all applicable incentives, permits and violations at this specific address (not community area).

### E) Neighborhood Intelligence — "What's happening around this address?"

**Router emits:** `sources: [crime_api, 311_api, permits_api, violations_api, business_api, neighborhood_domain], workflow_hint: general, intent: neighborhood_overview`

**Same as existing behavior plus:** Demographics (population, income, age distribution) and transit access (nearest stations, TOD eligibility). The demographic data provides baseline context for interpreting activity data.

---

## 8. Architecture Recommendations

### Retrieval Architecture Evolution

**Recommendation: Hybrid domain-based routing with workflow hints.**

Current state: Router selects from 6 flat source tags → parallel asyncio.gather.

New state: Router selects from 6 existing tags + 4 new domain tags → parallel asyncio.gather. Each domain tag triggers a domain orchestrator that handles internal dependency chains.

**Expanded SourceTag:**
```python
SourceTag = Literal[
    # Existing (unchanged)
    "crime_api", "311_api", "permits_api", "violations_api", "business_api", "vector_search",
    # New domains
    "property_domain", "regulatory_domain", "incentives_domain", "neighborhood_domain",
]
```

**New WorkflowHint (added to RetrievalPlan):**
```python
WorkflowHint = Literal[
    "general",
    "site_due_diligence",
    "development_feasibility",
    "business_launch",
    "property_intelligence",
    "neighborhood_overview",
]
```

The workflow hint tells domain orchestrators how deep to go. Example: `property_domain` under `site_due_diligence` fetches everything (characteristics, assessments, sales, tax). Under `neighborhood_overview` it skips entirely. Under `development_feasibility` it fetches lot dimensions and current building but skips sales/tax.

**Why hybrid over alternatives:**
- **Flat expansion** (20+ source tags) would overwhelm the router LLM with fine-grained API selection decisions it shouldn't make
- **Pure workflow routing** is too rigid — "What TIF district is this in?" is a single-domain query, not a full workflow
- **Hybrid** lets the router make coarse-grained domain selections (easy for the LLM) while domain orchestrators handle the runtime details (dependency chains, conditional queries)

### Directory Structure

```
backend/retrieval/
  property/
    __init__.py          # property_domain() orchestrator
    parcels.py           # Cook County GIS parcel lookup
    characteristics.py   # CCAO characteristics by PIN
    assessments.py       # CCAO assessed values by PIN
    sales.py             # CCAO sales history by PIN
    tax_estimate.py      # PTAXSIM local DB query
  regulatory/
    __init__.py          # regulatory_domain() orchestrator
    overlays.py          # Zoning MapServer layers 2-26 (generalized)
    flood.py             # FEMA flood zones
    environmental.py     # EPA brownfields/superfund
  incentives/
    __init__.py          # incentives_domain() orchestrator
    tif.py               # TIF boundaries + financials
    opportunity_zones.py # OZ by census tract
    enterprise_zones.py  # EZ spatial query
  neighborhood/
    __init__.py          # neighborhood_domain() orchestrator
    demographics.py      # Census/ACS
    transit.py           # GTFS-based station proximity
    walkscore.py         # Walk Score API (walk/transit/bike scores) ✅
  # Existing modules stay in place (unchanged):
  crime.py, three11.py, buildings.py, business.py,
  geo.py, vector_search.py, zoning.py, socrata.py,
  utils.py, map_data.py
```

### Source Classification

| Source | Pattern | Cache Strategy |
|--------|---------|---------------|
| **First-class retrieval sources** (query per request) | Socrata API, ArcGIS REST | |
| Cook County GIS Parcels | ArcGIS REST spatial | TTL 1 hour (by rounded lat/lon) |
| CCAO Characteristics | Socrata by PIN | TTL 24 hours |
| CCAO Assessments | Socrata by PIN | TTL 24 hours |
| CCAO Sales | Socrata by PIN | TTL 24 hours |
| Zoning MapServer layers | ArcGIS REST spatial | TTL 1 hour |
| FEMA Flood | ArcGIS REST spatial | TTL 1 hour |
| EPA Brownfields | ArcGIS REST spatial | TTL 1 hour |
| TIF Boundaries | Socrata spatial (point-in-polygon) | TTL 24 hours |
| Enterprise Zones | Socrata spatial | TTL 24 hours |
| **Precomputed / startup-loaded** | | |
| Community area polygons | GeoJSON file | Already loaded at startup |
| CTA/Metra stations | GTFS stops.txt | Load at startup, refresh monthly |
| Census tract→CA crosswalk | Static table | Load at startup |
| **Local database** | | |
| PTAXSIM | SQLite (read-only) | Downloaded annually |
| ACS demographics by CA | Socrata prefetch | Refresh weekly in SQLite |
| **GIS overlay layers** (for map, not synthesis) | | |
| Parcel geometry | From parcel lookup response | Same as parcel lookup |
| TIF boundary polygons | Socrata GeoJSON | TTL 24 hours |
| Overlay district polygons | ArcGIS envelope query | TTL 1 hour |
| **Enrichment services** (optional secondary queries) | | |
| TIF financials | Socrata by TIF name | Only if parcel is in TIF |
| OZ lookup | Static list by tract | Only if tract resolved |
| Cook County tax incentive class | CCAO by PIN | Only for property_intelligence workflow |

### Caching Implementation

Add a simple TTL cache utility (used by all domain modules):

```python
# backend/retrieval/cache.py
class TTLCache:
    """In-memory TTL cache. Thread-safe for asyncio (single-threaded event loop)."""
    def __init__(self, ttl_seconds: int, maxsize: int = 2048): ...
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any) -> None: ...
```

Cache key strategy: `f"{source}:{round(lat,5)}:{round(lon,5)}"` for spatial queries, `f"{source}:{pin14}"` for PIN queries, `f"{source}:{tract_fips}"` for tract queries.

### Main Orchestration Change

The existing `_retrieve()` function in `main.py` (line ~323) creates tasks per source tag and gathers them. The expansion adds domain orchestrator tasks alongside:

```python
# In main.py _retrieve():
# ... existing source tasks unchanged ...

# New domain tasks (parallel with existing)
if "property_domain" in plan.sources and lat and lon:
    tasks["property"] = property_domain(lat, lon, workflow=plan.workflow_hint, client=client)
if "regulatory_domain" in plan.sources and lat and lon:
    tasks["regulatory"] = regulatory_domain(lat, lon, workflow=plan.workflow_hint, client=client)
if "incentives_domain" in plan.sources and lat and lon:
    tasks["incentives"] = incentives_domain(lat, lon, ca=ca, workflow=plan.workflow_hint, client=client)
if "neighborhood_domain" in plan.sources:
    tasks["neighborhood"] = neighborhood_domain(lat, lon, ca=ca, workflow=plan.workflow_hint, client=client)

# Gather all (domains + existing sources, fully parallel)
results = await asyncio.gather(*tasks.values(), return_exceptions=True)
```

### Synthesis Prompt Evolution

Add rules to `SYNTHESIZER_SYSTEM` in `prompts.py`:

1. When property data present: lead with address, PIN, zoning, lot size, building characteristics, assessed value, most recent sale price.
2. When regulatory overlays present: list each applicable overlay as a distinct item with its implications (e.g., "This parcel is in the Lincoln Park Landmark District — exterior alterations require Commission on Chicago Landmarks review").
3. When incentives present: state eligibility clearly with practical implications (e.g., "This parcel is within TIF District #44 (Elston/Armstrong, expires 2029) — TIF increment financing may be available for infrastructure improvements").
4. When flood zone present: state the FEMA zone designation and whether it's a Special Flood Hazard Area (mandatory flood insurance).
5. When demographics present: weave key statistics into context naturally, don't dump a table.
6. When transit access present: mention nearest station(s), walking distance, and TOD eligibility.

### Map Layer Integration

**Expand MapDataResponse** with optional fields for new layers:

```python
class MapDataResponse(BaseModel):
    # Existing (unchanged)
    crimes: list[dict] = []
    requests_311: list[dict] = []
    building_permits: list[dict] = []
    zoning: dict | None = None
    queried_address: dict | None = None
    capped: dict[str, bool] = {}
    
    # New contextual layers
    parcel_boundary: dict | None = None           # GeoJSON polygon
    overlay_districts: dict[str, dict] = {}       # layer_type → GeoJSON FeatureCollection
    incentive_zones: dict[str, dict] = {}         # zone_type → GeoJSON FeatureCollection
    transit_stations: list[dict] = []             # [{lat, lon, name, type, lines}]
```

**Frontend layer strategy:**
- Parcel boundary: thick blue outline, no fill (always shown when property domain active)
- Overlay districts: semi-transparent fills with distinct colors per type
- Incentive zones: dashed outlines (TIF = red, OZ = green, EZ = blue)
- Transit stations: star markers with line colors

### Frontend Type Expansion

Add TypeScript interfaces in `frontend/src/lib/types.ts` mirroring all new Pydantic models.

---

## 9. Implementation Roadmap

### Phase 1: Infrastructure Foundation (Week 1)

**Goal:** Set up domain structure, expand models, wire orchestration.

1. Add new models to `backend/models.py` (PropertySummary, RegulatorySummary, IncentivesSummary, DemographicsSummary, TransitAccess, OverlayDistrict, WorkflowHint)
2. Expand SourceTag with domain tags, add WorkflowHint to RetrievalPlan
3. Create directory structure: `backend/retrieval/{property,regulatory,incentives,neighborhood}/`
4. Add TTL cache utility (`backend/retrieval/cache.py`)
5. Expand ContextObject with optional domain summary fields
6. Update router prompt to emit domain tags and workflow hints
7. Wire domain orchestrator tasks into `_retrieve()` in `main.py`
8. Add Cook County Socrata app token to `.env` config
9. Add Census API key to `.env` config

**Key files:** `models.py`, `config.py`, `main.py`, `router.py`, `prompts.py`

### Phase 2: Property Domain (Week 2)

**Goal:** Parcel lookup, characteristics, assessments, sales.

1. `backend/retrieval/property/parcels.py` — Cook County GIS parcel lookup (ArcGIS REST, same pattern as existing `zoning.py`)
2. `backend/retrieval/property/characteristics.py` — CCAO characteristics by PIN (Socrata, same pattern as existing `business.py`)
3. `backend/retrieval/property/assessments.py` — CCAO assessed values by PIN, last 5 years
4. `backend/retrieval/property/sales.py` — CCAO sales history by PIN
5. `backend/retrieval/property/__init__.py` — Property domain orchestrator (parcel → PIN → parallel fan-out)
6. Update assembler to pass PropertySummary to context
7. Update synthesis prompt with property data rules
8. Tests for each module + orchestrator
9. Add TypeScript types for PropertySummary

**Reusable patterns:** `zoning.py` for ArcGIS REST queries, `socrata.py` for Socrata queries, `buildings.py` for PIN-based data retrieval.

### Phase 3: Regulatory Domain (Week 3)

**Goal:** All zoning overlays, flood zones, environmental constraints.

1. `backend/retrieval/regulatory/overlays.py` — Generalized Zoning MapServer query for layers 2-24. Single function: `query_overlay(lat, lon, layer_id, client)`. A dict maps layer IDs to names/descriptions.
2. `backend/retrieval/regulatory/flood.py` — FEMA NFHL query (ArcGIS REST, same pattern)
3. `backend/retrieval/regulatory/environmental.py` — EPA brownfields/superfund spatial query (ArcGIS REST)
4. `backend/retrieval/regulatory/__init__.py` — Regulatory domain orchestrator (all queries in parallel)
5. Move/refactor existing `zoning.py` lookup to live within regulatory domain (keep backward-compatible import path)
6. Update assembler and synthesis prompt
7. Tests
8. Frontend: add overlay GeoJSON layers to MapView

**Implementation note:** The overlay query function is a 1-line generalization of the existing `lookup_zoning()` — change the layer ID parameter. All 12+ overlay layers use identical endpoint pattern.

### Phase 4: Incentives Domain (Week 4)

**Goal:** TIF, Opportunity Zones, Enterprise Zones.

1. `backend/retrieval/incentives/tif.py`
   - TIF boundary check: download GeoJSON from Socrata (`eejr-xtfb`), cache at startup, point-in-polygon with Shapely (same pattern as community area resolution in `geo.py`)
   - TIF financials: Socrata query by TIF name (`72uz-ikdv`) — only if boundary check hits
2. `backend/retrieval/incentives/opportunity_zones.py`
   - Census tract resolution: FCC API (`geo.fcc.gov/api/census/area`) or extend existing Census Geocoder response parsing
   - OZ lookup: download CDFI Fund designated tract list, cache at startup, simple set membership check
3. `backend/retrieval/incentives/enterprise_zones.py`
   - Download GeoJSON from Socrata (`64xf-pyvh`), cache at startup, point-in-polygon
4. Orchestrator, assembler update, synthesis prompt, tests
5. Frontend: add incentive zone boundary layers to map

**Implementation note:** TIF, OZ, and Enterprise Zone boundaries change rarely. Cache boundary GeoJSON at startup and do client-side point-in-polygon (same pattern as community areas in `geo.py`). This avoids API calls entirely for boundary checks.

### Phase 5: Neighborhood Domain (Week 5)

**Goal:** Demographics, transit proximity, TOD eligibility, walkability scores.

1. `backend/retrieval/neighborhood/demographics.py`
   - Option A (simpler): Use pre-aggregated community area data from `data.cityofchicago.org/resource/t68z-cikk.json`. Prefetch at startup, store in cache. Query by community area number.
   - Option B (richer): Census API by tract. Requires tract resolution step.
   - **Recommend starting with Option A** (community area level), upgrade to Option B later.
2. `backend/retrieval/neighborhood/transit.py`
   - Parse CTA GTFS `stops.txt` at startup → in-memory list of (stop_name, lat, lon, type, routes)
   - Parse Metra GTFS `stops.txt` similarly
   - `nearest_stations(lat, lon, radius_mi=1.0)` → sorted by distance (haversine)
   - TOD eligibility: check if within TSL layers 13/24 from MapServer (simplest), OR calculate distance from CTA/Metra stations + apply Connected Communities Ordinance rules (½ mile rail, ¼ mile bus)
   - **Recommend using MapServer layers 13/24** for TOD — they contain pre-computed boundaries
3. ✅ **`backend/retrieval/neighborhood/walkscore.py`** — Walk Score API integration (DONE)
   - Single GET to `api.walkscore.com/score` with `transit=1&bike=1` returns Walk Score, Transit Score, and Bike Score (all 0-100)
   - API key: `WALKSCORE_API_KEY` env var, 5,000 calls/day limit
   - 48-hour TTL cache (walk scores change rarely), `_NOT_FOUND` sentinel for bad coordinates
   - Requires `address` parameter (threaded from `plan.location.resolved_address`)
   - Skipped when API key is empty or workflow is `property_intelligence`
   - Frontend: color-coded score bars in `NeighborhoodCard.tsx`, text "Walk Score®" attribution link
   - Synthesis prompt rule 18: weave scores naturally into walkability/livability discussion
4. Orchestrator, assembler, synthesis prompt, tests
5. Frontend: add transit station markers to map

### Phase 6: Frontend Integration (Week 6)

**Goal:** Display all new data in sidebar and map.

1. Expand `types.ts` with all new domain interfaces
2. Add property card component to DataView (parcel info, assessment history, sales, tax)
3. Add regulatory overlay visualization (list of applicable overlays with descriptions)
4. Add incentives card (TIF, OZ, EZ status with descriptions)
5. Add demographics card (key stats in a compact format)
6. Add transit access card (nearest stations, TOD status)
7. Expand `MapView.tsx`:
   - Parcel boundary GeoJsonLayer
   - Overlay district GeoJsonLayers (color-coded by type)
   - Incentive zone boundary layers
   - Transit station ScatterplotLayer
   - Dynamic toggle generation based on available layers
8. Update `MapLayerToggles.tsx` for new layer types
9. Update SSE event handling in `useChat.ts` for expanded context/map data

### Phase 7: Polish and Optimization (Weeks 7-8)

1. **PTAXSIM integration** — Download SQLite DB, mount read-only alongside chicago.db, implement `tax_estimate.py` that queries PTAXSIM for line-item tax breakdown by PIN
2. **Router prompt tuning** — Fine-tune for workflow detection accuracy. Add test cases to eval suite.
3. **TTL cache implementation** — Wire up caching for all spatial lookups to reduce latency on repeated/nearby queries
4. **Startup preloading** — TIF boundaries, Enterprise Zone boundaries, OZ tract list, GTFS stations, ACS community area demographics
5. **Performance testing** — Measure end-to-end latency for each workflow type. Target: <6s retrieval for full site due diligence
6. **Eval expansion** — Add 10-15 test queries for new workflows (due diligence, feasibility, business launch)
7. **Error handling** — Graceful degradation when external APIs are down (return partial results)

---

## 10. Effort Estimates

| Phase | Scope | Estimate | Dependencies |
|-------|-------|----------|-------------|
| 1. Infrastructure | Models, routing, wiring | 3-4 days | None |
| 2. Property Domain | 5 modules + orchestrator | 4-5 days | Phase 1 |
| 3. Regulatory Domain | 3 modules + overlay generalization | 3-4 days | Phase 1 |
| 4. Incentives Domain | 3 modules + boundary caching | 3-4 days | Phase 1 |
| 5. Neighborhood Domain | 2 modules + GTFS parsing | 3-4 days | Phase 1 |
| 6. Frontend Integration | Types, cards, map layers | 5-6 days | Phases 2-5 |
| 7. Polish & Optimization | PTAXSIM, caching, eval, perf | 4-5 days | Phase 6 |
| **Total** | | **~6-8 weeks** | |

**Per-module estimates:**
- New ArcGIS REST query module: ~2-3 hours (copy pattern from zoning.py, change endpoint/fields)
- New Socrata query module: ~2-3 hours (copy pattern from business.py, change dataset/fields)
- Domain orchestrator: ~4-6 hours (async dependency chain, error handling, summary assembly)
- Frontend data card: ~3-4 hours (component + styling + state wiring)
- Map layer type: ~2-3 hours (deck.gl layer + toggle + legend)
- Tests per module: ~1-2 hours

---

## 11. Risk Analysis

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **ArcGIS service downtime** | Medium | High — Regulatory domain fails entirely | Graceful degradation: return partial results when some layers fail. Individual layer failures should not block other layers. |
| **Cook County GIS rate limiting** | Low | Medium — Property lookups throttled | TTL cache (1hr) on spatial queries. Batch queries within a session. |
| **Census API rate limiting** | Low-Medium | Low — Demographics unavailable | Pre-aggregate community area data from Socrata. Census API is fallback for tract-level. |
| **PTAXSIM DB size** | Low | Low — Large download | DB is ~500MB compressed. Download once, store alongside chicago.db. Annual refresh. |
| **Router prompt degradation** | Medium | Medium — Wrong domains selected | Incremental prompt changes with eval regression testing. Keep existing source tags working. |
| **Synthesis prompt overload** | Medium | Medium — LLM loses coherence with too much context | Workflow-based context selection (don't send everything for every query). Cap context size per domain. |
| **GTFS feed format changes** | Low | Low — Transit data stale | GTFS is a stable standard. Station locations rarely change. Monthly refresh is sufficient. |
| **Cook County data quality** | Medium | Medium — Missing/stale assessments | CCAO data has known gaps for recent tax years (assessment cycle). Show data vintage in UI. |

### Data Risks

| Risk | Description | Mitigation |
|------|-------------|-----------|
| **PIN resolution failure** | Parcel GIS may not find a match for every address (e.g., new construction, address errors) | Return what we can without PIN. Zoning and regulatory overlays don't need PIN. |
| **Assessment lag** | CCAO assessments are triennial by township. Recent years may show $0 or stale values. | Show the most recent non-zero assessment year. Display "(Assessment Year: 20XX)" label. |
| **TIF data freshness** | TIF financials are annual reports, potentially 1-2 years behind. | Display the report year prominently. Note that TIF surplus is based on the most recent annual report. |
| **Census data vintage** | ACS 5-year estimates have a 2-year lag (2023 data = 2019-2023 period). | Label as "ACS 2019-2023 Estimates" in UI. |
| **Opportunity Zone permanence** | OZ designations were made permanent by the One Big Beautiful Bill Act (2025). Before that, they were set to expire in 2028. | Static dataset — load once. Note: tax benefits may still have sunset provisions distinct from the designations. |

### Operational Risks

| Risk | Description | Mitigation |
|------|-------------|-----------|
| **API key management** | Census API key and potential Cook County Socrata token need secure storage. | Add to `.env` file (already gitignored). Document in `.env.example`. |
| **Startup time increase** | Loading TIF boundaries, EZ boundaries, OZ tracts, GTFS stations, ACS data adds to cold start. | Lazy-load with locks (same pattern as `_get_known_sections()` in vector_search.py). First request triggers load; subsequent requests use cache. |
| **Cost increase** | More context tokens per query → higher Anthropic API cost. | Estimate: +2,000-3,000 tokens input per query = ~$0.006-0.009 at Sonnet pricing. Negligible vs. current ~$0.02/query. |
| **Test coverage** | 15-18 new modules need tests. | Follow existing test patterns. Mock external APIs (already done for Socrata in test_socrata.py). |

---

## 12. Recommended Order of Implementation

### Week 1: Infrastructure + First Integration

**Day 1-2:** Models, config, directory structure, cache utility
**Day 3-4:** Cook County GIS parcel lookup (the keystone — unlocks all property data)
**Day 5:** Wire parcel lookup into main.py, basic smoke test

The parcel lookup is the first integration because it provides the PIN, which is the join key for everything in the property domain. Getting this working validates the entire ArcGIS REST → domain orchestrator → context assembly pipeline.

### Week 2: Property Domain Complete

**Day 1:** CCAO characteristics module
**Day 2:** CCAO assessments module
**Day 3:** CCAO sales module
**Day 4:** Property domain orchestrator (parcel → PIN → parallel fan-out)
**Day 5:** Synthesis prompt update, tests

### Week 3: Regulatory Domain

**Day 1-2:** Generalized MapServer overlay query function + regulatory orchestrator
**Day 3:** FEMA flood zone query
**Day 4:** EPA brownfields query
**Day 5:** Tests, synthesis prompt update

This is the fastest phase because all 12+ overlay layers use the identical query pattern. The generalized function takes a layer_id parameter — one function covers all layers.

### Week 4: Incentives + Neighborhood Domains

**Day 1:** TIF boundary loading + point-in-polygon + financials query
**Day 2:** Opportunity Zone lookup (tract resolution + set membership)
**Day 3:** Enterprise Zone boundary loading + lookup
**Day 4:** Demographics (community area pre-aggregated data from Socrata)
**Day 5:** Transit proximity (GTFS parsing + MapServer TOD layers)

### Week 5-6: Frontend Integration

**Week 5:**
- TypeScript types for all new domains
- Property card component (assessment history chart, sales table)
- Regulatory overlay list component
- Incentives status card
- Demographics + transit card

**Week 6:**
- Map layer expansion (parcel boundary, overlay polygons, incentive zones, stations)
- Dynamic layer toggles
- Integration testing across all workflows
- Router prompt fine-tuning

### Week 7-8: Polish

- PTAXSIM integration
- TTL caching for all spatial lookups
- Startup preloading optimization
- Eval suite expansion (new workflow queries)
- Performance benchmarking
- Error handling and graceful degradation
- Documentation

---

## Appendix A: Environment Configuration

Add to `.env.example`:

```bash
# Existing
ANTHROPIC_API_KEY=
SOCRATA_APP_TOKEN=           # Chicago Data Portal

# New
COOK_COUNTY_SOCRATA_TOKEN=   # datacatalog.cookcountyil.gov (optional, recommended)
CENSUS_API_KEY=              # api.census.gov (free, register at census.gov)
WALKSCORE_API_KEY=           # walkscore.com (free tier, 5000 calls/day) ✅ INTEGRATED
```

Walk Score API key is required for walk/transit/bike scores. All ArcGIS services (Chicago, Cook County, FEMA, EPA, HUD, NPS) are fully public with no authentication.

## Appendix B: Key Endpoint Reference

```
# Cook County GIS — Parcel Lookup
GET https://gis.cookcountyil.gov/traditional/rest/services/cookVwrDynmc/MapServer/44/query
    ?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326
    &spatialRel=esriSpatialRelIntersects&outFields=*&f=json

# CCAO Socrata — Property Characteristics by PIN
GET https://datacatalog.cookcountyil.gov/resource/x54s-btds.json
    ?pin={14_digit_pin}&$order=year DESC&$limit=1

# CCAO Socrata — Assessed Values by PIN (5 years)
GET https://datacatalog.cookcountyil.gov/resource/uzyt-m557.json
    ?pin={14_digit_pin}&$order=tax_year DESC&$limit=5

# CCAO Socrata — Sales History by PIN
GET https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json
    ?pin={14_digit_pin}&$order=sale_date DESC&$limit=10

# Chicago Zoning MapServer — Any Overlay Layer
GET https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer/{layer_id}/query
    ?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326
    &spatialRel=esriSpatialRelIntersects&outFields=*&f=json

# FEMA Flood Zone
GET https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query
    ?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326
    &spatialRel=esriSpatialRelIntersects&outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF&f=json

# EPA Brownfields (within 1km radius)
GET https://geopub.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer/5/query
    ?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326
    &spatialRel=esriSpatialRelIntersects&distance=1000&units=esriSRUnit_Meter
    &outFields=SITE_NAME,EPA_ID,CLEANUP_STATUS&f=json

# TIF District Boundaries (GeoJSON)
GET https://data.cityofchicago.org/resource/eejr-xtfb.geojson

# TIF Financial Reports
GET https://data.cityofchicago.org/resource/72uz-ikdv.json
    ?$where=tif_name='{tif_name}'&$order=year DESC&$limit=5

# Enterprise Zones (GeoJSON)
GET https://data.cityofchicago.org/resource/64xf-pyvh.geojson

# HUD Opportunity Zones
GET https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Opportunity_Zones/FeatureServer/0/query
    ?where=GEOID='{11_char_tract_fips}'&outFields=*&f=json

# Census ACS Demographics (all Cook County tracts)
GET https://api.census.gov/data/2023/acs/acs5
    ?get=NAME,B01003_001E,B19013_001E,B25077_001E
    &for=tract:*&in=state:17%20county:031&key={CENSUS_API_KEY}

# FCC Tract Lookup (lat/lon → census tract)
GET https://geo.fcc.gov/api/census/area?lat={lat}&lon={lon}&format=json

# CTA GTFS (static download)
GET https://www.transitchicago.com/downloads/sch_data/google_transit.zip

# Metra GTFS (static download)
GET https://schedules.metrarail.com/gtfs/schedule.zip

# Pre-aggregated Community Area Demographics
GET https://data.cityofchicago.org/resource/t68z-cikk.json
    ?community_area={ca_number}
```

## Appendix C: What's Not Programmatically Accessible

| Data | Why Not | Workaround |
|------|---------|-----------|
| Property ownership/taxpayer names | CAPTCHA-protected on Assessor website; not in open data | Paid: Chicago Cityscape API or Regrid. Free: Manual lookup at cookcountyassessoril.gov |
| Planned Development applications | Plan Commission agendas are PDF-only; no structured dataset | Paid: Chicago Cityscape tracks these. Free: Monitor plan commission agendas manually |
| Zoning Board of Appeals cases | No public API or structured dataset | Monitor ZBA meeting agendas (PDF) |
| Illinois SOS business entity search | No API, scraping prohibited | Manual lookup at apps.ilsos.gov |
| Cook County Clerk recordings search | Web-only (crs.cookcountyclerkil.gov), no API, returns 403 on programmatic access | Manual search. Archived partial data on Open Data (Quit Claims 2013-2015, Mortgages 2011+) |
| Detailed deed documents | Only searchable via Clerk portal | cookcountypropertyinfo.com for basic deed info |
| DSIRE energy incentive database | API requires paid subscription | Link out to programs.dsireusa.org for user self-service |
| Illinois HARGIS (historic sites) | Web-app only, no API | Use NPS MapServer + Chicago landmark datasets instead |
