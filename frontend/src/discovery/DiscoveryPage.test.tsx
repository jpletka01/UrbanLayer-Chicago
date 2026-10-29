import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DiscoveryPage from "./DiscoveryPage";
import { REG } from "./_fixtures";
import type { Diagnostics, PinsResponse, SearchResponse } from "./types";

const mocks = vi.hoisted(() => ({
  runSearch: vi.fn(),
  runPins: vi.fn(),
  loadRegistry: vi.fn(),
  track: vi.fn(),
  previewText: vi.fn(),
}));

vi.mock("./searchClient", () => ({
  runSearch: mocks.runSearch,
  runPins: mocks.runPins,
  previewText: mocks.previewText,
  exportCsv: vi.fn(),
}));
vi.mock("./registryClient", () => ({ loadRegistry: mocks.loadRegistry }));
vi.mock("../contexts/AuthContext", () => ({ useAuthContext: () => ({ user: null }) }));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("../lib/tracking", () => ({ track: mocks.track }));
vi.mock("./../components/PageHeader", () => ({ default: () => <div /> }));
vi.mock("./../components/UpgradePrompt", () => ({ default: () => null }));
vi.mock("./chips", () => ({
  chipLabel: (id: string) => (id === "tif" ? "TIF district" : id),
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
vi.mock("./RecipeShelf", () => ({ RecipeShelf: () => <div data-testid="recipe-shelf" /> }));
// The Start panel has its own tests; here it is a stub that lets a test make each choice.
vi.mock("./StartPanel", () => ({
  StartPanel: ({ resumable, onChoose, onForgetResume }: {
    resumable: { sentence: string } | null;
    onChoose: (c: unknown) => void;
    onForgetResume: () => void;
  }) => (
    <div data-testid="start-panel">
      <button type="button" onClick={() => onChoose({ kind: "recipe", topic: { id: "vacant_mf", presets: {} } })}>start-recipe</button>
      <button type="button" onClick={() => onChoose({ kind: "neighborhood", areaId: 24 })}>start-area</button>
      <button type="button" onClick={() => onChoose({ kind: "all" })}>start-all</button>
      {resumable && <button type="button" onClick={() => onChoose({ kind: "resume" })}>{`start-resume:${resumable.sentence}`}</button>}
      <button type="button" onClick={onForgetResume}>start-forget</button>
    </div>
  ),
}));
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

// The one response a search returns when it asked for `includePins`.
function combined(dataVersion: string, pin: string, total = 1): SearchResponse {
  return { ...response(dataVersion, pin, total), pins: pins(dataVersion, pin, total) };
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
  mocks.track.mockReset();
  // the text compiler understood something, unless a test says otherwise
  mocks.previewText.mockReset().mockResolvedValue({ understood: [{ filterId: "tif", predicate: { kind: "flag", value: true } }], residual: [], droppedInvalid: [] });
  localStorage.clear();
});

afterEach(cleanup);

describe("DiscoveryPage issued-query pairing", () => {
  it("lets only the latest issued request commit when searches resolve out of order", async () => {
    const firstSearch = deferred<SearchResponse | null>();
    const secondSearch = deferred<SearchResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => firstSearch.promise).mockImplementationOnce(() => secondSearch.promise);
    const { button, input } = await readyPage();

    // The text check runs before each search, so let the first search start (its request is in
    // flight, unresolved) before the second is issued; the second must then supersede it.
    fireEvent.change(input, { target: { value: "first" } });
    fireEvent.click(button);
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalledTimes(1));
    fireEvent.change(input, { target: { value: "second" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalledTimes(2));

    secondSearch.resolve(combined("v2", "new"));
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v2:1"));
    expect(screen.getByTestId("map-state").textContent).toContain("ready:1");

    firstSearch.resolve(combined("v1", "old"));
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
  mocks.runSearch.mockResolvedValueOnce({ ...response("v1", "one", 1, { ...THREE }), pins: pins("v1", "one") });
  const ready = await readyPage();
  fireEvent.click(ready.button);
  await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v1:1"));
  mocks.runSearch.mockClear();
  mocks.runPins.mockClear();
  return ready;
}

describe("DiscoveryPage Phase 0: draft edits, then one Update results", () => {
  it("never blanks the page while chips are removed, requests nothing, then sends one request", async () => {
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

    mocks.runSearch.mockResolvedValueOnce(combined("v1", "two"));
    fireEvent.click(screen.getByTestId("discovery-update-results"));
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    expect(mocks.runPins).not.toHaveBeenCalled(); // list and map from one request
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

// --- Start panel (redesign Phase 2): nothing runs on arrival; each way in is one explicit search ---

const savedSearch = {
  v: 1,
  inputs: { panelState: { tif: { kind: "flag", value: true } }, text: "", sort: null, topicId: "r1" },
  sentence: "Parcels where TIF district.",
  savedAt: Date.now(),
};

describe("DiscoveryPage Start panel", () => {
  it("opens on the Start panel and requests nothing (the old auto-run of the first recipe is gone)", async () => {
    render(<DiscoveryPage />);
    await screen.findByTestId("start-panel");
    await waitFor(() => expect((screen.getByRole("button", { name: "Search" }) as HTMLButtonElement).disabled).toBe(false));
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(mocks.runPins).not.toHaveBeenCalled();
    expect(screen.queryByTestId("results-state")).toBeNull(); // no results area, so no result to mistake for one
    expect(screen.queryByTestId("recipe-shelf")).toBeNull(); // the recipes are in the Start panel, not twice
  });

  it("shows the index-as-of line once: in the Start panel before a search, in the rail after it", async () => {
    mocks.loadRegistry.mockResolvedValue({
      ...REG,
      coverage: { mode: "all", liveAreas: Array.from({ length: 77 }, (_, i) => i + 1), asOf: "2026-10-01" },
    });
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    await screen.findByTestId("start-panel");
    expect(screen.queryByTestId("discovery-index-as-of")).toBeNull(); // the (stubbed) panel owns it
    fireEvent.click(screen.getByText("start-all"));
    await screen.findByTestId("discovery-index-as-of");
    expect(screen.getAllByTestId("discovery-index-as-of")).toHaveLength(1);
  });

  it("a recipe is one explicit search with its presets, and the panel goes away", async () => {
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    fireEvent.click(await screen.findByText("start-recipe"));
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    const sent = mocks.runSearch.mock.calls[0][0];
    // the presets come from the registry's recipe, as plain user filters
    expect(sent.panelState).toEqual(REG.topics[0].presets);
    expect(sent.topicId).toBe("vacant_mf");
    expect(mocks.track).toHaveBeenCalledWith("discovery_start_choice", { kind: "recipe", id: "vacant_mf" });
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("v1:1"));
    expect(screen.queryByTestId("start-panel")).toBeNull();
    expect(screen.getAllByTestId("recipe-shelf").length).toBeGreaterThan(0); // the rail shelf takes over after the first search
  });

  it("a neighborhood is a search for that one community area and nothing else", async () => {
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    fireEvent.click(await screen.findByText("start-area"));
    const sent = mocks.runSearch.mock.calls[0][0];
    expect(sent.panelState).toEqual({ neighborhood: { kind: "region", regions: ["neighborhood:24"] } });
    expect(sent.topicId).toBeNull();
    expect(mocks.track).toHaveBeenCalledWith("discovery_start_choice", { kind: "neighborhood", id: 24 });
  });

  it("'all parcels' is a search with no filters, and says which choice was made", async () => {
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    fireEvent.click(await screen.findByText("start-all"));
    expect(mocks.runSearch.mock.calls[0][0].panelState).toEqual({});
    expect(mocks.track).toHaveBeenCalledWith("discovery_start_choice", { kind: "all" });
  });

  it("keeps the Start panel until a search is actually running, and not after a failed first search", async () => {
    mocks.runSearch.mockResolvedValueOnce(null);
    render(<DiscoveryPage />);
    fireEvent.click(await screen.findByText("start-all"));
    await waitFor(() => expect(screen.getByTestId("results-state").textContent).toBe("unavailable"));
    expect(screen.queryByTestId("start-panel")).toBeNull();
  });

  it("remembers what was evaluated, in this browser, as inputs plus the server's sentence", async () => {
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    fireEvent.click(await screen.findByText("start-recipe"));
    await waitFor(() => expect(localStorage.getItem("ul_discovery_last")).not.toBeNull());
    const stored = JSON.parse(localStorage.getItem("ul_discovery_last")!);
    expect(stored.inputs.panelState).toEqual(REG.topics[0].presets);
    expect(stored.inputs.topicId).toBe("vacant_mf");
    expect(typeof stored.sentence).toBe("string");
    expect(stored.sentence.length).toBeGreaterThan(0);
  });

  it("offers the last search, re-runs its inputs on Resume, and can forget it", async () => {
    localStorage.setItem("ul_discovery_last", JSON.stringify(savedSearch));
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    render(<DiscoveryPage />);
    const resume = await screen.findByText("start-resume:Parcels where TIF district.");
    expect(mocks.runSearch).not.toHaveBeenCalled(); // offering is not running
    fireEvent.click(resume);
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    expect(mocks.runSearch.mock.calls[0][0].panelState).toEqual(savedSearch.inputs.panelState);
    expect(mocks.track).toHaveBeenCalledWith("discovery_start_choice", { kind: "resume", id: "r1" });
  });

  it("forgetting the last search removes it from storage and from the panel", async () => {
    localStorage.setItem("ul_discovery_last", JSON.stringify(savedSearch));
    render(<DiscoveryPage />);
    await screen.findByText("start-resume:Parcels where TIF district.");
    fireEvent.click(screen.getByText("start-forget"));
    expect(localStorage.getItem("ul_discovery_last")).toBeNull();
    expect(screen.queryByText(/start-resume/)).toBeNull();
  });
});


// --- Text box: ask the compiler first; say so instead of searching everything ---

describe("DiscoveryPage text box feedback", () => {
  it("does not search, and says why, when the compiler understood none of the phrase", async () => {
    mocks.previewText.mockResolvedValue({ understood: [], residual: ["teardown", "logan", "square"], droppedInvalid: [] });
    const { input } = await readyPage();
    fireEvent.change(input, { target: { value: "teardown in logan square" } });
    fireEvent.keyDown(input, { key: "Enter" });
    const note = await screen.findByTestId("discovery-text-feedback");
    expect(note.getAttribute("data-kind")).toBe("none");
    expect(note.textContent).toContain("no search was run");
    expect(note.textContent).toContain("Not understood: teardown, logan, square.");
    expect(mocks.runSearch).not.toHaveBeenCalled();
  });

  it("clears the notice when the text is edited", async () => {
    mocks.previewText.mockResolvedValue({ understood: [], residual: ["xyz"], droppedInvalid: [] });
    const { input } = await readyPage();
    fireEvent.change(input, { target: { value: "xyz" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await screen.findByTestId("discovery-text-feedback");
    fireEvent.change(input, { target: { value: "xyz tif" } });
    expect(screen.queryByTestId("discovery-text-feedback")).toBeNull();
  });

  it("searches when the compiler understood the phrase, and names what the evaluated search took from it", async () => {
    mocks.runSearch.mockResolvedValueOnce({
      ...combined("v1", "one"),
      cqs: {
        filters: { tif: { predicate: { kind: "flag", value: true }, source: "text" } },
        sort: REG.defaultSort, scope: { mode: "all" }, meta: { rawText: "tif near the L", textResidual: ["l"] },
      },
    });
    const { input } = await readyPage();
    fireEvent.change(input, { target: { value: "tif near the L" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalledTimes(1));
    expect(mocks.runSearch.mock.calls[0][0].text).toBe("tif near the L");
    const note = await screen.findByTestId("discovery-text-feedback");
    expect(note.getAttribute("data-kind")).toBe("partial");
    expect(note.textContent).toContain("TIF district");
    expect(note.textContent).toContain("Not understood: l.");
  });
});
