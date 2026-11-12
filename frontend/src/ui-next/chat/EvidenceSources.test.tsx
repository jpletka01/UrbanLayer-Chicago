// The Sources tab (wireframe v2): a code section opens on its highlighted passage, a code table on the district's
// row with the whole table one click away, and a crime record shows its split, its key and "Show on map".
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Message } from "../../lib/types";
import { EvidenceSources } from "./EvidenceSources";
import { axeViolations } from "../test/axe";

const LOT = { latitude: 41.9278, longitude: -87.7105, label: "2541 N Spaulding Ave" };
const MSG: Message = {
  role: "assistant",
  content: "RS-3 needs 2,500 sq ft of lot per unit [1]. A coach house could add one dwelling unit in an ADU-eligible area [2]. Crime is about average [data:crime].",
  context: {
    resolved_address: "2541 N Spaulding Ave",
    community_area_name: "Logan Square",
    property: { pin14: "13264210060000", land_sqft: 3125, units: 2, sales_history: [] },
    crime_last_90d: { total: 386, arrest_rate: 0.1, by_type: {} },
    code_chunks: [
      { text: "| District | Min lot area per unit | Max FAR |\n|---|---|---|\n| RS-2 | 5,000 | 0.65 |\n| RS-3 | 2,500 | 0.9 |", section: "17-2-0300", section_title: "Bulk", source_document: "", subsection: null, score: 1, cross_references: [] },
      { text: "A. Purpose. The ADU overlay allows units. C. Coach houses. In an ADU-eligible area one coach house with one dwelling unit may be established. E. Owners must live on the lot.", section: "17-7-0570", section_title: "ADU", source_document: "", subsection: null, score: 1, cross_references: [] },
    ],
  } as never,
  mapData: {
    crimes: [
      { latitude: LOT.latitude + 0.001, longitude: LOT.longitude, primary_type: "BATTERY", date: "2026-11-01", description: "", arrest: true },
      { latitude: LOT.latitude + 0.002, longitude: LOT.longitude, primary_type: "THEFT", date: "2026-11-02", description: "", arrest: false },
    ],
    requests_311: [], building_permits: [], queried_address: LOT,
  },
};

afterEach(cleanup);

describe("the Sources tab", () => {
  it("opens a cited code section on its highlighted passage", async () => {
    const { container } = render(<EvidenceSources message={MSG} openN={2} onShowOnMap={vi.fn()} />);
    expect(screen.getByTestId("code-passage").textContent).toContain("one coach house with one dwelling unit");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("trims a code table to the district's row, with the whole table one click away", () => {
    render(<EvidenceSources message={MSG} openN={1} onShowOnMap={vi.fn()} />);
    const table = screen.getByTestId("code-table");
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    fireEvent.click(screen.getByText("Show the whole table (2 rows)"));
    expect(within(screen.getByTestId("code-table")).getAllByRole("row")).toHaveLength(3);
  });

  it("shows crime near the lot split violent and property, and puts violent incidents on the map", () => {
    const show = vi.fn();
    render(<EvidenceSources message={MSG} openN={5} onShowOnMap={show} />);
    const row = screen.getByTestId("source-crime");
    expect(row.textContent).toContain("Within ½ mile");
    expect(row.textContent).toContain("Arrest made in 1 of 2");
    fireEvent.click(within(row).getByTestId("show-crime-on-map"));
    expect(show).toHaveBeenCalledWith("crime");
  });
});
