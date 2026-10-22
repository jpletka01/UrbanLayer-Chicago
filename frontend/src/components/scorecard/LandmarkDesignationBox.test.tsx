import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LandmarkDesignationBox } from "./LandmarkDesignationBox";
import { ScorecardRegulatoryCard } from "./ScorecardRegulatoryCard";
import type { PassedLandmarkDesignation, RegulatorySummary } from "../../lib/types";

afterEach(cleanup);

const building: PassedLandmarkDesignation = {
  record: "O2026-0026117", passed_on: "2026-07-15", url: "https://clerk/y", name: "Chicago Daily News Building",
  kind: "building", segment: "2 N Riverside Plz", map_checked: true, matched_by: "pin",
};
const district: PassedLandmarkDesignation = {
  record: "O2026-0027059", passed_on: "2026-09-23", url: "https://clerk/x", name: "Bryn Mawr Avenue District",
  kind: "district", segment: "900-1199 W Bryn Mawr Ave", map_checked: true, matched_by: "pin",
};

describe("LandmarkDesignationBox — what the ordinance lists, never that the parcel is a landmark", () => {
  it("a building: listing this address, the date, the record, the map's answer and the review", () => {
    render(<LandmarkDesignationBox hits={[building]} />);
    const box = screen.getByTestId("landmark-designation-passed");
    const text = box.textContent ?? "";
    expect(text).toContain("Chicago Daily News Building (O2026-0026117) passed Council on Jul 15, 2026 and lists this address");
    expect(text).toContain("didn't show this parcel as a landmark when checked");
    expect(text).toContain("§2-120-740");
    expect(text).not.toMatch(/is a (Chicago )?Landmark|has been designated/i);
    expect(box.querySelector("a")?.getAttribute("href")).toBe("https://clerk/y");
  });

  it("a district: names the blocks and says the boundary is in the ordinance", () => {
    render(<LandmarkDesignationBox hits={[district]} />);
    const text = screen.getByTestId("landmark-designation-passed").textContent ?? "";
    expect(text).toContain("names the blocks of 900-1199 W Bryn Mawr Ave");
    expect(text).toContain("can't say whether this parcel is inside it");
  });

  it("when the landmark layers didn't answer it does not claim the map says no", () => {
    render(<LandmarkDesignationBox hits={[{ ...building, map_checked: false }]} />);
    const text = screen.getByTestId("landmark-designation-passed").textContent ?? "";
    expect(text).toContain("couldn't be checked today");
    expect(text).not.toContain("didn't show this parcel");
  });

  it("the title's generic word 'building' is not quoted as a name", () => {
    render(<LandmarkDesignationBox hits={[{ ...building, name: "building", record: "O2026-0023266" }]} />);
    expect(screen.getByTestId("landmark-designation-passed").textContent).toContain("O2026-0023266 passed Council");
  });

  it("renders nothing without a listing", () => {
    const { container } = render(<LandmarkDesignationBox hits={[]} />);
    expect(container.firstChild).toBeNull();
    cleanup();
    expect(render(<LandmarkDesignationBox hits={undefined} />).container.firstChild).toBeNull();
  });
});

describe("the Regulatory card with a passed designation", () => {
  const reg = { overlays: [], unchecked_overlays: [], data_gaps: [], brownfield_sites: [] } as unknown as RegulatorySummary;

  it("shows the box and does not say there are no overlays", () => {
    render(<ScorecardRegulatoryCard data={reg} designations={[building]} />);
    expect(screen.getByTestId("landmark-designation-passed")).toBeTruthy();
    expect(screen.queryByText(/no overlay|None of the/i)).toBeNull();
  });

  it("without one, the card is as it was", () => {
    render(<ScorecardRegulatoryCard data={reg} />);
    expect(screen.queryByTestId("landmark-designation-passed")).toBeNull();
  });
});
