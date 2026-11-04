import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { ScorecardZoningCard } from "./ScorecardZoningCard";
import type { ZoneDefinition } from "../../lib/api";
import type { UnitYield } from "../../lib/types";

afterEach(cleanup);

const rm45: ZoneDefinition = {
  zone_class: "RM-4.5",
  name: "Residential Multi-Unit",
  code_section: "§17-2-0104",
  far: 1.7,
  max_height: "45–47 ft (varies by lot frontage)",
  lot_coverage: null,
  min_lot_sqft: 1650,
  min_lot_area_per_unit: 700,
  lot_area_note: "",
  uses: "Detached houses, two-flats, townhouses, multi-unit buildings",
  notes: "",
  is_fallback: false,
};

const yieldRm45: UnitYield = {
  units: 4,
  lot_sqft: 3191,
  min_lot_area_per_unit: 700,
  arithmetic: "3,191 sq ft ÷ 700 sq ft per unit = 4.6 → 4 units",
  basis: "Minimum lot area per dwelling unit for the district",
  caveat: "Lot area per unit only: ...",
  lot_area_note: "",
};

describe("ScorecardZoningCard — the binding number (F3)", () => {
  it("shows min lot area per unit and the unit yield with its arithmetic and caveat", () => {
    render(<ScorecardZoningCard def={rm45} unitYield={yieldRm45} />);
    expect(screen.getByText("Min lot area per unit")).toBeTruthy();
    expect(screen.getByText("700 ft²")).toBeTruthy();
    const box = screen.getByTestId("unit-yield");
    expect(box.textContent).toContain("Max units by lot area");
    // the arithmetic and the caveat sit behind the row's Explain tool (decision Item 54)
    fireEvent.click(screen.getByRole("button", { name: "What this means: Max units by lot area" }));
    const explain = screen.getByTestId("unit-yield-explain");
    expect(explain.textContent).toContain("3,191 sq ft ÷ 700 sq ft per unit = 4.6 → 4 units");
    expect(explain.textContent).toContain("one limit"); // never presented as the final unit count
  });

  it("renders no yield block (and no per-unit row) when the district has none", () => {
    const pd: ZoneDefinition = { ...rm45, zone_class: "PD 835", far: null, max_height: null, min_lot_area_per_unit: null };
    render(<ScorecardZoningCard def={pd} unitYield={null} />);
    expect(screen.queryByTestId("unit-yield")).toBeNull();
    expect(screen.queryByText("Min lot area per unit")).toBeNull();
  });

  it("says when the 606 rule raised the yield, and when the 606 check failed (WS5 PR1)", () => {
    const rs3: ZoneDefinition = { ...rm45, zone_class: "RS-3", min_lot_area_per_unit: 2500 };
    render(<ScorecardZoningCard def={rs3} unitYield={{ ...yieldRm45, units: 2, base_units: 1, rule_606: "applied" }} />);
    expect(screen.getByTestId("unit-yield-606").textContent).toContain("raises this from 1 to 2");
    cleanup();
    render(<ScorecardZoningCard def={rs3} unitYield={{ ...yieldRm45, units: 1, base_units: 1, rule_606: "unchecked" }} />);
    expect(screen.getByTestId("unit-yield-606-unchecked").textContent).toContain("could not check");
    expect(screen.queryByTestId("unit-yield-606")).toBeNull();
    cleanup();
    render(<ScorecardZoningCard def={rs3} unitYield={{ ...yieldRm45, units: 3, base_units: 3, rule_606: "applied" }} />);
    expect(screen.queryByTestId("unit-yield-606")).toBeNull(); // in the district, but the rule changed nothing
  });

  it("shows the 606-style exemption note when the district has one", () => {
    render(<ScorecardZoningCard def={{ ...rm45, zone_class: "RS-3", lot_area_note: "Reduced to 1,500 sq ft per unit in the 606 district." }} />);
    fireEvent.click(screen.getByRole("button", { name: "What this means: Zoning" }));
    expect(screen.getByText(/1,500 sq ft per unit in the 606/)).toBeTruthy();
  });

  it("stamps the card with the zoning record's date and the Municipal Code's vintage", () => {
    render(
      <ScorecardZoningCard
        def={rm45}
        freshness={{ ordinance_num: "A7210", ordinance_date: "2007-09-05", map_updated: "2021-10-27", clerk_url: null, recently_rezoned: false }}
        codeVintage={{ current_through: "2026-03-18", label: "Council Journal of March 18, 2026" }}
      />,
    );
    // the dates sit behind ⏱ (decision Item 51); the stamps themselves are unchanged
    fireEvent.click(screen.getByRole("button", { name: "Dates: Zoning" }));
    const stamps = screen.getByTestId("freshness-stamps");
    expect(stamps.textContent).toContain("Zoning record last updated");
    expect(stamps.textContent).toContain("Oct 27, 2021"); // readable, like every other date on the page
    expect(stamps.textContent).toContain("Municipal Code current through");
    expect(stamps.textContent).toContain("Mar 18, 2026");
    expect(screen.queryByTestId("recently-rezoned")).toBeNull(); // 2007 is not recent
  });

  it("flags a recent rezoning with the ordinance date and a link to the clerk's record (kit P7)", () => {
    render(
      <ScorecardZoningCard
        def={{ ...rm45, zone_class: "RT-4" }}
        freshness={{
          ordinance_num: "O2026-0025358", ordinance_date: "2026-06-16", map_updated: "2026-08-21",
          clerk_url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=abc", recently_rezoned: true,
        }}
      />,
    );
    const note = screen.getByTestId("recently-rezoned");
    expect(note.textContent).toContain("2026-06-16");
    const link = note.querySelector("a");
    expect(link?.getAttribute("href")).toContain("chicityclerkelms.chicago.gov");
    expect(link?.textContent).toContain("O2026-0025358");
    expect(note.textContent).not.toContain("23082T1"); // the application number is never shown as the ordinance
  });

  it("says a passed rezoning listing this address isn't on the City's map yet, with the ordinance linked (WS1 M5)", () => {
    render(
      <ScorecardZoningCard
        def={{ ...rm45, zone_class: "B3-2" }}
        passedNotOnMap={[{
          record: "O2026-0028350", passed_on: "2026-10-14", url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=EBBB",
          segment: "6701-6731 S Western Ave", maps: "16-H", matched_by: "pin",
        }]}
      />,
    );
    const box = screen.getByTestId("passed-not-on-map");
    expect(box.textContent).toContain("A rezoning listing this address passed Council on Oct 14, 2026 (O2026-0028350)");
    expect(box.textContent).toContain("hasn't been updated for it yet");
    expect(box.textContent).toContain("the district the map still shows");
    expect(box.textContent).not.toMatch(/was rezoned|rezoned to/);
    expect(box.querySelector("a")?.getAttribute("href")).toContain("chicityclerkelms.chicago.gov");
  });

  it("adds the AI-read new district, labeled, only when the backend sends it (WS1 M6)", () => {
    const hit = {
      record: "O2026-0028350", passed_on: "2026-10-14", url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=EBBB",
      segment: "6701-6731 S Western Ave", maps: "16-H", matched_by: "pin" as const,
    };
    const { rerender } = render(<ScorecardZoningCard def={{ ...rm45, zone_class: "C2-2" }} passedNotOnMap={[hit]} />);
    expect(screen.queryByTestId("passed-district")).toBeNull();
    rerender(<ScorecardZoningCard def={{ ...rm45, zone_class: "C2-2" }} passedNotOnMap={[{ ...hit, from_district: "C2-2", to_district: "B2-5", district_source: "ai_read_ordinance" }]} />);
    const text = screen.getByTestId("passed-district").textContent ?? "";
    expect(text).toContain("changes it from C2-2 to B2-5");
    expect(text).toContain("read by AI");
  });

  it("shows nothing about it without a listing", () => {
    render(<ScorecardZoningCard def={rm45} passedNotOnMap={[]} />);
    expect(screen.queryByTestId("passed-not-on-map")).toBeNull();
  });

  it("shows no stamps when the API supplies none (older payloads)", () => {
    render(<ScorecardZoningCard def={rm45} />);
    expect(screen.queryByTestId("freshness-stamps")).toBeNull();
  });
});

describe("ScorecardZoningCard — typical lot for this district (WS5 PR3, Item 66)", () => {
  const lotDef = { zone_class: "RS-3", name: "Residential Single-Unit (Detached House)", far: 0.9 } as unknown as ZoneDefinition;
  const lot = { n: 4210, p25_lot_sqft: 3000, median_lot_sqft: 3125, p75_lot_sqft: 3750 };

  it("shows one figure and keeps the sample and this lot behind the Info tool", () => {
    render(<ScorecardZoningCard def={lotDef} typicalLot={lot} lotSqft={3750} areaName="Logan Square" />);
    const row = screen.getByTestId("typical-lot");
    expect(row.textContent).toContain("Typical lot here");
    expect(row.textContent).toContain("3,125 ft²");
    expect(row.textContent).not.toContain("4,210");
    fireEvent.click(within(row).getByRole("button", { name: "What this means: Typical lot here" }));
    const explain = screen.getByTestId("typical-lot-explain").textContent ?? "";
    expect(explain).toContain("4,210 RS-3 lots in Logan Square");
    expect(explain).toContain("3,000 ft² to 3,750 ft²");
    expect(explain).toContain("This lot: 3,750 ft².");
  });

  it("renders nothing when the district has too few lots", () => {
    render(<ScorecardZoningCard def={lotDef} typicalLot={null} />);
    expect(screen.queryByTestId("typical-lot")).toBeNull();
  });
});

describe("ScorecardZoningCard — the RS-3 block-face rule (Item 67)", () => {
  const rs3 = { zone_class: "RS-3", name: "Residential Single-Unit (Detached House)", far: 0.9 } as unknown as ZoneDefinition;
  const yieldWith = (over: Partial<UnitYield>): UnitYield => ({
    units: 2, base_units: 1, lot_sqft: 3125, min_lot_area_per_unit: 1500, arithmetic: "3,125 sq ft ÷ 2,500 …",
    basis: "", caveat: "", lot_area_note: "", rule_606: "not_in_district", rule_block_face: "met", ...over,
  });

  it("says the block face raised the number, once", () => {
    render(<ScorecardZoningCard def={rs3} unitYield={yieldWith({})} />);
    expect(screen.getByTestId("unit-yield-block-face").textContent).toContain("from 1 to 2");
    expect(screen.queryByTestId("unit-yield-606")).toBeNull();
  });

  it("an unchecked face says so; a face that isn't met adds no line", () => {
    render(<ScorecardZoningCard def={rs3} unitYield={yieldWith({ units: 1, rule_block_face: "unchecked" })} />);
    expect(screen.getByTestId("unit-yield-block-face-unchecked")).toBeTruthy();
    cleanup();
    render(<ScorecardZoningCard def={rs3} unitYield={yieldWith({ units: 1, rule_block_face: "not_met" })} />);
    expect(screen.queryByTestId("unit-yield-block-face")).toBeNull();
    expect(screen.queryByTestId("unit-yield-block-face-unchecked")).toBeNull();
  });

  it("the 606 district comes first: no block-face line when 606 applied", () => {
    render(<ScorecardZoningCard def={rs3} unitYield={yieldWith({ rule_606: "applied" })} />);
    expect(screen.queryByTestId("unit-yield-block-face")).toBeNull();
  });
});
