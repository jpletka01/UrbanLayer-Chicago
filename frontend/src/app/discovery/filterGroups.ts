// The filters as groups with plain-language choices (owner's review, 2026-11-10; decision Item 104). Presentation
// only: every choice compiles to a registry predicate the server evaluates (INV-1). Technical names (FAR, the
// registry's labels) appear in small print, never as the choice itself.
import type { LucideIcon } from "lucide-react";
import {
  Bird, Building, Building2, Factory, Gift, Hotel, House, Hourglass, Landmark, LandPlot, Maximize2,
  Receipt, Ruler, Shovel, Sprout, SquareParking, Square, Store, TrainFront, TrendingDown, Warehouse,
} from "lucide-react";
import { isPopulated } from "../../discovery/coverage";
import type { Predicate, Registry } from "../../discovery/types";

export type GroupId = "lot" | "zoning" | "building" | "transit" | "money" | "incentives";

export interface Choice {
  /** i18n key under `discovery.choice.<filter>.<id>` (name, hint). */
  id: string;
  icon: LucideIcon;
  predicate: Predicate;
}

export interface FilterSpec {
  filter: string;
  icon: LucideIcon;
  /** "cards": pick one (a range or enum value per card); "multi": enum values, several; "toggle": a flag on/off;
      "walk": the transit slider. */
  kind: "cards" | "multi" | "toggle" | "walk";
  choices?: Choice[];
}

export interface GroupSpec { id: GroupId; icon: LucideIcon; filters: FilterSpec[] }

const range = (min?: number, max?: number): Predicate => ({ kind: "range", ...(min != null ? { min } : {}), ...(max != null ? { max } : {}) });
const yes: Predicate = { kind: "flag", value: true };

// Base-district FAR, read as "about N stories' worth" over the whole lot: RS 0.65-0.9, RT/RM-4.5 1.05-1.7,
// RM-5/RM-6 and most B/C 2-4.4, downtown and RM-6.5+ 5 and up.
export const INTENSITY: Choice[] = [
  { id: "houses", icon: House, predicate: range(undefined, 1) },
  { id: "flats", icon: Building, predicate: range(1, 2) },
  { id: "apartments", icon: Building2, predicate: range(2, 5) },
  { id: "towers", icon: Hotel, predicate: range(5) },
];

export const GROUPS: GroupSpec[] = [
  { id: "lot", icon: Square, filters: [
    { filter: "empty_land", icon: Sprout, kind: "toggle" },  // physically empty, not the tax class (Item 110)
    { filter: "surface_parking", icon: SquareParking, kind: "toggle" },  // a parking lot with no building (Item 112)
    { filter: "room_to_build", icon: Maximize2, kind: "cards", choices: [
      { id: "some", icon: Maximize2, predicate: range(2500) },
      { id: "more", icon: Maximize2, predicate: range(5000) },
      { id: "lots", icon: Maximize2, predicate: range(10000) },
    ] },
    { filter: "lot_size", icon: Ruler, kind: "cards", choices: [
      { id: "small", icon: Square, predicate: range(undefined, 2500) },
      { id: "standard", icon: Square, predicate: range(2500, 5000) },
      { id: "double", icon: Square, predicate: range(5000, 10000) },
      { id: "large", icon: LandPlot, predicate: range(10000) },
    ] },
  ] },
  { id: "zoning", icon: LandPlot, filters: [
    { filter: "zoning_group", icon: LandPlot, kind: "multi", choices: [
      { id: "residential", icon: House, predicate: { kind: "enum", values: ["residential"] } },
      { id: "business", icon: Store, predicate: { kind: "enum", values: ["business"] } },
      { id: "commercial", icon: Store, predicate: { kind: "enum", values: ["commercial"] } },
      { id: "manufacturing", icon: Factory, predicate: { kind: "enum", values: ["manufacturing"] } },
      { id: "downtown", icon: Hotel, predicate: { kind: "enum", values: ["downtown"] } },
      { id: "planned_development", icon: Landmark, predicate: { kind: "enum", values: ["planned_development"] } },
    ] },
    { filter: "density_band", icon: Building2, kind: "cards", choices: INTENSITY },
  ] },
  { id: "building", icon: Building2, filters: [
    { filter: "land_use", icon: Building2, kind: "multi", choices: [
      { id: "residential", icon: House, predicate: { kind: "enum", values: ["residential"] } },
      { id: "multi_family", icon: Building, predicate: { kind: "enum", values: ["multi_family"] } },
      { id: "commercial", icon: Store, predicate: { kind: "enum", values: ["commercial"] } },
      { id: "industrial", icon: Warehouse, predicate: { kind: "enum", values: ["industrial"] } },
      { id: "vacant", icon: Sprout, predicate: { kind: "enum", values: ["vacant"] } },
    ] },
    { filter: "is_teardown_candidate", icon: Shovel, kind: "toggle" },
    { filter: "year_built", icon: Hourglass, kind: "cards", choices: [
      { id: "pre1920", icon: Hourglass, predicate: range(undefined, 1919) },
      { id: "1920to1979", icon: Hourglass, predicate: range(1920, 1979) },
      { id: "since1980", icon: Hourglass, predicate: range(1980) },
    ] },
    { filter: "building_size", icon: Building, kind: "cards", choices: [
      { id: "small", icon: House, predicate: range(undefined, 2500) },
      { id: "medium", icon: Building, predicate: range(2500, 10000) },
      { id: "large", icon: Building2, predicate: range(10000) },
    ] },
  ] },
  { id: "transit", icon: TrainFront, filters: [{ filter: "transit_proximity", icon: TrainFront, kind: "walk" }] },
  { id: "money", icon: Receipt, filters: [
    { filter: "sale_recency", icon: Receipt, kind: "cards", choices: [
      { id: "6mo", icon: Receipt, predicate: range(undefined, 183) },
      { id: "1y", icon: Receipt, predicate: range(undefined, 365) },
      { id: "2y", icon: Receipt, predicate: range(undefined, 730) },
      { id: "5y", icon: Receipt, predicate: range(undefined, 1825) },
    ] },
    { filter: "last_sale_price", icon: Receipt, kind: "cards", choices: [
      { id: "under250k", icon: TrendingDown, predicate: range(10000, 250000) },
      { id: "under500k", icon: Receipt, predicate: range(10000, 500000) },
      { id: "under1m", icon: Receipt, predicate: range(10000, 1000000) },
    ] },
  ] },
  { id: "incentives", icon: Gift, filters: [
    { filter: "tif", icon: Gift, kind: "toggle" },
    { filter: "enterprise_zone", icon: Gift, kind: "toggle" },
    { filter: "opportunity_zone", icon: Bird, kind: "toggle" },
  ] },
];

/** Every filter a group shows (so the group's count and Clear know which panel keys are theirs). */
export const groupFilters = (g: GroupSpec) => g.filters.map((f) => f.filter);

export const sameChoice = (a: Predicate | undefined, b: Predicate): boolean => {
  if (!a || a.kind !== b.kind) return false;
  if (a.kind === "range" && b.kind === "range") return (a.min ?? null) === (b.min ?? null) && (a.max ?? null) === (b.max ?? null);
  if (a.kind === "flag" && b.kind === "flag") return a.value === b.value;
  return false;
};

/** Minutes of walking to the nearest L stop -> miles (20 minutes a mile), and back. */
export const WALK_MIN = 1;
export const WALK_MAX = 20;
export const walkMiles = (minutes: number) => Math.round((minutes / 20) * 100) / 100;
export const walkMinutes = (miles: number) => Math.round(miles * 20);

export { yes as FLAG_YES };

/** The groups that have at least one filter with data in this index. */
export function liveGroups(registry: Registry): GroupSpec[] {
  return GROUPS
    .map((g) => ({ ...g, filters: g.filters.filter((f) => isPopulated(registry, f.filter)) }))
    .filter((g) => g.filters.length > 0);
}
