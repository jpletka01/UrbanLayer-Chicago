import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
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
    expect(box.textContent).toContain("3,191 sq ft ÷ 700 sq ft per unit = 4.6 → 4 units");
    expect(box.textContent).toContain("one limit"); // never presented as the final unit count
  });

  it("renders no yield block (and no per-unit row) when the district has none", () => {
    const pd: ZoneDefinition = { ...rm45, zone_class: "PD 835", far: null, max_height: null, min_lot_area_per_unit: null };
    render(<ScorecardZoningCard def={pd} unitYield={null} />);
    expect(screen.queryByTestId("unit-yield")).toBeNull();
    expect(screen.queryByText("Min lot area per unit")).toBeNull();
  });

  it("shows the 606-style exemption note when the district has one", () => {
    render(<ScorecardZoningCard def={{ ...rm45, zone_class: "RS-3", lot_area_note: "Reduced to 1,500 sq ft per unit in the 606 district." }} />);
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
    const stamps = screen.getByTestId("freshness-stamps");
    expect(stamps.textContent).toContain("Zoning record last updated");
    expect(stamps.textContent).toContain("2021-10-27");
    expect(stamps.textContent).toContain("Municipal Code current through");
    expect(stamps.textContent).toContain("2026-03-18");
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

  it("shows no stamps when the API supplies none (older payloads)", () => {
    render(<ScorecardZoningCard def={rm45} />);
    expect(screen.queryByTestId("freshness-stamps")).toBeNull();
  });
});
