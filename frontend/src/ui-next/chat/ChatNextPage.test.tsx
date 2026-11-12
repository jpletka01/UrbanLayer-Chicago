// The full chat page with a mocked session (no production model calls, Items 75 and 83): the nearly empty first
// screen with its typed example, answers with their previews, a preview filling the space above the box and
// minimize returning, a citation opening its source, an honest error with Try again, the limit line, and the
// sign-in card at the free limit.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ChatNextPage from "./ChatNextPage";
import { axeViolations } from "../test/axe";
import type { Message } from "../../lib/types";

vi.mock("../../contexts/AuthContext", () => ({
  useAuthContext: () => ({ user: null, isAuthenticated: false, authRequired: true, signIn: vi.fn(), signOut: vi.fn() }),
}));
vi.mock("../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({ theme: "system", resolvedTheme: "light", setTheme: vi.fn() }),
}));
vi.mock("./ChatMap", () => ({ ChatMap: () => <div data-testid="chat-map" /> }));
vi.mock("../../components/sidebar/DataView", () => ({ DataView: () => <div data-testid="data-cards" /> }));
vi.mock("../../components/MessageBubble", () => ({
  MessageBubble: ({ message, footer, onCitationClick, onDataClick }: { message: Message; footer?: React.ReactNode; onCitationClick?: (n: number) => void; onDataClick?: (s: string) => void }) => (
    <div>
      <p>{message.content}</p>
      {message.role === "assistant" && <button type="button" onClick={() => onCitationClick?.(2)}>[2]</button>}
      {message.role === "assistant" && <button type="button" onClick={() => onDataClick?.("crime")}>[data:crime]</button>}
      {footer}
    </div>
  ),
}));

const ANSWER: Message = {
  role: "assistant",
  content: "Probably yes.",
  context: {
    resolved_address: "2611 N Sawyer Ave",
    property: { pin14: "13254020120000" },
    code_chunks: [
      { text: "Coach houses are allowed…", section: "17-9-0201", section_title: "Coach houses", source_document: "", subsection: null, score: 1, cross_references: [] },
      { text: "Rear yard…", section: "17-2-0309", section_title: "Rear setbacks", source_document: "", subsection: null, score: 1, cross_references: [] },
    ],
  } as never,
  mapData: {
    crimes: [{ latitude: 41.92, longitude: -87.7, primary_type: "THEFT", date: "2026-10-01", description: "", arrest: false }],
    requests_311: [], building_permits: [], queried_address: { latitude: 41.92, longitude: -87.71, label: "2611 N Sawyer Ave" },
  },
};

let session: Record<string, unknown>;
const base = () => ({
  messages: [] as Message[], streaming: false, context: null, activities: [], errorMsg: null, canRetry: false, retry: vi.fn(),
  rateLimited: false, atMessageLimit: false, messagesRemaining: 10, conversationId: null, loadingConversation: false,
  loadError: null, isSharedView: false, sinceThen: {}, canPersist: false, groundedContext: null, pendingAttachments: [],
  showAuthModal: false, sendMessage: vi.fn(), sendPropertyStarter: vi.fn(), attach: vi.fn(), removeAttachment: vi.fn(),
  newChat: vi.fn(), dismissAuth: vi.fn(),
});
vi.mock("../../lib/useChatSession", () => ({ useChatSession: () => session }));

const mount = () => render(<MemoryRouter initialEntries={["/chat"]}><ChatNextPage /></MemoryRouter>);

beforeEach(() => { localStorage.clear(); session = base(); });
afterEach(cleanup);

describe("the full chat page", () => {
  it("opens nearly empty: a heading, the box with an example, and sends with Enter", async () => {
    const { container } = mount();
    expect(screen.getByRole("heading", { name: "What do you want to know?" })).toBeTruthy();
    expect(screen.getByTestId("chat-example")).toBeTruthy();
    const box = screen.getByTestId("chat-box");
    fireEvent.change(box, { target: { value: "  How many units does RT-4 allow?  " } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(session.sendMessage).toHaveBeenCalledWith("How many units does RT-4 allow?");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("offers the lot, the map and the sources under an answer; the lot opens its Profile in a new tab", async () => {
    session.messages = [{ role: "user", content: "Could I add a coach house at 2611 N Sawyer?" }, ANSWER];
    const { container } = mount();
    const row = screen.getByTestId("chat-previews");
    expect(within(row).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/scorecard?pin=13254020120000&address=2611+N+Sawyer+Ave"]);
    expect(screen.getByTestId("preview-lot").getAttribute("target")).toBe("_blank");
    expect(screen.getByTestId("preview-map").textContent).toContain("the lot's zoning");
    expect(screen.getByTestId("preview-sources").textContent).toContain("2");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("opens the evidence beside the answer: the answer stays, the panel shows the chosen tab", async () => {
    session.messages = [{ role: "user", content: "Q" }, ANSWER];
    const { container } = mount();
    fireEvent.click(screen.getByTestId("preview-map"));
    const panel = screen.getByTestId("chat-evidence");
    expect(within(panel).getByTestId("chat-map")).toBeTruthy();
    // Read side by side: the answer and the box stay on screen.
    expect(screen.getByText("Probably yes.")).toBeTruthy();
    expect(screen.getByTestId("chat-box")).toBeTruthy();
    // The panel's tabs are only those this answer has; the chip reads as selected.
    expect(within(panel).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Sources", "Data", "Map"]);
    expect(screen.getByTestId("preview-map").getAttribute("aria-pressed")).toBe("true");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("grows the same map to full screen, and back (no second map)", () => {
    session.messages = [{ role: "user", content: "Q" }, ANSWER];
    mount();
    fireEvent.click(screen.getByTestId("preview-map"));
    fireEvent.click(screen.getByTestId("evidence-fullscreen"));
    expect(screen.getByTestId("chat-fullmap")).toBeTruthy();
    expect(screen.getAllByTestId("chat-map")).toHaveLength(1);
    fireEvent.click(screen.getByTestId("chat-minimize"));
    expect(screen.queryByTestId("chat-fullmap")).toBeNull();
    expect(screen.getByTestId("evidence-tab-map").getAttribute("aria-selected")).toBe("true");
  });

  it("opens a citation's own source in the panel, one open at a time", () => {
    session.messages = [{ role: "user", content: "Q" }, ANSWER];
    mount();
    fireEvent.click(screen.getByText("[2]"));
    const list = within(screen.getByTestId("chat-evidence")).getByTestId("chat-sources");
    const open = within(list).getAllByRole("button").filter((b) => b.getAttribute("aria-expanded") === "true");
    expect(open).toHaveLength(1);
    expect(open[0].textContent).toContain("17-2-0309");
  });

  it("opens the answer's records from a data citation and from the Data preview", () => {
    session.messages = [{ role: "user", content: "Q" }, ANSWER];
    mount();
    fireEvent.click(screen.getByText("[data:crime]"));
    expect(within(screen.getByTestId("chat-evidence")).getByTestId("data-cards")).toBeTruthy();
    fireEvent.click(screen.getByTestId("evidence-tab-sources"));
    expect(within(screen.getByTestId("chat-evidence")).queryByTestId("data-cards")).toBeNull();
    fireEvent.click(screen.getByTestId("preview-data"));
    expect(within(screen.getByTestId("chat-evidence")).getByTestId("data-cards")).toBeTruthy();
  });

  it("names a failed step and offers Try again", () => {
    session.messages = [{ role: "user", content: "Q" }];
    session.errorMsg = "We couldn't check the zoning just now.";
    session.canRetry = true;
    mount();
    fireEvent.click(screen.getByTestId("chat-retry"));
    expect(session.retry).toHaveBeenCalled();
  });

  it("says when the conversation is at its limit and offers a new chat", () => {
    session.messages = [{ role: "user", content: "Q" }, ANSWER];
    session.atMessageLimit = true;
    session.messagesRemaining = 0;
    mount();
    expect(screen.getByTestId("chat-limit").textContent).toContain("question limit");
    expect((screen.getByTestId("chat-box") as HTMLTextAreaElement).disabled).toBe(true);
  });

  it("frosts the conversation behind a sign-in card when an anonymous visitor runs out", async () => {
    session.messages = [{ role: "user", content: "Q" }];
    session.rateLimited = true;
    const { container } = mount();
    const card = screen.getByTestId("chat-signin");
    expect(within(card).getByRole("dialog", { name: "Sign in to keep going" })).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Close" }));
    expect(session.dismissAuth).toHaveBeenCalled();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("grounded on a lot: the heading names it, starters replace the example, and the box says what it's about", () => {
    session.groundedContext = { pin: "13254020120000", address: "2611 N Sawyer Ave" };
    mount();
    expect(screen.getByRole("heading", { name: "What do you want to know about 2611 N Sawyer Ave?" })).toBeTruthy();
    expect(screen.queryByTestId("chat-example")).toBeNull();
    expect(screen.getByTestId("chat-about").textContent).toContain("2611 N Sawyer Ave");
  });
});
