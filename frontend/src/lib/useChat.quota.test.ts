// Quotas (decision Item 120): a refused question is worded by plan, stops further sends, and the remaining count
// comes from the server's usage. No model call.
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import i18n from "../lib/i18n";

const m = vi.hoisted(() => ({ refuse: null as unknown, usage: null as unknown, sent: 0 }));

vi.mock("./api", async () => {
  class ChatStreamError extends Error {
    status: number; detail: string | null; quota: unknown; paused: unknown;
    constructor(status: number, _t: string, detail: string | null, structured: unknown = null) {
      super("x"); this.status = status; this.detail = detail;
      const d = structured as { error?: string } | null;
      this.quota = d?.error === "quota" ? d : null; this.paused = d?.error === "paused" ? d : null;
    }
  }
  return {
    ChatStreamError,
    getUsage: async () => m.usage,
    chatStream: () => {
      m.sent += 1;
      return (async function* () {
        if (m.refuse) throw new ChatStreamError(429, "Too Many", null, m.refuse);
        yield { type: "done" };
      })();
    },
  };
});

import { quotaText, useChat } from "./useChat";

const en = (k: string, o?: Record<string, unknown>) => i18n.t(k, { ...o, lng: "en" });

describe("quotaText", () => {
  it("words each plan in English and Spanish (usted)", () => {
    expect(quotaText({ error: "quota", plan: "anonymous", limit: 3, used: 3, resets_on: null, free_limit: 50 }, en))
      .toBe("You've used your 3 free questions. Sign in to keep asking: 50 a month, free.");
    expect(quotaText({ error: "quota", plan: "free", limit: 50, used: 50, resets_on: "2026-12-01", pro_limit: 200 }, en))
      .toBe("You've used this month's 50 questions. They come back on December 1. Pro gives you 200 a month.");
    expect(quotaText({ error: "quota", plan: "pro", limit: 200, used: 200, resets_on: "2027-01-01" }, en))
      .toBe("You've used this month's 200 questions. They come back on January 1.");
    expect(quotaText({ error: "quota", plan: "anonymous", limit: 3, used: 1, resets_on: null, network: true }, en))
      .toContain("this network");
    const es = (k: string, o?: Record<string, unknown>) => i18n.t(k, { ...o, lng: "es" });
    expect(quotaText({ error: "quota", plan: "free", limit: 50, used: 50, resets_on: "2026-12-01", pro_limit: 200 }, es, "es"))
      .toBe("Ya usó las 50 preguntas de este mes. Vuelven el 1 de diciembre. Pro le da 200 al mes.");
  });
});

describe("useChat and the allowance", () => {
  it("a refusal stops further sends and says why", async () => {
    m.refuse = { error: "quota", plan: "free", limit: 50, used: 50, resets_on: "2026-12-01", pro_limit: 200 };
    m.sent = 0;
    const { result } = renderHook(() => useChat());
    await act(async () => { await result.current.sendMessage("Can I build a 3-flat?"); });
    await waitFor(() => expect(result.current.atQuota).toBe(true));
    expect(result.current.quotaMessage).toContain("They come back on December 1");
    await act(async () => { await result.current.sendMessage("And a 4-flat?"); });
    expect(m.sent).toBe(1); // the second question never left the browser
    m.refuse = null;
  });

  it("reads the remaining count from the server's usage", async () => {
    m.usage = { plan: "anonymous", used: 1, limit: 3, resets_on: null, free_limit: 50 };
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.questionsLeft).toBe(2));
    expect(result.current.usagePlan).toBe("anonymous");
    expect(result.current.atQuota).toBe(false);
    m.usage = null;
  });
});
