// "Continue in the full analyst" opens the full chat in a NEW tab and leaves the Profile where it was
// (Jack, 2026-11-06); the transcript reaches the new tab through a one-time handoff id.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MiniChatDock } from "./MiniChatDock";
import { takeHandoff } from "../lib/openInNewTab";
import type { ScorecardResponse } from "../lib/api";

vi.mock("../lib/useChat", () => ({
  useChat: () => ({
    messages: [
      { role: "user", content: "Can I build a 3-flat? — 642 W Belden Ave" },
      { role: "assistant", content: "RS-3 allows ..." },
    ],
    streaming: false, context: null, errorMsg: null, atQuota: false, quotaMessage: null, activities: [],
    sendMessage: vi.fn(), setGrounding: vi.fn(),
  }),
}));
vi.mock("../lib/scorecardContext", () => ({
  buildScorecardContext: () => ({ pin: "14331030110000", address: "642 W Belden Ave" }),
  propertyStarterKeys: () => [],
}));
vi.mock("../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("./MessageBubble", () => ({ MessageBubble: ({ content }: { content: string }) => <p>{content}</p> }));

const data = { address: "642 W Belden Ave" } as unknown as ScorecardResponse;

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function openDock() {
  render(<MiniChatDock data={data} signal={{ question: null, id: 1 }} />);
  return screen.getByRole("button", { name: /Continue in the full analyst/ });
}

describe("dock escalate", () => {
  it("opens /?pin=…&handoff=… in a new tab, with the transcript behind the id", () => {
    const open = vi.spyOn(window, "open").mockReturnValue({ opener: null } as Window);
    fireEvent.click(openDock());
    expect(open).toHaveBeenCalledTimes(1);
    const [url, target] = open.mock.calls[0];
    expect(target).toBe("_blank");
    const params = new URL(String(url), "https://x.test").searchParams;
    expect(params.get("pin")).toBe("14331030110000");
    expect(takeHandoff(params.get("handoff")!)).toEqual([
      { role: "user", content: "Can I build a 3-flat? — 642 W Belden Ave" },
      { role: "assistant", content: "RS-3 allows ..." },
    ]);
    expect(screen.queryByTestId("dock-tab-blocked")).toBeNull();
  });

  it("a blocked tab keeps the page, says so, and leaves no handoff behind", () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    fireEvent.click(openDock());
    expect(screen.getByTestId("dock-tab-blocked").textContent).toContain("blocked the new tab");
    expect(Object.keys(localStorage).filter((k) => k.startsWith("ul_dock_handoff:"))).toEqual([]);
  });
});
