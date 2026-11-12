// A chat turn is never lost to a strict server check (owner's review, 2026-11-12): a 422 on the full save stores the
// turn again with its text and map only.
import { beforeEach, describe, expect, it, vi } from "vitest";

const saveMessages = vi.fn();
vi.mock("./api", () => ({
  saveMessages: (...a: unknown[]) => saveMessages(...a),
  clearAllConversations: vi.fn(), deleteConversationAPI: vi.fn(), importConversations: vi.fn(), listConversations: vi.fn(),
}));
import { appendMessages } from "./history";

const turn = [
  { role: "user" as const, content: "Tell me about 44 W Wrightwood Ave" },
  { role: "assistant" as const, content: "It's RM-5.", context: { odd: true } as never, plan: { intent: "x" } as never, mapData: { crimes: [] } as never, mapFetchedAt: 5 },
];

beforeEach(() => saveMessages.mockReset());

describe("appendMessages", () => {
  it("stores the full turn when the server accepts it", async () => {
    saveMessages.mockResolvedValue(undefined);
    await appendMessages("c1", turn);
    expect(saveMessages).toHaveBeenCalledTimes(1);
    expect(saveMessages.mock.calls[0][1][1]).toHaveProperty("context");
  });

  it("on a 422, stores the turn again with its text and map only", async () => {
    saveMessages.mockRejectedValueOnce(new Error("Failed to save messages: 422")).mockResolvedValueOnce(undefined);
    await appendMessages("c1", turn);
    expect(saveMessages).toHaveBeenCalledTimes(2);
    expect(saveMessages.mock.calls[1][1]).toEqual([
      { role: "user", content: "Tell me about 44 W Wrightwood Ave" },
      { role: "assistant", content: "It's RM-5.", map_data: { crimes: [] }, map_fetched_at: 5 },
    ]);
  });
});
