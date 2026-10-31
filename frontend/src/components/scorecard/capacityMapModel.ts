// capacityMapModel — the one place the capacity map's colors, counts and key are decided (WS8 Phase 1,
// decision Item 41). Pure: the component and the tests read the same model, so what is drawn, what is counted
// and what the key says cannot disagree (the discoveryMapModel pattern).
//
// The backend decides every state and confidence (`/api/capacity-map`, backend/capacity_map.py); this module only
// maps them to paint. Rules:
//   - only `computable` polygons with a utilization get a bin color;
//   - every other state is drawn in one neutral fill and named in the key with its count (never read as low);
//   - `apparently_overbuilt` is neutral with a warning outline: flagged, never ranked;
//   - `low` confidence = half fill alpha + dashed outline;
//   - a `withheld` or `unavailable` view draws no bins at all (the backend already sends no utilization).
import type { MapTheme } from "../../lib/mapColors";

export type CapacityState =
  | "no_zoning" | "planned_development" | "condo_building" | "exempt" | "no_allowed_far" | "unknown_land"
  | "suspect_land" | "class_conflict" | "vacant_land" | "multi_pin_member" | "unknown_gfa"
  | "apparently_overbuilt" | "no_base_row" | "split_zoning" | "unchecked" | "computable";

export type CapacityVerdict = "standard" | "low" | "withheld" | "unavailable";

export interface CapacityFeatureProps {
  pin10: string;
  pin: string | null;
  address?: string | null;
  state: CapacityState;
  existing_far: number | null;
  allowed_far: number | null;
  utilization: number | null;
  zone_class: string | null;
  confidence: "standard" | "low" | "withheld";
  reason: string | null;
  subject?: boolean;
}

export interface CapacityMapResponse {
  subject?: { pin10: string | null; lat: number; lon: number };
  radius_mi: number;
  features: GeoJSON.FeatureCollection<GeoJSON.Geometry, CapacityFeatureProps>;
  summary: {
    polygons: number;
    colorable: number;
    colorable_share: number;
    verdict: CapacityVerdict;
    states: Partial<Record<CapacityState, number>>;
  };
  sources?: {
    index?: { built_at?: string };
    commercial_valuation?: { year?: string | null };
  };
  unchecked: string[];
  reason?: string;
}

export type BinKey = "under25" | "25to50" | "50to80" | "over80";

// Upper bounds of each bin (utilization = built floor area / allowed floor area).
export const BIN_EDGES: Array<{ key: BinKey; below: number }> = [
  { key: "under25", below: 0.25 },
  { key: "25to50", below: 0.5 },
  { key: "50to80", below: 0.8 },
  { key: "over80", below: Infinity },
];

type RGBA = [number, number, number, number];

// One orange ramp (brand series 1), light to deep: more of the allowance built reads darker in light mode and
// brighter in dark mode, so "most built" is the strongest mark in both themes.
const BIN_COLORS: Record<MapTheme, Record<BinKey, RGBA>> = {
  light: {
    under25: [254, 226, 205, 220],
    "25to50": [251, 182, 135, 220],
    "50to80": [236, 124, 60, 220],
    over80: [176, 72, 18, 225],
  },
  dark: {
    under25: [92, 52, 30, 220],
    "25to50": [160, 86, 44, 220],
    "50to80": [222, 128, 72, 225],
    over80: [255, 186, 140, 235],
  },
};

const NEUTRAL: Record<MapTheme, RGBA> = { light: [150, 150, 150, 70], dark: [140, 140, 140, 60] };
const NEUTRAL_LINE: Record<MapTheme, RGBA> = { light: [120, 120, 120, 160], dark: [150, 150, 150, 150] };
const WARNING_LINE: Record<MapTheme, RGBA> = { light: [180, 83, 9, 255], dark: [251, 191, 36, 255] };
export const SUBJECT_LINE: RGBA = [249, 164, 116, 255];

// The order the key lists the uncolored states in (most common reasons first is not stable; this is).
export const UNCOLORED_ORDER: CapacityState[] = [
  "unknown_gfa", "multi_pin_member", "condo_building", "planned_development", "exempt", "vacant_land",
  "no_allowed_far", "split_zoning", "apparently_overbuilt", "class_conflict", "unknown_land", "suspect_land",
  "no_base_row", "no_zoning", "unchecked",
];

export function binOf(utilization: number): BinKey {
  return BIN_EDGES.find((b) => utilization < b.below)!.key;
}

export interface DrawnFeature {
  feature: GeoJSON.Feature<GeoJSON.Geometry, CapacityFeatureProps>;
  fill: RGBA;
  line: RGBA;
  dashed: boolean;
  bin: BinKey | null;
}

export interface CapacityKeyRow {
  key: string;
  kind: "bin" | "state";
  count: number;
  swatchCSS: string;
  outlineCSS?: string;
}

export interface CapacityMapModel {
  drawn: DrawnFeature[];
  subject: DrawnFeature | null;
  bins: CapacityKeyRow[];
  uncolored: CapacityKeyRow[];
  total: number;
  colored: number;
  share: number;
  verdict: CapacityVerdict;
  /** Bins are drawn only for a standard or low view. */
  binsDrawn: boolean;
}

const css = (c: RGBA) => `rgba(${c[0]},${c[1]},${c[2]},${(c[3] / 255).toFixed(2)})`;

export function buildCapacityMapModel(resp: CapacityMapResponse | null, theme: MapTheme): CapacityMapModel {
  const features = resp?.features?.features ?? [];
  const verdict: CapacityVerdict = resp?.summary?.verdict ?? "unavailable";
  const binsDrawn = verdict === "standard" || verdict === "low";
  const binCounts: Record<BinKey, number> = { under25: 0, "25to50": 0, "50to80": 0, over80: 0 };
  const stateCounts = new Map<CapacityState, number>();
  const drawn: DrawnFeature[] = [];
  let subject: DrawnFeature | null = null;
  for (const feature of features) {
    const p = feature.properties;
    const colorable = binsDrawn && p.state === "computable" && p.utilization != null;
    const bin = colorable ? binOf(p.utilization!) : null;
    let fill = bin ? BIN_COLORS[theme][bin] : NEUTRAL[theme];
    const low = p.confidence === "low";
    if (low) fill = [fill[0], fill[1], fill[2], Math.round(fill[3] / 2)];
    const line = p.state === "apparently_overbuilt" ? WARNING_LINE[theme] : NEUTRAL_LINE[theme];
    const d: DrawnFeature = { feature, fill, line, dashed: low, bin };
    drawn.push(d);
    if (p.subject) subject = d;
    if (bin) binCounts[bin] += 1;
    else stateCounts.set(p.state, (stateCounts.get(p.state) ?? 0) + 1);
  }
  const bins: CapacityKeyRow[] = binsDrawn
    ? BIN_EDGES.map(({ key }) => ({ key, kind: "bin", count: binCounts[key], swatchCSS: css(BIN_COLORS[theme][key]) }))
    : [];
  const order = [...UNCOLORED_ORDER, "computable" as CapacityState];
  const uncolored: CapacityKeyRow[] = order
    .filter((s) => (stateCounts.get(s) ?? 0) > 0)
    .map((s) => ({
      key: s, kind: "state", count: stateCounts.get(s)!, swatchCSS: css(NEUTRAL[theme]),
      outlineCSS: s === "apparently_overbuilt" ? css(WARNING_LINE[theme]) : undefined,
    }));
  const colored = bins.reduce((n, r) => n + r.count, 0);
  return {
    drawn, subject, bins, uncolored, total: features.length, colored,
    share: features.length ? colored / features.length : 0, verdict, binsDrawn,
  };
}
