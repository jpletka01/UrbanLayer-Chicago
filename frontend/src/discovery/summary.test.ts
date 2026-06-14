import { describe, expect, it } from "vitest";
import { summarize } from "./summary";
import { REG } from "./_fixtures";
import type { CQS } from "./types";

const cqs: CQS = {
  filters: {
    land_use: { predicate: { kind: "enum", values: ["multi_family"] }, source: "user" },
    tif: { predicate: { kind: "flag", value: true }, source: "text" },
  },
  sort: { key: "lot_size", dir: "desc" },
  scope: { mode: "all" },
  meta: {},
};

describe("summarize", () => {
  it("renders plain-English from the CQS (ids sorted, with sort clause)", () => {
    expect(summarize(cqs, REG)).toBe(
      "Parcels where land use: multi family; tif, sorted by lot size (descending).",
    );
  });

  it("describes an empty CQS as all parcels", () => {
    const empty: CQS = { filters: {}, sort: { key: "pin", dir: "asc" }, scope: { mode: "all" }, meta: {} };
    expect(summarize(empty, REG)).toBe("All parcels, sorted by pin (ascending).");
  });

  it("is deterministic regardless of source/meta", () => {
    const a = summarize(cqs, REG);
    const b = summarize({ ...cqs, meta: { topicId: "x", rawText: "y" } }, REG);
    expect(a).toBe(b);
  });

  it("names neighborhood regions (West Town, not neighborhood:24)", () => {
    const c: CQS = {
      filters: {
        neighborhood: { predicate: { kind: "region", regions: ["neighborhood:24"] }, source: "user" },
      },
      sort: { key: "pin", dir: "asc" },
      scope: { mode: "all" },
      meta: {},
    };
    const s = summarize(c, REG);
    expect(s).toContain("West Town");
    expect(s).not.toContain("neighborhood:24");
  });
});
