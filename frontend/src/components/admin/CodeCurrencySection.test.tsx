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

describe("CodeCurrencySection — rezonings the City's map lacks (WS1 M5)", () => {
  it("shows how many are waiting, how long, and the titles to map by hand", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue({
      ...base,
      map_lag: {
        source_id: "chi.zoning.passed_not_on_map", passed_not_on_map: 80, oldest_days: 98, flaggable: 77, with_parcels: 54,
        unparsed_titles: 3, unparsed: ["O2026-0026168"], no_parcels: ["a", "b"], check_status: "ok",
        last_checked: "2026-10-21T11:00:00Z", last_error: null,
      },
    });
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("map-lag")).toBeTruthy());
    expect(screen.getByTestId("map-lag-count").textContent).toBe("80");
    expect(screen.getByText("98 days")).toBeTruthy();
    expect(screen.getByText(/Map by hand in rezoning_overrides.json: O2026-0026168/)).toBeTruthy();
  });

  it("says unknown, never zero, when the check has never run", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue({
      ...base,
      map_lag: {
        source_id: "chi.zoning.passed_not_on_map", passed_not_on_map: null, oldest_days: null, flaggable: null, with_parcels: null,
        unparsed_titles: null, unparsed: [], no_parcels: [], check_status: "missing", last_checked: null, last_error: null,
      },
    });
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("map-lag-count")).toBeTruthy());
    expect(screen.getByTestId("map-lag-count").textContent).toBe("unknown (never checked)");
  });
});

describe("CodeCurrencySection — landmark designations (WS1 M5b)", () => {
  it("shows how many were placed on a parcel and the titles that were not", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue({
      ...base,
      designations: {
        passed: 8, flaggable: 8, with_parcels: 5, unparsed_titles: 1, unparsed: ["O2025-0019665"], no_parcels: ["O2026-0024659"],
        check_status: "ok", last_checked: "2026-10-22T11:00:00Z", last_error: null,
      },
    });
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("designations")).toBeTruthy());
    expect(screen.getByTestId("designations-count").textContent).toBe("8");
    expect(screen.getByText(/Not placed \(no flag\): O2025-0019665/)).toBeTruthy();
  });

  it("says unknown, never zero, when the check has never run; renders nothing for an older payload", async () => {
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue({
      ...base,
      designations: { passed: null, flaggable: null, with_parcels: null, unparsed_titles: null, unparsed: [], no_parcels: [], check_status: "missing", last_checked: null, last_error: null },
    });
    const { unmount } = render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("designations-count")).toBeTruthy());
    expect(screen.getByTestId("designations-count").textContent).toBe("unknown (never checked)");
    unmount();
    vi.mocked(fetchAdminCodeCurrency).mockResolvedValue(base);
    render(<CodeCurrencySection />);
    await waitFor(() => expect(screen.getByTestId("code-currency")).toBeTruthy());
    expect(screen.queryByTestId("designations")).toBeNull();
  });
});

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
