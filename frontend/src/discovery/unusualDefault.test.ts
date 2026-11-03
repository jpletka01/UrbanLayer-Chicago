import { describe, expect, it } from "vitest";
import { carriedFilters, appliedFilters, diffDraft, HIDE_UNUSUAL } from "./draftModel";
import { summarize } from "./summary";
import type { CQS, Registry } from "./types";

// The server's default `hide_unusual` filter (decision Item 60) is not a filter the user chose.
const cqs: CQS = {
  filters: {
    [HIDE_UNUSUAL]: { predicate: { kind: "flag", value: false }, source: "default" },
    vacancy: { predicate: { kind: "flag", value: true }, source: "user" },
  },
  sort: { key: "lot_size", dir: "desc" }, scope: { mode: "all" }, meta: {},
};
const registry = {
  version: "v", topics: [], sortKeys: [], defaultSort: { key: "lot_size", dir: "desc" }, broadMinFilters: 2,
  coverage: { mode: "all", liveAreas: [] }, populatedFields: [],
  filters: [
    { id: "vacancy", category: "property_use", kind: "flag", field: "is_vacant", unknownPolicy: "exclude", label: "Vacant" },
    { id: HIDE_UNUSUAL, category: "property_use", kind: "flag", field: "unusual", unknownPolicy: "include", label: "Hide unusual parcels" },
  ],
} as unknown as Registry;

describe("the default unusual-parcels filter", () => {
  it("is never a chip, a carried filter or a pending change", () => {
    expect(carriedFilters(cqs)).toEqual({});
    expect(Object.keys(appliedFilters(cqs))).toEqual(["vacancy"]);
    const draft = { panelState: { vacancy: { kind: "flag" as const, value: true } }, text: "", sort: cqs.sort, topicId: null };
    const diff = diffDraft(draft, cqs, "");
    expect(diff.chips.map((c) => c.id)).toEqual(["vacancy"]);
    expect(diff.pendingCount).toBe(0);
    // opting in is one pending change until it is evaluated
    expect(diffDraft({ ...draft, includeUnusual: true }, cqs, "").pendingCount).toBe(1);
  });

  it("is said by the hidden count, not in the sentence", () => {
    expect(summarize(cqs, registry)).not.toMatch(/unusual/i);
  });
});
