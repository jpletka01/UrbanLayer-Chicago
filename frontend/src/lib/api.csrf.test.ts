import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { discoverySearch } from "./api";

// Regression: Discovery's first search on a cold visit raced the CSRF cookie
// (issued by GET /api/auth/me), went out with an empty token, got a 403, and
// the page showed no results.

function clearCsrfCookie() {
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
}

describe("authFetch CSRF bootstrap", () => {
  let calls: { url: string; init?: RequestInit }[];

  beforeEach(() => {
    clearCsrfCookie();
    calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith("/api/auth/me")) document.cookie = "csrf_token=tok123; path=/";
        return new Response(JSON.stringify({ rows: [], total: 0 }), { status: 200 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCsrfCookie();
  });

  it("fetches the cookie before the first POST and sends it", async () => {
    await discoverySearch({ userFilters: [], registryVersion: "1" } as never);
    expect(calls.map((c) => c.url.replace(/^.*\/api/, "/api"))).toEqual([
      "/api/auth/me",
      "/api/discovery/search",
    ]);
    const headers = calls[1].init?.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe("tok123");
  });

  it("shares one bootstrap request across concurrent POSTs", async () => {
    await Promise.all([
      discoverySearch({ userFilters: [], registryVersion: "1" } as never),
      discoverySearch({ userFilters: [], registryVersion: "1" } as never),
    ]);
    expect(calls.filter((c) => c.url.endsWith("/api/auth/me"))).toHaveLength(1);
  });

  it("skips the bootstrap when the cookie already exists", async () => {
    document.cookie = "csrf_token=existing; path=/";
    await discoverySearch({ userFilters: [], registryVersion: "1" } as never);
    expect(calls).toHaveLength(1);
  });
});
