import { describe, expect, it } from "vitest";
import { clipBox } from "./discoveryData";

describe("clipBox", () => {
  it("keeps the view without a search view, cuts it to the overlap, and is null apart", () => {
    expect(clipBox([0, 0, 2, 2], null)).toEqual([0, 0, 2, 2]);
    expect(clipBox([0, 0, 2, 2], [1, 1, 3, 3])).toEqual([1, 1, 2, 2]);
    expect(clipBox([0, 0, 1, 1], [2, 2, 3, 3])).toBeNull();
  });
});
