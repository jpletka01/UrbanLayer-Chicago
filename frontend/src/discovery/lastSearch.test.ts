import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearLastSearch, loadLastSearch, saveLastSearch } from "./lastSearch";

const SAVED = {
  inputs: { panelState: { tif: { kind: "flag" as const, value: true } }, text: "", sort: null, topicId: null },
  sentence: "Parcels where TIF district, sorted by upside score (descending).",
};

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("lastSearch", () => {
  it("round-trips the inputs and the evaluated sentence", () => {
    saveLastSearch(SAVED, 1_000);
    expect(loadLastSearch(2_000)).toEqual({ ...SAVED, savedAt: 1_000 });
  });

  it("forgets a search older than 30 days", () => {
    saveLastSearch(SAVED, 0);
    expect(loadLastSearch(31 * 24 * 60 * 60 * 1000)).toBeNull();
  });

  it("ignores anything it did not write (other version, wrong shape, bad JSON)", () => {
    localStorage.setItem("ul_discovery_last", JSON.stringify({ v: 99, ...SAVED, savedAt: 1 }));
    expect(loadLastSearch(2)).toBeNull();
    localStorage.setItem("ul_discovery_last", JSON.stringify({ v: 1, sentence: "x", savedAt: 1 }));
    expect(loadLastSearch(2)).toBeNull();
    localStorage.setItem("ul_discovery_last", "{not json");
    expect(loadLastSearch(2)).toBeNull();
  });

  it("clears on request", () => {
    saveLastSearch(SAVED);
    clearLastSearch();
    expect(loadLastSearch()).toBeNull();
  });

  it("never throws when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => saveLastSearch(SAVED)).not.toThrow();
    expect(loadLastSearch()).toBeNull();
    expect(() => clearLastSearch()).not.toThrow();
  });
});
