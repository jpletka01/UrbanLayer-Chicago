// Street View is a link out to Google's public Maps URL (owner's pick, Item 94): no key, no account, no billing.
import { describe, expect, it } from "vitest";
import { streetViewUrl } from "./mapInfo";

describe("streetViewUrl", () => {
  it("opens Google's Street View panorama at the point, with only the coordinates in the link", () => {
    const url = new URL(streetViewUrl(41.9097123, -87.6773456));
    expect(url.origin).toBe("https://www.google.com");
    expect(url.searchParams.get("api")).toBe("1");
    expect(url.searchParams.get("map_action")).toBe("pano");
    expect(url.searchParams.get("viewpoint")).toBe("41.909712,-87.677346");
    expect([...url.searchParams.keys()].sort()).toEqual(["api", "map_action", "viewpoint"]);
  });
});
