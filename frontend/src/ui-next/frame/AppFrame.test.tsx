// The frame: the side panel lists only destinations the readiness registry allows, collapses to
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
  it("shows Home, Search, Discovery, Saved and Chat, with the current page marked", async () => {
    const { container } = mount();
    const panel = screen.getAllByRole("navigation", { name: "Main menu" })[0];
    const links = within(panel).getAllByRole("link").map((a) => a.textContent);
    expect(links).toEqual(["UrbanLayer", "Home", "Search", "Discovery", "Saved", "Chat", "About UrbanLayer"]);
    expect(within(panel).getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
    expect(container.querySelector(".ui-next")).not.toBeNull();
    expect(screen.getByRole("navigation", { name: "You are here" }).textContent).toContain("1601 N Milwaukee Ave");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("links Chat straight to the chat page: past chats live in its own list, not here (owner, 2026-11-12)", () => {
    mount();
    const panel = screen.getAllByRole("navigation", { name: "Main menu" })[0];
    expect(within(panel).getByRole("link", { name: "Chat" }).getAttribute("href")).toBe("/chat");
    expect(within(panel).queryByTestId("chat-folder")).toBeNull();
    expect(within(panel).queryByRole("button", { name: "Chat" })).toBeNull();
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
