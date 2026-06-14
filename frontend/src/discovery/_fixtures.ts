// Shared test fixture registry.
import type { Registry } from "./types";

export const REG: Registry = {
  version: "v1",
  filters: [
    {
      id: "land_use", category: "property_use", kind: "enum", field: "land_use_class",
      unknownPolicy: "exclude", enumValues: ["residential", "multi_family"],
    },
    { id: "tif", category: "incentives", kind: "flag", field: "in_tif_district", unknownPolicy: "exclude" },
    {
      id: "lot_size", category: "property_use", kind: "range", field: "land_sqft",
      unknownPolicy: "exclude", unit: "sqft",
    },
  ],
  topics: [
    {
      id: "vacant_mf",
      presets: {
        land_use: { kind: "enum", values: ["multi_family"] },
        tif: { kind: "flag", value: true },
      },
    },
  ],
  sortKeys: [
    { key: "pin", field: "pin" },
    { key: "lot_size", field: "land_sqft" },
  ],
  defaultSort: { key: "pin", dir: "asc" },
  broadMinFilters: 2,
};
