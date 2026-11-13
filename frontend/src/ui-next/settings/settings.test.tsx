// Settings in the new UI (design B, 2026-11-13): which sections a visitor gets, the address that opens each, the
// plan's figures from /api/usage, sign-in methods, and the typed delete. No network: the api module is mocked.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { axeViolations } from "../test/axe";
import { sectionFrom, sectionsFor, usedShare } from "./settingsModel";

type Auth = Record<string, unknown>;
let auth: Auth;
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
const theme = vi.hoisted(() => ({ setTheme: vi.fn() }));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: theme.setTheme }),
}));
const api = vi.hoisted(() => ({
  fetchMyPurchases: vi.fn(), getSubscription: vi.fn(), getUsage: vi.fn(), listConversations: vi.fn(), redeemVoucher: vi.fn(),
  createBillingPortal: vi.fn(), deleteAccount: vi.fn(), getSignInIdentities: vi.fn(), removeSignInIdentity: vi.fn(),
  startLinkProvider: vi.fn(), createCheckoutSession: vi.fn(),
  CheckoutError: class CheckoutError extends Error { reason: string; constructor(r: string) { super(r); this.reason = r; } },
  savedApi: { lots: vi.fn(), searches: vi.fn() },
}));
vi.mock("../../lib/api", () => api);

import SettingsNextPage from "./SettingsNextPage";

const signedIn = (tier = "free"): Auth => ({
  user: { id: "u1", name: "Pat Lee", email: "pat@example.com", picture_url: null, tier },
  isAuthenticated: true, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn(async () => {}),
  providers: [{ id: "google", test: false }], signInWith: vi.fn(), checkAuth: vi.fn(),
});

/** `/api/subscription` (Item 123): free with purchases off unless overridden. */
function sub(over: Record<string, unknown> = {}) {
  return {
    tier: "free", plan: "free", source: null, status: null, interval: null, renews_on: null, ends_on: null,
    past_due: false, subscription_active: false, can_manage: false, comp_until: null, purchases_enabled: false, ...over,
  };
}
const PAID = { tier: "premium", plan: "pro", source: "stripe", status: "active", interval: "year", subscription_active: true, can_manage: true };

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings" element={<SettingsNextPage />} />
        <Route path="/settings/:section" element={<SettingsNextPage />} />
        <Route path="*" element={<div data-testid="elsewhere" />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  auth = signedIn();
  api.fetchMyPurchases.mockResolvedValue([]);
  api.getSubscription.mockResolvedValue(sub());
  api.getUsage.mockResolvedValue({ plan: "free", used: 12, limit: 50, resets_on: "2026-12-01", pro_limit: 200 });
  api.listConversations.mockResolvedValue([{ id: "c1" }, { id: "c2" }]);
  api.savedApi.lots.mockResolvedValue({ lots: [{}, {}, {}], max: 200 });
  api.savedApi.searches.mockResolvedValue({ searches: [{}], max: 20 });
  api.getSignInIdentities.mockResolvedValue({
    identities: [{ provider: "google", email: "p•••@example.com", private_email: false, added_at: Date.UTC(2026, 10, 2), last_used_at: 0 }],
    available: [{ id: "google", test: false }, { id: "apple", test: false }, { id: "microsoft", test: false }],
  });
});
afterEach(cleanup);

describe("settingsModel", () => {
  it("gives each visitor only the sections that apply", () => {
    expect(sectionsFor({ signedIn: false, authRequired: true, hasReports: false })).toEqual(["preferences"]);
    expect(sectionsFor({ signedIn: true, authRequired: true, hasReports: false }))
      .toEqual(["account", "plan", "signin", "preferences", "things", "delete"]);
    expect(sectionsFor({ signedIn: true, authRequired: true, hasReports: true })).toContain("reports");
    // Sign-in off (development): nothing to sign in with, nothing to delete.
    expect(sectionsFor({ signedIn: true, authRequired: false, hasReports: false })).toEqual(["account", "plan", "preferences", "things"]);
  });

  it("opens the named section only when the visitor has it", () => {
    const s = sectionsFor({ signedIn: true, authRequired: true, hasReports: false });
    expect(sectionFrom("plan", s)).toBe("plan");
    expect(sectionFrom("reports", s)).toBe("account");
    expect(sectionFrom("nonsense", s)).toBe("account");
    expect(sectionFrom(undefined, ["preferences"])).toBe("preferences");
  });

  it("the share used is clamped and absent without a limit", () => {
    expect(usedShare(12, 50)).toBeCloseTo(0.24);
    expect(usedShare(60, 50)).toBe(1);
    expect(usedShare(3, null)).toBeNull();
  });
});

describe("the page", () => {
  it("Plan: the month's questions from the server, when they come back, and Pro not for sale yet", async () => {
    const { container } = at("/settings/plan");
    const usage = await screen.findByTestId("settings-usage");
    expect(usage.textContent).toContain("12");
    expect(usage.textContent).toContain("of 50");
    expect(usage.textContent).toContain("Dec 1");
    expect(within(usage).getByRole("img", { name: "12 of 50 questions used" })).toBeTruthy();
    const offer = await screen.findByTestId("settings-pro-offer");
    expect(offer.textContent).toContain("200 questions a month, Deep analysis on every lot");
    expect(offer.textContent).toContain("Coming soon");
    expect(within(offer).getByRole("link", { name: "See pricing" }).getAttribute("href")).toBe("/pricing");
    expect(screen.queryByTestId("settings-get-pro")).toBeNull();
    expect(screen.getByRole("link", { name: "Plan and questions" }).getAttribute("aria-current")).toBe("page");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("Plan, free with purchases on: choose monthly or yearly, then Get Pro starts that checkout", async () => {
    api.getSubscription.mockResolvedValue(sub({ purchases_enabled: true }));
    api.createCheckoutSession.mockReturnValue(new Promise(() => {}));
    const { container } = at("/settings/plan");
    const year = await screen.findByRole("radio", { name: /\$199 a year/ });
    expect(screen.getByRole("radio", { name: "$19 a month" }).getAttribute("aria-checked")).toBe("true");
    expect(year.textContent).toContain("Save $29");
    fireEvent.click(year);
    expect(year.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByTestId("settings-get-pro"));
    expect(api.createCheckoutSession).toHaveBeenCalledWith("year", "settings");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("Plan, back from Stripe: confirming until the webhook lands, never from the address alone", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      api.getSubscription.mockResolvedValueOnce(sub({ purchases_enabled: true }))
        .mockResolvedValue(sub({ ...PAID, renews_on: "2027-11-13", purchases_enabled: true }));
      at("/settings/plan?checkout=done");
      expect((await screen.findByTestId("settings-confirming")).textContent).toContain("Confirming your payment with Stripe");
      expect(screen.getByTestId("settings-plan").textContent).toContain("Free");
      await vi.advanceTimersByTimeAsync(2100);
      await waitFor(() => expect(screen.queryByTestId("settings-confirming")).toBeNull());
      expect(screen.getByTestId("settings-date-tile").textContent).toContain("Nov 13, 2027");
      expect(auth.checkAuth).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("Plan, Pro renewing: the renewal date and price, and Manage billing opens Stripe's page", async () => {
    auth = signedIn("premium");
    api.getSubscription.mockResolvedValue(sub({ ...PAID, renews_on: "2027-12-13" }));
    api.createBillingPortal.mockReturnValue(new Promise(() => {}));
    at("/settings/plan");
    const tile = await screen.findByTestId("settings-date-tile");
    expect(tile.textContent).toContain("Renews");
    expect(tile.textContent).toContain("Dec 13, 2027");
    expect(tile.textContent).toContain("$199 a year");
    fireEvent.click(screen.getByRole("button", { name: "Manage billing" }));
    expect(api.createBillingPortal).toHaveBeenCalled();
    expect(screen.queryByText("Coming soon")).toBeNull();
  });

  it("Plan, Pro canceled: Pro until the date, then free, and Keep Pro", async () => {
    auth = signedIn("premium");
    api.getSubscription.mockResolvedValue(sub({ ...PAID, ends_on: "2026-12-13" }));
    at("/settings/plan");
    expect((await screen.findByTestId("settings-date-tile")).textContent).toContain("Then the free plan");
    const plan = screen.getByTestId("settings-plan");
    expect(plan.textContent).toContain("Pro until Dec 13, 2026");
    expect(plan.textContent).toContain("You canceled.");
    expect(within(plan).getByRole("button", { name: "Keep Pro" })).toBeTruthy();
  });

  it("Plan, a declined card Stripe is retrying: still Pro, and a way to update the card", async () => {
    auth = signedIn("premium");
    api.getSubscription.mockResolvedValue(sub({ ...PAID, status: "past_due", past_due: true, renews_on: "2026-12-13" }));
    at("/settings/plan");
    expect(await screen.findByText("Payment failed")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Update your card" })).toBeTruthy();
  });

  it("Plan, an access code: Pro until when, with nothing to manage at Stripe", async () => {
    auth = signedIn("premium");
    api.getSubscription.mockResolvedValue(sub({ tier: "premium", plan: "pro", source: "voucher", comp_until: Date.UTC(2027, 0, 15) }));
    at("/settings/plan");
    expect((await screen.findByTestId("settings-plan")).textContent).toMatch(/Early access: Pro, 200 questions a month, until/);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Manage billing" })).toBeNull());
  });

  it("Plan: an access code applies and says until when", async () => {
    api.redeemVoucher.mockResolvedValue({ ok: true, premium_until: Date.UTC(2027, 0, 15) });
    at("/settings/plan");
    fireEvent.change(await screen.findByLabelText("An early-access code gives you Pro for a while."), { target: { value: "ul-abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect((await screen.findByRole("status")).textContent).toContain("Early access is on until");
    expect(api.redeemVoucher).toHaveBeenCalledWith("ul-abc");
  });

  it("Sign-in methods: the account's methods, the only one can't be removed, the others to add", async () => {
    at("/settings/signin");
    const list = await screen.findByTestId("signin-methods");
    expect(list.textContent).toContain("Google");
    expect(list.textContent).toContain("Only way in");
    expect(within(list).queryByRole("button", { name: "Remove" })).toBeNull();
    const adds = screen.getAllByRole("button", { name: /^Continue with / }).map((b) => b.getAttribute("data-provider"));
    expect(adds).toEqual(["apple", "microsoft"]);
  });

  it("Your things: counts, each a link to its own page", async () => {
    at("/settings/things");
    const lots = await screen.findByRole("link", { name: /Saved lots/ });
    await waitFor(() => expect(lots.textContent).toContain("3"));
    expect(lots.getAttribute("href")).toBe("/saved");
    expect(screen.getByRole("link", { name: /Saved searches/ }).getAttribute("href")).toBe("/saved?tab=searches");
    expect(screen.getByRole("link", { name: /Chats/ }).textContent).toContain("2");
  });

  it("Preferences: the theme as a radio group", async () => {
    at("/settings/preferences");
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    fireEvent.click(within(group).getByRole("radio", { name: /Dark/ }));
    expect(theme.setTheme).toHaveBeenCalledWith("dark");
  });

  it("Delete: nothing happens until the word is typed", async () => {
    api.deleteAccount.mockResolvedValue(undefined);
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    at("/settings/delete");
    fireEvent.click(await screen.findByTestId("settings-delete-open"));
    const confirm = await screen.findByTestId("settings-delete-confirm");
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Type “delete” to confirm"), { target: { value: "DELETE" } });
    expect((confirm as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    expect(api.deleteAccount).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("Reports appear only for an account that bought one", async () => {
    at("/settings");
    await screen.findByTestId("settings-nav");
    expect(screen.queryByRole("link", { name: "Reports you bought" })).toBeNull();
    cleanup();
    api.fetchMyPurchases.mockResolvedValue([{ id: 1, address: "1601 N Milwaukee Ave", pin: null, lat: 0, lon: 0, created_at: 0 }]);
    at("/settings");
    expect(await screen.findAllByRole("link", { name: "Reports you bought" })).not.toHaveLength(0);
  });

  it("signed out: Preferences and one quiet sign-in line, nothing locked", async () => {
    auth = { user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() };
    at("/settings/plan");
    expect(await screen.findByTestId("settings-signin")).toBeTruthy();
    expect(screen.getByTestId("settings-preferences")).toBeTruthy();
    expect(screen.queryByTestId("settings-usage")).toBeNull();
    expect(api.fetchMyPurchases).not.toHaveBeenCalled();
  });
});
