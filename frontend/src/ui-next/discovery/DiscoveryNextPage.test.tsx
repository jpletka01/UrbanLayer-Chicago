// One Discovery flow in the new frame: search, results, open a Profile. The search client is mocked.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { REG } from "../../discovery/_fixtures";
import type { Diagnostics, Registry, SearchResponse } from "../../discovery/types";
import { axeViolations } from "../test/axe";
import DiscoveryNextPage from "./DiscoveryNextPage";

const mocks = vi.hoisted(() => ({ runSearch: vi.fn(), previewText: vi.fn(), loadRegistry: vi.fn() }));
vi.mock("../../discovery/searchClient", () => ({
  runSearch: mocks.runSearch, runPins: () => Promise.resolve(null), previewText: mocks.previewText, exportCsv: vi.fn(),
}));
vi.mock("../../discovery/registryClient", () => ({ loadRegistry: mocks.loadRegistry }));
vi.mock("../../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("../frame/AppFrame", () => ({ AppFrame: ({ children }: { children: React.ReactNode }) => <div className="ui-next">{children}</div> }));

const diagnostics: Diagnostics = {
  resultCount: 1, broad: false, appliedFilters: 1, conflicts: [], droppedInvalid: [], excludedUnknown: {}, mostRestrictive: [],
};
const registry: Registry = { ...REG, populatedFields: ["land_use", "tif"], recipeCounts: { vacant_mf: 12 } };

function response(): SearchResponse {
  return {
    dataVersion: "d1",
    cqs: { filters: {}, sort: REG.defaultSort, scope: { mode: "all" }, meta: {} },
    result: {
      rows: [{
        pin: "14313250010000", lat: 41.9, lon: -87.7, address: "1601 N MILWAUKEE AVE", community_area: 24,
        land_use: "commercial", class: "5-17", lot_sqft: 11250, bldg_sqft: 14700, year_built: 1920, units: 4,
        assessed_value: 250000, price_per_sf: 300, last_sale_price: 1200000, last_sale_date: "2019-06-24",
        improvement_ratio: 0.5, value_percentile: null, upside_score: null, is_teardown_candidate: false,
        zone_class: "B3-2", allowed_far: 2.2, nominal_assessment: false, sortValue: null,
      }],
      total: 1,
      nextOffset: null,
    },
    diagnostics,
  };
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Discovery in the new frame", () => {
  it("runs a Try goal, shows cards with icons and labels, and a card opens its Profile", async () => {
    mocks.loadRegistry.mockResolvedValue(registry);
    mocks.runSearch.mockResolvedValue(response());
    const { container } = render(
      <MemoryRouter initialEntries={["/discovery"]}>
        <Routes>
          <Route path="/discovery" element={<DiscoveryNextPage />} />
          <Route path="/scorecard" element={<Where />} />
        </Routes>
      </MemoryRouter>,
    );
    const chip = await screen.findByRole("button", { name: /vacant_mf|Vacant/i });
    fireEvent.click(chip);
    const list = await screen.findByTestId("next-results");
    const card = within(list).getByRole("button");
    expect(card.textContent).toContain("1601 N Milwaukee Ave");
    expect(card.textContent).toContain("B3-2");
    expect(card.textContent).toContain("Room to build");
    expect(card.textContent).toContain("10,050 sq ft");
    expect(await axeViolations(container)).toEqual([]);
    fireEvent.click(card);
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/scorecard?pin=14313250010000&address=1601+N+Milwaukee+Ave"));
  });

  it("a typed description searches on Enter through the same engine", async () => {
    mocks.loadRegistry.mockResolvedValue(registry);
    mocks.previewText.mockResolvedValue({ understood: true, filters: { tif: { kind: "flag", value: true } }, residual: [] });
    mocks.runSearch.mockResolvedValue(response());
    render(<MemoryRouter><DiscoveryNextPage /></MemoryRouter>);
    await waitFor(() => expect(mocks.loadRegistry).toHaveBeenCalled());
    const box = screen.getByLabelText("Describe the lots");
    fireEvent.change(box, { target: { value: "lots in a TIF" } });
    fireEvent.submit(box.closest("form")!);
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalled());
    expect(mocks.runSearch.mock.calls[0][0].text).toBe("lots in a TIF");
  });

  it("says so when Discovery can't load", async () => {
    mocks.loadRegistry.mockResolvedValue(null);
    render(<MemoryRouter><DiscoveryNextPage /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
