import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { RentBlock } from "./RentBlock";
import { ProvenanceProvider } from "../../contexts/ProvenanceContext";
import type { Provenance } from "../../lib/api";
import type { AssessorModelRent, BedroomRent, NeighborhoodSummary, RentEvidence } from "../../lib/types";

afterEach(cleanup);

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Rent", kind: "derived", source: null, record_id: null, url: null, section: null, as_of: "2024-12-31",
    effective_date: null, query_date: "2026-10-28", note: null, tier: "official_estimate", as_of_basis: "period_end",
    period: "2020–2024", age_days: 667, scope: "tract", geography: "Census Tract 8310, Cook, IL",
    method_key: "survey_estimate", method: "Census survey estimate", confidence: "standard", confidence_reasons: [],
    precision: { moe: 220, moe_level: 0.9, cv: 0.055 },
    ...over,
  };
}

const caEntry = entry({
  tier: "our_calculation", method_key: "bracket_median", scope: "community_area", geography: "West Town",
  source_id: "artifact.rent_by_area", precision: { moe: 159, moe_level: 0.9, cv: 0.047, moe_method: "acs_handbook_median" },
});

function bedroom(over: Partial<BedroomRent>): BedroomRent {
  return {
    bedrooms: "1_bedroom", scope: "tract", geography: "Census Tract 8310, Cook, IL", geoid: "17031831000",
    estimate: 2336, moe: 260, cv: 0.068, tract_fallback: null, ...over,
  };
}

function rent(over: Partial<RentEvidence> = {}): RentEvidence {
  return {
    community_area: {
      community_area: 24, households: 25407, median: 2054, moe: 159, cv: 0.047, top_coded: false,
      moe_method: "acs_handbook_median", design_factor: 1.5, acs_period: "2020–2024", acs_release: "acs2024_5yr", period_end: "2024-12-31",
    },
    bedrooms: [bedroom({}), bedroom({ bedrooms: "2_bedrooms", estimate: 2373, moe: 530, cv: 0.136 }), bedroom({ bedrooms: "3_bedrooms", estimate: 3273, moe: 756, cv: 0.14 })],
    acs_period: "2020–2024", acs_release: "acs2024_5yr", tract_name: "Census Tract 8310, Cook, IL",
    puma_geoid: "1703159", puma_name: "West Town & Near West Side PUMA, IL", unchecked: [],
    ...over,
  };
}

function hood(r: RentEvidence | null, tractRent: number | null = 2435): NeighborhoodSummary {
  return {
    demographics: null, divvy: null, transit: null, walkscore: null, rent: r,
    census_tract: tractRent == null ? null : ({ tract_fips: "17031831000", median_gross_rent: tractRent } as NeighborhoodSummary["census_tract"]),
  };
}

const prov: Record<string, Provenance> = {
  "area.rent.community_area": caEntry,
  "area.tract.median_gross_rent": entry({}),
  "area.rent.1_bedroom": entry({}),
  "area.rent.2_bedrooms": entry({}),
  "area.rent.3_bedrooms": entry({}),
};

function renderBlock(h: NeighborhoodSummary, p: Record<string, Provenance> = prov) {
  return render(<ProvenanceProvider value={p}><RentBlock data={h} /></ProvenanceProvider>);
}

describe("RentBlock", () => {
  it("shows the area, tract and bedroom medians with period, margin and method", () => {
    renderBlock(hood(rent()));
    expect(screen.getByText(/Census ACS 2020–2024 5-year estimates, not listing prices/)).toBeTruthy();
    const area = within(screen.getByTestId("rent-tile-community-area"));
    expect(area.getByText(/\$2,054/)).toBeTruthy();
    const cap = area.getByTestId("confidence-caption").textContent!;
    expect(cap).toContain("Summed from Census rent brackets");  // not "estimated from income brackets"
    expect(cap).toContain("±$159");
    expect(cap).toContain("West Town");
    expect(within(screen.getByTestId("rent-tile-tract")).getByText(/\$2,435/)).toBeTruthy();
    expect(within(screen.getByTestId("rent-tile-2_bedrooms")).getByText(/\$2,373/)).toBeTruthy();
    expect(within(screen.getByTestId("rent-tile-1_bedroom")).getByText("This census tract")).toBeTruthy();
  });

  it("names a PUMA as a PUMA and says why the tract's figure was not used", () => {
    const r = rent({ bedrooms: [bedroom({ scope: "puma", geography: "West Town & Near West Side PUMA, IL", geoid: "1703159", tract_fallback: "suppressed" })] });
    renderBlock(hood(r), { ...prov, "area.rent.1_bedroom": entry({ scope: "puma", geography: "West Town & Near West Side PUMA, IL" }) });
    const tile = within(screen.getByTestId("rent-tile-1_bedroom"));
    expect(tile.getByText("A wider area (a PUMA), not this tract")).toBeTruthy();
    expect(tile.getByText("The Census publishes no median for this tract, so this is the PUMA's.")).toBeTruthy();
    expect(tile.getByTestId("confidence-caption").textContent).toContain("West Town & Near West Side PUMA, IL");
  });

  it("shows a withheld community-area median as a dash with the reason", () => {
    const withheld = { ...caEntry, confidence: "withheld" as const, confidence_reasons: ["high_cv"], precision: { moe: 943, moe_level: 0.9, cv: 1.6, moe_method: "acs_handbook_median" } };
    renderBlock(hood(rent()), { ...prov, "area.rent.community_area": withheld });
    const area = within(screen.getByTestId("rent-tile-community-area"));
    expect(area.queryByText(/\$2,054/)).toBeNull();
    expect(area.getByText("—")).toBeTruthy();
    expect(area.getByText("Not shown: the margin of error is 160% of the estimate.")).toBeTruthy();
  });

  it("says a suppressed cell is not published and a failed PUMA read was not checked", () => {
    const r = rent({ bedrooms: [bedroom({ bedrooms: "1_bedroom", estimate: null, moe: null, cv: null, tract_fallback: "suppressed" })], unchecked: ["puma_rent"] });
    renderBlock(hood(r));
    expect(within(screen.getByTestId("rent-tile-1_bedroom")).getByText("The Census publishes no usable median for this tract or its PUMA")).toBeTruthy();
    // 2 and 3 bedrooms have no cell and the PUMA could not be read: "couldn't check", never silence
    expect(within(screen.getByTestId("rent-tile-2_bedrooms")).getByText("Couldn't check the PUMA's figure today")).toBeTruthy();
  });

  it("says when the area figure could not be checked, and renders nothing without rent", () => {
    renderBlock(hood(rent({ community_area: null, unchecked: ["community_area_rent"] })));
    expect(within(screen.getByTestId("rent-tile-community-area")).getByText("Couldn't check today")).toBeTruthy();
    cleanup();
    const { container } = renderBlock(hood(null));
    expect(container.innerHTML).toBe("");
  });

  it("renders without a provenance map (a stored answer that predates it) and shows no caption", () => {
    render(<RentBlock data={hood(rent())} />);
    expect(screen.getByTestId("rent-tile-community-area").textContent).toContain("$2,054");
    expect(screen.queryAllByTestId("confidence-caption").length).toBe(0);
  });

  describe("the Assessor model (a separate series)", () => {
    const model = (over: Partial<AssessorModelRent> = {}): AssessorModelRent => ({
      community_area: 24, buildings: 427, priced: 412, units: 14210, households: 25407, coverage: 0.559,
      median_per_unit_month: 2300, year: "2024", cycle: "city reassessment", as_of: "2024-12-31", dataset: "csik-bsws", ...over,
    });
    const modelEntry = (over: Partial<Provenance> = {}) => entry({
      tier: "official_estimate", method_key: "government_model", method: "A government agency's model", scope: "community_area",
      geography: "West Town", period: "2024 city reassessment", as_of: "2024-12-31", as_of_basis: "tax_year", age_days: 667,
      precision: undefined, source_id: "artifact.assessor_model_by_area",
      coverage: { n: 412, share: 0.559, universe: "renter households with cash rent", unit: "buildings", sample: "area_sample" }, ...over,
    });
    const withModel = (m: AssessorModelRent | null, extra: Partial<RentEvidence> = {}) => rent({ assessor_model: m, ...extra });

    it("sits in its own section, named and dated, apart from the Census tiles", () => {
      renderBlock(hood(withModel(model())), { ...prov, "area.rent.assessor_model": modelEntry() });
      const acs = within(screen.getByTestId("rent-acs"));
      const sec = within(screen.getByTestId("rent-assessor"));
      expect(sec.getByText("Assessor model")).toBeTruthy();
      expect(sec.getByText(/2024 city reassessment model of apartment income, a separate series from the Census rents above\. Not an asking or achieved rent\./)).toBeTruthy();
      const tile = within(screen.getByTestId("rent-tile-assessor-model"));
      expect(tile.getByText(/\$2,300/)).toBeTruthy();
      expect(tile.getByText("Median of 412 apartment buildings, before vacancy")).toBeTruthy();
      const cap = tile.getByTestId("confidence-caption").textContent!;
      expect(cap).toContain("Government model");
      expect(cap).toContain("2024 city reassessment");
      expect(cap).toContain("56%");
      expect(cap).not.toMatch(/±|Census/);
      // the Census section never contains the Assessor tile, and has no bedroom-style Assessor figure
      expect(acs.queryByTestId("rent-tile-assessor-model")).toBeNull();
      expect(screen.getAllByTestId(/^rent-tile-/).filter((n) => /assessor/.test(n.getAttribute("data-testid")!)).length).toBe(1);
    });

    it("withholds an over-100% coverage as 'not comparable', with the reason, never silently", () => {
      const e = modelEntry({ confidence: "withheld", confidence_reasons: ["not_comparable"], coverage: { n: 67, share: 1.24, universe: "renter households with cash rent", unit: "buildings", sample: "area_sample" } });
      renderBlock(hood(withModel(model({ coverage: 1.24, priced: 67, median_per_unit_month: 2471 }))), { ...prov, "area.rent.assessor_model": e });
      const tile = within(screen.getByTestId("rent-tile-assessor-model"));
      expect(tile.queryByText(/\$2,471/)).toBeNull();
      expect(tile.getByText("—")).toBeTruthy();
      expect(tile.queryByText(/Median of/)).toBeNull();   // no description of a figure we are not showing
      expect(tile.getByText("Not shown: the model counts 124% of this area's renter households, so it is not a comparable set of homes.")).toBeTruthy();
    });

    it("says a small sample is withheld in buildings", () => {
      const e = modelEntry({ confidence: "withheld", confidence_reasons: ["small_sample"], coverage: { n: 12, share: 0.5, unit: "buildings", sample: "area_sample" } });
      renderBlock(hood(withModel(model({ priced: 12 }))), { ...prov, "area.rent.assessor_model": e });
      expect(screen.getByText("Not shown: only 12 buildings (needs 30).")).toBeTruthy();
    });

    it("says an area with no modeled apartments has none, and a failed read was not checked", () => {
      renderBlock(hood(withModel(model({ buildings: 0, priced: 0, units: 0, coverage: 0, median_per_unit_month: null }))));
      expect(within(screen.getByTestId("rent-tile-assessor-model")).getByText("The Assessor's model includes no apartment buildings in this area")).toBeTruthy();
      cleanup();
      renderBlock(hood(withModel(null, { unchecked: ["assessor_model"] })));
      expect(within(screen.getByTestId("rent-tile-assessor-model")).getByText("Couldn't check today")).toBeTruthy();
    });

    it("shows nothing for the series when the response has none (an older stored answer)", () => {
      renderBlock(hood(withModel(null)));
      expect(screen.queryByTestId("rent-assessor")).toBeNull();
      expect(screen.getByTestId("rent-acs")).toBeTruthy();
    });
  });
});
