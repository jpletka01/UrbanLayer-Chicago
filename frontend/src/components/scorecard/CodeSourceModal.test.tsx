import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CodeSourceModal } from "./CodeSourceModal";
import { ScorecardZoningCard } from "./ScorecardZoningCard";
import type { Provenance, ZoneDefinition } from "../../lib/api";
import { currency, lawrence, tod } from "./amendments.fixtures";

vi.mock("../../lib/api", async (orig) => {
  const mod = await orig<typeof import("../../lib/api")>();
  return { ...mod, fetchCodeSubsection: vi.fn() };
});
import { fetchCodeSubsection } from "../../lib/api";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const far = {
  section_id: "17-2-0304-A", article: "17-2-0300", article_title: "Bulk and density standards", heading: "Standards",
  paragraphs: ["17-2-0304-A Standards. All development in R districts is subject to the following maximum floor area ratio standards:"],
  tables: ["Columns: District | Maximum Floor Area Ratio*\nRow 1: District: RM4.5; Maximum Floor Area Ratio*: 1.70"],
  current_through: "2026-03-18", vintage_label: "Council Journal of March 18, 2026", source: "Municipal Code of Chicago",
};

describe("CodeSourceModal — the exact code text behind a number (V2)", () => {
  it("shows the subsection, its table and how current the code is", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue(far);
    render(<CodeSourceModal sectionId="17-2-0304-A" onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("code-vintage")).toBeTruthy());
    expect(screen.getByText(/§ 17-2-0304-A — Standards/)).toBeTruthy();
    expect(screen.getByText(/maximum floor area ratio standards/)).toBeTruthy();
    expect(screen.getByText("RM4.5")).toBeTruthy();
    expect(screen.getByText("1.70")).toBeTruthy();
    expect(screen.getByTestId("code-vintage").textContent).toContain("2026-03-18");
    expect(screen.getByTestId("code-vintage").textContent).toContain("may not be reflected");
  });

  it("says so when the text can't be loaded instead of showing nothing", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue(null);
    render(<CodeSourceModal sectionId="17-2-0304-A" onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/isn't available right now/)).toBeTruthy());
  });
});

describe("CodeSourceModal — amendments after the text's vintage (WS1 M3)", () => {
  it("shows an amber banner above a section an amendment touches", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue({ ...far, amended_since: [lawrence] });
    render(<CodeSourceModal sectionId="17-2-0304-A" onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("amended-since")).toBeTruthy());
    expect(screen.getByTestId("amended-since").textContent).toContain("O2026-0026042");
    expect(screen.getByTestId("code-vintage")).toBeTruthy();
  });

  it("no banner when nothing touches the section", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue({ ...far, amended_since: [] });
    render(<CodeSourceModal sectionId="17-2-0304-A" onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("code-vintage")).toBeTruthy());
    expect(screen.queryByTestId("amended-since")).toBeNull();
  });

  it("explains a section an amendment added instead of 'unavailable'", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue({ not_in_published_code: true, section_id: "17-3-0600", message: "x", added_by: [tod] });
    render(<CodeSourceModal sectionId="17-3-0600" onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("not-codified")).toBeTruthy());
    expect(screen.getByTestId("not-codified").textContent).toContain("SO2026-0025391");
    expect(screen.queryByText(/isn't available right now/)).toBeNull();
  });
});

const rm45: ZoneDefinition = {
  zone_class: "RM-4.5", name: "Residential Multi-Unit", code_section: "§17-2-0104", far: 1.7, max_height: "45–47 ft (varies by lot frontage)",
  lot_coverage: null, min_lot_sqft: 1650, min_lot_area_per_unit: 700, lot_area_note: "", uses: "", notes: "", is_fallback: false,
};
const dated = { kind: "code_text", source: "Title 17", record_id: null, url: null, as_of: "2026-03-18", effective_date: null, query_date: "2026-10-02" } as const;
const prov: Record<string, Provenance> = {
  "zoning.far": { ...dated, label: "FAR", section: "17-2-0304-A" },
  "zoning.max_height": { ...dated, label: "Height", section: "17-2-0311-A" },
  "zoning.min_lot_area_per_unit": { ...dated, label: "MLA", section: "17-2-0303-A" },
};

describe("ScorecardZoningCard — a standard links to its source", () => {
  it("each standard shows its code section and opens the viewer on click", async () => {
    vi.mocked(fetchCodeSubsection).mockResolvedValue(far);
    render(<ScorecardZoningCard def={rm45} provenance={prov} />);
    expect(screen.getByTestId("source-zoning.far").textContent).toBe("§17-2-0304-A");
    expect(screen.getByTestId("source-zoning.max_height").textContent).toBe("§17-2-0311-A");
    expect(screen.getByTestId("source-zoning.min_lot_area_per_unit").textContent).toBe("§17-2-0303-A");
    fireEvent.click(screen.getByTestId("source-zoning.far"));
    await waitFor(() => expect(screen.getByTestId("code-source")).toBeTruthy());
    expect(fetchCodeSubsection).toHaveBeenCalledWith("17-2-0304-A");
  });

  it("no source buttons on a payload without provenance (older API)", () => {
    render(<ScorecardZoningCard def={rm45} />);
    expect(screen.queryByTestId("source-zoning.far")).toBeNull();
  });

  it("the stamp carries the count of later amendments, and says nothing when the check is stale", () => {
    const { unmount } = render(<ScorecardZoningCard def={rm45} codeVintage={{ current_through: "2026-06-17", label: "x" }} codeCurrency={currency()} />);
    expect(screen.getByTestId("later-amendments").textContent).toContain("3 later amendments");
    unmount();
    render(<ScorecardZoningCard def={rm45} codeVintage={{ current_through: "2026-06-17", label: "x" }} codeCurrency={currency({ check_state: "unknown", since: null })} />);
    expect(screen.queryByTestId("later-amendments")).toBeNull();
  });
});
