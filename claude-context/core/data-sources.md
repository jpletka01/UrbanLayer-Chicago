# Data Sources — UrbanLayer

## Chicago Data Portal (Socrata)

Base: `https://data.cityofchicago.org/resource/{id}.json` with SoQL + `X-App-Token` header.

| Dataset | ID | Key Fields | Use | Query Strategy |
|---------|-----|-----------|-----|----------------|
| Crimes 2001–Present | `ijzp-q8t2` | date, primary_type, description, arrest, community_area, lat/lon | Crime trends, safety. 7-day data lag | Grouped by primary_type (limit 35, never caps) |
| 311 Service Requests | `v6vf-nfxy` | sr_type, status, owner_department, created_date, lat/lon | Quality-of-life. `Open - Dup` filtered | Grouped by dept+type (limit 200) |
| Building Permits | `ydr8-5enu` | permit_type, work_description, issue_date, reported_cost, lat/lon | Development activity | Grouped by permit_type + detail sample (limit 20) for descriptions |
| Building Violations | `22u3-xenr` | violation_date, violation_description, violation_status, lat/lon | Property condition | Status counts (grouped) + detail sample (limit 200) for categorization |
| Business Licenses | `uupf-x98q` | doing_business_as_name, license_description, business_activity, date_issued, lat/lon | Neighborhood character. Active only (license_status='AAI') | Grouped by license_description + detail sample (limit 20) for activities |
| Vacant Buildings | `kc9i-wq85` | property_address, issued_date, violation_type, entity, fines, lat/lon | Vacant/abandoned building cases. Bounding-box filter | Grouped by issuing_department + detail sample (limit 20) |
| Food Inspections | `4ijn-s7e5` | dba_name, facility_type, risk, results, inspection_date, violations, lat/lon | Restaurant/food safety inspections. Bounding-box filter | Grouped by results + risk + detail sample (limit 20) |
| Community Areas | `igwz-8jzy` | Boundaries GeoJSON | Address → community area (shapely) |
| TIF District Boundaries | `eejr-xtfb` | geometry (multipolygon), name, approval_d, expiration, comm_area, repealed_d | Preloaded at startup. Point-in-polygon for address queries, comm_area matching for neighborhood queries. Repealed districts filtered out |
| TIF Annual Report Projects | `72uz-ikdv` | tif_district, report_year, public_funds, current_year_payments, project_name, status | Per-project financial data. Queried by `tif_district` (not tif_name). Conditional query when point-based TIF hit |
| TIF Fund Analysis | `qm7s-3ctt` | tif_district, report_year, property_tax_increment_current/cumulative, total_expenditure, fund_balance, net_income | District-level annual financials. Primary source for TIF revenue/expenditure/balance headlines |
| Enterprise Zone Boundaries | `64xf-pyvh` | geometry, zone_name | Preloaded at startup |
| SBIF Projects | `etqr-sz5x` | project_name, community_area, incentive_amount, total_project_cost, property_type, project_description, completion_date, tif_district | 2,152 records. Small Business Improvement Fund grants in TIF districts | Queried by community_area name match (limit 15) |
| NOF Large Grants | `j7ew-b73u` | project_name, community_area, incentive_amount, total_project_cost, property_type, project_description, completion_date | 6 records. Neighborhood Opportunity Fund large grants | Queried by community_area (limit 15) |
| NOF Small Grants | `rym7-49n8` | Same schema as NOF Large | 126 records. Neighborhood Opportunity Fund small grants | Queried by community_area (limit 15) |
| ARO Housing | `s6ha-ppgi` | property_name, address, units, property_type, community_area, community_area_number, management_company, lat/lon | 598 records. Affordable Requirements Ordinance housing projects | Queried by community_area_number (limit 20) |
| ACS 5-Year by Community Area | `t68z-cikk` | population, income brackets, poverty | Demographics (estimated medians) |
| Census Tracts 2020 | `4hp8-2i8z` | geometry, tractce20, geoid20 | Tract resolution for OZ lookup |

## Cook County Open Data (Socrata)

Base: `https://datacatalog.cookcountyil.gov/resource/{id}.json`. Same SODA 2.1 API.

| Dataset | ID | Key Fields | Join Key |
|---------|-----|-----------|----------|
| Parcel Universe (Current) | `pabr-t5kh` | pin, class, township, lat, lon | PIN — also used as **fallback for lat/lon → PIN** when GIS is down (bounding-box query on lat/lon). PIN-direct lookup via `lookup_parcel_by_pin()` |
| **Address Points** | `78yw-iddh` | add_number, **st_predir** (spelled-out word, e.g. `WEST`), st_name (no suffix), lst_type (suffix abbr), pin, lat, **long** | **Authoritative address→PIN map** (GIS-index-independent). Powers R7 `address_to_pin()` (`retrieval/property/address_points.py`). `inc_muni='Chicago'` filter (title-case). **Gotchas:** `st_predir` is the word not the letter (match `in ('W','WEST')`); coord column is `long` not `lon`; query by number+direction+name only (no suffix-type filter → numbered streets like `87TH ST`/`87TH PL` can multi-match → conservative fall-through). Some exempt/institutional parcels have **no** address point (e.g. EX subject `14283190070000`) |
| Assessed Values | `uzyt-m557` | pin, tax_year, mailed_tot, certified_tot, board_tot | PIN + year |
| Parcel Sales | `wvhk-k5uv` | pin, sale_date, sale_price, deed_type | PIN |
| Single/Multi-Family Characteristics | `x54s-btds` | pin, char_bldg_sf, char_land_sf, char_rooms, char_age | PIN |
| Condo Characteristics | `3r7i-mrz4` | pin, char_bldg_sf, char_rooms | PIN |

## Chicago Zoning MapServer (ArcGIS)

Base: `https://gisapps.chicago.gov/arcgis/rest/services/ExternalApps/Zoning/MapServer`

No auth required. All layers use identical spatial query pattern:
```
GET {base}/{layer_id}/query?geometry={lon},{lat}&geometryType=esriGeometryPoint
  &inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
```

| Layer | Name | Status |
|-------|------|--------|
| 1 | Zoning Districts (detailed) | Integrated — `zoning.py` |
| 2 | Planned Developments | Integrated — `regulatory/overlays.py` |
| 3 | Lakefront Protection | Integrated |
| 4 | Pedestrian Streets | Integrated |
| 5 | Landmark Boundaries | Integrated |
| 6 | Historic Districts | Integrated |
| 7 | Landmark Buildings | Integrated |
| 8 | National Register | Integrated |
| 9 | Special Districts (PMDs) | Integrated |
| 11 | FEMA Floodplain (local copy) | Integrated |
| 12 | PMD SubAreas | Integrated |
| 13 | TSL/CTA Stations (TOD boundaries) | Integrated |
| 17 | ADU Areas | Integrated |
| 20 | ARO Zones | Integrated |
| 23 | SSAs (Special Service Areas) | Integrated |
| 24 | TSL Metra Stations (TOD boundaries) | Integrated |
| 10, 14, 18, 19, 21 | Optional layers | Not integrated |

## External ArcGIS Services

| Service | Endpoint | Use | Status |
|---------|----------|-----|--------|
| Cook County GIS Parcels | `gis.cookcountyil.gov/.../cookVwrDynmc/MapServer/44/query` | lat/lon → PIN14 (layer 44, max 2000 records) | **Intermittent** — spatial index broken, queries can timeout 60s+. Socrata Parcel Universe (`pabr-t5kh`) used as automatic fallback (bounding-box on lat/lon, no polygon geometry). |
| FEMA Flood Zones | `hazards.fema.gov/.../NFHL/MapServer/28/query` | FLD_ZONE, SFHA_TF | Working (occasional 500s) |
| EPA Brownfields | `geopub.epa.gov/.../FRS_INTERESTS/MapServer/5/query` | SITE_NAME, CLEANUP_STATUS (1km radius) | Working |
| HUD Opportunity Zones | `services.arcgis.com/.../Opportunity_Zones/FeatureServer/0/query` | GEOID match by tract FIPS | Working |

## Other APIs

| API | Auth | Use |
|-----|------|-----|
| Census Geocoder | None | Address → lat/lon. Already integrated in `geo.py` |
| FCC Census Block | None | lat/lon → tract FIPS (~100ms). Used for OZ lookup + census tract demographics |
| Census Reporter | None | ACS 5-year data by census tract (age, income, race, education, transportation distributions). 24h TTL cache. Endpoint: `api.censusreporter.org/1.0/data/show/latest` |
| Walk Score | API key (free, 5K/day) | Walk/Transit/Bike scores (0-100). 48h TTL cache |
| CTA GTFS (static) | None | Parsed at startup → transit station locations |
| Metra GTFS (static) | None | Parsed at startup → station locations |

## Local Data

| Source | Location | Use |
|--------|----------|-----|
| Municipal Code | Qdrant (14,535 chunks from 8,615 sections) | Vector search for legal questions |
| PTAXSIM | `backend/data/ptaxsim.db` (8.8GB SQLite) | Property tax estimation by PIN |
| Transit Stations | Parsed from GTFS at startup | Nearest station proximity |
| Community Area Polygons | `ingestion/data/community_areas.geojson` | Point-in-polygon resolution |

## PIN System

The Property Index Number (PIN) is the universal join key for Cook County property data:
- Format: `TT-SS-BBB-PPP-UUUU` (14 digits). TT=Township, SS=Section, BBB=Block, PPP=Parcel, UUUU=Unit
- 10-digit = land parcel. 14-digit = specific unit (condos). Always zero-pad to 14 digits.
- Obtained via Cook County GIS spatial query: lat/lon → parcel → PIN14

## What's Not Programmatically Accessible

| Data | Reason | Workaround |
|------|--------|------------|
| Property ownership/taxpayer names | CAPTCHA-protected, not in open data | Paid: Chicago Cityscape, Regrid |
| Planned Development applications | PDF-only (Plan Commission agendas) | Monitor agendas manually |
| Illinois SOS business entities | No API, scraping prohibited | Manual lookup |
| Cook County Clerk recordings | Web-only, returns 403 programmatically | Manual search |
| DSIRE energy incentives | Paid API subscription | Link to programs.dsireusa.org |
