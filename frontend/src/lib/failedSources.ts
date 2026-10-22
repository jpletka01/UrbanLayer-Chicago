// What the Profile couldn't check, by module (WS6 M7). The backend (`backend/data_health/failures.py`) names
// each failed source and the words that reported it; this places it in the module whose figures it left out,
// so that module says so instead of going quiet ("nothing here"). The module ids are the page's own
// (`module-<name>`); a backend test pins this table to `failures.MODULES`.

export interface FailedSource {
  key: string;
  /** The words that reported it, e.g. "property tax estimate" for a gap inside records that otherwise answered. */
  labels: string[];
}

export type ProfileModuleName = "build" | "economics" | "market" | "record" | "area";

export const MODULE_OF: Readonly<Record<string, ProfileModuleName>> = {
  zoning: "build", regulatory: "build", adjacent_zoning: "build",
  property: "economics", incentives: "economics",
  comparables: "market", nearby_construction: "market",
  violations: "record", address_311: "record", address_permits: "record", address_violations: "record",
  crime: "area", crime_yoy: "area", neighborhood: "area", aro_housing: "area", "311": "area",
  permits: "area", business: "area", vacant: "area", food_inspections: "area",
};

/** The failed sources whose figures belong to ``module``. */
export function failedIn(failed: readonly FailedSource[] | null | undefined, module: ProfileModuleName): FailedSource[] {
  return (failed ?? []).filter((f) => MODULE_OF[f.key] === module);
}

/** Every label that reported a failure in ``module``, once each. */
export function failedLabels(failed: readonly FailedSource[] | null | undefined, module: ProfileModuleName): string[] {
  return [...new Set(failedIn(failed, module).flatMap((f) => f.labels))];
}

/** The City's own zoning map: where to look up a district or an overlay yourself when ours couldn't. */
export const ZONING_MAP_URL = "https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning";
