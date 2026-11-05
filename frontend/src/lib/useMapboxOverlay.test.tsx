import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// A browser without WebGL makes `new mapboxgl.Map` throw. Uncaught, that unmounted the whole app (Sentry,
// /discovery, 2026-11-04); the hook must report it instead.
vi.mock("mapbox-gl", () => {
  class Map {
    constructor() {
      throw new Error("Failed to initialize WebGL.");
    }
  }
  return { default: { Map, NavigationControl: class {}, accessToken: "" } };
});
vi.mock("@deck.gl/mapbox", () => ({ MapboxOverlay: class {} }));

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("useMapboxOverlay without WebGL", () => {
  it("returns mapError instead of throwing, and the page around the map still renders", async () => {
    vi.stubEnv("VITE_MAPBOX_TOKEN", "pk.test"); // read at import, so stub before importing
    const { useMapboxOverlay } = await import("./useMapboxOverlay");
    const { MapUnavailable } = await import("../components/ui/MapUnavailable");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    function Probe() {
      const { containerRef, mapError, mapReady } = useMapboxOverlay({ center: [-87.63, 41.88], zoom: 10 });
      return (
        <div>
          <p>rest of the page</p>
          <div ref={containerRef} data-testid="container" />
          {mapError && <MapUnavailable />}
          <span data-testid="state">{`${mapError}:${mapReady}`}</span>
        </div>
      );
    }

    render(<Probe />);
    expect(await screen.findByTestId("map-unavailable")).toBeTruthy();
    expect(screen.getByText("rest of the page")).toBeTruthy();
    expect(screen.getByTestId("state").textContent).toBe("webgl:false");
    expect(screen.getByTestId("map-unavailable").textContent).toContain("WebGL");
    expect(warn).toHaveBeenCalled();
  });
});
