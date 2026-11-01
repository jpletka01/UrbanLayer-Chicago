// Which provenance facts each Profile section's Sources sheet lists (decision Item 51).
import type { Provenance } from "./api";

export type SourceScope = "build" | "economics" | "market" | "record" | "area" | "all";

/** Which fact ids each section's Sources list shows (by id prefix). */
export function factsFor(scope: SourceScope, provenance: Record<string, Provenance>): string[] {
  const ids = Object.keys(provenance).sort();
  const is = (id: string, prefixes: string[]) => prefixes.some((p) => id === p || id.startsWith(`${p}.`));
  switch (scope) {
    case "build": return ids.filter((id) => is(id, ["zoning", "overlay", "code", "capacity", "upcoming", "pending", "incentive.aro"]));
    case "economics": return ids.filter((id) => is(id, ["property", "incentive"]) && !is(id, ["property.comps", "property.sales", "property.311", "property.violations", "incentive.aro"]));
    case "market": return ids.filter((id) => is(id, ["property.comps", "property.sales"]));
    case "record": return ids.filter((id) => is(id, ["property.311", "property.violations", "regulatory"]));
    case "area": return ids.filter((id) => is(id, ["area", "neighborhood", "geo"]));
    default: return ids;
  }
}
