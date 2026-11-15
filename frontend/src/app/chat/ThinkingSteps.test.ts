import { describe, expect, it } from "vitest";
import { STEP_PACE_S, stepsAt } from "./ThinkingSteps";
import type { ActivityItem } from "../../lib/types";

const planned: ActivityItem[] = [
  { id: "routing", label: "Analyzed your question", status: "done" },
  { id: "location", label: "Located Lincoln Park", status: "done" },
  { id: "retrieve_zoning", label: "Zoning in Lincoln Park", status: "active" },
  { id: "retrieve_crime_api", label: "Crime in Lincoln Park", status: "active" },
  { id: "retrieve_permits_api", label: "Permits in Lincoln Park", status: "active" },
];

describe("the thinking steps", () => {
  it("reveals the planned lookups one at a time, the latest current, none checked early", () => {
    const at = (s: number) => stepsAt(planned, s).map((x) => `${x.id}:${x.state}`);
    expect(at(0)).toEqual(["routing:done", "location:done", "retrieve_zoning:current"]);
    expect(at(STEP_PACE_S + 0.1)).toEqual(["routing:done", "location:done", "retrieve_zoning:done", "retrieve_crime_api:current"]);
    // However long it takes, the last lookup stays current until the records arrive.
    expect(at(999).slice(-1)).toEqual(["retrieve_permits_api:current"]);
  });

  it("checks every lookup when the records arrive and moves on to writing", () => {
    const fetched: ActivityItem[] = [...planned.map((a) => ({ ...a, status: "done" as const })), { id: "synthesis", label: "Composing response…", status: "active" }];
    expect(stepsAt(fetched, 1).map((x) => `${x.id}:${x.state}`)).toEqual([
      "routing:done", "location:done", "retrieve_zoning:done", "retrieve_crime_api:done", "retrieve_permits_api:done", "synthesis:current",
    ]);
  });
});
