import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { KIT_CODE_CURRENT_THROUGH, formatKitVintage } from "./kitVintage";

describe("kit vintage", () => {
  it("matches the answer key's code_current_through", () => {
    const key = JSON.parse(readFileSync(resolve(__dirname, "../../../eval/kit/parcels.json"), "utf8"));
    expect(KIT_CODE_CURRENT_THROUGH).toBe(key.code_current_through);
  });

  it("formats as a long US date", () => {
    expect(formatKitVintage("2026-03-18")).toBe("March 18, 2026");
  });
});
