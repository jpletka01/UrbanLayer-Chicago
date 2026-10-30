import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DiscoveryResults } from "./DiscoveryResults";
import type { CQS, Diagnostics, Registry, ResultRow, SearchResponse } from "./types";

afterEach(cleanup);

// A registry with the filters the zero-state logic inspects, plus PR4 coverage/populated.
function reg(over: Partial<Registry> = {}): Registry {
  return {
    version: "v1",
    filters: [
      { id: "land_use", category: "property_use", kind: "enum", field: "land_use_class", unknownPolicy: "exclude", enumValues: ["multi_family"], label: "Property use" },
      { id: "neighborhood", category: "location", kind: "region", field: "neighborhood", unknownPolicy: "exclude", label: "Neighborhood" },
      { id: "value_percentile", category: "financial", kind: "range", field: "value_percentile", unknownPolicy: "exclude", label: "Undervalued vs. neighborhood" },
    ],
    topics: [],
    sortKeys: [{ key: "pin", field: "pin" }, { key: "assessed_value", field: "total_assessed_value_sortkey" }],
    defaultSort: { key: "assessed_value", dir: "asc" },
    broadMinFilters: 2,
    coverage: { mode: "none", liveAreas: [] },
    populatedFields: [],
    ...over,
  };
}

const EMPTY_DIAG: Diagnostics = {
  resultCount: 0, broad: false, appliedFilters: 1,
  conflicts: [], droppedInvalid: [], excludedUnknown: {}, mostRestrictive: [],
};

function resp(filters: CQS["filters"], over: Partial<SearchResponse> = {}): SearchResponse {
  return {
    dataVersion: "v",
    cqs: { filters, sort: { key: "assessed_value", dir: "asc" }, scope: { mode: "all" }, meta: {} },
    result: { rows: [], total: 0, nextOffset: null },
    diagnostics: EMPTY_DIAG,
    ...over,
  };
}

const noop = () => {};
const baseProps = { loading: false, loadingMore: false, hasMore: false, onLoadMore: noop, onOpenParcel: noop };
const rowFixture: ResultRow = {
  pin: "17-06-426-013-0000", lat: 41.9, lon: -87.67, address: "1840 W Erie St",
  community_area: 24, land_use: "multi_family", class: "3-13", lot_sqft: 3125,
  bldg_sqft: 6800, year_built: 1901, units: 6, assessed_value: 118400, price_per_sf: 174,
  last_sale_price: null, last_sale_date: null, improvement_ratio: null,
  value_percentile: 8, upside_score: 86, is_teardown_candidate: false, sortValue: 118400,
};

describe("DiscoveryResults zero states (PR4-aware)", () => {
  it("(1) NULL-backed: a filter on an unpopulated field explains the 0", () => {
    const r = reg({ populatedFields: ["land_use"] }); // value_percentile NOT populated
    const response = resp({
      value_percentile: { predicate: { kind: "range", max: 25 }, source: "user" },
    });
    render(<DiscoveryResults {...baseProps} registry={r} rows={[]} response={response} onRelax={noop} />);
    expect(screen.getByText(/no data in this dataset yet/i)).toBeTruthy();
    // Label appears both in the message and the relax chip.
    expect(screen.getAllByText(/Undervalued vs\. neighborhood/).length).toBeGreaterThan(0);
  });

  it("(2) non-live area: a neighborhood not in coverage explains the 0", () => {
    const r = reg({
      populatedFields: ["neighborhood", "land_use"],
      coverage: { mode: "partial", liveAreas: [24] }, // West Town live
    });
    const response = resp({
      neighborhood: { predicate: { kind: "region", regions: ["neighborhood:22"] }, source: "user" }, // Logan Square
    });
    render(<DiscoveryResults {...baseProps} registry={r} rows={[]} response={response} onRelax={noop} />);
    expect(screen.getByText(/isn't indexed yet/i)).toBeTruthy();
    expect(screen.getByText(/Logan Square/)).toBeTruthy();
  });

  it("(3) too tight: offers most-restrictive removals", () => {
    const r = reg({ populatedFields: ["land_use", "neighborhood", "value_percentile"], coverage: { mode: "all", liveAreas: [] } });
    const response = resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
      { diagnostics: { ...EMPTY_DIAG, mostRestrictive: [{ filterId: "land_use", countWithoutIt: 42 }] } },
    );
    const onRelax = vi.fn();
    render(<DiscoveryResults {...baseProps} registry={r} rows={[]} response={response} onRelax={onRelax} />);
    expect(screen.getByText(/Try removing/i)).toBeTruthy();
    fireEvent.click(screen.getByText(/Property use \(\+42\)/));
    expect(onRelax).toHaveBeenCalledWith("land_use");
  });
});

describe("DiscoveryResults row-cards", () => {
  it("renders address-first with the PIN demoted", () => {
    const response = resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
      { result: { rows: [rowFixture], total: 1, nextOffset: null } },
    );
    render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} />,
    );
    expect(screen.getByText("1840 W Erie St")).toBeTruthy();
    expect(screen.getByText("17-06-426-013-0000")).toBeTruthy(); // PIN still present, demoted
    expect(screen.getByText(/Upside 86/)).toBeTruthy();
  });

  it("shows the Export CSV button (with results) and fires onExport", () => {
    const response = resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
      { result: { rows: [], total: 5, nextOffset: null } },
    );
    const onExport = vi.fn();
    render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={[]} response={response} onRelax={noop} onExport={onExport} />,
    );
    fireEvent.click(screen.getByText(/Export CSV/));
    expect(onExport).toHaveBeenCalled();
  });

  it("hides the Export CSV button when there are zero results", () => {
    const response = resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
    ); // total 0
    render(
      <DiscoveryResults {...baseProps} registry={reg({ populatedFields: ["land_use"] })} rows={[]} response={response} onRelax={noop} onExport={() => {}} />,
    );
    expect(screen.queryByText(/Export CSV/)).toBeNull();
  });

  it("highlights the matching pin from both pointer hover and keyboard focus", () => {
    const response = resp({}, { result: { rows: [rowFixture], total: 1, nextOffset: null } });
    const onHoverPin = vi.fn();
    render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} onHoverPin={onHoverPin} />,
    );
    const row = screen.getByRole("button", { name: /1840 W Erie St/i });
    fireEvent.mouseEnter(row);
    expect(onHoverPin).toHaveBeenLastCalledWith(rowFixture.pin);
    fireEvent.mouseLeave(row);
    expect(onHoverPin).toHaveBeenLastCalledWith(null);
    fireEvent.focus(row);
    expect(onHoverPin).toHaveBeenLastCalledWith(rowFixture.pin);
    fireEvent.blur(row);
    expect(onHoverPin).toHaveBeenLastCalledWith(null);
  });

  it("scrolls only an already-loaded row requested by a Pro map hover", () => {
    const scrollIntoView = vi.fn();
    const original = HTMLElement.prototype.scrollIntoView;
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const response = resp({}, { result: { rows: [rowFixture], total: 2, nextOffset: 1 } });

    const { rerender } = render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} scrollToPin="unloaded" />,
    );
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(screen.getAllByRole("button", { name: /1840 W Erie St/i })).toHaveLength(1);

    rerender(
      <DiscoveryResults {...baseProps} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} scrollToPin={rowFixture.pin} />,
    );
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });

    if (original) {
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: original });
    } else {
      delete (HTMLElement.prototype as { scrollIntoView?: unknown }).scrollIntoView;
    }
  });
});

describe("PR9 free-tier teaser", () => {
  const tenRows: ResultRow[] = Array.from({ length: 10 }, (_, i) => ({
    pin: `p${i}`, lat: null, lon: null, address: `${i} St`, community_area: 24,
    land_use: "multi_family", class: "3-13", lot_sqft: null, bldg_sqft: null, year_built: null,
    units: null, assessed_value: null, price_per_sf: null, last_sale_price: null,
    last_sale_date: null, improvement_ratio: null, value_percentile: null, upside_score: 80,
    is_teardown_candidate: false, sortValue: null,
  }));

  function gatedResponse() {
    return resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
      { result: { rows: tenRows, total: 847, nextOffset: null, gated: true } },
    );
  }

  it("renders the query-aware teaser wall and fires onUpgrade", () => {
    const onUpgrade = vi.fn();
    render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={tenRows} response={gatedResponse()} onRelax={noop} onUpgrade={onUpgrade} exportLocked />,
    );
    expect(screen.getByText(/847 parcels match — you're seeing 10/)).toBeTruthy();
    fireEvent.click(screen.getByText(/Unlock with Pro/));
    expect(onUpgrade).toHaveBeenCalled();
  });

  it("shows a locked Export button for free users that routes to upgrade", () => {
    const onUpgrade = vi.fn();
    render(
      <DiscoveryResults {...baseProps} registry={reg()} rows={tenRows} response={gatedResponse()} onRelax={noop} onUpgrade={onUpgrade} exportLocked onExport={() => { throw new Error("must not export"); }} />,
    );
    fireEvent.click(screen.getByText(/Export \(Pro\)/));
    expect(onUpgrade).toHaveBeenCalled();
  });
});

describe("Phase 0: previous results stay while a refresh runs", () => {
  const response = resp(
    { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
    { result: { rows: [rowFixture], total: 17, nextOffset: null } },
  );

  it("keeps the evaluated count and rows, dimmed, busy, inert and labelled Updating…", () => {
    render(
      <DiscoveryResults {...baseProps} loading registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} />,
    );
    // never the blank "Searching…" page once there is something to keep
    expect(screen.queryByText("Searching…")).toBeNull();
    expect(screen.getByText("17")).toBeTruthy();
    expect(screen.getByText("1840 W Erie St")).toBeTruthy();
    expect(screen.getByText("Updating…")).toBeTruthy();
    const body = screen.getByTestId("discovery-results-body");
    expect(body.getAttribute("aria-busy")).toBe("true");
    expect(body.getAttribute("data-stale")).toBe("true");
    expect(body.hasAttribute("inert")).toBe(true);
    expect(body.className).toContain("opacity-[0.55]");
    expect(body.className).toContain("pointer-events-none");
  });

  it("is not dimmed or inert when nothing is loading", () => {
    render(<DiscoveryResults {...baseProps} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} />);
    const body = screen.getByTestId("discovery-results-body");
    expect(body.getAttribute("aria-busy")).toBe("false");
    expect(body.hasAttribute("inert")).toBe(false);
    expect(screen.queryByText("Updating…")).toBeNull();
  });

  it("shows Searching… only for the first search, with nothing to keep", () => {
    render(<DiscoveryResults {...baseProps} loading registry={reg()} rows={[]} response={null} onRelax={noop} />);
    expect(screen.getByText("Searching…")).toBeTruthy();
  });

  it("shows an inline retry bar above the previous results after a failed refresh", () => {
    const onRetry = vi.fn();
    render(
      <DiscoveryResults {...baseProps} refreshFailed onRetry={onRetry} registry={reg()} rows={[rowFixture]} response={response} onRelax={noop} />,
    );
    expect(screen.getByTestId("discovery-update-failed").textContent).toContain("Couldn't update.");
    expect(screen.getByText("1840 W Erie St")).toBeTruthy(); // previous results kept
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("Phase 4b: zero and error states", () => {
  const tight = () =>
    resp(
      { land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" } },
      { diagnostics: { ...EMPTY_DIAG, mostRestrictive: [{ filterId: "land_use", countWithoutIt: 42 }] } },
    );
  const regAll = () => reg({ populatedFields: ["land_use", "neighborhood"], coverage: { mode: "all", liveAreas: [] } });

  it("offers Discard changes in the zero state only when there are unapplied edits", () => {
    const onDiscard = vi.fn();
    const { rerender } = render(
      <DiscoveryResults {...baseProps} registry={regAll()} rows={[]} response={tight()} onRelax={noop} canDiscard={false} onDiscard={onDiscard} />,
    );
    expect(screen.queryByTestId("discovery-zero-discard")).toBeNull();
    rerender(<DiscoveryResults {...baseProps} registry={regAll()} rows={[]} response={tight()} onRelax={noop} canDiscard onDiscard={onDiscard} />);
    fireEvent.click(screen.getByTestId("discovery-zero-discard"));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("offers it in the no-data and not-indexed zero states too", () => {
    const onDiscard = vi.fn();
    const nullBacked = resp({ value_percentile: { predicate: { kind: "range", max: 25 }, source: "user" } });
    const { unmount } = render(
      <DiscoveryResults {...baseProps} registry={reg({ populatedFields: ["land_use"] })} rows={[]} response={nullBacked} onRelax={noop} canDiscard onDiscard={onDiscard} />,
    );
    expect(screen.getByTestId("discovery-zero-discard")).toBeTruthy();
    unmount();
    const offCoverage = resp({ neighborhood: { predicate: { kind: "region", regions: ["neighborhood:22"] }, source: "user" } });
    render(
      <DiscoveryResults {...baseProps} registry={reg({ populatedFields: ["neighborhood"], coverage: { mode: "partial", liveAreas: [24] } })} rows={[]} response={offCoverage} onRelax={noop} canDiscard onDiscard={onDiscard} />,
    );
    expect(screen.getByTestId("discovery-zero-discard")).toBeTruthy();
  });

  it("states the zero reason at page scale (text-caption), not micro", () => {
    render(<DiscoveryResults {...baseProps} registry={regAll()} rows={[]} response={tight()} onRelax={noop} />);
    const reason = screen.getByText(/Try removing/i);
    expect(reason.className).toContain("text-caption");
    expect(reason.className).not.toContain("text-micro");
  });

  it("a failed first search says so and offers Retry", () => {
    const onRetry = vi.fn();
    render(<DiscoveryResults {...baseProps} registry={reg()} rows={[]} response={null} unavailable onRetry={onRetry} onRelax={noop} />);
    expect(screen.getByRole("status").textContent).toContain("temporarily unavailable");
    fireEvent.click(screen.getByTestId("discovery-search-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("without a retry handler the failed first search is just the message", () => {
    render(<DiscoveryResults {...baseProps} registry={reg()} rows={[]} response={null} unavailable onRelax={noop} />);
    expect(screen.queryByTestId("discovery-search-retry")).toBeNull();
  });
});

