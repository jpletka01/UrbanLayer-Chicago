import { describe, expect, it } from "vitest";
import { buildScorecardCSV } from "./csvExport";
import type { ContextObject } from "./types";

describe("buildScorecardCSV demographics (WS0 M1)", () => {
  it("exports only the community-area fields we hold, and no percentage over 100", () => {
    // An old stored context: the retired fields are present and percentage-scaled
    // (4.6 = 4.6%). The old export multiplied them by 100 → "460.0%".
    const ctx = {
      neighborhood: {
        demographics: {
          community_area: 24, community_area_name: "West Town", population: 87781,
          median_household_income: 82000, acs_period: "2019–2023",
          poverty_rate: 4.6, owner_occupied_pct: 35.7, bachelors_degree_pct: 58.3,
        },
      },
    } as unknown as ContextObject;
    const csv = buildScorecardCSV(ctx, "1601 N Milwaukee Ave");
    expect(csv).toContain("ACS Period");
    expect(csv).toContain("2019–2023");
    expect(csv).toContain("estimated from 5 brackets");
    expect(csv).not.toMatch(/Poverty|Owner Occupied|Bachelor/);
    const pcts = [...csv.matchAll(/(\d+(?:\.\d+)?)%/g)].map((m) => Number(m[1]));
    expect(pcts.every((p) => p <= 100)).toBe(true);
  });
});
