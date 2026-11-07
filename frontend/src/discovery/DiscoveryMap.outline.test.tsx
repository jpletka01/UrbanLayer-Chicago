// Every visible lot outline opens something (Item 68 follow-up, 2026-11-06): a click on an outline with no dot
// under it opens that lot's preview by PIN10, or says "Not in our data yet" and still opens the Profile at the point.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryMap } from "./DiscoveryMap";
import type { ResultRow } from "./types";

const m = vi.hoisted(() => ({
  hookOptions: null as { onClick?: (info: unknown) => void } | null,
  outlineAt: vi.fn((): string | null => null),
  fetchOutlineRow: vi.fn(),
  map: {
    resize: vi.fn(), fitBounds: vi.fn(), getZoom: vi.fn(() => 16), isStyleLoaded: vi.fn(() => true),
    on: vi.fn(), off: vi.fn(), once: vi.fn(), setStyle: vi.fn(), jumpTo: vi.fn(),
  },
}));

vi.mock("../lib/useMapboxOverlay", () => ({
  useMapboxOverlay: (options: { onClick?: (info: unknown) => void }) => {
    m.hookOptions = options;
    return {
      containerRef: { current: null },
      mapRef: { current: m.map },
      overlayRef: { current: { setProps: vi.fn() } },
      mapReady: true,
      styleRevision: 0,
    };
  },
}));
vi.mock("../contexts/ThemeContext", () => ({ useThemeContext: () => ({ resolvedTheme: "dark" }) }));
vi.mock("./parcelTiles", () => ({
  MATCH_COLORS: { dark: { fill: "#000", line: "#000", outline: "#000" }, light: { fill: "#000", line: "#000", outline: "#000" } },
  addParcelLayers: vi.fn(),
  markMatches: vi.fn(),
  outlineAt: m.outlineAt,
}));
vi.mock("./searchClient", () => ({ fetchParcelRow: vi.fn(async () => null), fetchOutlineRow: m.fetchOutlineRow }));
vi.mock("@deck.gl/layers", () => ({ ScatterplotLayer: class { constructor(public props: unknown) {} } }));

const row: ResultRow = {
  pin: "14-33-103-011-0000", lat: 41.92, lon: -87.64, address: "642 W BELDEN AVE", community_area: 7, land_use: "residential",
  class: "2-11", lot_sqft: 3000, bldg_sqft: null, year_built: null, units: null, assessed_value: 90000,
  price_per_sf: null, last_sale_price: null, last_sale_date: null, improvement_ratio: null, value_percentile: null,
  upside_score: null, is_teardown_candidate: false, zoning_group: "residential", allowed_far: 1.2, sortValue: 3000,
} as ResultRow;

function renderMap(over: Partial<React.ComponentProps<typeof DiscoveryMap>> = {}) {
  const props: React.ComponentProps<typeof DiscoveryMap> = {
    points: [], truncated: false, total: 0, hoveredPin: null, onHoverPin: () => {}, onOpenParcel: vi.fn(),
    onOpenPoint: vi.fn(), colorBy: "land_use", rows: [], sortKey: "lot_size", onSelectPin: () => {}, status: "ready",
    visible: true, parcelTiles: { minZoom: 14, maxZoom: 16 } as React.ComponentProps<typeof DiscoveryMap>["parcelTiles"],
    ...over,
  };
  render(<DiscoveryMap {...props} />);
  return props;
}

const clickAt = () => act(() => m.hookOptions?.onClick?.({ x: 50, y: 60, coordinate: [-87.64, 41.92] }));

beforeEach(() => {
  m.outlineAt.mockReset();
  m.fetchOutlineRow.mockReset();
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => { cb(0); return 1; });
  vi.stubGlobal("cancelAnimationFrame", () => {});
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("lot outlines open something", () => {
  it("opens the lot's preview by its PIN10 and its Profile by the row's own PIN", async () => {
    m.outlineAt.mockReturnValue("1433103011");
    m.fetchOutlineRow.mockResolvedValue({ status: "found", row });
    const props = renderMap();
    clickAt();
    expect(m.outlineAt).toHaveBeenCalledWith(m.map, 50, 60);
    await waitFor(() => expect(screen.getByTestId("dot-preview").textContent).toContain("642 W Belden Ave"));
    expect(m.fetchOutlineRow.mock.calls[0][0]).toBe("1433103011");
    fireEvent.click(screen.getByTestId("dot-preview-open"));
    expect(props.onOpenParcel).toHaveBeenCalledWith("14-33-103-011-0000");
  });

  it("says 'Not in our data yet' for a lot the index lacks, and opens the Profile at the point", async () => {
    m.outlineAt.mockReturnValue("1433103099");
    m.fetchOutlineRow.mockResolvedValue({ status: "missing" });
    const props = renderMap();
    clickAt();
    await waitFor(() => expect(screen.getByTestId("dot-preview-missing").textContent).toBe("Not in our data yet."));
    fireEvent.click(screen.getByTestId("dot-preview-open"));
    expect(props.onOpenPoint).toHaveBeenCalledWith(41.92, -87.64);
    expect(props.onOpenParcel).not.toHaveBeenCalled();
  });

  it("a failed read is not 'not in our data'", async () => {
    m.outlineAt.mockReturnValue("1433103011");
    m.fetchOutlineRow.mockResolvedValue({ status: "failed" });
    renderMap();
    clickAt();
    await waitFor(() => expect(screen.getByTestId("dot-preview-missing").textContent).toBe("Couldn't load this lot."));
  });

  it("an empty spot with no outline opens nothing", () => {
    m.outlineAt.mockReturnValue(null);
    renderMap();
    clickAt();
    expect(screen.queryByTestId("dot-preview")).toBeNull();
  });

  it("no tiles: never asks the map for outlines", () => {
    renderMap({ parcelTiles: null });
    clickAt();
    expect(m.outlineAt).not.toHaveBeenCalled();
  });
});
