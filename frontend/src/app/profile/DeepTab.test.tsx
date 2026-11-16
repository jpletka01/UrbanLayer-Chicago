// The Deep analysis tab's states (decision Item 124): signed out, the free one unused (one button, browsing claims
// nothing), used on another lot (one quiet Pro offer), a lot we couldn't confirm, and the analysis itself. No network:
// the api module and auth are mocked.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../lib/i18n";
import { axeViolations } from "../test/axe";

let auth: Record<string, unknown>;
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
const api = vi.hoisted(() => {
  class DeepClaimError extends Error { status: number; freePin: string | null; constructor(s: number, p: string | null) { super("x"); this.status = s; this.freePin = p; } }
  class DeepAnalysisError extends Error { status: number; constructor(s: number) { super("x"); this.status = s; } }
  return {
    getEntitlements: vi.fn(), claimDeepAnalysis: vi.fn(), getDeepAnalysis: vi.fn(), getDeepProject: vi.fn(), putDeepProject: vi.fn(),
    DeepClaimError, DeepAnalysisError,
  };
});
vi.mock("../../lib/api", () => api);

import { DeepTab } from "./DeepTab";
import { analysisCache } from "./deepGate";

const PIN = "14331030110000";
const A = (value: number, low: number, high: number, source = "builders_reported") => ({ value, low, high, unit: "x", source, as_of: "2025" });
const ANALYSIS = {
  pin: PIN, address: "642 W BELDEN AVE", approximate: false, envelope: null, partial_failures: [],
  inputs: {
    lot: { land_sqft: 3350, far: 2, max_height_ft: 45, units_allowed: 8, lot_area_per_unit: 400, footprint_sqft: null },
    last_sale: { price: 1_207_000, date: "2023-05-01", deed_type: "WARRANTY" },
    area_sales: { condo: { median: 605_000, n: 900, year: "2025" } },
    rents: { census: { "2_bedrooms": { estimate: 3084, moe: 487, scope: "tract" } }, hud: null, acs_period: "2020–2024" },
    tax: { effective_rate: 0.0201, tax_year: 2024, current_bill: 23024 },
    assumptions: {
      build_cost_sqft: A(250, 200, 275), soft_cost_pct: A(0.18, 0.15, 0.25, "terner_2024"), loan_to_cost: A(0.65, 0.6, 0.75, "lenders_2026"),
      loan_rate: A(0.09, 0.0775, 0.1175, "lenders_2026"), build_months: A(14, 10, 24, "lenders_2026"), selling_pct: A(0.06, 0.04, 0.08, "common_practice"),
      profit_on_cost: A(0.2, 0.15, 0.25, "developer_rule"), vacancy_pct: A(0.05, 0.03, 0.08, "common_practice"), opex_pct: A(0.3, 0.25, 0.4, "common_practice"),
      cap_rate: A(0.0625, 0.055, 0.07, "chicago_brokers_2026"), target_yield: A(0.0775, 0.07, 0.09, "spread_rule"),
    },
    floor_ft: 11,
  },
};
const ent = (d: Record<string, unknown>) => ({ signed_in: true, deep_analysis: { unlimited: false, free_left: 1, free_pin: null, free_address: null, ...d } });
const show = (props: Partial<{ pin: string | null; exact: boolean }> = {}) => {
  const onProject = vi.fn();
  const r = render(<MemoryRouter><DeepTab pin={PIN} exact onProject={onProject} {...props} /></MemoryRouter>);
  return { ...r, onProject };
};

beforeEach(() => {
  vi.clearAllMocks();
  analysisCache.clear();
  auth = { isAuthenticated: true, authRequired: true, signIn: vi.fn() };
  api.getDeepProject.mockResolvedValue({ project: null, numbers: null, step: 0 });
  api.putDeepProject.mockResolvedValue(undefined);
});
afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

describe("who sees what", () => {
  it("signed out: the outline and one sign-in line, nothing fetched", async () => {
    auth = { isAuthenticated: false, authRequired: true, signIn: vi.fn() };
    const { container } = show();
    fireEvent.click(screen.getByTestId("deep-sign-in"));
    expect(auth.signIn).toHaveBeenCalled();
    expect(screen.getByTestId("deep-outline")).toBeTruthy();
    expect(api.getDeepAnalysis).not.toHaveBeenCalled();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("free, unused: opening the tab claims nothing; the button does, then the analysis loads", async () => {
    api.getEntitlements.mockResolvedValue(ent({}));
    api.claimDeepAnalysis.mockResolvedValue({ ok: true, pin: PIN, unlimited: false });
    api.getDeepAnalysis.mockResolvedValue(ANALYSIS);
    show();
    const button = await screen.findByTestId("deep-claim");
    expect(api.claimDeepAnalysis).not.toHaveBeenCalled();
    expect(api.getDeepAnalysis).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() => expect(api.claimDeepAnalysis).toHaveBeenCalledWith(PIN));
    expect((await screen.findByTestId("deep-bid")).textContent).toBe("$1.75M");
  });

  it("used on another lot: names it with a link, one quiet Pro offer, no analysis fetched", async () => {
    api.getEntitlements.mockResolvedValue(ent({ free_left: 0, free_pin: "14283190070000", free_address: "481 W DEMING PL" }));
    const { container } = show();
    const box = await screen.findByTestId("deep-elsewhere");
    expect(within(box).getByRole("link", { name: "481 W DEMING PL" }).getAttribute("href")).toBe("/scorecard?pin=14283190070000");
    expect(within(box).getByRole("link", { name: "See Pro" }).getAttribute("href")).toBe("/pricing");
    expect(api.getDeepAnalysis).not.toHaveBeenCalled();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("a condo unit of the free lot opens it (the first ten digits name the lot)", async () => {
    api.getEntitlements.mockResolvedValue(ent({ free_left: 0, free_pin: "14331030111002" }));
    api.getDeepAnalysis.mockResolvedValue(ANALYSIS);
    show();
    expect(await screen.findByTestId("deep-bid")).toBeTruthy();
  });

  it("a claim refused because the free one went elsewhere moves to that state", async () => {
    api.getEntitlements.mockResolvedValue(ent({}));
    api.claimDeepAnalysis.mockRejectedValue(new api.DeepClaimError(409, "14283190070000"));
    show();
    fireEvent.click(await screen.findByTestId("deep-claim"));
    expect(await screen.findByTestId("deep-elsewhere")).toBeTruthy();
  });

  it("a lot we couldn't confirm: no claim, no fetch, a way to pick the lot", () => {
    show({ exact: false });
    expect(screen.getByTestId("deep-tab").getAttribute("data-gate")).toBe("approximate");
    expect(screen.queryByTestId("deep-claim")).toBeNull();
    expect(api.getEntitlements).not.toHaveBeenCalled();
  });
});

describe("the analysis", () => {
  beforeEach(() => {
    api.getEntitlements.mockResolvedValue(ent({ unlimited: true }));
    api.getDeepAnalysis.mockResolvedValue(ANALYSIS);
  });

  it("the most you can pay first, the projects with their limits as rings, sourced numbers, the stress grid", async () => {
    const { container, onProject } = show();
    expect((await screen.findByTestId("deep-answer")).textContent).toMatch(/up to about \$1\.75M .* last sold for \$1\.21M/);
    expect(screen.getByTestId("deep-project-largest").getAttribute("data-selected")).toBe("true");
    expect(within(screen.getByTestId("deep-project-largest")).getAllByRole("img").map((i) => i.getAttribute("aria-label")))
      .toEqual(["Floor area: 100% of the limit", "Height: 98% of the limit"]);
    expect(screen.getByText(/What Chicago builders report, 2025/)).toBeTruthy();
    expect(within(screen.getByTestId("deep-stress")).getAllByRole("cell")).toHaveLength(9);
    expect(onProject).toHaveBeenLastCalledWith({ heightFt: 44, capFt: 45, label: "Your project · 8 units · 4 floors" });
    expect(await axeViolations(container)).toEqual([]);
  });

  it("a floor over the height limit turns the project red and says so", async () => {
    const { onProject } = show();
    await screen.findByTestId("deep-bid");
    fireEvent.click(screen.getByRole("button", { name: "More: Floors" }));
    const own = screen.getByTestId("deep-project-own");
    expect(own.getAttribute("data-selected")).toBe("true");
    expect(own.textContent).toMatch(/Over a limit/);
    expect(onProject).toHaveBeenLastCalledWith(expect.objectContaining({ heightFt: 55, capFt: 45 }));
  });

  it("renting: no land price works here, said in words, never a negative price", async () => {
    show();
    await screen.findByTestId("deep-bid");
    fireEvent.click(screen.getByRole("radio", { name: "Rent them out" }));
    expect(screen.getByTestId("deep-bid").textContent).toBe("No land price works");
    expect(screen.getByTestId("deep-answer").textContent).toMatch(/doesn't meet your target/);
  });

  it("the sale price starts from what new condos sell for here, and says how it got there", async () => {
    api.getDeepAnalysis.mockResolvedValue({ ...ANALYSIS, inputs: { ...ANALYSIS.inputs, new_construction: {
      value: 462, low: 398, high: 578, level: 398, n: 1254, pooled_areas: ["7", "6"], new_sales: 0,
      years: ["2023", "2025"], premium: 1.161, premium_n: 71 } } });
    show();
    await screen.findByTestId("deep-bid");
    expect(screen.getByText(/A new condo here: \$462 a sq ft × 838 sq ft a unit .* 1\.16, the new-build premium .* with nearby areas .* no new condos sold here/)).toBeTruthy();
  });

  it("too many lots today: says so, no retry", async () => {
    api.getDeepAnalysis.mockRejectedValue(new api.DeepAnalysisError(429));
    show();
    expect(await screen.findByText(/a lot of lots for one day/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("renders in Spanish (usted)", async () => {
    await i18n.changeLanguage("es");
    show();
    expect((await screen.findByTestId("deep-answer")).textContent).toMatch(/Vender 8 unidades aquí permite pagar hasta/);
  });
});
