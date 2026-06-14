import { describe, expect, it } from "vitest";
import { compilePanel, predicateIsValid } from "./uiCompiler";
import type { PanelState } from "./types";

describe("predicateIsValid", () => {
  it("rejects empty enum/region and boundless range", () => {
    expect(predicateIsValid({ kind: "enum", values: [] })).toBe(false);
    expect(predicateIsValid({ kind: "region", regions: [] })).toBe(false);
    expect(predicateIsValid({ kind: "range" })).toBe(false);
  });

  it("accepts non-empty / one-bound / inverted range / flag", () => {
    expect(predicateIsValid({ kind: "enum", values: ["residential"] })).toBe(true);
    expect(predicateIsValid({ kind: "range", min: 100 })).toBe(true);
    expect(predicateIsValid({ kind: "range", min: 500, max: 100 })).toBe(true); // inverted is valid
    expect(predicateIsValid({ kind: "flag", value: false })).toBe(true);
  });
});

describe("compilePanel", () => {
  it("drops cleared/invalid controls, keeps valid ones (pure)", () => {
    const state: PanelState = {
      land_use: { kind: "enum", values: ["residential"] },
      lot_size: { kind: "range" }, // boundless → dropped
      overlay: { kind: "enum", values: [] }, // empty → dropped
      tif: { kind: "flag", value: true },
    };
    const out = compilePanel(state);
    expect(out).toEqual({
      land_use: { kind: "enum", values: ["residential"] },
      tif: { kind: "flag", value: true },
    });
    // purity: same input → same output, input not mutated
    expect(compilePanel(state)).toEqual(out);
    expect(Object.keys(state)).toHaveLength(4);
  });
});
