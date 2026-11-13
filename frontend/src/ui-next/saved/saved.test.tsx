// Saved (Phase 9, decision Item 119): browser saves move to the account once; the change lines say what changed and
// open the right place; the page is usable signed out (no wall) and signed in (changes, notes, searches).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { axeViolations } from "../test/axe";
import type { SavedChange } from "../../lib/api";

let auth = { user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() };
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: vi.fn() }),
}));
vi.mock("../../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("../../discovery/registryClient", () => ({ loadRegistry: vi.fn().mockResolvedValue(null) }));

const wire = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `L${n}`, key: `addr:${n} n milwaukee ave`, pin: null, address: `${n} N Milwaukee Ave`, lat: 41.91, lon: -87.68,
  zone: "B3-2", area: "West Town", outline: null, note: "", saved_at: Date.UTC(2026, 10, 1), watching_since: null, ...extra,
});
const api = vi.hoisted(() => ({
  lots: vi.fn(), merge: vi.fn(), save: vi.fn(), unsave: vi.fn(), note: vi.fn(), changes: vi.fn(),
  searches: vi.fn(), searchNew: vi.fn(), searchSeen: vi.fn(), renameSearch: vi.fn(), deleteSearch: vi.fn(), saveSearch: vi.fn(),
}));
vi.mock("../../lib/api", () => ({
  savedApi: api,
  SavedError: class SavedError extends Error { status: number; constructor(s: number) { super(String(s)); this.status = s; } },
  listConversations: vi.fn().mockResolvedValue([]),
}));

class Seen {
  cb: IntersectionObserverCallback;
  constructor(cb: IntersectionObserverCallback) { this.cb = cb; }
  observe(el: Element) { this.cb([{ isIntersecting: true, target: el } as IntersectionObserverEntry], this as unknown as IntersectionObserver); }
  unobserve() {} disconnect() {} takeRecords() { return []; }
}
(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = Seen;

const { _resetForTests, pointOf, toInput } = await import("./savedStore");
const { changeLine, familyOf, limiter, shortName, uncheckedWords } = await import("./savedModel");
const { default: SavedNextPage } = await import("./SavedNextPage");
const { SAVED_KEY, readSaved } = await import("../home/lotMemory");

const mount = (path = "/saved") => render(<MemoryRouter initialEntries={[path]}><SavedNextPage /></MemoryRouter>);
const t = (k: string, o?: Record<string, unknown>) => `${k}${o ? JSON.stringify(o) : ""}`;

beforeEach(() => {
  localStorage.clear();
  _resetForTests();
  Object.values(api).forEach((f) => f.mockReset());
  auth = { user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() };
});
afterEach(cleanup);

describe("moving a browser save to the account", () => {
  it("places a lot by its point, else the middle of its outline, else not at all", () => {
    expect(pointOf({ lat: 41.9, lon: -87.6, outline: null })).toEqual({ lat: 41.9, lon: -87.6 });
    expect(pointOf({ lat: null, lon: null, outline: [[-87.6, 41.9], [-87.8, 41.9], [-87.7, 42.0]] })).toEqual({ lat: expect.closeTo(41.933, 2), lon: expect.closeTo(-87.7, 5) });
    expect(toInput({ key: "k", address: "x", pin: "14-31-325-001-0000", zone: null, area: null, outline: null })).toBeNull();
    expect(toInput({ key: "k", address: "x", pin: "14-31-325-001-0000", zone: null, area: null, outline: null, lat: 41.9, lon: -87.6, at: 5 }))
      .toMatchObject({ pin: "14313250010000", saved_at: 5 });
  });

  it("moves the browser's saves in once on sign-in, and keeps the ones it can't place", async () => {
    auth.isAuthenticated = true;
    localStorage.setItem(SAVED_KEY, JSON.stringify([
      { key: "addr:1 n milwaukee ave", address: "1 N Milwaukee Ave", pin: null, zone: null, area: null, outline: null, at: 1, lat: 41.91, lon: -87.68 },
      { key: "addr:9 n nowhere", address: "9 N Nowhere", pin: null, zone: null, area: null, outline: null, at: 2 },
    ]));
    api.merge.mockResolvedValue({ added: 1, skipped: 0, lots: [wire(1)], max: 200 });
    api.changes.mockResolvedValue({ since: "2026-11-01", watching_since: null, status: "none", changes: [], unchecked: [] });
    mount();
    expect(await screen.findByTestId("saved-moved")).toBeTruthy();
    expect(api.merge).toHaveBeenCalledTimes(1);
    expect(api.merge.mock.calls[0][0]).toHaveLength(1);
    expect(readSaved().map((l) => l.address)).toEqual(["9 N Nowhere"]);
    expect(screen.getByTestId("saved-moved").textContent).toContain("1 stays in this browser");
  });
});

describe("change lines", () => {
  const lot = { pin: "14313250010000", address: "1601 N Milwaukee Ave" };
  const money = (v: number) => `$${v}`;
  it("words each change and sends records to History, filings to the Clerk", () => {
    const sale = changeLine({ kind: "sale", date: "2026-11-03", price: 450000 } as SavedChange, lot, t, money);
    expect(sale.text).toBe('saved.change.soldFor{"price":"$450000"}');
    expect(sale.href).toBe("/scorecard?pin=14313250010000&address=1601+N+Milwaukee+Ave&tab=history");
    const filed = changeLine({ kind: "rezoning_filed", date: "2026-11-04", record: "O2026-1", title: "x", url: "https://chicityclerkelms.chicago.gov/x" } as SavedChange, lot, t, money);
    expect(filed.external).toBe(true);
    expect(filed.href).toContain("chicityclerkelms");
    const overlay = changeLine({ kind: "overlay", date: null, change: "added", layer: "tod_cta", name: null } as SavedChange, lot, t, money);
    expect(overlay.href).toContain("tab=build");
  });

  it("lists what couldn't be checked in words", () => {
    const tt = (k: string) => ({ "saved.unchecked.sales": "sales", "saved.unchecked.permits": "permits", "saved.unchecked.zoning": "zoning", "saved.and": "and" } as Record<string, string>)[k] ?? k;
    expect(uncheckedWords(["sales"], tt)).toBe("sales");
    expect(uncheckedWords(["sales", "permits", "zoning"], tt)).toBe("sales, permits and zoning");
  });

  it("runs at most n checks at once", async () => {
    const run = limiter(2);
    let live = 0, peak = 0;
    const job = () => new Promise<void>((r) => { live++; peak = Math.max(peak, live); setTimeout(() => { live--; r(); }, 5); });
    await Promise.all([1, 2, 3, 4, 5].map(() => run(job)));
    expect(peak).toBe(2);
  });
});

describe("the zoning tag on a saved lot's block", () => {
  it("colors a district or Discovery's group label by its family", () => {
    expect(familyOf("B3-2")).toBe("business");
    expect(familyOf("RS-3")).toBe("residential");
    expect(familyOf("Residential (R)")).toBe("residential");
    expect(familyOf("Commercial (C)")).toBe("business");
    expect(familyOf("Planned development")).toBe("planned");
    expect(familyOf(null)).toBeNull();
  });
});

describe("a saved search's default name", () => {
  it("fits 80 characters, cut between filters", () => {
    const name = "Vacant, Zoning group: Residential (R), Near transit ≤ 0.5 mi, Lot size ≥ 3000 sqft";
    expect(shortName(name)).toBe("Vacant, Zoning group: Residential (R), Near transit ≤ 0.5 mi, Lot size ≥ 3000…");
    expect(shortName(name).length).toBeLessThanOrEqual(80);
    expect(shortName("Vacant")).toBe("Vacant");
  });
});

describe("the Saved page", () => {
  it("signed out: the browser's lots, one quiet sign-in line, no wall", async () => {
    localStorage.setItem(SAVED_KEY, JSON.stringify([{ key: "addr:1 n milwaukee ave", address: "1 N Milwaukee Ave", pin: null, zone: "B3-2", area: null, outline: null, at: 1 }]));
    const { container } = mount();
    expect(screen.getByTestId("saved-signin")).toBeTruthy();
    expect(within(screen.getByTestId("saved-lots")).getByText("1 N Milwaukee Ave")).toBeTruthy();
    expect(api.lots).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByTestId("saved-signin")).getByRole("button", { name: "Sign in" }));
    expect(auth.signIn).toHaveBeenCalled();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("signed in: what changed since the save, what couldn't be checked, and a private note", async () => {
    auth.isAuthenticated = true;
    api.lots.mockResolvedValue({ lots: [wire(1)], max: 200 });
    api.changes.mockResolvedValue({
      since: "2026-11-01", watching_since: "2026-11-01", status: "changes", unchecked: ["violations"],
      changes: [{ kind: "permit", date: "2026-11-05", permit: "P1", permit_type: "RENOVATION/ALTERATION", description: null, cost: 90000 }],
    });
    api.note.mockImplementation(async (id: string, note: string) => ({ ...wire(1), id, note }));
    const { container } = mount();
    const change = await screen.findByTestId("saved-change");
    expect(change.textContent).toContain("Permit: Renovation/alteration, $90,000");
    expect(change.getAttribute("href")).toContain("tab=history");
    expect(screen.getByTestId("saved-unchecked").textContent).toBe("Couldn't check today: violations.");
    fireEvent.click(screen.getByTestId("saved-note"));
    fireEvent.change(screen.getByTestId("saved-note-input"), { target: { value: "Call the broker" } });
    fireEvent.click(screen.getByTestId("saved-note-save"));
    await waitFor(() => expect(screen.getByTestId("saved-note").textContent).toContain("Call the broker"));
    expect(api.note).toHaveBeenCalledWith("L1", "Call the broker");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("a failed check says so and can be retried, never 'nothing new'", async () => {
    auth.isAuthenticated = true;
    api.lots.mockResolvedValue({ lots: [wire(1)], max: 200 });
    api.changes.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ since: "2026-11-01", watching_since: null, status: "none", changes: [], unchecked: [] });
    mount();
    expect(await screen.findByTestId("saved-changes-failed")).toBeTruthy();
    expect(screen.queryByTestId("saved-nothing-new")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("saved-nothing-new")).toBeTruthy();
  });

  it("lists saved searches with their new matches, and Open goes to Discovery with the search", async () => {
    auth.isAuthenticated = true;
    api.lots.mockResolvedValue({ lots: [], max: 200 });
    api.searches.mockResolvedValue({ max: 20, searches: [{ id: "S1", name: "Empty land in Logan", draft: {}, cqs: {}, match_count: 10, saved_at: 1, seen_at: 1 }] });
    api.searchNew.mockResolvedValue({ total: 12, new: 3, gone: 1, exact: true, same_data: false, since: "2026-11-01" });
    mount("/saved?tab=searches");
    expect((await screen.findByTestId("saved-search-news")).textContent).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("saved-search-news").textContent).toBe("3 new lots match · 12 in all"));
    expect(screen.getByTestId("saved-search-open")).toBeTruthy();
  });
});
