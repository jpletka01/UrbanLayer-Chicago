// Sign-in methods in the browser (Phase 9, Item 121): the notice a round trip comes back with, the chooser, and
// Settings' sign-in methods. The server's rules are tested in backend/tests/test_identity.py.
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { parseAuthNotice, stripAuthNotice, takeAuthNotice } from "../../lib/authNotice";

const auth = {
  user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn(async () => {}),
  signInWith: vi.fn(), checkAuth: vi.fn(), chooserOpen: false, closeChooser: vi.fn(),
  providers: [{ id: "google", test: false }, { id: "apple", test: false }, { id: "microsoft", test: true }],
};
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));

const api = vi.hoisted(() => ({
  getSignInIdentities: vi.fn(),
  removeSignInIdentity: vi.fn(),
  startLinkProvider: vi.fn(),
}));
vi.mock("../../lib/api", async (orig) => ({ ...(await orig<typeof import("../../lib/api")>()), ...api }));

import AuthOverlays from "./AuthOverlays";
import SignInMethods from "../settings/SignInMethods";

afterEach(cleanup);

describe("the sign-in notice in the address", () => {
  it("reads errors, the hint and link results, and nothing else", () => {
    expect(parseAuthNotice("?signin_error=expired")).toEqual({ kind: "error", code: "expired" });
    expect(parseAuthNotice("?signin_error=<script>")).toEqual({ kind: "error", code: "failed" });
    expect(parseAuthNotice("?signin_hint=google")).toEqual({ kind: "hint", provider: "google" });
    expect(parseAuthNotice("?signin_hint=evil")).toBeNull();
    expect(parseAuthNotice("?link=taken&provider=apple")).toEqual({ kind: "link", result: "taken", provider: "apple" });
    expect(parseAuthNotice("?link=merged&provider=apple")).toBeNull();
    expect(parseAuthNotice("?q=zoning")).toBeNull();
  });

  it("is removed from the address, keeping the page's own parameters", () => {
    expect(stripAuthNotice("?tab=history&link=linked&provider=apple")).toBe("?tab=history");
    expect(stripAuthNotice("?signin_error=failed")).toBe("");
    window.history.replaceState(null, "", "/settings?link=linked&provider=microsoft#x");
    expect(takeAuthNotice()).toEqual({ kind: "link", result: "linked", provider: "microsoft" });
    expect(`${window.location.pathname}${window.location.search}${window.location.hash}`).toBe("/settings#x");
    expect(takeAuthNotice()).toBeNull();
  });
});

describe("today's UI overlays", () => {
  beforeEach(() => { auth.chooserOpen = false; vi.clearAllMocks(); });

  it("the chooser offers every method in order and goes to the one chosen", () => {
    window.history.replaceState(null, "", "/scorecard");
    auth.chooserOpen = true;
    render(<AuthOverlays />);
    const dialog = screen.getByRole("dialog");
    const buttons = within(dialog).getAllByRole("button", { name: /^Continue with / });
    expect(buttons.map((b) => b.getAttribute("data-provider"))).toEqual(["google", "apple", "microsoft"]);
    expect(buttons[2].textContent).toContain("local test account");
    fireEvent.click(buttons[1]);
    expect(auth.signInWith).toHaveBeenCalledWith("apple");
  });

  it("says what a link did, and the hint offers the other method", async () => {
    window.history.replaceState(null, "", "/settings?link=taken&provider=apple");
    const { unmount } = render(<AuthOverlays />);
    expect(screen.getByTestId("auth-notice").textContent).toContain(
      "That Apple account signs in to a different UrbanLayer account, so it wasn't added. Nothing was merged.");
    unmount();
    window.history.replaceState(null, "", "/?signin_hint=google");
    render(<AuthOverlays />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with Google instead" }));
    await waitFor(() => expect(auth.signInWith).toHaveBeenCalledWith("google"));
    expect(auth.signOut).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByTestId("auth-notice")).toBeNull();
  });
});

describe("Settings: sign-in methods", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists the methods, hides Apple's relay address, and can't remove the only one", async () => {
    api.getSignInIdentities.mockResolvedValue({
      identities: [{ provider: "apple", email: null, private_email: true, added_at: Date.UTC(2026, 10, 1), last_used_at: 0 }],
      available: auth.providers,
    });
    render(<SignInMethods />);
    const list = await screen.findByTestId("signin-methods");
    expect(list.textContent).toContain("Email hidden by Apple");
    expect(within(list).queryByRole("button", { name: "Remove" })).toBeNull();
    expect(list.textContent).toContain("Only way in");
    // Add offers the methods not yet on the account.
    const adds = Array.from(list.querySelectorAll("[data-add-provider]")).map((b) => b.getAttribute("data-add-provider"));
    expect(adds).toEqual(["google", "microsoft"]);
  });

  it("Add goes to the provider through the link endpoint, back to this page", async () => {
    api.getSignInIdentities.mockResolvedValue({
      identities: [{ provider: "google", email: "p•••@example.com", private_email: false, added_at: 0, last_used_at: 0 }],
      available: auth.providers,
    });
    api.startLinkProvider.mockResolvedValue("https://login.microsoftonline.com/x");
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, pathname: "/settings", assign });
    render(<SignInMethods />);
    fireEvent.click(await screen.findByRole("button", { name: /Add Microsoft/ }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://login.microsoftonline.com/x"));
    expect(api.startLinkProvider).toHaveBeenCalledWith("microsoft", "/settings");
    vi.unstubAllGlobals();
  });

  it("Remove asks first, then reloads the list", async () => {
    api.getSignInIdentities.mockResolvedValue({
      identities: [
        { provider: "google", email: "p•••@example.com", private_email: false, added_at: 0, last_used_at: 0 },
        { provider: "microsoft", email: null, private_email: false, added_at: 0, last_used_at: 0 },
      ],
      available: auth.providers,
    });
    api.removeSignInIdentity.mockResolvedValue("removed");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<SignInMethods />);
    const removes = await screen.findAllByRole("button", { name: "Remove" });
    fireEvent.click(removes[1]);
    await waitFor(() => expect(api.removeSignInIdentity).toHaveBeenCalledWith("microsoft"));
    expect(api.getSignInIdentities).toHaveBeenCalledTimes(2);
  });
});
