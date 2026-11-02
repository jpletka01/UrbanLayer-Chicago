import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

// The layers themselves are tested on their own (ParcelMap, CapacityMap); here they are stand-ins that name
// themselves, so the test reads which one the switch mounted.
vi.mock("./ParcelMap", async (orig) => {
  const real = await orig<typeof import("./ParcelMap")>();
  return { ...real, ParcelMap: ({ variant }: { variant: string }) => <div data-testid="mounted">{variant}</div> };
});
vi.mock("./CapacityMap", () => ({ CapacityMap: () => <div data-testid="mounted">capacity</div> }));

import { AnalysisMap } from "./AnalysisMap";
import { availableLayers } from "./analysisLayers";
import type { ParcelMapLayers } from "./ParcelMap";

const square: GeoJSON.Polygon = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] };
const fc = (n: number): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: Array.from({ length: n }, () => ({ type: "Feature" as const, geometry: square, properties: {} })),
});
const both = { zoning: fc(2), overlays: fc(1) } as unknown as ParcelMapLayers;

afterEach(() => cleanup());

describe("AnalysisMap", () => {
  it("offers only the layers with something to draw", () => {
    expect(availableLayers(both)).toEqual(["zoning", "overlays", "capacity"]);
    expect(availableLayers({ zoning: fc(1) } as unknown as ParcelMapLayers)).toEqual(["zoning", "capacity"]);
    // an outage is still offered, so the map can say it couldn't load (empty and unavailable stay distinct)
    expect(availableLayers({ availability: { overlays: "unavailable" } } as unknown as ParcelMapLayers)).toContain("overlays");
    expect(availableLayers(null)).toEqual(["capacity"]);
  });

  it("mounts one map at a time, starting on Zoning", () => {
    render(<AnalysisMap lat={41.9} lon={-87.68} layers={both} />);
    expect(screen.getAllByTestId("mounted")).toHaveLength(1);
    expect(screen.getByTestId("mounted").textContent).toBe("zoning");
    expect(screen.getByRole("radio", { name: "Zoning" }).getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("radio", { name: "Overlays & incentives" }));
    expect(screen.getByTestId("mounted").textContent).toBe("boundaries");
    fireEvent.click(screen.getByRole("radio", { name: "Built vs allowed" }));
    expect(screen.getAllByTestId("mounted")).toHaveLength(1);
    expect(screen.getByTestId("mounted").textContent).toBe("capacity");
  });

  it("is a radio group: one tab stop, arrow keys move the choice", () => {
    render(<AnalysisMap lat={41.9} lon={-87.68} layers={both} />);
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    fireEvent.keyDown(screen.getByRole("radiogroup"), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Overlays & incentives" }).getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "Overlays & incentives" }));
    fireEvent.keyDown(screen.getByRole("radiogroup"), { key: "ArrowLeft" });
    fireEvent.keyDown(screen.getByRole("radiogroup"), { key: "ArrowLeft" });
    expect(screen.getByTestId("mounted").textContent).toBe("capacity");
  });

  it("holds the Zoning slot while the layers load, then falls back when a parcel has no zoning map", () => {
    const { rerender } = render(<AnalysisMap lat={41.9} lon={-87.68} layers={null} />);
    expect(screen.queryByTestId("mounted")).toBeNull();
    rerender(<AnalysisMap lat={41.9} lon={-87.68} layers={{ overlays: fc(1) } as unknown as ParcelMapLayers} />);
    expect(screen.getByTestId("mounted").textContent).toBe("boundaries");
  });
});
