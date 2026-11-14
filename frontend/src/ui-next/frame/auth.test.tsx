// Sign-in in the browser (Phase 9, Item 121): the notice a round trip comes back with, and the chooser. Settings'
// sign-in methods are tested with Settings. The server's rules are tested in backend/tests/test_identity.py.
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { parseAuthNotice, stripAuthNotice } from "../../lib/authNotice";

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
  });
});

function Where() {
  const l = useLocation();
  return <output data-testid="where">{`${l.pathname}${l.search}${l.hash}`}</output>;
}

function at(url: string) {
  return render(<MemoryRouter initialEntries={[url]}><AuthOverlays /><Where /></MemoryRouter>);
}

describe("the overlays", () => {
  beforeEach(() => { auth.chooserOpen = false; vi.clearAllMocks(); });

  it("the chooser offers every method in order and goes to the one chosen", () => {
    auth.chooserOpen = true;
    at("/scorecard");
    const dialog = screen.getByRole("dialog");
    const buttons = within(dialog).getAllByRole("button", { name: /^Continue with / });
    expect(buttons.map((b) => b.getAttribute("data-provider"))).toEqual(["google", "apple", "microsoft"]);
    expect(screen.getByTestId("signin-test-note").textContent).toContain("a test account");
    fireEvent.click(buttons[1]);
    expect(auth.signInWith).toHaveBeenCalledWith("apple");
  });

  it("says what a link did, and the hint offers the other method", async () => {
    const { unmount } = at("/settings?tab=x&link=taken&provider=apple#top");
    expect(screen.getByTestId("auth-notice").textContent).toContain(
      "That Apple account signs in to a different UrbanLayer account, so it wasn't added. Nothing was merged.");
    // The address keeps the page's own parameters and loses the notice's.
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/settings?tab=x#top"));
    unmount();
    at("/?signin_hint=google");
    fireEvent.click(screen.getByRole("button", { name: "Sign in with Google instead" }));
    await waitFor(() => expect(auth.signInWith).toHaveBeenCalledWith("google"));
    expect(auth.signOut).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByTestId("auth-notice")).toBeNull();
  });
});
