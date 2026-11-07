// A failed chat turn names its step (or says chat is unavailable) and keeps the question for "Try again"
// (decision Item 72; tester report 2026-11-06).
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatChunk } from "./types";

const m = vi.hoisted(() => ({ script: [] as ChatChunk[][], calls: [] as Array<{ text: string; history: unknown }> }));

vi.mock("./api", () => ({
  ChatStreamError: class ChatStreamError extends Error {
    status = 500;
    detail: string | null = null;
  },
  chatStream: (text: string, history: unknown) => {
    m.calls.push({ text, history });
    const chunks = m.script.shift() ?? [];
    return (async function* () {
      for (const c of chunks) yield c;
    })();
  },
}));

import { turnErrorText, useChat } from "./useChat";

const t = (k: string) => k;

beforeEach(() => {
  m.script = [];
  m.calls = [];
});

describe("turnErrorText", () => {
  it("words the failed step, an outage, the message limit, and leaves an older backend's text alone", () => {
    expect(turnErrorText({ error: "x", error_step: "route", error_kind: "step" }, t)).toBe("chat:turnError.step.route");
    expect(turnErrorText({ error: "x", error_step: "route", error_kind: "unavailable" }, t)).toBe("chat:turnError.unavailable");
    expect(turnErrorText({ error: "MESSAGE_LIMIT_REACHED" }, t)).toBe("common:messageLimit");
    expect(turnErrorText({ error: "Something went wrong" }, t)).toBe("Something went wrong");
  });
});

describe("useChat retry", () => {
  it("keeps the failed question and resends it once, without duplicating the bubble", async () => {
    m.script.push([
      { type: "error", error: "x", error_step: "route", error_kind: "unavailable" },
      { type: "done" },
    ]);
    const { result } = renderHook(() => useChat());
    await act(async () => { await result.current.sendMessage("What can I build at 642 W Belden?"); });

    expect(result.current.errorMsg).toBe("Chat is temporarily unavailable. Your question is kept: try again in a little while.");
    expect(result.current.canRetry).toBe(true);
    expect(result.current.messages.filter((x) => x.role === "user").map((x) => x.content)).toEqual([
      "What can I build at 642 W Belden?",
    ]);

    m.script.push([{ type: "token", text: "RS-3 allows two units." }, { type: "done" }]);
    await act(async () => { result.current.retry(); });
    await waitFor(() => expect(result.current.streaming).toBe(false));

    expect(m.calls.map((c) => c.text)).toEqual(["What can I build at 642 W Belden?", "What can I build at 642 W Belden?"]);
    expect(m.calls[1].history).toEqual([]); // the failed turn is not sent back as history
    expect(result.current.messages.map((x) => [x.role, x.content])).toEqual([
      ["user", "What can I build at 642 W Belden?"],
      ["assistant", "RS-3 allows two units."],
    ]);
    expect(result.current.errorMsg).toBeNull();
    expect(result.current.canRetry).toBe(false);
  });

  it("a half-written answer that failed is replaced on retry", async () => {
    m.script.push([
      { type: "token", text: "RS-3 all" },
      { type: "error", error: "x", error_step: "answer", error_kind: "step" },
      { type: "done" },
    ]);
    const { result } = renderHook(() => useChat());
    await act(async () => { await result.current.sendMessage("q"); });
    expect(result.current.errorMsg).toBe("The answer failed while writing the answer. Your question is kept: try again.");

    m.script.push([{ type: "token", text: "full answer" }, { type: "done" }]);
    await act(async () => { result.current.retry(); });
    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(result.current.messages.map((x) => x.content)).toEqual(["q", "full answer"]);
  });

  it("a healthy turn offers no retry", async () => {
    m.script.push([{ type: "token", text: "ok" }, { type: "done" }]);
    const { result } = renderHook(() => useChat());
    await act(async () => { await result.current.sendMessage("q"); });
    expect(result.current.canRetry).toBe(false);
  });
});
