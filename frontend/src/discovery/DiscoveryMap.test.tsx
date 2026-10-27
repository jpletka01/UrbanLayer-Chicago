import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryMap } from "./DiscoveryMap";
import type { PinPoint } from "./types";

const mapMocks = vi.hoisted(() => ({
  map: { resize: vi.fn(), fitBounds: vi.fn() },
  overlay: { setProps: vi.fn() },
  containerRef: { current: null as HTMLDivElement | null },
  mapRef: { current: null as {
    resize: ReturnType<typeof vi.fn>;
    fitBounds: ReturnType<typeof vi.fn>;
  } | null },
  overlayRef: { current: null as { setProps: ReturnType<typeof vi.fn> } | null },
}));

mapMocks.mapRef.current = mapMocks.map;
mapMocks.overlayRef.current = mapMocks.overlay;

vi.mock("../lib/useMapboxOverlay", () => ({
  useMapboxOverlay: () => ({
    containerRef: mapMocks.containerRef,
    mapRef: mapMocks.mapRef,
    overlayRef: mapMocks.overlayRef,
    mapReady: true,
  }),
}));

vi.mock("@deck.gl/layers", () => ({
  ScatterplotLayer: class ScatterplotLayer {
    constructor(public props: unknown) {}
  },
}));

const noop = () => {};
const point = (pin: string, lat: number | null, lon: number | null): PinPoint => ({
  pin,
  lat,
  lon,
  upside: 72,
  landUse: "commercial",
});

function props(over: Partial<React.ComponentProps<typeof DiscoveryMap>> = {}) {
  return {
    points: [point("one", 41.9, -87.7)],
    truncated: false,
    total: 1,
    hoveredPin: null,
    onHoverPin: noop,
    onOpenParcel: noop,
    colorBy: "land_use" as const,
    interactive: false,
    status: "ready" as const,
    visible: true,
    ...over,
  };
}

beforeEach(() => {
  mapMocks.map.resize.mockReset();
  mapMocks.map.fitBounds.mockReset();
  mapMocks.overlay.setProps.mockReset();
  mapMocks.containerRef.current = null;
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.stubGlobal("ResizeObserver", class ResizeObserver {
    observe() {}
    disconnect() {}
  });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0, y: 0, top: 0, left: 0, right: 390, bottom: 440,
    width: 390, height: 440, toJSON: () => ({}),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DiscoveryMap request states and sizing", () => {
  it.each([
    ["idle", "Run a search to map matching parcels."],
    ["loading", "Loading the current search map…"],
    ["unavailable", "The map is unavailable for this search. Try running the search again."],
  ] as const)("names the %s state", (status, message) => {
    render(<DiscoveryMap {...props({ points: [], total: 0, status })} />);
    expect(screen.getAllByText(message).length).toBeGreaterThan(0);
  });

  it("distinguishes a successful empty result from returned parcels without coordinates", () => {
    const { rerender } = render(<DiscoveryMap {...props({ points: [], total: 0 })} />);
    expect(screen.getAllByText("No parcels match this search.").length).toBeGreaterThan(0);

    rerender(<DiscoveryMap {...props({ points: [point("bad", 100, -87.7)], total: 1 })} />);
    expect(screen.getAllByText("The returned parcel does not have a valid map location.").length).toBeGreaterThan(0);
  });

  it("reports returned coordinate gaps separately from capped matches", () => {
    render(<DiscoveryMap {...props({
      points: [point("good", 41.9, -87.7), point("missing", null, null)],
      total: 5,
      truncated: true,
    })} />);

    expect(screen.getByText("1 of 2 returned parcels plotted.")).toBeTruthy();
    expect(screen.getByText("1 returned parcel lacks valid map coordinates.")).toBeTruthy();
    expect(screen.getByText("3 additional matches are outside the map cap.")).toBeTruthy();
  });

  it("resizes before fitting when a mounted hidden map becomes visible", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ visible: false })} />);
    expect(mapMocks.map.resize).not.toHaveBeenCalled();

    rerender(<DiscoveryMap {...props({ visible: true })} />);
    await waitFor(() => expect(mapMocks.map.fitBounds).toHaveBeenCalled());
    expect(mapMocks.map.resize).toHaveBeenCalled();
    expect(mapMocks.map.resize.mock.invocationCallOrder[0]).toBeLessThan(
      mapMocks.map.fitBounds.mock.invocationCallOrder[0],
    );
  });
});
