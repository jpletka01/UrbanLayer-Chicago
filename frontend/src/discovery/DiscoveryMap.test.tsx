import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryMap } from "./DiscoveryMap";
import type { PinPoint } from "./types";

const mapMocks = vi.hoisted(() => ({
  resolvedTheme: "dark" as "dark" | "light",
  styleRevision: 0,
  styleLoad: null as (() => void) | null,
  moveStart: null as ((e: { originalEvent?: unknown }) => void) | null,
  hookOptions: null as { style?: string; interleaved?: boolean } | null,
  map: {
    resize: vi.fn(),
    fitBounds: vi.fn(),
    getCenter: vi.fn(() => ({ lng: -87.7, lat: 41.9 })),
    getZoom: vi.fn(() => 12),
    getBearing: vi.fn(() => 5),
    getPitch: vi.fn(() => 10),
    jumpTo: vi.fn(),
    setStyle: vi.fn(),
    once: vi.fn((_event: string, callback: () => void) => { mapMocks.styleLoad = callback; }),
    on: vi.fn((event: string, callback: (e: { originalEvent?: unknown }) => void) => {
      if (event === "movestart") mapMocks.moveStart = callback;
    }),
    off: vi.fn(),
  },
  overlay: { setProps: vi.fn() },
  containerRef: { current: null as HTMLDivElement | null },
  mapRef: { current: null as Record<string, ReturnType<typeof vi.fn>> | null },
  overlayRef: { current: null as { setProps: ReturnType<typeof vi.fn> } | null },
}));

mapMocks.mapRef.current = mapMocks.map;
mapMocks.overlayRef.current = mapMocks.overlay;

vi.mock("../lib/useMapboxOverlay", () => ({
  useMapboxOverlay: (options: { style?: string; interleaved?: boolean }) => {
    mapMocks.hookOptions = options;
    return {
      containerRef: mapMocks.containerRef,
      mapRef: mapMocks.mapRef,
      overlayRef: mapMocks.overlayRef,
      mapReady: true,
      styleRevision: mapMocks.styleRevision,
    };
  },
}));

vi.mock("../contexts/ThemeContext", () => ({
  useThemeContext: () => ({
    resolvedTheme: mapMocks.resolvedTheme,
    theme: mapMocks.resolvedTheme,
    setTheme: vi.fn(),
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
  mapMocks.map.jumpTo.mockReset();
  mapMocks.map.setStyle.mockReset();
  mapMocks.map.once.mockClear();
  mapMocks.map.on.mockClear();
  mapMocks.moveStart = null;
  mapMocks.map.off.mockReset();
  mapMocks.overlay.setProps.mockReset();
  mapMocks.containerRef.current = null;
  mapMocks.resolvedTheme = "dark";
  mapMocks.styleRevision = 0;
  mapMocks.styleLoad = null;
  mapMocks.hookOptions = null;
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

  it("keeps free dots non-pickable while row focus renders a separate accent ring", async () => {
    render(<DiscoveryMap {...props({ hoveredPin: "one", interactive: false })} />);
    await waitFor(() => expect(mapMocks.overlay.setProps).toHaveBeenCalled());
    const latest = mapMocks.overlay.setProps.mock.calls.at(-1)?.[0] as {
      layers: Array<{ props: Record<string, unknown> }>;
    };
    const base = latest.layers.find((layer) => layer.props.id === "discovery-pins")!;
    const ring = latest.layers.find((layer) => layer.props.id === "discovery-pin-highlight")!;

    expect(base.props.pickable).toBe(false);
    expect(base.props.onHover).toBeUndefined();
    expect(base.props.onClick).toBeUndefined();
    expect(base.props.autoHighlight).toBe(false);
    expect(ring.props.pickable).toBe(false);
    expect(ring.props.filled).toBe(false);
    expect(ring.props.stroked).toBe(true);
    const datum = (base.props.data as Array<{ fillColor: number[] }>)[0];
    expect((base.props.getFillColor as (entry: typeof datum) => number[])(datum)).toEqual(datum.fillColor);
  });

  it("preserves Pro map hover and click handlers", async () => {
    const onHoverPin = vi.fn();
    const onOpenParcel = vi.fn();
    render(<DiscoveryMap {...props({ interactive: true, onHoverPin, onOpenParcel })} />);
    await waitFor(() => expect(mapMocks.overlay.setProps).toHaveBeenCalled());
    const latest = mapMocks.overlay.setProps.mock.calls.at(-1)?.[0] as {
      layers: Array<{ props: Record<string, unknown> }>;
    };
    const base = latest.layers.find((layer) => layer.props.id === "discovery-pins")!;
    expect(base.props.pickable).toBe(true);
    (base.props.onHover as (info: { object: PinPoint | null }) => void)({ object: props().points[0] });
    (base.props.onClick as (info: { object: PinPoint | null }) => void)({ object: props().points[0] });
    expect(onHoverPin).toHaveBeenCalledWith("one");
    expect(onOpenParcel).toHaveBeenCalledWith("one");
  });

  it("switches theme style, restores the camera, and reapplies layers after style.load", async () => {
    const stableProps = props();
    const { rerender } = render(<DiscoveryMap {...stableProps} />);
    expect(mapMocks.hookOptions?.style).toBe("mapbox://styles/mapbox/dark-v11");
    mapMocks.resolvedTheme = "light";
    rerender(<DiscoveryMap {...stableProps} />);
    expect(mapMocks.map.setStyle).toHaveBeenCalledWith("mapbox://styles/mapbox/light-v11");
    expect(mapMocks.styleLoad).not.toBeNull();
    mapMocks.styleLoad?.();
    expect(mapMocks.map.jumpTo).toHaveBeenCalledWith({
      center: { lng: -87.7, lat: 41.9 }, zoom: 12, bearing: 5, pitch: 10,
    });

    const callsBeforeRevision = mapMocks.overlay.setProps.mock.calls.length;
    mapMocks.styleRevision += 1;
    rerender(<DiscoveryMap {...stableProps} />);
    await waitFor(() => expect(mapMocks.overlay.setProps.mock.calls.length).toBeGreaterThan(callsBeforeRevision));
  });

  it("exposes a keyboard-operable counted Map key", () => {
    render(<DiscoveryMap {...props({ points: [
      point("one", 41.9, -87.7),
      point("two", 41.91, -87.71),
    ] })} />);
    const button = screen.getByRole("button", { name: "Map key" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    const key = screen.getByTestId("discovery-map-legend");
    expect(within(key).getByText("Commercial")).toBeTruthy();
    expect(within(key).getByText("2")).toBeTruthy();
  });
});

describe("Phase 4b: what the map leaves out is named inside the counted key", () => {
  it("puts the cap and coordinate-gap notes in the key, not in a separate box", () => {
    render(<DiscoveryMap {...props({
      points: [point("good", 41.9, -87.7), point("missing", null, null)],
      total: 5,
      truncated: true,
    })} />);
    const key = screen.getByTestId("discovery-map-legend");
    const notes = within(key).getByTestId("discovery-map-notes");
    expect(within(notes).getByText("1 of 2 returned parcels plotted.")).toBeTruthy();
    expect(within(notes).getByText("1 returned parcel lacks valid map coordinates.")).toBeTruthy();
    expect(within(notes).getByText("3 additional matches are outside the map cap.")).toBeTruthy();
    // exactly one place says it
    expect(screen.getAllByText("3 additional matches are outside the map cap.")).toHaveLength(1);
  });

  it("names the shortfall on the phone key button, so it shows while the key is closed", () => {
    render(<DiscoveryMap {...props({
      points: [point("a", 41.9, -87.7), point("b", 41.91, -87.71)],
      total: 5,
      truncated: true, // 3 more matches than the 2 returned
    })} />);
    const button = screen.getByRole("button", { name: /Map key/ });
    expect(within(button).getByTestId("discovery-map-key-shortfall").textContent).toBe("2 of 5 shown");
    expect(button.getAttribute("aria-expanded")).toBe("false"); // closed, and the count is still there
  });

  it("says nothing extra when every match is plotted", () => {
    render(<DiscoveryMap {...props({ points: [point("a", 41.9, -87.7), point("b", 41.91, -87.71)], total: 2 })} />);
    expect(screen.queryByTestId("discovery-map-key-shortfall")).toBeNull();
    expect(screen.queryByTestId("discovery-map-notes")).toBeNull();
  });

  it("counts a parcel without coordinates as not shown", () => {
    render(<DiscoveryMap {...props({ points: [point("a", 41.9, -87.7), point("x", null, null)], total: 2 })} />);
    expect(screen.getByTestId("discovery-map-key-shortfall").textContent).toBe("1 of 2 shown");
  });
});

describe("Phase 0: previous dots while a refresh runs", () => {
  async function latestLayers() {
    await waitFor(() => expect(mapMocks.overlay.setProps).toHaveBeenCalled());
    const latest = mapMocks.overlay.setProps.mock.calls.at(-1)?.[0] as {
      layers: Array<{ props: Record<string, unknown> }>;
      getTooltip?: unknown;
    };
    return latest;
  }

  it("keeps the dots and the counted key but makes them dimmed and NOT pickable, even for Pro", async () => {
    const onHoverPin = vi.fn();
    const onOpenParcel = vi.fn();
    render(<DiscoveryMap {...props({ interactive: true, stale: true, hoveredPin: "one", onHoverPin, onOpenParcel })} />);
    const latest = await latestLayers();
    const base = latest.layers.find((layer) => layer.props.id === "discovery-pins")!;
    expect(base).toBeTruthy(); // dots stay
    expect(base.props.pickable).toBe(false);
    expect(base.props.onHover).toBeUndefined();
    expect(base.props.onClick).toBeUndefined();
    expect(base.props.opacity as number).toBeLessThan(0.5);
    expect(latest.getTooltip).toBeUndefined();
    // no hover ring on a dot that is about to be replaced
    expect(latest.layers.find((layer) => layer.props.id === "discovery-pin-highlight")).toBeUndefined();
    expect(screen.getByTestId("discovery-map-stale").textContent).toBe("Previous results, updating");
    fireEvent.click(screen.getByRole("button", { name: "Map key" }));
    expect(within(screen.getByTestId("discovery-map-legend")).getByText("Commercial")).toBeTruthy(); // previous model's key
  });

  it("restores picking at full opacity when the refresh ends", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ interactive: true, stale: true })} />);
    await latestLayers();
    rerender(<DiscoveryMap {...props({ interactive: true, stale: false })} />);
    await waitFor(() => {
      const latest = mapMocks.overlay.setProps.mock.calls.at(-1)?.[0] as { layers: Array<{ props: Record<string, unknown> }> };
      expect(latest.layers[0].props.pickable).toBe(true);
    });
    const latest = mapMocks.overlay.setProps.mock.calls.at(-1)?.[0] as { layers: Array<{ props: Record<string, unknown> }> };
    expect(latest.layers[0].props.opacity).toBe(1);
    expect(screen.queryByTestId("discovery-map-stale")).toBeNull();
  });

  it("withholds the map on an Item 30 mismatch (unavailable shows no dots and no stale chip)", () => {
    render(<DiscoveryMap {...props({ points: [], total: 0, status: "unavailable", stale: false })} />);
    expect(screen.getAllByText("The map is unavailable for this search. Try running the search again.").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("discovery-map-stale")).toBeNull();
    expect(screen.queryByTestId("discovery-map-legend")).toBeNull();
  });
});

describe("Phase 0: camera policy", () => {
  const first = [point("one", 41.9, -87.7)];
  const second = [point("two", 41.95, -87.65)];
  const fits = () => mapMocks.map.fitBounds.mock.calls.length;
  // The first fit also re-runs once for the pane's measured size; wait for that to settle.
  async function settledFits() {
    await waitFor(() => expect(fits()).toBeGreaterThan(0));
    await new Promise((resolve) => setTimeout(resolve, 20));
    return fits();
  }

  it("fits the first result and later results while the user has not moved the camera", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ points: first })} />);
    const before = await settledFits();
    rerender(<DiscoveryMap {...props({ points: second })} />);
    await waitFor(() => expect(fits()).toBeGreaterThan(before));
    expect(screen.queryByTestId("discovery-map-zoom")).toBeNull();
  });

  it("ignores camera moves that carry no user event (our own fitBounds, theme jumpTo)", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ points: first })} />);
    const before = await settledFits();
    act(() => mapMocks.moveStart?.({}));
    rerender(<DiscoveryMap {...props({ points: second })} />);
    await waitFor(() => expect(fits()).toBeGreaterThan(before));
    expect(screen.queryByTestId("discovery-map-zoom")).toBeNull();
  });

  it("does not move a camera the user has moved; offers Zoom to results instead", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ points: first })} />);
    const before = await settledFits();
    act(() => mapMocks.moveStart?.({ originalEvent: {} }));
    rerender(<DiscoveryMap {...props({ points: second })} />);
    const button = await screen.findByTestId("discovery-map-zoom");
    expect(fits()).toBe(before);
    expect(button.textContent).toBe("Zoom to results");

    fireEvent.click(button);
    expect(fits()).toBe(before + 1);
    expect(screen.queryByTestId("discovery-map-zoom")).toBeNull();
    // and later results follow the camera again
    rerender(<DiscoveryMap {...props({ points: [point("three", 41.8, -87.6)] })} />);
    await waitFor(() => expect(fits()).toBeGreaterThan(before + 1));
  });

  it("does not offer the button while the results are stale", async () => {
    const { rerender } = render(<DiscoveryMap {...props({ points: first })} />);
    await settledFits();
    act(() => mapMocks.moveStart?.({ originalEvent: {} }));
    rerender(<DiscoveryMap {...props({ points: second, stale: true })} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByTestId("discovery-map-zoom")).toBeNull();
    expect(screen.getByTestId("discovery-map-stale")).toBeTruthy();
  });
});
