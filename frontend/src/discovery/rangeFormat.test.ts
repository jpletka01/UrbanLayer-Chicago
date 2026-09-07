import { describe, it, expect } from "vitest";

import { formatRangeValue } from "./rangeFormat";

describe("formatRangeValue", () => {
  it("groups plain numbers", () => {
    expect(formatRangeValue(50000, "number")).toBe("50,000");
  });

  it("prefixes and groups money", () => {
    expect(formatRangeValue(250000, "usd")).toBe("$250,000");
    expect(formatRangeValue(0, "usd")).toBe("$0");
  });

  it("renders a stored 0-1 ratio as a percentage", () => {
    // improvement_ratio's registry domain is [0, 1] with step 0.05.
    expect(formatRangeValue(0.35, "percent")).toBe("35%");
    expect(formatRangeValue(1, "percent")).toBe("100%");
  });

  it("does NOT group years", () => {
    // The bug this guards: 1954 must not render as "1,954".
    expect(formatRangeValue(1954, "year")).toBe("1954");
    expect(formatRangeValue(2025, "year")).toBe("2025");
  });

  it("keeps FAR to one decimal and never groups it", () => {
    expect(formatRangeValue(2.5, "far")).toBe("2.5");
    expect(formatRangeValue(16, "far")).toBe("16");
  });

  it("suffixes miles", () => {
    expect(formatRangeValue(0.5, "mi")).toBe("0.5 mi");
  });

  it("appends a unit only for displays without their own symbol", () => {
    expect(formatRangeValue(12, "count", "units")).toBe("12 units");
    // usd already carries "$" — appending would give "$250,000 dollars".
    expect(formatRangeValue(250000, "usd", "dollars")).toBe("$250,000");
  });

  it("returns empty string for non-finite input", () => {
    expect(formatRangeValue(NaN, "number")).toBe("");
    expect(formatRangeValue(Infinity, "usd")).toBe("");
  });

  it("falls back to grouped number for an unknown display", () => {
    expect(formatRangeValue(1234, undefined)).toBe("1,234");
  });
});
