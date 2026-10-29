import { describe, expect, it } from "vitest";
import {
  diffDraft,
  inputsSignature,
  reconcileWithResponse,
  removeFromDraft,
  restoreToDraft,
  type DiscoveryDraft,
} from "./draftModel";
import type { CQS } from "./types";

const SORT = { key: "pin", dir: "asc" as const };

function cqs(filters: CQS["filters"], sort = SORT): CQS {
  return { filters, sort, scope: { mode: "all" }, meta: {} };
}

const APPLIED = cqs({
  land_use: { predicate: { kind: "enum", values: ["residential", "multi_family"] }, source: "user" },
  tif: { predicate: { kind: "flag", value: true }, source: "user" },
  lot_size: { predicate: { kind: "range", min: 3000 }, source: "text" },
});

function draft(over: Partial<DiscoveryDraft> = {}): DiscoveryDraft {
  return {
    panelState: {
      land_use: { kind: "enum", values: ["multi_family", "residential"] }, // same set, other order
      tif: { kind: "flag", value: true },
    },
    text: "lots over 3000",
    sort: SORT,
    topicId: null,
    ...over,
  };
}

describe("diffDraft", () => {
  it("reports no pending change for a draft equal to the evaluated query", () => {
    const { chips, pendingCount } = diffDraft(draft(), APPLIED, "lots over 3000");
    expect(pendingCount).toBe(0);
    expect(chips.map((c) => c.state)).toEqual(["applied", "applied", "applied"]);
  });

  it("returns no chips before anything has been evaluated", () => {
    expect(diffDraft(draft(), null, "")).toEqual({ chips: [], pendingCount: 0 });
  });

  it("counts removed, added and changed filters, and a changed sort", () => {
    const d = draft({
      panelState: {
        land_use: { kind: "enum", values: ["residential"] }, // changed
        overlay: { kind: "flag", value: true }, // added
        // tif removed
      },
      sort: { key: "lot_size", dir: "desc" },
    });
    const { chips, pendingCount } = diffDraft(d, APPLIED, "lots over 3000");
    const byId = Object.fromEntries(chips.map((c) => [c.id, c.state]));
    expect(byId).toEqual({
      land_use: "changed",
      lot_size: "applied", // carried from the text, still there
      overlay: "added",
      tif: "removed",
    });
    expect(pendingCount).toBe(4); // changed + added + removed + sort
  });

  it("counts changed text once and keeps the carried chips until it is evaluated", () => {
    const { chips, pendingCount } = diffDraft(draft({ text: "something else" }), APPLIED, "lots over 3000");
    expect(chips.find((c) => c.id === "lot_size")?.state).toBe("applied");
    expect(pendingCount).toBe(1);
  });

  it("shows emptied text as the carried filters being removed, not as an extra text change", () => {
    const { chips, pendingCount } = diffDraft(draft({ text: "" }), APPLIED, "lots over 3000");
    expect(chips.find((c) => c.id === "lot_size")?.state).toBe("removed");
    expect(pendingCount).toBe(1);
  });
});

describe("removeFromDraft / restoreToDraft", () => {
  it("removing a panel filter touches only the panel", () => {
    const next = removeFromDraft(draft(), APPLIED, "lots over 3000", "tif");
    expect(Object.keys(next.panelState)).toEqual(["land_use"]);
    expect(next.text).toBe("lots over 3000");
  });

  it("removing a text-derived chip folds the evaluated query into the panel and drops the text", () => {
    const next = removeFromDraft(draft(), APPLIED, "lots over 3000", "lot_size");
    expect(Object.keys(next.panelState).sort()).toEqual(["land_use", "tif"]);
    expect(next.text).toBe("");
    // and nothing is left that would re-add the removed chip
    expect(diffDraft(next, APPLIED, "lots over 3000").pendingCount).toBe(1);
  });

  it("keeps newly typed text when a carried chip is removed", () => {
    const next = removeFromDraft(draft({ text: "new words" }), APPLIED, "lots over 3000", "lot_size");
    expect(next.text).toBe("new words");
    expect(next.panelState.lot_size).toBeUndefined();
  });

  it("restores an evaluated filter with one call", () => {
    const removed = removeFromDraft(draft(), APPLIED, "lots over 3000", "tif");
    const restored = restoreToDraft(removed, APPLIED, "tif");
    expect(restored.panelState.tif).toEqual({ kind: "flag", value: true });
    expect(diffDraft(restored, APPLIED, "lots over 3000").pendingCount).toBe(0);
  });
});

describe("reconcileWithResponse / inputsSignature", () => {
  it("keeps only the user-sourced filters the server evaluated", () => {
    const d = reconcileWithResponse(draft(), APPLIED);
    expect(Object.keys(d.panelState).sort()).toEqual(["land_use", "tif"]);
  });

  it("signs equal inputs identically regardless of order, and different ones differently", () => {
    const a = inputsSignature(draft());
    const b = inputsSignature({
      ...draft(),
      panelState: {
        tif: { kind: "flag", value: true },
        land_use: { kind: "enum", values: ["residential", "multi_family"] },
      },
    });
    expect(a).toBe(b);
    expect(inputsSignature(draft({ text: "x" }))).not.toBe(a);
  });
});
