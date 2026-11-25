import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { checkReportAccess, getAuthStatus } from "./api";

// Regression: every anonymous page load logged 401s, because the client tried
// to refresh a session that didn't exist (and the 401 handler retried it).

describe("anonymous visitors don't attempt session refresh", () => {
  let calls: string[];

  beforeEach(() => {
    document.cookie = "csrf_token=tok; path=/";
    calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const path = url.replace(/^.*?(\/api\/)/, "/api/");
        calls.push(path.split("?")[0]);
        if (path.startsWith("/api/auth/me")) {
          return new Response(JSON.stringify({ authenticated: false, auth_required: true, user: null, can_refresh: false }));
        }
        return new Response("{}", { status: 401 });
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("a 401 after an anonymous auth check does not call /api/auth/refresh", async () => {
    await getAuthStatus();
    await checkReportAccess({ pin: "14313320180000", lat: 41.9, lon: -87.6 } as never);
    expect(calls).not.toContain("/api/auth/refresh");
  });
});
