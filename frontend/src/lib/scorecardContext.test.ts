import { describe, it, expect } from "vitest";
import { buildScorecardContext } from "./scorecardContext";
import type { ScorecardResponse } from "./api";

// Minimal ScorecardResponse builder. buildScorecardContext + computeVerdict read
// their inputs with optional chaining, so a partial shape exercises the real
// code paths; the cast keeps the fixture readable without restating every field.
function makeResp(overrides: Partial<ScorecardResponse> = {}): ScorecardResponse {
  return {
    address: "1601 N Milwaukee Ave",
    lat: 41.9,
    lon: -87.68,
    community_area: 24,
    community_area_name: "West Town",
    resolved_pin: "16012345678900",
    resolved_confidence: "authoritative",
    resolved_lat: 41.9,
    resolved_lon: -87.68,
    partial_failures: [],
    zone_definition: {
      zone_class: "B3-2",
      name: "Community Shopping District",
      far: 2.5,
      is_fallback: false,
    },
    comparables: { median_sale_price: 800000, sales_volume: 6, sales: [] },
    context: {
      // Area-level feeds — these must NEVER appear in the parcel grounding payload.
      crime_last_90d: { total: 142, arrest_rate: 0.1, by_type: {} },
      parcel_zoning: { zone_class: "B3-2", zone_type: 3, ordinance_num: null, zoning_map_url: "" },
      regulatory: { in_landmark_district: false, in_planned_development: false },
      incentives: { in_tif_district: true, tif_name: "Kinzie Industrial" },
      property: { bldg_class: "2-11", bldg_sqft: 5000, land_sqft: 3000 },
    },
    ...overrides,
  } as unknown as ScorecardResponse;
}

describe("buildScorecardContext — pin-null (unverified identity) tier", () => {
  it("ships zoning + a caveated verdict but OMITS PIN-keyed property/comps", () => {
    const resp = makeResp({
      resolved_pin: null,
      resolved_confidence: "approximate",
      nearest_parcel_unverified: true,
    });

    const ctx = buildScorecardContext(resp);

    expect(ctx).not.toBeNull();
    // Identity-independent facts ride along.
    expect(ctx!.zone_definition).toBeTruthy();
    expect(ctx!.regulatory).toBeTruthy();
    expect(ctx!.incentives).toBeTruthy();
    // The verdict ships AND stays hedged (nearest_parcel_unverified → caveated).
    expect(ctx!.verdict).toBeTruthy();
    expect(ctx!.verdict!.confidence).toBe("caveated");
    expect(ctx!.verdict!.caveats.length).toBeGreaterThan(0);
    // PIN-keyed fields are omitted — they could belong to a neighbor parcel.
    expect(ctx!.property).toBeUndefined();
    expect(ctx!.comparables).toBeUndefined();
  });

  it("returns null only when there is no zoning at all", () => {
    const resp = makeResp({
      resolved_pin: null,
      zone_definition: null,
      context: { parcel_zoning: null } as unknown as ScorecardResponse["context"],
    });
    expect(buildScorecardContext(resp)).toBeNull();
  });

  it("pin present → property + comparables included", () => {
    const ctx = buildScorecardContext(makeResp());
    expect(ctx!.property).toBeTruthy();
    expect(ctx!.comparables).toBeTruthy();
  });
});

describe("scope discipline — area-level facts never enter the grounding payload", () => {
  // The trust bug as a regression test: the payload that disentangled parcel
  // from area must not re-conflate them by smuggling an area feed into chat.
  for (const tier of ["pin present", "pin null"] as const) {
    it(`omits crime/311/neighborhood feeds (${tier})`, () => {
      const resp = makeResp(tier === "pin null" ? { resolved_pin: null } : {});
      // Sanity: the source response really does carry the area-level feed.
      expect(resp.context.crime_last_90d).toBeTruthy();

      const ctx = buildScorecardContext(resp)!;

      expect(ctx).toBeTruthy();
      expect("crime_last_90d" in ctx).toBe(false);
      expect("open_311_requests" in ctx).toBe(false);
      expect("neighborhood" in ctx).toBe(false);
      expect("permits" in ctx).toBe(false);
      // Parcel violations ride ONLY under the address-scoped `address_violations`
      // field — a raw area-style `violations` key must never appear (#4b).
      expect("violations" in ctx).toBe(false);
      expect(ctx.address_violations).toBeTruthy();
    });
  }
});

describe("address violations tri-state (#4b) — chat agrees with the page", () => {
  function withViolations(over: Partial<ScorecardResponse["context"]> & { violations_checked?: boolean }) {
    const { violations_checked, ...ctxOver } = over;
    return makeResp({
      violations_checked,
      context: { ...makeResp().context, ...ctxOver } as ScorecardResponse["context"],
    });
  }

  it("present → status 'present' carrying the address summary", () => {
    const ctx = buildScorecardContext(
      withViolations({
        violations: { total: 2, open_count: 1, by_category: {}, top_descriptions: [] },
      }),
    )!;
    expect(ctx.address_violations!.status).toBe("present");
    expect(ctx.address_violations!.summary!.total).toBe(2);
  });

  it("confirmed_zero → lookup ran with no rows (NOT unconfirmed)", () => {
    const ctx = buildScorecardContext(
      withViolations({ violations: null as never, violations_checked: true }),
    )!;
    expect(ctx.address_violations!.status).toBe("confirmed_zero");
    expect(ctx.address_violations!.summary).toBeNull();
  });

  it("unconfirmed → lookup never ran; must NOT read as zero", () => {
    const ctx = buildScorecardContext(
      withViolations({ violations: null as never, violations_checked: false }),
    )!;
    expect(ctx.address_violations!.status).toBe("unconfirmed");
    expect(ctx.address_violations!.summary).toBeNull();
  });

  it("ships in BOTH tiers (address-keyed, identity-independent)", () => {
    const present = buildScorecardContext(makeResp({ resolved_pin: null, violations_checked: true }))!;
    expect(present.address_violations).toBeTruthy();
    expect(present.property).toBeUndefined(); // still the zoning-only tier
  });
});
