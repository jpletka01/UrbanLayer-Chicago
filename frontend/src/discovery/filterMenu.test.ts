import { describe, expect, it } from "vitest";
import { menuGroups } from "./filterMenu";
import type { FilterDef, Registry } from "./types";

const def = (id: string, tier?: "essential" | "more"): FilterDef => ({
  id, category: "property_use", kind: "flag", field: id, unknownPolicy: "exclude", tier,
});

const REGISTRY: Registry = {
  version: "t",
  filters: [def("a_ess", "essential"), def("b_more", "more"), def("c_ess", "essential"), def("d_none"), def("e_dead_ess", "essential"), def("f_dead_more", "more")],
  topics: [],
  sortKeys: [{ key: "pin", field: "pin" }],
  defaultSort: { key: "pin", dir: "asc" },
  broadMinFilters: 2,
  coverage: { mode: "all", liveAreas: [1], asOf: "2026-10-01" },
  populatedFields: ["a_ess", "b_more", "c_ess", "d_none"],
};
const nameOf = (d: FilterDef) => d.id.replace(/_/g, " ");
const ids = (defs: FilterDef[]) => defs.map((d) => d.id);

describe("menuGroups", () => {
  it("splits live filters by tier and keeps registry order inside each group", () => {
    const g = menuGroups(REGISTRY, "", nameOf);
    expect(ids(g.essentials)).toEqual(["a_ess", "c_ess"]);
    expect(ids(g.more)).toEqual(["b_more", "d_none"]); // an absent tier reads as "more"
  });

  it("puts a filter with no data in 'coming soon' whatever its tier", () => {
    const g = menuGroups(REGISTRY, "", nameOf);
    expect(ids(g.soon)).toEqual(["e_dead_ess", "f_dead_more"]);
  });

  it("a data refresh moves a filter out of 'coming soon' with no tier change", () => {
    const g = menuGroups({ ...REGISTRY, populatedFields: [...REGISTRY.populatedFields!, "e_dead_ess"] }, "", nameOf);
    expect(ids(g.essentials)).toEqual(["a_ess", "c_ess", "e_dead_ess"]);
    expect(ids(g.soon)).toEqual(["f_dead_more"]);
  });

  it("searches the localized display name, case-insensitively, across all three groups", () => {
    const g = menuGroups(REGISTRY, "  MORE ", nameOf);
    expect(ids(g.more)).toEqual(["b_more"]);
    expect(g.essentials).toEqual([]);
    expect(ids(menuGroups(REGISTRY, "dead", nameOf).soon)).toEqual(["e_dead_ess", "f_dead_more"]);
    expect(menuGroups(REGISTRY, "zzz", nameOf)).toEqual({ essentials: [], more: [], soon: [] });
  });

  it("with no index at all every filter is 'coming soon' (never a live control that returns nothing)", () => {
    const g = menuGroups({ ...REGISTRY, populatedFields: [] }, "", nameOf);
    expect(g.essentials).toEqual([]);
    expect(g.more).toEqual([]);
    expect(g.soon).toHaveLength(6);
  });
});
