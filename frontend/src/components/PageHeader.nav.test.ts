import { describe, expect, it } from "vitest";
import { navItemsFor } from "./PageHeader";

describe("PageHeader nav — Discovery linked only when its index is live", () => {
  it("omits Discovery while dormant (coverage none)", () => {
    const keys = navItemsFor(false).map((n) => n.key);
    expect(keys).not.toContain("nav.discovery");
  });

  it("inserts Discovery after Explore once live", () => {
    const keys = navItemsFor(true).map((n) => n.key);
    expect(keys).toContain("nav.discovery");
    expect(keys.indexOf("nav.discovery")).toBe(keys.indexOf("nav.explore") + 1);
  });
});
