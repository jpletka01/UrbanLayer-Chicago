// /admin redesigned (owner's review 2026-11-17): sections on the left, one at a time at /admin/<id>, Overview first
// with four figures and what needs attention in a few words; Early access makes a code from chips and a stepper. The
// admin API is mocked.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { AdminCodeCurrency, DataHealth } from "../../lib/api";
import { axeViolations } from "../test/axe";
import { badgeText, codeAttention, correctionsAttention, dataAttention, adminSectionFrom, sectionBadges } from "./adminModel";
import AdminNextPage from "./AdminNextPage";
import { VouchersSection } from "./VouchersSection";

vi.mock("../../contexts/AuthContext", () => ({
  useAuthContext: () => ({ user: { id: "a", tier: "admin" }, isAuthenticated: true, authRequired: true, loading: false }),
}));
vi.mock("../frame/AppFrame", () => ({
  AppFrame: ({ children, secondary, tools }: { children: React.ReactNode; secondary?: React.ReactNode; tools?: React.ReactNode }) => (
    <div className="ui-next">{tools}{secondary}<main>{children}</main></div>
  ),
  ToolButton: ({ label, onClick, testId }: { label: string; onClick: () => void; testId?: string }) => <button type="button" aria-label={label} onClick={onClick} data-testid={testId} />,
}));
vi.mock("../../lib/api", async (orig) => {
  const mod = await orig<typeof import("../../lib/api")>();
  const overview = { total_requests: 12, total_input_tokens: 1000, total_output_tokens: 500, estimated_cost_usd: 0.42, by_model: {}, by_phase: {} };
  return {
    ...mod,
    fetchAdminOverview: vi.fn().mockResolvedValue(overview),
    fetchAdminTimeseries: vi.fn().mockResolvedValue([]),
    fetchAdminLatency: vi.fn().mockResolvedValue([]),
    fetchAdminEngagement: vi.fn().mockResolvedValue(null),
    fetchConversationStats: vi.fn().mockResolvedValue(null),
    fetchRequestLogs: vi.fn().mockResolvedValue([]),
    fetchBenchmarkResults: vi.fn().mockResolvedValue(null),
    fetchJudgeResults: vi.fn().mockResolvedValue(null),
    fetchDataHealth: vi.fn().mockResolvedValue(null),
    fetchAdminCodeCurrency: vi.fn().mockResolvedValue(null),
    fetchAdminCorrections: vi.fn().mockResolvedValue({ reports: [], total: 2 }),
    fetchAdminVouchers: vi.fn().mockResolvedValue([]),
    createAdminVoucher: vi.fn(),
  };
});
import { createAdminVoucher, fetchAdminOverview } from "../../lib/api";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const words = (s: string) => s.split(/\s+/).length;
const health = (over: Partial<DataHealth["checker"]>, counts: DataHealth["counts"] = {}): DataHealth => ({
  checker: { state: "ok", last_run: "2026-11-17T05:37:00Z", age_h: 3, late_after_h: 36, next_run: null, last_error: null, runs: [], ...over },
  counts, sources: [],
});
const code = (status: "green" | "amber" | "red", unreviewed = 0, age = 30): AdminCodeCurrency => ({
  code: { source_id: "x", as_of: "2026-06-17", ingested_at: null, age_days: age, lag: { title17_passed_since: 0, cited_other_passed_since: 0, unreviewed, oldest_unreviewed_days: null, uncodified_applied: 0 },
    last_checked: null, check_state: "fresh", status, reasons: [] },
  clerk: { last_success: null, last_attempt: null, last_error: null, consecutive_failures: 0, snapshot_state: "ok", contract_ok: true, contract_problems: [] },
  amendments: [],
});

describe("what needs attention, in five words or fewer", () => {
  it("puts the checker first, then failing sources, then warnings", () => {
    expect(dataAttention(health({ state: "late", last_run: null }))).toMatchObject({ tone: "red", words: "Daily check never ran" });
    expect(dataAttention(health({}, { alarm: 2, error: 1, warn: 4 }))).toMatchObject({ tone: "red", words: "3 sources failing" });
    expect(dataAttention(health({}, { warn: 1 }))).toMatchObject({ tone: "yellow", words: "1 source to check" });
    expect(dataAttention(health({}, { ok: 80 }))).toMatchObject({ tone: "green", words: "All sources fresh" });
  });

  it("says the code text's age, amendments to read, or that it's current", () => {
    expect(codeAttention(code("red", 0, 154))).toMatchObject({ tone: "red", words: "Code text 154 days old" });
    expect(codeAttention(code("amber", 3))).toMatchObject({ tone: "yellow", words: "3 amendments to review" });
    expect(codeAttention(code("green"))).toMatchObject({ tone: "green", words: "Code text current" });
    expect(correctionsAttention(1)).toMatchObject({ tone: "yellow", words: "1 report to review" });
    expect(correctionsAttention(0)).toMatchObject({ tone: "green", words: "No reports waiting" });
  });

  it("never runs past five words", () => {
    const all = [
      dataAttention(undefined), dataAttention(null), dataAttention(health({ state: "late" })), dataAttention(health({}, { alarm: 12 })),
      codeAttention(undefined), codeAttention(null), codeAttention(code("red", 0, 1540)), codeAttention({ ...code("amber"), code: { ...code("amber").code, check_state: "unknown" } }),
      correctionsAttention(undefined), correctionsAttention(null), correctionsAttention(120),
    ];
    for (const a of all) expect(words(a.words), a.words).toBeLessThanOrEqual(5);
  });

  it("opens the named section, else Overview", () => {
    expect(adminSectionFrom("code")).toBe("code");
    expect(adminSectionFrom("nope")).toBe("overview");
    expect(adminSectionFrom(undefined)).toBe("overview");
  });
});

function page(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin" element={<AdminNextPage />} />
        <Route path="/admin/:section" element={<AdminNextPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the badges", () => {
  it("count what waits; red only for something failing; a dot when there is nothing to count", () => {
    expect(sectionBadges(health({}, { alarm: 2, error: 1 }), code("amber", 3), 4)).toEqual({
      data: { count: 3, tone: "red", spoken: "3 sources failing" },
      code: { count: 3, tone: "work", spoken: "3 amendments to review" },
      corrections: { count: 4, tone: "work", spoken: "4 reports to review" },
    });
    // Nothing to count: a dot, never a "!" (it reads like a 1).
    expect(sectionBadges(health({ state: "late" }), code("red", 0, 154), 0)).toEqual({
      data: { count: null, tone: "red", spoken: "daily check not running" },
      code: { count: null, tone: "red", spoken: "code text out of date" },
    });
    expect(badgeText(3)).toBe("3");
    expect(badgeText(12)).toBe("9+");
    expect(badgeText(null)).toBeNull();
    expect(sectionBadges(health({}, { ok: 80 }), code("green"), 0)).toEqual({});
    expect(sectionBadges(undefined, null, undefined)).toEqual({});
  });
});

describe("the page", () => {
  it("the sections fold to a strip like the chat's list, and open as a sheet from the top bar", async () => {
    try { sessionStorage.removeItem("urbanlayer-next-adminnav"); } catch { /* jsdom */ }
    page("/admin/usage");
    await screen.findByTestId("admin-usage-tiles");
    fireEvent.click(screen.getByTestId("admin-nav-hide"));
    const strip = screen.getByTestId("admin-nav-strip");
    expect(within(strip).getByRole("link", { name: "Usage and cost" }).getAttribute("aria-current")).toBe("page");
    expect(sessionStorage.getItem("urbanlayer-next-adminnav")).toBe("hidden");
    fireEvent.click(screen.getByTestId("admin-nav-expand"));
    expect(screen.getByTestId("admin-nav")).toBeTruthy();
    fireEvent.click(screen.getByTestId("admin-nav-show"));
    expect(await screen.findByTestId("admin-nav-sheet")).toBeTruthy();
    // The phone's Sections tool carries everything waiting: the 2 open reports.
    expect(screen.getByTestId("admin-nav-show-badge").textContent).toBe("2");
    expect(screen.getByTestId("admin-nav-show").getAttribute("aria-label")).toBe("Sections, 2 reports to review");
  });

  it("opens on Overview: four figures, what needs attention linked to its section, the section list, axe", async () => {
    const { container } = page("/admin");
    const tiles = await screen.findByTestId("admin-overview-tiles");
    expect(tiles.textContent).toContain("12");
    expect(tiles.textContent).toContain("$0.42");
    await waitFor(() => expect(screen.getByTestId("attention-corrections").textContent).toContain("2 reports to review"));
    expect(screen.getByTestId("attention-corrections").getAttribute("href")).toBe("/admin/corrections");
    const nav = screen.getByTestId("admin-nav");
    expect(within(nav).getByRole("link", { name: "Overview" }).getAttribute("aria-current")).toBe("page");
    expect(within(nav).getAllByRole("link").map((l) => l.getAttribute("aria-label") ?? l.textContent)).toEqual([
      "Overview", "Usage and cost", "Visitors", "Answer quality", "Requests", "Data health", "Corrections, 2 reports to review", "Code updates", "Early access",
    ]);
    // The badge on Corrections counts the open reports.
    expect(within(nav).getByTestId("admin-badge-corrections").textContent).toBe("2");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("a section at its own address; the period switch only where figures follow it", async () => {
    page("/admin/access");
    await screen.findByTestId("early-access");
    expect(screen.getByRole("heading", { name: "Early access" })).toBeTruthy();
    expect(screen.queryByTestId("admin-period")).toBeNull();
    cleanup();
    page("/admin/usage");
    await screen.findByTestId("admin-usage-tiles");
    fireEvent.click(within(screen.getByTestId("admin-period")).getByRole("button", { name: "7 days" }));
    await waitFor(() => expect(fetchAdminOverview).toHaveBeenLastCalledWith("7d"));
  });
});

describe("Early access", () => {
  it("makes a code from a label, a length chip and the uses stepper", async () => {
    vi.mocked(createAdminVoucher).mockResolvedValue({ code: "UL-ABC123", label: "Realtor meetup", duration_days: 90, max_redemptions: 3, disabled: 0, created_at: 0, redemptions: [] });
    const { container } = render(<div className="ui-next"><VouchersSection /></div>);
    const form = await screen.findByTestId("voucher-new");
    fireEvent.change(within(form).getByLabelText("Who it's for"), { target: { value: " Realtor meetup " } });
    fireEvent.click(within(form).getByRole("radio", { name: "90 days" }));
    fireEvent.click(within(form).getByRole("button", { name: "One more use" }));
    fireEvent.click(within(form).getByRole("button", { name: "One more use" }));
    expect(within(form).getByTestId("voucher-uses").textContent).toBe("3");
    fireEvent.click(within(form).getByTestId("voucher-make"));
    await waitFor(() => expect(createAdminVoucher).toHaveBeenCalledWith({ label: "Realtor meetup", duration_days: 90, max_redemptions: 3, code: undefined }));
    const row = await screen.findByTestId("voucher-row");
    expect(row.textContent).toContain("UL-ABC123");
    expect(row.textContent).toContain("90 days");
    expect(row.textContent).toContain("0 of 3 used");
    expect(within(form).getByRole("status").textContent).toContain("UL-ABC123");
    expect(await axeViolations(container)).toEqual([]);
  });
});
