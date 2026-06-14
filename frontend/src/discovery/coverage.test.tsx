import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoverageBanner } from "./CoverageBanner";
import { coverageOf, isPopulated, missingFieldsFor } from "./coverage";
import { buildRequest } from "./searchClient";
import { REG } from "./_fixtures";
import type { PanelState, Registry } from "./types";

function reg(over: Partial<Registry>): Registry {
  return { ...REG, ...over };
}

describe("coverage selectors — safe defaults", () => {
  it("treats a registry with no coverage/populatedFields as fully dormant", () => {
    // Simulates a stale localStorage payload missing the PR4 fields.
    const stale = { ...REG } as Registry;
    // @ts-expect-error intentionally drop the fields
    delete stale.coverage;
    // @ts-expect-error intentionally drop the fields
    delete stale.populatedFields;
    expect(coverageOf(stale).mode).toBe("none");
    expect(isPopulated(stale, "land_use")).toBe(false);
  });

  it("isPopulated is true only for ids in populatedFields", () => {
    const r = reg({ populatedFields: ["land_use", "lot_size"] });
    expect(isPopulated(r, "land_use")).toBe(true);
    expect(isPopulated(r, "tif")).toBe(false);
  });

  it("missingFieldsFor returns the unpopulated subset (drives recipe NEEDS-DATA badges)", () => {
    const r = reg({ populatedFields: ["land_use"] });
    expect(missingFieldsFor(r, ["land_use", "tif", "value_percentile"])).toEqual([
      "tif",
      "value_percentile",
    ]);
  });
});

describe("CoverageBanner", () => {
  it("renders nothing at full coverage", () => {
    const { container } = render(<CoverageBanner registry={reg({ coverage: { mode: "all", liveAreas: [] } })} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the dormant notice when nothing is indexed", () => {
    render(<CoverageBanner registry={reg({ coverage: { mode: "none", liveAreas: [] } })} />);
    expect(screen.getByText(/being prepared/i)).toBeTruthy();
  });

  it("names the live areas when coverage is partial", () => {
    render(<CoverageBanner registry={reg({ coverage: { mode: "partial", liveAreas: [24] } })} />);
    expect(screen.getByText(/Indexed area: West Town/)).toBeTruthy();
    expect(screen.getByText(/limited to live areas/)).toBeTruthy();
  });
});

describe("coverage never enters the CQS path", () => {
  it("buildRequest emits no coverage key regardless of registry coverage", () => {
    const panelState: PanelState = { land_use: { kind: "enum", values: ["residential"] } };
    const req = buildRequest(
      { panelState },
      reg({ coverage: { mode: "partial", liveAreas: [24] } }),
    );
    expect("coverage" in req).toBe(false);
    expect(JSON.stringify(req)).not.toContain("coverage");
  });
});
