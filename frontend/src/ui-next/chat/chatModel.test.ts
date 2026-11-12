import { describe, expect, it } from "vitest";
import type { MapData, Message } from "../../lib/types";
import { chatTitle, lotHref, previewsFor } from "./chatModel";

const MAP: MapData = {
  crimes: [{ latitude: 41.91, longitude: -87.68, primary_type: "THEFT", date: "2026-10-01", description: "", arrest: false }],
  requests_311: [{ latitude: 41.92, longitude: -87.67, sr_type: "Pothole", status: "Open", created_date: "2026-10-02", owner_department: "CDOT" }],
  building_permits: [{ latitude: Number.NaN, longitude: -87.66, permit_type: "NEW", work_description: "", estimated_cost: 0, issue_date: "2026-10-03" }],
  queried_address: { latitude: 41.9, longitude: -87.69, label: "1601 N Milwaukee Ave" },
};

const answer = (over: Partial<Message> = {}): Message => ({
  role: "assistant",
  content: "Probably yes.",
  context: { resolved_address: "2611 N Sawyer Ave", property: { pin14: "13254020120000" }, code_chunks: [{}, {}] } as never,
  mapData: MAP,
  ...over,
});

describe("answer previews", () => {
  it("offers the lot, the map and the sources (code and records) in that order", () => {
    expect(previewsFor(answer()).map((p) => p.kind)).toEqual(["lot", "map", "sources"]);
  });

  it("links the lot by PIN when the answer resolved one, else by address", () => {
    expect(lotHref("2611 N Sawyer Ave", "13254020120000")).toBe("/scorecard?pin=13254020120000&address=2611+N+Sawyer+Ave");
    expect(lotHref("2611 N Sawyer Ave", null)).toBe("/scorecard?address=2611+N+Sawyer+Ave");
  });

  it("offers nothing for a question, a streaming answer or an answer with no data", () => {
    expect(previewsFor({ role: "user", content: "Hi" })).toEqual([]);
    expect(previewsFor(answer({ content: "" }))).toEqual([]);
    expect(previewsFor({ role: "assistant", content: "RT-4 allows 4 units." })).toEqual([]);
  });
});

describe("the title", () => {
  it("is the first question, shortened like the stored title", () => {
    expect(chatTitle([])).toBeNull();
    expect(chatTitle([{ role: "user", content: "x".repeat(60) }])).toBe(`${"x".repeat(47)}...`);
  });
});
