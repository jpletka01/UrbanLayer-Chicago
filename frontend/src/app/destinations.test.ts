// The destinations list (Phase 10): the side panel's order, and the page names page_view sends.
import { describe, expect, it } from "vitest";
import { navEntries, pageNameFor } from "./destinations";
import { isChatDoor } from "./chatDoor";

describe("destinations", () => {
  it("lists the side panel's destinations in order", () => {
    expect(navEntries().map((e) => e.id)).toEqual(["home", "profile", "discovery", "saved", "chat"]);
  });

  it("names every page without the preview's next_ prefix", () => {
    expect(pageNameFor("/")).toBe("home");
    expect(pageNameFor("/scorecard")).toBe("profile");
    expect(pageNameFor("/c/abc")).toBe("chat");
    expect(pageNameFor("/s/tok")).toBe("shared_chat");
    expect(pageNameFor("/settings/plan")).toBe("settings");
    expect(pageNameFor("/about")).toBe("about");
    expect(pageNameFor("/admin")).toBe("admin");
    expect(pageNameFor("/nowhere")).toBe("not_found");
  });

  it("sends the chat doors on / to /chat", () => {
    expect(isChatDoor("?q=zoning")).toBe(true);
    expect(isChatDoor("?pin=123&handoff=abc")).toBe(true);
    expect(isChatDoor("?ask=1")).toBe(true);
    expect(isChatDoor("?landing=1")).toBe(false);
    expect(isChatDoor("")).toBe(false);
  });
});
