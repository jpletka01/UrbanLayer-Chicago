import { describe, expect, it } from "vitest";
import { computeVerdict, deriveSignals, selectCategory, type TFunc } from "./scorecardVerdict";
import type { ScorecardResponse } from "./api";

// Mock t: echoes the key (+ interpolation) so tests assert logic, not catalog strings.
const t: TFunc = (key, opts) => (opts ? `${key} ${JSON.stringify(opts)}` : key);

type Mk = {
  far?: number | null;
  fallback?: boolean;
  zone?: string;
  bldg?: number | null;
  land?: number | null;
  bldgClass?: string | null;
  bldgSource?: string | null;
  noProperty?: boolean;
  noZone?: boolean;
  oz?: boolean;
  tif?: boolean;
  tifName?: string;
  tifBalance?: number | null;
  tifCumulative?: number | null;
  ez?: boolean;
  qct?: boolean;
  nmtc?: boolean;
  landmark?: boolean;
  historic?: boolean;
  natlReg?: boolean;
  pd?: boolean;
  lakefront?: boolean;
  flood?: string | null;
  tod?: boolean;
  adu?: boolean;
  aro?: boolean;
  openViolations?: number;
  unverified?: boolean;
  approximate?: boolean;
  partial?: string[];
  cityOwned?: boolean;
  scofflaw?: boolean;
  strProhibited?: boolean;
  appealWins?: number;
  appealMedian?: number | null;
};

function mk(o: Mk): ScorecardResponse {
  const property = o.noProperty
    ? null
    : {
        bldg_sqft: o.bldg ?? null,
        land_sqft: o.land ?? null,
        bldg_sqft_source: o.bldgSource ?? null,
        bldg_class: o.bldgClass ?? "2-11",
        address: "1 Test St",
        flags:
          o.cityOwned || o.scofflaw || o.strProhibited
            ? {
                tax_sale_years: [2013], // historic — must never influence anything
                scavenger_sale_years: [],
                city_owned: !!o.cityOwned,
                city_owned_status: null,
                city_owned_sales_status: null,
                city_owned_application_url: null,
                scofflaw: !!o.scofflaw,
                scofflaw_case: null,
                str_prohibited: !!o.strProhibited,
              }
            : null,
        appeals:
          o.appealWins !== undefined
            ? {
                records: [],
                nearby_window_years: [2024, 2025],
                nearby_appeal_count: Math.max(o.appealWins ?? 0, 50),
                nearby_reduced_count: o.appealWins ?? 0,
                nearby_median_reduction_pct: o.appealMedian ?? null,
              }
            : null,
      };
  const zone_definition = o.noZone
    ? null
    : { zone_class: o.zone ?? "RT-4", name: "Test", code_section: "§x", far: o.far === undefined ? 1.2 : o.far, max_height: null, lot_coverage: null, uses: "", notes: "", is_fallback: !!o.fallback };
  const context = {
    property,
    incentives: {
      in_opportunity_zone: !!o.oz,
      in_tif_district: !!o.tif,
      tif_name: o.tifName ?? null,
      tif_fund_balance: o.tifBalance ?? null,
      tif_cumulative_revenue: o.tifCumulative ?? null,
      in_enterprise_zone: !!o.ez,
      in_qct: !!o.qct,
      in_nmtc: !!o.nmtc,
    },
    regulatory: {
      in_landmark_district: !!o.landmark,
      is_landmark_building: false,
      in_historic_district: !!o.historic,
      on_national_register: !!o.natlReg,
      in_planned_development: !!o.pd,
      in_lakefront_protection: !!o.lakefront,
      in_tod_area: !!o.tod,
      in_adu_area: !!o.adu,
      in_aro_zone: !!o.aro,
      flood_zone: o.flood ?? "X",
    },
    violations: { total: 491, open_count: o.openViolations ?? 0 },
  };
  return {
    address: "1 Test St",
    context,
    partial_failures: o.partial ?? [],
    resolved_pin: o.unverified ? null : "12345678901234",
    resolved_confidence: o.approximate || o.unverified ? "approximate" : "authoritative",
    nearest_parcel_unverified: !!o.unverified,
    zone_definition,
  } as unknown as ScorecardResponse;
}

const cat = (o: Mk) => selectCategory(deriveSignals(mk(o)), mk(o));

describe("scorecardVerdict — category selection", () => {
  it("strong: high capacity on a high-intensity zone, no friction", () => {
    expect(cat({ zone: "DS-5", far: 5.0, bldg: 1000, land: 970 })).toBe("strong");
  });

  it("incentive_driven: strong incentive stack, capacity unknown, no friction", () => {
    expect(cat({ zone: "B2-3", far: 3.0, noProperty: true, oz: true, tif: true, qct: true })).toBe("incentive_driven");
  });

  it("limited: ordinary built-out parcel, no incentives, no friction (the honest modal verdict)", () => {
    expect(cat({ zone: "RS-3", far: 0.9, bldg: 900, land: 1000 })).toBe("limited");
  });

  it("entitlement_defined: PD zone with null FAR", () => {
    expect(cat({ zone: "PD 533", far: null, bldg: 5000, land: 10000 })).toBe("entitlement_defined");
  });

  it("entitlement_defined: fallback zone definition", () => {
    expect(cat({ zone: "RS-3", far: null, fallback: true })).toBe("entitlement_defined");
  });

  it("insufficient_data ONLY when no zone AND no property", () => {
    expect(cat({ noZone: true, noProperty: true })).toBe("insufficient_data");
  });
});

describe("scorecardVerdict — calibration decisions (signed off 2026-06-29)", () => {
  it("#2: friction wins the label — TIF + landmark is constrained, NOT incentive_driven", () => {
    const o: Mk = { zone: "DR-3", far: 3.0, bldg: 1900, land: 1000, tif: true, tifBalance: 213_000_000, landmark: true };
    expect(cat(o)).toBe("constrained");
    const v = computeVerdict(mk(o), t);
    // the incentive must still show as a positive, AND a negative must be forced
    expect(v.reasons.some((r) => r.polarity === "negative")).toBe(true);
    expect(v.reasons.some((r) => r.polarity === "positive")).toBe(true);
  });

  it("#2 guard: ANY meaningful friction forces ≥1 negative reason regardless of label", () => {
    const v = computeVerdict(mk({ zone: "B3-2", far: 2.2, noProperty: true, landmark: true, historic: true }), t);
    expect(v.reasons.some((r) => r.polarity === "negative")).toBe(true);
  });

  it("decision B: single-family FAR headroom is NOT strong (allowed_far < 1.5 floor)", () => {
    // RT-4 under-built: ratio is 'high' but allowed FAR 1.2 < 1.5 → limited, not strong
    expect(cat({ zone: "RT-4", far: 1.2, bldg: 360, land: 1000 })).toBe("limited");
    // contrast: same headroom on an RM-6 (far 4.4) IS strong
    expect(cat({ zone: "RM-6", far: 4.4, bldg: 1300, land: 1000 })).toBe("strong");
  });

  it("caveated-unverified: zoning resolved but identity unconfirmed → still a verdict, flagged caveated", () => {
    const v = computeVerdict(mk({ zone: "DX-12", far: 12, noProperty: true, unverified: true }), t);
    expect(v.category).not.toBe("insufficient_data");
    expect(v.confidence).toBe("caveated");
    expect(v.caveats.length).toBeGreaterThan(0);
  });

  it("ARO + area-violations are NOT friction (would otherwise force constrained citywide)", () => {
    // aro + openViolations present but no real obstacle → must NOT be constrained
    expect(cat({ zone: "RS-3", far: 0.9, bldg: 900, land: 1000, aro: true, openViolations: 391 })).toBe("limited");
  });
});

describe("scorecardVerdict — output contract", () => {
  it("strong leads with a non-commercial chat step and no money action in the band (#4)", () => {
    const v = computeVerdict(mk({ zone: "DS-5", far: 5.0, bldg: 1000, land: 970 }), t);
    expect(v.nextStep.kind).toBe("chat");
    // The band carries one azure next-step only; the paid report is the separate
    // ReportCTACard, never a verdict secondary.
    expect("secondary" in v.nextStep).toBe(false);
  });

  it("every verdict has 1–4 reasons and a headline", () => {
    for (const o of [
      { zone: "DS-5", far: 5.0, bldg: 1000, land: 970 },
      { zone: "RS-3", far: 0.9, bldg: 900, land: 1000 },
      { zone: "PD 5", far: null as number | null },
      { noZone: true, noProperty: true },
    ]) {
      const v = computeVerdict(mk(o), t);
      expect(v.reasons.length).toBeGreaterThanOrEqual(1);
      expect(v.reasons.length).toBeLessThanOrEqual(4);
      expect(v.headline).toContain("scorecard.verdict.headline.");
    }
  });

  it("reasons carry a card anchor for deep-linking", () => {
    const v = computeVerdict(mk({ zone: "DS-5", far: 5.0, bldg: 1000, land: 970 }), t);
    for (const r of v.reasons) expect(["zoning", "incentives", "regulatory", "property", "comparables", "violations"]).toContain(r.cardAnchor);
  });
});

describe("scorecardVerdict — parcel flags + appeal signals (2026-07-02 arc)", () => {
  // Representative spread of the calibrated category space.
  const CONFIGS: Mk[] = [
    { far: 5.0, bldg: 2000, land: 5000, zone: "B3-5" }, // strong
    { oz: true, tif: true, bldg: null, land: null }, // incentive_driven
    { far: 5.0, bldg: 2000, land: 5000, zone: "B3-5", landmark: true }, // constrained
    {}, // limited
    { zone: "PD 1234", far: null }, // entitlement_defined
  ];
  const FLAGS: Partial<Mk> = { cityOwned: true, scofflaw: true, strProhibited: true, appealWins: 40, appealMedian: 16.9 };

  it("categories are stable by construction — flags/appeals never change the label", () => {
    for (const base of CONFIGS) {
      expect(cat({ ...base, ...FLAGS })).toBe(cat(base));
    }
  });

  it("city-owned adds a positive property-anchored reason", () => {
    const v = computeVerdict(mk({ cityOwned: true }), t);
    const r = v.reasons.find((x) => x.text.includes("reason.cityOwned"));
    expect(r).toBeDefined();
    expect(r!.polarity).toBe("positive");
    expect(r!.cardAnchor).toBe("property");
  });

  it("appeal upside fires only above BOTH thresholds (wins ≥10 AND median ≥10%)", () => {
    const fires = (o: Mk) =>
      computeVerdict(mk(o), t).reasons.some((x) => x.text.includes("reason.appealUpside"));
    expect(fires({ appealWins: 40, appealMedian: 16.9 })).toBe(true);
    expect(fires({ appealWins: 9, appealMedian: 16.9 })).toBe(false);
    expect(fires({ appealWins: 40, appealMedian: 5.8 })).toBe(false); // dense-area background noise
    expect(fires({ appealWins: 40, appealMedian: null })).toBe(false);
  });

  it("scofflaw + STR-prohibited are caveats that do NOT flip confidence", () => {
    const v = computeVerdict(mk({ scofflaw: true, strProhibited: true }), t);
    expect(v.caveats.some((c) => c.includes("caveat.scofflaw"))).toBe(true);
    expect(v.caveats.some((c) => c.includes("caveat.strProhibited"))).toBe(true);
    expect(v.confidence).toBe("high");
  });

  it("historic tax-sale years never surface anywhere in the verdict", () => {
    const v = computeVerdict(mk({ cityOwned: true }), t); // factory sets tax_sale_years=[2013]
    const all = [...v.reasons.map((r) => r.text), ...v.caveats, v.headline].join(" ");
    expect(all).not.toMatch(/tax.?sale/i);
  });

  it("flag positives never push the forced friction negative out of the 4-cap (constrained)", () => {
    const v = computeVerdict(
      mk({ far: 5.0, bldg: 2000, land: 5000, zone: "B3-5", landmark: true, tif: true, tifName: "X", ...FLAGS }),
      t,
    );
    expect(v.reasons.length).toBeLessThanOrEqual(4);
    expect(v.reasons.some((r) => r.polarity === "negative")).toBe(true);
  });
});

describe("scorecardVerdict — 2026-07-06 audit fixes", () => {
  it("condo unit sqft never drives capacity: one unit vs the whole lot is not a teardown", () => {
    // 900 sqft unit on a 10,000 sqft lot in a high-FAR zone: existingFar
    // would read 0.09 → vacant_or_teardown → "strong". Source gate must
    // degrade capacity to unknown instead.
    const data = mk({ zone: "RM-6", far: 4.4, bldg: 900, land: 10000, bldgSource: "condo_unit" });
    const s = deriveSignals(data);
    expect(s.bldgAreaLowConfidence).toBe(true);
    expect(s.capacityBand).toBe("unknown");
    expect(s.existingFar).toBeNull();
    expect(selectCategory(s, data)).not.toBe("strong");
  });

  it("footprint sqft never drives capacity (ground area, not GFA)", () => {
    const data = mk({ zone: "B3-3", far: 3.0, bldg: 2000, land: 5000, bldgSource: "footprint" });
    const s = deriveSignals(data);
    expect(s.capacityBand).toBe("unknown");
  });

  it("assessor-sourced sqft still computes capacity", () => {
    const data = mk({ zone: "DS-5", far: 5.0, bldg: 1000, land: 970, bldgSource: "assessor" });
    const s = deriveSignals(data);
    expect(s.capacityBand).not.toBe("unknown");
    expect(selectCategory(s, data)).toBe("strong");
  });

  it("cumulative TIF revenue is NOT a fund balance: no well-funded gate, no balance reason", () => {
    // Lifetime increment $8M but no balance — the district may have spent it all.
    const data = mk({ zone: "RS-3", far: 0.9, bldg: 900, land: 1000, tif: true, tifCumulative: 8_000_000 });
    const s = deriveSignals(data);
    expect(s.tifBalance).toBe(0);
    expect(s.incentiveStrength).toBe("some"); // single incentive, not "strong"
  });

  it("a real fund balance still gates well-funded strength", () => {
    const data = mk({ zone: "RS-3", far: 0.9, bldg: 900, land: 1000, tif: true, tifBalance: 8_000_000 });
    const s = deriveSignals(data);
    expect(s.tifBalance).toBe(8_000_000);
    expect(s.incentiveStrength).toBe("strong");
  });
});
