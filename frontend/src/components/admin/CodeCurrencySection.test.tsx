import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { CodeCurrencySection } from "./CodeCurrencySection";
import { lawrence, tod } from "../scorecard/amendments.fixtures";
import type { AdminCodeCurrency } from "../../lib/api";

vi.mock("../../lib/api", async (orig) => {
  const mod = await orig<typeof import("../../lib/api")>();
  return { ...mod, fetchAdminCodeCurrency: vi.fn() };
});
import { fetchAdminCodeCurrency } from "../../lib/api";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const base: AdminCodeCurrency = {
  code: {
    source_id: "code.municipal_text", as_of: "2026-06-17", ingested_at: "2026-10-21", age_days: 126,
    lag: { title17_passed_since: 2, cited_other_passed_since: 0, unreviewed: 1, oldest_unreviewed_days: 28, uncodified_applied: 1 },
    last_checked: "2026-10-21T11:00:00Z", check_state: "fresh", status: "amber", reasons: ["code text 126 days old (> 60)"],
  },
  clerk: { last_success: "2026-10-21T11:00:00Z", last_attempt: null, last_error: null, consecutive_failures: 0, snapshot_state: "ok", contract_ok: true, contract_problems: [] },
  amendments: [lawrence, tod],
};

describe("CodeCurrencySection — admin 'Code currency' card", () => {
  it("shows status, age, the Title 17 count and the unreviewed amendments", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue(base);
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("code-currency")).toBeTruthy());
    expect(screen.getByTestId("code-status").textContent).toBe("amber");
    expect(screen.getByTestId("code-title17").textContent).toBe("2");
    expect(screen.getByText("126 days")).toBeTruthy();
    const rows = screen.getByTestId("code-amendments-table").querySelectorAll("tbody tr");
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain("not reviewed");
    expect(rows[1].textContent).toContain("applied");
  });

  it("never shows a count when the Clerk check is stale, and surfaces the last error", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue({
      ...base,
      code: { ...base.code, check_state: "unknown", status: "red", lag: { ...base.code.lag, title17_passed_since: null } },
      clerk: { ...base.clerk, last_error: "ClerkUnavailable: 503", consecutive_failures: 4, snapshot_state: "failed" },
    });
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("code-title17")).toBeTruthy());
    expect(screen.getByTestId("code-title17").textContent).toContain("unknown");
    expect(screen.getByText("ClerkUnavailable: 503")).toBeTruthy();
  });

  it("says so when the endpoint is unavailable", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue(null);
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByText(/isn't available right now/)).toBeTruthy());
  });
});
