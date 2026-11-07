// The frame: the side panel lists only destinations the readiness registry allows (Saved hidden), collapses to
// icons with accessible names, opens as a sheet on a phone, and the top bar carries the breadcrumb.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppFrame } from "./AppFrame";
import { axeViolations } from "../test/axe";

vi.mock("../../contexts/AuthContext", () => ({
  useAuthContext: () => ({ user: null, isAuthenticated: false, authRequired: true, signIn: vi.fn(), signOut: vi.fn() }),
}));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: vi.fn() }),
}));

function mount() {
  return render(
    <MemoryRouter initialEntries={["/scorecard"]}>
      <AppFrame crumbs={["Profile", "1601 N Milwaukee Ave"]}><p>content</p></AppFrame>
    </MemoryRouter>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe("AppFrame", () => {
  it("shows Search, Discovery and Chat, never Saved, with the current page marked", async () => {
    const { container } = mount();
    const panel = screen.getAllByRole("navigation", { name: "Main menu" })[0];
    const links = within(panel).getAllByRole("link").map((a) => a.textContent);
    expect(links).toEqual(["UrbanLayer", "Search", "Discovery"]);
    expect(within(panel).getByRole("button", { name: "Chat" }).getAttribute("aria-expanded")).toBe("false");
    expect(within(panel).queryByText("Saved")).toBeNull();
    expect(within(panel).getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
    expect(container.querySelector(".ui-next")).not.toBeNull();
    expect(screen.getByRole("navigation", { name: "You are here" }).textContent).toContain("1601 N Milwaukee Ave");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("opens Chat like a folder: New chat first, then a sign-in line for anonymous visitors", () => {
    mount();
    const panel = screen.getAllByRole("navigation", { name: "Main menu" })[0];
    fireEvent.click(within(panel).getByRole("button", { name: "Chat" }));
    const folder = within(panel).getByTestId("chat-folder");
    const rows = within(folder).getAllByRole("listitem").map((li) => li.textContent);
    expect(rows).toEqual(["New chat", "Sign in to see past chats"]);
    expect(within(folder).getByRole("link", { name: "New chat" }).getAttribute("href")).toBe("/?ask=1");
  });

  it("collapses to icons that keep their names, and remembers it", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Collapse menu" }));
    const panel = screen.getAllByRole("navigation", { name: "Main menu" })[0];
    expect(within(panel).getByRole("link", { name: "Discovery" }).textContent).toBe("");
    expect(localStorage.getItem("urbanlayer-next-panel")).toBe("collapsed");
  });

  it("opens the same panel as a sheet from the phone menu button", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByRole("link", { name: "Discovery" })).toBeTruthy();
    fireEvent.click(within(sheet).getByRole("button", { name: "Close menu" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
