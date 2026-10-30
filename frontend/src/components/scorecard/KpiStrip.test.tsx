import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KpiStrip, type KpiTile } from "./KpiStrip";

afterEach(cleanup);

const tiles: KpiTile[] = [
  { anchor: "property", label: "Est. tax", value: "$83K/yr", valueNote: "(2024)", caption: <p data-testid="cap">Government model</p> },
  { anchor: "comparables", label: "Comps", value: "—", state: "withheld", caption: <p>Not shown: only 2 sales (needs 3).</p> },
  { anchor: "comparables", label: "Median", value: "$310K", state: "low" },
  { anchor: "zoning", label: "Zoning", value: "B3-2" },
];

describe("KpiStrip confidence states", () => {
  it("prints the year beside the value and the caption under the tile", () => {
    render(<KpiStrip tiles={tiles} onScrollTo={() => {}} />);
    expect(screen.getByText("$83K/yr")).toBeTruthy();
    expect(screen.getByText("(2024)")).toBeTruthy();
    expect(screen.getByTestId("cap").textContent).toBe("Government model");
  });

  it("mutes a withheld tile and quiets a low one; a standard tile keeps primary text", () => {
    render(<KpiStrip tiles={tiles} onScrollTo={() => {}} />);
    expect(screen.getByText("—").parentElement!.className).toContain("text-text-muted");
    expect(screen.getByText("$310K").parentElement!.className).toContain("text-text-secondary");
    expect(screen.getByText("B3-2").parentElement!.className).toContain("text-text-primary");
    expect(screen.getByText("Not shown: only 2 sales (needs 3).")).toBeTruthy();
  });
});
