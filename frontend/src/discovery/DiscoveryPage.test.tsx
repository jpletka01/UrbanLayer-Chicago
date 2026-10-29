import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
vi.mock("./chips", () => ({
  Chips: ({ items, onRemove, onRestore }: {
    items: Array<{ id: string; state: string }>;
    onRemove: (id: string) => void;
    onRestore: (id: string) => void;
  }) => (
    <div data-testid="chips">
      {items.map((item) => (
        <span key={item.id} data-testid={`chip-${item.id}`} data-state={item.state}>
          {item.state === "removed" ? (
            <button type="button" onClick={() => onRestore(item.id)}>{`restore-${item.id}`}</button>
          ) : (
            <button type="button" onClick={() => onRemove(item.id)}>{`remove-${item.id}`}</button>
          )}
        </span>
      ))}
    </div>
  ),
}));
vi.mock("./CoverageBanner", () => ({ CoverageBanner: () => null }));
vi.mock("./DiscoveryFilterPanel", () => ({
  DiscoveryFilterPanel: ({ state, onChange }: {
    state: Record<string, unknown>;
    onChange: (id: string, predicate: unknown) => void;
  }) => (
    <div data-testid="panel" data-keys={Object.keys(state).sort().join(",")}>
      <button type="button" onClick={() => onChange("tif", { kind: "flag", value: true })}>panel-add-tif</button>
    </div>
  ),
}));
vi.mock("./RecipeShelf", () => ({ RecipeShelf: () => null }));
vi.mock("./DiscoveryResults", () => ({
  DiscoveryResults: ({ response, rows, loading, unavailable, refreshFailed, onRetry }: {
    response: SearchResponse | null;
    rows: unknown[];
    loading: boolean;
    unavailable?: boolean;
    refreshFailed?: boolean;
    onRetry?: () => void;
  }) => (
    <div>
      <div
        data-testid="results-state"
        data-loading={String(loading)}
        data-stale={String(loading && response !== null)}
        data-failed={String(!!refreshFailed)}
      >
        {unavailable ? "unavailable" : `${response?.dataVersion ?? "none"}:${rows.length}`}
      </div>
      {refreshFailed && <button type="button" onClick={onRetry}>mock-retry</button>}
    </div>
  ),
}));
vi.mock("./DiscoveryMap", () => ({
  DiscoveryMap: ({ points, status, visible, stale }: { points: unknown[]; status: string; visible: boolean; stale?: boolean }) => (
    <div data-testid="map-state">{`${status}:${points.length}:${visible ? "visible" : "hidden"}:${stale ? "stale" : "fresh"}`}</div>
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

function response(
  dataVersion: string,
  pin: string,
  total = 1,
  filters: SearchResponse["cqs"]["filters"] = {},
): SearchResponse {
  return {
    dataVersion,
    cqs: { filters, sort: REG.defaultSort, scope: { mode: "all" }, meta: {} },
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

const THREE = {
  land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" },
  tif: { predicate: { kind: "flag", value: true }, source: "user" },
  lot_size: { predicate: { kind: "range", min: 3000 }, source: "user" },
} as const;

async function pageWithResults() {
  mocks.runSearch.mockResolvedValueOnce(response("v1", "one", 1, { ...THREE }));
  mocks.runPins.mockResolvedValueOnce(pins("v1", "one"));
  const ready = await readyPage();
  fireEvent.click(ready.button);
  await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v1:1"));
  mocks.runSearch.mockClear();
  mocks.runPins.mockClear();
  return ready;
}

describe("DiscoveryPage Phase 0: draft edits, then one Update results", () => {
  it("never blanks the page while chips are removed, requests nothing, then sends one pair", async () => {
    const { button } = await pageWithResults();
    const summaryBefore = screen.getByTestId("discovery-summary").textContent;

    fireEvent.click(screen.getByText("remove-land_use"));
    fireEvent.click(screen.getByText("remove-tif"));
    fireEvent.click(screen.getByText("remove-lot_size"));

    // chips stay (struck through, restorable); results, count and summary are untouched
    expect(screen.getByTestId("chip-land_use").getAttribute("data-state")).toBe("removed");
    expect(screen.getByTestId("chip-tif").getAttribute("data-state")).toBe("removed");
    expect(screen.getByTestId("results-state").textContent).toBe("v1:1");
    expect(screen.getByTestId("map-state").textContent).toContain("ready:1");
    expect(screen.getByTestId("discovery-summary").textContent).toBe(summaryBefore);
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(mocks.runPins).not.toHaveBeenCalled();
    expect(button.disabled).toBe(false);

    mocks.runSearch.mockResolvedValueOnce(response("v1", "two"));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "two"));
    fireEvent.click(screen.getByTestId("discovery-update-results"));
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    expect(mocks.runPins).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v1:1"));
    expect(screen.queryByTestId("discovery-update-results")).toBeNull();
    expect(screen.queryByTestId("chip-land_use")).toBeNull();
  });

  it("offers one-click restore of a removed chip", async () => {
    await pageWithResults();
    fireEvent.click(screen.getByText("remove-tif"));
    expect(screen.getByTestId("discovery-update-results").textContent).toBe("Update results (1)");
    fireEvent.click(screen.getByText("restore-tif"));
    expect(screen.getByTestId("chip-tif").getAttribute("data-state")).toBe("applied");
    expect(screen.queryByTestId("discovery-update-results")).toBeNull();
  });

  it("shows a pending count for panel edits and Clear all, and applies them with Enter or Search", async () => {
    const { button, input } = await pageWithResults();
    fireEvent.click(screen.getByText("panel-add-tif")); // already there: no change
    expect(screen.queryByTestId("discovery-update-results")).toBeNull();
    fireEvent.click(screen.getByText(/Clear all/));
    expect(screen.getByTestId("discovery-update-results").textContent).toBe("Update results (3)");
    expect(screen.getByTestId("panel").getAttribute("data-keys")).toBe("");
    expect(mocks.runSearch).not.toHaveBeenCalled();

    mocks.runSearch.mockResolvedValue(response("v2", "all"));
    mocks.runPins.mockResolvedValue(pins("v2", "all"));
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v2:1"));
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("panel-add-tif"));
    fireEvent.click(button);
    expect(mocks.runSearch).toHaveBeenCalledTimes(2);
  });

  it("keeps the previous results, summary and dots dimmed while the refresh runs; Search stays enabled", async () => {
    const { button } = await pageWithResults();
    const nextSearch = deferred<SearchResponse | null>();
    const nextPins = deferred<PinsResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => nextSearch.promise);
    mocks.runPins.mockImplementationOnce(() => nextPins.promise);
    const summaryBefore = screen.getByTestId("discovery-summary").textContent;
    fireEvent.click(screen.getByText("remove-tif"));
    fireEvent.click(screen.getByTestId("discovery-update-results"));

    const results = screen.getByTestId("results-state");
    expect(results.getAttribute("data-stale")).toBe("true");
    expect(results.textContent).toBe("v1:1"); // previous rows, not "none:0"
    expect(screen.getByTestId("map-state").textContent).toBe("ready:1:hidden:stale");
    expect(screen.getByTestId("discovery-summary").textContent).toBe(summaryBefore);
    expect(screen.getByTestId("discovery-summary").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByTestId("discovery-summary").className).toContain("opacity-[0.55]");
    expect(button.disabled).toBe(false);
    // chips stay clickable mid-refresh, and the in-flight draft needs no second button
    expect(screen.getByTestId("chip-land_use")).toBeTruthy();
    expect(screen.queryByTestId("discovery-update-results")).toBeNull();
    fireEvent.click(screen.getByText("remove-lot_size"));
    expect(screen.getByTestId("discovery-update-results").textContent).toBe("Update results (2)");

    await act(async () => {
      nextSearch.resolve(response("v2", "next", 1, { land_use: THREE.land_use }));
      nextPins.resolve(pins("v2", "next"));
    });
    await waitFor(() => expect(screen.getByTestId("results-state").getAttribute("data-stale")).toBe("false"));
    expect(screen.getByTestId("map-state").textContent).toBe("ready:1:hidden:fresh");
    expect(screen.getByTestId("results-state").textContent).toBe("v2:1");
  });

  it("keeps the previous results when a refresh fails and retries on request", async () => {
    await pageWithResults();
    mocks.runSearch.mockResolvedValueOnce(null);
    mocks.runPins.mockResolvedValueOnce(null);
    fireEvent.click(screen.getByText("remove-tif"));
    fireEvent.click(screen.getByTestId("discovery-update-results"));
    await waitFor(() => expect(screen.getByTestId("results-state").getAttribute("data-failed")).toBe("true"));
    expect(screen.getByTestId("results-state").textContent).toBe("v1:1");
    expect(screen.getByTestId("map-state").textContent).toContain("ready:1");

    mocks.runSearch.mockResolvedValueOnce(response("v2", "again"));
    mocks.runPins.mockResolvedValueOnce(pins("v2", "again"));
    fireEvent.click(screen.getByText("mock-retry"));
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v2:1"));
    expect(mocks.runSearch).toHaveBeenCalledTimes(2);
  });

  it("offers Update results on the phone Map tab too, where the strip is hidden", async () => {
    await pageWithResults();
    fireEvent.click(screen.getByText("remove-tif"));
    expect(screen.getAllByTestId("discovery-update-results")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Map" }));
    expect(screen.getAllByTestId("discovery-update-results")).toHaveLength(2);
  });
});
