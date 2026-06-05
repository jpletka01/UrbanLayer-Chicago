# Data Source Coverage Report

**34/41 sub-source checks covered** across 29 queries.

## Coverage Matrix

| Sub-Source | Tested | Covered | Synthesis Gap | Retrieval Gap | Hallucination |
|---|---:|---:|---:|---:|---:|
| `311_api` | 1 | 1 | 0 | 0 | 0 |
| `business_api` | 1 | 1 | 0 | 0 | 0 |
| `crime_api` | 2 | 2 | 0 | 0 | 0 |
| `food_inspections_api` | 1 | 1 | 0 | 0 | 0 |
| `incentives_ez` | 1 | 0 | 1 | 0 | 0 |
| `incentives_grants` | 1 | 1 | 0 | 0 | 0 |
| `incentives_oz` | 2 | 2 | 0 | 0 | 0 |
| `incentives_tax_class` | 1 | 0 | 0 | 0 | 1 |
| `incentives_tif` | 3 | 3 | 0 | 0 | 0 |
| `neighborhood_census_tract` | 1 | 1 | 0 | 0 | 0 |
| `neighborhood_demographics` | 2 | 2 | 0 | 0 | 0 |
| `neighborhood_transit` | 2 | 2 | 0 | 0 | 0 |
| `neighborhood_walkscore` | 1 | 0 | 0 | 0 | 1 |
| `parcel_zoning` | 2 | 2 | 0 | 0 | 0 |
| `permits_api` | 2 | 2 | 0 | 0 | 0 |
| `property_assessments` | 1 | 0 | 0 | 1 | 0 |
| `property_characteristics` | 1 | 0 | 0 | 1 | 0 |
| `property_pin` | 3 | 3 | 0 | 0 | 0 |
| `property_sales` | 1 | 1 | 0 | 0 | 0 |
| `property_tax` | 1 | 0 | 0 | 0 | 1 |
| `regulatory_aro_housing` | 1 | 0 | 0 | 0 | 1 |
| `regulatory_environmental` | 1 | 1 | 0 | 0 | 0 |
| `regulatory_flood` | 1 | 1 | 0 | 0 | 0 |
| `regulatory_overlays` | 1 | 1 | 0 | 0 | 0 |
| `regulatory_overlays_historic` | 1 | 1 | 0 | 0 | 0 |
| `regulatory_overlays_tod` | 1 | 1 | 0 | 0 | 0 |
| `vacant_buildings_api` | 1 | 1 | 0 | 0 | 0 |
| `vector_search` | 1 | 1 | 0 | 0 | 0 |
| `violations_api` | 3 | 3 | 0 | 0 | 0 |

## API Cap Report

| Source | Capped In | Limit | "at least" Used |
|---|---:|---:|---|
| `311_api` | 0/6 | 50 | n/a |
| `business_api` | 0/4 | 500 | n/a |
| `crime_api` | 0/4 | 35 | n/a |
| `permits_api` | 0/5 | 500 | n/a |
| `violations_api` | 0/5 | 200 | n/a |

## Per-Query Detail

| Query | Sub-Source | Status | Context | Synthesis |
|---|---|---|---|---|
| `crime_coverage` | `crime_api` | COVERED | 3/3 | 2/2 |
| `311_coverage` | `311_api` | COVERED | 2/2 | 2/2 |
| `permits_coverage` | `permits_api` | COVERED | 3/3 | 2/2 |
| `violations_coverage` | `violations_api` | COVERED | 3/3 | 2/2 |
| `business_coverage` | `business_api` | COVERED | 3/3 | 2/2 |
| `vacant_buildings_coverage` | `vacant_buildings_api` | COVERED | 2/2 | 2/2 |
| `food_inspections_coverage` | `food_inspections_api` | COVERED | 3/3 | 2/2 |
| `property_pin_characteristics` | `property_pin` | COVERED | 1/1 | 1/1 |
| `property_pin_characteristics` | `property_characteristics` | RETRIEVAL_GAP | 0/1 | 0/1 |
| `property_assessments_sales` | `property_pin` | COVERED | 1/1 | 1/1 |
| `property_assessments_sales` | `property_assessments` | RETRIEVAL_GAP | 0/1 | 1/2 |
| `property_assessments_sales` | `property_sales` | COVERED | 1/1 | 1/1 |
| `property_tax_estimate` | `property_tax` | HALLUCINATION | 0/1 | 2/2 |
| `zoning_class_lookup` | `parcel_zoning` | COVERED | 1/1 | 1/1 |
| `overlays_downtown` | `regulatory_overlays` | COVERED | 1/1 | 1/1 |
| `historic_landmark_coverage` | `regulatory_overlays_historic` | COVERED | 1/1 | 1/1 |
| `flood_zone_coverage` | `regulatory_flood` | COVERED | 1/1 | 1/1 |
| `tif_coverage` | `incentives_tif` | COVERED | 1/1 | 1/1 |
| `opportunity_zone_coverage` | `incentives_oz` | COVERED | 1/1 | 1/1 |
| `enterprise_zone_coverage` | `incentives_tif` | COVERED | 1/1 | 1/1 |
| `enterprise_zone_coverage` | `incentives_oz` | COVERED | 1/1 | 1/1 |
| `enterprise_zone_coverage` | `incentives_ez` | SYNTHESIS_GAP | 1/1 | 0/1 |
| `demographics_coverage` | `neighborhood_demographics` | COVERED | 1/1 | 2/2 |
| `census_tract_coverage` | `neighborhood_census_tract` | COVERED | 1/1 | 1/1 |
| `transit_coverage` | `neighborhood_transit` | COVERED | 1/1 | 2/2 |
| `walkscore_coverage` | `neighborhood_walkscore` | HALLUCINATION | 0/1 | 2/2 |
| `municipal_code_coverage` | `vector_search` | COVERED | 1/1 | 2/2 |
| `due_diligence_full` | `property_pin` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `parcel_zoning` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `crime_api` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `permits_api` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `violations_api` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `incentives_tif` | COVERED | 1/1 | 1/1 |
| `due_diligence_full` | `neighborhood_demographics` | COVERED | 1/1 | 1/1 |
| `due_diligence_violations_synthesis` | `violations_api` | COVERED | 2/2 | 2/2 |
| `tod_transit_cross` | `regulatory_overlays_tod` | COVERED | 1/1 | 1/1 |
| `tod_transit_cross` | `neighborhood_transit` | COVERED | 1/1 | 1/1 |
| `brownfield_coverage` | `regulatory_environmental` | COVERED | 1/1 | 1/1 |
| `grant_programs_coverage` | `incentives_grants` | COVERED | 1/1 | 1/1 |
| `aro_housing_coverage` | `regulatory_aro_housing` | HALLUCINATION | 0/1 | 1/1 |
| `tax_incentive_class_coverage` | `incentives_tax_class` | HALLUCINATION | 0/1 | 1/1 |