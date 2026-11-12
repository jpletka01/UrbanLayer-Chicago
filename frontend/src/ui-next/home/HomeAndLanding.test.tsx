// "/" in the new UI (Phase 8, wireframe v5): the landing for visitors and the home for signed-in visitors. The landing
// has its one action pinned, figures that end at their real values for screen readers, and an Explore button; the
// home lists Saved lots first, then the last six Recent lots with a bookmark each and "Clear all", and no per-lot
// remove (owner, 2026-11-12).
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import RootNextPage from "./RootNextPage";
import { axeViolations } from "../test/axe";
import { lotKey, rememberRecent, readSaved } from "./lotMemory";

let auth = { user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() };
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: vi.fn() }),
}));
vi.mock("../../lib/api", () => ({
  listConversations: vi.fn().mockResolvedValue([{ id: "c1", title: "Coach house at 2611 N Sawyer", message_count: 2, createdAt: 0, updatedAt: Date.now() }]),
  getAutocomplete: vi.fn().mockResolvedValue([]),
}));

// jsdom has no IntersectionObserver; the landing's count-ups and bar fills wait for one (they never fire here).
class NoIntersection { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver ??= NoIntersection;

const mount = (path = "/") => render(<MemoryRouter initialEntries={[path]}><RootNextPage /></MemoryRouter>);
const lot = (n: number) => ({ key: lotKey(null, `${n} N Milwaukee Ave`), address: `${n} N Milwaukee Ave`, pin: null, zone: "B3-2", area: "West Town", outline: null });

beforeEach(() => {
  localStorage.clear();
  auth = { user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() };
});
afterEach(cleanup);

describe("the landing", () => {
  it("is what a visitor who isn't signed in sees: the headline, Explore, the pinned address bar", async () => {
    const { container } = mount();
    expect(screen.getByTestId("landing")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "Know what you can build on any Chicago lot." })).toBeTruthy();
    expect(screen.getAllByTestId("landing-explore")[0].getAttribute("href")).toBe("/discovery");
    const bar = screen.getByTestId("landing-bar");
    expect((within(bar).getByRole("textbox") as HTMLInputElement).value).toBe("1601 N Milwaukee Ave");
    expect(within(bar).getByRole("button", { name: "Show me this lot" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("gives screen readers the final figures while the visible ones count", () => {
    mount();
    const stats = screen.getByTestId("landing-stats");
    expect(stats.textContent).toContain("880,000");
    expect(stats.textContent).toContain("14,500");
  });

  it("shows the landing to a signed-in visitor who asks for it", () => {
    auth.isAuthenticated = true;
    mount("/?landing=1");
    expect(screen.getByTestId("landing")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open the app" })).toBeTruthy();
  });
});

describe("the signed-in home", () => {
  beforeEach(() => { auth.isAuthenticated = true; });

  it("lists Saved first, then Recent lots with a bookmark each and no per-lot remove", async () => {
    for (let i = 1; i <= 3; i++) rememberRecent(lot(i), i);
    const { container } = mount();
    const home = screen.getByTestId("home");
    const order = [...home.querySelectorAll("section h2")].map((h) => h.textContent);
    expect(order.slice(0, 2)).toEqual(["Saved lots", "Recent lots"]);
    const recent = screen.getByTestId("home-recent");
    expect(within(recent).getAllByTestId("home-lot")).toHaveLength(3);
    expect(within(recent).queryByRole("button", { name: /remove from recent/i })).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("saves a recent lot into Saved with its bookmark", () => {
    rememberRecent(lot(1));
    mount();
    fireEvent.click(within(screen.getByTestId("home-recent")).getByRole("button", { name: "Save 1 N Milwaukee Ave" }));
    expect(readSaved().map((l) => l.address)).toEqual(["1 N Milwaukee Ave"]);
    expect(within(screen.getByTestId("home-saved")).getByText("1 N Milwaukee Ave")).toBeTruthy();
    // Saved shows as selected, and its bookmark unsaves it.
    const unsave = within(screen.getByTestId("home-saved")).getByRole("button", { name: "Remove 1 N Milwaukee Ave from saved" });
    expect(unsave.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(unsave);
    expect(readSaved()).toEqual([]);
  });

  it("clears all recent lots at once, and folds the row away", () => {
    rememberRecent(lot(1));
    rememberRecent(lot(2));
    mount();
    const recent = screen.getByTestId("home-recent");
    const heading = within(recent).getByRole("button", { name: "Recent lots" });
    fireEvent.click(heading);
    expect(heading.getAttribute("aria-expanded")).toBe("false");
    expect((document.getElementById("home-recent-list") as HTMLElement).hidden).toBe(true);
    fireEvent.click(heading);
    expect((document.getElementById("home-recent-list") as HTMLElement).hidden).toBe(false);
    fireEvent.click(screen.getByTestId("home-clear"));
    // Nothing saved and nothing recent: the home goes back to its start-here block.
    expect(screen.queryByTestId("home-recent")).toBeNull();
    expect(screen.getByTestId("home-start")).toBeTruthy();
  });

  it("with nothing saved or opened yet, offers three lots to start from instead of empty rows", async () => {
    const { container } = mount();
    expect(screen.getAllByTestId("home-example").map((a) => a.getAttribute("href"))).toEqual([
      "/scorecard?address=1601+N+Milwaukee+Ave", "/scorecard?address=2541+N+Spaulding+Ave", "/scorecard?address=2611+N+Sawyer+Ave",
    ]);
    expect(screen.queryByTestId("home-recent")).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("keeps recent chats beside the lots", async () => {
    mount();
    expect(await within(screen.getByTestId("home-chats")).findByText("Coach house at 2611 N Sawyer")).toBeTruthy();
  });
});
