// Discovery in the new frame (Item 104): goals, the one search box, quick filters, the list and its cards. The search
// client is mocked; the map is a stand-in that records what it was handed (jsdom has no WebGL).
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
const mapProps = vi.hoisted(() => ({ last: null as null | Record<string, unknown> }));
vi.mock("./ExploreMap", () => ({
  ExploreMap: (props: Record<string, unknown>) => {
    mapProps.last = props;
    return <div data-testid="explore-map" />;
  },
}));
vi.mock("../../lib/useIsPhone", () => ({ useIsPhone: () => false }));
vi.mock("./discoveryData", async (orig) => ({
  ...(await orig<typeof import("./discoveryData")>()),
  fetchLotShape: () => Promise.resolve(null),
  fetchLotContext: () => Promise.resolve(null),
  useDistribution: () => null,
}));
vi.mock("../frame/AppFrame", () => ({ AppFrame: ({ children, bar }: { children: React.ReactNode; bar?: React.ReactNode }) => <div className="ui-next">{bar}{children}</div> }));

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
        room_sqft: 10050, bldg_sqft_source: "commercial_valuation", warning: { kind: "pending_rezoning", detail: null },
      }],
      total: 1,
      nextOffset: null,
    },
    diagnostics,
    pins: { dataVersion: "d1", total: 1, truncated: false, points: [{ pin: "14313250010000", lat: 41.9, lon: -87.7, upside: null, landUse: "commercial" }] },
    areaCounts: { "24": 1 },
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
    const goals = await screen.findByTestId("goals");
    fireEvent.click(within(goals).getAllByRole("button")[0]);
    const list = await screen.findByTestId("next-results");
    const card = within(list).getByRole("button");
    expect(card.textContent).toContain("1601 N Milwaukee Ave");
    expect(card.textContent).toContain("B3-2");
    expect(card.textContent).toMatch(/room to build/i);
    expect(card.textContent).toContain("Built 14,700");
    expect(card.textContent).toContain("10,050 sq ft");
    expect(card.textContent).toContain("Rezoning filed");
    expect(card.textContent).toContain("Assessor's commercial records");
    // The search asked for the map's points and the area counts in the same evaluation.
    expect(mocks.runSearch.mock.calls[0][0]).toMatchObject({ includePins: true, includeAreaCounts: true });
    // The map outlines the matches by PIN10 and labels the areas.
    await waitFor(() => expect(mapProps.last?.matches).toEqual(["1431325001"]));
    expect(mapProps.last?.areaCounts).toEqual({ "24": 1 });
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
    const box = screen.getByLabelText("Search an address, a neighborhood or describe the lots");
    fireEvent.change(box, { target: { value: "lots in a TIF" } });
    fireEvent.submit(box.closest("form")!);
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalled());
    expect(mocks.runSearch.mock.calls[0][0].text).toBe("lots in a TIF");
    expect(mocks.runSearch.mock.calls[0][0].sort).toEqual({ key: "room_to_build", dir: "desc" });
  });

  it("quick filters before a search dim the map: the server evaluates them, the map gets the matches", async () => {
    mocks.loadRegistry.mockResolvedValue(registry);
    mocks.runSearch.mockResolvedValue(response());
    render(<MemoryRouter><DiscoveryNextPage /></MemoryRouter>);
    await waitFor(() => expect(mapProps.last).not.toBeNull());
    expect(mapProps.last?.matches).toBeNull();
    (mapProps.last!.onView as (v: unknown) => void)({ bbox: [-87.7, 41.9, -87.6, 41.95], zoom: 15, center: [-87.65, 41.92] });
    fireEvent.click(await screen.findByRole("button", { name: "Vacant" }));
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalled(), { timeout: 2000 });
    expect(mocks.runSearch.mock.calls[0][0]).toMatchObject({
      panelState: { vacancy: { kind: "flag", value: true } }, scope: { mode: "viewport", bbox: [-87.7, 41.9, -87.6, 41.95] }, limit: 1,
    });
    await waitFor(() => expect(mapProps.last?.matches).toEqual(["1431325001"]));
    expect(screen.getByTestId("search-view").textContent).toContain("Search 1 lot in view");
  });

  it("a filter group opens a panel of plain choices; Show applies them as one search", async () => {
    mocks.loadRegistry.mockResolvedValue({
      ...registry,
      filters: [...registry.filters, {
        id: "density_band", category: "zoning_dev", kind: "range", field: "density_band", unknownPolicy: "exclude",
        range: { domain: [0, 16], step: 0.1, boundMode: "both", display: "far" },
      }],
      populatedFields: ["land_use", "tif", "density_band"],
    } as Registry);
    mocks.runSearch.mockResolvedValue(response());
    render(<MemoryRouter><DiscoveryNextPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Zoning/ }));
    const panel = await screen.findByTestId("group-panel");
    fireEvent.click(within(panel).getByRole("button", { name: /Apartments/ }));
    await waitFor(() => expect(within(panel).getByTestId("filters-show").textContent).toMatch(/Show 1 lot/));
    fireEvent.click(within(panel).getByTestId("filters-show"));
    await waitFor(() => expect(mocks.runSearch.mock.calls.some((c) => c[0].includePins && c[0].panelState.density_band)).toBe(true));
    const applied = mocks.runSearch.mock.calls.find((c) => c[0].includePins)![0];
    expect(applied.panelState.density_band).toEqual({ kind: "range", min: 2, max: 5 });
    expect(applied.sort).toEqual({ key: "room_to_build", dir: "desc" });
  });

  it("says so when Discovery can't load", async () => {
    mocks.loadRegistry.mockResolvedValue(null);
    render(<MemoryRouter><DiscoveryNextPage /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
