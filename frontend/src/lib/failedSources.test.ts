import { describe, expect, it } from "vitest";
import { failedIn, failedLabels, MODULE_OF, type FailedSource } from "./failedSources";

const failed: FailedSource[] = [
  { key: "property", labels: ["property tax estimate"] },
  { key: "comparables", labels: ["comparable sales"] },
  { key: "crime", labels: ["crime statistics"] },
  { key: "regulatory", labels: ["landmark designation (City zoning map didn't answer)"] },
  { key: "zoning", labels: ["parcel zoning"] },
];

describe("failedSources — a failure shows in the module whose figures it left out", () => {
  it("places each by module", () => {
    expect(failedIn(failed, "economics").map((f) => f.key)).toEqual(["property"]);
    expect(failedIn(failed, "market").map((f) => f.key)).toEqual(["comparables"]);
    expect(failedIn(failed, "area").map((f) => f.key)).toEqual(["crime"]);
    expect(failedIn(failed, "build").map((f) => f.key)).toEqual(["regulatory", "zoning"]);
    expect(failedIn(failed, "record")).toEqual([]);
  });

  it("words it with what reported it, once each", () => {
    expect(failedLabels(failed, "economics")).toEqual(["property tax estimate"]);
    expect(failedLabels([{ key: "property", labels: ["a"] }, { key: "incentives", labels: ["a", "b"] }], "economics")).toEqual(["a", "b"]);
  });

  it("a payload without the field (an older cached response) shows nothing", () => {
    expect(failedIn(undefined, "build")).toEqual([]);
    expect(failedLabels(null, "area")).toEqual([]);
  });

  it("every key has a module", () => {
    expect(Object.keys(MODULE_OF).length).toBeGreaterThan(15);
  });
});
