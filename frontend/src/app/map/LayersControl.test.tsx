// The Layers control (Item 128): a corner square that previews and switches to the other map; hovering opens the
// layer toggles; no close button.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LayersControl, type LayersState } from "./LayersControl";

afterEach(cleanup);
const base: LayersState = { basemap: "standard", transit: true, zoning: false, saved: true };

describe("the Layers control", () => {
  it("previews the other map and switches to it on a click", () => {
    const onChange = vi.fn();
    render(<LayersControl value={base} onChange={onChange} theme="light" />);
    const tile = screen.getByTestId("layers-button");
    expect(tile.getAttribute("aria-label")).toBe("Switch to Satellite");
    expect(tile.querySelector("img")?.getAttribute("src")).toContain("gis.cookcountyil.gov");
    fireEvent.click(tile);
    expect(onChange).toHaveBeenCalledWith({ ...base, basemap: "satellite" });
  });

  it("shows our map's preview while on Satellite", () => {
    render(<LayersControl value={{ ...base, basemap: "satellite" }} onChange={() => {}} theme="dark" />);
    const tile = screen.getByTestId("layers-button");
    expect(tile.getAttribute("aria-label")).toBe("Switch to Map");
    expect(tile.querySelector("svg")).not.toBeNull();
  });

  it("opens the layer row on hover, toggles a layer, and has no close button", () => {
    const onChange = vi.fn();
    render(<LayersControl value={base} onChange={onChange} theme="light" />);
    expect(screen.queryByTestId("layers-row")).toBeNull();
    fireEvent.mouseEnter(screen.getByTestId("layers-control"));
    expect(screen.getByTestId("layers-row")).toBeTruthy();
    expect(screen.getByTestId("layers-transit").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByTestId("layers-zoning"));
    expect(onChange).toHaveBeenCalledWith({ ...base, zoning: true });
    expect(screen.queryByRole("button", { name: /close/i })).toBeNull();
    // The credits hide behind the info icon at the row's end (owner's review 2026-11-16).
    expect(screen.queryByText(/Data: City of Chicago/)).toBeNull();
    fireEvent.click(screen.getByTestId("layers-credits"));
    expect(screen.getByText(/Data: City of Chicago/)).toBeTruthy();
    fireEvent.mouseLeave(screen.getByTestId("layers-control"));
    expect(screen.queryByTestId("layers-row")).toBeNull();
  });
});
