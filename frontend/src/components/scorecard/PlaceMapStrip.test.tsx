import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

// ParcelMap itself is tested on its own; the stand-in names its mode, so the test reads which map is mounted.
vi.mock("./ParcelMap", () => ({
  ParcelMap: ({ bare }: { bare?: boolean }) => <div data-testid="mounted">{bare ? "strip" : "full"}</div>,
}));

import { PlaceMapStrip } from "./PlaceMapStrip";

afterEach(() => cleanup());

describe("PlaceMapStrip", () => {
  it("is a still strip that opens the full map, one map at a time", () => {
    render(<PlaceMapStrip lat={41.9} lon={-87.68} />);
    expect(screen.getByTestId("mounted").textContent).toBe("strip");
    fireEvent.click(screen.getByRole("button", { name: "Open the full map" }));
    expect(screen.getByRole("dialog", { name: "Where the parcel is" })).toBeTruthy();
    expect(screen.getAllByTestId("mounted").map((m) => m.textContent)).toEqual(["full"]);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close the map" }));
  });

  it("Escape and Close return to the strip, with focus on it", () => {
    render(<PlaceMapStrip lat={41.9} lon={-87.68} />);
    const strip = screen.getByRole("button", { name: "Open the full map" });
    fireEvent.click(strip);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(strip);
    fireEvent.click(strip);
    fireEvent.click(screen.getByRole("button", { name: "Close the map" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByTestId("mounted").textContent).toBe("strip");
  });
});
