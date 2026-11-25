// The Ask drawer on the existing chat path, with mocks only (no production model calls, decision Item 75):
// questions carry the address and the parcel grounding, the conversation outlives closing the drawer, focus
// goes back to the Ask button, Escape closes, and "Open in full chat" opens a new tab.
import { useRef, useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AskDrawer } from "./AskDrawer";
import { useParcelChat } from "../../lib/useParcelChat";
import { takeHandoff } from "../../lib/openInNewTab";
import { axeViolations } from "../test/axe";
import type { ScorecardResponse } from "../../lib/api";

const sendMessage = vi.fn();
const messages: Array<{ role: string; content: string }> = [];
vi.mock("../../lib/useChat", () => ({
  useChat: () => ({
    messages, streaming: false, context: null, errorMsg: null, canRetry: false, retry: vi.fn(),
    atQuota: false, quotaMessage: null, activities: [], sendMessage, setGrounding: vi.fn(),
  }),
}));
vi.mock("../../lib/scorecardContext", () => ({
  buildScorecardContext: () => ({ pin: "14313250010000", address: "1601 N Milwaukee Ave" }),
  propertyStarterKeys: () => ["build", "zoning"],
}));
vi.mock("../../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("../../components/MessageBubble", () => ({ MessageBubble: ({ message }: { message: { content: string } }) => <p>{message.content}</p> }));

const data = { address: "1601 N Milwaukee Ave" } as unknown as ScorecardResponse;

function Harness() {
  const chat = useParcelChat(data, "en");
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("Overview");
  const ref = useRef<HTMLButtonElement | null>(null);
  return (
    <div className="ui-next">
      <button ref={ref} type="button" onClick={() => setOpen(true)}>Ask</button>
      <button type="button" onClick={() => setTab("Build")}>Build tab</button>
      {open && <AskDrawer chat={chat} onClose={() => setOpen(false)} returnFocusRef={ref} tabLabel={tab} />}
    </div>
  );
}

beforeEach(() => { localStorage.clear(); sendMessage.mockClear(); messages.length = 0; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Ask drawer", () => {
  it("opens with the question box focused and sends the question with the address and the pin", async () => {
    const { container } = render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    const box = screen.getByLabelText("Your question");
    expect(document.activeElement).toBe(box);
    fireEvent.change(box, { target: { value: "Could I add a coach house?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(sendMessage).toHaveBeenCalledWith(
      "Could I add a coach house? — 1601 N Milwaukee Ave",
      undefined,
      { parcelPin: "14313250010000", scorecardContext: { pin: "14313250010000", address: "1601 N Milwaukee Ave" } },
    );
    expect(await axeViolations(container)).toEqual([]);
  });

  it("knows the tab, keeps the conversation when closed and reopened, and returns focus to Ask", () => {
    messages.push({ role: "user", content: "Q1" }, { role: "assistant", content: "A1" });
    render(<Harness />);
    const ask = screen.getByRole("button", { name: "Ask" });
    fireEvent.click(ask);
    expect(screen.getByText("Knows this lot and the Overview tab")).toBeTruthy();
    fireEvent.keyDown(screen.getByTestId("ask-drawer"), { key: "Escape" });
    expect(screen.queryByTestId("ask-drawer")).toBeNull();
    expect(document.activeElement).toBe(ask);
    fireEvent.click(screen.getByRole("button", { name: "Build tab" }));
    fireEvent.click(ask);
    expect(screen.getByText("A1")).toBeTruthy();
    expect(screen.getByText("Knows this lot and the Build tab")).toBeTruthy();
  });

  it("opens the full chat in a new tab with the transcript, never in place", () => {
    messages.push({ role: "user", content: "Q1" }, { role: "assistant", content: "A1" });
    const open = vi.spyOn(window, "open").mockReturnValue({ opener: null } as Window);
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    fireEvent.click(screen.getByRole("button", { name: /Open in full chat/ }));
    const [url, target] = open.mock.calls[0];
    expect(target).toBe("_blank");
    const params = new URL(String(url), "https://x.test").searchParams;
    expect(params.get("pin")).toBe("14313250010000");
    expect(takeHandoff(params.get("handoff")!)).toEqual([{ role: "user", content: "Q1" }, { role: "assistant", content: "A1" }]);
  });

  it("a starter sends at once", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    const starters = screen.getAllByRole("button").filter((b) => b.className.includes("bg-nx-block"));
    expect(starters).toHaveLength(2);
    fireEvent.click(starters[0]);
    expect(sendMessage).toHaveBeenCalledTimes(1);
  });
});
