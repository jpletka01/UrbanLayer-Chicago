// Pricing in the new UI (Item 123): $19 a month or $199 a year, the free plan complete, Pro "Coming soon" while
// purchases are off, sign in before checkout, and the figures the page and Settings share. No network.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { axeViolations } from "../test/axe";
import { PRICE_CENTS, chicagoDay, dollars, planState, yearlyPerMonthCents, yearlySavingsCents } from "./pricingModel";

type Auth = Record<string, unknown>;
let auth: Auth;
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: vi.fn() }),
}));
const api = vi.hoisted(() => ({
  fetchPaymentsStatus: vi.fn(), createCheckoutSession: vi.fn(), createBillingPortal: vi.fn(),
  CheckoutError: class CheckoutError extends Error { reason: string; constructor(r: string) { super(r); this.reason = r; } },
}));
vi.mock("../../lib/api", () => api);

import PricingNextPage from "./PricingNextPage";

const person = (tier = "free"): Auth => ({
  user: { id: "u1", name: "Pat", email: null, picture_url: null, tier },
  isAuthenticated: true, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn(),
  providers: [], signInWith: vi.fn(), checkAuth: vi.fn(),
});

function page() {
  return render(<MemoryRouter initialEntries={["/pricing"]}><PricingNextPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  auth = person();
  api.fetchPaymentsStatus.mockResolvedValue({ reports: false, subscriptions: true });
});
afterEach(cleanup);

describe("pricingModel", () => {
  it("Pro is $19 a month or $199 a year: $29 saved, $16.58 a month", () => {
    expect(PRICE_CENTS).toEqual({ month: 1900, year: 19900 });
    expect(yearlySavingsCents()).toBe(2900);
    expect(yearlyPerMonthCents()).toBe(1658);
    expect(dollars(1900, "en-US")).toBe("$19");
    expect(dollars(1658, "en-US")).toBe("$16.58");
  });

  it("a Chicago day never moves with the time zone", () => {
    expect(chicagoDay("2026-12-13", "en-US")).toBe("Dec 13, 2026");
  });

  it("the Plan state comes from Stripe's stored state, never from the return address alone", () => {
    const free = { plan: "free" as const, source: null, ends_on: null, past_due: false };
    expect(planState(free, "free", false)).toBe("free");
    expect(planState(free, "free", true)).toBe("confirming");
    const paid = { plan: "pro" as const, source: "stripe" as const, ends_on: null, past_due: false };
    expect(planState(paid, "premium", true)).toBe("pro_renewing");
    expect(planState({ ...paid, ends_on: "2026-12-13" }, "premium", false)).toBe("pro_ending");
    expect(planState({ ...paid, past_due: true }, "premium", false)).toBe("pro_past_due");
    expect(planState({ plan: "pro", source: "voucher", ends_on: null, past_due: false }, "premium", false)).toBe("voucher");
    expect(planState({ plan: "admin", source: null, ends_on: null, past_due: false }, "admin", false)).toBe("admin");
    expect(planState(null, "free", false)).toBe("free");
  });
});

describe("the page", () => {
  it("Free and Pro side by side, the free plan complete, nothing locked", async () => {
    const { container } = page();
    const free = screen.getByTestId("pricing-free");
    expect(free.textContent).toContain("$0");
    expect(free.textContent).toContain("One Deep analysis, free");
    expect(within(free).getByText("Your plan")).toBeTruthy();
    const pro = screen.getByTestId("pricing-pro");
    expect(screen.getByTestId("pricing-price").textContent).toBe("$19");
    expect(pro.textContent).toContain("200 questions a month");
    expect(await screen.findByTestId("pricing-get-pro")).toBeTruthy();
    expect(container.textContent).not.toMatch(/\$99|\$25/);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("Yearly shows $199, the monthly figure and the saving; Get Pro starts the yearly checkout", async () => {
    api.createCheckoutSession.mockReturnValue(new Promise(() => {}));
    page();
    const year = screen.getByRole("radio", { name: /Yearly/ });
    expect(year.textContent).toContain("Save $29");
    fireEvent.click(year);
    expect(screen.getByTestId("pricing-price").textContent).toBe("$199");
    expect(screen.getByTestId("pricing-pro").textContent).toContain("$16.58 a month, billed yearly");
    const button = await screen.findByTestId("pricing-get-pro");
    expect(button.textContent).toBe("Get Pro, $199 a year");
    fireEvent.click(button);
    expect(api.createCheckoutSession).toHaveBeenCalledWith("year", "pricing");
    expect((await screen.findByTestId("pricing-get-pro")).textContent).toBe("Opening Stripe…");
  });

  it("purchases off: Pro says Coming soon, no button", async () => {
    api.fetchPaymentsStatus.mockResolvedValue({ reports: false, subscriptions: false });
    page();
    expect(await screen.findByText("Coming soon")).toBeTruthy();
    expect(screen.queryByTestId("pricing-get-pro")).toBeNull();
  });

  it("signed out: sign in first, nothing is sent to Stripe", async () => {
    auth = { ...person(), user: null, isAuthenticated: false };
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Sign in to get Pro" }));
    expect(auth.signIn).toHaveBeenCalled();
    expect(api.createCheckoutSession).not.toHaveBeenCalled();
    expect(screen.queryByText("Your plan")).toBeNull();
  });

  it("a failed checkout says nothing was charged", async () => {
    api.createCheckoutSession.mockRejectedValue(new api.CheckoutError("error"));
    page();
    fireEvent.click(await screen.findByTestId("pricing-get-pro"));
    expect((await screen.findByRole("alert")).textContent).toContain("nothing was charged");
  });

  it("a Pro account sees its plan on Pro and a way to Settings", async () => {
    auth = person("premium");
    page();
    const pro = screen.getByTestId("pricing-pro");
    expect(within(pro).getByText("Your plan")).toBeTruthy();
    expect(within(pro).getByRole("link", { name: "See your plan" }).getAttribute("href")).toBe("/settings/plan");
    expect(within(screen.getByTestId("pricing-free")).queryByText("Your plan")).toBeNull();
  });
});
