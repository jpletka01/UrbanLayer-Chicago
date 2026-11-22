// A page chunk that fails to download must not blank the app (Sentry JAVASCRIPT-REACT-6): reload once for the new build.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadPage } from "./loadPage";

const chunkError = () =>
  new TypeError("Failed to fetch dynamically imported module: https://example.test/assets/RootNextPage-DIHrKpQG.js");

/** Settles within a few ticks, or reports that it is still pending. */
async function settle<T>(p: Promise<T>): Promise<{ value?: T; error?: unknown; pending?: true }> {
  const pending = new Promise<{ pending: true }>((r) => setTimeout(() => r({ pending: true }), 20));
  return Promise.race([p.then((value) => ({ value }), (error) => ({ error })), pending]);
}

describe("loadPage", () => {
  beforeEach(() => sessionStorage.clear());

  it("reloads once instead of throwing when a page chunk is gone after a deploy", async () => {
    const reload = vi.fn();
    const result = await settle(loadPage(() => Promise.reject(chunkError()), reload)());
    expect(reload).toHaveBeenCalledTimes(1);
    expect(result.pending).toBe(true);
  });

  it("throws on the second failure in a row, so a missing chunk can never loop reloads", async () => {
    const reload = vi.fn();
    await settle(loadPage(() => Promise.reject(chunkError()), reload)());
    const second = await settle(loadPage(() => Promise.reject(chunkError()), reload)());
    expect(reload).toHaveBeenCalledTimes(1);
    expect(second.error).toBeInstanceOf(TypeError);
  });

  it("reloads again after a page has loaded, so the next deploy is covered too", async () => {
    const reload = vi.fn();
    await settle(loadPage(() => Promise.reject(chunkError()), reload)());
    await loadPage(() => Promise.resolve({ default: "page" }), reload)();
    await settle(loadPage(() => Promise.reject(chunkError()), reload)());
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("matches Firefox's and Safari's wording of the same failure", async () => {
    for (const message of ["error loading dynamically imported module: x.js", "Importing a module script failed."]) {
      sessionStorage.clear();
      const reload = vi.fn();
      await settle(loadPage(() => Promise.reject(new TypeError(message)), reload)());
      expect(reload).toHaveBeenCalledTimes(1);
    }
  });

  it("passes other errors through without reloading", async () => {
    const reload = vi.fn();
    const result = await settle(loadPage(() => Promise.reject(new Error("boom")), reload)());
    expect(reload).not.toHaveBeenCalled();
    expect((result.error as Error).message).toBe("boom");
  });

  it("returns the module when the chunk loads", async () => {
    const mod = { default: "page" };
    await expect(loadPage(() => Promise.resolve(mod), vi.fn())()).resolves.toBe(mod);
  });
});
