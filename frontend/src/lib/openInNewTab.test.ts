import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { openInNewTab, takeHandoff, writeHandoff } from "./openInNewTab";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("openInNewTab", () => {
  it("opens a new tab and cuts its opener", () => {
    const win = { opener: {} as unknown };
    const open = vi.spyOn(window, "open").mockReturnValue(win as Window);
    expect(openInNewTab("/?ask=1")).toBe(true);
    expect(open).toHaveBeenCalledWith("/?ask=1", "_blank");
    expect(win.opener).toBeNull();
  });

  it("reports a blocked tab instead of navigating in place", () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    const before = window.location.href;
    expect(openInNewTab("/?ask=1")).toBe(false);
    expect(window.location.href).toBe(before);
  });
});

describe("dock handoff", () => {
  const msgs = [{ role: "user" as const, content: "Can I build a 3-flat?" }, { role: "assistant" as const, content: "RS-3 ..." }];

  it("round-trips once through localStorage (sessionStorage does not reach a new tab)", () => {
    const id = writeHandoff(msgs)!;
    expect(id).toMatch(/^[a-z0-9]+$/);
    expect(takeHandoff(id)).toEqual(msgs);
    expect(takeHandoff(id)).toBeNull(); // consumed exactly once
  });

  it("drops handoffs older than an hour on the next write", () => {
    const old = writeHandoff(msgs, Date.now() - 2 * 60 * 60 * 1000)!;
    const fresh = writeHandoff(msgs)!;
    expect(takeHandoff(old)).toBeNull();
    expect(takeHandoff(fresh)).toEqual(msgs);
  });

  it("rejects a malformed id", () => {
    expect(takeHandoff("../x")).toBeNull();
  });
});
