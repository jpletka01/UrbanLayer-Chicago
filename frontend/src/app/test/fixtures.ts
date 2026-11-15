// Typed Profile fixtures for the new UI's tests (decision Item 76: new pages render from typed fixtures in CI).
// Shaped like `/api/scorecard` for 1601 N Milwaukee Ave; figures are illustrative, not the live parcel's.
import type { ScorecardResponse } from "../../lib/api";

type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? DeepPartial<T[K]> : T[K] };

export function profileFixture(over: DeepPartial<ScorecardResponse> & Record<string, unknown> = {}): ScorecardResponse {
  const base = {
    address: "1601 N MILWAUKEE AVE",
    lat: 41.9105,
    lon: -87.6776,
    resolved_lat: 41.9105,
    resolved_lon: -87.6776,
    resolved_pin: "14313250010000",
    resolved_confidence: "authoritative",
    community_area: 24,
    community_area_name: "West Town",
    partial_failures: [],
    failed_sources: [],
    data_dates: [{ key: "zoning", kind: "checked", as_of: "2026-11-01", period: null }],
    provenance: {
      "property.tax_estimate": { label: "Property tax estimate", source: "Cook County Clerk (PTAXSIM)", period: "2024", confidence: "standard" },
    },
    zone_definition: {
      zone_class: "B3-2", name: "Community Shopping District", code_section: "17-3-0402", far: 2.2,
      max_height: "50 ft", lot_coverage: null, min_lot_sqft: null, min_lot_area_per_unit: 1000,
      uses: "Retail, residential above", notes: "", is_fallback: false,
    },
    comparables: {
      median_sale_price: 850000, median_price_per_land_sqft: 140, median_price_per_bldg_sqft: 312,
      median_price_per_buildable_sqft: null, buildable_median_basis: null, buildable_median_n: null,
      price_range_min: 400000, price_range_max: 1400000, sales_volume: 9, sales: [],
    },
    context: {
      code_chunks: [],
      requires_disclaimer: false,
      community_area: 24,
      community_area_name: "West Town",
      resolved_address: "1601 N Milwaukee Ave",
      data_as_of: null, data_lag_note: null, data_lag_days: null, data_lag_cutoff: null,
      crime_last_90d: null, open_311_requests: null, permits: null, violations: null, businesses: null,
      vacant_buildings: null, food_inspections: null,
      parcel_zoning: { zone_class: "B3-2" },
      unit_yield: {
        units: 11, lot_sqft: 11250, min_lot_area_per_unit: 1000, arithmetic: "11,250 ÷ 1,000 = 11",
        basis: "lot area", caveat: "One limit among several.", lot_area_note: "",
      },
      property: {
        pin14: "14313250010000", address: "1601 N MILWAUKEE AVE", bldg_class: "5-17", bldg_class_description: "Commercial",
        bldg_sqft: 14700, land_sqft: 11250, stories: 3, units: 4, commercial_units: 2, rooms: null, bedrooms: null,
        full_baths: null, half_baths: null, bldg_age: 100, total_assessed_value: 250000,
        estimated_annual_tax: 64000, effective_tax_rate: 0.0515, tax_year: 2024, assessment_level: 0.25,
        implied_market_value: 1000000, tax_code: "71001", tax_breakdown: [], tax_exemptions: [],
        assessment_history: [], sales_history: [{ date: "2019-06-24T00:00:00.000", price: 1200000, deed_type: "Warranty", arms_length: true }], parcel_geometry: null, assessor_permits: null,
      },
      regulatory: {
        overlays: [], in_planned_development: false, in_landmark_district: true, is_landmark_building: false,
        in_historic_district: false, on_national_register: false, in_lakefront_protection: false,
        on_pedestrian_street: true, in_special_district: false, in_pmd: false, in_tod_area: true, in_adu_area: false,
        in_aro_zone: true, in_ssa: false, ssa_name: null, flood_zone: "X", flood_zone_subtype: null,
        in_special_flood_hazard: false, brownfield_sites: [], aro_housing: null, unchecked_overlays: [],
      },
      incentives: { in_tif_district: false, unchecked: [] },
      neighborhood: { walkscore: { walk_score: 99, walk_description: "Walker's Paradise", transit_score: 77, transit_description: null, bike_score: 94, bike_description: null, ws_link: null } },
      upcoming_zoning: {
        status: "ready", placement_status: "complete", checked_at: "2026-11-05", radius_mi: 0.5,
        subject_filings: [],
        nearby_filings: [
          { record_number: "O2026-0001", title: "Map amendment, 1650 N Damen", status: "4-In Committee", sub_status: "Referred",
            url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=1", match_kind: "nearby", distance_mi: 0.21 },
        ],
        placed_count: 1, unplaced_count: 0,
        record_provenance: { source_id: "clerk", method: "", confidence: "standard" },
        placement_provenance: { source_id: "clerk", method: "", confidence: "standard" },
      },
    },
  };
  return merge(base, over) as unknown as ScorecardResponse;
}

function merge(a: Record<string, unknown>, b: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...a };
  for (const [k, v] of Object.entries(b)) {
    const av = a[k];
    out[k] = v && typeof v === "object" && !Array.isArray(v) && av && typeof av === "object" && !Array.isArray(av)
      ? merge(av as Record<string, unknown>, v as Record<string, unknown>)
      : v;
  }
  return out;
}
