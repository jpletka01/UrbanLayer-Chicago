import { describe, expect, it, vi } from "vitest";
import { markMatches, pinFeatureId } from "./parcelTiles";

describe("parcel tiles", () => {
  it("keys a PIN by its first ten digits, dashed or not", () => {
    expect(pinFeatureId("14-31-300-012-1001")).toBe(1431300012);
    expect(pinFeatureId("14313000121001")).toBe(1431300012);
    expect(pinFeatureId("bad")).toBeNull();
  });

  it("clears the previous matches before marking the new ones", () => {
    const calls: string[] = [];
    const map = {
      getSource: () => ({}),
      removeFeatureState: vi.fn(() => calls.push("clear")),
      setFeatureState: vi.fn((f: { id: number }) => calls.push(`set ${f.id}`)),
    };
    markMatches(map as never, ["14-31-300-012-1001", "x"]);
    expect(calls).toEqual(["clear", "set 1431300012"]);
  });

  it("does nothing before the source exists", () => {
    const map = { getSource: () => undefined, removeFeatureState: vi.fn(), setFeatureState: vi.fn() };
    markMatches(map as never, ["14-31-300-012-1001"]);
    expect(map.removeFeatureState).not.toHaveBeenCalled();
  });
});
