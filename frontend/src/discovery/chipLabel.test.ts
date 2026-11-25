import { describe, expect, it } from "vitest";
import "../lib/i18n";
import { chipLabel } from "./chipLabel";
import { REG } from "./_fixtures";

const def = (id: string) => REG.filters.find((f) => f.id === id);

describe("chipLabel (a filter as one line of words)", () => {
  it("names an enum filter with its values", () => {
    expect(chipLabel("land_use", { kind: "enum", values: ["multi_family"] }, def("land_use"))).toBe("Property use: Multifamily");
  });

  it("names a flag filter, and its negation", () => {
    expect(chipLabel("tif", { kind: "flag", value: true }, def("tif"))).toBe("TIF district");
    expect(chipLabel("tif", { kind: "flag", value: false }, def("tif"))).toBe("no TIF district");
  });

  it("names neighborhood regions by community-area name, not raw id", () => {
    const label = chipLabel("neighborhood", { kind: "region", regions: ["neighborhood:24"] });
    expect(label).toMatch(/West Town/);
    expect(label).not.toMatch(/neighborhood:24/);
  });

  it("writes a range with both bounds, one bound, or none", () => {
    expect(chipLabel("lot_size", { kind: "range", min: 3000, max: 6000 }, def("lot_size"))).toMatch(/^Lot size 3000–6000/);
    expect(chipLabel("lot_size", { kind: "range", min: 3000 }, def("lot_size"))).toMatch(/^Lot size ≥ 3000/);
    expect(chipLabel("lot_size", { kind: "range" }, def("lot_size"))).toBe("Lot size");
  });
});
