import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DiscoveryPage from "./DiscoveryPage";
import { REG } from "./_fixtures";
import type { Diagnostics, PinsResponse, SearchResponse } from "./types";

const mocks = vi.hoisted(() => ({
  runSearch: vi.fn(),
  runPins: vi.fn(),
  loadRegistry: vi.fn(),
}));

vi.mock("./searchClient", () => ({
  runSearch: mocks.runSearch,
  runPins: mocks.runPins,
  exportCsv: vi.fn(),
}));
vi.mock("./registryClient", () => ({ loadRegistry: mocks.loadRegistry }));
vi.mock("../contexts/AuthContext", () => ({ useAuthContext: () => ({ user: null }) }));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("./../components/PageHeader", () => ({ default: () => <div /> }));
vi.mock("./../components/UpgradePrompt", () => ({ default: () => null }));
vi.mock("./chips", () => ({ Chips: () => null }));
vi.mock("./CoverageBanner", () => ({ CoverageBanner: () => null }));
vi.mock("./DiscoveryFilterPanel", () => ({ DiscoveryFilterPanel: () => null }));
vi.mock("./RecipeShelf", () => ({ RecipeShelf: () => null }));
vi.mock("./DiscoveryResults", () => ({
  DiscoveryResults: ({ response, rows, loading, unavailable }: {
    response: SearchResponse | null;
    rows: unknown[];
    loading: boolean;
    unavailable?: boolean;
  }) => (
    <div data-testid="results-state">
      {loading ? "loading" : unavailable ? "unavailable" : `${response?.dataVersion ?? "none"}:${rows.length}`}
    </div>
  ),
}));
vi.mock("./DiscoveryMap", () => ({
  DiscoveryMap: ({ points, status, visible }: { points: unknown[]; status: string; visible: boolean }) => (
    <div data-testid="map-state">{`${status}:${points.length}:${visible ? "visible" : "hidden"}`}</div>
  ),
}));

const diagnostics: Diagnostics = {
  resultCount: 1,
  broad: false,
  appliedFilters: 0,
  conflicts: [],
  droppedInvalid: [],
  excludedUnknown: {},
  mostRestrictive: [],
};

function response(dataVersion: string, pin: string, total = 1): SearchResponse {
  return {
    dataVersion,
    cqs: { filters: {}, sort: REG.defaultSort, scope: { mode: "all" }, meta: {} },
    result: {
      rows: total === 0 ? [] : [{
        pin, lat: 41.9, lon: -87.7, address: `${pin} address`, community_area: 24,
        land_use: "commercial", class: null, lot_sqft: null, bldg_sqft: null,
        year_built: null, units: null, assessed_value: null, price_per_sf: null,
        last_sale_price: null, last_sale_date: null, improvement_ratio: null,
        value_percentile: null, upside_score: null, is_teardown_candidate: false, sortValue: pin,
      }],
      total,
      nextOffset: null,
    },
    diagnostics: { ...diagnostics, resultCount: total },
  };
}

function pins(dataVersion: string, pin: string, total = 1): PinsResponse {
  return {
    dataVersion,
    total,
    truncated: false,
    points: total === 0 ? [] : [{ pin, lat: 41.9, lon: -87.7, upside: null, landUse: "commercial" }],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function readyPage() {
  render(<DiscoveryPage />);
  const button = screen.getByRole("button", { name: "Search" }) as HTMLButtonElement;
  await waitFor(() => expect(button.disabled).toBe(false));
  return {
    button,
    input: screen.getByRole("textbox", { name: "Describe what you're looking for" }),
  };
}

beforeEach(() => {
  mocks.runSearch.mockReset();
  mocks.runPins.mockReset();
  mocks.loadRegistry.mockReset().mockResolvedValue(REG);
});

afterEach(cleanup);

describe("DiscoveryPage issued-query pairing", () => {
  it("lets only the latest issued request commit when searches resolve out of order", async () => {
    const firstSearch = deferred<SearchResponse | null>();
    const firstPins = deferred<PinsResponse | null>();
    const secondSearch = deferred<SearchResponse | null>();
    const secondPins = deferred<PinsResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => firstSearch.promise).mockImplementationOnce(() => secondSearch.promise);
    mocks.runPins.mockImplementationOnce(() => firstPins.promise).mockImplementationOnce(() => secondPins.promise);
    const { button, input } = await readyPage();

    fireEvent.change(input, { target: { value: "first" } });
    fireEvent.click(button);
    fireEvent.change(input, { target: { value: "second" } });
    fireEvent.keyDown(input, { key: "Enter" });

    secondSearch.resolve(response("v2", "new"));
    secondPins.resolve(pins("v2", "new"));
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v2:1"));
    expect(screen.getByTestId("map-state").textContent).toContain("ready:1");

    firstSearch.resolve(response("v1", "old"));
    firstPins.resolve(pins("v1", "old"));
    await Promise.resolve();
    expect(screen.getByTestId("results-state").textContent).toBe("v2:1");
    expect(screen.getByTestId("map-state").textContent).toContain("ready:1");
  });

  it("keeps the canonical list but makes the map unavailable on a pins version mismatch", async () => {
    mocks.runSearch.mockResolvedValue(response("canonical", "one"));
    mocks.runPins.mockResolvedValue(pins("other", "wrong"));
    const { button } = await readyPage();
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("canonical:1"));
    expect(screen.getByTestId("map-state").textContent).toContain("unavailable:0");
  });

  it("rejects a non-truncated pins projection with missing entries", async () => {
    mocks.runSearch.mockResolvedValue(response("canonical", "one"));
    mocks.runPins.mockResolvedValue({ ...pins("canonical", "one"), points: [] });
    const { button } = await readyPage();
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("canonical:1"));
    expect(screen.getByTestId("map-state").textContent).toContain("unavailable:0");
  });

  it("keeps the canonical list when the pins request rejects", async () => {
    mocks.runSearch.mockResolvedValue(response("canonical", "one"));
    mocks.runPins.mockRejectedValue(new Error("map request failed"));
    const { button } = await readyPage();
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("canonical:1"));
    expect(screen.getByTestId("map-state").textContent).toContain("unavailable:0");
  });

  it("commits neither projection as successful when the canonical search fails", async () => {
    mocks.runSearch.mockResolvedValue(null);
    mocks.runPins.mockResolvedValue(pins("orphan", "wrong"));
    const { button } = await readyPage();
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("unavailable"));
    expect(screen.getByTestId("map-state").textContent).toContain("unavailable:0");
  });

  it("clears old dots as soon as a new issued search starts", async () => {
    mocks.runSearch.mockResolvedValueOnce(response("v1", "one"));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one"));
    const nextSearch = deferred<SearchResponse | null>();
    const nextPins = deferred<PinsResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => nextSearch.promise);
    mocks.runPins.mockImplementationOnce(() => nextPins.promise);
    const { button, input } = await readyPage();
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByTestId("map-state").textContent).toContain("ready:1"));

    fireEvent.change(input, { target: { value: "next" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByTestId("map-state").textContent).toContain("loading:0");
    expect(screen.getByTestId("results-state").textContent).toBe("loading");
  });

  it("keeps a successful zero-result query distinct from map failure", async () => {
    mocks.runSearch.mockResolvedValue(response("empty", "none", 0));
    mocks.runPins.mockResolvedValue(pins("empty", "none", 0));
    const { button } = await readyPage();
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("empty:0"));
    expect(screen.getByTestId("map-state").textContent).toContain("ready:0");
  });

  it("uses one content pane below xl and restores both panes at xl", async () => {
    await readyPage();
    expect(screen.getByTestId("discovery-list-pane").className).toContain("xl:flex");
    expect(screen.getByTestId("discovery-list-pane").className).not.toContain("md:flex");
    expect(screen.getByTestId("discovery-map-pane").className).toContain("xl:block");
    expect(screen.getByTestId("discovery-map-pane").className).not.toContain("md:block");
  });
});
